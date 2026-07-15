"""
业务异常类

定义业务领域相关的异常，如验证错误、业务规则违反等。

Author: Kaidoki Team
"""

from typing import Any, Dict, List, Optional
from .base import DomainException


class ValidationError(DomainException):
    """验证错误异常"""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        validation_errors: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> None:
        details = {
            "field": field,
            "value": value,
            "validation_errors": validation_errors or [],
        }
        super().__init__(message, "VALIDATION_ERROR", details, **kwargs)


class BusinessRuleViolationError(DomainException):
    """业务规则违反异常"""
    
    def __init__(
        self,
        message: str,
        rule_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> None:
        details = {
            "rule_name": rule_name,
            "context": context or {},
        }
        super().__init__(message, "BUSINESS_RULE_VIOLATION", details, **kwargs)


class ProductNotFoundError(DomainException):
    """商品未找到异常"""
    
    def __init__(
        self,
        message: str = "Product not found",
        product_id: Optional[str] = None,
        search_criteria: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> None:
        details = {
            "product_id": product_id,
            "search_criteria": search_criteria or {},
        }
        super().__init__(message, "PRODUCT_NOT_FOUND", details, **kwargs)


class InvalidQueryError(DomainException):
    """无效查询异常"""
    
    def __init__(
        self,
        message: str = "Invalid query",
        query: Optional[str] = None,
        reason: Optional[str] = None,
        suggestions: Optional[List[str]] = None,
        **kwargs
    ) -> None:
        details = {
            "query": query,
            "reason": reason,
            "suggestions": suggestions or [],
        }
        super().__init__(message, "INVALID_QUERY", details, **kwargs)


class PriceRangeError(DomainException):
    """价格范围错误异常"""
    
    def __init__(
        self,
        message: str = "Invalid price range",
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        **kwargs
    ) -> None:
        details = {
            "min_price": min_price,
            "max_price": max_price,
        }
        super().__init__(message, "PRICE_RANGE_ERROR", details, **kwargs)


class CategoryError(DomainException):
    """商品类别错误异常"""
    
    def __init__(
        self,
        message: str = "Invalid category",
        category: Optional[str] = None,
        available_categories: Optional[List[str]] = None,
        **kwargs
    ) -> None:
        details = {
            "category": category,
            "available_categories": available_categories or [],
        }
        super().__init__(message, "CATEGORY_ERROR", details, **kwargs)


class SearchLimitExceededError(DomainException):
    """搜索限制超出异常"""
    
    def __init__(
        self,
        message: str = "Search limit exceeded",
        current_count: Optional[int] = None,
        limit: Optional[int] = None,
        reset_time: Optional[str] = None,
        **kwargs
    ) -> None:
        details = {
            "current_count": current_count,
            "limit": limit,
            "reset_time": reset_time,
        }
        super().__init__(message, "SEARCH_LIMIT_EXCEEDED", details, **kwargs)


class RecommendationError(DomainException):
    """推荐错误异常"""
    
    def __init__(
        self,
        message: str = "Recommendation generation failed",
        user_preferences: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
        **kwargs
    ) -> None:
        details = {
            "user_preferences": user_preferences or {},
            "reason": reason,
        }
        super().__init__(message, "RECOMMENDATION_ERROR", details, **kwargs)


class AnalysisError(DomainException):
    """分析错误异常"""
    
    def __init__(
        self,
        message: str = "Analysis failed",
        analysis_type: Optional[str] = None,
        input_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> None:
        details = {
            "analysis_type": analysis_type,
            "input_data": input_data or {},
        }
        super().__init__(message, "ANALYSIS_ERROR", details, **kwargs)


class DataQualityError(DomainException):
    """数据质量错误异常"""
    
    def __init__(
        self,
        message: str = "Data quality issue detected",
        data_source: Optional[str] = None,
        quality_issues: Optional[List[str]] = None,
        **kwargs
    ) -> None:
        details = {
            "data_source": data_source,
            "quality_issues": quality_issues or [],
        }
        super().__init__(message, "DATA_QUALITY_ERROR", details, **kwargs)


class UserPreferenceError(DomainException):
    """用户偏好错误异常"""
    
    def __init__(
        self,
        message: str = "Invalid user preference",
        preference_key: Optional[str] = None,
        preference_value: Optional[Any] = None,
        **kwargs
    ) -> None:
        details = {
            "preference_key": preference_key,
            "preference_value": preference_value,
        }
        super().__init__(message, "USER_PREFERENCE_ERROR", details, **kwargs)


class MarketDataError(DomainException):
    """市场数据错误异常"""
    
    def __init__(
        self,
        message: str = "Market data error",
        market_segment: Optional[str] = None,
        data_type: Optional[str] = None,
        **kwargs
    ) -> None:
        details = {
            "market_segment": market_segment,
            "data_type": data_type,
        }
        super().__init__(message, "MARKET_DATA_ERROR", details, **kwargs)


# 特定于 Kaidoki 的业务异常


class ProductValidationError(ValidationError):
    """商品验证错误异常"""
    
    def __init__(
        self,
        message: str = "Product validation failed",
        product_field: Optional[str] = None,
        product_value: Optional[Any] = None,
        **kwargs
    ) -> None:
        super().__init__(
            message=message,
            field=product_field,
            value=product_value,
            **kwargs
        )
        self.details["error_code"] = "PRODUCT_VALIDATION_ERROR"


class QueryValidationError(ValidationError):
    """查询验证错误异常"""
    
    def __init__(
        self,
        message: str = "Query validation failed",
        query_field: Optional[str] = None,
        query_value: Optional[Any] = None,
        **kwargs
    ) -> None:
        super().__init__(
            message=message,
            field=query_field,
            value=query_value,
            **kwargs
        )
        self.details["error_code"] = "QUERY_VALIDATION_ERROR"


class PriceParsingError(DomainException):
    """价格解析错误异常"""
    
    def __init__(
        self,
        message: str = "Price parsing failed",
        price_text: Optional[str] = None,
        reason: Optional[str] = None,
        **kwargs
    ) -> None:
        details = {
            "price_text": price_text,
            "reason": reason,
        }
        super().__init__(message, "PRICE_PARSING_ERROR", details, **kwargs)


class PriceNormalizationError(DomainException):
    """价格规范化错误异常"""
    
    def __init__(
        self,
        message: str = "Price normalization failed",
        original_price: Optional[str] = None,
        currency: Optional[str] = None,
        **kwargs
    ) -> None:
        details = {
            "original_price": original_price,
            "currency": currency,
        }
        super().__init__(message, "PRICE_NORMALIZATION_ERROR", details, **kwargs)


class CurrencyConversionError(DomainException):
    """货币转换错误异常"""
    
    def __init__(
        self,
        message: str = "Currency conversion failed",
        from_currency: Optional[str] = None,
        to_currency: Optional[str] = None,
        amount: Optional[float] = None,
        **kwargs
    ) -> None:
        details = {
            "from_currency": from_currency,
            "to_currency": to_currency,
            "amount": amount,
        }
        super().__init__(message, "CURRENCY_CONVERSION_ERROR", details, **kwargs)


class ProductImageError(DomainException):
    """商品图片错误异常"""
    
    def __init__(
        self,
        message: str = "Product image error",
        image_url: Optional[str] = None,
        error_type: Optional[str] = None,
        **kwargs
    ) -> None:
        details = {
            "image_url": image_url,
            "error_type": error_type,
        }
        super().__init__(message, "PRODUCT_IMAGE_ERROR", details, **kwargs)


class SellerInfoError(DomainException):
    """卖家信息错误异常"""
    
    def __init__(
        self,
        message: str = "Seller information error",
        seller_id: Optional[str] = None,
        issue_type: Optional[str] = None,
        **kwargs
    ) -> None:
        details = {
            "seller_id": seller_id,
            "issue_type": issue_type,
        }
        super().__init__(message, "SELLER_INFO_ERROR", details, **kwargs)


class ProductConditionError(DomainException):
    """商品状态错误异常"""
    
    def __init__(
        self,
        message: str = "Invalid product condition",
        condition: Optional[str] = None,
        valid_conditions: Optional[List[str]] = None,
        **kwargs
    ) -> None:
        details = {
            "condition": condition,
            "valid_conditions": valid_conditions or [],
        }
        super().__init__(message, "PRODUCT_CONDITION_ERROR", details, **kwargs)


class QueryIntentError(DomainException):
    """查询意图错误异常"""
    
    def __init__(
        self,
        message: str = "Query intent detection failed",
        query_text: Optional[str] = None,
        detected_intent: Optional[str] = None,
        confidence: Optional[float] = None,
        **kwargs
    ) -> None:
        details = {
            "query_text": query_text,
            "detected_intent": detected_intent,
            "confidence": confidence,
        }
        super().__init__(message, "QUERY_INTENT_ERROR", details, **kwargs)


class QueryComplexityError(DomainException):
    """查询复杂度错误异常"""
    
    def __init__(
        self,
        message: str = "Query too complex to process",
        complexity_score: Optional[int] = None,
        max_complexity: Optional[int] = None,
        **kwargs
    ) -> None:
        details = {
            "complexity_score": complexity_score,
            "max_complexity": max_complexity,
        }
        super().__init__(message, "QUERY_COMPLEXITY_ERROR", details, **kwargs)
