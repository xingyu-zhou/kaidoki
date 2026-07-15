"""
错误处理中间件
"""

import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """全局错误处理中间件"""
    
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except HTTPException:
            # FastAPI HTTPException 应该正常传递
            raise
        except Exception as e:
            logger.error(f"未处理的异常: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_server_error",
                    "message": "内部服务器错误",
                    "timestamp": time.time()
                }
            )