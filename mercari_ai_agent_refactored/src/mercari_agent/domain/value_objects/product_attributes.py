"""
商品属性值对象

定义商品相关的值对象，包含商品图片、条件、元数据等。

Author: Mercari AI Agent Team
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set
from datetime import datetime
from enum import Enum
from urllib.parse import urlparse

from ...shared.exceptions import (
    ProductImageError,
    ProductConditionError,
    ValidationError
)


class ProductStatus(Enum):
    """产品状态枚举"""
    ACTIVE = "active"           # 在售
    SOLD = "sold"              # 已售出
    SUSPENDED = "suspended"     # 暂停销售
    EXPIRED = "expired"        # 已过期
    DELETED = "deleted"        # 已删除


class ProductCategory(Enum):
    """产品类别枚举"""
    ELECTRONICS = "electronics"      # 电子产品
    FASHION = "fashion"              # 时装
    HOME = "home"                    # 家居
    BEAUTY = "beauty"                # 美容
    SPORTS = "sports"                # 运动
    BOOKS = "books"                  # 书籍
    TOYS = "toys"                    # 玩具
    AUTOMOTIVE = "automotive"        # 汽车
    MUSIC = "music"                  # 音乐
    GAMES = "games"                  # 游戏
    HEALTH = "health"                # 健康
    FOOD = "food"                    # 食品
    PETS = "pets"                    # 宠物
    CRAFTS = "crafts"                # 手工艺品
    OTHERS = "others"                # 其他


class ProductCondition(Enum):
    """产品状态枚举"""
    NEW = "新品・未使用"
    LIKE_NEW = "未使用に近い"
    GOOD = "目立った傷や汚れなし"
    FAIR = "やや傷や汚れあり"
    POOR = "傷や汚れあり"
    BAD = "全体的に状態が悪い"


@dataclass(frozen=True)
class ProductImage:
    """产品图片值对象"""
    url: str
    width: Optional[int] = None
    height: Optional[int] = None
    is_primary: bool = False
    alt_text: Optional[str] = None
    file_size: Optional[int] = None
    format: Optional[str] = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        """后初始化验证"""
        # URL验证
        if not self.url:
            raise ProductImageError("图片URL不能为空", image_url=self.url)
        
        parsed_url = urlparse(self.url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ProductImageError("无效的图片URL格式", image_url=self.url)
        
        # 尺寸验证
        if self.width is not None and self.width <= 0:
            raise ValidationError("图片宽度必须大于0", field="width", value=self.width)
        
        if self.height is not None and self.height <= 0:
            raise ValidationError("图片高度必须大于0", field="height", value=self.height)
        
        # 文件大小验证
        if self.file_size is not None and self.file_size < 0:
            raise ValidationError("文件大小不能为负数", field="file_size", value=self.file_size)
        
        # 设置默认创建时间
        if self.created_at is None:
            object.__setattr__(self, 'created_at', datetime.now())
    
    @classmethod
    def create_primary(
        cls, 
        url: str, 
        alt_text: Optional[str] = None, 
        **kwargs
    ) -> ProductImage:
        """创建主图片"""
        return cls(url=url, is_primary=True, alt_text=alt_text, **kwargs)
    
    @classmethod
    def create_additional(
        cls, 
        url: str, 
        alt_text: Optional[str] = None, 
        **kwargs
    ) -> ProductImage:
        """创建附加图片"""
        return cls(url=url, is_primary=False, alt_text=alt_text, **kwargs)
    
    def with_dimensions(self, width: int, height: int) -> ProductImage:
        """添加尺寸信息"""
        return dataclass.replace(self, width=width, height=height)
    
    def with_file_info(self, file_size: int, format: str) -> ProductImage:
        """添加文件信息"""
        return dataclass.replace(self, file_size=file_size, format=format)
    
    def get_aspect_ratio(self) -> Optional[float]:
        """获取宽高比"""
        if self.width and self.height:
            return self.width / self.height
        return None
    
    def is_landscape(self) -> bool:
        """是否为横向图片"""
        ratio = self.get_aspect_ratio()
        return ratio is not None and ratio > 1.0
    
    def is_portrait(self) -> bool:
        """是否为纵向图片"""
        ratio = self.get_aspect_ratio()
        return ratio is not None and ratio < 1.0
    
    def is_square(self) -> bool:
        """是否为方形图片"""
        ratio = self.get_aspect_ratio()
        return ratio is not None and abs(ratio - 1.0) < 0.1
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "url": self.url,
            "width": self.width,
            "height": self.height,
            "is_primary": self.is_primary,
            "alt_text": self.alt_text,
            "file_size": self.file_size,
            "format": self.format,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProductImage:
        """从字典创建"""
        created_at = None
        if data.get("created_at"):
            created_at = datetime.fromisoformat(data["created_at"])
        
        return cls(
            url=data["url"],
            width=data.get("width"),
            height=data.get("height"),
            is_primary=data.get("is_primary", False),
            alt_text=data.get("alt_text"),
            file_size=data.get("file_size"),
            format=data.get("format"),
            created_at=created_at
        )


@dataclass(frozen=True)
class ProductImages:
    """产品图片集合值对象"""
    images: List[ProductImage] = field(default_factory=list)
    
    def __post_init__(self):
        """后初始化验证"""
        # 检查是否有重复URL
        urls = [img.url for img in self.images]
        if len(urls) != len(set(urls)):
            raise ProductImageError("存在重复的图片URL", error_type="duplicate_url")
        
        # 检查主图片数量
        primary_count = sum(1 for img in self.images if img.is_primary)
        if primary_count > 1:
            raise ProductImageError("只能有一张主图片", error_type="multiple_primary")
    
    @classmethod
    def create_with_primary(cls, primary_url: str, additional_urls: List[str] = None) -> ProductImages:
        """创建包含主图的图片集合"""
        images = [ProductImage.create_primary(primary_url)]
        
        if additional_urls:
            for url in additional_urls:
                images.append(ProductImage.create_additional(url))
        
        return cls(images)
    
    def get_primary_image(self) -> Optional[ProductImage]:
        """获取主图片"""
        for image in self.images:
            if image.is_primary:
                return image
        return self.images[0] if self.images else None
    
    def get_additional_images(self) -> List[ProductImage]:
        """获取附加图片"""
        return [img for img in self.images if not img.is_primary]
    
    def get_all_urls(self) -> List[str]:
        """获取所有图片URL"""
        return [img.url for img in self.images]
    
    def count(self) -> int:
        """获取图片数量"""
        return len(self.images)
    
    def has_images(self) -> bool:
        """是否有图片"""
        return len(self.images) > 0
    
    def add_image(self, image: ProductImage) -> ProductImages:
        """添加图片"""
        if image.url in self.get_all_urls():
            raise ProductImageError("图片URL已存在", image_url=image.url)
        
        new_images = list(self.images)
        new_images.append(image)
        return ProductImages(new_images)
    
    def remove_image(self, url: str) -> ProductImages:
        """移除图片"""
        new_images = [img for img in self.images if img.url != url]
        if len(new_images) == len(self.images):
            raise ProductImageError("图片不存在", image_url=url)
        
        return ProductImages(new_images)
    
    def set_primary_image(self, url: str) -> ProductImages:
        """设置主图片"""
        new_images = []
        found = False
        
        for img in self.images:
            if img.url == url:
                new_images.append(dataclass.replace(img, is_primary=True))
                found = True
            else:
                new_images.append(dataclass.replace(img, is_primary=False))
        
        if not found:
            raise ProductImageError("指定的图片不存在", image_url=url)
        
        return ProductImages(new_images)


@dataclass(frozen=True)
class ProductMetadata:
    """产品元数据值对象"""
    scraped_at: datetime
    source: str
    source_id: str
    last_updated: Optional[datetime] = None
    data_quality: Optional[float] = None
    confidence_score: Optional[float] = None
    tags: Set[str] = field(default_factory=set)
    
    def __post_init__(self):
        """后初始化验证"""
        # 验证数据质量分数
        if self.data_quality is not None and not (0 <= self.data_quality <= 1):
            raise ValidationError(
                "数据质量分数必须在0-1之间", 
                field="data_quality", 
                value=self.data_quality
            )
        
        # 验证置信度分数
        if self.confidence_score is not None and not (0 <= self.confidence_score <= 1):
            raise ValidationError(
                "置信度分数必须在0-1之间", 
                field="confidence_score", 
                value=self.confidence_score
            )
        
        # 验证来源信息
        if not self.source or not self.source.strip():
            raise ValidationError("数据来源不能为空", field="source", value=self.source)
        
        if not self.source_id or not self.source_id.strip():
            raise ValidationError("来源ID不能为空", field="source_id", value=self.source_id)
    
    @classmethod
    def create_mercari(cls, product_id: str, **kwargs) -> ProductMetadata:
        """创建Mercari来源的元数据"""
        return cls(
            scraped_at=datetime.now(),
            source="mercari",
            source_id=product_id,
            **kwargs
        )
    
    def with_quality_score(self, quality: float, confidence: float) -> ProductMetadata:
        """设置质量和置信度分数"""
        return dataclass.replace(
            self, 
            data_quality=quality, 
            confidence_score=confidence
        )
    
    def add_tag(self, tag: str) -> ProductMetadata:
        """添加标签"""
        new_tags = set(self.tags)
        new_tags.add(tag.lower().strip())
        return dataclass.replace(self, tags=new_tags)
    
    def remove_tag(self, tag: str) -> ProductMetadata:
        """移除标签"""
        new_tags = set(self.tags)
        new_tags.discard(tag.lower().strip())
        return dataclass.replace(self, tags=new_tags)
    
    def has_tag(self, tag: str) -> bool:
        """检查是否有标签"""
        return tag.lower().strip() in self.tags
    
    def is_high_quality(self) -> bool:
        """是否高质量数据"""
        return (self.data_quality is not None and self.data_quality >= 0.8 and
                self.confidence_score is not None and self.confidence_score >= 0.8)
    
    def update_timestamp(self) -> ProductMetadata:
        """更新时间戳"""
        return dataclass.replace(self, last_updated=datetime.now())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "scraped_at": self.scraped_at.isoformat(),
            "source": self.source,
            "source_id": self.source_id,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "data_quality": self.data_quality,
            "confidence_score": self.confidence_score,
            "tags": list(self.tags)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProductMetadata:
        """从字典创建"""
        scraped_at = datetime.fromisoformat(data["scraped_at"])
        last_updated = None
        if data.get("last_updated"):
            last_updated = datetime.fromisoformat(data["last_updated"])
        
        return cls(
            scraped_at=scraped_at,
            source=data["source"],
            source_id=data["source_id"],
            last_updated=last_updated,
            data_quality=data.get("data_quality"),
            confidence_score=data.get("confidence_score"),
            tags=set(data.get("tags", []))
        )


@dataclass(frozen=True)
class SellerInfo:
    """卖家信息值对象"""
    seller_id: str
    seller_name: str
    seller_rating: Optional[float] = None
    review_count: Optional[int] = None
    verified: bool = False
    join_date: Optional[datetime] = None
    response_rate: Optional[float] = None
    shipping_speed: Optional[float] = None
    
    def __post_init__(self):
        """后初始化验证"""
        # 验证卖家ID
        if not self.seller_id or not self.seller_id.strip():
            raise ValidationError("卖家ID不能为空", field="seller_id", value=self.seller_id)
        
        # 验证卖家名称
        if not self.seller_name or not self.seller_name.strip():
            raise ValidationError("卖家名称不能为空", field="seller_name", value=self.seller_name)
        
        # 验证评分范围
        if self.seller_rating is not None and not (0 <= self.seller_rating <= 5):
            raise ValidationError(
                "卖家评分必须在0-5之间", 
                field="seller_rating", 
                value=self.seller_rating
            )
        
        # 验证评价数量
        if self.review_count is not None and self.review_count < 0:
            raise ValidationError(
                "评价数量不能为负数", 
                field="review_count", 
                value=self.review_count
            )
        
        # 验证响应率
        if self.response_rate is not None and not (0 <= self.response_rate <= 1):
            raise ValidationError(
                "响应率必须在0-1之间", 
                field="response_rate", 
                value=self.response_rate
            )
        
        # 验证发货速度评分
        if self.shipping_speed is not None and not (0 <= self.shipping_speed <= 5):
            raise ValidationError(
                "发货速度评分必须在0-5之间", 
                field="shipping_speed", 
                value=self.shipping_speed
            )
    
    def is_verified_seller(self) -> bool:
        """是否为认证卖家"""
        return self.verified
    
    def has_good_rating(self, threshold: float = 4.0) -> bool:
        """是否有良好评分"""
        return self.seller_rating is not None and self.seller_rating >= threshold
    
    def has_sufficient_reviews(self, min_count: int = 10) -> bool:
        """是否有足够的评价"""
        return self.review_count is not None and self.review_count >= min_count
    
    def is_responsive_seller(self, min_rate: float = 0.9) -> bool:
        """是否为响应及时的卖家"""
        return self.response_rate is not None and self.response_rate >= min_rate
    
    def is_reliable_seller(self) -> bool:
        """是否为可靠卖家"""
        return (self.has_good_rating() and 
                self.has_sufficient_reviews() and 
                self.is_responsive_seller())
    
    def get_trust_score(self) -> float:
        """获取信任评分"""
        score = 0.0
        
        if self.verified:
            score += 0.2
        
        if self.seller_rating is not None:
            score += (self.seller_rating / 5.0) * 0.3
        
        if self.response_rate is not None:
            score += self.response_rate * 0.2
        
        if self.shipping_speed is not None:
            score += (self.shipping_speed / 5.0) * 0.2
        
        if self.has_sufficient_reviews():
            score += 0.1
        
        return min(score, 1.0)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "seller_id": self.seller_id,
            "seller_name": self.seller_name,
            "seller_rating": self.seller_rating,
            "review_count": self.review_count,
            "verified": self.verified,
            "join_date": self.join_date.isoformat() if self.join_date else None,
            "response_rate": self.response_rate,
            "shipping_speed": self.shipping_speed
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SellerInfo:
        """从字典创建"""
        join_date = None
        if data.get("join_date"):
            join_date = datetime.fromisoformat(data["join_date"])
        
        return cls(
            seller_id=data["seller_id"],
            seller_name=data["seller_name"],
            seller_rating=data.get("seller_rating"),
            review_count=data.get("review_count"),
            verified=data.get("verified", False),
            join_date=join_date,
            response_rate=data.get("response_rate"),
            shipping_speed=data.get("shipping_speed")
        )