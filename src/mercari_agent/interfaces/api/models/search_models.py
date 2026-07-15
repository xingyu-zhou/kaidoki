"""
搜索相关的API数据模型

定义搜索和推荐功能的请求和响应模型。

功能：
- 搜索请求和响应模型
- 推荐请求和响应模型
- 商品响应模型
- 数据验证和序列化

Author: Mercari AI Agent Team (Refactored)
"""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, validator
from enum import Enum
import time

from ....domain.entities.product import Product


class SortBy(str, Enum):
    """排序方式枚举"""
    RELEVANCE = "relevance"
    PRICE_LOW = "price_low"
    PRICE_HIGH = "price_high"
    NEWEST = "newest"
    OLDEST = "oldest"
    POPULARITY = "popularity"


class Condition(str, Enum):
    """商品状态枚举"""
    NEW = "new"
    LIKE_NEW = "like_new"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    ALL = "all"


class RecommendationType(str, Enum):
    """推荐类型枚举"""
    SIMILAR = "similar"
    PERSONALIZED = "personalized"
    POPULAR = "popular"
    TRENDING = "trending"


class Language(str, Enum):
    """语言枚举"""
    JAPANESE = "ja"
    ENGLISH = "en"
    CHINESE = "zh"


class SearchRequest(BaseModel):
    """搜索请求模型"""
    query: str = Field(..., description="搜索关键词", min_length=1, max_length=200)
    min_price: Optional[float] = Field(None, description="最低价格", ge=0)
    max_price: Optional[float] = Field(None, description="最高价格", ge=0)
    condition: Optional[Condition] = Field(Condition.ALL, description="商品状态")
    sort_by: Optional[SortBy] = Field(SortBy.RELEVANCE, description="排序方式")
    limit: Optional[int] = Field(20, description="返回数量限制", ge=1, le=100)
    offset: Optional[int] = Field(0, description="偏移量", ge=0)
    include_recommendations: Optional[bool] = Field(False, description="是否包含推荐")
    language: Optional[Language] = Field(Language.JAPANESE, description="语言")
    
    @validator('max_price')
    def validate_price_range(cls, v, values):
        if v is not None and 'min_price' in values and values['min_price'] is not None:
            if v < values['min_price']:
                raise ValueError('最高价格不能小于最低价格')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "query": "iPhone 13",
                "min_price": 50000,
                "max_price": 100000,
                "condition": "good",
                "sort_by": "price_low",
                "limit": 20,
                "include_recommendations": True,
                "language": "ja"
            }
        }


class ProductResponse(BaseModel):
    """商品响应模型"""
    id: str = Field(..., description="商品ID")
    title: str = Field(..., description="商品标题")
    price: float = Field(..., description="商品价格")
    description: str = Field("", description="商品描述")
    images: List[str] = Field(default_factory=list, description="商品图片URL列表")
    seller: str = Field("", description="卖家信息")
    condition: str = Field("unknown", description="商品状态")
    category: str = Field("", description="商品分类")
    url: str = Field("", description="商品链接")
    location: str = Field("", description="商品位置")
    shipping_cost: float = Field(0, description="运费")
    is_sold: bool = Field(False, description="是否已售出")
    relevance_score: Optional[float] = Field(None, description="相关度分数")
    
    @classmethod
    def from_product(cls, product: Product) -> 'ProductResponse':
        """从Product实体创建响应模型"""
        return cls(
            id=product.id,
            title=product.title,
            price=product.price,
            description=product.description,
            images=product.images,
            seller=product.seller,
            condition=product.condition,
            category=product.category,
            url=product.url,
            location=product.location,
            shipping_cost=product.shipping_cost,
            is_sold=product.is_sold
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProductResponse':
        """从字典创建响应模型"""
        return cls(
            id=data.get('id', ''),
            title=data.get('title', ''),
            price=data.get('price', 0),
            description=data.get('description', ''),
            images=data.get('images', []),
            seller=data.get('seller', ''),
            condition=data.get('condition', 'unknown'),
            category=data.get('category', ''),
            url=data.get('url', ''),
            location=data.get('location', ''),
            shipping_cost=data.get('shipping_cost', 0),
            is_sold=data.get('is_sold', False)
        )
    
    class Config:
        schema_extra = {
            "example": {
                "id": "m12345678",
                "title": "iPhone 13 Pro 128GB ゴールド",
                "price": 89800,
                "description": "iPhone 13 Pro 128GB ゴールド。画面に小さな傷がありますが、動作は正常です。",
                "images": ["https://example.com/image1.jpg", "https://example.com/image2.jpg"],
                "seller": "yamada_shop",
                "condition": "good",
                "category": "スマートフォン",
                "url": "https://mercari.com/jp/items/m12345678",
                "location": "東京都",
                "shipping_cost": 300,
                "is_sold": False,
                "relevance_score": 0.95
            }
        }


class SearchResponse(BaseModel):
    """搜索响应模型"""
    query: str = Field(..., description="搜索关键词")
    total_count: int = Field(..., description="总结果数")
    products: List[ProductResponse] = Field(..., description="商品列表")
    recommendations: List[ProductResponse] = Field(default_factory=list, description="推荐商品")
    search_time: float = Field(..., description="搜索时间戳")
    filters_applied: Dict[str, Any] = Field(default_factory=dict, description="已应用的筛选条件")
    suggestions: List[str] = Field(default_factory=list, description="搜索建议")
    
    class Config:
        schema_extra = {
            "example": {
                "query": "iPhone 13",
                "total_count": 45,
                "products": [],
                "recommendations": [],
                "search_time": 1640995200.0,
                "filters_applied": {
                    "min_price": 50000,
                    "max_price": 100000,
                    "condition": "good"
                },
                "suggestions": ["iPhone 13 Pro", "iPhone 13 mini", "iPhone 12"]
            }
        }


class RecommendationRequest(BaseModel):
    """推荐请求模型"""
    user_id: Optional[str] = Field(None, description="用户ID")
    recommendation_type: RecommendationType = Field(RecommendationType.PERSONALIZED, description="推荐类型")
    query: Optional[str] = Field(None, description="查询关键词")
    preferences: Optional[Dict[str, Any]] = Field(None, description="用户偏好")
    limit: Optional[int] = Field(10, description="返回数量限制", ge=1, le=50)
    exclude_products: Optional[List[str]] = Field(default_factory=list, description="排除的商品ID列表")
    
    class Config:
        schema_extra = {
            "example": {
                "user_id": "user123",
                "recommendation_type": "personalized",
                "query": "スマートフォン",
                "preferences": {
                    "keywords": ["iPhone", "Android"],
                    "category": "スマートフォン",
                    "min_price": 30000,
                    "max_price": 100000
                },
                "limit": 10,
                "exclude_products": ["m12345678"]
            }
        }


class RecommendationResponse(BaseModel):
    """推荐响应模型"""
    user_id: Optional[str] = Field(None, description="用户ID")
    recommendation_type: RecommendationType = Field(..., description="推荐类型")
    products: List[ProductResponse] = Field(..., description="推荐商品列表")
    confidence_scores: List[float] = Field(default_factory=list, description="置信度分数列表")
    generated_at: float = Field(..., description="生成时间戳")
    algorithm_version: str = Field("1.0.0", description="算法版本")
    
    class Config:
        schema_extra = {
            "example": {
                "user_id": "user123",
                "recommendation_type": "personalized",
                "products": [],
                "confidence_scores": [0.95, 0.89, 0.87],
                "generated_at": 1640995200.0,
                "algorithm_version": "2.0.0"
            }
        }


class SearchFilter(BaseModel):
    """搜索筛选器模型"""
    categories: List[str] = Field(default_factory=list, description="分类列表")
    brands: List[str] = Field(default_factory=list, description="品牌列表")
    conditions: List[Condition] = Field(default_factory=list, description="状态列表")
    price_ranges: List[Dict[str, float]] = Field(default_factory=list, description="价格范围列表")
    locations: List[str] = Field(default_factory=list, description="地点列表")
    
    class Config:
        schema_extra = {
            "example": {
                "categories": ["スマートフォン", "タブレット", "パソコン"],
                "brands": ["Apple", "Samsung", "Google"],
                "conditions": ["new", "like_new", "good"],
                "price_ranges": [
                    {"min": 0, "max": 10000},
                    {"min": 10000, "max": 50000},
                    {"min": 50000, "max": 100000}
                ],
                "locations": ["東京都", "大阪府", "神奈川県"]
            }
        }


class SearchHistory(BaseModel):
    """搜索历史模型"""
    user_id: str = Field(..., description="用户ID")
    query: str = Field(..., description="搜索关键词")
    filters: Dict[str, Any] = Field(default_factory=dict, description="筛选条件")
    results_count: int = Field(..., description="结果数量")
    searched_at: float = Field(..., description="搜索时间戳")
    
    class Config:
        schema_extra = {
            "example": {
                "user_id": "user123",
                "query": "iPhone 13",
                "filters": {"min_price": 50000, "condition": "good"},
                "results_count": 45,
                "searched_at": 1640995200.0
            }
        }


class SearchSuggestion(BaseModel):
    """搜索建议模型"""
    query: str = Field(..., description="建议的搜索关键词")
    popularity: float = Field(..., description="热度分数")
    category: Optional[str] = Field(None, description="相关分类")
    
    class Config:
        schema_extra = {
            "example": {
                "query": "iPhone 13 Pro",
                "popularity": 0.95,
                "category": "スマートフォン"
            }
        }