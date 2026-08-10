"""
BenchmarkService —— 用 Google 检索结果给 kaidoki 打对照分。

它回答一个问题:**我们有没有比自己上网搜更强?** 不是给 agent 提供输入。

三条设计红线:

1. **绝不回写 agent 的 messages**。基线一旦进对话，模型会抄 Google 的数字，
   基线失去独立性，记分板变成自证。本模块只读 AgentResult，不返回任何东西给 agent。

2. **打分在读取时算，不在写入时定**。JSONL 里存双方**原始结果** + 当次 verdict 快照。
   判定标准一定会变（以后想加运费、只算未使用品……），只存结论就等于每次改标准都
   丢掉全部历史。`rescore_record()` 能从旧数据重算。

3. **不能拿原始中文 query 去打 Google**。`"Braun Pro只买新品"` 送给 Google 会得到很差
   的结果，那样赢了毫无意义。所以同时评两份:raw_query（对等输入）与
   fair_query（agent 自己用的日文型号 + 最安値，≈懂行的人自己搜）。

我方数据一律从 `TraceStep.result_full` 确定性提取 —— 不解析 agent 的 Markdown 回答，
不用 LLM 打分。打分必须确定性，否则记分板自己会漂。

Author: Kaidoki Team (google benchmark)
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from ...shared.utils.item_filters import (
    ambiguous_flags,
    classify_exclusion,
    looks_like_body,
)
from ...shared.utils.logger_utils import get_logger
from ...tools.model_compare import (
    normalize_model_no,
    split_model_name,
    token_variants,
    tokens_of,
)

logger = get_logger(__name__)

# 打分逻辑的版本号：改了判定标准就 +1，历史记录能看出是哪套标准算的
SCORING_VERSION = 2

# 价格下限 = 被搜机型新品最安値 × 该比例。关键词表永远补不全，这是第二道闸。
DEFAULT_FLOOR_RATIO = 0.35

# 我方价格要便宜多于这个比例才算赢（避免几十日元的噪声算成胜利）
WIN_MARGIN = 0.02

_MERCARI_TOOLS = ("search_mercari", "recommend_deals")
_MODEL_COMPARE_TOOL = "get_new_and_newer_models"

# 已经带了价格意图的关键词就不要再追加"最安値"
_PRICE_INTENT = re.compile(r"最安|価格|値段|いくら|相場")


# --------------------------------------------------------------------------- #
# 我方候选：从 trace 的完整返回里确定性提取
# --------------------------------------------------------------------------- #
def _guess_model_nos(text: str) -> List[str]:
    """从任意标题里猜型番（归一化）。用于判断"Google 那条是不是同一个型号"。

    要求 >=5 字符且 >=2 个数字：挡掉 "6in1" 这类噪声，保留 9517sv / 9660cc / mfhp4ja。
    """
    out: List[str] = []
    for tok in re.split(r"[\s　/、,，\[\]【】()（）]+", text or ""):
        norm = normalize_model_no(tok)
        if len(norm) >= 5 and sum(c.isdigit() for c in norm) >= 2:
            if norm not in out:
                out.append(norm)
    return out


def _our_item(
    source: str,
    role: str,
    title: Optional[str],
    price: Optional[int],
    url: Optional[str],
    **extra: Any,
) -> Dict[str, Any]:
    title = title or ""
    model_nos = _guess_model_nos(title)
    catalog_no = split_model_name(title)[1]
    if catalog_no and catalog_no not in model_nos:
        model_nos.insert(0, catalog_no)
    item = {
        "source": source,        # mercari | kakaku | 品牌官方站域名
        "role": role,            # listing | searched | newer | candidate
        "title": title,
        "price": price,
        "url": url,
        "model_nos": model_nos,
    }
    item.update({k: v for k, v in extra.items() if v is not None})
    return item


def extract_our_items(trace: List[Any]) -> List[Dict[str, Any]]:
    """从 agent trace 提取我方所有候选商品（plain dict，可直接进 JSONL）。

    trace 元素既可以是 TraceStep 对象，也可以是它的 to_dict() —— rescore 时用后者。
    """
    items: List[Dict[str, Any]] = []
    seen: set = set()

    for step in trace or []:
        tool = getattr(step, "tool", None) or (step.get("tool") if isinstance(step, dict) else None)
        raw = getattr(step, "result_full", None)
        if raw is None and isinstance(step, dict):
            raw = step.get("result_full")
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        if not isinstance(data, dict) or "error" in data:
            continue

        if tool in _MERCARI_TOOLS:
            for p in data.get("products") or []:
                url = p.get("url")
                if url and url in seen:
                    continue
                if url:
                    seen.add(url)
                items.append(
                    _our_item(
                        "mercari", "listing", p.get("title"), p.get("price"), url,
                        condition=p.get("condition"),
                    )
                )

        elif tool == _MODEL_COMPARE_TOOL:
            groups: List[Tuple[str, Any]] = [
                ("searched", data.get("searched_model")),
                ("newer", data.get("newer_models")),
                ("candidate", data.get("candidates")),
            ]
            for role, payload in groups:
                entries = payload if isinstance(payload, list) else ([payload] if payload else [])
                for e in entries:
                    if not isinstance(e, dict):
                        continue
                    url = e.get("url")
                    key = url or f"{role}:{e.get('name')}"
                    if key in seen:
                        continue
                    seen.add(key)
                    items.append(
                        _our_item(
                            e.get("source") or "kakaku", role,
                            e.get("name"), e.get("new_price_min"), url,
                            release=e.get("release"), shops=e.get("shops"),
                            series=e.get("series"),
                        )
                    )
    return items


def build_fair_query(trace: List[Any]) -> Optional[str]:
    """构造"懂行的人会怎么搜"的公平 query：agent 自己用的日文关键词 + 最安値。

    优先级：**最后一次取到数据的** get_new_and_newer_models 关键词 → 任一次该工具的关键词
    → 第一个 search_mercari 的关键词。

    为什么要"最后一次成功的"：agent 第一次常会用一个过度具体的关键词而查空，然后自己纠正。
    实测它先试 `ブラウン シリーズ9 Pro+ 9517s-V CC`（把 s 型番和 CC 拼在一起，自相矛盾、
    kakaku 0 结果），第二轮才改成 `ブラウン シリーズ9 Pro+`。旧实现取第一个，
    于是拿一句废话去打 Google，基线直接失去意义。
    """
    best: Optional[str] = None          # 最后一次成功的 model_compare 关键词
    any_compare: Optional[str] = None   # 任一次 model_compare 关键词
    mercari: Optional[str] = None

    for step in trace or []:
        tool = getattr(step, "tool", None) or (step.get("tool") if isinstance(step, dict) else None)
        args = getattr(step, "arguments", None)
        if args is None and isinstance(step, dict):
            args = step.get("arguments")
        if not isinstance(args, dict):
            continue
        kw = (args.get("keyword") or args.get("query") or "").strip()
        if not kw:
            continue

        if tool == _MODEL_COMPARE_TOOL:
            any_compare = kw
            raw = getattr(step, "result_full", None)
            if raw is None and isinstance(step, dict):
                raw = step.get("result_full")
            try:
                data = json.loads(raw) if raw else {}
            except (ValueError, TypeError):
                data = {}
            if isinstance(data, dict) and data.get("searched_model"):
                best = kw
        elif tool in _MERCARI_TOOLS and mercari is None:
            mercari = kw

    chosen = best or any_compare or mercari
    if not chosen:
        return None
    return chosen if _PRICE_INTENT.search(chosen) else f"{chosen} 最安値"


# --------------------------------------------------------------------------- #
# 打分
# --------------------------------------------------------------------------- #
def _norm_url(url: Optional[str]) -> str:
    if not url:
        return ""
    p = urlparse(url)
    host = (p.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return f"{host}{(p.path or '').rstrip('/')}"


def _host(url: Optional[str]) -> str:
    host = (urlparse(url or "").netloc or "").lower()
    return host[4:] if host.startswith("www.") else host


def _derive_floor(
    our_items: List[Dict[str, Any]], ratio: float = DEFAULT_FLOOR_RATIO
) -> Optional[int]:
    """价格下限：优先用被搜机型的新品最安値 × ratio。

    用"被搜机型"而不是最贵的那个变体 —— 否则 ¥77,510 的高配会把下限推到 ¥27k，
    连真正便宜的本体（实测有 ¥22,600 的 Pro+ 9577cc）都会被误排除。
    """
    anchor: Optional[int] = None
    for it in our_items:
        if it.get("role") == "searched" and it.get("price"):
            anchor = int(it["price"])
            break
    if anchor is None:
        catalog = [
            int(it["price"])
            for it in our_items
            if it.get("price") and it.get("role") in ("newer", "candidate")
        ]
        anchor = min(catalog) if catalog else None
    if anchor is None:
        return None
    return int(anchor * ratio)


def product_keyword(trace: List[Any]) -> Optional[str]:
    """agent 自己用来查这个产品的关键词（不带"最安値"）。

    这是"产品身份"的最佳来源:它是模型有意选的、简短干净的日文型号名。
    **不要**改用 kakaku 的 series 名 —— 实测 kakaku 会返回这种目录标题:
      "Apple アップル 純正 AirPods Pro 第2世代 USB-C エアポッズプロ2 … ラッピング可"
    拿它当 token 要求会得到 12 个 token，任何正常挂牌都匹配不全，
    结果把**所有** Mercari 商品都误杀，记分板反而只剩 kakaku 自己跟 Google 比。
    """
    fair = build_fair_query(trace)
    if not fair:
        return None
    return re.sub(r"\s*最安値\s*$", "", fair).strip() or None


def required_product_tokens(keyword: Optional[str]) -> List[str]:
    """关键词 → 必须出现在标题里的 token。

    配件词表管不了"不同产品":实测 Mercari 里 "AirPods (第2世代) 早い者勝ち‼️" ¥18,888
    既不是配件也不是残缺品，但它是 **AirPods 2 而不是 AirPods Pro 2**，
    混进来就会刷出假的最低价（它比真品便宜一万多）。
    """
    return tokens_of(keyword) if keyword else []


def matches_product(title: str, required: List[str]) -> bool:
    """标题是否覆盖了全部系列 token。

    两条宽松处理，避免误杀真商品:
    - 品牌罗马字↔片假名互通("Braun シリーズ9 Pro+ …" 里没有「ブラウン」也算命中);
    - 含数字的 token 允许只匹配数字("シリーズ9" 由 "S9 Pro" 里的 9 满足)。
    """
    if not required:
        return True
    t = (title or "").lower()
    for tok in required:
        if any(v.lower() in t for v in token_variants(tok)):
            continue
        digits = re.sub(r"\D", "", tok)
        if digits and digits in t:
            continue
        return False
    return True


def comparability(
    our_best: Optional[Dict[str, Any]], google_best: Optional[Dict[str, Any]]
) -> str:
    """双方最低价是不是同一个型番。

    为什么必须单独标出来:实测两次"近似同价"都**不是同型号**，
    比出来的 win/tie 因此含义完全不同：
      · Braun   —— kakaku ¥29,800 是 2022 年 9435s-V，我方 ¥29,333 是 2025 年 Pro+ 9517s-V；
      · AirPods —— kakaku ¥28,000 的 MQD83J/A 是 Lightning 版，不是 USB-C 的 MTJV3J/A。
    一个"tie"若发生在不同型号之间，它既不能证明我们更强，也不能拿来做买哪个的依据。
    """
    if not our_best or not google_best:
        return "unknown"
    ours = set(our_best.get("model_nos") or [])
    theirs = set(
        _guess_model_nos(f"{google_best.get('title', '')} {google_best.get('snippet', '')}")
    )
    if not ours or not theirs:
        return "unknown"       # 标题没写型番 —— 不知道，不能假装同款
    return "same_model" if ours & theirs else "different_model"


def _google_item_price(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """一条 Google 结果的最低价（附 source/verified）。"""
    prices = [p for p in (item.get("prices") or []) if p.get("price")]
    if not prices:
        return None
    return min(prices, key=lambda p: p["price"])


def _find_in_google(
    our_item: Dict[str, Any], google_items: List[Dict[str, Any]]
) -> Optional[int]:
    """我方这条在 Google top-N 里的排名（1-based），找不到返回 None。"""
    target_url = _norm_url(our_item.get("url"))
    target_host = _host(our_item.get("url"))
    target_models = set(our_item.get("model_nos") or [])

    for g in google_items:
        if target_url and target_url == _norm_url(g.get("link")):
            return g.get("rank")
        if target_models and target_host and target_host == _host(g.get("link")):
            g_models = set(_guess_model_nos(f"{g.get('title', '')} {g.get('snippet', '')}"))
            if target_models & g_models:
                return g.get("rank")
    return None


def score(
    our_items: List[Dict[str, Any]],
    google_items: List[Dict[str, Any]],
    keyword: Optional[str] = None,
    floor_ratio: float = DEFAULT_FLOOR_RATIO,
) -> Dict[str, Any]:
    """算一次对照分。纯函数、只吃 plain dict —— 所以能对历史记录重算。

    verdict:
      loss —— Google top-N 里有比我方更便宜的同类本体（漏项）。**最有价值的信号。**
      win  —— 无漏项，且我方最低价便宜超过 WIN_MARGIN。
      tie  —— 其余。
      n/a  —— 任一侧没有可比价格。
    """
    floor = _derive_floor(our_items, floor_ratio)
    required = required_product_tokens(keyword)

    ours_body: List[Dict[str, Any]] = []
    ours_excluded: List[Dict[str, Any]] = []
    for it in our_items:
        price = it.get("price")
        excl = classify_exclusion(it.get("title") or "")
        if excl is not None:
            ours_excluded.append({**it, "excluded_by": excl[0], "matched": excl[1]})
            continue
        # 产品线闸只对 Mercari 挂牌生效：kakaku 目录条目本来就是同产品线取来的，
        # 它们的名称格式规整，再过一道只会误杀。
        if it.get("role") == "listing" and not matches_product(it.get("title") or "", required):
            ours_excluded.append({
                **it, "excluded_by": "wrong_product", "matched": " ".join(required),
            })
            continue
        if not price:
            continue
        if floor is not None and price < floor:
            ours_excluded.append({**it, "excluded_by": "below_floor", "matched": floor})
            continue
        ours_body.append(it)

    # Google 侧只按**标题**判配件：页面标题才代表这个页面是什么。
    # 若连 snippet 一起判，kakaku 目录页顺带提到"替刃"就会被误排除。
    g_body: List[Dict[str, Any]] = []
    g_excluded: List[Dict[str, Any]] = []
    for g in google_items:
        best = _google_item_price(g)
        excl = classify_exclusion(g.get("title") or "")
        if excl is not None:
            g_excluded.append({
                "rank": g.get("rank"), "title": g.get("title"), "link": g.get("link"),
                "excluded_by": excl[0], "matched": excl[1],
            })
            continue
        if not best:
            continue
        if floor is not None and best["price"] < floor:
            g_excluded.append({
                "rank": g.get("rank"), "title": g.get("title"), "link": g.get("link"),
                "excluded_by": "below_floor", "matched": floor,
            })
            continue
        g_body.append({**g, "best_price": best})

    our_best = min(ours_body, key=lambda it: it["price"]) if ours_body else None
    our_min = our_best["price"] if our_best else None

    g_best = min(g_body, key=lambda g: g["best_price"]["price"]) if g_body else None
    google_min = g_best["best_price"]["price"] if g_best else None

    # 漏项：Google 上更便宜的本体。每条都留 title/url/verified，让人一眼看出真漏还是误报。
    miss: List[Dict[str, Any]] = []
    if our_min is not None:
        for g in g_body:
            if g["best_price"]["price"] < our_min:
                miss.append({
                    "rank": g.get("rank"),
                    "title": g.get("title"),
                    "link": g.get("link"),
                    "price": g["best_price"]["price"],
                    "price_source": g["best_price"]["source"],
                    "verified": g["best_price"]["verified"],
                })
        miss.sort(key=lambda m: m["price"])

    compare_kind = comparability(our_best, g_best)

    if our_min is None:
        verdict, reason = "n/a", "我方未取到可比的本体价格"
    elif google_min is None:
        verdict, reason = "n/a", "Google 侧未取到可比的本体价格"
    elif miss:
        verdict = "loss"
        reason = (
            f"Google 上有 {len(miss)} 条更便宜的同类本体，"
            f"最低 ¥{miss[0]['price']:,}（我方 ¥{our_min:,}）"
        )
    elif our_min < google_min * (1 - WIN_MARGIN):
        verdict = "win"
        reason = f"我方 ¥{our_min:,} 比 Google 最低 ¥{google_min:,} 便宜 {google_min - our_min:,} 円"
    else:
        verdict = "tie"
        reason = f"我方 ¥{our_min:,} 与 Google 最低 ¥{google_min:,} 差距在 {int(WIN_MARGIN * 100)}% 内"

    # 不同型号（或型番不明）之间的 win/tie 是弱证据，必须写进 reason，不能只藏在字段里
    if verdict in ("win", "tie", "loss"):
        if compare_kind == "different_model":
            reason += "；⚠ 双方最低价并非同一型番，价差里含规格差异，不能直接当性价比结论"
        elif compare_kind == "unknown":
            reason += "；⚠ 至少一侧未注明型番，无法确认是否同款"

    return {
        "verdict": verdict,
        "reason": reason,
        "comparability": compare_kind,
        "floor_price": floor,
        "our_min": our_min,
        "our_best": (
            {
                "title": our_best["title"], "price": our_min,
                "url": our_best.get("url"), "source": our_best.get("source"),
                "model_nos": our_best.get("model_nos") or [],
                "release": our_best.get("release"),
                "shops": our_best.get("shops"),
                "ambiguous": ambiguous_flags(our_best["title"]),
            }
            if our_best else None
        ),
        "google_min": google_min,
        "google_best": (
            {
                "rank": g_best.get("rank"), "title": g_best.get("title"),
                "link": g_best.get("link"), "price": google_min,
                "price_source": g_best["best_price"]["source"],
                "verified": g_best["best_price"]["verified"],
            }
            if g_best else None
        ),
        # 记录项，不单独构成 win：Google 几乎不索引单条 Mercari 商品页，
        # 否则会刷出无意义的连胜。它的价值在于量化"我们推荐的东西在 Google 排第几"。
        "our_pick_google_rank": _find_in_google(our_best, google_items) if our_best else None,
        "miss": miss,
        "counts": {
            "our_body": len(ours_body),
            "our_excluded": len(ours_excluded),
            "google_items": len(google_items),
            "google_body": len(g_body),
            "google_excluded": len(g_excluded),
        },
        "required_tokens": required,
        "our_excluded": ours_excluded,
        "google_excluded": g_excluded,
        "scoring_version": SCORING_VERSION,
    }


# --------------------------------------------------------------------------- #
# 记录读写
# --------------------------------------------------------------------------- #
def build_record(
    raw_query: str,
    fair_query: Optional[str],
    our_items: List[Dict[str, Any]],
    google: Dict[str, Dict[str, Any]],
    agent_meta: Optional[Dict[str, Any]] = None,
    timestamp: Optional[str] = None,
    keyword: Optional[str] = None,
) -> Dict[str, Any]:
    """组一条记录（含原始结果 + 当次 verdict 快照）。"""
    record: Dict[str, Any] = {
        "ts": timestamp or datetime.now().isoformat(timespec="seconds"),
        "source": "google_cse",  # CSE ≠ google.com，措辞上别混
        "raw_query": raw_query,
        "fair_query": fair_query,
        # 存下来，rescore 时才能用同一套产品身份重算
        "product_keyword": keyword,
        "agent": agent_meta or {},
        "our_items": our_items,
        "google": google,
    }
    record["comparisons"] = _score_all(record)
    return record


def _score_all(record: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, payload in (record.get("google") or {}).items():
        if not isinstance(payload, dict):
            continue
        if payload.get("error"):
            out[key] = {"verdict": "n/a", "reason": f"Google 取数失败: {payload['error']}"}
            continue
        out[key] = score(
            record.get("our_items") or [],
            payload.get("items") or [],
            keyword=record.get("product_keyword"),
        )
    return out


def rescore_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """用当前打分逻辑重算历史记录（不需要重新打 API）。"""
    updated = dict(record)
    updated["comparisons"] = _score_all(record)
    return updated


def append_record(path: Path, record: Dict[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return path


def load_records(path: Path) -> List[Dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except ValueError:
            logger.warning("跳过无法解析的 benchmark 记录行")
    return records


# --------------------------------------------------------------------------- #
# 服务门面
# --------------------------------------------------------------------------- #
class BenchmarkService:
    """跑一次 Google 对照并落盘。**只读 AgentResult，绝不回写 messages。**"""

    def __init__(self, google_client, output_path: Path, floor_ratio: float = DEFAULT_FLOOR_RATIO):
        self.google = google_client
        self.output_path = Path(output_path)
        self.floor_ratio = floor_ratio

    @property
    def enabled(self) -> bool:
        return bool(getattr(self.google, "configured", False))

    async def compare(self, raw_query: str, agent_result: Any) -> Optional[Dict[str, Any]]:
        """跑对照。任何失败都返回 None 或带 error 的记录，绝不抛给调用方。"""
        trace = getattr(agent_result, "trace", None) or []
        our_items = extract_our_items(trace)
        fair_query = build_fair_query(trace)
        keyword = product_keyword(trace)

        google: Dict[str, Dict[str, Any]] = {"raw": await self.google.search(raw_query)}
        # 公平 query 与原样 query 相同时不重复消耗配额
        if fair_query and fair_query.strip() != (raw_query or "").strip():
            google["fair"] = await self.google.search(fair_query)

        record = build_record(
            raw_query=raw_query,
            fair_query=fair_query,
            our_items=our_items,
            google=google,
            keyword=keyword,
            agent_meta={
                "iterations": getattr(agent_result, "iterations", None),
                "truncated": getattr(agent_result, "truncated", None),
                "answer_chars": len(getattr(agent_result, "answer", "") or ""),
                "tools_called": [
                    getattr(s, "tool", None) or (s.get("tool") if isinstance(s, dict) else None)
                    for s in trace
                ],
            },
        )
        append_record(self.output_path, record)
        return record


def summarize(records: List[Dict[str, Any]], key: str = "fair") -> Dict[str, Any]:
    """累计记分板。key 选 "fair"（默认，更硬的基线）或 "raw"。"""
    tally = {"win": 0, "tie": 0, "loss": 0, "n/a": 0}
    for r in records:
        comp = (r.get("comparisons") or {}).get(key) or (r.get("comparisons") or {}).get("raw")
        verdict = (comp or {}).get("verdict", "n/a")
        tally[verdict] = tally.get(verdict, 0) + 1
    decided = tally["win"] + tally["tie"] + tally["loss"]
    return {
        "total": len(records),
        "decided": decided,
        "win_rate": round(tally["win"] / decided, 3) if decided else None,
        **tally,
    }
