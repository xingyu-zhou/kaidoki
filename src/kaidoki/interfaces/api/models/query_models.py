"""
查询相关的API数据模型

定义查询解析和分析功能的请求和响应模型。

功能：
- 查询解析请求和响应模型
- 查询建议请求和响应模型
- 查询分析请求和响应模型
- 数据验证和序列化

Author: Kaidoki Team (Refactored)
"""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, validator
from enum import Enum
import time


class Language(str, Enum):
    """语言枚举"""
    JAPANESE = "ja"
    ENGLISH = "en"
    CHINESE = "zh"


class IntentType(str, Enum):
    """意图类型枚举"""
    SEARCH = "search"
    BUY = "buy"
    SELL = "sell"
    COMPARE = "compare"
    INFORMATION = "information"


class SentimentType(str, Enum):
    """情感类型枚举"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class ComplexityLevel(str, Enum):
    """复杂度级别枚举"""
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


class QueryParseRequest(BaseModel):
    """查询解析请求模型"""
    query: str = Field(..., description="要解析的查询文本", min_length=1, max_length=500)
    language: Optional[Language] = Field(Language.JAPANESE, description="查询语言")
    include_suggestions: Optional[bool] = Field(True, description="是否包含建议")
    timestamp: Optional[float] = Field(None, description="请求时间戳")
    
    @validator('timestamp', pre=True, always=True)
    def set_timestamp(cls, v):
        return v or time.time()
    
    class Config:
        schema_extra = {
            "example": {
                "query": "iPhone 13 Pro 128GB 5万円以下",
                "language": "ja",
                "include_suggestions": True,
                "timestamp": 1640995200.0
            }
        }


class EntityInfo(BaseModel):
    """实体信息模型"""
    type: str = Field(..., description="实体类型")
    value: str = Field(..., description="实体值")
    confidence: float = Field(..., description="置信度", ge=0.0, le=1.0)
    start_position: Optional[int] = Field(None, description="开始位置")
    end_position: Optional[int] = Field(None, description="结束位置")
    
    class Config:
        schema_extra = {
            "example": {
                "type": "product_name",
                "value": "iPhone 13 Pro",
                "confidence": 0.95,
                "start_position": 0,
                "end_position": 12
            }
        }


class QueryParseResponse(BaseModel):
    """查询解析响应模型"""
    original_query: str = Field(..., description="原始查询")
    parsed_entities: Dict[str, Any] = Field(..., description="解析出的实体")
    formatted_output: str = Field(..., description="格式化输出")
    confidence_score: float = Field(..., description="整体置信度", ge=0.0, le=1.0)
    processing_time: float = Field(..., description="处理时间（秒）")
    suggestions: List[str] = Field(default_factory=list, description="查询建议")
    entities: List[EntityInfo] = Field(default_factory=list, description="详细实体信息")
    
    class Config:
        schema_extra = {
            "example": {
                "original_query": "iPhone 13 Pro 128GB 5万円以下",
                "parsed_entities": {
                    "product_name": "iPhone 13 Pro",
                    "storage": "128GB",
                    "max_price": 50000,
                    "keywords": ["iPhone", "13", "Pro", "128GB"]
                },
                "formatted_output": "商品: iPhone 13 Pro 128GB\n価格上限: 50,000円",
                "confidence_score": 0.92,
                "processing_time": 0.15,
                "suggestions": ["iPhone 13 Pro Max", "iPhone 13 Pro 256GB"],
                "entities": []
            }
        }


class QuerySuggestionRequest(BaseModel):
    """查询建议请求模型"""
    partial_query: str = Field(..., description="部分查询文本", min_length=1, max_length=100)
    language: Optional[Language] = Field(Language.JAPANESE, description="语言")
    category: Optional[str] = Field(None, description="分类筛选")
    limit: Optional[int] = Field(5, description="建议数量限制", ge=1, le=20)
    include_popular: Optional[bool] = Field(True, description="是否包含热门建议")
    
    class Config:
        schema_extra = {
            "example": {
                "partial_query": "iPhone",
                "language": "ja",
                "category": "スマートフォン",
                "limit": 5,
                "include_popular": True
            }
        }


class QuerySuggestion(BaseModel):
    """查询建议模型"""
    query: str = Field(..., description="建议的查询")
    popularity: float = Field(..., description="热度分数", ge=0.0, le=1.0)
    category: Optional[str] = Field(None, description="相关分类")
    reason: Optional[str] = Field(None, description="建议原因")
    
    class Config:
        schema_extra = {
            "example": {
                "query": "iPhone 13 Pro",
                "popularity": 0.95,
                "category": "スマートフォン",
                "reason": "高人気商品"
            }
        }


class QuerySuggestionResponse(BaseModel):
    """查询建议响应模型"""
    partial_query: str = Field(..., description="部分查询")
    suggestions: List[QuerySuggestion] = Field(..., description="建议列表")
    generated_at: float = Field(..., description="生成时间戳")
    
    class Config:
        schema_extra = {
            "example": {
                "partial_query": "iPhone",
                "suggestions": [],
                "generated_at": 1640995200.0
            }
        }


class QueryAnalysisRequest(BaseModel):
    """查询分析请求模型"""
    query: str = Field(..., description="要分析的查询", min_length=1, max_length=500)
    language: Optional[Language] = Field(Language.JAPANESE, description="查询语言")
    include_optimization: Optional[bool] = Field(True, description="是否包含优化建议")
    user_context: Optional[Dict[str, Any]] = Field(None, description="用户上下文信息")
    
    class Config:
        schema_extra = {
            "example": {
                "query": "安いiPhoneが欲しい",
                "language": "ja",
                "include_optimization": True,
                "user_context": {
                    "previous_searches": ["iPhone", "スマートフォン"],
                    "budget_range": [20000, 80000]
                }
            }
        }


class IntentInfo(BaseModel):
    """意图信息模型"""
    type: IntentType = Field(..., description="意图类型")
    confidence: float = Field(..., description="置信度", ge=0.0, le=1.0)
    keywords: List[str] = Field(default_factory=list, description="关键词")
    
    class Config:
        schema_extra = {
            "example": {
                "type": "buy",
                "confidence": 0.87,
                "keywords": ["欲しい", "安い"]
            }
        }


class SentimentInfo(BaseModel):
    """情感信息模型"""
    sentiment: SentimentType = Field(..., description="情感类型")
    score: float = Field(..., description="情感分数", ge=0.0, le=1.0)
    positive_indicators: int = Field(..., description="积极指标数")
    negative_indicators: int = Field(..., description="消极指标数")
    
    class Config:
        schema_extra = {
            "example": {
                "sentiment": "positive",
                "score": 0.7,
                "positive_indicators": 2,
                "negative_indicators": 0
            }
        }


class ComplexityInfo(BaseModel):
    """复杂度信息模型"""
    level: ComplexityLevel = Field(..., description="复杂度级别")
    score: float = Field(..., description="复杂度分数", ge=0.0, le=1.0)
    factors: Dict[str, Any] = Field(..., description="影响因素")
    
    class Config:
        schema_extra = {
            "example": {
                "level": "medium",
                "score": 0.6,
                "factors": {
                    "word_count": 5,
                    "entity_count": 3,
                    "has_price_range": True,
                    "has_category": False
                }
            }
        }


class OptimizationSuggestion(BaseModel):
    """优化建议模型"""
    type: str = Field(..., description="建议类型")
    message: str = Field(..., description="建议内容")
    priority: str = Field(..., description="优先级")
    example: Optional[str] = Field(None, description="示例")
    
    class Config:
        schema_extra = {
            "example": {
                "type": "add_price_range",
                "message": "添加价格范围可以获得更精准的结果",
                "priority": "medium",
                "example": "iPhone 13 Pro 5万円以下"
            }
        }


class QueryAnalysisResponse(BaseModel):
    """查询分析响应模型"""
    query: str = Field(..., description="分析的查询")
    intent: IntentInfo = Field(..., description="意图信息")
    sentiment: SentimentInfo = Field(..., description="情感信息")
    complexity: ComplexityInfo = Field(..., description="复杂度信息")
    entities: Dict[str, Any] = Field(..., description="实体信息")
    optimization_suggestions: List[OptimizationSuggestion] = Field(
        default_factory=list, 
        description="优化建议"
    )
    analyzed_at: float = Field(..., description="分析时间戳")
    
    class Config:
        schema_extra = {
            "example": {
                "query": "安いiPhoneが欲しい",
                "intent": {
                    "type": "buy",
                    "confidence": 0.87,
                    "keywords": ["欲しい", "安い"]
                },
                "sentiment": {
                    "sentiment": "positive",
                    "score": 0.7,
                    "positive_indicators": 2,
                    "negative_indicators": 0
                },
                "complexity": {
                    "level": "simple",
                    "score": 0.3,
                    "factors": {}
                },
                "entities": {},
                "optimization_suggestions": [],
                "analyzed_at": 1640995200.0
            }
        }


class QueryHistory(BaseModel):
    """查询历史模型"""
    query: str = Field(..., description="查询内容")
    timestamp: float = Field(..., description="查询时间戳")
    results_count: int = Field(..., description="结果数量")
    user_action: Optional[str] = Field(None, description="用户行为")
    
    class Config:
        schema_extra = {
            "example": {
                "query": "iPhone 13 Pro",
                "timestamp": 1640995200.0,
                "results_count": 45,
                "user_action": "clicked_first_result"
            }
        }


class PopularQuery(BaseModel):
    """热门查询模型"""
    query: str = Field(..., description="查询内容")
    popularity: float = Field(..., description="热度分数", ge=0.0, le=1.0)
    category: str = Field(..., description="分类")
    trend: Optional[str] = Field(None, description="趋势")
    
    class Config:
        schema_extra = {
            "example": {
                "query": "iPhone 13",
                "popularity": 0.95,
                "category": "スマートフォン",
                "trend": "rising"
            }
        }


class QueryStatistics(BaseModel):
    """查询统计模型"""
    total_queries: int = Field(..., description="总查询数")
    unique_queries: int = Field(..., description="唯一查询数")
    average_length: float = Field(..., description="平均查询长度")
    top_categories: List[Dict[str, Any]] = Field(..., description="热门分类")
    time_distribution: Dict[str, int] = Field(..., description="时间分布")
    
    class Config:
        schema_extra = {
            "example": {
                "total_queries": 10000,
                "unique_queries": 8500,
                "average_length": 15.3,
                "top_categories": [
                    {"category": "スマートフォン", "count": 2500},
                    {"category": "パソコン", "count": 1800}
                ],
                "time_distribution": {
                    "morning": 2500,
                    "afternoon": 4000,
                    "evening": 3500
                }
            }
        }