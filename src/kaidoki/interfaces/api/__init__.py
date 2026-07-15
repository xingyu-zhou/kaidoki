"""
API接口模块

提供REST API接口功能的模块。

主要组件：
- FastAPI应用和路由
- 中间件（速率限制、错误处理等）
- 数据模型（请求和响应）
- 服务器启动脚本

Author: Kaidoki Team (Refactored)
"""

from .main import create_app, APIServices, get_services
from .server import APIServer

__all__ = [
    "create_app",
    "APIServices",
    "get_services",
    "APIServer"
]