"""
推荐服务 LLM 重排 / JSON 解析单元测试。

覆盖四类 LLM 返回内容：带 ```json 围栏、纯 JSON、前后带散文、垃圾内容，
并验证重排顺序、reasoning 填充与 fallback 行为。

全部使用 fake llm_service，绝不做网络抓取或真实 OpenAI 调用。
"""

import sys
from pathlib import Path

import pytest

# 该包未以 editable 方式安装，测试时把 src 加入 import 路径
SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mercari_agent.application.services.recommendation_service import (  # noqa: E402
    RecommendationService,
    RecommendationResult,
)
from mercari_agent.domain.entities.product import ProductEntity  # noqa: E402
from mercari_agent.domain.entities.query import QueryEntity, QueryIntent  # noqa: E402


# --------------------------------------------------------------------------- #
# Fake LLM service（不联网、不调用真实 OpenAI）
# --------------------------------------------------------------------------- #
class _FakeLLMResponse:
    """模拟 LLMResponse，仅需要 .content 字段。"""

    def __init__(self, content):
        self.content = content


class _FakeLLMService:
    """返回预设 content 的假 LLM 服务，并记录调用参数供断言。"""

    def __init__(self, content):
        self._content = content
        self.calls = []

    async def generate_response(self, prompt, response_format=None, **kwargs):
        self.calls.append(
            {"prompt": prompt, "response_format": response_format, **kwargs}
        )
        return _FakeLLMResponse(self._content)


def _make_products():
    return [
        ProductEntity(
            id="0", title="iPhone 15 Pro Max 1TB", price=150000,
            condition="新品", seller_name="seller_a",
        ),
        ProductEntity(
            id="1", title="iPhone 14 128GB", price=90000,
            condition="中古", seller_name="seller_b",
        ),
        ProductEntity(
            id="2", title="Galaxy S23", price=80000,
            condition="中古", seller_name="seller_c",
        ),
    ]


def _make_query(keywords=("iPhone",), price_min=None, price_max=None):
    return QueryEntity(
        original_query="iPhone",
        intent=QueryIntent.SEARCH,
        keywords=list(keywords),
        price_min=price_min,
        price_max=price_max,
    )


@pytest.fixture
def products():
    return _make_products()


@pytest.fixture
def query():
    return _make_query()


# --------------------------------------------------------------------------- #
# _extract_json 单元测试
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "content, expected",
    [
        # 1. 带 ```json 围栏
        (
            '```json\n{"recommended_indices": [2, 0, 1], "reasoning": "r"}\n```',
            {"recommended_indices": [2, 0, 1], "reasoning": "r"},
        ),
        # 无语言标记的围栏
        (
            '```\n{"recommended_indices": [0]}\n```',
            {"recommended_indices": [0]},
        ),
        # 2. 纯 JSON
        (
            '{"recommended_indices": [0, 1]}',
            {"recommended_indices": [0, 1]},
        ),
        # 3. 前后带散文
        (
            '好的，这是结果：\n{"recommended_indices": [1]}\n希望有帮助',
            {"recommended_indices": [1]},
        ),
    ],
)
def test_extract_json_success(content, expected):
    svc = RecommendationService(config=None)
    assert svc._extract_json(content) == expected


@pytest.mark.parametrize(
    "content",
    [
        "",
        None,
        "完全不是 JSON 的垃圾内容",
        "```json\nnot valid json at all\n```",
        '["a", "list", "not", "dict"]',  # 合法 JSON 但不是对象
    ],
)
def test_extract_json_failure(content):
    svc = RecommendationService(config=None)
    assert svc._extract_json(content) is None


# --------------------------------------------------------------------------- #
# recommend 端到端（fake LLM）测试
# --------------------------------------------------------------------------- #
async def test_recommend_fenced_json_reorders(products, query):
    """情况 1：带围栏 JSON → 正确解析并按 recommended_indices 顺序重排。"""
    fake = _FakeLLMService(
        '```json\n'
        '{"recommended_indices": [2, 0, 1], "reasoning": "按相关性排序", '
        '"strategy_applied": "balanced"}\n'
        '```'
    )
    svc = RecommendationService(config=None, llm_service=fake)

    result = await svc.recommend(products, query, limit=3, strategy="balanced")

    assert isinstance(result, RecommendationResult)
    assert [p.id for p in result.recommendations] == ["2", "0", "1"]
    assert result.reasoning == "按相关性排序"
    assert result.strategy_used == "balanced"
    assert result.total_analyzed == 3
    # 必须启用结构化 JSON 输出
    assert fake.calls, "LLM 服务应被调用"
    assert fake.calls[0]["response_format"] == "json"


async def test_recommend_plain_json(products, query):
    """情况 2：纯 JSON → 正确解析并重排。"""
    fake = _FakeLLMService('{"recommended_indices": [1, 0], "reasoning": "ok"}')
    svc = RecommendationService(config=None, llm_service=fake)

    result = await svc.recommend(products, query, limit=3)

    assert [p.id for p in result.recommendations[:2]] == ["1", "0"]
    assert result.reasoning == "ok"


async def test_recommend_prose_wrapped_json(products, query):
    """情况 3：前后带散文的 JSON → 仍能抓出对象并重排。"""
    fake = _FakeLLMService(
        "好的，这是我的推荐：\n"
        '{"recommended_indices": [2], "reasoning": "只推荐一个"}\n'
        "希望对你有帮助！"
    )
    svc = RecommendationService(config=None, llm_service=fake)

    result = await svc.recommend(products, query, limit=3)

    # index 2 排最前，其余商品补齐
    assert result.recommendations[0].id == "2"
    assert result.reasoning == "只推荐一个"
    assert len(result.recommendations) == 3


async def test_recommend_garbage_falls_back(products, query):
    """情况 4：垃圾内容 → 走 fallback，不崩溃，且关键词匹配优先。"""
    fake = _FakeLLMService("这不是 JSON，只是一段废话")
    svc = RecommendationService(config=None, llm_service=fake)

    result = await svc.recommend(products, query, limit=3)

    assert len(result.recommendations) > 0
    assert result.reasoning is None  # fallback 不产生 reasoning
    # iPhone 关键词命中的商品（id 0/1）应排在未命中的 Galaxy（id 2）之前
    ids = [p.id for p in result.recommendations]
    assert ids.index("0") < ids.index("2")
    assert ids.index("1") < ids.index("2")


async def test_recommend_no_llm_uses_fallback(products, query):
    """无 llm_service → 直接使用 fallback，命中关键词优先。"""
    svc = RecommendationService(config=None, llm_service=None)

    result = await svc.recommend(products, query, limit=3)

    ids = [p.id for p in result.recommendations]
    # 未命中的 Galaxy(id 2) 应排在最后
    assert ids[-1] == "2"
    assert result.reasoning is None


async def test_fallback_ignores_invalid_indices(products, query):
    """LLM 返回越界/非法索引时应被忽略，不抛异常。"""
    fake = _FakeLLMService(
        '{"recommended_indices": [99, -1, "x", 1], "reasoning": "含脏数据"}'
    )
    svc = RecommendationService(config=None, llm_service=fake)

    result = await svc.recommend(products, query, limit=3)

    # 仅合法索引 1 被采纳并排在最前，其余补齐
    assert result.recommendations[0].id == "1"
    assert len(result.recommendations) == 3
    assert result.reasoning == "含脏数据"
