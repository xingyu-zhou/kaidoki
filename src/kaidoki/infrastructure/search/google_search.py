"""
Google Custom Search JSON API 客户端 —— **只用于对照基线,不给 agent 当输入**。

用途:每次 agent 跑完,顺手记一份 Google 的检索结果,用来回答"我们有没有比 Google
做得好"。结果绝不回写进 agent 的 messages —— 一旦进去,模型会抄 Google 的数字,
基线就失去独立性,记分板变成自证。

为什么用官方 API 而不是抓 google.com:Google 会挡无头浏览器、DOM 频繁变、且违反 ToS。
这个项目的历史教训正是"别跟反爬墙较劲"。CSE 免费 100 次/天,个人自用够。

注意 CSE ≠ google.com:Programmable Search Engine 的排序与真实 google.com 有差异。
记录里一律标 source="google_cse",不要声称"完全等于 Google"。

网络环境(实测):公司 Netskope 会对 www.googleapis.com 做 TLS 中间人,但环境变量
SSL_CERT_FILE 指向了它的 CA bundle,httpx 走 ssl.create_default_context() 会遵循该变量,
因此校验通过。一旦从不继承 shell profile 的环境启动(launchd / cron / 某些 IDE),
证书校验会失败 —— 这里把它翻译成可读提示,而不是抛原始 SSL 栈错误。

Author: Kaidoki Team (google benchmark)
"""

import asyncio
import os
import re
import ssl
from typing import Any, Dict, List, Optional

import httpx

from ...shared.utils.logger_utils import get_logger

logger = get_logger(__name__)

CSE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"

# 日元锚定的价格模式。
# 刻意**不用** shared/utils/price_utils.py:PriceParser.parse_price_text ——
# 它有 _extract_number_price 兜底，会把 "9435s-V" / "9660cc" / "K0001713157"
# 这类型番当成价格。基线里出现一个假价格，整条比较就废了。
# 这里只保留 price_utils._compile_price_patterns 的前两条(¥前缀 / 円后缀)。
_JPY_PATTERNS = [
    re.compile(r"[¥￥]\s*(\d{1,3}(?:,\d{3})+|\d{3,7})"),
    re.compile(r"(\d{1,3}(?:,\d{3})+|\d{3,7})\s*円"),
]

# 合理价格区间：低于 100 円 / 高于 500 万円 的匹配几乎都是误抽（页码、型番、年份）
_MIN_SANE_JPY = 100
_MAX_SANE_JPY = 5_000_000


_CERT_ERROR_HINT = (
    "TLS 证书校验失败。公司代理(Netskope 等)会对 googleapis.com 做中间人，"
    "需要把它的 CA bundle 告诉 Python:"
    "export SSL_CERT_FILE=/etc/ssl/netskope/<org>/ca-bundle.pem"
    "（或设置 BENCHMARK_CA_BUNDLE 指向同一文件）。"
    "注意 certifi 自带的根证书里没有企业代理的 CA，"
    "所以从不继承 shell profile 的环境（launchd / cron / 某些 IDE）启动时一定会撞到这个。"
)


def _is_cert_error(exc: BaseException) -> bool:
    """判断异常链里是否有证书校验失败。

    httpx 会把 ssl.SSLCertVerificationError 包成 httpx.ConnectError，
    所以直接 `except ssl.SSLCertVerificationError` 抓不到 —— 必须走异常链。
    """
    seen = 0
    cur: Optional[BaseException] = exc
    while cur is not None and seen < 10:
        if isinstance(cur, ssl.SSLCertVerificationError):
            return True
        if "CERTIFICATE_VERIFY_FAILED" in str(cur):
            return True
        cur = cur.__cause__ or cur.__context__
        seen += 1
    return False


def extract_jpy_prices(text: str) -> List[int]:
    """从任意文本里抽出日元金额（去重、升序）。只认 ¥/￥ 前缀或 円 后缀。"""
    found: set = set()
    for pat in _JPY_PATTERNS:
        for m in pat.finditer(text or ""):
            try:
                value = int(m.group(1).replace(",", ""))
            except ValueError:
                continue
            if _MIN_SANE_JPY <= value <= _MAX_SANE_JPY:
                found.add(value)
    return sorted(found)


def _pagemap_prices(pagemap: Dict[str, Any]) -> List[int]:
    """从 CSE 的 pagemap 结构化数据里取价格（权威，比 snippet 可信）。"""
    out: List[int] = []
    if not isinstance(pagemap, dict):
        return out
    for key in ("offer", "product", "aggregateoffer", "aggregaterating"):
        for entry in pagemap.get(key) or []:
            if not isinstance(entry, dict):
                continue
            for field in ("price", "lowprice", "lowPrice", "highprice"):
                raw = entry.get(field)
                if raw is None:
                    continue
                digits = re.sub(r"[^\d]", "", str(raw))
                if digits:
                    value = int(digits)
                    if _MIN_SANE_JPY <= value <= _MAX_SANE_JPY:
                        out.append(value)
    for entry in pagemap.get("metatags") or []:
        if not isinstance(entry, dict):
            continue
        for field in ("og:price:amount", "product:price:amount"):
            raw = entry.get(field)
            if raw is None:
                continue
            digits = re.sub(r"[^\d]", "", str(raw))
            if digits:
                value = int(digits)
                if _MIN_SANE_JPY <= value <= _MAX_SANE_JPY:
                    out.append(value)
    return sorted(set(out))


def parse_cse_response(payload: Dict[str, Any], top_n: int = 10) -> List[Dict[str, Any]]:
    """CSE 响应 → 紧凑结果列表（plain dict，可直接进 JSONL 并支持事后重算）。

    每条结果的 prices 里每个价格都带 source/verified：
      pagemap 来源 = 结构化数据，verified=True
      snippet 来源 = 摘要文本正则，verified=False（可能过期 / 是别的变体 / 是中古价）
    """
    items: List[Dict[str, Any]] = []
    for rank, raw in enumerate((payload.get("items") or [])[:top_n], 1):
        pagemap = raw.get("pagemap") or {}
        snippet = raw.get("snippet") or ""
        title = raw.get("title") or ""

        prices: List[Dict[str, Any]] = [
            {"price": p, "source": "pagemap", "verified": True}
            for p in _pagemap_prices(pagemap)
        ]
        structured = {p["price"] for p in prices}
        for p in extract_jpy_prices(f"{title} {snippet}"):
            if p not in structured:
                prices.append({"price": p, "source": "snippet", "verified": False})

        items.append(
            {
                "rank": rank,
                "title": title,
                "link": raw.get("link") or "",
                "display_link": raw.get("displayLink") or "",
                "snippet": snippet,
                "prices": prices,
            }
        )
    return items


class GoogleCseClient:
    """Custom Search JSON API 客户端。失败一律返回错误结构，绝不抛给调用方。"""

    def __init__(
        self,
        api_key: Optional[str],
        cse_id: Optional[str],
        top_n: int = 10,
        timeout: float = 20.0,
        delay_seconds: float = 1.0,
        ca_bundle: Optional[str] = None,
    ):
        self.api_key = api_key
        self.cse_id = cse_id
        self.top_n = max(1, min(int(top_n), 10))  # CSE 单次上限 10
        self.timeout = timeout
        self.delay_seconds = delay_seconds
        # 企业代理(Netskope)做 TLS 中间人时需要它的 CA。默认沿用进程环境里的设置。
        self.ca_bundle = ca_bundle or os.environ.get("SSL_CERT_FILE")

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.cse_id)

    def _verify_arg(self):
        """httpx 的 verify 参数：有 CA bundle 用它，否则走默认信任库。"""
        if self.ca_bundle and os.path.exists(self.ca_bundle):
            return self.ca_bundle
        return True

    async def search(self, query: str) -> Dict[str, Any]:
        """搜一次。返回 {query, items[], total_results, error?}（永不抛异常）。"""
        query = (query or "").strip()
        if not query:
            return {"query": query, "items": [], "error": "query 为空"}
        if not self.configured:
            return {
                "query": query,
                "items": [],
                "error": "未配置 GOOGLE_API_KEY / GOOGLE_CSE_ID，跳过 Google 对照",
            }

        params = {
            "key": self.api_key,
            "cx": self.cse_id,
            "q": query,
            "num": self.top_n,
            "hl": "ja",
            "gl": "jp",
        }
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, verify=self._verify_arg()
            ) as client:
                resp = await client.get(CSE_ENDPOINT, params=params)
        except Exception as e:  # noqa: BLE001 —— 基线失败绝不能影响主流程
            if _is_cert_error(e):
                logger.warning(f"Google CSE 证书校验失败: {e}")
                return {
                    "query": query,
                    "items": [],
                    "error": f"{_CERT_ERROR_HINT} 原始错误: {e}",
                }
            logger.warning(f"Google CSE 请求失败: {e}")
            return {"query": query, "items": [], "error": f"{type(e).__name__}: {e}"}

        if resp.status_code != 200:
            detail = ""
            try:
                detail = (resp.json().get("error") or {}).get("message") or ""
            except Exception:  # noqa: BLE001
                detail = resp.text[:200]
            note = "（每天 100 次免费额度可能已用完）" if resp.status_code == 429 else ""
            return {
                "query": query,
                "items": [],
                "error": f"HTTP {resp.status_code}{note}: {detail}",
            }

        payload = resp.json()
        await asyncio.sleep(self.delay_seconds)  # 克制：两次查询之间留间隔
        return {
            "query": query,
            "items": parse_cse_response(payload, self.top_n),
            "total_results": (payload.get("searchInformation") or {}).get("totalResults"),
        }
