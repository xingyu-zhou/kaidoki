"""
价格规范化工具模块

该模块提供价格处理和规范化功能。
支持多种货币格式的解析和转换。

主要功能：
- 价格字符串解析
- 货币格式规范化
- 价格范围处理
- 汇率转换
- 价格验证

Author: Mercari AI Agent Team
"""

import re
import logging
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal, InvalidOperation

from .logger import get_logger

logger = get_logger(__name__)


class Currency(Enum):
    """货币类型枚举"""
    JPY = "JPY"  # 日元
    USD = "USD"  # 美元
    EUR = "EUR"  # 欧元
    CNY = "CNY"  # 人民币


@dataclass
class PriceInfo:
    """价格信息"""
    amount: Decimal
    currency: Currency
    original_text: str
    is_range: bool = False
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
    confidence: float = 1.0
    metadata: Dict[str, Any] = None


class PriceNormalizer:
    """
    价格规范化器类
    
    负责解析和规范化各种格式的价格信息。
    支持多种货币和价格格式。
    """
    
    def __init__(self):
        """初始化价格规范化器"""
        self.currency_symbols = self._load_currency_symbols()
        self.price_patterns = self._compile_price_patterns()
        self.exchange_rates = self._load_exchange_rates()
        
        logger.info("PriceNormalizer initialized")
    
    async def normalize(self, price_text: str) -> Optional[float]:
        """
        规范化价格文本为数值
        
        Args:
            price_text: 价格文本
            
        Returns:
            Optional[float]: 规范化后的价格数值
        """
        if not price_text:
            return None
        
        try:
            price_info = await self.parse_price(price_text)
            if price_info:
                return float(price_info.amount)
            return None
        except Exception as e:
            logger.error(f"价格规范化失败: {e}")
            return None
    
    async def parse_price(self, price_text: str) -> Optional[PriceInfo]:
        """
        解析价格文本
        
        Args:
            price_text: 价格文本
            
        Returns:
            Optional[PriceInfo]: 解析后的价格信息
        """
        if not price_text or not price_text.strip():
            return None
        
        text = price_text.strip()
        
        try:
            # 1. 尝试解析价格范围
            range_info = await self._parse_price_range(text)
            if range_info:
                return range_info
            
            # 2. 尝试解析单个价格
            single_price = await self._parse_single_price(text)
            if single_price:
                return single_price
            
            # 3. 尝试数字提取
            number_price = await self._extract_number_price(text)
            if number_price:
                return number_price
            
            logger.warning(f"无法解析价格: {text}")
            return None
            
        except Exception as e:
            logger.error(f"价格解析失败: {e}")
            return None
    
    async def _parse_price_range(self, text: str) -> Optional[PriceInfo]:
        """解析价格范围"""
        # 价格范围模式
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
                    return PriceInfo(
                        amount=min_amount,  # 使用最小值作为主要金额
                        currency=Currency.JPY,
                        original_text=text,
                        is_range=True,
                        min_amount=min_amount,
                        max_amount=max_amount,
                        confidence=0.9,
                        metadata={"pattern": pattern}
                    )
        
        return None
    
    async def _parse_single_price(self, text: str) -> Optional[PriceInfo]:
        """解析单个价格"""
        # 单价格模式
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
                    return PriceInfo(
                        amount=amount,
                        currency=Currency.JPY,
                        original_text=text,
                        confidence=0.8,
                        metadata={"pattern": pattern}
                    )
        
        return None
    
    async def _extract_number_price(self, text: str) -> Optional[PriceInfo]:
        """提取数字价格"""
        # 纯数字模式
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
                    return PriceInfo(
                        amount=amount,
                        currency=Currency.JPY,
                        original_text=text,
                        confidence=0.5,
                        metadata={"pattern": pattern, "extracted_number": max_number}
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
    
    async def format_price(self, amount: float, currency: Currency = Currency.JPY) -> str:
        """
        格式化价格显示
        
        Args:
            amount: 金额
            currency: 货币类型
            
        Returns:
            str: 格式化后的价格字符串
        """
        try:
            if currency == Currency.JPY:
                return f"¥{amount:,.0f}"
            elif currency == Currency.USD:
                return f"${amount:,.2f}"
            elif currency == Currency.EUR:
                return f"€{amount:,.2f}"
            elif currency == Currency.CNY:
                return f"¥{amount:,.2f}"
            else:
                return f"{amount:,.2f} {currency.value}"
        except Exception as e:
            logger.error(f"价格格式化失败: {e}")
            return str(amount)
    
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
            return None
    
    async def validate_price(self, price_info: PriceInfo) -> bool:
        """
        验证价格信息
        
        Args:
            price_info: 价格信息
            
        Returns:
            bool: 是否有效
        """
        if not price_info:
            return False
        
        # 检查金额范围
        if price_info.amount <= 0:
            return False
        
        # 检查最大金额限制
        if price_info.amount > 10000000:  # 1000万日元
            return False
        
        # 检查价格范围的合理性
        if price_info.is_range and price_info.min_amount and price_info.max_amount:
            if price_info.min_amount > price_info.max_amount:
                return False
        
        return True
    
    async def compare_prices(self, price1: PriceInfo, price2: PriceInfo) -> Optional[int]:
        """
        比较两个价格
        
        Args:
            price1: 价格1
            price2: 价格2
            
        Returns:
            Optional[int]: -1(价格1更低), 0(相等), 1(价格1更高), None(无法比较)
        """
        if not price1 or not price2:
            return None
        
        try:
            # 转换为相同货币
            amount1 = price1.amount
            amount2 = price2.amount
            
            if price1.currency != price2.currency:
                converted_amount2 = await self.convert_currency(
                    float(amount2), price2.currency, price1.currency
                )
                if converted_amount2:
                    amount2 = Decimal(str(converted_amount2))
                else:
                    return None
            
            # 比较
            if amount1 < amount2:
                return -1
            elif amount1 > amount2:
                return 1
            else:
                return 0
                
        except Exception as e:
            logger.error(f"价格比较失败: {e}")
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
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取价格处理统计"""
        return {
            "supported_currencies": [currency.value for currency in Currency],
            "pattern_count": len(self.price_patterns),
            "exchange_rates_count": len(self.exchange_rates)
        }
    
    def get_info(self) -> Dict[str, Any]:
        """获取规范化器信息"""
        return {
            "version": "1.0.0",
            "supported_currencies": [currency.value for currency in Currency],
            "features": [
                "price_parsing",
                "range_detection",
                "currency_conversion",
                "price_validation",
                "format_normalization"
            ]
        }