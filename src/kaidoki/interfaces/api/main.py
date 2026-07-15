"""
REST API主应用模块

该模块提供REST API接口，用于访问Kaidoki的各项功能。
基于FastAPI构建，提供高性能的异步API服务。

主要功能：
- 商品搜索和推荐API
- 查询解析API
- 系统状态API
- 健康检查API

Author: Kaidoki Team (Refactored)
"""

import asyncio
from typing import Optional, List
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import time
import logging

from ...shared.config.app_config import AppConfig, get_config
from ...shared.utils.logger_utils import setup_logging, get_logger
from ...shared.exceptions.service_exceptions import BaseServiceException
from ...application.services.query_parser_service import QueryParserService
from ...application.services.recommendation_service import RecommendationService
from ...application.services.output_formatter_service import OutputFormatterService
from ...infrastructure.llm.llm_service import LLMService
from ...infrastructure.scraping.scraper_service import ScraperService
from .v1.routes import search_router, system_router, query_router
from .middleware.rate_limiter import RateLimiterMiddleware
from .middleware.error_handler import ErrorHandlerMiddleware

logger = get_logger(__name__)


class APIServices:
    """API服务容器"""
    
    def __init__(self):
        self.config: Optional[AppConfig] = None
        self.query_parser: Optional[QueryParserService] = None
        self.recommendation_service: Optional[RecommendationService] = None
        self.output_formatter: Optional[OutputFormatterService] = None
        self.llm_service: Optional[LLMService] = None
        self.scraper_service: Optional[ScraperService] = None
    
    async def initialize(self):
        """初始化所有服务"""
        try:
            # 加载配置
            self.config = get_config()
            
            # 设置日志
            setup_logging(
                log_level=self.config.logging.level,
                log_dir=self.config.logging.log_dir
            )
            
            # 初始化服务
            self.llm_service = LLMService(self.config)
            self.query_parser = QueryParserService(self.config, self.llm_service)
            self.recommendation_service = RecommendationService(self.config)
            self.output_formatter = OutputFormatterService(self.config)
            self.scraper_service = ScraperService(self.config)
            
            # 初始化异步服务
            await self.scraper_service.initialize()
            
            logger.info("API服务初始化完成")
            
        except Exception as e:
            logger.error(f"API服务初始化失败: {e}")
            raise
    
    async def cleanup(self):
        """清理服务资源"""
        try:
            if self.scraper_service:
                await self.scraper_service.close()
            if self.llm_service:
                await self.llm_service.close()
            logger.info("API服务清理完成")
        except Exception as e:
            logger.error(f"API服务清理失败: {e}")


# 全局服务实例
api_services = APIServices()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动
    logger.info("启动API服务...")
    await api_services.initialize()
    
    yield
    
    # 关闭
    logger.info("关闭API服务...")
    await api_services.cleanup()


def get_services() -> APIServices:
    """获取服务实例的依赖注入函数"""
    return api_services


def create_app() -> FastAPI:
    """创建FastAPI应用"""
    config = get_config()
    
    app = FastAPI(
        title="Kaidoki API",
        description="智能购物助手API服务",
        version="2.0.0",
        debug=config.debug,
        lifespan=lifespan
    )
    
    # 添加中间件
    _add_middleware(app, config)
    
    # 添加路由
    _add_routes(app)
    
    # 添加异常处理
    _add_exception_handlers(app)
    
    return app


def _add_middleware(app: FastAPI, config: AppConfig):
    """添加中间件"""
    
    # CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 信任主机中间件
    if not config.debug:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["localhost", "127.0.0.1", config.api.host]
        )
    
    # 速率限制中间件
    app.add_middleware(
        RateLimiterMiddleware,
        requests_per_minute=config.api.rate_limit
    )
    
    # 错误处理中间件
    app.add_middleware(ErrorHandlerMiddleware)
    
    # 请求日志中间件
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        logger.info(
            f"{request.method} {request.url.path} - "
            f"Status: {response.status_code} - "
            f"Time: {process_time:.3f}s"
        )
        
        return response


def _add_routes(app: FastAPI):
    """添加路由"""
    
    # 健康检查
    @app.get("/health")
    async def health_check():
        """健康检查端点"""
        return {"status": "healthy", "timestamp": time.time()}
    
    # 根路径
    @app.get("/")
    async def root():
        """根路径信息"""
        return {
            "name": "Kaidoki API",
            "version": "2.0.0",
            "description": "智能购物助手API服务",
            "endpoints": {
                "health": "/health",
                "docs": "/docs",
                "api": "/api/v1"
            }
        }
    
    # API路由
    app.include_router(search_router, prefix="/api/v1", tags=["search"])
    app.include_router(query_router, prefix="/api/v1", tags=["query"])
    app.include_router(system_router, prefix="/api/v1", tags=["system"])


def _add_exception_handlers(app: FastAPI):
    """添加异常处理器"""
    
    @app.exception_handler(BaseServiceException)
    async def service_exception_handler(request: Request, exc: BaseServiceException):
        """服务异常处理"""
        logger.error(f"服务异常: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "service_error",
                "message": str(exc),
                "timestamp": time.time()
            }
        )
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """HTTP异常处理"""
        logger.warning(f"HTTP异常: {exc.status_code} - {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "http_error",
                "message": exc.detail,
                "timestamp": time.time()
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """通用异常处理"""
        logger.error(f"未处理的异常: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "message": "内部服务器错误",
                "timestamp": time.time()
            }
        )


# 创建应用实例
app = create_app()


if __name__ == "__main__":
    config = get_config()
    uvicorn.run(
        "main:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.debug,
        log_level=config.logging.level.lower()
    )