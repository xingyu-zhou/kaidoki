"""
输出格式化单测:验证 --output-format 只产出所选的一种格式。

回归此前的 bug:LLM 提示词里列了全部四种格式,导致一次性输出全部格式。
纯单测,不联网、不调用真实 LLM(detailed_report 用 llm=None 走确定性回退)。
"""

import json
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kaidoki.application.services.output_formatter_service import (  # noqa: E402
    OutputFormatterService,
)
from kaidoki.application.services.recommendation_service import (  # noqa: E402
    RecommendationResult,
)
from kaidoki.domain.entities.product import ProductEntity  # noqa: E402
from kaidoki.domain.entities.query import QueryEntity  # noqa: E402


def _result():
    products = [
        ProductEntity(id="m1", title="AirPods Pro 第2世代", price=18000,
                      condition="目立った傷や汚れなし", url="https://jp.mercari.com/item/m1"),
        ProductEntity(id="m2", title="AirPods 4", price=9800,
                      condition="新品・未使用", url="https://jp.mercari.com/item/m2"),
    ]
    return RecommendationResult(
        recommendations=products, strategy_used="balanced",
        processing_time=0.1, total_analyzed=2, reasoning="按性价比排序",
    )


def _query():
    return QueryEntity(original_query="AirPods Pro 2万円以下", keywords=["airpods", "pro"])


def _fmt():
    # llm_service=None → detailed_report 走确定性回退,其它格式本就不用 LLM
    return OutputFormatterService(config=None, llm_service=None)


@pytest.mark.asyncio
async def test_markdown_table_only():
    out = await _fmt().format(_result(), _query(), "markdown_table", "zh")
    assert out.format_type == "markdown_table"
    assert "| 排名 |" in out.content and "|------" in out.content
    # 不应混入其它格式的特征
    assert "```json" not in out.content
    assert not out.content.lstrip().startswith("[")


@pytest.mark.asyncio
async def test_simple_list_only():
    out = await _fmt().format(_result(), _query(), "simple_list", "zh")
    assert out.content.splitlines()[0].startswith("1. ")
    assert "|" not in out.content  # 不是表格


@pytest.mark.asyncio
async def test_json_export_is_valid_json():
    out = await _fmt().format(_result(), _query(), "json_export", "zh")
    parsed = json.loads(out.content)  # 必须是合法 JSON
    assert len(parsed) == 2
    assert parsed[0]["rank"] == 1
    assert parsed[0]["url"] == "https://jp.mercari.com/item/m1"
    assert "|" not in out.content  # 不含表格


@pytest.mark.asyncio
async def test_detailed_report_fallback_without_llm():
    out = await _fmt().format(_result(), _query(), "detailed_report", "zh")
    assert out.format_type == "detailed_report"
    assert "推荐报告" in out.content
    assert "按性价比排序" in out.content  # 用上了 reasoning


@pytest.mark.asyncio
async def test_unknown_format_falls_back_to_markdown():
    out = await _fmt().format(_result(), _query(), "no_such_format", "zh")
    assert out.format_type == "markdown_table"


@pytest.mark.asyncio
async def test_empty_products_message():
    empty = RecommendationResult(recommendations=[], strategy_used="balanced",
                                 processing_time=0.0, total_analyzed=0)
    out = await _fmt().format(empty, _query(), "markdown_table", "zh")
    assert "没有找到" in out.content
