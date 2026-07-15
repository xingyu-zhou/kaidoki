"""
Mercari日本智能购物AI代理系统

这是一个基于LLM的智能购物助手系统，专为日本Mercari平台设计。
系统具备自然语言理解、实时数据爬取、智能分析和推荐功能。

主要功能：
- 日语查询解析和意图理解
- Mercari平台数据实时爬取
- 多维度产品分析和评分
- 智能推荐和排名
- 透明化推理和决策说明

技术特点：
- 支持多种LLM（OpenAI GPT、Anthropic Claude）
- 异步编程架构
- 分层模块化设计
- 完整的日语NLP支持
- 智能反爬虫机制

Author: Mercari AI Agent Team
Version: 1.0.0
License: MIT
"""

__version__ = "1.0.0"
__author__ = "Mercari AI Agent Team"
__email__ = "support@mercari-ai-agent.com"
__license__ = "MIT"

from .core.query_parser import QueryParser
from .core.recommendation_engine import RecommendationEngine
from .core.output_formatter import OutputFormatter
from .services.llm_service import LLMService
from .services.scraper_service import ScraperService
from .services.analysis_service import AnalysisService
from .models.product import Product, ProductData
from .models.query import ParsedQuery, SearchQuery
from .models.recommendation import Recommendation, RecommendationResult

__all__ = [
    # Core components
    "QueryParser",
    "RecommendationEngine", 
    "OutputFormatter",
    
    # Services
    "LLMService",
    "ScraperService",
    "AnalysisService",
    
    # Models
    "Product",
    "ProductData",
    "ParsedQuery",
    "SearchQuery",
    "Recommendation",
    "RecommendationResult",
    
    # Metadata
    "__version__",
    "__author__",
    "__email__",
    "__license__"
]

# 系统配置
import logging
from .config.settings import load_settings

# 加载配置
settings = load_settings()

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.log.level, "INFO"),
    format=settings.log.format
)

logger = logging.getLogger(__name__)
logger.info(f"Mercari AI Agent v{__version__} initialized")