"""
产品实体
"""

from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime


@dataclass
class ProductEntity:
    """产品实体"""
    id: str
    title: str
    price: Optional[int] = None
    original_price: Optional[int] = None
    description: Optional[str] = None
    condition: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    seller_name: Optional[str] = None
    seller_id: Optional[str] = None
    seller_rating: Optional[float] = None
    image_urls: List[str] = None
    url: Optional[str] = None
    location: Optional[str] = None
    shipping_fee: Optional[int] = None
    shipping_method: Optional[str] = None
    listed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    sold: bool = False
    
    def __post_init__(self):
        if self.image_urls is None:
            self.image_urls = []
    
    @property
    def formatted_price(self) -> str:
        """格式化价格"""
        if self.price is None:
            return "価格不明"
        return f"¥{self.price:,}"
    
    @property
    def is_available(self) -> bool:
        """是否可用"""
        return not self.sold