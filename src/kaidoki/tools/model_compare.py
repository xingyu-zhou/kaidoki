"""
新品 / 新型号对比工具（native function-calling tool）

供 LLM 自主调用的工具 `get_new_and_newer_models`:

    入参: keyword（型号名，如 "AirPods Pro" / "Braun Pro" / "Bambu A1 mini"）
    出参(紧凑 JSON):
      {
        "searched_model": {"name","series","model_no","new_price_min","release",
                           "shops","url","source","confidence","warnings"},
        "newer_models":   [{"name","series","relation","new_price_min","release",
                            "shops","url","note"}, ...],
        "newer_lookup":   "ok" | "unknown",     # ← 见下
        "newer_lookup_reason": "...",
        "candidates":     [...],                 # 仅当选型不确定时给出
        "coverage":       {...},
        "currency": "JPY"
      }
    取不到数据时返回 {"keyword", "note": "未获取到新品/新型号数据", "newer_lookup": "unknown"}。

设计要点（都是踩过的坑，别回退）：

1. **区分「没有更新型号」和「查不出来」**。`newer_lookup` 显式区分二者：只有 "ok" 才
   代表"确实比较过発売日、确实没有更新机型"；"unknown" 代表匹配/数据不足。历史 bug：
   family 锚点用最长英文 token（如 "braun"），对日文机型名恒不命中 → newer 恒为空列表 →
   模型把"匹配失败"当成"确认无后继"，输出了错误结论。

2. **选型必须证据驱动，不能靠名字长度**。历史 bug：跨语种 token（"braun" vs "ブラウン"）
   匹配全废，打分退化成"名字最短者胜"，于是 "Braun Pro" 选中了名字最短的三年前旧机型
   9435s-V（発売日 2022-09、全 3 店舗）。现在按 型番命中 > 系列尾部精确 > 命中 token 数 >
   発売日新 > 在售店舗多 排序，并带 `confidence` 与 `candidates`。

3. **页面顺序 ≠ 新旧顺序**。kakaku 搜索页是人気/おすすめ順（实测発売日序列为
   2024-08, 2025-11, 2025-11, 2023-08, ...）。新旧一律用行内的 `発売日` 判定。

4. **输出必须可验证**。每个机型都带 `url`（商品页）、`release`、`shops`，并对
   旧型号 / 在售店舗极少的情况给出 `warnings`，避免报出一个查不到的"最安値"。

后端两级，依次尝试(第一个给出结果者胜):
  1) KakakuBackend —— httpx 裸抓 kakaku(shift_jis)，读搜索页目录机型 + 各机型新品最安値。
     仅当该商品在 kakaku 比价目录内(搜索结果行含 /item/K.../)时命中；否则返回 None。
  2) BrandStoreBackend —— 对非目录/品牌直营商品(如 Bambu Lab 3D 打印机)，用 LineupFinder
     渲染官方商店商品页，从 JSON-LD Offer 取新品价。

合规克制:kakaku/官网低频取数、带浏览器 UA、请求间加延时、单商品少量请求。

Author: Kaidoki Team (model compare feature)
"""

import asyncio
import datetime as _dt
import html
import re
import urllib.parse as urlparse
from typing import Any, Dict, List, Optional, Pattern, Tuple

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

# 旧型号 / 在售店舗过少的判定阈值（用于 warnings，让模型主动提示价格可能已失效）
_STALE_MONTHS = 24
_FEW_SHOPS = 3

# 罗马字 → 日文（kakaku 的机型名多为片假名/汉字，纯英文 token 直接匹配会全废）。
# 只收常见电子/家电品牌；没收录的品牌退化为原样匹配，不会更差。
_BRAND_ALIASES: Dict[str, str] = {
    "braun": "ブラウン",
    "panasonic": "パナソニック",
    "philips": "フィリップス",
    "sony": "ソニー",
    "apple": "アップル",
    "sharp": "シャープ",
    "toshiba": "東芝",
    "hitachi": "日立",
    "dyson": "ダイソン",
    "anker": "アンカー",
    "bose": "ボーズ",
    "epson": "エプソン",
    "canon": "キヤノン",
    "nikon": "ニコン",
    "fujifilm": "富士フイルム",
    "sanyo": "サンヨー",
    "mitsubishi": "三菱",
    "balmuda": "バルミューダ",
    "shark": "シャーク",
    "irobot": "アイロボット",
    "logicool": "ロジクール",
    "logitech": "ロジクール",
    "razer": "レイザー",
    "samsung": "サムスン",
    "xiaomi": "シャオミ",
}
_BRAND_WORDS = set(_BRAND_ALIASES) | set(_BRAND_ALIASES.values())

# 产品线尾部的等级词（Pro / Pro+ / Sport+ / Max ...）：归并 family 时剥掉，
# 使 "シリーズ9 Pro" 与 "シリーズ9 Pro+" 归到同一 family "ブラウン シリーズ9"。
_TIER_TAIL = re.compile(r"^[A-Za-z][A-Za-z+\-]{0,8}$")

_ROW_SPLIT = re.compile(r'(?=<div class="p-resultItem_in p-item)')

# 目录机型行的结构标记(メーカー名 / 発売日 / 取扱店舗数)。
#
# 只判断"有没有 /item/K.../ 链接"是**不够**的:kakaku 搜索页里的单店购物行也会链到目录页。
# 实测 "ニコン D850" 的 35 个带 K 链接的行里有 29 个是购物行,其中一条
# "ニコン Nikon D850 ボディ D850" 报的是某一家店的 ¥327,834,而目录最安値是 ¥279,980
# —— 差 ¥47,854,而且购物行没有発売日/店舗数,导致"旧型号"警告整个失效。
# 同一个坑还产出过 "Apple アップル 純正 AirPods Pro … メーカー保証付き ラッピング可"
# 这种店铺文案标题(它把系列名污染成 12 个 token)。
# 反过来不能用购物标记做否定信号 —— 实测目录行也带 p-item_summary / p-resultItem_btnLink。
_CATALOG_MARKER = re.compile(r'class="p-item_(?:shopCounts|date|maker)')

# 型番形状:同时含数字与 ASCII 字母、且整体由 ascii 字母数字与 -/ 组成。
# "シリーズ9"(片假名+数字)与 "Pro"(无数字)都不算。
_MODEL_TOKEN = re.compile(r"^(?=.*\d)(?=.*[A-Za-z])[0-9A-Za-z][0-9A-Za-z\-/]*$")


def _tokens(keyword: str) -> List[str]:
    """把关键词切成有意义的小写 token(长度>=2 或纯数字,去标点)。

    **保留 `+`**:在 Braun 的命名里 "Pro" 与 "Pro+" 是不同世代。旧实现把 `+` 当标点删掉，
    于是查 "シリーズ9 Pro+" 会命中 "シリーズ9 Pro"（实测选出了 2022 年的 Pro 9450cc-V，
    而用户要的是 2025 年的 Pro+）。
    """
    raw = re.split(r"\s+", (keyword or "").strip().lower())
    out: List[str] = []
    for t in raw:
        t = re.sub(r"[^0-9a-z+぀-ヿ一-鿿]", "", t)
        if len(t) >= 2 or t.isdigit():
            out.append(t)
    return out


def _token_variants(token: str) -> List[str]:
    """一个 token 的可匹配写法(原样 + 品牌罗马字↔日文互换)。"""
    variants = [token]
    alias = _BRAND_ALIASES.get(token)
    if alias:
        variants.append(alias)
    else:
        for latin, ja in _BRAND_ALIASES.items():
            if token == ja:
                variants.append(latin)
                break
    return variants


def _norm_model_no(text: str) -> str:
    """型番归一化:只留 ascii 字母数字并小写(9435s-V → 9435sv)。"""
    return re.sub(r"[^0-9a-z]", "", (text or "").lower())


def _split_name(name: str) -> Tuple[str, str]:
    """机型名 → (series, model_no)。

    "ブラウン シリーズ9 Pro 9435s-V"          → ("ブラウン シリーズ9 Pro", "9435sv")
    "ブラウン シリーズ9 Pro+ 9660cc [マットブラック]" → ("ブラウン シリーズ9 Pro+", "9660cc")
    "AirPods Pro 3 MFHP4J/A"                  → ("AirPods Pro 3", "mfhp4ja")

    尾部"同时含数字与字母"的 token 视为型番剥掉;纯数字 token(代际,如 "3")保留在 series 里。
    只剥 `[` `【` `（` 起头的后缀(kakaku 的颜色/变体注记),**不剥**半角 `(` ——
    半角括号会出现在名称中段(如 "MagSafe充電ケース(USB-C)付き MTJV3J/A"),剥掉会连带吃掉型番。
    """
    stripped = re.sub(r"[\[【（].*$", "", name or "").strip()
    toks = stripped.split()
    model_parts: List[str] = []
    while toks and re.search(r"\d", toks[-1]) and re.search(r"[A-Za-z]", toks[-1]):
        model_parts.insert(0, toks.pop())
    return " ".join(toks), _norm_model_no(" ".join(model_parts))


def _variant_of(model_no: str, category: Optional[str]) -> Optional[str]:
    """从型番后缀推断"配置"这一维（目前只对电动剃须刀成立）。

    Braun 的命名约定:型番以 `cc` 结尾 = クリーン&チャージ **洗浄器付き**；
    以 `s` 结尾 = **本体のみ**（洗浄器なし）。9660cc / 9450cc-V vs 9617s / 9435s-V。

    这一维和"型番是否相同"同样致命:同一系列里 cc 与 s 的差价可达 ¥8,000 以上
    （实测 Pro+ 9617s ¥35,698 vs 9657cc ¥43,999），把两者当同类比价会得出错误结论。

    刻意用 `category` 收窄适用范围 —— `cc`/`s` 后缀只在シェーバー品类里有这个含义，
    对相机/PC 乱套会得出胡说八道的"配置"。
    """
    if not model_no or not category or "シェーバー" not in category:
        return None
    if re.search(r"cc[a-z]?$", model_no):
        return "with_cleaning_station"
    if re.search(r"s[a-z]?$", model_no):
        return "body_only"
    return None


def _wants_cleaning_station(keyword: str) -> Optional[bool]:
    """关键词有没有表达"要/不要洗浄器"。None = 没表态。"""
    k = (keyword or "").lower()
    if re.search(r"洗浄器|洗浄機|クリーン|\bcc\b|cc型番", k):
        return True
    if re.search(r"本体のみ|洗浄器なし|洗浄器無し", k):
        return False
    return None


# 检索时该丢掉的规格/意图词。kakaku 搜索是"所有词都要命中"，
# 把 "洗浄器付き" "新品" "最安値" 塞进去往往直接 0 结果。
_NOISE_WORDS = re.compile(
    r"(洗浄器付き|洗浄器つき|洗浄機付き|洗浄器|洗浄機|クリーン&リニュー|クリーン＆リニュー"
    r"|cc型番|型番|新品|中古|未使用|未開封|最安値|最安|価格|値段|相場|おすすめ"
    r"|本体のみ|セット|購入|買いたい|どっち|一番安い|\bcc\b|\bnew\b)",
    re.I,
)


def _core_keyword(keyword: str) -> str:
    """把关键词收敛成"品牌 + 系列 + 型番"，用于 kakaku 检索的降级重试。"""
    s = _NOISE_WORDS.sub(" ", keyword or "")
    s = re.sub(r"[（）()【】\[\]、,，。？?！!]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _model_no_candidates(name: str) -> List[str]:
    """名称里所有型番形状的 token（归一化）。

    `_split_name` 只剥**尾部**型番，对 "…Pro 9435s-V" 正确，但对 "D850 ボディ"
    这种型番在**开头**的名称会得出空型番 —— 于是真正的目录行拿不到"型番命中"这个
    最强信号，反而输给一个尾部恰好是型番的单店购物行（实测 D850 就是这么错的）。
    """
    stripped = re.sub(r"[\[【（].*$", "", name or "")
    out: List[str] = []
    for tok in stripped.split():
        if _MODEL_TOKEN.match(tok):
            norm = _norm_model_no(tok)
            if len(norm) >= 3 and norm not in out:
                out.append(norm)
    return out


def _family_of(series: str) -> str:
    """series → family(产品线):剥掉尾部的等级词与代际数字,至少保留 1 个 token。

    "ブラウン シリーズ9 Pro"  → "ブラウン シリーズ9"   （"シリーズ9" 非纯数字/非 ascii，保留）
    "ブラウン シリーズ9 Sport+" → "ブラウン シリーズ9"
    "AirPods Pro 3"           → "AirPods"
    """
    toks = (series or "").split()
    while len(toks) > 1 and (toks[-1].isdigit() or _TIER_TAIL.match(toks[-1])):
        toks.pop()
    return " ".join(toks)


def _tail_patterns(toks: List[str]) -> List[Pattern[str]]:
    """关键词去掉品牌后的残余是否精确落在 series 尾部。

    用来区分 "Pro"(→ 只匹配 series 以 Pro 结尾) 与 "Pro+"。没有这条,"Braun Pro" 会
    把 "シリーズ9 Pro+" 也当成同等候选。
    """
    non_brand = [t for t in toks if t not in _BRAND_WORDS]
    if not non_brand:
        return []
    joined = r"[\s　]*".join(re.escape(t) for t in non_brand)
    return [
        re.compile(joined + r"$", re.I),
        re.compile(re.escape(non_brand[-1]) + r"$", re.I),
    ]


def _months_since(release: Optional[str]) -> Optional[int]:
    """"YYYY-MM" → 距今月数;未知返回 None。"""
    if not release:
        return None
    try:
        y, m = (int(x) for x in release.split("-"))
    except (ValueError, AttributeError):
        return None
    today = _dt.date.today()
    return (today.year - y) * 12 + (today.month - m)


def _warnings_for(row: Dict[str, Any]) -> List[str]:
    """给一行机型生成鲜度/可得性警告(让模型主动提示,而不是报个查不到的价)。"""
    out: List[str] = []
    age = _months_since(row.get("release"))
    if age is not None and age >= _STALE_MONTHS:
        out.append(
            f"発売から約 {age // 12} 年（{row.get('release')}）的旧型号，"
            f"价格与在售情况可能已变化"
        )
    shops = row.get("shops")
    if shops is not None and shops <= _FEW_SHOPS:
        out.append(
            f"在售店舗仅 {shops} 店，最安値不代表主流行情，可能已接近断货"
        )
    if row.get("lowest") is None:
        out.append("未取到新品最安値")
    return out


# --------------------------------------------------------------------------- #
# Backend 1: kakaku（目录内电子品 = 行）
# --------------------------------------------------------------------------- #
class KakakuBackend:
    """从 kakaku 搜索页取同关键词下的目录机型 + 各机型新品最安値/発売日/店舗数。"""

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
        """解析搜索页,返回目录机型列表。

        每行取:kcode / name / lowest(新品最安値) / url / release(発売日 YYYY-MM) /
        shops(取扱店舗数) / series / model_no / family。
        release 与 shops 就在同一区块的可见文本里,是判断新旧与可得性的唯一可靠依据
        （**不要**用页面顺序判断新旧,那是人気順）。
        """
        models: List[Dict[str, Any]] = []
        for block in _ROW_SPLIT.split(text)[1:]:
            k = re.search(r"/item/(K\d+)/", block)
            if not k:  # 无 /item/K.../ = 纯购物列表,不是目录机型,跳过
                continue
            if not _CATALOG_MARKER.search(block):
                # 有 K 链接但没有目录结构标记 = 单店购物行（它也会链到目录页）。
                # 它的价格是那一家店的报价，不是目录最安値，且没有発売日/店舗数。
                continue
            nm = re.search(r'class="p-item_name">\s*<a[^>]*>(.*?)</a>', block, re.S)
            if not nm:
                continue
            name = self._clean(nm.group(1))
            if not name:
                continue

            pr = re.search(r'class="p-item_priceNum[^"]*">([\d,]+)', block)
            mk = re.search(r'class="p-item_maker[^"]*"[^>]*>(.*?)<', block, re.S)
            cg = re.search(r'class="p-item_category[^"]*"[^>]*>(.*?)<', block, re.S)
            flat = self._clean(block)
            rel = re.search(r"発売日[:：]\s*(\d{4})\s*年\s*(\d{1,2})\s*月", flat)
            shops = re.search(r"全\s*([\d,]+)\s*店舗", flat)
            series, model_no = _split_name(name)
            category = self._clean(cg.group(1)) if cg else None
            model_nos = _model_no_candidates(name)
            variant = _variant_of(model_no or (model_nos[0] if model_nos else ""), category)

            models.append(
                {
                    "kcode": k.group(1),
                    "name": name,
                    "lowest": int(pr.group(1).replace(",", "")) if pr else None,
                    "url": f"https://kakaku.com/item/{k.group(1)}/",
                    "release": (
                        f"{rel.group(1)}-{int(rel.group(2)):02d}" if rel else None
                    ),
                    "shops": int(shops.group(1).replace(",", "")) if shops else None,
                    "maker": self._clean(mk.group(1)) if mk else None,
                    "category": category,
                    "series": series,
                    "model_no": model_no,
                    "model_nos": model_nos,
                    "variant": variant,
                    "family": _family_of(series),
                }
            )
        return models

    # ------------------------------------------------------------------ #
    # 选型：证据驱动排序 + 置信度（不再"名字最短者胜"）
    # ------------------------------------------------------------------ #
    @staticmethod
    def _select(
        keyword: str, models: List[Dict[str, Any]]
    ) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], str]:
        """在目录机型里定位被搜机型。返回 (searched, ranked_candidates, confidence)。"""
        toks = _tokens(keyword)
        if not toks or not models:
            return None, [], "none"

        kw_norm = _norm_model_no(keyword)
        tail_pats = _tail_patterns(toks)
        want_cleaning = _wants_cleaning_station(keyword)

        def hits(row: Dict[str, Any]) -> int:
            nm = (row["name"] or "").lower()
            return sum(
                1 for t in toks if any(v.lower() in nm for v in _token_variants(t))
            )

        def model_hit(row: Dict[str, Any]) -> int:
            """关键词里直接出现了这一行的任一型番 —— 最强信号。

            要看名称里**所有**型番候选，不能只看尾部那个:"D850 ボディ" 的型番在开头。
            """
            for mn in row.get("model_nos") or [row.get("model_no") or ""]:
                if len(mn) >= 4 and mn in kw_norm:
                    return 1
            return 0

        def series_exact(row: Dict[str, Any]) -> int:
            s = row.get("series") or ""
            return 1 if any(p.search(s) for p in tail_pats) else 0

        def variant_match(row: Dict[str, Any]) -> int:
            """关键词要求了洗浄器付き(cc)/本体のみ(s) 时，同配置的机型优先。"""
            if want_cleaning is None or row.get("variant") is None:
                return 0
            wanted = "with_cleaning_station" if want_cleaning else "body_only"
            return 1 if row["variant"] == wanted else -1

        candidates = [m for m in models if hits(m) > 0]
        if not candidates:
            return None, [], "none"

        def sort_key(row: Dict[str, Any]):
            return (
                model_hit(row),
                series_exact(row),
                variant_match(row),        # 要洗浄器就别选本体のみ
                hits(row),
                row.get("release") or "",   # 発売日新者优先（"" 排最后）
                row.get("shops") or 0,      # 在售店舗多者优先
            )

        ranked = sorted(candidates, key=sort_key, reverse=True)
        best = ranked[0]

        if model_hit(best):
            confidence = "high"
        elif series_exact(best) and hits(best) == len(toks):
            confidence = "medium"
        else:
            confidence = "low"

        # 另有一个不同产品线、证据分完全相同的候选 → 选型有歧义，降一档
        tied_other_family = [
            r
            for r in ranked[1:]
            if sort_key(r)[:3] == sort_key(best)[:3] and r["family"] != best["family"]
        ]
        if confidence == "medium" and tied_other_family:
            confidence = "low"

        return best, ranked, confidence

    # ------------------------------------------------------------------ #
    # 新旧判定：只用発売日；并显式区分「没有」与「不知道」
    # ------------------------------------------------------------------ #
    @staticmethod
    def _newer(
        searched: Dict[str, Any], models: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], str, str]:
        """返回 (newer_rows, newer_lookup, reason)。

        newer_lookup == "ok"      → 真的比较过発売日，结论可信（含"确实没有更新机型"）
        newer_lookup == "unknown" → 数据/归类不足，**不允许**下"没有后继型号"的结论
        """
        fam = searched.get("family")
        siblings = [
            m
            for m in models
            if m["kcode"] != searched["kcode"] and m.get("family") == fam
        ]
        def _newer_related(exclude_family: bool) -> List[Dict[str, Any]]:
            """搜索结果里発売日比被搜机型更新的相关机型（可跨产品线）。

            必须限定**同厂商**:搜索页里混着第三方配件，实测 "ニコン D850" 会把
            ケンコー 的保护膜 "KLPK-ND850 / 2018-05" 当成"更新的相关机型"提示给用户。
            """
            if not searched.get("release"):
                return []
            maker = searched.get("maker")
            out = [
                m
                for m in models
                if m["kcode"] != searched["kcode"]
                and m.get("release")
                and m["release"] > searched["release"]
                and (not maker or m.get("maker") == maker)
                and (not exclude_family or m.get("family") != fam)
            ]
            out.sort(key=lambda m: m["release"], reverse=True)
            return out

        if not siblings:
            # 同 family 只有它自己时，仍然把"页面上有更新的相关机型"说出来 ——
            # 光说"只找到 1 个机型"对用户没用（实测 D850 就落在这个分支）。
            related = _newer_related(exclude_family=False)
            base = f"同产品线（{fam}）在本页只找到 1 个机型，无法判断是否有更新型号"
            if related:
                base += (
                    f"；但搜索结果里有 {len(related)} 个発売日更新的相关机型"
                    f"（如 {related[0]['name']} / {related[0]['release']}），"
                    "它们可能属于不同产品线，需人工确认"
                )
            return [], "unknown", base

        if not searched.get("release"):
            return [], "unknown", "被搜机型的発売日未知，无法比较新旧"

        newer = [
            m for m in siblings if m.get("release") and m["release"] > searched["release"]
        ]
        unknown_release = [m for m in siblings if not m.get("release")]
        newer.sort(key=lambda m: m["release"], reverse=True)

        if newer:
            reason = f"按発売日比较，同产品线（{fam}）有 {len(newer)} 个更新机型"
            if unknown_release:
                reason += f"；另有 {len(unknown_release)} 个発売日未知未计入"
            return newer, "ok", reason

        if unknown_release:
            return (
                [],
                "unknown",
                f"同产品线（{fam}）有 {len(unknown_release)} 个机型発売日未知，无法确认是否更新",
            )

        # 自检：同 family 内没有更新机型，但搜索结果里还有同厂商的更新机型
        # → 说明 family 归类可能切错了产品线，不能报"无后继"。
        cross = _newer_related(exclude_family=True)
        if cross:
            return (
                [],
                "unknown",
                (
                    f"同产品线（{fam}）内未发现更新机型，但搜索结果里有 {len(cross)} 个"
                    f"発売日更新的相关机型（如 {cross[0]['name']} / {cross[0]['release']}），"
                    "产品线归类可能不准，未能确认"
                ),
            )

        return [], "ok", f"同产品线（{fam}）所有机型的発売日均不晚于被搜机型"

    # ------------------------------------------------------------------ #
    @staticmethod
    def _entry(row: Dict[str, Any], **extra: Any) -> Dict[str, Any]:
        """机型 → 给模型的紧凑条目（一定带 url，让结论可核对）。"""
        out = {
            "name": row.get("name"),
            "series": row.get("series"),
            "model_no": row.get("model_no") or None,
            # 配置维度：with_cleaning_station(cc) / body_only(s) / None(不适用)。
            # 不同 variant 之间不可直接比价 —— 同系列差价可达 ¥8,000 以上。
            "variant": row.get("variant"),
            "new_price_min": row.get("lowest"),
            "release": row.get("release"),
            "shops": row.get("shops"),
            "url": row.get("url"),
        }
        out.update(extra)
        return out

    async def _search(self, keyword: str) -> Tuple[Optional[str], str]:
        """搜一次 kakaku，返回 (html|None, url)。失败只 warn，不抛。"""
        url = f"https://search.kakaku.com/{urlparse.quote(keyword)}/"
        try:
            text = await self._fetch_text(url)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"kakaku 取数失败: {e}")
            return None, url
        await asyncio.sleep(self.delay_seconds)  # 克制
        return text, url

    async def lookup(self, keyword: str) -> Optional[Dict[str, Any]]:
        text, url = await self._search(keyword)

        models = self._parse_search(text) if text else []
        if not models:
            # 关键词里塞了规格/意图词时 kakaku 搜不到目录机型（实测
            # "ブラウン シリーズ9 Pro+ 洗浄器付き cc" 与 "…Pro+ 9517s-V CC" 都是 0 结果）。
            # 降级成"品牌+系列+型番"再试一次，省掉一整轮 agent 往返。
            core = _core_keyword(keyword)
            if core and core != (keyword or "").strip():
                logger.info(f"kakaku 无目录机型，降级重试: {keyword!r} → {core!r}")
                text, url = await self._search(core)
                models = self._parse_search(text) if text else []
        if not models:  # 非目录商品(如 Bambu)——交给下一级 backend
            return None

        # 用**原始**关键词做选型:核心词用于检索，cc/洗浄器 这类意图仍要从原词里读
        searched, ranked, confidence = self._select(keyword, models)
        if searched is None:
            return None

        newer, newer_lookup, reason = self._newer(searched, models)
        total_hits = re.search(r"([\d,]+)\s*件中", self._clean(text))

        result: Dict[str, Any] = {
            "searched_model": self._entry(
                searched,
                source="kakaku.com",
                confidence=confidence,
                warnings=_warnings_for(searched),
            ),
            "newer_models": [
                self._entry(
                    m,
                    relation=(
                        "same_series" if m.get("series") == searched.get("series")
                        else "same_family"
                    ),
                    note="kakaku 同产品线机型（新品最安値，按発売日判定为更新）",
                )
                for m in newer[: self.max_newer]
            ],
            "newer_lookup": newer_lookup,
            "newer_lookup_reason": reason,
            "search_url": url,
            "coverage": {
                "catalog_models_parsed": len(models),
                "total_hits_reported": (
                    int(total_hits.group(1).replace(",", "")) if total_hits else None
                ),
                "note": "仅解析 kakaku 搜索结果第 1 页；排名靠后或未收录的机型可能未纳入比较",
            },
            "currency": "JPY",
        }

        # 选型不确定时，把候选一起交给模型（让它追问或说明歧义，而不是硬报一个价）
        if confidence != "high":
            others = [m for m in ranked if m["kcode"] != searched["kcode"]][:5]
            result["candidates"] = [self._entry(m) for m in others]

        return result


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
        """关键词 → (adapter, searched_entry, newer_entries[], exact_match)。"""
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
            exact = searched is not None
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
            return ad, searched, newer, exact
        return None, None, [], False

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
        ad, searched, newer, exact = self._resolve(keyword)
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
                    "series": entry["series"],
                    "relation": "same_series",
                    "new_price_min": n_price,
                    "url": entry["url"],
                    "note": entry.get("note") or f"{ad['brand']} 同线更新机型",
                }
            )

        return {
            "searched_model": {
                "name": searched["name"],
                "series": searched["series"],
                "new_price_min": s_price,
                "url": searched["url"],
                "source": urlparse.urlparse(searched["url"]).netloc,
                "confidence": "high" if exact else "low",
                "warnings": [] if s_price else ["未取到官方商店新品价"],
            },
            "newer_models": newer_out,
            # adapter 的 lineup 是人工维护的确定列表 → 比较结果本身是可信的
            "newer_lookup": "ok",
            "newer_lookup_reason": (
                f"{ad['brand']} 内置产品线表比较代际（共 {len(ad['lineup'])} 个机型）"
            ),
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
                "给定一个电子产品型号名(如 'AirPods Pro'、'Braun シリーズ9 Pro')，"
                "查询它的『新品最安値』以及同产品线里更新的型号(及各自新品价)。"
                "数据来自 kakaku 新品比价或品牌官方商店(非 Mercari)。"
                "返回里每个机型都带 url / release(発売日) / shops(在售店舗数)，"
                "并带 confidence(选型置信度) 与 newer_lookup"
                "（'ok'=确实比较过発売日；'unknown'=数据不足，此时不得断言『没有更新型号』）。"
                "关键词越具体越准；只给品牌+等级词(如 'Braun Pro')时可能命中错机型，"
                "此时返回的 candidates 列出了其它候选。"
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
                        "description": (
                            "型号名，如 'AirPods Pro 2'、'ブラウン シリーズ9 Pro'、"
                            "'Bambu A1 mini'。带上系列名/型番最准；日文名对 kakaku 更友好。"
                        ),
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
                data={
                    "keyword": keyword,
                    "note": _NO_DATA_NOTE,
                    "newer_lookup": "unknown",
                    "newer_lookup_reason": "keyword 为空",
                    "currency": "JPY",
                },
            )

        for backend in self.backends:
            try:
                res = await backend.lookup(keyword)
            except Exception as e:  # noqa: BLE001 —— 单个 backend 出错不影响整体
                logger.warning(f"backend {type(backend).__name__} 失败: {e}")
                continue
            if res and res.get("searched_model"):
                res.setdefault("keyword", keyword)
                # backend 没表态就按"不知道"处理 —— 绝不让缺失被读成"没有"
                res.setdefault("newer_lookup", "unknown")
                res.setdefault("newer_lookup_reason", "backend 未提供新旧比较依据")
                return ToolResult(status=ToolStatus.SUCCESS, data=res)

        return ToolResult(
            status=ToolStatus.SUCCESS,
            data={
                "keyword": keyword,
                "note": _NO_DATA_NOTE,
                "newer_lookup": "unknown",
                "newer_lookup_reason": "所有 backend 都未取到数据",
                "currency": "JPY",
            },
        )


# 公开别名：Google 对照基线要用同一套型番/系列解析来判断"是不是同一个型号"。
# 别再写第二份 —— 两份解析一旦漂移，记分板会把同型号判成不同型号。
normalize_model_no = _norm_model_no
split_model_name = _split_name
family_of = _family_of
tokens_of = _tokens
token_variants = _token_variants


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
