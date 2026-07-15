"""
新品 / 新型号对比工具（native function-calling tool）

新增一个供 LLM 自主调用的工具 `get_new_and_newer_models`:

    入参: keyword（型号名，如 "AirPods Pro" / "Bambu A1 mini"）
    出参(紧凑 JSON):
      {
        "searched_model": {"name", "new_price_min", "source"},
        "newer_models":   [{"name", "new_price_min", "note"}, ...],
        "currency": "JPY"
      }
    取不到数据时返回 {"keyword", "note": "未获取到新品/新型号数据", "currency": "JPY"}（不崩）。

后端按调研落地,两级 backend,依次尝试(第一个给出结果者胜):
  1) KakakuBackend —— httpx 裸抓 kakaku(shift_jis),读搜索页目录机型 + 各机型新品最安値。
     仅当该商品在 kakaku 比价目录内(搜索结果行含 /item/K.../)时命中;否则返回 None 让下一级接手。
  2) BrandStoreBackend —— 对非目录/品牌直营商品(如 Bambu Lab 3D 打印机),用 LineupFinder
     渲染官方商店商品页,从 JSON-LD Offer 取新品价。品牌 → URL 由内置 adapter 表提供
     (Stage-1 发现是 agent 的 WebSearch 职责;本工具内置已验证过的少量电子品类 adapter)。

合规克制:kakaku/官网低频取数、带浏览器 UA、请求间加延时、单商品少量请求。

Author: Kaidoki Team (model compare feature)
"""

import asyncio
import html
import re
import urllib.parse as urlparse
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .framework.base_tool import BaseTool, ToolResult, ToolStatus
from ..infrastructure.scraping.lineup_finder import LineupFinder
from ..shared.utils.logger_utils import get_logger

logger = get_logger(__name__)

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)
_HEADERS = {"User-Agent": _UA, "Accept-Language": "ja-JP,ja;q=0.9"}

_NO_DATA_NOTE = "未获取到新品/新型号数据"


def _tokens(keyword: str) -> List[str]:
    """把关键词切成有意义的小写 token(长度>=2 或纯数字,去标点)。"""
    raw = re.split(r"\s+", (keyword or "").strip().lower())
    out: List[str] = []
    for t in raw:
        t = re.sub(r"[^0-9a-z぀-ヿ一-鿿]", "", t)
        if len(t) >= 2 or t.isdigit():
            out.append(t)
    return out


# --------------------------------------------------------------------------- #
# Backend 1: kakaku（目录内电子品 = 行）
# --------------------------------------------------------------------------- #
class KakakuBackend:
    """从 kakaku 搜索页取同关键词下的目录机型 + 各机型新品最安値。"""

    def __init__(self, delay_seconds: float = 2.0, timeout: float = 25.0, max_newer: int = 8):
        self.delay_seconds = delay_seconds
        self.timeout = timeout
        self.max_newer = max_newer

    async def _fetch_text(self, url: str) -> str:
        """抓 kakaku 页面并按 shift_jis 解码(kakaku 是 shift_jis,不能用默认 r.text)。"""
        async with httpx.AsyncClient(
            headers=_HEADERS, timeout=self.timeout, follow_redirects=True
        ) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.content.decode("shift_jis", errors="replace")

    @staticmethod
    def _clean(s: str) -> str:
        return html.unescape(re.sub(r"<[^>]+>|\s+", " ", s)).strip()

    def _parse_search(self, text: str) -> List[Dict[str, Any]]:
        """解析搜索页,返回目录机型列表(页面顺序=最新在前)。"""
        models: List[Dict[str, Any]] = []
        for b in re.split(r'(?=<div class="p-resultItem_in p-item)', text)[1:]:
            k = re.search(r"/item/(K\d+)/", b)
            if not k:  # 无 /item/K.../ = 购物列表(单店),不是目录机型,跳过
                continue
            nm = re.search(r'class="p-item_name">\s*<a[^>]*>(.*?)</a>', b, re.S)
            name = self._clean(nm.group(1)) if nm else None
            pr = re.search(r'class="p-item_priceNum[^"]*">([\d,]+)', b)
            lowest = int(pr.group(1).replace(",", "")) if pr else None
            if name:
                models.append({"kcode": k.group(1), "name": name, "lowest": lowest})
        return models

    @staticmethod
    def _split(keyword: str, models: List[Dict[str, Any]]):
        """在目录机型里定位被搜机型,并挑出比它新的同线机型(用页面 newest-first 顺序)。"""
        kw = _tokens(keyword)
        if not kw:
            return None, []

        def matches(m) -> int:
            nm = (m["name"] or "").lower()
            return sum(1 for t in kw if t in nm)

        candidates = [m for m in models if matches(m) > 0]
        if not candidates:
            return None, []

        def score(m):
            nm = (m["name"] or "").lower()
            leftover = nm
            for t in kw:
                leftover = leftover.replace(t, "")
            # 命中 token 越多越好；命中后剩余字符越少越"就是这个型号本体"
            return (matches(m), -len(re.sub(r"\W", "", leftover)))

        searched = max(candidates, key=score)
        idx = models.index(searched)

        # 家族锚点:最长的字母 token(如 "airpods"),用于把"新型号"限定在同一产品线
        alpha = [t for t in kw if not t.isdigit()]
        fam = max(alpha, key=len) if alpha else (kw[0] if kw else "")
        newer = [
            m for m in models[:idx]  # 页面里排在被搜机型之前 = 更新
            if fam and fam in (m["name"] or "").lower() and m is not searched
        ]
        return searched, newer

    async def lookup(self, keyword: str) -> Optional[Dict[str, Any]]:
        url = f"https://search.kakaku.com/{urlparse.quote(keyword)}/"
        try:
            text = await self._fetch_text(url)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"kakaku 取数失败: {e}")
            return None
        await asyncio.sleep(self.delay_seconds)  # 克制

        models = self._parse_search(text)
        if not models:  # 非目录商品(如 Bambu)——交给下一级 backend
            return None
        searched, newer = self._split(keyword, models)
        if searched is None:
            return None

        return {
            "searched_model": {
                "name": searched["name"],
                "new_price_min": searched["lowest"],
                "source": "kakaku.com",
            },
            "newer_models": [
                {
                    "name": m["name"],
                    "new_price_min": m["lowest"],
                    "note": "kakaku 同线目录机型(新品最安値,页面顺序更新在前)",
                }
                for m in newer[: self.max_newer]
            ],
            "currency": "JPY",
        }


# --------------------------------------------------------------------------- #
# Backend 2: 品牌官方商店（非目录/直营 = kakaku 拿不到时的 fallback）
# --------------------------------------------------------------------------- #
# 每条 adapter:matcher 命中关键词 → 该产品线机型列表(newest-first,带官方商品页 URL)。
# newer = 命中的被搜机型之前(更新)、且同 series 的机型。区域固定 JP 商店 → JPY。
_BRAND_ADAPTERS: List[Dict[str, Any]] = [
    {
        "brand": "Bambu Lab",
        "match": re.compile(
            r"bambu|\ba2l\b|\ba1\s*mini\b|\ba1\b|\bp1s\b|\bp2s\b|\bx1c\b|\bh2[dsc]\b",
            re.I,
        ),
        # key 用于匹配被搜机型(长 key 优先);series+gen 用于判定"更新的同线机型"
        "lineup": [
            {"key": "a2l", "name": "Bambu Lab A2L",
             "url": "https://us.store.bambulab.com/products/a2l",
             "series": "A", "gen": 2,
             "note": "A 系列大幅面新机型,2026-06 发布(官方称为增补款而非直接替代)"},
            {"key": "a1 mini", "name": "Bambu Lab A1 mini",
             "url": "https://us.store.bambulab.com/products/a1-mini",
             "series": "A", "gen": 1},
            {"key": "a1", "name": "Bambu Lab A1",
             "url": "https://us.store.bambulab.com/products/a1",
             "series": "A", "gen": 1},
        ],
    },
    {
        "brand": "Apple AirPods",
        "match": re.compile(r"airpods\s*pro", re.I),
        "lineup": [
            {"key": "airpods pro 3", "name": "AirPods Pro 3",
             "url": "https://www.apple.com/jp/shop/buy-airpods/airpods-pro-3",
             "series": "AirPodsPro", "gen": 3,
             "note": "AirPods Pro 现行最新一代"},
            {"key": "airpods pro 2", "name": "AirPods Pro 2",
             "url": "https://www.apple.com/jp/shop/buy-airpods/airpods-pro",
             "series": "AirPodsPro", "gen": 2},
        ],
    },
]


class BrandStoreBackend:
    """品牌官方商店取价(Playwright 渲染 + JSON-LD),用于 kakaku 不收录的商品。"""

    def __init__(self, lineup_finder: LineupFinder, delay_seconds: float = 2.0):
        self.finder = lineup_finder
        self.delay_seconds = delay_seconds

    @staticmethod
    def _resolve(keyword: str):
        """关键词 → (adapter, searched_entry, newer_entries[])。"""
        kw = keyword.lower()
        for ad in _BRAND_ADAPTERS:
            if not ad["match"].search(keyword):
                continue
            lineup = ad["lineup"]
            # 长 key 优先(先匹配 "a1 mini" 再 "a1"),命中被搜机型
            searched = None
            for entry in sorted(lineup, key=lambda e: -len(e["key"])):
                if entry["key"] in kw:
                    searched = entry
                    break
            if searched is None:
                # 关键词命中品牌但没锁定具体机型:取最新一代作被搜机型
                searched = max(lineup, key=lambda e: e["gen"])
            newer = [
                e for e in lineup
                if e is not searched
                and e["series"] == searched["series"]
                and e["gen"] > searched["gen"]
            ]
            newer.sort(key=lambda e: -e["gen"])
            return ad, searched, newer
        return None, None, []

    async def _price_of(self, entry: Dict[str, Any]) -> Tuple[Optional[int], Optional[str]]:
        try:
            data = await self.finder.render(entry["url"])
        except Exception as e:  # noqa: BLE001
            logger.warning(f"官方页渲染失败 {entry['url']}: {e}")
            return None, None
        if data.get("status") != 200:
            logger.warning(f"官方页非 200 {entry['url']}: status={data.get('status')}")
            return None, None
        price, _src, currency = self.finder.min_offer(data)
        return price, currency

    async def lookup(self, keyword: str) -> Optional[Dict[str, Any]]:
        ad, searched, newer = self._resolve(keyword)
        if searched is None:
            return None  # 无对应品牌 adapter

        s_price, s_cur = await self._price_of(searched)
        newer_out: List[Dict[str, Any]] = []
        currency = s_cur
        for entry in newer:
            await asyncio.sleep(self.delay_seconds)  # 克制:请求间延时
            n_price, n_cur = await self._price_of(entry)
            currency = currency or n_cur
            newer_out.append(
                {
                    "name": entry["name"],
                    "new_price_min": n_price,
                    "note": entry.get("note") or f"{ad['brand']} 同线更新机型",
                }
            )

        return {
            "searched_model": {
                "name": searched["name"],
                "new_price_min": s_price,
                "source": urlparse.urlparse(searched["url"]).netloc,
            },
            "newer_models": newer_out,
            "currency": currency or "JPY",
        }


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #
class GetNewAndNewerModelsTool(BaseTool):
    """给定型号名,返回该型号的新品最安値 + 同线更新型号(及新品价)。"""

    def __init__(self, backends: List[Any]):
        super().__init__(
            name="get_new_and_newer_models",
            description=(
                "给定一个电子产品型号名(如 'AirPods Pro'、'Bambu A1 mini'),"
                "查询它的『新品最安値』以及同产品线里更新的型号(及各自新品价)。"
                "数据来自 kakaku 新品比价或品牌官方商店(非 Mercari 二手)。"
                "用于在『买二手 / 买新品 / 买新款』之间做取舍:先知道新品价和有没有新型号,"
                "再结合 Mercari 二手行情给建议。返回紧凑 JSON;取不到则返回 note。"
            ),
        )
        self.backends = backends

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "型号名,如 'AirPods Pro'、'Bambu A1 mini'。用通用型号名效果最好。",
                    },
                },
                "required": ["keyword"],
            }
        }

    async def execute(self, keyword: str, **kwargs) -> ToolResult:  # noqa: D401
        keyword = (keyword or "").strip()
        if not keyword:
            return ToolResult(
                status=ToolStatus.SUCCESS,
                data={"keyword": keyword, "note": _NO_DATA_NOTE, "currency": "JPY"},
            )

        for backend in self.backends:
            try:
                res = await backend.lookup(keyword)
            except Exception as e:  # noqa: BLE001 —— 单个 backend 出错不影响整体
                logger.warning(f"backend {type(backend).__name__} 失败: {e}")
                continue
            if res and res.get("searched_model"):
                res.setdefault("keyword", keyword)
                return ToolResult(status=ToolStatus.SUCCESS, data=res)

        return ToolResult(
            status=ToolStatus.SUCCESS,
            data={"keyword": keyword, "note": _NO_DATA_NOTE, "currency": "JPY"},
        )


def build_default_backends(scraper_service=None) -> List[Any]:
    """构建默认 backend 链:kakaku 优先,品牌官方商店兜底。

    scraper_service 若提供,则 LineupFinder 复用其已启动的浏览器上下文
    (scraper.scraper._new_context),不另起浏览器。
    """
    context_factory = None
    if scraper_service is not None and getattr(scraper_service, "scraper", None) is not None:
        context_factory = scraper_service.scraper._new_context
    finder = LineupFinder(context_factory=context_factory)
    return [KakakuBackend(), BrandStoreBackend(finder)]
