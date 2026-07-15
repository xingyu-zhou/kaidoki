"""
分析组件模块

该模块包含系统的分析组件，负责产品数据的多维度分析和评分。

主要组件：
- ProductAnalyzer: 产品分析器，进行产品数据分析
- ScoringEngine: 评分引擎，计算产品综合评分
- RankingSystem: 排名系统，对产品进行智能排序

功能特点：
- 多维度分析：价格、质量、相关性、卖家信誉等
- 智能评分：基于机器学习的评分算法
- 动态排名：考虑用户偏好和市场趋势
- 透明推理：提供详细的分析理由

设计原则：
- 模块化设计：每个分析器独立工作
- 可扩展性：易于添加新的分析维度
- 高性能：优化的算法和数据结构
- 准确性：基于历史数据的训练和验证

Author: Mercari AI Agent Team
"""

from .product_analyzer import ProductAnalyzer, AnalysisResult
from .scoring_engine import ScoringEngine, ScoreResult
from .ranking_system import RankingSystem, RankingResult

__all__ = [
    "ProductAnalyzer",
    "AnalysisResult",
    "ScoringEngine",
    "ScoreResult",
    "RankingSystem",
    "RankingResult"
]