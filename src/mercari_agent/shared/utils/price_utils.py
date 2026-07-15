"""
价格处理工具模块

提供价格解析、规范化和转换功能。
与领域模型中的价格值对象集成，提供实用的价格处理方法。

Author: Mercari AI Agent Team
"""

import re
import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from ..exceptions import (
    PriceParsingError,
    PriceNormalizationError,
    CurrencyConversionError,
    ValidationError
)
from ...domain.value_objects.price import Price, PriceRange, Currency

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class PriceParseResult:
    """价格解析结果"""
    price: Optional[Price] = None
    is_range: bool = False
    min_price: Optional[Price] = None
    max_price: Optional[Price] = None
    confidence: float = 1.0
    original_text: str = ""
    extraction_method: str = ""


class PriceParser:
    """
    价格解析器
    
    负责从文本中解析价格信息，支持多种格式和货币。
    """
    
    def __init__(self):
        """初始化价格解析器"""
        self.currency_symbols = self._load_currency_symbols()
        self.price_patterns = self._compile_price_patterns()
        
        logger.info("PriceParser initialized")
    
    async def parse_price_text(self, text: str) -> Optional[PriceParseResult]:
        """
        解析价格文本
        
        Args:
            text: 价格文本
            
        Returns:
            PriceParseResult: 解析结果
        """
        if not text or not text.strip():
            return None
        
        text = text.strip()
        
        try:
            # 1. 尝试解析价格范围
            range_result = await self._parse_price_range(text)
            if range_result:
                return range_result
            
            # 2. 尝试解析单个价格
            single_result = await self._parse_single_price(text)
            if single_result:
                return single_result
            
            # 3. 尝试数字提取
            number_result = await self._extract_number_price(text)
            if number_result:
                return number_result
            
            logger.warning(f"无法解析价格: {text}")
            return None
            
        except Exception as e:
            logger.error(f"价格解析失败: {e}")
            raise PriceParsingError(
                f"价格解析失败: {str(e)}",
                price_text=text
            ) from e
    
    async def normalize_price(self, price_text: str) -> Optional[float]:
        """
        规范化价格文本为数值
        
        Args:
            price_text: 价格文本
            
        Returns:
            Optional[float]: 规范化后的价格数值
        """
        try:
            result = await self.parse_price_text(price_text)
            if result and result.price:
                return result.price.to_float()
            return None
        except Exception as e:
            logger.error(f"价格规范化失败: {e}")
            raise PriceNormalizationError(
                f"价格规范化失败: {str(e)}",
                original_price=price_text
            ) from e
    
    async def _parse_price_range(self, text: str) -> Optional[PriceParseResult]:
        """解析价格范围"""
        range_patterns = [
            r'([¥￥]?\s*\d+(?:,\d{3})*)\s*[～〜-]\s*([¥￥]?\s*\d+(?:,\d{3})*)',
            r'(\d+(?:,\d{3})*)\s*[～〜-]\s*(\d+(?:,\d{3})*)\s*円',
            r'([¥￥]?\s*\d+(?:,\d{3})*)\s*から\s*([¥￥]?\s*\d+(?:,\d{3})*)',
            r'(\d+(?:,\d{3})*)\s*から\s*(\d+(?:,\d{3})*)\s*円'
        ]
        
        for pattern in range_patterns:
            match = re.search(pattern, text)
            if match:
                min_text = match.group(1)
                max_text = match.group(2)
                
                min_amount = await self._extract_amount(min_text)
                max_amount = await self._extract_amount(max_text)
                
                if min_amount and max_amount:
                    min_price = Price(min_amount, Currency.JPY)
                    max_price = Price(max_amount, Currency.JPY)
                    
                    return PriceParseResult(
                        price=min_price,  # 使用最小值作为主要价格
                        is_range=True,
                        min_price=min_price,
                        max_price=max_price,
                        confidence=0.9,
                        original_text=text,
                        extraction_method="range_pattern"
                    )
        
        return None
    
    async def _parse_single_price(self, text: str) -> Optional[PriceParseResult]:
        """解析单个价格"""
        single_patterns = [
            r'([¥￥])\s*(\d+(?:,\d{3})*)',
            r'(\d+(?:,\d{3})*)\s*円',
            r'(\d+(?:,\d{3})*)\s*yen',
            r'(\d+(?:,\d{3})*)\s*JPY'
        ]
        
        for pattern in single_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if len(match.groups()) == 2:
                    amount_text = match.group(2)
                else:
                    amount_text = match.group(1)
                
                amount = await self._extract_amount(amount_text)
                if amount:
                    price = Price(amount, Currency.JPY)
                    return PriceParseResult(
                        price=price,
                        confidence=0.8,
                        original_text=text,
                        extraction_method="single_pattern"
                    )
        
        return None
    
    async def _extract_number_price(self, text: str) -> Optional[PriceParseResult]:
        """提取数字价格"""
        number_patterns = [
            r'\b(\d+(?:,\d{3})*)\b',
            r'\b(\d+)\b'
        ]
        
        for pattern in number_patterns:
            matches = re.findall(pattern, text)
            if matches:
                # 选择最大的数字作为价格
                max_number = max(matches, key=lambda x: int(x.replace(',', '')))
                amount = await self._extract_amount(max_number)
                
                if amount and amount > 10:  # 过滤掉太小的数字
                    price = Price(amount, Currency.JPY)
                    return PriceParseResult(
                        price=price,
                        confidence=0.5,
                        original_text=text,
                        extraction_method="number_extraction"
                    )
        
        return None
    
    async def _extract_amount(self, amount_text: str) -> Optional[Decimal]:
        """提取金额数值 - 修复日语数字单位处理"""
        if not amount_text:
            return None
        
        try:
            # 清理文本
            clean_text = amount_text.strip()
            
            # 处理日语数字单位
            # 1. 处理万単位 (1万 = 10,000)
            man_pattern = r'(\d+)万'
            man_match = re.search(man_pattern, clean_text)
            if man_match:
                base_number = int(man_match.group(1))
                amount = Decimal(base_number * 10000)
                
                # 验证合理性
                if amount < 0 or amount > 10000000:  # 1000万日元上限
                    return None
                
                return amount
            
            # 2. 处理千単位 (1千 = 1,000)
            sen_pattern = r'(\d+)千'
            sen_match = re.search(sen_pattern, clean_text)
            if sen_match:
                base_number = int(sen_match.group(1))
                amount = Decimal(base_number * 1000)
                
                # 验证合理性
                if amount < 0 or amount > 10000000:  # 1000万日元上限
                    return None
                
                return amount
            
            # 3. 处理普通数字
            # 移除货币符号
            clean_text = re.sub(r'[¥￥円yen]', '', clean_text, flags=re.IGNORECASE)
            
            # 移除空格
            clean_text = re.sub(r'\s+', '', clean_text)
            
            # 处理千位分隔符
            clean_text = clean_text.replace(',', '')
            
            # 转换为数字
            amount = Decimal(clean_text)
            
            # 验证合理性
            if amount < 0 or amount > 10000000:  # 1000万日元上限
                return None
            
            return amount
            
        except (ValueError, InvalidOperation):
            return None
    
    def _load_currency_symbols(self) -> Dict[str, Currency]:
        """加载货币符号映射"""
        return {
            '¥': Currency.JPY,
            '￥': Currency.JPY,
            '円': Currency.JPY,
            'yen': Currency.JPY,
            'jpy': Currency.JPY,
            '$': Currency.USD,
            'usd': Currency.USD,
            '€': Currency.EUR,
            'eur': Currency.EUR,
            '元': Currency.CNY,
            'cny': Currency.CNY
        }
    
    def _compile_price_patterns(self) -> List[re.Pattern]:
        """编译价格正则表达式"""
        patterns = [
            # 日元格式
            r'[¥￥]\s*(\d+(?:,\d{3})*)',
            r'(\d+(?:,\d{3})*)\s*円',
            r'(\d+(?:,\d{3})*)\s*yen',
            
            # 美元格式
            r'\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*USD',
            
            # 欧元格式
            r'€\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*EUR',
            
            # 人民币格式
            r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*元',
            r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*CNY'
        ]
        
        return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]


class PriceFormatter:
    """
    价格格式化器
    
    负责将价格对象格式化为不同的显示格式。
    """
    
    @staticmethod
    def format_price(price: Price, include_currency: bool = True) -> str:
        """
        格式化价格显示
        
        Args:
            price: 价格对象
            include_currency: 是否包含货币符号
            
        Returns:
            str: 格式化后的价格字符串
        """
        if not price:
            return "价格未设定"
        
        try:
            if include_currency:
                return price.format()
            else:
                return f"{price.amount:,.0f}" if price.currency == Currency.JPY else f"{price.amount:,.2f}"
        except Exception as e:
            logger.error(f"价格格式化失败: {e}")
            return str(price.amount)
    
    @staticmethod
    def format_price_range(price_range: PriceRange) -> str:
        """
        格式化价格范围显示
        
        Args:
            price_range: 价格范围对象
            
        Returns:
            str: 格式化后的价格范围字符串
        """
        if not price_range:
            return "价格范围未设定"
        
        return price_range.get_formatted_range()
    
    @staticmethod
    def format_price_with_trend(current_price: Price, previous_price: Optional[Price] = None) -> str:
        """
        格式化价格并显示趋势
        
        Args:
            current_price: 当前价格
            previous_price: 之前价格
            
        Returns:
            str: 包含趋势的价格字符串
        """
        price_str = PriceFormatter.format_price(current_price)
        
        if previous_price:
            try:
                comparison = current_price.compare(previous_price)
                if comparison > 0:
                    return f"{price_str} ↑"
                elif comparison < 0:
                    return f"{price_str} ↓"
                else:
                    return f"{price_str} →"
            except Exception:
                pass
        
        return price_str


class CurrencyConverter:
    """
    货币转换器
    
    负责不同货币之间的转换。
    """
    
    def __init__(self):
        """初始化货币转换器"""
        self.exchange_rates = self._load_exchange_rates()
    
    async def convert_currency(
        self,
        amount: float,
        from_currency: Currency,
        to_currency: Currency
    ) -> Optional[float]:
        """
        货币转换
        
        Args:
            amount: 金额
            from_currency: 源货币
            to_currency: 目标货币
            
        Returns:
            Optional[float]: 转换后的金额
        """
        if from_currency == to_currency:
            return amount
        
        try:
            # 获取汇率
            rate = self.exchange_rates.get(f"{from_currency.value}_{to_currency.value}")
            if rate:
                return amount * rate
            
            # 尝试反向汇率
            reverse_rate = self.exchange_rates.get(f"{to_currency.value}_{from_currency.value}")
            if reverse_rate:
                return amount / reverse_rate
            
            logger.warning(f"无法获取汇率: {from_currency.value} -> {to_currency.value}")
            return None
            
        except Exception as e:
            logger.error(f"货币转换失败: {e}")
            raise CurrencyConversionError(
                f"货币转换失败: {str(e)}",
                from_currency=from_currency.value,
                to_currency=to_currency.value,
                amount=amount
            ) from e
    
    async def convert_price(
        self,
        price: Price,
        to_currency: Currency
    ) -> Optional[Price]:
        """
        价格货币转换
        
        Args:
            price: 源价格
            to_currency: 目标货币
            
        Returns:
            Optional[Price]: 转换后的价格
        """
        if price.currency == to_currency:
            return price
        
        converted_amount = await self.convert_currency(
            price.to_float(),
            price.currency,
            to_currency
        )
        
        if converted_amount is not None:
            return Price.from_float(converted_amount, to_currency)
        
        return None
    
    def _load_exchange_rates(self) -> Dict[str, float]:
        """加载汇率数据"""
        # 这里应该从实时API获取汇率，暂时使用静态数据
        return {
            'USD_JPY': 150.0,
            'EUR_JPY': 165.0,
            'CNY_JPY': 20.0,
            'JPY_USD': 0.0067,
            'JPY_EUR': 0.0061,
            'JPY_CNY': 0.05
        }


class PriceValidator:
    """
    价格验证器
    
    负责验证价格的有效性和合理性。
    """
    
    @staticmethod
    def validate_price(price: Price) -> bool:
        """
        验证价格
        
        Args:
            price: 价格对象
            
        Returns:
            bool: 是否有效
        """
        if not price:
            return False
        
        try:
            # 检查金额范围
            if price.amount <= 0:
                return False
            
            # 检查最大金额限制
            if price.amount > Decimal('10000000'):  # 1000万日元
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"价格验证失败: {e}")
            return False
    
    @staticmethod
    def validate_price_range(price_range: PriceRange) -> bool:
        """
        验证价格范围
        
        Args:
            price_range: 价格范围对象
            
        Returns:
            bool: 是否有效
        """
        if not price_range:
            return False
        
        try:
            # 检查基本有效性
            if not price_range.is_valid():
                return False
            
            # 检查单个价格的有效性
            if price_range.min_price and not PriceValidator.validate_price(price_range.min_price):
                return False
            
            if price_range.max_price and not PriceValidator.validate_price(price_range.max_price):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"价格范围验证失败: {e}")
            return False
    
    @staticmethod
    def is_reasonable_price(price: Price, category: str = None) -> bool:
        """
        检查价格是否合理
        
        Args:
            price: 价格对象
            category: 商品类别
            
        Returns:
            bool: 是否合理
        """
        if not PriceValidator.validate_price(price):
            return False
        
        # 基于类别的价格合理性检查
        if category:
            reasonable_ranges = {
                'electronics': (1000, 500000),
                'fashion': (100, 100000),
                'home': (500, 200000),
                'books': (100, 5000),
                'toys': (100, 20000),
            }
            
            if category.lower() in reasonable_ranges:
                min_price, max_price = reasonable_ranges[category.lower()]
                amount = price.to_float()
                return min_price <= amount <= max_price
        
        # 通用合理性检查
        amount = price.to_float()
        return 10 <= amount <= 1000000  # 10日元到100万日元


# 便利函数
async def parse_price(text: str) -> Optional[Price]:
    """
    解析价格文本为价格对象
    
    Args:
        text: 价格文本
        
    Returns:
        Optional[Price]: 价格对象
    """
    parser = PriceParser()
    result = await parser.parse_price_text(text)
    return result.price if result else None


async def normalize_price(text: str) -> Optional[float]:
    """
    规范化价格文本为数值
    
    Args:
        text: 价格文本
        
    Returns:
        Optional[float]: 价格数值
    """
    parser = PriceParser()
    return await parser.normalize_price(text)


def format_price(price: Price) -> str:
    """
    格式化价格显示
    
    Args:
        price: 价格对象
        
    Returns:
        str: 格式化后的价格字符串
    """
    return PriceFormatter.format_price(price)


def validate_price(price: Price) -> bool:
    """
    验证价格有效性
    
    Args:
        price: 价格对象
        
    Returns:
        bool: 是否有效
    """
    return PriceValidator.validate_price(price)


# 默认实例
default_parser = PriceParser()
default_formatter = PriceFormatter()
default_converter = CurrencyConverter()
default_validator = PriceValidator()