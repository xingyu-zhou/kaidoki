"""
配置模块包

该包包含了系统的配置管理功能。
提供了设置、常量、环境变量等配置相关的模块。

Author: Mercari AI Agent Team
"""

# 导入配置类
from .settings import (
    Settings,
    LLMConfig,
    ScraperConfig,
    CacheConfig,
    LogConfig,
    DatabaseConfig,
    APIConfig,
    load_settings
)

# 导出所有配置相关的类和函数
__all__ = [
    # 设置类
    "Settings",
    "LLMConfig",
    "ScraperConfig",
    "CacheConfig",
    "LogConfig",
    "DatabaseConfig",
    "APIConfig",
    "load_settings"
]

# 版本信息
__version__ = "1.0.0"