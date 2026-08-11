"""
Mercari 原生工具（native function calling tools）

定义供 LLM 自主调用的具体工具，后端接真实 ScraperService：

- SearchMercariTool (`search_mercari`)：按关键词/价格/状态搜索，返回紧凑商品列表。
- PriceStatisticsTool (`get_price_statistics`)：抓一批算 count/min/max/median/average，
  让 agent 判断"贵不贵/是不是好价"。

所有工具都是 BaseTool 子类，通过 ToolRegistry 注册，用 to_openai_function() 生成 schema。
返回给模型的 data 均为紧凑、可 JSON 序列化的结构（不塞整个 ProductEntity）。

Author: Kaidoki Team (native tools)
"""

import statistics
from typing import Any, Dict, List, Optional, Tuple

from .framework.base_tool import BaseTool, ToolResult, ToolStatus
from ..domain.entities.query import QueryEntity
from ..infrastructure.scraping.scraper_service import ScraperService
from ..shared.utils.item_filters import (
    classify_exclusion,
    matches_product,
    required_product_tokens,
)
from ..shared.utils.logger_utils import get_logger

logger = get_logger(__name__)

# Mercari 商品状态（itemConditionId 对应的可读日文；scraper 只认这些精确字符串）。
# 注意第一档「新品・未使用」= 全新未拆封 —— Mercari 上有大量这种"新品"，往往比
# kakaku 的新品最安値更便宜。"只买新品"的需求**不应该**因为 Mercari 是二手平台而跳过它。
_CONDITION_ENUM = [
    "新品・未使用",
    "未使用に近い",
    "目立った傷や汚れなし",
    "やや傷や汚れあり",
    "傷や汚れあり",
    "全体的に状態が悪い",
]

# "只买新品/未使用" 这类需求的推荐组合（供 prompt 与工具描述引用）
_UNUSED_CONDITIONS = ["新品・未使用", "未使用に近い"]


def _compact_product(p) -> Dict[str, Any]:
    """把 ProductEntity 压成给模型的紧凑 dict（只保留决策必需字段）。"""
    return {
        "id": p.id,
        "title": p.title,
        "price": p.price,
        "condition": p.condition or "不明",
        "url": p.url,
    }


def _normalize_conditions(condition: Any) -> Tuple[List[str], List[str]]:
    """把模型传来的 condition（字符串 / 数组 / 逗号串）拆成 (合法项, 非法项)。

    历史坑：非法值曾被**静默丢弃**（`condition if condition in ENUM else None`），
    模型传 "新品" / "未使用" 就退化成无过滤搜索且毫无提示，结果看起来"正常"但答案是错的。
    现在非法项会被显式回报给模型，让它改用 enum 里的精确字符串重试。
    """
    if condition is None:
        return [], []
    raw = condition if isinstance(condition, (list, tuple)) else str(condition).split(",")
    valid, invalid = [], []
    for item in raw:
        c = str(item).strip()
        if not c:
            continue
        if c in _CONDITION_ENUM:
            if c not in valid:
                valid.append(c)
        else:
            invalid.append(c)
    return valid, invalid


def _invalid_condition_result(invalid: List[str]) -> ToolResult:
    """非法 condition → 明确报错给模型（不静默降级为无过滤搜索）。"""
    return ToolResult(
        status=ToolStatus.ERROR,
        error=(
            f"condition 取值非法: {invalid}。只接受这些精确字符串: {_CONDITION_ENUM}。"
            f"想找全新/未使用品请传 {_UNUSED_CONDITIONS}。"
        ),
    )


def _build_query(
    keyword: str,
    price_min: Optional[int] = None,
    price_max: Optional[int] = None,
    conditions: Optional[List[str]] = None,
) -> QueryEntity:
    # 多个成色用逗号串给下游（scraper 会拆开映射成 item_condition_id=1,2）
    return QueryEntity(
        original_query=keyword,
        keywords=[keyword],
        price_min=int(price_min) if price_min is not None else None,
        price_max=int(price_max) if price_max is not None else None,
        condition=",".join(conditions) if conditions else None,
    )


class SearchMercariTool(BaseTool):
    """在 Mercari 搜索商品，返回紧凑列表。"""

    def __init__(self, scraper_service: ScraperService):
        super().__init__(
            name="search_mercari",
            description=(
                "在 Mercari（日本个人间交易平台）搜索在售商品。返回紧凑商品列表"
                "（id/title/price/condition/url）。支持价格区间与成色过滤，可按价格排序。"
                "**重要：Mercari 不只有二手品** —— 成色「新品・未使用」就是全新未拆封的商品，"
                "「未使用に近い」几乎等同全新。所以用户说『只买新品』时也应该用 "
                "condition=[\"新品・未使用\"]（或再加「未使用に近い」）搜一次，"
                "它常常比 kakaku 的新品最安値更便宜，不要因为『这是二手平台』而跳过。"
            ),
        )
        self.scraper = scraper_service

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词，如 'AirPods Pro 第2世代'。用日文或商品通用名效果最好。",
                    },
                    "price_min": {
                        "type": "integer",
                        "description": "最低价格（日元），可选。",
                    },
                    "price_max": {
                        "type": "integer",
                        "description": "最高价格（日元），可选。用于预算过滤。",
                    },
                    "condition": {
                        "type": "array",
                        "items": {"type": "string", "enum": _CONDITION_ENUM},
                        "description": (
                            "成色过滤，可选，可多选。想要全新品传 [\"新品・未使用\"]；"
                            "放宽到几乎全新传 [\"新品・未使用\", \"未使用に近い\"]。"
                            "必须用 enum 里的精确字符串，传别的会报错（不会被忽略）。"
                        ),
                    },
                    "sort": {
                        "type": "string",
                        "enum": ["price_asc", "price_desc"],
                        "description": "对返回结果按价格排序，可选。price_asc=从低到高。",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回商品数量上限，默认 10，建议 5~20。",
                    },
                },
                "required": ["keyword"],
            }
        }

    async def execute(
        self,
        keyword: str,
        price_min: Optional[int] = None,
        price_max: Optional[int] = None,
        condition: Any = None,
        sort: Optional[str] = None,
        limit: int = 10,
        **kwargs,  # 吸收模型可能给出的多余/幻觉参数，避免整次工具调用失败
    ) -> ToolResult:
        limit = max(1, min(int(limit or 10), 30))
        conditions, invalid = _normalize_conditions(condition)
        if invalid:
            return _invalid_condition_result(invalid)
        query = _build_query(keyword, price_min, price_max, conditions)
        # 需要按价格排序时，先抓更大样本再排序截断；否则只是把相关度前 limit 条重排，
        # 给不出预算内真正最便宜/最贵的商品。
        fetch_n = max(limit, 60) if sort in ("price_asc", "price_desc") else limit
        result = await self.scraper.scrape(query, max_products=fetch_n)

        products = [p for p in result.products if not getattr(p, "sold", False)]
        if sort == "price_asc":
            products.sort(key=lambda p: (p.price is None, p.price or 0))
        elif sort == "price_desc":
            products.sort(key=lambda p: (p.price is None, -(p.price or 0)))

        compact = [_compact_product(p) for p in products[:limit]]
        return ToolResult(
            status=ToolStatus.SUCCESS,
            data={
                "keyword": keyword,
                # 回显实际生效的过滤条件，让模型（和 trace）能看出搜的到底是什么
                "condition_filter": conditions or None,
                "price_min": price_min,
                "price_max": price_max,
                "count": len(compact),
                "total_found": result.total_found,
                "products": compact,
            },
        )


class PriceStatisticsTool(BaseTool):
    """抓一批商品算价格统计，供 agent 判断价位。"""

    def __init__(self, scraper_service: ScraperService, sample_size: int = 80):
        super().__init__(
            name="get_price_statistics",
            description=(
                "抓取某关键词在 Mercari 的一批在售商品并计算**本体**价格统计"
                "（count/min/max/median/average），用于判断某个价格是否划算。"
                "会自动剔除配件（替刃/ケース/保護フィルム…）、残缺品（刃無し/片耳…）"
                "和不同产品（如查 AirPods Pro 时混进来的 AirPods），"
                "并回报剔除了多少条、按什么规则（excluded 字段）。"
                "**强烈建议同时传 price_min**（例如 kakaku 新品最安値的 30~40%）——"
                "关键词永远挡不住所有配件，价格下限是第二道闸。"
                "unfiltered 字段保留未过滤的原始统计，便于对照。"
            ),
        )
        self.scraper = scraper_service
        self.sample_size = sample_size

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "要统计价格行情的关键词。",
                    },
                    "condition": {
                        "type": "array",
                        "items": {"type": "string", "enum": _CONDITION_ENUM},
                        "description": (
                            "限定成色再统计，可选，可多选。"
                            "想知道『全新未使用品的行情』传 [\"新品・未使用\"]。"
                        ),
                    },
                    "price_min": {
                        "type": "integer",
                        "description": (
                            "价格下限（日元），可选但**强烈建议给**。"
                            "关键词永远挡不住所有配件 —— 实测 'ニコン D850' 不给下限时"
                            "中位数只有 ¥5,000（样本里全是镜头盖/保护膜/书籍）。"
                            "取 kakaku 新品最安値的 30~40% 是个安全值。"
                        ),
                    },
                },
                "required": ["keyword"],
            }
        }

    async def execute(
        self,
        keyword: str,
        condition: Any = None,
        price_min: Optional[int] = None,
        **kwargs,  # 吸收模型可能给出的多余/幻觉参数
    ) -> ToolResult:
        conditions, invalid = _normalize_conditions(condition)
        if invalid:
            return _invalid_condition_result(invalid)
        query = _build_query(keyword, price_min=price_min, conditions=conditions)
        result = await self.scraper.scrape(query, max_products=self.sample_size)

        on_sale = [
            p for p in result.products
            if p.price and p.price > 0 and not getattr(p, "sold", False)
        ]
        # 未过滤的原始统计一并留着 —— 让模型能看出过滤起了多大作用，
        # 也让"过滤是不是过头了"这件事查得出来。
        raw_prices = sorted(p.price for p in on_sale)

        # 三层过滤：配件/残缺词表 → 产品身份 token → 价格下限。
        # 关键词行情对"本体贵不贵"没有参考价值（D850 中位数 ¥5,000 vs 本体十几万）。
        required = required_product_tokens(keyword)
        kept: List[Any] = []
        excluded_by: Dict[str, int] = {}
        samples: Dict[str, str] = {}

        def drop(reason: str, product) -> None:
            excluded_by[reason] = excluded_by.get(reason, 0) + 1
            samples.setdefault(reason, f"¥{product.price} {(product.title or '')[:34]}")

        for p in on_sale:
            title = p.title or ""
            excl = classify_exclusion(title)
            if excl is not None:
                drop(excl[0], p)
                continue
            if not matches_product(title, required):
                drop("wrong_product", p)
                continue
            if price_min is not None and p.price < int(price_min):
                drop("below_price_min", p)
                continue
            kept.append(p)

        prices = sorted(p.price for p in kept)
        excluded = {
            "count": len(on_sale) - len(kept),
            "by": excluded_by,
            "examples": samples,
        }

        # 没给 price_min 时，词表挡不住的杂物会把中位数压到毫无意义的水平
        # （实测 D850 过滤后 median 仍只有 ¥1,000，而本体在十几万）。
        # 用 max/median 比值检测这种双峰分布，直接把"该重查"说出来。
        warnings: List[str] = []
        if prices and price_min is None:
            median = statistics.median(prices)
            if median > 0 and prices[-1] / median >= 10:
                warnings.append(
                    f"样本疑似混着配件与本体（最高价 ¥{prices[-1]:,} 是中位数 "
                    f"¥{int(median):,} 的 {int(prices[-1] / median)} 倍）。"
                    "这个中位数不能代表本体行情 —— 请给 price_min"
                    "（例如 kakaku 新品最安値的 30~40%）后重查。"
                )
        unfiltered = (
            {
                "count": len(raw_prices),
                "min": raw_prices[0],
                "max": raw_prices[-1],
                "median": int(statistics.median(raw_prices)),
            }
            if raw_prices else {"count": 0}
        )

        if not prices:
            return ToolResult(
                status=ToolStatus.SUCCESS,
                data={
                    "keyword": keyword,
                    "condition_filter": conditions or None,
                    "price_min": price_min,
                    "basis": "body_only",
                    "count": 0,
                    "note": (
                        "过滤后没有剩下可用于本体行情的商品。"
                        "可能是关键词太宽（全是配件）或 price_min 定得太高。"
                        if raw_prices else "未抓到带价格的在售商品"
                    ),
                    "excluded": excluded,
                    "unfiltered": unfiltered,
                },
            )

        return ToolResult(
            status=ToolStatus.SUCCESS,
            data={
                "keyword": keyword,
                "condition_filter": conditions or None,
                "price_min": price_min,
                # 明确声明这是**本体**行情，不是关键词行情
                "basis": "body_only",
                "warnings": warnings,
                "excluded": excluded,
                "unfiltered": unfiltered,
                "count": len(prices),
                "min": prices[0],
                "max": prices[-1],
                "median": int(statistics.median(prices)),
                "average": int(statistics.mean(prices)),
                "currency": "JPY",
            },
        )


class RecommendMercariTool(BaseTool):
    """把整条固定流程(解析→抓取→LLM 重排)包成一个高层工具,一步给出成品推荐。"""

    def __init__(self, scraper_service: ScraperService, query_parser, recommendation_service):
        super().__init__(
            name="recommend_deals",
            description=(
                "运行完整的推荐流程:理解自然语言查询 → 抓取 Mercari 在售商品 → "
                "LLM 按策略重排,一步返回一份现成的高性价比推荐(含推荐理由)。"
                "适合直接、明确的'帮我找 X 的好货/性价比高的 X'类请求。"
                "已内置配件/残缺品/异产品过滤（与 search_mercari 同一套词表），"
                "返回的 filtered 字段交代抓了多少、留了多少、按什么剔除。"
                "若需要比较多个商品、先查价格行情再判断、或多步精细控制,"
                "请改用 search_mercari + get_price_statistics 组合。"
            ),
        )
        self.scraper = scraper_service
        self.query_parser = query_parser
        self.recommendation = recommendation_service

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "自然语言购物需求,如 'iPhone 15 128GB 8万円以下'、'性价比高的二手 AirPods Pro'。",
                    },
                    "strategy": {
                        "type": "string",
                        "enum": ["price_oriented", "quality_oriented", "balanced", "trending"],
                        "description": "推荐策略,可选,默认 balanced。price_oriented=偏低价,quality_oriented=偏成色。",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "返回推荐数量,默认 8,建议 5~12。",
                    },
                },
                "required": ["query"],
            }
        }

    async def execute(
        self,
        query: str,
        strategy: str = "balanced",
        max_results: int = 8,
        **kwargs,  # 吸收模型可能给出的多余/幻觉参数
    ) -> ToolResult:
        max_results = max(1, min(int(max_results or 8), 20))
        parsed = await self.query_parser.parse(query)
        q = parsed.query
        # 多抓一些：过滤会砍掉一部分，抓 max_results*2 会导致重排样本太少
        scraping = await self.scraper.scrape(q, max_products=max_results * 4)
        if not scraping.products:
            return ToolResult(
                status=ToolStatus.SUCCESS,
                data={"query": query, "count": 0, "note": "未抓到符合条件的在售商品"},
            )

        # 这条固定流水线原先**绕过了所有过滤** —— 它是唯一没吃到配件/残缺品/异产品
        # 过滤的入口。实测查 "パタゴニア レトロX フリース 中古 安い" 时它的 top1 是
        # ¥3,000 的**童装**(12-18M)。过滤放在重排之前:别把 LLM 的重排预算浪费在配件上。
        required = required_product_tokens(" ".join(getattr(q, "keywords", None) or []) or query)
        kept, excluded_by = [], {}
        for p in scraping.products:
            title = p.title or ""
            excl = classify_exclusion(title)
            if excl is not None:
                excluded_by[excl[0]] = excluded_by.get(excl[0], 0) + 1
                continue
            if not matches_product(title, required):
                excluded_by["wrong_product"] = excluded_by.get("wrong_product", 0) + 1
                continue
            kept.append(p)

        if not kept:
            return ToolResult(
                status=ToolStatus.SUCCESS,
                data={
                    "query": query,
                    "count": 0,
                    "note": (
                        "抓到了商品，但全被判为配件/残缺品/异产品。"
                        "可能是关键词太宽，或这个品类的标题写法不在词表里。"
                    ),
                    "excluded": {"count": len(scraping.products), "by": excluded_by},
                },
            )

        rec = await self.recommendation.recommend(kept, q, max_results, strategy)
        return ToolResult(
            status=ToolStatus.SUCCESS,
            data={
                "query": query,
                "understood": {
                    "keywords": list(getattr(q, "keywords", None) or []),
                    "price_min": getattr(q, "price_min", None),
                    "price_max": getattr(q, "price_max", None),
                    "condition": getattr(q, "condition", None),
                    "category": getattr(q, "category", None),
                },
                # 与其它工具一致地交代过滤情况（这条流水线以前是完全不过滤的）
                "filtered": {
                    "basis": "body_only",
                    "scraped": len(scraping.products),
                    "kept": len(kept),
                    "excluded_by": excluded_by,
                },
                "strategy": rec.strategy_used,
                "reasoning": getattr(rec, "reasoning", None),
                "count": len(rec.recommendations),
                "products": [_compact_product(p) for p in rec.recommendations],
            },
        )


def build_mercari_tool_registry(
    scraper_service: ScraperService,
    query_parser=None,
    recommendation_service=None,
    include_model_compare: bool = False,
    model_compare_backends=None,
):
    """创建并注册 Mercari 工具，返回 ToolRegistry。

    低层工具(search_mercari / get_price_statistics)总是注册；
    仅当同时传入 query_parser 与 recommendation_service 时，才注册把整条固定流程
    包起来的高层工具 recommend_deals。
    仅当 include_model_compare=True 时，注册新品/新型号对比工具
    get_new_and_newer_models(默认后端:kakaku 优先 + 品牌官方商店兜底,
    复用 scraper_service 的浏览器;也可用 model_compare_backends 注入自定义后端)。
    """
    from .framework.tool_registry import ToolRegistry

    registry = ToolRegistry()
    registry.register(SearchMercariTool(scraper_service), category="mercari")
    registry.register(PriceStatisticsTool(scraper_service), category="mercari")
    if query_parser is not None and recommendation_service is not None:
        registry.register(
            RecommendMercariTool(scraper_service, query_parser, recommendation_service),
            category="mercari",
        )
    if include_model_compare:
        from .model_compare import GetNewAndNewerModelsTool, build_default_backends

        backends = model_compare_backends or build_default_backends(scraper_service)
        registry.register(GetNewAndNewerModelsTool(backends), category="mercari")
    return registry
