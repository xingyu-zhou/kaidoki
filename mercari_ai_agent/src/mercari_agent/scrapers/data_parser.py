"""
Mercari数据解析器模块

该模块提供专门的Mercari页面数据解析功能。
负责从HTML内容中提取商品信息并转换为结构化数据。

主要功能：
- 商品列表页面解析
- 商品详情页面解析
- 卖家信息提取
- 图片链接处理
- 价格和数字解析
- 日语文本处理
- 数据验证和清洗

Author: Mercari AI Agent Team
"""

import re
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup, Tag
from dataclasses import dataclass
from enum import Enum

from ..models.product import ProductData
from ..utils.logger import get_logger
from ..utils.japanese_processor import JapaneseProcessor
from ..utils.price_normalizer import PriceNormalizer

logger = get_logger(__name__)


class PageType(Enum):
    """页面类型枚举"""
    SEARCH_RESULTS = "search_results"
    PRODUCT_DETAIL = "product_detail"
    SELLER_PROFILE = "seller_profile"
    CATEGORY_PAGE = "category_page"
    UNKNOWN = "unknown"


@dataclass
class ParsingContext:
    """解析上下文"""
    page_type: PageType
    base_url: str
    current_url: str
    user_agent: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class ParsingResult:
    """解析结果"""
    products: List[ProductData]
    total_count: Optional[int] = None
    current_page: int = 1
    has_next_page: bool = False
    next_page_url: Optional[str] = None
    metadata: Dict[str, Any] = None
    errors: List[str] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.errors is None:
            self.errors = []


class MercariDataParser:
    """
    Mercari数据解析器
    
    专门用于解析Mercari页面的数据提取器。
    支持多种页面类型和数据格式。
    """
    
    def __init__(self):
        """初始化数据解析器"""
        self.japanese_processor = JapaneseProcessor()
        self.price_normalizer = PriceNormalizer()
        
        # Mercari页面选择器映射
        self.selectors = {
            # 搜索结果页面
            "search_results": {
                "item_container": ".mer-item-thumbnail, [data-testid='item-cell']",
                "item_link": "a[href*='/item/']",
                "item_title": "[data-testid='name'], .mer-item-name",
                "item_price": "[data-testid='price'], .mer-item-price",
                "item_image": "img[src*='mercari'], img[data-src*='mercari']",
                "item_condition": "[data-testid='item-condition'], .mer-item-condition",
                "item_sold": "[data-testid='sold-out'], .mer-item-sold-out",
                "pagination_next": "a[data-testid='pagination-next'], .mer-pagination-next",
                "total_count": "[data-testid='search-result-count'], .mer-search-result-count"
            },
            
            # 商品详情页面
            "product_detail": {
                "title": "h1[data-testid='name'], .mer-item-name",
                "price": "[data-testid='price'], .mer-item-price",
                "condition": "[data-testid='item-condition'], .mer-item-condition",
                "description": "[data-testid='description'], .mer-item-description",
                "category": "[data-testid='breadcrumb'] a, .mer-breadcrumb a",
                "brand": "[data-testid='brand'], .mer-item-brand",
                "size": "[data-testid='size'], .mer-item-size",
                "color": "[data-testid='color'], .mer-item-color",
                "material": "[data-testid='material'], .mer-item-material",
                "seller_name": "[data-testid='seller-name'], .mer-seller-name",
                "seller_rating": "[data-testid='seller-rating'], .mer-seller-rating",
                "seller_review_count": "[data-testid='seller-review-count'], .mer-seller-review-count",
                "view_count": "[data-testid='view-count'], .mer-view-count",
                "like_count": "[data-testid='like-count'], .mer-like-count",
                "comment_count": "[data-testid='comment-count'], .mer-comment-count",
                "images": "img[data-testid='product-image'], .mer-item-image img",
                "specifications": "[data-testid='item-detail-table'] tr, .mer-item-detail-table tr",
                "shipping_cost": "[data-testid='shipping-cost'], .mer-shipping-cost",
                "shipping_method": "[data-testid='shipping-method'], .mer-shipping-method",
                "created_at": "[data-testid='created-at'], .mer-created-at",
                "updated_at": "[data-testid='updated-at'], .mer-updated-at"
            }
        }
        
        # 正则表达式模式
        self.patterns = {
            "price": r'[\d,]+',
            "rating": r'(\d+\.?\d*)',
            "count": r'(\d+)',
            "item_id": r'/item/([a-zA-Z0-9]+)',
            "seller_id": r'/u/(\d+)',
            "category_id": r'/category/(\d+)',
            "japanese_numbers": r'[０-９]+',
            "size_pattern": r'(XS|S|M|L|XL|XXL|XXXL|\d+cm|\d+号)',
            "color_pattern": r'(赤|青|黄|緑|黒|白|灰|茶|紫|橙|ピンク|ベージュ|ネイビー|カーキ|ワイン)'
        }
        
        logger.info("MercariDataParser initialized")
    
    def parse_page(self, html_content: str, context: ParsingContext) -> ParsingResult:
        """
        解析页面内容
        
        Args:
            html_content: HTML内容
            context: 解析上下文
            
        Returns:
            ParsingResult: 解析结果
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 检测页面类型
            if context.page_type == PageType.UNKNOWN:
                context.page_type = self._detect_page_type(soup, context.current_url)
            
            # 根据页面类型选择解析方法
            if context.page_type == PageType.SEARCH_RESULTS:
                return self._parse_search_results(soup, context)
            elif context.page_type == PageType.PRODUCT_DETAIL:
                return self._parse_product_detail(soup, context)
            else:
                logger.warning(f"Unsupported page type: {context.page_type}")
                return ParsingResult(products=[], errors=[f"Unsupported page type: {context.page_type}"])
        
        except Exception as e:
            logger.error(f"Failed to parse page: {e}")
            return ParsingResult(products=[], errors=[f"Parsing failed: {str(e)}"])
    
    def _detect_page_type(self, soup: BeautifulSoup, url: str) -> PageType:
        """
        检测页面类型
        
        Args:
            soup: BeautifulSoup对象
            url: 页面URL
            
        Returns:
            PageType: 页面类型
        """
        # 通过URL模式检测
        if '/search' in url or '/category' in url:
            return PageType.SEARCH_RESULTS
        elif '/item/' in url:
            return PageType.PRODUCT_DETAIL
        elif '/u/' in url:
            return PageType.SELLER_PROFILE
        
        # 通过页面元素检测
        if soup.select(self.selectors["search_results"]["item_container"]):
            return PageType.SEARCH_RESULTS
        elif soup.select(self.selectors["product_detail"]["title"]):
            return PageType.PRODUCT_DETAIL
        
        return PageType.UNKNOWN
    
    def _parse_search_results(self, soup: BeautifulSoup, context: ParsingContext) -> ParsingResult:
        """
        解析搜索结果页面
        
        Args:
            soup: BeautifulSoup对象
            context: 解析上下文
            
        Returns:
            ParsingResult: 解析结果
        """
        products = []
        errors = []
        
        # 查找商品容器
        item_containers = soup.select(self.selectors["search_results"]["item_container"])
        
        if not item_containers:
            errors.append("No product containers found")
            return ParsingResult(products=[], errors=errors)
        
        # 解析每个商品
        for container in item_containers:
            try:
                product = self._parse_search_item(container, context)
                if product:
                    products.append(product)
            except Exception as e:
                errors.append(f"Failed to parse item: {str(e)}")
                logger.warning(f"Failed to parse search item: {e}")
        
        # 获取分页信息
        has_next_page = bool(soup.select(self.selectors["search_results"]["pagination_next"]))
        next_page_url = None
        
        if has_next_page:
            next_link = soup.select_one(self.selectors["search_results"]["pagination_next"])
            if next_link:
                next_page_url = urljoin(context.base_url, next_link.get("href", ""))
        
        # 获取总数
        total_count = self._extract_total_count(soup)
        
        # 获取当前页码
        current_page = self._extract_current_page(context.current_url)
        
        return ParsingResult(
            products=products,
            total_count=total_count,
            current_page=current_page,
            has_next_page=has_next_page,
            next_page_url=next_page_url,
            metadata={
                "page_type": context.page_type.value if hasattr(context.page_type, 'value') else str(context.page_type),
                "items_found": len(products),
                "containers_found": len(item_containers)
            },
            errors=errors
        )
    
    def _parse_search_item(self, container: Tag, context: ParsingContext) -> Optional[ProductData]:
        """
        解析搜索结果中的单个商品
        
        Args:
            container: 商品容器元素
            context: 解析上下文
            
        Returns:
            Optional[ProductData]: 商品数据
        """
        try:
            # 提取链接
            link_elem = container.select_one(self.selectors["search_results"]["item_link"])
            if not link_elem:
                link_elem = container.select_one("a[href*='/item/']")
            
            if not link_elem:
                return None
            
            url = urljoin(context.base_url, link_elem.get("href", ""))
            item_id = self._extract_item_id(url)
            
            # 提取标题
            title_elem = container.select_one(self.selectors["search_results"]["item_title"])
            if not title_elem:
                title_elem = container.select_one("h3, .item-name, [data-testid*='name']")
            
            title = self._extract_text(title_elem) if title_elem else None
            
            if not title:
                return None
            
            # 提取价格
            price_elem = container.select_one(self.selectors["search_results"]["item_price"])
            if not price_elem:
                price_elem = container.select_one("[data-testid*='price'], .price, .item-price")
            
            price = self._extract_price(price_elem) if price_elem else None
            
            # 提取图片
            image_elem = container.select_one(self.selectors["search_results"]["item_image"])
            if not image_elem:
                image_elem = container.select_one("img")
            
            images = []
            if image_elem:
                image_url = self._extract_image_url(image_elem)
                if image_url:
                    images.append(self._normalize_image_url(image_url, context.base_url))
            
            # 提取状态
            condition_elem = container.select_one(self.selectors["search_results"]["item_condition"])
            condition = self._extract_text(condition_elem) if condition_elem else None
            
            # 检查是否已售出
            sold_elem = container.select_one(self.selectors["search_results"]["item_sold"])
            is_sold = bool(sold_elem)
            
            # 创建产品数据
            product_data = ProductData(
                title=title,
                price=price,
                url=url,
                condition=condition,
                images=images,
                is_sold=is_sold,
                source="mercari",
                source_id=item_id,
                scraped_at=context.timestamp
            )
            
            return product_data
            
        except Exception as e:
            logger.warning(f"Failed to parse search item: {e}")
            return None
    
    def _parse_product_detail(self, soup: BeautifulSoup, context: ParsingContext) -> ParsingResult:
        """
        解析商品详情页面
        
        Args:
            soup: BeautifulSoup对象
            context: 解析上下文
            
        Returns:
            ParsingResult: 解析结果
        """
        try:
            product = self._parse_detailed_product(soup, context)
            
            if product:
                return ParsingResult(
                    products=[product],
                    metadata={
                        "page_type": context.page_type.value if hasattr(context.page_type, 'value') else str(context.page_type),
                        "detailed_parsing": True
                    }
                )
            else:
                return ParsingResult(
                    products=[],
                    errors=["Failed to parse product detail"]
                )
                
        except Exception as e:
            logger.error(f"Failed to parse product detail: {e}")
            return ParsingResult(
                products=[],
                errors=[f"Product detail parsing failed: {str(e)}"]
            )
    
    def _parse_detailed_product(self, soup: BeautifulSoup, context: ParsingContext) -> Optional[ProductData]:
        """
        解析详细商品信息
        
        Args:
            soup: BeautifulSoup对象
            context: 解析上下文
            
        Returns:
            Optional[ProductData]: 详细商品数据
        """
        try:
            selectors = self.selectors["product_detail"]
            
            # 基础信息
            title_elem = soup.select_one(selectors["title"])
            title = self._extract_text(title_elem) if title_elem else None
            
            if not title:
                return None
            
            # 价格
            price_elem = soup.select_one(selectors["price"])
            price = self._extract_price(price_elem) if price_elem else None
            
            # 描述
            description_elem = soup.select_one(selectors["description"])
            description = self._extract_text(description_elem) if description_elem else None
            
            # 状态
            condition_elem = soup.select_one(selectors["condition"])
            condition = self._extract_text(condition_elem) if condition_elem else None
            
            # 分类
            category_elems = soup.select(selectors["category"])
            category = " > ".join([self._extract_text(elem) for elem in category_elems]) if category_elems else None
            
            # 品牌
            brand_elem = soup.select_one(selectors["brand"])
            brand = self._extract_text(brand_elem) if brand_elem else None
            
            # 尺寸
            size_elem = soup.select_one(selectors["size"])
            size = self._extract_text(size_elem) if size_elem else None
            
            # 颜色
            color_elem = soup.select_one(selectors["color"])
            color = self._extract_text(color_elem) if color_elem else None
            
            # 材质
            material_elem = soup.select_one(selectors["material"])
            material = self._extract_text(material_elem) if material_elem else None
            
            # 图片
            image_elems = soup.select(selectors["images"])
            images = []
            for img_elem in image_elems:
                image_url = self._extract_image_url(img_elem)
                if image_url:
                    images.append(self._normalize_image_url(image_url, context.base_url))
            
            # 卖家信息
            seller_name_elem = soup.select_one(selectors["seller_name"])
            seller_name = self._extract_text(seller_name_elem) if seller_name_elem else None
            
            seller_rating_elem = soup.select_one(selectors["seller_rating"])
            seller_rating = self._extract_rating(seller_rating_elem) if seller_rating_elem else None
            
            seller_review_count_elem = soup.select_one(selectors["seller_review_count"])
            seller_review_count = self._extract_count(seller_review_count_elem) if seller_review_count_elem else None
            
            # 交互统计
            view_count_elem = soup.select_one(selectors["view_count"])
            view_count = self._extract_count(view_count_elem) if view_count_elem else None
            
            like_count_elem = soup.select_one(selectors["like_count"])
            like_count = self._extract_count(like_count_elem) if like_count_elem else None
            
            comment_count_elem = soup.select_one(selectors["comment_count"])
            comment_count = self._extract_count(comment_count_elem) if comment_count_elem else None
            
            # 规格信息
            specifications = self._extract_specifications(soup, selectors["specifications"])
            
            # 配送信息
            shipping_cost_elem = soup.select_one(selectors["shipping_cost"])
            shipping_cost = self._extract_price(shipping_cost_elem) if shipping_cost_elem else None
            
            shipping_method_elem = soup.select_one(selectors["shipping_method"])
            shipping_method = self._extract_text(shipping_method_elem) if shipping_method_elem else None
            
            # 时间信息
            created_at_elem = soup.select_one(selectors["created_at"])
            created_at = self._extract_datetime(created_at_elem) if created_at_elem else None
            
            updated_at_elem = soup.select_one(selectors["updated_at"])
            updated_at = self._extract_datetime(updated_at_elem) if updated_at_elem else None
            
            # 提取商品ID
            item_id = self._extract_item_id(context.current_url)
            
            # 创建产品数据
            product_data = ProductData(
                title=title,
                price=price,
                url=context.current_url,
                description=description,
                condition=condition,
                category=category,
                brand=brand,
                size=size,
                color=color,
                material=material,
                images=images,
                seller_name=seller_name,
                seller_rating=seller_rating,
                seller_review_count=seller_review_count,
                view_count=view_count,
                like_count=like_count,
                comment_count=comment_count,
                shipping_cost=shipping_cost,
                shipping_method=shipping_method,
                created_at=created_at,
                updated_at=updated_at,
                scraped_at=context.timestamp,
                source="mercari",
                source_id=item_id,
                specifications=specifications
            )
            
            return product_data
            
        except Exception as e:
            logger.error(f"Failed to parse detailed product: {e}")
            return None
    
    def _extract_text(self, element: Optional[Tag]) -> Optional[str]:
        """
        提取元素文本
        
        Args:
            element: HTML元素
            
        Returns:
            Optional[str]: 提取的文本
        """
        if not element:
            return None
        
        text = element.get_text(strip=True)
        if not text:
            return None
        
        # 日语文本处理
        text = self.japanese_processor.normalize_text(text)
        
        return text if text else None
    
    def _extract_price(self, element: Optional[Tag]) -> Optional[float]:
        """
        提取价格
        
        Args:
            element: 价格元素
            
        Returns:
            Optional[float]: 价格
        """
        if not element:
            return None
        
        text = element.get_text(strip=True)
        if not text:
            return None
        
        # 使用简单的价格提取逻辑，避免async调用
        try:
            # 移除货币符号和空格
            import re
            clean_text = re.sub(r'[¥￥円yen$€]', '', text, flags=re.IGNORECASE)
            clean_text = re.sub(r'\s+', '', clean_text)
            
            # 处理千位分隔符
            clean_text = clean_text.replace(',', '')
            
            # 提取数字
            match = re.search(r'(\d+(?:\.\d+)?)', clean_text)
            if match:
                return float(match.group(1))
            
            return None
        except (ValueError, AttributeError):
            return None
    
    def _extract_rating(self, element: Optional[Tag]) -> Optional[float]:
        """
        提取评分
        
        Args:
            element: 评分元素
            
        Returns:
            Optional[float]: 评分
        """
        if not element:
            return None
        
        text = element.get_text(strip=True)
        if not text:
            return None
        
        # 查找评分模式
        rating_match = re.search(self.patterns["rating"], text)
        if rating_match:
            try:
                rating = float(rating_match.group(1))
                return rating if 0 <= rating <= 5 else None
            except ValueError:
                return None
        
        return None
    
    def _extract_count(self, element: Optional[Tag]) -> Optional[int]:
        """
        提取计数
        
        Args:
            element: 计数元素
            
        Returns:
            Optional[int]: 计数
        """
        if not element:
            return None
        
        text = element.get_text(strip=True)
        if not text:
            return None
        
        # 移除逗号和其他格式符号
        text = re.sub(r'[,\s]', '', text)
        
        # 查找数字
        count_match = re.search(self.patterns["count"], text)
        if count_match:
            try:
                return int(count_match.group(1))
            except ValueError:
                return None
        
        return None
    
    def _extract_image_url(self, element: Tag) -> Optional[str]:
        """
        提取图片URL
        
        Args:
            element: 图片元素
            
        Returns:
            Optional[str]: 图片URL
        """
        if not element:
            return None
        
        # 尝试多种属性
        for attr in ["src", "data-src", "data-lazy-src", "data-original"]:
            url = element.get(attr)
            if url and url.startswith(("http", "//")):
                return url
        
        return None
    
    def _normalize_image_url(self, image_url: str, base_url: str) -> str:
        """
        标准化图片URL
        
        Args:
            image_url: 原始图片URL
            base_url: 基础URL
            
        Returns:
            str: 标准化后的URL
        """
        if not image_url:
            return ""
        
        # 如果是相对URL，转换为绝对URL
        if image_url.startswith("//"):
            return f"https:{image_url}"
        elif image_url.startswith("/"):
            return urljoin(base_url, image_url)
        
        return image_url
    
    def _extract_item_id(self, url: str) -> Optional[str]:
        """
        从URL中提取商品ID
        
        Args:
            url: 商品URL
            
        Returns:
            Optional[str]: 商品ID
        """
        match = re.search(self.patterns["item_id"], url)
        return match.group(1) if match else None
    
    def _extract_specifications(self, soup: BeautifulSoup, selector: str) -> Dict[str, str]:
        """
        提取规格信息
        
        Args:
            soup: BeautifulSoup对象
            selector: 规格表选择器
            
        Returns:
            Dict[str, str]: 规格信息
        """
        specifications = {}
        
        try:
            spec_rows = soup.select(selector)
            
            for row in spec_rows:
                cells = row.select("td, th")
                if len(cells) >= 2:
                    key = self._extract_text(cells[0])
                    value = self._extract_text(cells[1])
                    
                    if key and value:
                        specifications[key] = value
        
        except Exception as e:
            logger.warning(f"Failed to extract specifications: {e}")
        
        return specifications
    
    def _extract_datetime(self, element: Optional[Tag]) -> Optional[datetime]:
        """
        提取日期时间
        
        Args:
            element: 日期时间元素
            
        Returns:
            Optional[datetime]: 日期时间
        """
        if not element:
            return None
        
        text = element.get_text(strip=True)
        if not text:
            return None
        
        # 尝试解析日期时间
        try:
            # 日本时间格式
            if re.match(r'\d{4}/\d{2}/\d{2}', text):
                return datetime.strptime(text[:10], '%Y/%m/%d')
            elif re.match(r'\d{4}-\d{2}-\d{2}', text):
                return datetime.strptime(text[:10], '%Y-%m-%d')
        except ValueError:
            pass
        
        return None
    
    def _extract_total_count(self, soup: BeautifulSoup) -> Optional[int]:
        """
        提取总结果数
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            Optional[int]: 总结果数
        """
        count_elem = soup.select_one(self.selectors["search_results"]["total_count"])
        if count_elem:
            return self._extract_count(count_elem)
        
        # 尝试从页面中查找其他计数信息
        for pattern in [r'(\d+)\s*件', r'(\d+)\s*個', r'(\d+)\s*results']:
            match = re.search(pattern, soup.get_text())
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
        
        return None
    
    def _extract_current_page(self, url: str) -> int:
        """
        从URL提取当前页码
        
        Args:
            url: 当前页面URL
            
        Returns:
            int: 页码
        """
        match = re.search(r'page=(\d+)', url)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        
        return 1
    
    def validate_product_data(self, product_data: ProductData) -> Tuple[bool, List[str]]:
        """
        验证产品数据
        
        Args:
            product_data: 产品数据
            
        Returns:
            Tuple[bool, List[str]]: (是否有效, 错误信息列表)
        """
        errors = []
        
        # 必需字段检查
        if not product_data.title:
            errors.append("Title is required")
        
        if not product_data.url:
            errors.append("URL is required")
        
        # 价格验证
        if product_data.price is not None and product_data.price < 0:
            errors.append("Price cannot be negative")
        
        # 卖家评分验证
        if product_data.seller_rating is not None and not (0 <= product_data.seller_rating <= 5):
            errors.append("Seller rating must be between 0 and 5")
        
        # 图片URL验证
        for image_url in product_data.images:
            if image_url and not image_url.startswith(("http://", "https://")):
                errors.append(f"Invalid image URL: {image_url}")
        
        # 文本长度验证
        if product_data.title and len(product_data.title) > 500:
            errors.append("Title is too long")
        
        if product_data.description and len(product_data.description) > 10000:
            errors.append("Description is too long")
        
        return len(errors) == 0, errors
    
    def clean_product_data(self, product_data: ProductData) -> ProductData:
        """
        清洗产品数据
        
        Args:
            product_data: 原始产品数据
            
        Returns:
            ProductData: 清洗后的产品数据
        """
        # 文本清理
        if product_data.title:
            product_data.title = self.japanese_processor.clean_text(product_data.title)
        
        if product_data.description:
            product_data.description = self.japanese_processor.clean_text(product_data.description)
        
        # 价格标准化
        if product_data.price is not None:
            product_data.price = round(product_data.price, 2)
        
        # 移除重复图片
        if product_data.images:
            product_data.images = list(dict.fromkeys(product_data.images))
        
        # 标准化卖家评分
        if product_data.seller_rating is not None:
            product_data.seller_rating = round(product_data.seller_rating, 1)
        
        # 添加处理时间戳
        product_data.scraped_at = datetime.now()
        
        return product_data
    
    def get_parser_stats(self) -> Dict[str, Any]:
        """
        获取解析器统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        return {
            "supported_page_types": [page_type.value if hasattr(page_type, 'value') else str(page_type) for page_type in PageType],
            "selector_count": sum(len(selectors) for selectors in self.selectors.values()),
            "pattern_count": len(self.patterns),
            "japanese_processor_enabled": self.japanese_processor is not None,
            "price_normalizer_enabled": self.price_normalizer is not None
        }