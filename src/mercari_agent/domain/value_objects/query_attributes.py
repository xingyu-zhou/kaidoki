"""
查询属性值对象

定义查询相关的值对象，包含查询意图、查询类型、搜索条件等。

Author: Mercari AI Agent Team
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set
from datetime import datetime
from enum import Enum

from ...shared.exceptions import (
    InvalidQueryError,
    QueryValidationError,
    QueryIntentError,
    QueryComplexityError,
    ValidationError
)
from .price import PriceRange


class QueryIntent(Enum):
    """查询意图枚举"""
    SEARCH = "search"              # 搜索商品
    COMPARE = "compare"            # 比较商品
    RECOMMEND = "recommend"        # 推荐商品
    FILTER = "filter"              # 过滤商品
    SORT = "sort"                  # 排序商品
    ANALYZE = "analyze"            # 分析商品
    QUESTION = "question"          # 询问问题
    UNKNOWN = "unknown"            # 未知意图


class QueryType(Enum):
    """查询类型枚举"""
    KEYWORD = "keyword"            # 关键词查询
    CATEGORY = "category"          # 类别查询
    BRAND = "brand"               # 品牌查询
    PRICE_RANGE = "price_range"   # 价格范围查询
    CONDITION = "condition"        # 状态查询
    COMPLEX = "complex"           # 复杂查询


class QueryComplexity(Enum):
    """查询复杂度枚举"""
    SIMPLE = "simple"          # 简单查询
    MODERATE = "moderate"      # 中等查询
    COMPLEX = "complex"        # 复杂查询
    ADVANCED = "advanced"      # 高级查询


@dataclass(frozen=True)
class SearchFilters:
    """搜索过滤条件值对象"""
    category: Optional[str] = None
    brand: Optional[str] = None
    condition: Optional[str] = None
    size: Optional[str] = None
    color: Optional[str] = None
    material: Optional[str] = None
    price_range: Optional[PriceRange] = None
    custom_filters: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """后初始化验证"""
        # 验证自定义过滤器
        if self.custom_filters:
            for key, value in self.custom_filters.items():
                if not isinstance(key, str) or not key.strip():
                    raise ValidationError(
                        "过滤器键必须是非空字符串",
                        field="custom_filters",
                        value=key
                    )
    
    @classmethod
    def create_empty(cls) -> SearchFilters:
        """创建空的过滤条件"""
        return cls()
    
    @classmethod
    def create_with_category(cls, category: str) -> SearchFilters:
        """创建类别过滤条件"""
        return cls(category=category)
    
    @classmethod
    def create_with_price_range(cls, price_range: PriceRange) -> SearchFilters:
        """创建价格范围过滤条件"""
        return cls(price_range=price_range)
    
    def with_category(self, category: str) -> SearchFilters:
        """设置类别"""
        return dataclass.replace(self, category=category)
    
    def with_brand(self, brand: str) -> SearchFilters:
        """设置品牌"""
        return dataclass.replace(self, brand=brand)
    
    def with_condition(self, condition: str) -> SearchFilters:
        """设置商品状态"""
        return dataclass.replace(self, condition=condition)
    
    def with_price_range(self, price_range: PriceRange) -> SearchFilters:
        """设置价格范围"""
        return dataclass.replace(self, price_range=price_range)
    
    def with_custom_filter(self, key: str, value: Any) -> SearchFilters:
        """添加自定义过滤条件"""
        new_custom_filters = dict(self.custom_filters)
        new_custom_filters[key] = value
        return dataclass.replace(self, custom_filters=new_custom_filters)
    
    def remove_custom_filter(self, key: str) -> SearchFilters:
        """移除自定义过滤条件"""
        new_custom_filters = dict(self.custom_filters)
        if key in new_custom_filters:
            del new_custom_filters[key]
        return dataclass.replace(self, custom_filters=new_custom_filters)
    
    def has_filters(self) -> bool:
        """是否有过滤条件"""
        return (self.category is not None or
                self.brand is not None or
                self.condition is not None or
                self.size is not None or
                self.color is not None or
                self.material is not None or
                self.price_range is not None or
                bool(self.custom_filters))
    
    def get_filter_count(self) -> int:
        """获取过滤条件数量"""
        count = 0
        if self.category: count += 1
        if self.brand: count += 1
        if self.condition: count += 1
        if self.size: count += 1
        if self.color: count += 1
        if self.material: count += 1
        if self.price_range: count += 1
        count += len(self.custom_filters)
        return count
    
    def intersect(self, other: SearchFilters) -> SearchFilters:
        """与另一个过滤条件求交集"""
        # 基本属性取更具体的值
        new_category = self.category or other.category
        new_brand = self.brand or other.brand
        new_condition = self.condition or other.condition
        new_size = self.size or other.size
        new_color = self.color or other.color
        new_material = self.material or other.material
        
        # 价格范围求交集
        new_price_range = None
        if self.price_range and other.price_range:
            new_price_range = self.price_range.intersect(other.price_range)
        elif self.price_range:
            new_price_range = self.price_range
        elif other.price_range:
            new_price_range = other.price_range
        
        # 合并自定义过滤器
        new_custom_filters = dict(self.custom_filters)
        new_custom_filters.update(other.custom_filters)
        
        return SearchFilters(
            category=new_category,
            brand=new_brand,
            condition=new_condition,
            size=new_size,
            color=new_color,
            material=new_material,
            price_range=new_price_range,
            custom_filters=new_custom_filters
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "category": self.category,
            "brand": self.brand,
            "condition": self.condition,
            "size": self.size,
            "color": self.color,
            "material": self.material,
            "custom_filters": self.custom_filters
        }
        
        if self.price_range:
            result["price_range"] = self.price_range.to_dict() if hasattr(self.price_range, 'to_dict') else None
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SearchFilters:
        """从字典创建"""
        price_range = None
        if data.get("price_range"):
            price_range = PriceRange.from_dict(data["price_range"])
        
        return cls(
            category=data.get("category"),
            brand=data.get("brand"),
            condition=data.get("condition"),
            size=data.get("size"),
            color=data.get("color"),
            material=data.get("material"),
            price_range=price_range,
            custom_filters=data.get("custom_filters", {})
        )


@dataclass(frozen=True)
class QueryContext:
    """查询上下文值对象"""
    language: str = "ja"
    user_location: Optional[str] = None
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """后初始化验证"""
        # 验证语言代码
        valid_languages = {"ja", "en", "zh", "ko"}
        if self.language not in valid_languages:
            raise ValidationError(
                f"不支持的语言代码: {self.language}",
                field="language",
                value=self.language
            )
    
    @classmethod
    def create_japanese(cls, **kwargs) -> QueryContext:
        """创建日语上下文"""
        return cls(language="ja", **kwargs)
    
    @classmethod
    def create_english(cls, **kwargs) -> QueryContext:
        """创建英语上下文"""
        return cls(language="en", **kwargs)
    
    def with_session(self, session_id: str) -> QueryContext:
        """设置会话ID"""
        return dataclass.replace(self, session_id=session_id)
    
    def with_location(self, location: str) -> QueryContext:
        """设置用户位置"""
        return dataclass.replace(self, user_location=location)
    
    def with_preference(self, key: str, value: Any) -> QueryContext:
        """设置用户偏好"""
        new_preferences = dict(self.user_preferences)
        new_preferences[key] = value
        return dataclass.replace(self, user_preferences=new_preferences)
    
    def get_preference(self, key: str, default: Any = None) -> Any:
        """获取用户偏好"""
        return self.user_preferences.get(key, default)
    
    def has_preference(self, key: str) -> bool:
        """是否有特定偏好"""
        return key in self.user_preferences
    
    def is_japanese(self) -> bool:
        """是否为日语上下文"""
        return self.language == "ja"
    
    def is_english(self) -> bool:
        """是否为英语上下文"""
        return self.language == "en"


@dataclass(frozen=True)
class QueryMetadata:
    """查询元数据值对象"""
    processing_time: float = 0.0
    parser_version: str = "1.0.0"
    confidence: float = 0.8
    detected_entities: Dict[str, List[str]] = field(default_factory=dict)
    sentiment: Optional[str] = None
    urgency: Optional[str] = None
    complexity_score: Optional[int] = None
    
    def __post_init__(self):
        """后初始化验证"""
        # 验证置信度
        if not (0 <= self.confidence <= 1):
            raise ValidationError(
                "置信度必须在0-1之间",
                field="confidence",
                value=self.confidence
            )
        
        # 验证处理时间
        if self.processing_time < 0:
            raise ValidationError(
                "处理时间不能为负数",
                field="processing_time",
                value=self.processing_time
            )
        
        # 验证复杂度分数
        if self.complexity_score is not None and self.complexity_score < 0:
            raise ValidationError(
                "复杂度分数不能为负数",
                field="complexity_score",
                value=self.complexity_score
            )
    
    def with_confidence(self, confidence: float) -> QueryMetadata:
        """设置置信度"""
        return dataclass.replace(self, confidence=confidence)
    
    def with_processing_time(self, time: float) -> QueryMetadata:
        """设置处理时间"""
        return dataclass.replace(self, processing_time=time)
    
    def with_entity(self, entity_type: str, entities: List[str]) -> QueryMetadata:
        """添加检测到的实体"""
        new_entities = dict(self.detected_entities)
        new_entities[entity_type] = entities
        return dataclass.replace(self, detected_entities=new_entities)
    
    def add_entity(self, entity_type: str, entity_value: str) -> QueryMetadata:
        """添加单个实体"""
        new_entities = dict(self.detected_entities)
        if entity_type not in new_entities:
            new_entities[entity_type] = []
        
        entity_list = list(new_entities[entity_type])
        if entity_value not in entity_list:
            entity_list.append(entity_value)
            new_entities[entity_type] = entity_list
        
        return dataclass.replace(self, detected_entities=new_entities)
    
    def get_entities(self, entity_type: str) -> List[str]:
        """获取特定类型的实体"""
        return self.detected_entities.get(entity_type, [])
    
    def has_entity(self, entity_type: str) -> bool:
        """是否有特定类型的实体"""
        return entity_type in self.detected_entities and len(self.detected_entities[entity_type]) > 0
    
    def is_high_confidence(self, threshold: float = 0.8) -> bool:
        """是否为高置信度"""
        return self.confidence >= threshold
    
    def is_complex_query(self, threshold: int = 5) -> bool:
        """是否为复杂查询"""
        return (self.complexity_score is not None and 
                self.complexity_score >= threshold)
    
    def with_sentiment(self, sentiment: str) -> QueryMetadata:
        """设置情感"""
        return dataclass.replace(self, sentiment=sentiment)
    
    def with_urgency(self, urgency: str) -> QueryMetadata:
        """设置紧急度"""
        return dataclass.replace(self, urgency=urgency)
    
    def with_complexity_score(self, score: int) -> QueryMetadata:
        """设置复杂度分数"""
        return dataclass.replace(self, complexity_score=score)


@dataclass(frozen=True)
class SearchCriteria:
    """搜索条件值对象"""
    keywords: List[str] = field(default_factory=list)
    filters: SearchFilters = field(default_factory=SearchFilters.create_empty)
    sort_by: Optional[str] = None
    sort_order: str = "desc"  # "asc" 或 "desc"
    max_results: int = 50
    
    def __post_init__(self):
        """后初始化验证"""
        # 验证关键词
        if not self.keywords and not self.filters.has_filters():
            raise InvalidQueryError(
                "必须提供关键词或过滤条件",
                reason="empty_criteria"
            )
        
        # 验证排序顺序
        if self.sort_order not in ["asc", "desc"]:
            raise ValidationError(
                "排序顺序必须是'asc'或'desc'",
                field="sort_order",
                value=self.sort_order
            )
        
        # 验证最大结果数
        if self.max_results < 1 or self.max_results > 1000:
            raise ValidationError(
                "最大结果数必须在1-1000之间",
                field="max_results",
                value=self.max_results
            )
        
        # 验证关键词格式
        for keyword in self.keywords:
            if not keyword or not keyword.strip():
                raise ValidationError(
                    "关键词不能为空",
                    field="keywords",
                    value=keyword
                )
    
    @classmethod
    def create_keyword_search(cls, keywords: List[str], **kwargs) -> SearchCriteria:
        """创建关键词搜索条件"""
        return cls(keywords=keywords, **kwargs)
    
    @classmethod
    def create_filter_search(cls, filters: SearchFilters, **kwargs) -> SearchCriteria:
        """创建过滤搜索条件"""
        return cls(filters=filters, **kwargs)
    
    def add_keyword(self, keyword: str) -> SearchCriteria:
        """添加关键词"""
        if not keyword or not keyword.strip():
            raise ValidationError("关键词不能为空", field="keyword", value=keyword)
        
        new_keywords = list(self.keywords)
        keyword = keyword.strip()
        if keyword not in new_keywords:
            new_keywords.append(keyword)
        
        return dataclass.replace(self, keywords=new_keywords)
    
    def remove_keyword(self, keyword: str) -> SearchCriteria:
        """移除关键词"""
        new_keywords = [k for k in self.keywords if k != keyword.strip()]
        return dataclass.replace(self, keywords=new_keywords)
    
    def with_filters(self, filters: SearchFilters) -> SearchCriteria:
        """设置过滤条件"""
        return dataclass.replace(self, filters=filters)
    
    def with_sort(self, sort_by: str, sort_order: str = "desc") -> SearchCriteria:
        """设置排序"""
        return dataclass.replace(self, sort_by=sort_by, sort_order=sort_order)
    
    def with_max_results(self, max_results: int) -> SearchCriteria:
        """设置最大结果数"""
        return dataclass.replace(self, max_results=max_results)
    
    def get_keywords_string(self) -> str:
        """获取关键词字符串"""
        return " ".join(self.keywords)
    
    def has_keywords(self) -> bool:
        """是否有关键词"""
        return len(self.keywords) > 0
    
    def has_filters(self) -> bool:
        """是否有过滤条件"""
        return self.filters.has_filters()
    
    def get_complexity_score(self) -> int:
        """计算搜索复杂度分数"""
        score = 0
        score += len(self.keywords)
        score += self.filters.get_filter_count()
        if self.sort_by:
            score += 1
        return score
    
    def get_complexity_level(self) -> QueryComplexity:
        """获取搜索复杂度级别"""
        score = self.get_complexity_score()
        if score <= 2:
            return QueryComplexity.SIMPLE
        elif score <= 5:
            return QueryComplexity.MODERATE
        elif score <= 8:
            return QueryComplexity.COMPLEX
        else:
            return QueryComplexity.ADVANCED
    
    def merge_with(self, other: SearchCriteria) -> SearchCriteria:
        """与另一个搜索条件合并"""
        # 合并关键词
        all_keywords = list(set(self.keywords + other.keywords))
        
        # 合并过滤条件
        merged_filters = self.filters.intersect(other.filters)
        
        # 选择更具体的排序条件
        new_sort_by = self.sort_by or other.sort_by
        new_sort_order = self.sort_order if self.sort_by else other.sort_order
        
        # 选择更小的最大结果数
        new_max_results = min(self.max_results, other.max_results)
        
        return SearchCriteria(
            keywords=all_keywords,
            filters=merged_filters,
            sort_by=new_sort_by,
            sort_order=new_sort_order,
            max_results=new_max_results
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "keywords": self.keywords,
            "filters": self.filters.to_dict(),
            "sort_by": self.sort_by,
            "sort_order": self.sort_order,
            "max_results": self.max_results
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SearchCriteria:
        """从字典创建"""
        filters = SearchFilters.from_dict(data.get("filters", {}))
        
        return cls(
            keywords=data.get("keywords", []),
            filters=filters,
            sort_by=data.get("sort_by"),
            sort_order=data.get("sort_order", "desc"),
            max_results=data.get("max_results", 50)
        )