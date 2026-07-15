"""
recommend_deals 流程工具单测:把固定流程(解析→抓取→重排)包成一个工具。

纯单测,用 fake query_parser / scraper / recommendation_service,零网络、零真实 LLM、零浏览器。
"""

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mercari_agent.tools.mercari_tools import (  # noqa: E402
    RecommendMercariTool,
    build_mercari_tool_registry,
)
from mercari_agent.application.services.recommendation_service import (  # noqa: E402
    RecommendationResult,
)
from mercari_agent.domain.entities.product import ProductEntity  # noqa: E402
from mercari_agent.domain.entities.query import QueryEntity  # noqa: E402


# --------------------------------------------------------------------------- #
# 替身(不触网/不调 LLM/不开浏览器)
# --------------------------------------------------------------------------- #
class _FakeParseResult:
    def __init__(self, query):
        self.query = query
        self.confidence = 0.9


class _FakeQueryParser:
    def __init__(self, query_entity):
        self._q = query_entity
        self.calls = []

    async def parse(self, query):
        self.calls.append(query)
        return _FakeParseResult(self._q)


class _FakeScraping:
    def __init__(self, products):
        self.products = products
        self.total_found = len(products)
        self.pages_scraped = 1
        self.processing_time = 0.0
        self.strategy_used = None
        self.metadata = {}


class _FakeScraper:
    def __init__(self, products):
        self._products = products
        self.calls = []

    async def scrape(self, query, max_products=10):
        self.calls.append((query, max_products))
        return _FakeScraping(self._products)


class _FakeRecommendation:
    def __init__(self):
        self.calls = []

    async def recommend(self, products, query, limit, strategy):
        self.calls.append((len(products), limit, strategy))
        return RecommendationResult(
            recommendations=list(products)[:limit],
            strategy_used=strategy,
            processing_time=0.0,
            total_analyzed=len(products),
            reasoning="按性价比排序",
        )


def _products(n=4):
    return [
        ProductEntity(id=f"m{i}", title=f"AirPods {i}", price=1000 * i,
                      condition="新品・未使用", url=f"https://jp.mercari.com/item/m{i}")
        for i in range(1, n + 1)
    ]


# --------------------------------------------------------------------------- #
# recommend_deals 工具
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_recommend_deals_runs_full_pipeline():
    q = QueryEntity(original_query="AirPods Pro 5000円以下", keywords=["AirPods", "Pro"], price_max=5000)
    parser, scraper, rec = _FakeQueryParser(q), _FakeScraper(_products()), _FakeRecommendation()
    tool = RecommendMercariTool(scraper, parser, rec)

    result = await tool.call(query="AirPods Pro 5000円以下", strategy="price_oriented", max_results=3)

    assert result.is_success()
    data = result.data
    assert data["strategy"] == "price_oriented"
    assert data["count"] == 3
    assert data["reasoning"] == "按性价比排序"
    assert data["understood"]["price_max"] == 5000
    assert data["understood"]["keywords"] == ["AirPods", "Pro"]
    assert len(data["products"]) == 3
    assert data["products"][0]["url"].startswith("https://jp.mercari.com/item/")

    # 流程确实被逐段走通:parse → scrape(max_results*2) → recommend(strategy 透传)
    assert parser.calls == ["AirPods Pro 5000円以下"]
    assert scraper.calls[0][1] == 6  # max_results * 2
    assert rec.calls[0][2] == "price_oriented"


@pytest.mark.asyncio
async def test_recommend_deals_empty_result():
    tool = RecommendMercariTool(
        _FakeScraper([]),
        _FakeQueryParser(QueryEntity(original_query="不存在的商品")),
        _FakeRecommendation(),
    )
    result = await tool.call(query="不存在的商品")
    assert result.is_success()
    assert result.data["count"] == 0


@pytest.mark.asyncio
async def test_recommend_deals_absorbs_extra_args():
    # 模型给多余参数不应使整次调用失败
    q = QueryEntity(original_query="x", keywords=["x"])
    tool = RecommendMercariTool(_FakeScraper(_products(2)), _FakeQueryParser(q), _FakeRecommendation())
    result = await tool.call(query="x", bogus_param="ignored", limit=99)
    assert result.is_success()


# --------------------------------------------------------------------------- #
# 注册逻辑:仅在提供 LLM 服务时才注册高层工具
# --------------------------------------------------------------------------- #
def test_registry_low_level_only_without_services():
    reg = build_mercari_tool_registry(_FakeScraper([]))
    assert set(reg.list_tools()) == {"search_mercari", "get_price_statistics"}


def test_registry_adds_pipeline_tool_with_services():
    reg = build_mercari_tool_registry(
        _FakeScraper([]),
        _FakeQueryParser(QueryEntity(original_query="x")),
        _FakeRecommendation(),
    )
    tools = set(reg.list_tools())
    assert tools == {"search_mercari", "get_price_statistics", "recommend_deals"}
