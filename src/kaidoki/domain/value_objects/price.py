"""
价格值对象

定义价格相关的值对象，包含价格信息、价格范围、价格历史等。

Author: Kaidoki Team
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from decimal import Decimal
from enum import Enum

from ...shared.exceptions import (
    PriceRangeError,
    PriceParsingError,
    CurrencyConversionError,
    ValidationError
)


class Currency(Enum):
    """货币类型枚举"""
    JPY = "JPY"  # 日元
    USD = "USD"  # 美元
    EUR = "EUR"  # 欧元
    CNY = "CNY"  # 人民币


@dataclass(frozen=True)
class Price:
    """价格值对象"""
    amount: Decimal
    currency: Currency = Currency.JPY
    
    def __post_init__(self):
        """后初始化验证"""
        if self.amount < 0:
            raise ValidationError(
                "价格不能为负数",
                field="amount",
                value=self.amount
            )
        
        if self.amount > Decimal('10000000'):  # 1000万日元上限
            raise ValidationError(
                "价格超出合理范围",
                field="amount", 
                value=self.amount
            )
    
    @classmethod
    def from_float(cls, amount: float, currency: Currency = Currency.JPY) -> Price:
        """从浮点数创建价格"""
        return cls(Decimal(str(amount)), currency)
    
    @classmethod
    def from_string(cls, amount_str: str, currency: Currency = Currency.JPY) -> Price:
        """从字符串创建价格"""
        try:
            return cls(Decimal(amount_str), currency)
        except Exception as e:
            raise PriceParsingError(
                f"无法解析价格字符串: {amount_str}",
                price_text=amount_str
            ) from e
    
    def to_float(self) -> float:
        """转换为浮点数"""
        return float(self.amount)
    
    def format(self) -> str:
        """格式化价格显示"""
        if self.currency == Currency.JPY:
            return f"¥{self.amount:,.0f}"
        elif self.currency == Currency.USD:
            return f"${self.amount:,.2f}"
        elif self.currency == Currency.EUR:
            return f"€{self.amount:,.2f}"
        elif self.currency == Currency.CNY:
            return f"¥{self.amount:,.2f}"
        else:
            return f"{self.amount:,.2f} {self.currency.value}"
    
    def convert_to(self, target_currency: Currency, exchange_rate: Decimal) -> Price:
        """转换货币"""
        if self.currency == target_currency:
            return self
        
        converted_amount = self.amount * exchange_rate
        return Price(converted_amount, target_currency)
    
    def add(self, other: Price) -> Price:
        """价格相加"""
        if self.currency != other.currency:
            raise CurrencyConversionError(
                "不能直接相加不同货币的价格",
                from_currency=self.currency.value,
                to_currency=other.currency.value
            )
        
        return Price(self.amount + other.amount, self.currency)
    
    def multiply(self, factor: Decimal) -> Price:
        """价格乘法"""
        return Price(self.amount * factor, self.currency)
    
    def compare(self, other: Price) -> int:
        """比较价格"""
        if self.currency != other.currency:
            raise CurrencyConversionError(
                "不能直接比较不同货币的价格",
                from_currency=self.currency.value,
                to_currency=other.currency.value
            )
        
        if self.amount < other.amount:
            return -1
        elif self.amount > other.amount:
            return 1
        else:
            return 0
    
    def __lt__(self, other: Price) -> bool:
        return self.compare(other) < 0
    
    def __le__(self, other: Price) -> bool:
        return self.compare(other) <= 0
    
    def __gt__(self, other: Price) -> bool:
        return self.compare(other) > 0
    
    def __ge__(self, other: Price) -> bool:
        return self.compare(other) >= 0
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Price):
            return False
        return self.amount == other.amount and self.currency == other.currency


@dataclass(frozen=True)
class PriceRange:
    """价格范围值对象"""
    min_price: Optional[Price] = None
    max_price: Optional[Price] = None
    
    def __post_init__(self):
        """后初始化验证"""
        if self.min_price and self.max_price:
            if self.min_price.currency != self.max_price.currency:
                raise PriceRangeError(
                    "价格范围的最小和最大价格必须使用相同货币",
                    min_price=self.min_price.to_float(),
                    max_price=self.max_price.to_float()
                )
            
            if self.min_price > self.max_price:
                raise PriceRangeError(
                    "最低价格不能大于最高价格",
                    min_price=self.min_price.to_float(),
                    max_price=self.max_price.to_float()
                )
    
    @classmethod
    def from_floats(
        cls,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        currency: Currency = Currency.JPY
    ) -> PriceRange:
        """从浮点数创建价格范围"""
        min_p = Price.from_float(min_price, currency) if min_price is not None else None
        max_p = Price.from_float(max_price, currency) if max_price is not None else None
        return cls(min_p, max_p)
    
    def is_valid(self) -> bool:
        """检查价格范围是否有效"""
        return self.min_price is not None or self.max_price is not None
    
    def contains_price(self, price: Price) -> bool:
        """检查价格是否在范围内"""
        if self.min_price and price < self.min_price:
            return False
        if self.max_price and price > self.max_price:
            return False
        return True
    
    def get_formatted_range(self) -> str:
        """获取格式化的价格范围"""
        if not self.is_valid():
            return "无价格限制"
        elif self.min_price is None:
            return f"≤ {self.max_price.format()}"
        elif self.max_price is None:
            return f"≥ {self.min_price.format()}"
        else:
            return f"{self.min_price.format()} - {self.max_price.format()}"
    
    def intersect(self, other: PriceRange) -> Optional[PriceRange]:
        """与另一个价格范围求交集"""
        if not self.is_valid() or not other.is_valid():
            return None
        
        # 计算交集的最小价格
        new_min = None
        if self.min_price and other.min_price:
            new_min = max(self.min_price, other.min_price)
        elif self.min_price:
            new_min = self.min_price
        elif other.min_price:
            new_min = other.min_price
        
        # 计算交集的最大价格
        new_max = None
        if self.max_price and other.max_price:
            new_max = min(self.max_price, other.max_price)
        elif self.max_price:
            new_max = self.max_price
        elif other.max_price:
            new_max = other.max_price
        
        # 检查交集是否有效
        if new_min and new_max and new_min > new_max:
            return None
        
        return PriceRange(new_min, new_max)


@dataclass
class PriceHistory:
    """价格历史值对象"""
    product_id: str
    records: List[Tuple[datetime, Price]] = field(default_factory=list)
    
    def add_price_record(self, price: Price, timestamp: Optional[datetime] = None):
        """添加价格记录"""
        if timestamp is None:
            timestamp = datetime.now()
        
        self.records.append((timestamp, price))
        # 按时间排序
        self.records.sort(key=lambda x: x[0])
    
    def get_current_price(self) -> Optional[Price]:
        """获取当前价格"""
        if not self.records:
            return None
        return self.records[-1][1]
    
    def get_price_at_date(self, date: datetime) -> Optional[Price]:
        """获取指定日期的价格"""
        for timestamp, price in reversed(self.records):
            if timestamp <= date:
                return price
        return None
    
    def get_price_trend(self) -> str:
        """获取价格趋势"""
        if len(self.records) < 2:
            return "无变化"
        
        current_price = self.records[-1][1]
        previous_price = self.records[-2][1]
        
        try:
            if current_price > previous_price:
                return "上涨"
            elif current_price < previous_price:
                return "下跌"
            else:
                return "无变化"
        except CurrencyConversionError:
            return "无法比较"
    
    def get_average_price(self) -> Optional[Price]:
        """获取平均价格"""
        if not self.records:
            return None
        
        # 确保所有价格使用相同货币
        currency = self.records[0][1].currency
        total = Decimal('0')
        
        for _, price in self.records:
            if price.currency != currency:
                raise CurrencyConversionError(
                    "价格历史包含不同货币，无法计算平均值",
                    from_currency=price.currency.value,
                    to_currency=currency.value
                )
            total += price.amount
        
        average_amount = total / len(self.records)
        return Price(average_amount, currency)
    
    def get_price_range(self) -> Optional[PriceRange]:
        """获取价格历史中的价格范围"""
        if not self.records:
            return None
        
        prices = [record[1] for record in self.records]
        min_price = min(prices)
        max_price = max(prices)
        
        return PriceRange(min_price, max_price)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "product_id": self.product_id,
            "records": [
                {
                    "timestamp": timestamp.isoformat(),
                    "amount": float(price.amount),
                    "currency": price.currency.value
                }
                for timestamp, price in self.records
            ]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PriceHistory:
        """从字典创建"""
        history = cls(product_id=data["product_id"])
        
        for record_data in data.get("records", []):
            timestamp = datetime.fromisoformat(record_data["timestamp"])
            price = Price(
                Decimal(str(record_data["amount"])),
                Currency(record_data["currency"])
            )
            history.records.append((timestamp, price))
        
        return history