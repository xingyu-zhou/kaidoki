"""
查询解析器关键词清洗单测(纯单测,不调 LLM)。

回归 bug:解析器把整句片段(如 "を1万円以内で探して、コスパのいいもの")混进 keywords，
导致 Mercari 搜不到东西、recommend_deals / search 返回 0 条。
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kaidoki.application.services.query_parser_service import (  # noqa: E402
    QueryParserService,
)


def _svc():
    # _clean_keywords 是纯方法，不依赖 config / llm_service
    return QueryParserService(config=None, llm_service=None)


def test_clean_keywords_drops_sentence_fragment():
    kws = ["AirPods", "Pro", "を1万円以内で探して、コスパのいいもの"]
    assert _svc()._clean_keywords(kws) == ["AirPods", "Pro"]


def test_clean_keywords_drops_price_condition():
    assert _svc()._clean_keywords(["iPhone", "10万円以下"]) == ["iPhone"]


def test_clean_keywords_keeps_clean_product_terms():
    kws = ["Nintendo", "Switch", "有機EL"]
    assert _svc()._clean_keywords(kws) == ["Nintendo", "Switch", "有機EL"]


def test_clean_keywords_ignores_non_strings_and_empty():
    assert _svc()._clean_keywords([None, "", "   ", "iPhone", 123]) == ["iPhone"]
