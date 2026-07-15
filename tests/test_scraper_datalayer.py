"""
数据层(Playwright 爬虫)纯单元测试。

覆盖不依赖浏览器 / 网络的纯函数逻辑：
  - ProductDataConverter.convert_api_response：entities:search JSON → ProductEntity
  - SearchParameterProcessor：查询参数处理 + v2 请求体构建(数字守卫)
  - PlaywrightMercariScraper 的纯解析辅助：_build_search_url(数字守卫)、
    _parse_price_text、_dom_item_to_entity、_enrich_from_api

绝不做 live 抓取、绝不启动浏览器、绝不发真实 API 请求。
"""

import sys
import types
from pathlib import Path

import pytest

# 该包未以 editable 方式安装，测试时把 src 加入 import 路径
SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kaidoki.infrastructure.scraping.scraper_service import (  # noqa: E402
    ProductDataConverter,
    SearchParameterProcessor,
    PlaywrightMercariScraper,
)
from kaidoki.domain.entities.product import ProductEntity  # noqa: E402
from kaidoki.domain.entities.query import QueryEntity  # noqa: E402


# --------------------------------------------------------------------------- #
# 内联 sample：真实 entities:search 响应的精简结构(2 个 item)
# --------------------------------------------------------------------------- #
def _sample_api_response():
    return {
        "meta": {"nextPageToken": "v1:1", "previousPageToken": "", "numFound": "15000"},
        "items": [
            {
                "id": "m11111111111",
                "sellerId": "843862035",
                "status": "ITEM_STATUS_ON_SALE",
                "name": "Apple AirPods4 ANC搭載モデル",
                "price": "14999",  # API 返回字符串价格
                "thumbnails": [
                    "https://static.mercdn.net/thumb/item/webp/m11111111111_1.jpg"
                ],
                "itemType": "ITEM_TYPE_MERCARI",
                "itemConditionId": "3",
                "itemBrand": {"id": "420", "name": "Apple", "subName": "アップル"},
                "categoryId": "1660",
            },
            {
                "id": "m22222222222",
                "sellerId": "555",
                "status": "ITEM_STATUS_SOLD_OUT",  # 已售出
                "name": "AirPods Pro 第2世代",
                "price": 8000,  # int 价格
                "thumbnails": ["https://static.mercdn.net/thumb/item/webp/m22222222222_1.jpg"],
                "itemConditionId": "1",
                "itemBrand": {"name": "Apple"},
            },
        ],
    }


# --------------------------------------------------------------------------- #
# ProductDataConverter
# --------------------------------------------------------------------------- #
class TestProductDataConverter:
    def test_convert_basic_fields(self):
        products = ProductDataConverter.convert_api_response(_sample_api_response())
        assert len(products) == 2
        assert all(isinstance(p, ProductEntity) for p in products)

        p0 = products[0]
        assert p0.id == "m11111111111"
        assert p0.title == "Apple AirPods4 ANC搭載モデル"
        assert p0.price == 14999  # 字符串 "14999" → int
        assert p0.condition == "目立った傷や汚れなし"  # itemConditionId "3"
        assert p0.url == "https://jp.mercari.com/item/m11111111111"
        assert p0.image_urls == [
            "https://static.mercdn.net/thumb/item/webp/m11111111111_1.jpg"
        ]
        assert p0.brand == "Apple"  # itemBrand.name
        assert p0.seller_id == "843862035"  # sellerId
        assert p0.sold is False  # ITEM_STATUS_ON_SALE

    def test_convert_condition_price_and_sold(self):
        products = ProductDataConverter.convert_api_response(_sample_api_response())
        p1 = products[1]
        assert p1.price == 8000  # int 价格保持
        assert p1.condition == "新品・未使用"  # itemConditionId "1"
        assert p1.sold is True  # ITEM_STATUS_SOLD_OUT
        assert p1.brand == "Apple"
        assert p1.url == "https://jp.mercari.com/item/m22222222222"

    def test_empty_items_returns_empty_list(self):
        assert ProductDataConverter.convert_api_response({"items": []}) == []

    def test_missing_items_key_does_not_crash(self):
        # 没有 items 键(如异常响应) → 返回空列表，不抛异常
        assert ProductDataConverter.convert_api_response({"meta": {}}) == []
        assert ProductDataConverter.convert_api_response({}) == []

    def test_item_without_id_is_skipped(self):
        data = {"items": [{"name": "无 id 商品", "price": "100"}]}
        assert ProductDataConverter.convert_api_response(data) == []

    def test_item_with_missing_fields_uses_safe_defaults(self):
        data = {"items": [{"id": "m33333333333", "name": "极简商品"}]}
        products = ProductDataConverter.convert_api_response(data)
        assert len(products) == 1
        p = products[0]
        assert p.id == "m33333333333"
        assert p.title == "极简商品"
        assert p.price == 0  # 缺 price → 0
        assert p.condition == "不明"  # 缺 itemConditionId → 不明
        assert p.image_urls == []  # 缺 thumbnails → 空
        assert p.sold is False


# --------------------------------------------------------------------------- #
# SearchParameterProcessor
# --------------------------------------------------------------------------- #
class TestSearchParameterProcessor:
    def _query(self):
        return QueryEntity(
            original_query="airpods pro 新品 1000〜5000円",
            keywords=["airpods", "pro"],
            price_min=1000,
            price_max=5000,
            condition="新品・未使用",
            category="アクセサリー",  # 日文分类名(非数字)——守卫场景
        )

    def test_process_query_parameters(self):
        proc = SearchParameterProcessor()
        filters = proc.process_query_parameters(self._query())
        assert filters["keyword"] == "airpods pro"
        assert filters["price_min"] == "1000"
        assert filters["price_max"] == "5000"
        assert filters["status"] == "1"  # 新品・未使用 → "1"
        # category 原样透传(是分类名字符串，非数字 ID)
        assert filters["category_id"] == "アクセサリー"

    def test_build_body_ignores_non_numeric_category(self):
        proc = SearchParameterProcessor()
        filters = proc.process_query_parameters(self._query())
        body = proc.build_v2_request_body(filters, paging={})
        sc = body["searchCondition"]
        # 非数字分类名被 parse_numeric_array 正确忽略
        assert sc["categoryId"] == []
        # 价格正确进 body
        assert sc["priceMin"] == 1000
        assert sc["priceMax"] == 5000
        # 状态进 body
        assert sc["status"] == ["1"]
        assert body["pageSize"] == 120

    def test_build_body_keeps_numeric_category(self):
        proc = SearchParameterProcessor()
        body = proc.build_v2_request_body({"category_id": "1660"}, paging={})
        assert body["searchCondition"]["categoryId"] == [1660]

    def test_parse_numeric_array(self):
        assert SearchParameterProcessor.parse_numeric_array("1,2,3") == [1, 2, 3]
        assert SearchParameterProcessor.parse_numeric_array("アクセサリー") == []
        assert SearchParameterProcessor.parse_numeric_array(None) == []


# --------------------------------------------------------------------------- #
# PlaywrightMercariScraper —— 纯解析 / URL 构建(不启动浏览器)
# --------------------------------------------------------------------------- #
def _scraper():
    # __init__ 只读取属性、不触网、不启动浏览器；用空 config 即可
    return PlaywrightMercariScraper(types.SimpleNamespace())


class TestBuildSearchUrlGuard:
    def test_keyword_and_price_included(self):
        q = QueryEntity(
            original_query="airpods",
            keywords=["airpods"],
            price_min=1000,
            price_max=5000,
            category="アクセサリー",  # 日文名 → 应被守卫忽略
        )
        url = _scraper()._build_search_url(q)
        assert url.startswith("https://jp.mercari.com/search?")
        assert "keyword=airpods" in url
        assert "price_min=1000" in url
        assert "price_max=5000" in url
        # 非数字分类名不进 URL
        assert "category_id" not in url

    def test_numeric_category_and_condition_included(self):
        q = QueryEntity(
            original_query="x",
            keywords=["x"],
            category="1660",  # 纯数字分类 ID
            condition="新品・未使用",  # → item_condition_id=1
        )
        url = _scraper()._build_search_url(q)
        assert "category_id=1660" in url
        assert "item_condition_id=1" in url

    def test_keyword_falls_back_to_original_query(self):
        q = QueryEntity(original_query="fallback kw", keywords=[])
        url = _scraper()._build_search_url(q)
        # keywords 为空时退化用 original_query(空格被 urlencode)
        assert "fallback" in url


class TestPureParsers:
    def test_parse_price_text(self):
        s = PlaywrightMercariScraper
        assert s._parse_price_text("¥14,999") == 14999
        assert s._parse_price_text("1,200円") == 1200
        assert s._parse_price_text(500) == 500
        assert s._parse_price_text(None) is None
        assert s._parse_price_text("") is None
        assert s._parse_price_text("送料込み") is None

    def test_dom_item_to_entity_full(self):
        it = {
            "id": "m44444444444",
            "title": "テスト商品",
            "price": "¥1,200",
            "url": "https://jp.mercari.com/item/m44444444444",
            "thumb": "https://img.example/x.jpg",
        }
        pe = _scraper()._dom_item_to_entity(it)
        assert pe is not None
        assert pe.id == "m44444444444"
        assert pe.title == "テスト商品"
        assert pe.price == 1200
        assert pe.url == "https://jp.mercari.com/item/m44444444444"
        assert pe.image_urls == ["https://img.example/x.jpg"]

    def test_dom_item_to_entity_url_fallback(self):
        it = {"id": "m55555555555", "title": "no url", "price": None, "thumb": None}
        pe = _scraper()._dom_item_to_entity(it)
        assert pe is not None
        assert pe.url == "https://jp.mercari.com/item/m55555555555"
        assert pe.price is None
        assert pe.image_urls == []

    def test_dom_item_missing_id_or_title_returns_none(self):
        s = _scraper()
        assert s._dom_item_to_entity({"id": None, "title": "x"}) is None
        assert s._dom_item_to_entity({"id": "m6", "title": None}) is None

    def test_enrich_from_api_fills_missing_fields(self):
        dom = ProductEntity(id="m7", title="t", price=1200)  # condition/brand/seller 缺失
        api = ProductEntity(
            id="m7",
            title="t",
            price=999,
            condition="新品・未使用",
            brand="Apple",
            seller_id="9",
            category="イヤホン",
            sold=True,
        )
        PlaywrightMercariScraper._enrich_from_api(dom, api)
        assert dom.condition == "新品・未使用"
        assert dom.brand == "Apple"
        assert dom.seller_id == "9"
        assert dom.category == "イヤホン"
        assert dom.sold is True
        # DOM 已有的 price 不被 API 覆盖
        assert dom.price == 1200

    def test_enrich_from_api_none_is_noop(self):
        dom = ProductEntity(id="m8", title="t", price=100)
        PlaywrightMercariScraper._enrich_from_api(dom, None)  # 不崩
        assert dom.price == 100
