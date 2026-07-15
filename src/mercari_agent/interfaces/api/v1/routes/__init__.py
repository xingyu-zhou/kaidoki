"""
API路由模块
"""

from .search_router import router as search_router
from .query_router import router as query_router
from .system_router import router as system_router

__all__ = ["search_router", "query_router", "system_router"]