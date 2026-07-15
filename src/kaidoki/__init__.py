"""
Kaidoki - 重构版

一个整合二手市场、新品价格与官方产品线信息的智能购物助手。
采用六边形架构和领域驱动设计，集成多个 LLM 提供商。

主要特性:
- 多 LLM 提供商支持 (OpenAI, Anthropic, Azure)
- 智能工具调用系统
- 插件化架构
- 反爬虫系统
- 日语自然语言处理

Author: Kaidoki Team
Version: 2.0.0
License: MIT
"""

from typing import Dict, Any

__version__ = "2.0.0"
__author__ = "Kaidoki Team"
__license__ = "MIT"
__description__ = "Kaidoki - 多数据源智能购物助手"

# 版本信息
VERSION_INFO: Dict[str, Any] = {
    "version": __version__,
    "author": __author__,
    "license": __license__,
    "description": __description__,
    "python_requires": ">=3.11",
    "homepage": "https://github.com/xingyu-zhou/kaidoki",
    "repository": "https://github.com/xingyu-zhou/kaidoki.git",
}

# 公共 API 导出
# 注意：这里只导出最核心的接口，避免循环导入
__all__ = [
    "__version__",
    "__author__",
    "__license__",
    "__description__",
    "VERSION_INFO",
]


def get_version() -> str:
    """获取版本号"""
    return __version__


def get_version_info() -> Dict[str, Any]:
    """获取详细版本信息"""
    return VERSION_INFO.copy()


# 类型标记文件，用于 mypy 类型检查
__all__.append("py.typed")
