"""
核心业务逻辑层

该模块包含系统的核心业务逻辑组件，负责处理用户查询、生成推荐和格式化输出。

主要组件：
- QueryParser: 查询解析器，使用LLM理解用户的日语购物请求
- RecommendationEngine: 推荐引擎，基于多维度分析生成智能推荐
- OutputFormatter: 输出格式化器，生成结构化的Markdown报告

设计原则：
- 分离关注点：每个组件负责单一职责
- 异步处理：支持高并发和非阻塞操作
- 可扩展性：易于添加新的分析维度和推荐策略
- 类型安全：完整的类型注解和验证

Author: Mercari AI Agent Team
"""

from .query_parser import QueryParser, ParsedQuery
from .recommendation_engine import RecommendationEngine, RecommendationResult
from .output_formatter import OutputFormatter, FormattedOutput

__all__ = [
    "QueryParser",
    "ParsedQuery",
    "RecommendationEngine", 
    "RecommendationResult",
    "OutputFormatter",
    "FormattedOutput"
]