"""
爬虫服务模块 - 重构版

该模块提供Mercari平台的统一数据爬取功能。
实现了统一的/v2/entities:search接口调用、智能Session管理和指纹轮换。

主要功能：
- 统一的/v2/entities:search API接口
- 智能Session和CSRF Token管理
- 浏览器和TLS指纹轮换
- 统一的参数处理和数据转换
- 优化的错误处理和重试机制

Author: Mercari AI Agent Team (Refactored & Optimized)
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import json
import random
import time
import ssl
import hashlib
import httpx
import uuid
from urllib.parse import urlencode, quote
import re
from ...shared.utils.logger_utils import get_logger

# 配置日志级别
logger = get_logger(__name__)
logger.setLevel(logging.INFO)  # 降低日志级别，减少噪音

# 导入必要的依赖
from ...domain.entities.product import ProductEntity
from ...domain.entities.query import QueryEntity
from ...shared.exceptions.service_exceptions import BaseServiceException
from ...shared.config.app_config import AppConfig
from .browser_fingerprint_manager import BrowserFingerprintManager, FingerprintConfig
from .tls_fingerprint_manager import TLSFingerprintManager, TLSConfig

# API常量
DEFAULT_PAGE_SIZE = 120
INDEX_ROUTING_UNSPECIFIED = "INDEX_ROUTING_UNSPECIFIED"
SERVICE_FROM = "web"
SORT_DEFAULT = "default"
SORT_SCORE = "score"
ORDER_ASC = "asc"
ORDER_DESC = "desc"


@dataclass
class SessionContext:
    """Session上下文"""
    cookies: Dict[str, str]
    csrf_token: Optional[str]
    initialized: bool = False
    last_used: Optional[datetime] = None


@dataclass
class APIResponse:
    """统一的API响应格式"""
    success: bool
    data: Optional[Dict[str, Any]]
    error: Optional[str]
    status_code: int
    processing_time: float


class SearchParameterProcessor:
    """统一的搜索参数处理器"""
    
    @staticmethod
    def parse_numeric_array(value: Optional[str]) -> List[int]:
        """解析逗号分隔的数字字符串"""
        if not value:
            return []
        return [int(x) for x in value.split(",") if x.isdigit()]
    
    @staticmethod
    def map_sort_option(value: str) -> str:
        """映射排序选项"""
        return {
            "created_time": "SORT_CREATED_TIME",
            "num_likes": "SORT_NUM_LIKES", 
            "score": "SORT_SCORE",
            "price": "SORT_PRICE",
        }.get(value, "SORT_DEFAULT")
    
    @staticmethod
    def map_status_option(value: str) -> List[str]:
        """转换状态过滤器"""
        return [value] if value else []
    
    @staticmethod
    def map_shipping_method(value: Optional[str]) -> List[str]:
        """映射配送方式"""
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
        filters = {}
        
        # 关键词处理
        if query.keywords:
            if isinstance(query.keywords, list):
                filters['keyword'] = ' '.join(str(k) for k in query.keywords if k)
            else:
                filters['keyword'] = str(query.keywords)
        
        # 价格范围
        if hasattr(query, 'price_min') and query.price_min:
            filters['price_min'] = str(int(query.price_min))
        if hasattr(query, 'price_max') and query.price_max:
            filters['price_max'] = str(int(query.price_max))
        
        # 商品状态
        if hasattr(query, 'condition') and query.condition:
            condition_mapping = {
                "新品・未使用": "1",
                "未使用に近い": "2",
                "目立った傷や汚れなし": "3", 
                "やや傷や汚れあり": "4",
                "傷や汚れあり": "5",
                "全体的に状態が悪い": "6"
            }
            if query.condition in condition_mapping:
                filters['status'] = condition_mapping[query.condition]
        
        # 分类
        if hasattr(query, 'category') and query.category:
            filters['category_id'] = query.category
            
        return filters
    
    def build_v2_request_body(self, filters: Dict[str, Any], paging: Dict[str, Any]) -> Dict[str, Any]:
        """构建v2 API请求体"""
        # 构建搜索条件
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
            "attributes": [],  # 简化属性处理
            "itemTypes": [],   # 简化项目类型处理
            "skuIds": filters.get("sku_ids", "").split(",") if filters.get("sku_ids") else [],
        }
        
        # 如果排序为默认，则使用评分排序
        if search_condition.get("sort") == SORT_DEFAULT:
            search_condition["sort"] = SORT_SCORE
        
        # 构建完整请求体
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
        
        # 移除None值
        return {k: v for k, v in payload.items() if v is not None}


class UnifiedMercariAPIClient:
    """统一的Mercari API客户端"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.parameter_processor = SearchParameterProcessor()
        self.session_context = SessionContext(cookies={}, csrf_token=None)
        self.base_url = "https://api.mercari.jp"
        
    async def search_entities(
        self, 
        query: QueryEntity,
        paging: Optional[Dict[str, Any]] = None
    ) -> APIResponse:
        """统一的/v2/entities:search接口调用"""
        start_time = time.time()
        
        try:
            # 处理查询参数
            filters = self.parameter_processor.process_query_parameters(query)
            
            # 构建请求体
            paging = paging or {}
            request_body = self.parameter_processor.build_v2_request_body(filters, paging)
            
            # 发起API请求
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/v2/entities:search",
                    json=request_body,
                    timeout=30
                )
                
                processing_time = time.time() - start_time
                
                if response.status_code == 200:
                    return APIResponse(
                        success=True,
                        data=response.json(),
                        error=None,
                        status_code=response.status_code,
                        processing_time=processing_time
                    )
                else:
                    return APIResponse(
                        success=False,
                        data=None,
                        error=f"API请求失败: {response.status_code}",
                        status_code=response.status_code,
                        processing_time=processing_time
                    )
                    
        except Exception as e:
            processing_time = time.time() - start_time
            return APIResponse(
                success=False,
                data=None,
                error=str(e),
                status_code=0,
                processing_time=processing_time
            )


class ProductDataConverter:
    """简化的产品数据转换器"""
    
    @staticmethod
    def convert_api_response(api_data: Dict) -> List[ProductEntity]:
        """专注于API响应转换，移除HTML解析逻辑"""
        products = []
        
        # 提取商品数据
        items_data = ProductDataConverter._extract_items_from_response(api_data)
        
        for item_data in items_data:
            try:
                product = ProductDataConverter._convert_single_item(item_data)
                if product:
                    products.append(product)
            except Exception as e:
                logger.warning(f"转换单个商品失败: {e}")
                continue
                
        return products
    
    @staticmethod
    def _extract_items_from_response(api_data: Dict) -> List[Dict]:
        """从API响应中提取商品列表"""
        possible_paths = [
            ['items'],
            ['data', 'items'],
            ['results', 'items'],
            ['entities'],
            ['data', 'entities']
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
        """转换单个商品数据"""
        try:
            product_id = item_data.get('id') or item_data.get('item_id')
            if not product_id:
                return None
            
            # 价格处理
            price = item_data.get('price', 0)
            if isinstance(price, str):
                price = int(price.replace('¥', '').replace(',', '')) if price else 0
            elif not isinstance(price, int):
                price = 0
            
            # 状态映射
            status_mapping = {
                "1": "新品・未使用",
                "2": "未使用に近い", 
                "3": "目立った傷や汚れなし",
                "4": "やや傷や汚れあり",
                "5": "傷や汚れあり",
                "6": "全体的に状態が悪い"
            }
            condition = status_mapping.get(str(item_data.get('status', '')), "不明")
            
            # 图片处理
            images = []
            if 'thumbnails' in item_data and isinstance(item_data['thumbnails'], list):
                images = item_data['thumbnails']
            elif 'thumbnail' in item_data:
                images = [item_data['thumbnail']]
            elif 'image_url' in item_data:
                images = [item_data['image_url']]
            
            return ProductEntity(
                id=str(product_id),
                title=item_data.get('name', ''),
                price=price,
                url=f"https://jp.mercari.com/item/{product_id}",
                description=item_data.get('description', ''),
                condition=condition,
                category=ProductDataConverter._extract_category(item_data),
                brand=item_data.get('brand', '不明'),
                seller_name=ProductDataConverter._extract_seller_name(item_data),
                seller_id=item_data.get('seller_id'),
                seller_rating=ProductDataConverter._extract_seller_rating(item_data),
                image_urls=images,
                view_count=item_data.get('num_likes', 0),
                like_count=item_data.get('num_comments', 0),
                shipping_fee=item_data.get('shipping_fee'),
                listed_at=datetime.now(),
                updated_at=datetime.now(),
                sold=item_data.get('status') == 'sold'
            )
            
        except Exception as e:
            logger.error(f"转换商品数据失败: {e}")
            return None
    
    @staticmethod
    def _extract_category(item_data: Dict) -> str:
        """提取类别信息"""
        category = item_data.get('category')
        if isinstance(category, dict):
            return category.get('name', 'その他')
        elif isinstance(category, str):
            return category
        return 'その他'
    
    @staticmethod
    def _extract_seller_name(item_data: Dict) -> str:
        """提取卖家名称"""
        seller = item_data.get('seller')
        if isinstance(seller, dict):
            return seller.get('name', '不明')
        return '不明'
    
    @staticmethod
    def _extract_seller_rating(item_data: Dict) -> Optional[float]:
        """提取卖家评分"""
        seller = item_data.get('seller')
        if isinstance(seller, dict):
            return seller.get('rating')
        return None


class APIErrorHandler:
    """统一的API错误处理"""
    
    @staticmethod
    def handle_api_error(error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        """统一错误处理，减少异常分支"""
        error_info = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
            "timestamp": datetime.now().isoformat()
        }
        
        # 根据错误类型进行分类处理
        if isinstance(error, httpx.HTTPStatusError):
            error_info["http_status"] = error.response.status_code
            error_info["retry_recommended"] = error.response.status_code >= 500
        elif isinstance(error, httpx.TimeoutException):
            error_info["retry_recommended"] = True
        elif isinstance(error, httpx.ConnectError):
            error_info["retry_recommended"] = True
        else:
            error_info["retry_recommended"] = False
            
        logger.error(f"API错误: {error_info}")
        return error_info


class ScrapingStrategy(Enum):
    """爬虫策略枚举"""
    HTTP_CLIENT = "http_client"      # 基于HTTP客户端的爬虫


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
    max_pages: int = 5
    max_products: int = 50
    strategy: ScrapingStrategy = ScrapingStrategy.HTTP_CLIENT
    use_cache: bool = True


class MercariDataParser:
    """Mercari数据解析器 - 完全実装版"""
    
    def __init__(self):
        self.price_pattern = re.compile(r'¥([\d,]+)')
        self.id_pattern = re.compile(r'/items/([a-zA-Z0-9]+)')
        
        # より詳細な正規表現パターン
        self.number_pattern = re.compile(r'[\d,]+')
        self.condition_mapping = {
            "新品・未使用": "新品・未使用",
            "未使用に近い": "未使用に近い", 
            "目立った傷や汚れなし": "目立った傷や汚れなし",
            "やや傷や汚れあり": "やや傷や汚れあり",
            "傷や汚れあり": "傷や汚れあり",
            "全体的に状態が悪い": "全体的に状態が悪い"
        }
        
        # JSONデータ抽出用パターン
        self.json_pattern = re.compile(r'window\.__NUXT__\s*=\s*({.+?});', re.DOTALL)
        self.state_pattern = re.compile(r'"state":\s*({.+?})(?=,"serverRendered")', re.DOTALL)
    
    def parse_search_results(self, html_content: str) -> List[Dict[str, Any]]:
        """搜索结果页面"""
        products = []
        
        try:
            # 简化解析，主要使用正则表达式
            products = self._parse_regex_search_results(html_content)
            
            return products
            
        except Exception as e:
            logger.error(f"搜索结果的解析失败: {e}")
            return []
    
    def _find_search_data(self, state: Dict) -> Optional[Dict]:
        """从状态数据中查找搜索结果"""
        # 检查各种可能的路径
        possible_paths = [
            ['search', 'results'],
            ['searchResults', 'items'],
            ['itemList', 'items'],
            ['data', 'items']
        ]
        
        for path in possible_paths:
            current = state
            try:
                for key in path:
                    current = current[key]
                if isinstance(current, (list, dict)):
                    return current
            except (KeyError, TypeError):
                continue
        
        return None
    
    def _extract_products_from_data(self, data: Any) -> List[Dict[str, Any]]:
        """从数据结构中提取商品信息"""
        products = []
        
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict) and 'items' in data:
            items = data['items']
        else:
            return []
        
        for item in items:
            if isinstance(item, dict):
                product = self._parse_product_item(item)
                if product:
                    products.append(product)
        
        return products
    
    def _parse_product_item(self, item: Dict) -> Optional[Dict[str, Any]]:
        """解析单个商品项"""
        try:
            product = {
                'id': item.get('id') or item.get('itemId'),
                'title': item.get('name') or item.get('title'),
                'price': self._parse_price(item.get('price')),
                'condition': self._normalize_condition(item.get('condition')),
                'seller_name': item.get('seller', {}).get('name') if item.get('seller') else None,
                'seller_rating': item.get('seller', {}).get('rating') if item.get('seller') else None,
                'image_url': self._extract_image_url(item),
                'url': self._build_product_url(item.get('id') or item.get('itemId')),
                'description': item.get('description', ''),
                'category': self._extract_category(item),
                'view_count': item.get('numLikes') or 0,
                'like_count': item.get('numComments') or 0,
                'shipping_cost': self._parse_shipping_cost(item)
            }
            
            # 如果缺少必需字段，则返回None
            if not product['id'] or not product['title']:
                return None
            
            return product
            
        except Exception as e:
            logger.debug(f"商品项解析失败: {e}")
            return None
    
    
    def _parse_regex_search_results(self, html_content: str) -> List[Dict[str, Any]]:
        """使用正则表达式进行HTML解析（后备）"""
        products = []
        
        try:
            # 提取商品ID和URL
            id_matches = self.id_pattern.findall(html_content)
            
            # 提取价格
            price_matches = self.price_pattern.findall(html_content)
            
            # 提取标题（简单模式）
            title_pattern = re.compile(r'<h\d[^>]*>([^<]+)</h\d>', re.IGNORECASE)
            title_matches = title_pattern.findall(html_content)
            
            # 组合数据
            max_items = min(len(id_matches), 20)  # 最多20个
            for i in range(max_items):
                product_id = id_matches[i] if i < len(id_matches) else f"regex_{i}"
                price = int(price_matches[i].replace(',', '')) if i < len(price_matches) else 0
                title = title_matches[i].strip() if i < len(title_matches) else f"商品 {i+1}"
                
                products.append({
                    'id': product_id,
                    'title': title,
                    'price': price,
                    'condition': "不明",
                    'seller_name': "不明",
                    'seller_rating': None,
                    'image_url': None,
                    'url': f"https://jp.mercari.com/item/{product_id}",
                    'description': "",
                    'category': "その他",
                    'view_count': 0,
                    'like_count': 0,
                    'shipping_cost': None
                })
            
            return products
            
        except Exception as e:
            logger.error(f"正则表达式解析失败: {e}")
            return []
    
    def parse_product_detail(self, html_content: str, product_id: str) -> Optional[Dict[str, Any]]:
        """解析产品详情页面"""
        try:
            # 首先尝试从JSON数据中提取
            json_product = self._extract_detail_from_json(html_content, product_id)
            if json_product:
                return json_product
            
            # 使用正则表达式解析
            return self._parse_regex_product_detail(html_content, product_id)
                
        except Exception as e:
            logger.error(f"产品详情的解析失败: {e}")
            return None
    
    def _extract_detail_from_json(self, html_content: str, product_id: str) -> Optional[Dict[str, Any]]:
        """从JSON中提取商品详情"""
        try:
            json_match = self.json_pattern.search(html_content)
            if not json_match:
                return None
            
            nuxt_data = json.loads(json_match.group(1))
            
            if 'state' in nuxt_data:
                # 查找商品详情数据
                item_data = self._find_item_detail_data(nuxt_data['state'], product_id)
                if item_data:
                    return self._parse_detailed_product_item(item_data, product_id)
            
            return None
            
        except Exception as e:
            logger.debug(f"详情JSON提取失败: {e}")
            return None
    
    def _find_item_detail_data(self, state: Dict, product_id: str) -> Optional[Dict]:
        """从状态中查找商品详情数据"""
        possible_paths = [
            ['item'],
            ['itemDetail'],
            ['product'],
            ['data', 'item']
        ]
        
        for path in possible_paths:
            current = state
            try:
                for key in path:
                    current = current[key]
                if isinstance(current, dict) and current.get('id') == product_id:
                    return current
            except (KeyError, TypeError):
                continue
        
        return None
    
    def _parse_detailed_product_item(self, item: Dict, product_id: str) -> Dict[str, Any]:
        """解析详细商品数据"""
        return {
            'id': product_id,
            'title': item.get('name') or item.get('title', ''),
            'price': self._parse_price(item.get('price')),
            'condition': self._normalize_condition(item.get('condition')),
            'seller_name': item.get('seller', {}).get('name') if item.get('seller') else '不明',
            'seller_rating': item.get('seller', {}).get('rating') if item.get('seller') else None,
            'images': self._extract_multiple_images(item),
            'url': f"https://jp.mercari.com/item/{product_id}",
            'description': item.get('description', ''),
            'category': self._extract_category(item),
            'brand': item.get('brand', '不明'),
            'size': item.get('size', 'フリーサイズ'),
            'color': item.get('color', 'その他'),
            'shipping_cost': self._parse_shipping_cost(item),
            'view_count': item.get('viewCount', 0),
            'like_count': item.get('likeCount', 0)
        }
    
    
    def _parse_regex_product_detail(self, html_content: str, product_id: str) -> Dict[str, Any]:
        """使用正则表达式解析商品详情"""
        try:
            # 提取标题
            title_pattern = re.compile(r'<title[^>]*>([^<]+)</title>', re.IGNORECASE)
            title_match = title_pattern.search(html_content)
            title = title_match.group(1).strip() if title_match else f"商品 {product_id}"
            
            # 提取价格
            price_match = self.price_pattern.search(html_content)
            price = int(price_match.group(1).replace(',', '')) if price_match else 0
            
            return {
                'id': product_id,
                'title': title,
                'price': price,
                'condition': '不明',
                'seller_name': '不明',
                'seller_rating': None,
                'images': [],
                'url': f"https://jp.mercari.com/item/{product_id}",
                'description': '',
                'category': 'その他',
                'brand': '不明',
                'size': 'フリーサイズ',
                'color': 'その他',
                'shipping_cost': None,
                'view_count': 0,
                'like_count': 0
            }
            
        except Exception as e:
            logger.error(f"正则表达式详情解析失败: {e}")
            return None
    
    # ヘルパーメソッド
    def _parse_price(self, price_text: Any) -> int:
        """将价格字符串转换为数值"""
        if isinstance(price_text, (int, float)):
            return int(price_text)
        
        if not isinstance(price_text, str):
            return 0
        
        # 提取数字
        numbers = self.number_pattern.findall(price_text.replace(',', ''))
        if numbers:
            return int(numbers[0])
        return 0
    
    def _normalize_condition(self, condition: Any) -> str:
        """规范化商品状态"""
        if not condition:
            return "不明"
        
        condition_str = str(condition)
        for key, value in self.condition_mapping.items():
            if key in condition_str:
                return value
        
        return condition_str
    
    def _extract_image_url(self, item: Dict) -> Optional[str]:
        """从项中提取图片URL"""
        possible_keys = ['imageUrl', 'image', 'photo', 'thumbnail']
        for key in possible_keys:
            if key in item and item[key]:
                return item[key]
        
        if 'images' in item and isinstance(item['images'], list) and item['images']:
            return item['images'][0]
        
        return None
    
    def _extract_multiple_images(self, item: Dict) -> List[str]:
        """提取多个图片URL"""
        images = []
        
        if 'images' in item and isinstance(item['images'], list):
            images.extend(item['images'])
        
        single_image = self._extract_image_url(item)
        if single_image and single_image not in images:
            images.append(single_image)
        
        return images
    
    def _build_product_url(self, product_id: str) -> str:
        """构建商品URL"""
        return f"https://jp.mercari.com/item/{product_id}"
    
    def _extract_category(self, item: Dict) -> str:
        """提取类别"""
        possible_keys = ['category', 'categoryName', 'itemCategory']
        for key in possible_keys:
            if key in item and item[key]:
                return str(item[key])
        return "その他"
    
    def _parse_shipping_cost(self, item: Dict) -> Optional[int]:
        """解析运费"""
        shipping_keys = ['shippingCost', 'shipping', 'deliveryFee']
        for key in shipping_keys:
            if key in item:
                return self._parse_price(item[key])
        return None
    
    def _extract_html_title(self, soup) -> str:
        """从HTML提取标题"""
        selectors = ['h1', '[data-testid="item-name"]', '.item-name']
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)
        return "不明"
    
    def _extract_html_price(self, soup) -> int:
        """从HTML提取价格"""
        selectors = ['[data-testid="price"]', '.price', '[class*="price"]']
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return self._parse_price(element.get_text(strip=True))
        return 0
    
    def _extract_html_condition(self, soup) -> str:
        """从HTML提取商品状态"""
        selectors = ['[data-testid="condition"]', '.condition', '[class*="condition"]']
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return self._normalize_condition(element.get_text(strip=True))
        return "不明"
    
    def _extract_html_description(self, soup) -> str:
        """从HTML提取描述"""
        selectors = ['[data-testid="description"]', '.description', '[class*="description"]']
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)
        return ""
    
    def _extract_html_images(self, soup) -> List[str]:
        """从HTML提取图片URL"""
        images = []
        img_elements = soup.select('img[src*="mercdn.net"]')
        for img in img_elements:
            src = img.get('src')
            if src and src not in images:
                images.append(src)
        return images
    

class BaseScraper:
    """基础爬虫类"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.client = None
        self.parser = MercariDataParser()
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
        self.last_request_time = 0
        
        # 指纹管理器
        self.browser_fingerprint_manager = None
        self.tls_fingerprint_manager = None
        self.current_fingerprint = None
        self.current_tls_fingerprint = None
        
        # 配置
        self.max_retries = 3
        self.timeout = 30
        self.delay_range = (1, 3)
    
    async def initialize(self):
        """初始化爬虫"""
        try:
            logger.debug("开始初始化BaseScraper")
            
            # 初始化指纹管理器
            fingerprint_config = FingerprintConfig(
                enable_user_agent_rotation=True,
                enable_webgl_spoofing=True,
                enable_canvas_spoofing=True,
                enable_header_randomization=True,
                remove_automation_traces=True,
                max_fingerprint_usage=50,
                fingerprint_rotation_interval=1800
            )
            logger.debug(f"指纹配置: {fingerprint_config}")
            
            tls_config = TLSConfig(
                enable_fingerprint_rotation=True,
                fingerprint_rotation_interval=300,
                max_fingerprint_usage=100,
                enable_ja3_spoofing=True,
                enable_ja4_spoofing=True,
                enable_http2=True
            )
            logger.debug(f"TLS配置: {tls_config}")
            
            logger.debug("初始化浏览器指纹管理器...")
            self.browser_fingerprint_manager = BrowserFingerprintManager(fingerprint_config)
            logger.debug("浏览器指纹管理器初始化完成")
            
            logger.debug("初始化TLS指纹管理器...")
            self.tls_fingerprint_manager = TLSFingerprintManager(tls_config)
            logger.debug("TLS指纹管理器初始化完成")
            
            # 获取初始指纹
            logger.debug("生成浏览器指纹...")
            self.current_fingerprint = self.browser_fingerprint_manager.generate_fingerprint()
            logger.debug(f"生成的浏览器指纹: {self.current_fingerprint.browser_type.value} on {self.current_fingerprint.os_type.value}")
            
            logger.debug("获取TLS指纹...")
            self.current_tls_fingerprint = self.tls_fingerprint_manager.get_fingerprint()
            logger.debug(f"获取的TLS指纹: {self.current_tls_fingerprint.fingerprint_id}")
            
            # 使用指纹创建HTTP客户端
            headers = self.current_fingerprint.headers.copy()
            logger.debug(f"使用的请求头: {headers}")
            
            # 创建TLS连接器
            logger.debug("创建TLS连接器...")
            connector = self.tls_fingerprint_manager.create_connector(self.current_tls_fingerprint)
            logger.debug("TLS连接器创建完成")
            
            # 创建自定义SSL上下文
            logger.debug("创建SSL上下文...")
            ssl_context = self.tls_fingerprint_manager.create_ssl_context(self.current_tls_fingerprint)
            logger.debug(f"SSL上下文创建完成: {ssl_context}")
            
            logger.debug("创建httpx客户端...")
            self.client = httpx.AsyncClient(
                timeout=self.timeout,
                headers=headers,
                verify=ssl_context if ssl_context else True
            )
            logger.debug("httpx客户端创建完成")
            
            logger.info(f"BaseScraper initialized with fingerprint: {self.current_fingerprint.browser_type.value} on {self.current_fingerprint.os_type.value}")
            
        except Exception as e:
            logger.error(f"指纹管理器初始化失败: {e}")
            logger.debug(f"初始化异常详情: {e}", exc_info=True)
            raise e
    
    async def close(self):
        """关闭爬虫"""
        if self.client:
            await self.client.aclose()
        logger.info("BaseScraper closed")
    
    async def _make_request(self, url: str, **kwargs) -> Optional[httpx.Response]:
        """发起HTTP请求"""
        await self._apply_rate_limit()
        
        logger.debug(f"开始请求: {url}")
        logger.debug(f"请求参数: {kwargs}")
        logger.debug(f"当前请求头: {self.client.headers}")
        
        for attempt in range(self.max_retries):
            try:
                self.request_count += 1
                logger.debug(f"尝试 {attempt + 1}/{self.max_retries}: 发起请求到 {url}")
                
                response = await self.client.get(url, **kwargs)
                
                logger.debug(f"收到响应: 状态码 {response.status_code}, 内容长度: {len(response.text)}")
                logger.debug(f"响应头: {dict(response.headers)}")
                
                if response.status_code == 200:
                    self.success_count += 1
                    logger.debug(f"请求成功: {url}")
                    return response
                else:
                    logger.warning(f"请求返回状态码 {response.status_code}: {url}")
                    logger.debug(f"响应内容预览: {response.text[:500]}...")
                    if response.status_code == 429:  # 请求过于频繁
                        await asyncio.sleep(random.uniform(5, 10))
                    elif response.status_code >= 500:  # 服务器错误，可重试
                        await asyncio.sleep(random.uniform(2, 5))
                    else:  # 其他错误，不重试
                        break
                        
            except Exception as e:
                logger.error(f"请求失败 (尝试 {attempt + 1}): {e}")
                logger.debug(f"请求异常详情: {e}", exc_info=True)
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(random.uniform(1, 3))
        
        self.error_count += 1
        logger.error(f"所有请求尝试失败: {url}")
        return None
    
    async def _apply_rate_limit(self):
        """应用请求速率限制"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        min_interval = random.uniform(*self.delay_range)
        if time_since_last_request < min_interval:
            sleep_time = min_interval - time_since_last_request
            await asyncio.sleep(sleep_time)
        
        self.last_request_time = time.time()


class MercariScraper(BaseScraper):
    """Mercari爬虫类 - 支持Session和CSRF Token认证"""
    
    def __init__(self, config: AppConfig):
        super().__init__(config)
        self.base_url = "https://jp.mercari.com"
        self.search_url = f"{self.base_url}/search"
        self.search_api_url = "https://api.mercari.jp/v2/entities:search"
        
        # Session管理
        self.session_cookies = {}
        self.csrf_token = None
        self.session_initialized = False
    
    async def search_products(self, context: ScrapingContext) -> List[ProductEntity]:
        """搜索产品 - 自动初始化Session"""
        products = []
        
        try:
            # 确保Session已初始化
            if not self.session_initialized:
                await self._initialize_session()
            
            for page in range(1, min(context.max_pages + 1, 6)):  # 最多5页
                page_products = await self._scrape_search_page(context, page)
                if not page_products:
                    break
                
                products.extend(page_products)
                
                if len(products) >= context.max_products:
                    products = products[:context.max_products]
                    break
                
                # 页面间延迟
                await asyncio.sleep(random.uniform(2, 4))
        
        except Exception as e:
            logger.error(f"搜索产品失败: {e}")
            raise BaseServiceException(f"搜索产品失败: {e}", "scraper_service")
        
        return products
    
    async def _initialize_session(self):
        """初始化Session和CSRF Token"""
        try:
            logger.debug("开始初始化Mercari Session...")
            
            # 第一步：访问普通搜索页面获取Session Cookie
            initial_url = f"{self.search_url}?keyword=test"
            logger.debug(f"访问初始搜索页面: {initial_url}")
            
            response = await self._make_request(initial_url)
            if not response:
                raise BaseServiceException("无法获取初始搜索页面", "scraper_service")
            
            # 提取Cookie
            self._extract_session_cookies(response)
            
            # 提取CSRF Token
            self._extract_csrf_token(response.text)
            
            self.session_initialized = True
            logger.info(f"Session初始化成功 - Cookies: {len(self.session_cookies)}, CSRF: {'已获取' if self.csrf_token else '未获取'}")
            
        except Exception as e:
            logger.error(f"Session初始化失败: {e}")
            raise BaseServiceException(f"Session初始化失败: {e}", "scraper_service")
    
    def _extract_session_cookies(self, response: httpx.Response):
        """从响应中提取Session相关的Cookie"""
        cookies = {}
        
        # 从响应头中提取Set-Cookie
        set_cookies = response.headers.get_list('set-cookie')
        for cookie_header in set_cookies:
            try:
                # 解析Cookie
                cookie_parts = cookie_header.split(';')[0].split('=', 1)
                if len(cookie_parts) == 2:
                    name, value = cookie_parts
                    name = name.strip()
                    value = value.strip()
                    
                    # 只保存重要的Session Cookie
                    if name in ['mercari_session', '_mercari_session', 'csrf_token', '_csrf_token', 'XSRF-TOKEN']:
                        cookies[name] = value
                        logger.debug(f"提取到Cookie: {name}={value[:20]}...")
                        
            except Exception as e:
                logger.warning(f"解析Cookie失败: {e}")
                continue
        
        # 更新Session Cookies
        self.session_cookies.update(cookies)
        
        # 如果没有获取到关键Cookie，记录警告
        if not any(key in cookies for key in ['mercari_session', '_mercari_session']):
            logger.warning("未获取到mercari_session Cookie")
    
    def _extract_csrf_token(self, html_content: str):
        """从HTML中提取CSRF Token"""
        try:
            # 尝试多种CSRF Token提取方式
            csrf_patterns = [
                r'name="csrf-token"\s+content="([^"]+)"',
                r'name="_token"\s+content="([^"]+)"',
                r'"csrf_token":\s*"([^"]+)"',
                r'"_token":\s*"([^"]+)"',
                r'csrfToken:\s*["\']([^"\']+)["\']',
                r'X-CSRF-TOKEN["\']:\s*["\']([^"\']+)["\']'
            ]
            
            for pattern in csrf_patterns:
                match = re.search(pattern, html_content, re.IGNORECASE)
                if match:
                    self.csrf_token = match.group(1)
                    logger.debug(f"提取到CSRF Token: {self.csrf_token[:20]}...")
                    return
            
            # 如果没有找到CSRF Token，尝试从JavaScript中提取
            js_patterns = [
                r'window\.__NUXT__.*?"csrf_token":\s*"([^"]+)"',
                r'window\.csrf_token\s*=\s*["\']([^"\']+)["\']',
                r'_token["\']?\s*:\s*["\']([^"\']+)["\']'
            ]
            
            for pattern in js_patterns:
                match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
                if match:
                    self.csrf_token = match.group(1)
                    logger.debug(f"从JS中提取到CSRF Token: {self.csrf_token[:20]}...")
                    return
            
            logger.warning("未能提取到CSRF Token")
            
        except Exception as e:
            logger.error(f"提取CSRF Token失败: {e}")
    
    async def _scrape_search_page(self, context: ScrapingContext, page: int) -> List[ProductEntity]:
        """使用API爬取搜索页面"""
        try:
            # 构建API参数
            api_params = self._build_api_search_params(context, page)
            
            logger.debug(f"使用API搜索: {self.search_api_url}")
            logger.debug(f"API参数: {api_params}")
            
            # 准备请求头
            headers = self._build_api_headers()
            
            # 准备Cookie
            cookies = self._build_request_cookies()
            
            logger.debug(f"使用Cookie: {cookies}")
            logger.debug(f"使用Header: {headers}")
            
            response = await self._make_api_request(
                self.search_api_url, 
                json_data=api_params,
                headers=headers,
                cookies=cookies
            )
            
            if not response or response.status_code != 200:
                logger.warning(f"API请求失败: {response.status_code if response else 'None'}")
                if response:
                    logger.debug(f"API响应: {response.text[:500]}...")
                return []
            
            # 解析API返回的JSON数据
            try:
                json_data = response.json()
                logger.debug(f"API返回数据结构: {list(json_data.keys()) if isinstance(json_data, dict) else type(json_data)}")
                
                # 提取商品列表
                products_data = self._extract_products_from_api_response(json_data)
                
                # 转换为ProductEntity
                products = []
                for product_data in products_data:
                    try:
                        product = self._convert_api_product_to_entity(product_data)
                        if product:
                            products.append(product)
                    except Exception as e:
                        logger.warning(f"转换API产品数据失败: {e}")
                        continue
                
                logger.info(f"API页面 {page} 爬取完成，获得 {len(products)} 个产品")
                return products
                
            except Exception as e:
                logger.error(f"解析API响应失败: {e}")
                logger.debug(f"响应内容: {response.text[:1000]}...")
                return []
            
        except Exception as e:
            logger.error(f"API搜索请求失败: {e}")
            return []
    
    def _build_api_search_params(self, context: ScrapingContext, page: int) -> Dict[str, Any]:
        """构建API搜索参数 - 返回用于POST请求的JSON数据（使用v2 API结构）"""
        
        # 构建过滤器
        filters = {}
        
        # 关键词
        if context.query.keywords:
            filters['keyword'] = ' '.join(context.query.keywords)
        else:
            filters['keyword'] = ""
        
        # 价格范围
        if hasattr(context.query, 'price_min') and context.query.price_min:
            filters['price_min'] = str(int(context.query.price_min))
        if hasattr(context.query, 'price_max') and context.query.price_max:
            filters['price_max'] = str(int(context.query.price_max))
        
        # 商品状态
        if hasattr(context.query, 'condition') and context.query.condition:
            # 状态映射
            condition_mapping = {
                "新品・未使用": "1",
                "未使用に近い": "2", 
                "目立った傷や汚れなし": "3",
                "やや傷や汚れあり": "4",
                "傷や汚れあり": "5",
                "全体的に状態が悪い": "6"
            }
            if context.query.condition in condition_mapping:
                filters['status'] = condition_mapping[context.query.condition]
        
        # 分类
        if hasattr(context.query, 'category') and context.query.category:
            filters['category_id'] = context.query.category
        
        # 构建分页信息
        paging = {
            "pageSize": min(context.max_products, 10),  # 限制为10个产品
            "pageToken": "",
            "searchSessionId": str(uuid.uuid4()),
            "source": "web_search",
            "withShopname": False,
            "useDynamicAttribute": True,
            "withAuction": False
        }
        
        # 如果是第2页及以后，需要设置pageToken（实际实现中需要从上一页的响应中获取）
        if page > 1:
            # 这里应该使用从上一次API响应中获取的nextPageToken
            # 目前简化处理，实际使用时需要保存和传递pageToken
            paging["pageToken"] = f"page_{page}"
        
        # 使用参数处理器构建请求体
        processor = SearchParameterProcessor()
        request_body = processor.build_v2_request_body(filters, paging)
        
        logger.debug(f"构建的v2 API请求体: {request_body}")
        
        return request_body
    
    def _build_api_headers(self) -> Dict[str, str]:
        """构建API请求头"""
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': self.search_url,
            'Origin': self.base_url
        }
        
        # 添加CSRF Token如果可用
        if self.csrf_token:
            headers['X-CSRF-Token'] = self.csrf_token
            headers['X-CSRF-TOKEN'] = self.csrf_token
        
        return headers
    
    def _build_request_cookies(self) -> Dict[str, str]:
        """构建请求Cookie"""
        return self.session_cookies.copy()
    
    async def _make_api_request(self, url: str, json_data=None, **kwargs) -> Optional[httpx.Response]:
        """发起API请求"""
        await self._apply_rate_limit()
        
        logger.debug(f"开始API请求: {url}")
        logger.debug(f"请求参数: {kwargs}")
        logger.debug(f"JSON数据: {json_data}")
        
        for attempt in range(self.max_retries):
            try:
                self.request_count += 1
                logger.debug(f"尝试 {attempt + 1}/{self.max_retries}: 发起API请求到 {url}")
                
                # 使用POST方法发送JSON数据
                if json_data:
                    response = await self.client.post(url, json=json_data, **kwargs)
                else:
                    response = await self.client.get(url, **kwargs)
                
                logger.debug(f"收到API响应: 状态码 {response.status_code}, 内容长度: {len(response.text)}")
                logger.debug(f"API响应头: {dict(response.headers)}")
                
                if response.status_code == 200:
                    self.success_count += 1
                    logger.debug(f"API请求成功: {url}")
                    return response
                else:
                    logger.warning(f"API请求返回状态码 {response.status_code}: {url}")
                    logger.debug(f"API响应内容预览: {response.text[:500]}...")
                    if response.status_code == 429:  # 请求过于频繁
                        await asyncio.sleep(random.uniform(5, 10))
                    elif response.status_code >= 500:  # 服务器错误，可重试
                        await asyncio.sleep(random.uniform(2, 5))
                    elif response.status_code == 403:  # 可能需要重新初始化Session
                        logger.warning("API返回403，可能需要重新初始化Session")
                        self.session_initialized = False
                        break
                    else:  # 其他错误，不重试
                        break
                        
            except Exception as e:
                logger.error(f"API请求失败 (尝试 {attempt + 1}): {e}")
                logger.debug(f"API请求异常详情: {e}", exc_info=True)
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(random.uniform(1, 3))
        
        self.error_count += 1
        logger.error(f"所有API请求尝试失败: {url}")
        return None
    
    def _extract_products_from_api_response(self, json_data: Dict) -> List[Dict]:
        """从API响应中提取商品数据（v2 API结构）"""
        try:
            # v2 API响应结构可能的路径
            possible_paths = [
                ['items'],  # v2 API通常直接有items字段
                ['data', 'items'],
                ['results', 'items'],
                ['searchResult', 'items'],
                ['entities'],  # entities:search可能使用entities字段
                ['data', 'entities'],
                ['response', 'items']
            ]
            
            products_data = None
            for path in possible_paths:
                current = json_data
                try:
                    for key in path:
                        current = current[key]
                    if isinstance(current, list):
                        products_data = current
                        logger.debug(f"在路径 {path} 找到商品数据")
                        break
                except (KeyError, TypeError):
                    continue
            
            if products_data is None:
                logger.warning("无法在API响应中找到商品数据")
                logger.debug(f"API响应结构: {list(json_data.keys()) if isinstance(json_data, dict) else type(json_data)}")
                
                # 尝试输出完整的响应结构以便调试
                if isinstance(json_data, dict):
                    logger.debug(f"响应字段: {list(json_data.keys())}")
                    for key, value in json_data.items():
                        if isinstance(value, (dict, list)):
                            logger.debug(f"字段 {key} 类型: {type(value)}, 长度/键: {len(value) if hasattr(value, '__len__') else 'N/A'}")
                        else:
                            logger.debug(f"字段 {key}: {value}")
                
                return []
            
            logger.debug(f"从API响应中提取到 {len(products_data)} 个商品")
            return products_data
            
        except Exception as e:
            logger.error(f"提取API商品数据失败: {e}")
            return []
    
    def _convert_api_product_to_entity(self, api_product: Dict) -> Optional[ProductEntity]:
        """将API商品数据转换为ProductEntity"""
        try:
            # API返回的标准字段映射
            product_id = api_product.get('id') or api_product.get('item_id')
            if not product_id:
                return None
            
            # 价格处理
            price = api_product.get('price')
            if isinstance(price, str):
                price = int(price.replace('¥', '').replace(',', '')) if price else 0
            elif not isinstance(price, int):
                price = 0
            
            # 状态映射
            status_mapping = {
                "1": "新品・未使用",
                "2": "未使用に近い",
                "3": "目立った傷や汚れなし", 
                "4": "やや傷や汚れあり",
                "5": "傷や汚れあり",
                "6": "全体的に状態が悪い"
            }
            status_id = str(api_product.get('status', ''))
            condition = status_mapping.get(status_id, "不明")
            
            # 图片URL处理
            images = []
            if 'thumbnails' in api_product and isinstance(api_product['thumbnails'], list):
                images = api_product['thumbnails']
            elif 'thumbnail' in api_product:
                images = [api_product['thumbnail']]
            elif 'image_url' in api_product:
                images = [api_product['image_url']]
            
            return ProductEntity(
                id=str(product_id),
                title=api_product.get('name', ''),
                price=price,
                url=f"https://jp.mercari.com/item/{product_id}",
                description=api_product.get('description', ''),
                condition=condition,
                category=api_product.get('category', {}).get('name', 'その他') if isinstance(api_product.get('category'), dict) else str(api_product.get('category', 'その他')),
                brand=api_product.get('brand', '不明'),
                seller_name=api_product.get('seller', {}).get('name', '不明') if isinstance(api_product.get('seller'), dict) else '不明',
                seller_id=api_product.get('seller_id'),
                seller_rating=api_product.get('seller', {}).get('rating') if isinstance(api_product.get('seller'), dict) else None,
                image_urls=images,
                view_count=api_product.get('num_likes', 0),
                like_count=api_product.get('num_comments', 0),
                shipping_fee=api_product.get('shipping_fee'),
                listed_at=datetime.now(),
                updated_at=datetime.now(),
                sold=api_product.get('status') == 'sold'
            )
            
        except Exception as e:
            logger.error(f"转换API产品数据失败: {e}")
            logger.debug(f"API产品数据: {api_product}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """获取爬虫统计信息"""
        total_requests = self.request_count
        success_rate = self.success_count / total_requests if total_requests > 0 else 0
        
        return {
            "total_requests": total_requests,
            "successful_requests": self.success_count,
            "failed_requests": self.error_count,
            "success_rate": round(success_rate, 3),
            "strategy": "session_api_only",
            "session_initialized": self.session_initialized,
            "has_csrf_token": bool(self.csrf_token),
            "session_cookies_count": len(self.session_cookies),
            "endpoints": {
                "search_api": self.search_api_url,
                "session_init": self.search_url
            }
        }


class ScraperService:
    """
    爬虫服务类
    
    负责从Mercari平台爬取产品数据。
    提供基础的爬取功能和错误处理机制。
    """
    
    def __init__(self, config: AppConfig):
        """
        初始化爬虫服务
        
        Args:
            config: 应用配置
        """
        self.config = config
        self.scraper = None
        self.cache = {}  # 简单的内存缓存
        self.cache_ttl = 300  # 5分钟缓存
        
        logger.info("ScraperService initialized")
    
    async def initialize(self):
        """初始化服务"""
        self.scraper = MercariScraper(self.config)
        await self.scraper.initialize()
        logger.info("ScraperService initialized successfully")
    
    async def close(self):
        """关闭服务"""
        if self.scraper:
            await self.scraper.close()
        logger.info("ScraperService closed")
    
    async def scrape(self, query_or_context, max_products: int = 10) -> ScrapingResult:
        """
        执行爬取任务 - 支持简单调用和复杂调用
        
        Args:
            query_or_context: 查询实体或爬虫上下文
            max_products: 最大产品数量
            
        Returns:
            ScrapingResult: 爬取结果
        """
        # 兼容两种调用方式
        if isinstance(query_or_context, ScrapingContext):
            context = query_or_context
        else:
            # 简单调用，创建默认上下文
            context = ScrapingContext(
                query=query_or_context,
                max_products=max_products,
                max_pages=3
            )
        if not self.scraper:
            await self.initialize()
        
        start_time = time.time()
        
        try:
            # 检查缓存
            cache_key = self._generate_cache_key(context)
            if context.use_cache and cache_key in self.cache:
                cache_entry = self.cache[cache_key]
                if time.time() - cache_entry['timestamp'] < self.cache_ttl:
                    logger.info("使用缓存结果")
                    cached_result = cache_entry['result']
                    cached_result.processing_time = time.time() - start_time
                    return cached_result
            
            # 执行爬取
            products = await self.scraper.search_products(context)
            
            processing_time = time.time() - start_time
            
            result = ScrapingResult(
                products=products,
                total_found=len(products),
                pages_scraped=min(context.max_pages, 5),
                strategy_used=context.strategy,
                processing_time=processing_time,
                metadata={
                    "query": context.query.original_query,
                    "scraper_stats": self.scraper.get_stats() if self.scraper else {}
                }
            )
            
            # 缓存结果
            if context.use_cache:
                self.cache[cache_key] = {
                    'result': result,
                    'timestamp': time.time()
                }
            
            logger.info(f"爬取完成: 找到 {len(products)} 个产品，耗时 {processing_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"爬取失败: {e}")
            raise BaseServiceException(f"爬取失败: {e}", "scraper_service")
    
    def _generate_cache_key(self, context: ScrapingContext) -> str:
        """生成缓存键"""
        key_parts = [
            context.query.original_query,
            str(context.max_pages),
            str(context.max_products),
            context.query.category or "none",
            str(context.query.price_min or 0),
            str(context.query.price_max or 999999)
        ]
        return "scraper:" + ":".join(key_parts)
    
    async def get_product_detail(self, product_url: str) -> Optional[ProductEntity]:
        """获取产品详情"""
        if not self.scraper:
            await self.initialize()
        
        return await self.scraper.get_product_detail(product_url)
    
    def get_service_info(self) -> Dict[str, Any]:
        """获取服务信息"""
        service_info = {
            "service_name": "ScraperService",
            "available_strategies": ["session_api_only"],
            "endpoints": {
                "search_api": "https://api.mercari.jp/v2/entities:search",
                "session_init": "https://jp.mercari.com/search"
            },
            "authentication": {
                "session_cookies": "supported",
                "csrf_token": "supported"
            },
            "cache_size": len(self.cache),
            "scraper_stats": self.scraper.get_stats() if self.scraper else {}
        }
        
        # 添加指纹管理器统计信息
        if self.scraper and hasattr(self.scraper, 'browser_fingerprint_manager') and self.scraper.browser_fingerprint_manager:
            try:
                service_info["fingerprint_stats"] = {
                    "browser_fingerprint": self.scraper.browser_fingerprint_manager.get_fingerprint_stats(),
                    "tls_fingerprint": self.scraper.tls_fingerprint_manager.get_stats() if self.scraper.tls_fingerprint_manager else {},
                    "current_fingerprint": {
                        "browser_type": self.scraper.current_fingerprint.browser_type.value if self.scraper.current_fingerprint else "unknown",
                        "os_type": self.scraper.current_fingerprint.os_type.value if self.scraper.current_fingerprint else "unknown",
                        "usage_count": self.scraper.current_fingerprint.usage_count if self.scraper.current_fingerprint else 0
                    }
                }
            except Exception as e:
                logger.debug(f"获取指纹统计信息失败: {e}")
                service_info["fingerprint_stats"] = {"error": "指纹统计信息获取失败"}
        
        return service_info
    
    async def health_check(self) -> Dict[str, str]:
        """健康检查"""
        try:
            if not self.scraper:
                return {"status": "not_initialized"}
            
            # 检查Session状态
            if not self.scraper.session_initialized:
                try:
                    await self.scraper._initialize_session()
                except Exception as e:
                    return {"status": "unhealthy", "reason": f"Session初始化失败: {e}"}
            
            # 简单的连通性检查
            test_url = "https://jp.mercari.com"
            response = await self.scraper._make_request(test_url)
            
            if response:
                return {
                    "status": "healthy", 
                    "session_initialized": str(self.scraper.session_initialized),
                    "has_csrf_token": str(bool(self.scraper.csrf_token)),
                    "cookies_count": str(len(self.scraper.session_cookies))
                }
            else:
                return {"status": "unhealthy", "reason": "无法连接到Mercari"}
                
        except Exception as e:
            return {"status": "error", "reason": str(e)}
