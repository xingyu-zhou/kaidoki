"""
API数据模型模块

导出所有数据模型供API路由使用。

Author: Kaidoki Team (Refactored)
"""

from .search_models import (
    SearchRequest,
    SearchResponse, 
    RecommendationRequest,
    RecommendationResponse,
    ProductResponse,
    SearchFilter,
    SearchHistory,
    SearchSuggestion,
    SortBy,
    Condition,
    RecommendationType,
    Language
)

from .query_models import (
    QueryParseRequest,
    QueryParseResponse,
    QuerySuggestionRequest, 
    QuerySuggestionResponse,
    QueryAnalysisRequest,
    QueryAnalysisResponse,
    EntityInfo,
    QuerySuggestion,
    IntentInfo,
    SentimentInfo,
    ComplexityInfo,
    OptimizationSuggestion,
    QueryHistory as QueryHistoryModel,
    PopularQuery,
    QueryStatistics,
    IntentType,
    SentimentType,
    ComplexityLevel
)

from .system_models import (
    HealthCheckResponse,
    SystemStatusResponse,
    ServiceMetricsResponse,
    ConfigResponse,
    SystemResourceInfo,
    ProcessInfo,
    ServiceStatistics,
    ResponseTimeMetrics,
    EndpointStatistics,
    ErrorInfo,
    ConfigurationInfo,
    SystemAlert,
    PerformanceMetrics,
    SystemLog,
    MaintenanceMode,
    HealthStatus,
    ServiceStatus,
    AlertLevel
)

__all__ = [
    # 搜索相关模型
    "SearchRequest",
    "SearchResponse", 
    "RecommendationRequest",
    "RecommendationResponse",
    "ProductResponse",
    "SearchFilter",
    "SearchHistory",
    "SearchSuggestion",
    "SortBy",
    "Condition",
    "RecommendationType",
    "Language",
    
    # 查询相关模型
    "QueryParseRequest",
    "QueryParseResponse",
    "QuerySuggestionRequest", 
    "QuerySuggestionResponse",
    "QueryAnalysisRequest",
    "QueryAnalysisResponse",
    "EntityInfo",
    "QuerySuggestion",
    "IntentInfo",
    "SentimentInfo",
    "ComplexityInfo",
    "OptimizationSuggestion",
    "QueryHistoryModel",
    "PopularQuery",
    "QueryStatistics",
    "IntentType",
    "SentimentType",
    "ComplexityLevel",
    
    # 系统相关模型
    "HealthCheckResponse",
    "SystemStatusResponse",
    "ServiceMetricsResponse",
    "ConfigResponse",
    "SystemResourceInfo",
    "ProcessInfo",
    "ServiceStatistics",
    "ResponseTimeMetrics",
    "EndpointStatistics",
    "ErrorInfo",
    "ConfigurationInfo",
    "SystemAlert",
    "PerformanceMetrics",
    "SystemLog",
    "MaintenanceMode",
    "HealthStatus",
    "ServiceStatus",
    "AlertLevel"
]