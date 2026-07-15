"""
提示词管理系统

该模块提供了结构化的提示词管理功能，包括：
- 系统级提示词
- 查询解析提示词
- 分析推理提示词
- 输出格式化提示词
"""

from .system_prompts import SystemPrompts
from .query_prompts import QueryPrompts
from .analysis_prompts import AnalysisPrompts
from .formatting_prompts import FormattingPrompts

__all__ = [
    "SystemPrompts",
    "QueryPrompts", 
    "AnalysisPrompts",
    "FormattingPrompts",
]