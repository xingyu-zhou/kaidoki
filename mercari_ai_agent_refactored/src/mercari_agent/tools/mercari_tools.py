"""
Mercari 原生工具（native function calling tools）

定义供 LLM 自主调用的具体工具，后端接真实 ScraperService：

- SearchMercariTool (`search_mercari`)：按关键词/价格/状态搜索，返回紧凑商品列表。
- PriceStatisticsTool (`get_price_statistics`)：抓一批算 count/min/max/median/average，
  让 agent 判断"贵不贵/是不是好价"。

所有工具都是 BaseTool 子类，通过 ToolRegistry 注册，用 to_openai_function() 生成 schema。
返回给模型的 data 均为紧凑、可 JSON 序列化的结构（不塞整个 ProductEntity）。

Author: Mercari AI Agent Team (native tools)
"""

import statistics
from typing import Any, Dict, List, Optional

from .framework.base_tool import BaseTool, ToolResult, ToolStatus
from ..domain.entities.query import QueryEntity
from ..infrastructure.scraping.scraper_service import ScraperService
from ..shared.utils.logger_utils import get_logger

logger = get_logger(__name__)

# Mercari 商品状态（itemConditionId 对应的可读日文；scraper 只认这些精确字符串）
_CONDITION_ENUM = [
    "新品・未使用",
    "未使用に近い",
    "目立った傷や汚れなし",
    "やや傷や汚れあり",
    "傷や汚れあり",
    "全体的に状態が悪い",
]


def _compact_product(p) -> Dict[str, Any]:
    """把 ProductEntity 压成给模型的紧凑 dict（只保留决策必需字段）。"""
    return {
        "id": p.id,
        "title": p.title,
        "price": p.price,
        "condition": p.condition or "不明",
        "url": p.url,
    }


def _build_query(
    keyword: str,
    price_min: Optional[int] = None,
    price_max: Optional[int] = None,
    condition: Optional[str] = None,
) -> QueryEntity:
    return QueryEntity(
        original_query=keyword,
        keywords=[keyword],
        price_min=int(price_min) if price_min is not None else None,
        price_max=int(price_max) if price_max is not None else None,
        condition=condition if condition in _CONDITION_ENUM else None,
    )


class SearchMercariTool(BaseTool):
    """在 Mercari 搜索商品，返回紧凑列表。"""

    def __init__(self, scraper_service: ScraperService):
        super().__init__(
            name="search_mercari",
            description=(
                "在 Mercari（日本二手交易平台）搜索在售商品。用于查看具体有哪些商品、"
                "价格、成色和链接。返回紧凑商品列表（id/title/price/condition/url）。"
                "支持价格区间与成色过滤，可按价格排序。"
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
                        "type": "string",
                        "enum": _CONDITION_ENUM,
                        "description": "商品成色过滤，可选。",
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
        condition: Optional[str] = None,
        sort: Optional[str] = None,
        limit: int = 10,
        **kwargs,  # 吸收模型可能给出的多余/幻觉参数，避免整次工具调用失败
    ) -> ToolResult:
        limit = max(1, min(int(limit or 10), 30))
        query = _build_query(keyword, price_min, price_max, condition)
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
                "抓取某关键词在 Mercari 的一批在售商品并计算价格统计"
                "（count/min/max/median/average），用于判断某个价格是否划算、"
                "行情大致在什么区间。不返回具体商品，只返回统计数字。"
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
                        "type": "string",
                        "enum": _CONDITION_ENUM,
                        "description": "限定成色再统计，可选。",
                    },
                },
                "required": ["keyword"],
            }
        }

    async def execute(
        self,
        keyword: str,
        condition: Optional[str] = None,
        **kwargs,  # 吸收模型可能给出的多余/幻觉参数
    ) -> ToolResult:
        query = _build_query(keyword, condition=condition)
        result = await self.scraper.scrape(query, max_products=self.sample_size)

        prices = sorted(
            p.price
            for p in result.products
            if p.price and p.price > 0 and not getattr(p, "sold", False)
        )
        if not prices:
            return ToolResult(
                status=ToolStatus.SUCCESS,
                data={
                    "keyword": keyword,
                    "count": 0,
                    "note": "未抓到带价格的在售商品",
                },
            )

        return ToolResult(
            status=ToolStatus.SUCCESS,
            data={
                "keyword": keyword,
                "condition": condition,
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
        scraping = await self.scraper.scrape(q, max_products=max_results * 2)
        if not scraping.products:
            return ToolResult(
                status=ToolStatus.SUCCESS,
                data={"query": query, "count": 0, "note": "未抓到符合条件的在售商品"},
            )
        rec = await self.recommendation.recommend(scraping.products, q, max_results, strategy)
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
):
    """创建并注册 Mercari 工具，返回 ToolRegistry。

    低层工具(search_mercari / get_price_statistics)总是注册；
    仅当同时传入 query_parser 与 recommendation_service 时，才注册把整条固定流程
    包起来的高层工具 recommend_deals。
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
    return registry
