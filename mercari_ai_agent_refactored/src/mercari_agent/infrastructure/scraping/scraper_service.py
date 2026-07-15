"""
爬虫服务模块 - Playwright 无头浏览器版

Mercari (jp.mercari.com) 是 Next.js SPA，服务端返回的原始 HTML 里没有商品，
商品由页面 JS 渲染进 DOM。因此裸抓 HTML 永远拿不到数据（这才是旧代码"0 商品"
的真正原因，不是被反爬封）。本模块用无头 Chromium 真实渲染页面：

- 首屏：等待商品卡片 `li[data-testid="item-cell"]` 渲染后，直接抽 DOM（约 120 条）。
- 翻页：复用页面自己发出的 `POST api.mercari.jp/v2/entities:search` 请求里的
  dpop 头 + POST body，在浏览器上下文里用 fetch 带递增 pageToken 拉后续页，
  这样无需自己实现 DPoP 签名。返回的 JSON 直接喂给 ProductDataConverter。

合规克制（个人自用）：每次 scrape 一个浏览器会话、翻页间加延时、总页数有上限、
正常日本 Chrome UA / locale ja-JP / timezone Asia/Tokyo，绝不压测。

Author: Mercari AI Agent Team (Playwright rewrite)
"""

import asyncio
import json
import logging
import random
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from playwright.async_api import async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeout

from ...shared.utils.logger_utils import get_logger

logger = get_logger(__name__)
logger.setLevel(logging.INFO)

from ...domain.entities.product import ProductEntity
from ...domain.entities.query import QueryEntity
from ...shared.exceptions.service_exceptions import BaseServiceException
from ...shared.config.app_config import AppConfig

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
DEFAULT_PAGE_SIZE = 120
INDEX_ROUTING_UNSPECIFIED = "INDEX_ROUTING_UNSPECIFIED"
SERVICE_FROM = "web"
SORT_DEFAULT = "default"
SORT_SCORE = "score"
ORDER_ASC = "asc"
ORDER_DESC = "desc"

SEARCH_PAGE_URL = "https://jp.mercari.com/search"
SEARCH_API_PATH = "api.mercari.jp/v2/entities:search"
ITEM_CELL_SELECTOR = 'li[data-testid="item-cell"]'

# 真实日本 Chrome UA
DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/149.0.0.0 Safari/537.36"
)

# 首屏 DOM 抽取（选择器均经 spike 实测：item-cell / thumbnail-link /
# thumbnail-item-name / .merPrice 都是稳定的 data-testid 或语义类）
_EXTRACT_JS = r"""
() => {
  const cells = Array.from(document.querySelectorAll('li[data-testid="item-cell"]'));
  return cells.map(cell => {
    const a = cell.querySelector('a[href^="/item/"]') || cell.querySelector('a');
    const href = a ? a.getAttribute('href') : null;
    const idm = href ? (href.match(/\/item\/(m\d+)/) || [])[1] : null;

    let thumb = null, title = null;
    const img = cell.querySelector('img');
    if (img) { thumb = img.getAttribute('src'); title = img.getAttribute('alt'); }
    const nameEl = cell.querySelector('[data-testid="thumbnail-item-name"]');
    if (nameEl && nameEl.textContent) title = nameEl.textContent.trim();

    let price = null;
    const priceEl = cell.querySelector('.merPrice');
    if (priceEl && priceEl.textContent) price = priceEl.textContent.trim();
    if (!price) {
      const m = (cell.textContent || '').match(/[\d,]{3,}/);
      if (m) price = m[0];
    }
    return {
      id: idm,
      title: title ? title.trim() : null,
      price: price,
      url: href ? ('https://jp.mercari.com' + href) : null,
      thumb: thumb,
    };
  });
}
"""

# 在页面上下文里复用浏览器 dpop + cookies 调 entities:search 拉下一页
_REPLAY_JS = r"""
async (args) => {
  try {
    const r = await fetch(args.url, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'dpop': args.dpop,
        'x-platform': 'web',
      },
      body: JSON.stringify(args.body),
      credentials: 'include',
    });
    let data = null;
    try { data = await r.json(); } catch (e) {}
    return { status: r.status, data: data };
  } catch (e) {
    return { status: -1, error: String(e) };
  }
}
"""


# ---------------------------------------------------------------------------
# 保留复用：搜索参数处理器
# ---------------------------------------------------------------------------
class SearchParameterProcessor:
    """统一的搜索参数处理器（复用）"""

    @staticmethod
    def parse_numeric_array(value: Optional[str]) -> List[int]:
        if not value:
            return []
        return [int(x) for x in str(value).split(",") if str(x).strip().isdigit()]

    @staticmethod
    def map_sort_option(value: str) -> str:
        return {
            "created_time": "SORT_CREATED_TIME",
            "num_likes": "SORT_NUM_LIKES",
            "score": "SORT_SCORE",
            "price": "SORT_PRICE",
        }.get(value, "SORT_DEFAULT")

    @staticmethod
    def map_status_option(value: str) -> List[str]:
        return [value] if value else []

    @staticmethod
    def map_shipping_method(value: Optional[str]) -> List[str]:
        mapping = {
            "anonymous": "SHIPPING_METHOD_ANONYMOUS",
            "japan_post": "SHIPPING_METHOD_JAPAN_POST",
            "no_option": "SHIPPING_METHOD_NO_OPTION",
        }
        methods = []
        if value:
            for v in value.split(","):
                m = mapping.get(v.strip())
                if m:
                    methods.append(m)
        return methods

    def process_query_parameters(self, query: QueryEntity) -> Dict[str, Any]:
        """处理查询参数，统一参数验证逻辑"""
        filters: Dict[str, Any] = {}

        if getattr(query, "keywords", None):
            if isinstance(query.keywords, list):
                filters["keyword"] = " ".join(str(k) for k in query.keywords if k)
            else:
                filters["keyword"] = str(query.keywords)

        if getattr(query, "price_min", None):
            filters["price_min"] = str(int(query.price_min))
        if getattr(query, "price_max", None):
            filters["price_max"] = str(int(query.price_max))

        if getattr(query, "condition", None):
            condition_mapping = {
                "新品・未使用": "1",
                "未使用に近い": "2",
                "目立った傷や汚れなし": "3",
                "やや傷や汚れあり": "4",
                "傷や汚れあり": "5",
                "全体的に状態が悪い": "6",
            }
            if query.condition in condition_mapping:
                filters["status"] = condition_mapping[query.condition]

        if getattr(query, "category", None):
            filters["category_id"] = query.category

        return filters

    def build_v2_request_body(self, filters: Dict[str, Any], paging: Dict[str, Any]) -> Dict[str, Any]:
        """构建 v2 API 请求体（保留，供需要时手工构造 body 使用）"""
        search_condition = {
            "keyword": filters.get("keyword", ""),
            "excludeKeyword": filters.get("exclude_keyword", ""),
            "sort": self.map_sort_option(filters.get("sort", SORT_DEFAULT)),
            "order": ORDER_ASC if filters.get("order") == ORDER_ASC else ORDER_DESC,
            "status": self.map_status_option(filters.get("status", "")),
            "sizeId": filters.get("size_id", "").split(",") if filters.get("size_id") else [],
            "categoryId": self.parse_numeric_array(filters.get("category_id")),
            "brandId": self.parse_numeric_array(filters.get("brand_id")),
            "sellerId": filters.get("seller_id", "").split(",") if filters.get("seller_id") else [],
            "priceMin": int(filters.get("price_min", 0)) or 0,
            "priceMax": int(filters.get("price_max", 0)) or 0,
            "shippingPayerId": self.parse_numeric_array(filters.get("shipping_payer_id")),
            "shippingFromArea": self.parse_numeric_array(filters.get("shipping_from_area")),
            "shippingMethod": self.map_shipping_method(filters.get("shipping_method", "")),
            "colorId": self.parse_numeric_array(filters.get("color_id")),
            "hasCoupon": bool(filters.get("has_coupon", False)),
            "attributes": [],
            "itemTypes": [],
            "skuIds": filters.get("sku_ids", "").split(",") if filters.get("sku_ids") else [],
        }
        if search_condition.get("sort") == "SORT_DEFAULT":
            search_condition["sort"] = "SORT_SCORE"

        payload = {
            "userId": paging.get("userId", ""),
            "pageSize": paging.get("pageSize", DEFAULT_PAGE_SIZE),
            "pageToken": paging.get("pageToken", ""),
            "searchSessionId": paging.get("searchSessionId", str(uuid.uuid4())),
            "source": paging.get("source", ""),
            "indexRouting": INDEX_ROUTING_UNSPECIFIED,
            "searchCondition": search_condition,
            "serviceFrom": SERVICE_FROM,
            "withItemBrand": True,
            "withItemPromotions": True,
            "withItemSizes": True,
            "withShopname": paging.get("withShopname", False),
            "useDynamicAttribute": paging.get("useDynamicAttribute", True),
            "withSuggestedItems": True,
            "withOfferPricePromotion": True,
            "withProductSuggest": True,
            "withProductArticles": True,
            "withSearchConditionId": False,
            "withAuction": paging.get("withAuction", False),
            "laplaceDeviceUuid": str(uuid.uuid4()),
        }
        return {k: v for k, v in payload.items() if v is not None}


# ---------------------------------------------------------------------------
# 保留复用：API 响应 → ProductEntity 转换器
# ---------------------------------------------------------------------------
class ProductDataConverter:
    """entities:search API 响应转换器（复用；翻页拿到的 JSON 直接喂这里）"""

    # itemConditionId → 可读状态
    _CONDITION_MAP = {
        "1": "新品・未使用",
        "2": "未使用に近い",
        "3": "目立った傷や汚れなし",
        "4": "やや傷や汚れあり",
        "5": "傷や汚れあり",
        "6": "全体的に状態が悪い",
    }
    _SOLD_STATUSES = {"ITEM_STATUS_SOLD_OUT", "ITEM_STATUS_TRADING", "sold", "sold_out"}

    @staticmethod
    def convert_api_response(api_data: Dict) -> List[ProductEntity]:
        products: List[ProductEntity] = []
        for item_data in ProductDataConverter._extract_items_from_response(api_data):
            try:
                product = ProductDataConverter._convert_single_item(item_data)
                if product:
                    products.append(product)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"转换单个商品失败: {e}")
                continue
        return products

    @staticmethod
    def _extract_items_from_response(api_data: Dict) -> List[Dict]:
        possible_paths = [
            ["items"],
            ["data", "items"],
            ["results", "items"],
            ["entities"],
            ["data", "entities"],
        ]
        for path in possible_paths:
            current = api_data
            try:
                for key in path:
                    current = current[key]
                if isinstance(current, list):
                    return current
            except (KeyError, TypeError):
                continue
        return []

    @staticmethod
    def _convert_single_item(item_data: Dict) -> Optional[ProductEntity]:
        product_id = item_data.get("id") or item_data.get("item_id")
        if not product_id:
            return None

        # 价格：API 为字符串如 "14999"
        price = item_data.get("price", 0)
        if isinstance(price, str):
            digits = re.sub(r"[^\d]", "", price)
            price = int(digits) if digits else 0
        elif not isinstance(price, int):
            price = 0

        # 商品状态：优先 itemConditionId
        cond_key = str(item_data.get("itemConditionId") or item_data.get("condition") or "")
        condition = ProductDataConverter._CONDITION_MAP.get(cond_key, "不明")

        # 图片
        images: List[str] = []
        if isinstance(item_data.get("thumbnails"), list):
            images = item_data["thumbnails"]
        elif item_data.get("thumbnail"):
            images = [item_data["thumbnail"]]
        elif item_data.get("image_url"):
            images = [item_data["image_url"]]

        status = str(item_data.get("status", ""))

        return ProductEntity(
            id=str(product_id),
            title=item_data.get("name") or item_data.get("title") or "",
            price=price,
            url=f"https://jp.mercari.com/item/{product_id}",
            description=item_data.get("description", ""),
            condition=condition,
            category=ProductDataConverter._extract_category(item_data),
            brand=ProductDataConverter._extract_brand(item_data),
            seller_name=ProductDataConverter._extract_seller_name(item_data),
            seller_id=str(item_data.get("sellerId") or item_data.get("seller_id") or "") or None,
            seller_rating=ProductDataConverter._extract_seller_rating(item_data),
            image_urls=images,
            view_count=item_data.get("num_likes", 0),
            like_count=item_data.get("num_comments", 0),
            shipping_fee=item_data.get("shipping_fee"),
            listed_at=datetime.now(),
            updated_at=datetime.now(),
            sold=status in ProductDataConverter._SOLD_STATUSES,
        )

    @staticmethod
    def _extract_category(item_data: Dict) -> str:
        category = item_data.get("category")
        if isinstance(category, dict):
            return category.get("name", "その他")
        if isinstance(category, str):
            return category
        return "その他"

    @staticmethod
    def _extract_brand(item_data: Dict) -> str:
        brand = item_data.get("itemBrand") or item_data.get("brand")
        if isinstance(brand, dict):
            return brand.get("name") or brand.get("subName") or "不明"
        if isinstance(brand, str):
            return brand
        return "不明"

    @staticmethod
    def _extract_seller_name(item_data: Dict) -> str:
        seller = item_data.get("seller")
        if isinstance(seller, dict):
            return seller.get("name", "不明")
        return "不明"

    @staticmethod
    def _extract_seller_rating(item_data: Dict) -> Optional[float]:
        seller = item_data.get("seller")
        if isinstance(seller, dict):
            return seller.get("rating")
        return None


# ---------------------------------------------------------------------------
# 结果 / 上下文 / 策略（字段保持不变以兼容 CLI）
# ---------------------------------------------------------------------------
class ScrapingStrategy(Enum):
    """爬虫策略枚举"""
    PLAYWRIGHT = "playwright_browser"


@dataclass
class ScrapingResult:
    """爬虫结果"""
    products: List[ProductEntity]
    total_found: int
    pages_scraped: int
    strategy_used: ScrapingStrategy
    processing_time: float
    metadata: Dict[str, Any]


@dataclass
class ScrapingContext:
    """爬虫上下文"""
    query: QueryEntity
    max_pages: int = 3
    max_products: int = 50
    strategy: ScrapingStrategy = ScrapingStrategy.PLAYWRIGHT
    use_cache: bool = True


# ---------------------------------------------------------------------------
# Playwright 爬虫
# ---------------------------------------------------------------------------
class PlaywrightMercariScraper:
    """无头 Chromium 爬虫：首屏抓 DOM + 浏览器上下文调 API 翻页"""

    def __init__(self, config: AppConfig):
        self.config = config
        self._pw = None
        self._browser = None

        sc = getattr(config, "scraping", None)
        self.nav_timeout_ms = 45000
        self.selector_timeout_ms = 30000
        self.settle_seconds = 2.5
        self.delay_range = tuple(getattr(sc, "delay_range", (1, 3)) or (1, 3))

        # 统计
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0

    async def initialize(self):
        """启动 Playwright + 无头 Chromium（浏览器实例复用，不每次重启）"""
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=True)
        logger.info("PlaywrightMercariScraper: 无头 Chromium 已启动")

    async def close(self):
        try:
            if self._browser:
                await self._browser.close()
        finally:
            if self._pw:
                await self._pw.stop()
        self._browser = None
        self._pw = None
        logger.info("PlaywrightMercariScraper: 已关闭")

    async def _new_context(self):
        return await self._browser.new_context(
            user_agent=DEFAULT_UA,
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
            viewport={"width": 1440, "height": 900},
            extra_http_headers={"Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8"},
        )

    def _build_search_url(self, query: QueryEntity) -> str:
        proc = SearchParameterProcessor()
        filters = proc.process_query_parameters(query)
        keyword = filters.get("keyword") or (getattr(query, "original_query", "") or "")
        params: Dict[str, str] = {"keyword": keyword}
        if filters.get("price_min"):
            params["price_min"] = filters["price_min"]
        if filters.get("price_max"):
            params["price_max"] = filters["price_max"]
        # category_id / item_condition_id 仅在为纯数字时才带上（query_parser 有时给的是
        # 分类名而非 ID，Mercari 只认数字 ID，带上非数字会被忽略甚至干扰搜索）
        cat = str(filters.get("category_id") or "")
        if cat.isdigit():
            params["category_id"] = cat
        cond = str(filters.get("status") or "")
        if cond.isdigit():
            params["item_condition_id"] = cond
        return f"{SEARCH_PAGE_URL}?{urlencode(params)}"

    @staticmethod
    def _parse_price_text(text: Any) -> Optional[int]:
        if text is None:
            return None
        if isinstance(text, (int, float)):
            return int(text)
        digits = re.sub(r"[^\d]", "", str(text))
        return int(digits) if digits else None

    def _dom_item_to_entity(self, it: Dict[str, Any]) -> Optional[ProductEntity]:
        pid = it.get("id")
        title = it.get("title")
        if not pid or not title:  # id + title 必填
            return None
        return ProductEntity(
            id=str(pid),
            title=str(title),
            price=self._parse_price_text(it.get("price")),
            url=it.get("url") or f"https://jp.mercari.com/item/{pid}",
            image_urls=[it["thumb"]] if it.get("thumb") else [],
            listed_at=datetime.now(),
            updated_at=datetime.now(),
        )

    @staticmethod
    def _enrich_from_api(dom_pe: ProductEntity, api_pe: Optional[ProductEntity]) -> None:
        """用 API 商品数据富化 DOM 商品缺失的字段（状态/卖家/品牌/分类等）"""
        if api_pe is None:
            return
        if not dom_pe.condition or dom_pe.condition == "不明":
            dom_pe.condition = api_pe.condition
        if not dom_pe.seller_name or dom_pe.seller_name == "不明":
            dom_pe.seller_name = api_pe.seller_name
        if not dom_pe.seller_id:
            dom_pe.seller_id = api_pe.seller_id
        if not dom_pe.brand or dom_pe.brand == "不明":
            dom_pe.brand = api_pe.brand
        if not dom_pe.category or dom_pe.category == "その他":
            dom_pe.category = api_pe.category
        if not dom_pe.price and api_pe.price:
            dom_pe.price = api_pe.price
        if not dom_pe.image_urls and api_pe.image_urls:
            dom_pe.image_urls = api_pe.image_urls
        dom_pe.sold = api_pe.sold

    async def _fetch_next_page(self, page, captured_req: Dict[str, Any], page_token: str) -> Dict[str, Any]:
        """在页面上下文里复用浏览器 dpop 调 entities:search 拉下一页"""
        try:
            body = json.loads(captured_req["post_data"]) if captured_req.get("post_data") else {}
        except (ValueError, TypeError):
            body = {}
        body["pageToken"] = page_token
        dpop = captured_req.get("headers", {}).get("dpop", "")
        return await page.evaluate(
            _REPLAY_JS,
            {"url": captured_req["url"], "dpop": dpop, "body": body},
        )

    async def search(self, query: QueryEntity, max_products: int, max_pages: int) -> Dict[str, Any]:
        """执行一次搜索抓取，返回 {products, pages_scraped, total_found}"""
        products: List[ProductEntity] = []
        seen_ids = set()
        pages_scraped = 0
        total_found = 0

        # 每次 scrape 一个独立 context（会话）
        context = await self._new_context()
        page = await context.new_page()

        cap: Dict[str, Any] = {"req": None}
        api_responses: List[Any] = []

        def on_request(req):
            if SEARCH_API_PATH in req.url and cap["req"] is None:
                try:
                    cap["req"] = {
                        "url": req.url,
                        "headers": dict(req.headers),
                        "post_data": req.post_data,
                    }
                except Exception:  # noqa: BLE001
                    pass

        def on_response(resp):
            if SEARCH_API_PATH in resp.url:
                api_responses.append(resp)

        page.on("request", on_request)
        page.on("response", on_response)

        url = self._build_search_url(query)

        try:
            logger.info(f"打开搜索页: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=self.nav_timeout_ms)
            self.request_count += 1

            try:
                await page.wait_for_selector(ITEM_CELL_SELECTOR, timeout=self.selector_timeout_ms)
            except PlaywrightTimeout:
                logger.warning("等待商品卡片超时——可能无搜索结果")
                return {"products": [], "pages_scraped": 1, "total_found": 0}

            await asyncio.sleep(self.settle_seconds)  # 让 entities:search 响应落地

            # ---- 读首屏 API 响应（浏览器自己发的，免费复用）：
            #      拿 numFound + nextPageToken，并把完整 items 建成索引以补全/富化 ----
            api_items_by_id: Dict[str, ProductEntity] = {}
            api_meta: Optional[Dict[str, Any]] = None
            for resp in api_responses:
                try:
                    rj = await resp.json()
                except Exception:  # noqa: BLE001
                    continue
                if not isinstance(rj, dict):
                    continue
                meta = rj.get("meta")
                if isinstance(meta, dict) and api_meta is None:
                    api_meta = meta
                for pe in ProductDataConverter.convert_api_response(rj):
                    api_items_by_id.setdefault(pe.id, pe)

            # ---- 首屏：抽 DOM（主路径，证明真实渲染），用 API 数据富化状态/卖家等字段 ----
            dom_items = await page.evaluate(_EXTRACT_JS)
            pages_scraped = 1
            self.success_count += 1
            for it in dom_items:
                pe = self._dom_item_to_entity(it)
                if not pe or pe.id in seen_ids:
                    continue
                self._enrich_from_api(pe, api_items_by_id.get(pe.id))
                seen_ids.add(pe.id)
                products.append(pe)
            dom_count = len(products)

            # ---- 用首屏 API 响应补全 DOM 尚未 hydrate 的商品（同一批数据，零额外请求）----
            for pid, api_pe in api_items_by_id.items():
                if pid not in seen_ids:
                    seen_ids.add(pid)
                    products.append(api_pe)
            logger.info(
                f"首屏：DOM {dom_count} 个 + API 响应补全至 {len(products)} 个商品"
            )

            next_token = ""
            if isinstance(api_meta, dict):
                total_found = int(api_meta.get("numFound") or 0)
                next_token = api_meta.get("nextPageToken") or ""
            if total_found < len(products):
                total_found = len(products)

            # ---- 翻页：浏览器上下文调 API（仅当需要更多且有 token）----
            while (
                len(products) < max_products
                and pages_scraped < max_pages
                and next_token
                and cap["req"]
            ):
                await asyncio.sleep(random.uniform(*self.delay_range))  # 克制
                res = await self._fetch_next_page(page, cap["req"], next_token)
                status = res.get("status") if isinstance(res, dict) else -1

                # 401 兜底：重新 goto 刷新 dpop 再试一次
                if status == 401:
                    logger.warning("翻页 401，重新加载搜索页刷新 dpop 后重试")
                    cap["req"] = None
                    await page.goto(url, wait_until="domcontentloaded", timeout=self.nav_timeout_ms)
                    try:
                        await page.wait_for_selector(ITEM_CELL_SELECTOR, timeout=self.selector_timeout_ms)
                    except PlaywrightTimeout:
                        pass
                    await asyncio.sleep(self.settle_seconds)
                    if cap["req"]:
                        res = await self._fetch_next_page(page, cap["req"], next_token)
                        status = res.get("status") if isinstance(res, dict) else -1

                self.request_count += 1
                data = res.get("data") if isinstance(res, dict) else None
                if status != 200 or not isinstance(data, dict):
                    logger.warning(f"翻页失败 status={status}，停止翻页")
                    self.error_count += 1
                    break

                self.success_count += 1
                page_products = ProductDataConverter.convert_api_response(data)
                added = 0
                for pe in page_products:
                    if pe.id not in seen_ids:
                        seen_ids.add(pe.id)
                        products.append(pe)
                        added += 1
                pages_scraped += 1

                meta = data.get("meta") or {}
                next_token = meta.get("nextPageToken") or ""
                logger.info(f"翻页第 {pages_scraped} 页：新增 {added} 个商品（累计 {len(products)}）")
                if added == 0 or not next_token:
                    break

            products = products[:max_products]
            return {
                "products": products,
                "pages_scraped": pages_scraped,
                "total_found": max(total_found, len(products)),
            }
        finally:
            await context.close()

    async def connectivity_check(self) -> bool:
        """轻量连通性检查：打开一个 context 访问首页"""
        context = await self._new_context()
        try:
            page = await context.new_page()
            resp = await page.goto("https://jp.mercari.com", wait_until="domcontentloaded", timeout=self.nav_timeout_ms)
            return bool(resp and resp.status == 200)
        finally:
            await context.close()

    def get_stats(self) -> Dict[str, Any]:
        total = self.request_count
        success_rate = self.success_count / total if total > 0 else 0
        return {
            "total_requests": total,
            "successful_requests": self.success_count,
            "failed_requests": self.error_count,
            "success_rate": round(success_rate, 3),
            "strategy": ScrapingStrategy.PLAYWRIGHT.value,
            "browser": "chromium",
            "headless": True,
        }


# ---------------------------------------------------------------------------
# 对外服务（公共接口保持不变）
# ---------------------------------------------------------------------------
class ScraperService:
    """爬虫服务：封装 Playwright 抓取，供 CLI / API 使用"""

    def __init__(self, config: AppConfig):
        self.config = config
        self.scraper: Optional[PlaywrightMercariScraper] = None
        self.cache: Dict[str, Any] = {}
        self.cache_ttl = int(getattr(getattr(config, "scraping", None), "cache_ttl", 300) or 300)
        self.default_max_pages = int(getattr(getattr(config, "scraping", None), "max_pages", 3) or 3)
        # 克制：默认最多 3 页
        if self.default_max_pages > 5:
            self.default_max_pages = 5
        logger.info("ScraperService initialized")

    async def initialize(self):
        self.scraper = PlaywrightMercariScraper(self.config)
        await self.scraper.initialize()
        logger.info("ScraperService initialized successfully")

    async def close(self):
        if self.scraper:
            await self.scraper.close()
        logger.info("ScraperService closed")

    async def scrape(self, query_or_context, max_products: int = 10) -> ScrapingResult:
        """执行爬取任务（兼容 QueryEntity 与 ScrapingContext 两种入参）"""
        if isinstance(query_or_context, ScrapingContext):
            context = query_or_context
        else:
            context = ScrapingContext(
                query=query_or_context,
                max_products=max_products,
                max_pages=self.default_max_pages,
            )

        if not self.scraper:
            await self.initialize()

        start_time = time.time()

        # 缓存
        cache_key = self._generate_cache_key(context)
        if context.use_cache and cache_key in self.cache:
            entry = self.cache[cache_key]
            if time.time() - entry["timestamp"] < self.cache_ttl:
                logger.info("使用缓存结果")
                cached = entry["result"]
                cached.processing_time = time.time() - start_time
                return cached

        try:
            outcome = await self.scraper.search(
                context.query,
                max_products=context.max_products,
                max_pages=max(1, min(context.max_pages, 5)),
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"爬取失败: {e}")
            raise BaseServiceException(f"爬取失败: {e}", "scraper_service")

        processing_time = time.time() - start_time
        result = ScrapingResult(
            products=outcome["products"],
            total_found=outcome["total_found"],
            pages_scraped=outcome["pages_scraped"],
            strategy_used=context.strategy,
            processing_time=processing_time,
            metadata={
                "query": getattr(context.query, "original_query", ""),
                "scraper_stats": self.scraper.get_stats() if self.scraper else {},
            },
        )

        if context.use_cache:
            self.cache[cache_key] = {"result": result, "timestamp": time.time()}

        logger.info(
            f"爬取完成: 找到 {len(result.products)} 个产品，"
            f"翻 {result.pages_scraped} 页，耗时 {processing_time:.2f}s"
        )
        return result

    def _generate_cache_key(self, context: ScrapingContext) -> str:
        q = context.query
        kws = getattr(q, "keywords", None) or []
        key_parts = [
            getattr(q, "original_query", "") or "",
            ",".join(str(k) for k in kws),
            str(context.max_pages),
            str(context.max_products),
            str(getattr(q, "category", None) or "none"),
            str(getattr(q, "condition", None) or "none"),
            str(getattr(q, "price_min", None) or 0),
            str(getattr(q, "price_max", None) or 999999),
        ]
        return "scraper:" + ":".join(key_parts)

    def get_service_info(self) -> Dict[str, Any]:
        return {
            "service_name": "ScraperService",
            "available_strategies": [ScrapingStrategy.PLAYWRIGHT.value],
            "endpoints": {
                "search_page": SEARCH_PAGE_URL,
                "search_api": f"https://{SEARCH_API_PATH}",
            },
            "engine": "playwright-chromium-headless",
            "cache_size": len(self.cache),
            "scraper_stats": self.scraper.get_stats() if self.scraper else {},
        }

    async def health_check(self) -> Dict[str, str]:
        try:
            if not self.scraper or not self.scraper._browser:
                return {"status": "not_initialized"}
            ok = await self.scraper.connectivity_check()
            if ok:
                return {"status": "healthy", "engine": "playwright-chromium", "headless": "true"}
            return {"status": "unhealthy", "reason": "无法连接到 Mercari"}
        except Exception as e:  # noqa: BLE001
            return {"status": "error", "reason": str(e)}
