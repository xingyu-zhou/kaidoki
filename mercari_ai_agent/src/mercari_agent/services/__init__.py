"""
服务层

该模块包含系统的核心服务组件，提供各种业务功能的具体实现。

主要服务：
- LLMService: LLM服务，支持多种LLM提供商
- ScraperService: 爬虫服务，负责数据采集
- AnalysisService: 分析服务，进行产品分析和评分

设计原则：
- 单一职责：每个服务专注于特定功能
- 依赖注入：支持灵活的依赖管理
- 异步处理：提供高性能的异步接口
- 错误处理：完善的异常处理机制

Author: Mercari AI Agent Team
"""

from .llm_service import LLMService, LLMProvider, LLMResponse
from .scraper_service import ScraperService, ScrapingResult
from .analysis_service import AnalysisService, AnalysisResult

__all__ = [
    "LLMService",
    "LLMProvider",
    "LLMResponse",
    "ScraperService",
    "ScrapingResult",
    "AnalysisService",
    "AnalysisResult"
]