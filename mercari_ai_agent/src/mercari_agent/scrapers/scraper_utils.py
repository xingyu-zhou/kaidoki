"""
爬虫工具集模块

该模块提供爬虫相关的工具函数和辅助类。
包含HTML处理、文本清理、数据验证等功能。

主要功能：
- HTML选择器工具
- 日语文本处理工具
- 价格和数字解析工具
- URL构建和验证工具
- 数据清洗和验证工具
- 图片处理工具
- 时间处理工具

Author: Mercari AI Agent Team
"""

import re
import logging
import hashlib
import time
from typing import Dict, List, Optional, Any, Tuple, Union
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import random
import unicodedata
import base64
from bs4 import BeautifulSoup, Tag
import requests
from PIL import Image
import io

from ..utils.logger import get_logger
from ..config.settings import settings

logger = get_logger(__name__)


class ImageFormat(Enum):
    """图片格式枚举"""
    JPEG = "jpeg"
    PNG = "png"
    WEBP = "webp"
    GIF = "gif"
    UNKNOWN = "unknown"


@dataclass
class SelectorResult:
    """选择器结果"""
    element: Optional[Tag]
    text: Optional[str]
    exists: bool
    
    def __post_init__(self):
        self.exists = self.element is not None


@dataclass
class ImageInfo:
    """图片信息"""
    url: str
    width: Optional[int] = None
    height: Optional[int] = None
    format: ImageFormat = ImageFormat.UNKNOWN
    size_bytes: Optional[int] = None
    quality_score: float = 0.0
    is_valid: bool = True


class HTMLSelectorTool:
    """HTML选择器工具"""
    
    def __init__(self):
        """初始化选择器工具"""
        self.fallback_selectors = {
            "title": [
                "h1[data-testid='name']",
                "h1.mer-item-name",
                "h1.item-name",
                "h1[class*='title']",
                "h1",
                ".product-title",
                ".item-title"
            ],
            "price": [
                "[data-testid='price']",
                ".mer-item-price",
                ".price",
                ".item-price",
                "[class*='price']",
                ".product-price"
            ],
            "image": [
                "img[data-testid='product-image']",
                "img.mer-item-image",
                "img.product-image",
                "img.item-image",
                "img[src*='mercari']",
                "img[alt*='商品']"
            ],
            "description": [
                "[data-testid='description']",
                ".mer-item-description",
                ".description",
                ".item-description",
                ".product-description",
                "[class*='description']"
            ]
        }
    
    def find_element(self, soup: BeautifulSoup, element_type: str, custom_selectors: Optional[List[str]] = None) -> SelectorResult:
        """
        查找元素
        
        Args:
            soup: BeautifulSoup对象
            element_type: 元素类型
            custom_selectors: 自定义选择器
            
        Returns:
            SelectorResult: 查找结果
        """
        selectors = custom_selectors or self.fallback_selectors.get(element_type, [])
        
        for selector in selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    text = element.get_text(strip=True)
                    return SelectorResult(element=element, text=text, exists=True)
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue
        
        return SelectorResult(element=None, text=None, exists=False)
    
    def find_elements(self, soup: BeautifulSoup, element_type: str, custom_selectors: Optional[List[str]] = None) -> List[SelectorResult]:
        """
        查找多个元素
        
        Args:
            soup: BeautifulSoup对象
            element_type: 元素类型
            custom_selectors: 自定义选择器
            
        Returns:
            List[SelectorResult]: 查找结果列表
        """
        results = []
        selectors = custom_selectors or self.fallback_selectors.get(element_type, [])
        
        for selector in selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text(strip=True)
                    results.append(SelectorResult(element=element, text=text, exists=True))
                
                if results:  # 如果找到了元素，就不继续尝试其他选择器
                    break
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue
        
        return results
    
    def extract_attribute(self, element: Tag, attributes: List[str]) -> Optional[str]:
        """
        提取元素属性
        
        Args:
            element: HTML元素
            attributes: 属性列表
            
        Returns:
            Optional[str]: 属性值
        """
        for attr in attributes:
            value = element.get(attr)
            if value:
                return value
        return None


class JapaneseTextTool:
    """日语文本处理工具"""
    
    def __init__(self):
        """初始化日语文本工具"""
        self.hiragana_pattern = re.compile(r'[\u3041-\u3096]')
        self.katakana_pattern = re.compile(r'[\u30A1-\u30F6]')
        self.kanji_pattern = re.compile(r'[\u4E00-\u9FAF]')
        self.full_width_number_pattern = re.compile(r'[０-９]')
        self.japanese_punctuation_pattern = re.compile(r'[。、！？（）「」『』【】]')
        
        # 全角到半角的映射
        self.full_to_half_map = {
            '０': '0', '１': '1', '２': '2', '３': '3', '４': '4',
            '５': '5', '６': '6', '７': '7', '８': '8', '９': '9',
            '！': '!', '？': '?', '（': '(', '）': ')',
            '「': '"', '」': '"', '『': '"', '』': '"',
            '【': '[', '】': ']', '。': '.', '、': ',',
            '　': ' '  # 全角空格
        }
    
    def normalize_text(self, text: str) -> str:
        """
        标准化日语文本
        
        Args:
            text: 原始文本
            
        Returns:
            str: 标准化后的文本
        """
        if not text:
            return ""
        
        # Unicode标准化
        text = unicodedata.normalize('NFKC', text)
        
        # 转换全角数字和符号为半角
        for full, half in self.full_to_half_map.items():
            text = text.replace(full, half)
        
        # 清理多余的空白
        text = re.sub(r'\s+', ' ', text)
        
        # 移除前后空白
        text = text.strip()
        
        return text
    
    def clean_text(self, text: str) -> str:
        """
        清理文本
        
        Args:
            text: 原始文本
            
        Returns:
            str: 清理后的文本
        """
        if not text:
            return ""
        
        # 标准化
        text = self.normalize_text(text)
        
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        
        # 移除多余的换行和空格
        text = re.sub(r'\n+', '\n', text)
        text = re.sub(r'\s{2,}', ' ', text)
        
        # 移除特殊控制字符
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
        
        return text.strip()
    
    def extract_japanese_text(self, text: str) -> str:
        """
        提取日语文本
        
        Args:
            text: 原始文本
            
        Returns:
            str: 日语文本
        """
        if not text:
            return ""
        
        # 查找日语字符
        japanese_chars = []
        for char in text:
            if (self.hiragana_pattern.match(char) or 
                self.katakana_pattern.match(char) or 
                self.kanji_pattern.match(char) or
                self.japanese_punctuation_pattern.match(char)):
                japanese_chars.append(char)
        
        return ''.join(japanese_chars)
    
    def is_japanese_text(self, text: str) -> bool:
        """
        判断是否为日语文本
        
        Args:
            text: 文本
            
        Returns:
            bool: 是否为日语文本
        """
        if not text:
            return False
        
        japanese_chars = len(self.extract_japanese_text(text))
        total_chars = len(text.replace(' ', ''))
        
        return japanese_chars / total_chars > 0.3 if total_chars > 0 else False


class PriceNumberTool:
    """价格和数字解析工具"""
    
    def __init__(self):
        """初始化价格数字工具"""
        self.price_patterns = [
            r'¥\s*([0-9,]+)',
            r'￥\s*([0-9,]+)',
            r'([0-9,]+)\s*円',
            r'([0-9,]+)\s*yen',
            r'([0-9,]+)'
        ]
        
        self.number_patterns = [
            r'([0-9,]+)',
            r'([０-９，]+)',
            r'(\d+\.?\d*)',
            r'([0-9]+[kK])',  # 1k = 1000
            r'([0-9]+[mM])'   # 1m = 1000000
        ]
    
    def extract_price(self, text: str) -> Optional[float]:
        """
        提取价格
        
        Args:
            text: 包含价格的文本
            
        Returns:
            Optional[float]: 价格
        """
        if not text:
            return None
        
        # 标准化文本
        text = self._normalize_price_text(text)
        
        for pattern in self.price_patterns:
            match = re.search(pattern, text)
            if match:
                price_str = match.group(1)
                price = self._parse_number(price_str)
                if price is not None and price > 0:
                    return price
        
        return None
    
    def extract_number(self, text: str) -> Optional[float]:
        """
        提取数字
        
        Args:
            text: 包含数字的文本
            
        Returns:
            Optional[float]: 数字
        """
        if not text:
            return None
        
        # 标准化文本
        text = self._normalize_price_text(text)
        
        for pattern in self.number_patterns:
            match = re.search(pattern, text)
            if match:
                number_str = match.group(1)
                number = self._parse_number(number_str)
                if number is not None:
                    return number
        
        return None
    
    def _normalize_price_text(self, text: str) -> str:
        """
        标准化价格文本
        
        Args:
            text: 原始文本
            
        Returns:
            str: 标准化后的文本
        """
        # 全角转半角
        text = text.replace('￥', '¥')
        text = text.replace('，', ',')
        
        # 全角数字转半角
        for i in range(10):
            text = text.replace(chr(0xFF10 + i), str(i))
        
        return text
    
    def _parse_number(self, number_str: str) -> Optional[float]:
        """
        解析数字字符串
        
        Args:
            number_str: 数字字符串
            
        Returns:
            Optional[float]: 数字
        """
        if not number_str:
            return None
        
        # 移除逗号
        number_str = number_str.replace(',', '')
        
        # 处理k和m后缀
        if number_str.lower().endswith('k'):
            try:
                return float(number_str[:-1]) * 1000
            except ValueError:
                return None
        elif number_str.lower().endswith('m'):
            try:
                return float(number_str[:-1]) * 1000000
            except ValueError:
                return None
        
        # 解析普通数字
        try:
            return float(number_str)
        except ValueError:
            return None
    
    def format_price(self, price: float, currency: str = "¥") -> str:
        """
        格式化价格
        
        Args:
            price: 价格
            currency: 货币符号
            
        Returns:
            str: 格式化后的价格
        """
        if price is None:
            return "价格未知"
        
        return f"{currency}{price:,.0f}"
    
    def format_number(self, number: float, precision: int = 0) -> str:
        """
        格式化数字
        
        Args:
            number: 数字
            precision: 精度
            
        Returns:
            str: 格式化后的数字
        """
        if number is None:
            return "未知"
        
        if precision == 0:
            return f"{number:,.0f}"
        else:
            return f"{number:,.{precision}f}"


class URLTool:
    """URL构建和验证工具"""
    
    def __init__(self):
        """初始化URL工具"""
        self.mercari_domains = [
            "jp.mercari.com",
            "www.mercari.com",
            "mercari.com"
        ]
        
        self.mercari_patterns = {
            "search": r"/search",
            "item": r"/item/([a-zA-Z0-9]+)",
            "category": r"/category/(\d+)",
            "user": r"/u/(\d+)",
            "brand": r"/brand/(\d+)"
        }
    
    def is_valid_url(self, url: str) -> bool:
        """
        验证URL是否有效
        
        Args:
            url: URL
            
        Returns:
            bool: 是否有效
        """
        if not url:
            return False
        
        try:
            parsed = urlparse(url)
            return bool(parsed.netloc and parsed.scheme in ['http', 'https'])
        except Exception:
            return False
    
    def is_mercari_url(self, url: str) -> bool:
        """
        验证是否为Mercari URL
        
        Args:
            url: URL
            
        Returns:
            bool: 是否为Mercari URL
        """
        if not self.is_valid_url(url):
            return False
        
        try:
            parsed = urlparse(url)
            return parsed.netloc in self.mercari_domains
        except Exception:
            return False
    
    def build_search_url(self, keywords: str, **params) -> str:
        """
        构建搜索URL
        
        Args:
            keywords: 搜索关键词
            **params: 搜索参数
            
        Returns:
            str: 搜索URL
        """
        base_url = "https://jp.mercari.com/search"
        
        query_params = {
            'keyword': keywords
        }
        
        # 添加其他参数
        for key, value in params.items():
            if value is not None:
                query_params[key] = value
        
        return f"{base_url}?{urlencode(query_params)}"
    
    def build_item_url(self, item_id: str) -> str:
        """
        构建商品URL
        
        Args:
            item_id: 商品ID
            
        Returns:
            str: 商品URL
        """
        return f"https://jp.mercari.com/item/{item_id}"
    
    def extract_item_id(self, url: str) -> Optional[str]:
        """
        从URL提取商品ID
        
        Args:
            url: 商品URL
            
        Returns:
            Optional[str]: 商品ID
        """
        match = re.search(self.mercari_patterns["item"], url)
        return match.group(1) if match else None
    
    def extract_user_id(self, url: str) -> Optional[str]:
        """
        从URL提取用户ID
        
        Args:
            url: 用户URL
            
        Returns:
            Optional[str]: 用户ID
        """
        match = re.search(self.mercari_patterns["user"], url)
        return match.group(1) if match else None
    
    def normalize_url(self, url: str, base_url: str = "https://jp.mercari.com") -> str:
        """
        标准化URL
        
        Args:
            url: 原始URL
            base_url: 基础URL
            
        Returns:
            str: 标准化后的URL
        """
        if not url:
            return ""
        
        # 如果是相对URL，转换为绝对URL
        if url.startswith("//"):
            return f"https:{url}"
        elif url.startswith("/"):
            return urljoin(base_url, url)
        elif not url.startswith("http"):
            return urljoin(base_url, url)
        
        return url
    
    def add_url_params(self, url: str, params: Dict[str, Any]) -> str:
        """
        添加URL参数
        
        Args:
            url: 原始URL
            params: 参数字典
            
        Returns:
            str: 带参数的URL
        """
        if not url or not params:
            return url
        
        try:
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            
            for key, value in params.items():
                if value is not None:
                    query_params[key] = [str(value)]
            
            new_query = urlencode(query_params, doseq=True)
            return urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                new_query,
                parsed.fragment
            ))
        except Exception:
            return url


class DataValidationTool:
    """数据验证工具"""
    
    def __init__(self):
        """初始化数据验证工具"""
        self.required_fields = ["title", "url"]
        self.optional_fields = ["price", "description", "condition", "images"]
        
        self.validation_rules = {
            "title": {
                "max_length": 500,
                "min_length": 1,
                "required": True
            },
            "price": {
                "min_value": 0,
                "max_value": 10000000,
                "required": False
            },
            "description": {
                "max_length": 10000,
                "required": False
            },
            "url": {
                "required": True,
                "format": "url"
            },
            "seller_rating": {
                "min_value": 0,
                "max_value": 5,
                "required": False
            }
        }
    
    def validate_product_data(self, product_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        验证产品数据
        
        Args:
            product_data: 产品数据
            
        Returns:
            Tuple[bool, List[str]]: (是否有效, 错误信息列表)
        """
        errors = []
        
        # 检查必需字段
        for field in self.required_fields:
            if field not in product_data or not product_data[field]:
                errors.append(f"Required field '{field}' is missing or empty")
        
        # 验证各字段
        for field, value in product_data.items():
            if field in self.validation_rules:
                field_errors = self._validate_field(field, value)
                errors.extend(field_errors)
        
        return len(errors) == 0, errors
    
    def _validate_field(self, field: str, value: Any) -> List[str]:
        """
        验证单个字段
        
        Args:
            field: 字段名
            value: 字段值
            
        Returns:
            List[str]: 错误信息列表
        """
        errors = []
        rules = self.validation_rules.get(field, {})
        
        if value is None:
            if rules.get("required", False):
                errors.append(f"Field '{field}' is required")
            return errors
        
        # 字符串长度验证
        if isinstance(value, str):
            if "max_length" in rules and len(value) > rules["max_length"]:
                errors.append(f"Field '{field}' is too long (max {rules['max_length']})")
            
            if "min_length" in rules and len(value) < rules["min_length"]:
                errors.append(f"Field '{field}' is too short (min {rules['min_length']})")
        
        # 数值验证
        if isinstance(value, (int, float)):
            if "min_value" in rules and value < rules["min_value"]:
                errors.append(f"Field '{field}' is too small (min {rules['min_value']})")
            
            if "max_value" in rules and value > rules["max_value"]:
                errors.append(f"Field '{field}' is too large (max {rules['max_value']})")
        
        # 格式验证
        if "format" in rules:
            if rules["format"] == "url" and not self._is_valid_url(value):
                errors.append(f"Field '{field}' is not a valid URL")
        
        return errors
    
    def _is_valid_url(self, url: str) -> bool:
        """
        验证URL格式
        
        Args:
            url: URL
            
        Returns:
            bool: 是否有效
        """
        try:
            parsed = urlparse(url)
            return bool(parsed.netloc and parsed.scheme in ['http', 'https'])
        except Exception:
            return False
    
    def clean_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        清洗数据
        
        Args:
            data: 原始数据
            
        Returns:
            Dict[str, Any]: 清洗后的数据
        """
        cleaned = {}
        
        for key, value in data.items():
            if value is not None:
                if isinstance(value, str):
                    # 清理字符串
                    cleaned_value = value.strip()
                    if cleaned_value:
                        cleaned[key] = cleaned_value
                elif isinstance(value, (int, float)):
                    # 清理数值
                    cleaned[key] = value
                elif isinstance(value, list):
                    # 清理列表
                    cleaned_list = [item for item in value if item is not None]
                    if cleaned_list:
                        cleaned[key] = cleaned_list
                else:
                    cleaned[key] = value
        
        return cleaned


class ImageTool:
    """图片处理工具"""
    
    def __init__(self):
        """初始化图片工具"""
        self.supported_formats = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
        self.max_image_size = 10 * 1024 * 1024  # 10MB
    
    def analyze_image_url(self, image_url: str) -> ImageInfo:
        """
        分析图片URL
        
        Args:
            image_url: 图片URL
            
        Returns:
            ImageInfo: 图片信息
        """
        info = ImageInfo(url=image_url)
        
        try:
            # 检查URL格式
            if not image_url or not image_url.startswith(('http://', 'https://')):
                info.is_valid = False
                return info
            
            # 分析文件格式
            info.format = self._detect_format_from_url(image_url)
            
            # 计算质量分数
            info.quality_score = self._calculate_quality_score(image_url)
            
        except Exception as e:
            logger.debug(f"Failed to analyze image URL {image_url}: {e}")
            info.is_valid = False
        
        return info
    
    def _detect_format_from_url(self, url: str) -> ImageFormat:
        """
        从URL检测图片格式
        
        Args:
            url: 图片URL
            
        Returns:
            ImageFormat: 图片格式
        """
        url_lower = url.lower()
        
        if '.jpg' in url_lower or '.jpeg' in url_lower:
            return ImageFormat.JPEG
        elif '.png' in url_lower:
            return ImageFormat.PNG
        elif '.webp' in url_lower:
            return ImageFormat.WEBP
        elif '.gif' in url_lower:
            return ImageFormat.GIF
        else:
            return ImageFormat.UNKNOWN
    
    def _calculate_quality_score(self, url: str) -> float:
        """
        计算图片质量分数
        
        Args:
            url: 图片URL
            
        Returns:
            float: 质量分数 (0-1)
        """
        score = 0.5  # 基础分数
        
        # 基于URL特征评分
        if 'thumb' in url or 'small' in url:
            score -= 0.2
        elif 'large' in url or 'original' in url:
            score += 0.2
        
        # 基于格式评分
        if '.webp' in url:
            score += 0.1
        elif '.jpg' in url or '.jpeg' in url:
            score += 0.05
        
        # 基于域名评分
        if 'mercari' in url:
            score += 0.2
        
        return max(0.0, min(1.0, score))
    
    def filter_valid_images(self, image_urls: List[str]) -> List[str]:
        """
        过滤有效图片
        
        Args:
            image_urls: 图片URL列表
            
        Returns:
            List[str]: 有效图片URL列表
        """
        valid_images = []
        
        for url in image_urls:
            if url and self.analyze_image_url(url).is_valid:
                valid_images.append(url)
        
        return valid_images
    
    def sort_images_by_quality(self, image_urls: List[str]) -> List[str]:
        """
        按质量排序图片
        
        Args:
            image_urls: 图片URL列表
            
        Returns:
            List[str]: 按质量排序的图片URL列表
        """
        image_infos = []
        
        for url in image_urls:
            info = self.analyze_image_url(url)
            if info.is_valid:
                image_infos.append((url, info.quality_score))
        
        # 按质量分数降序排序
        image_infos.sort(key=lambda x: x[1], reverse=True)
        
        return [url for url, _ in image_infos]


class TimeTool:
    """时间处理工具"""
    
    def __init__(self):
        """初始化时间工具"""
        self.date_patterns = [
            (r'(\d{4})/(\d{1,2})/(\d{1,2})', '%Y/%m/%d'),
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', '%Y-%m-%d'),
            (r'(\d{1,2})/(\d{1,2})/(\d{4})', '%m/%d/%Y'),
            (r'(\d{1,2})-(\d{1,2})-(\d{4})', '%m-%d-%Y'),
        ]
        
        self.relative_patterns = [
            (r'(\d+)時間前', lambda x: datetime.now() - timedelta(hours=int(x))),
            (r'(\d+)日前', lambda x: datetime.now() - timedelta(days=int(x))),
            (r'(\d+)週間前', lambda x: datetime.now() - timedelta(weeks=int(x))),
            (r'(\d+)ヶ月前', lambda x: datetime.now() - timedelta(days=int(x)*30)),
            (r'昨日', lambda x: datetime.now() - timedelta(days=1)),
            (r'今日', lambda x: datetime.now()),
        ]
    
    def parse_japanese_date(self, date_text: str) -> Optional[datetime]:
        """
        解析日语日期
        
        Args:
            date_text: 日期文本
            
        Returns:
            Optional[datetime]: 解析后的日期
        """
        if not date_text:
            return None
        
        date_text = date_text.strip()
        
        # 尝试相对时间模式
        for pattern, func in self.relative_patterns:
            match = re.search(pattern, date_text)
            if match:
                try:
                    if pattern in [r'昨日', r'今日']:
                        return func(None)
                    else:
                        return func(match.group(1))
                except Exception:
                    continue
        
        # 尝试绝对时间模式
        for pattern, format_str in self.date_patterns:
            match = re.search(pattern, date_text)
            if match:
                try:
                    return datetime.strptime(match.group(0), format_str)
                except ValueError:
                    continue
        
        return None
    
    def format_relative_time(self, dt: datetime) -> str:
        """
        格式化相对时间
        
        Args:
            dt: 日期时间
            
        Returns:
            str: 相对时间字符串
        """
        if not dt:
            return "不明"
        
        now = datetime.now()
        diff = now - dt
        
        if diff.days > 0:
            return f"{diff.days}日前"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours}時間前"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes}分前"
        else:
            return "たった今"
    
    def is_recent(self, dt: datetime, days: int = 7) -> bool:
        """
        判断是否为最近时间
        
        Args:
            dt: 日期时间
            days: 天数阈值
            
        Returns:
            bool: 是否为最近时间
        """
        if not dt:
            return False
        
        now = datetime.now()
        diff = now - dt
        
        return diff.days <= days


def generate_request_id() -> str:
    """
    生成请求ID
    
    Returns:
        str: 请求ID
    """
    timestamp = str(int(time.time() * 1000))
    random_part = str(random.randint(1000, 9999))
    return f"{timestamp}_{random_part}"


def calculate_hash(text: str) -> str:
    """
    计算文本hash
    
    Args:
        text: 文本
        
    Returns:
        str: Hash值
    """
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def safe_get(dictionary: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    安全获取字典值
    
    Args:
        dictionary: 字典
        key: 键
        default: 默认值
        
    Returns:
        Any: 值
    """
    try:
        return dictionary.get(key, default)
    except (AttributeError, TypeError):
        return default


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    截断文本
    
    Args:
        text: 文本
        max_length: 最大长度
        suffix: 后缀
        
    Returns:
        str: 截断后的文本
    """
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def merge_dicts(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    """
    合并字典
    
    Args:
        *dicts: 字典列表
        
    Returns:
        Dict[str, Any]: 合并后的字典
    """
    result = {}
    for d in dicts:
        if d:
            result.update(d)
    return result


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """
    失败重试装饰器
    
    Args:
        max_retries: 最大重试次数
        delay: 重试延迟
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(f"Function {func.__name__} failed (attempt {attempt + 1}), retrying in {delay}s: {e}")
                        time.sleep(delay)
                    else:
                        logger.error(f"Function {func.__name__} failed after {max_retries} retries: {e}")
            
            raise last_exception
        
        return wrapper
    return decorator