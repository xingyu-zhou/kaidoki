"""
日志系统模块

该模块提供统一的日志记录功能。
支持结构化日志、性能监控和错误追踪。

主要功能：
- 结构化日志记录
- 多级日志输出
- 性能监控
- 错误追踪
- 日志格式化

Author: Mercari AI Agent Team
"""

import logging
import logging.handlers
import sys
import os
from typing import Dict, Any, Optional
from datetime import datetime
import json
from pathlib import Path

# 默认日志配置
DEFAULT_LOG_LEVEL = logging.INFO
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_LOG_DIR = "logs"


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器"""
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录"""
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # 添加额外字段
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)
        
        return json.dumps(log_data, ensure_ascii=False, indent=None)


class PerformanceLogger:
    """性能日志记录器"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.timers = {}
    
    def start_timer(self, name: str):
        """开始计时"""
        self.timers[name] = datetime.now()
    
    def end_timer(self, name: str, extra_info: Optional[Dict[str, Any]] = None):
        """结束计时并记录"""
        if name not in self.timers:
            return
        
        elapsed = (datetime.now() - self.timers[name]).total_seconds()
        
        log_data = {
            "timer_name": name,
            "elapsed_seconds": elapsed,
            "extra_info": extra_info or {}
        }
        
        # 创建带有额外字段的日志记录
        record = self.logger.makeRecord(
            self.logger.name,
            logging.INFO,
            __file__,
            0,
            f"Timer {name}: {elapsed:.3f}s",
            (),
            None
        )
        record.extra_fields = log_data
        
        self.logger.handle(record)
        
        del self.timers[name]


def setup_logging(
    log_level: str = "INFO",
    log_dir: str = DEFAULT_LOG_DIR,
    enable_console: bool = True,
    enable_file: bool = True,
    enable_json: bool = False,
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> None:
    """
    设置日志系统
    
    Args:
        log_level: 日志级别
        log_dir: 日志目录
        enable_console: 是否启用控制台输出
        enable_file: 是否启用文件输出
        enable_json: 是否使用JSON格式
        max_file_size: 最大文件大小
        backup_count: 备份文件数量
    """
    # 创建日志目录
    if enable_file:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # 清除现有处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 设置格式化器
    if enable_json:
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(DEFAULT_LOG_FORMAT)
    
    # 控制台处理器
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # 文件处理器
    if enable_file:
        # 主日志文件
        file_handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, "mercari_agent.log"),
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        # 错误日志文件
        error_handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, "errors.log"),
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root_logger.addHandler(error_handler)
    
    # 记录日志系统启动
    logger = logging.getLogger(__name__)
    logger.info(f"日志系统已启动 - 级别: {log_level}, 目录: {log_dir}")


def get_logger(name: str) -> logging.Logger:
    """
    获取日志记录器
    
    Args:
        name: 日志记录器名称
        
    Returns:
        logging.Logger: 日志记录器实例
    """
    return logging.getLogger(name)


def get_performance_logger(name: str) -> PerformanceLogger:
    """
    获取性能日志记录器
    
    Args:
        name: 日志记录器名称
        
    Returns:
        PerformanceLogger: 性能日志记录器实例
    """
    logger = get_logger(name)
    return PerformanceLogger(logger)


class LoggerMixin:
    """日志记录器混入类"""
    
    @property
    def logger(self) -> logging.Logger:
        """获取当前类的日志记录器"""
        return get_logger(self.__class__.__module__ + "." + self.__class__.__name__)
    
    def log_method_call(self, method_name: str, **kwargs):
        """记录方法调用"""
        self.logger.debug(f"调用方法 {method_name}", extra={"method_args": kwargs})
    
    def log_performance(self, operation: str, elapsed_time: float, **kwargs):
        """记录性能信息"""
        self.logger.info(
            f"性能记录 - {operation}: {elapsed_time:.3f}s",
            extra={"operation": operation, "elapsed_time": elapsed_time, **kwargs}
        )
    
    def log_error(self, error: Exception, context: Optional[Dict[str, Any]] = None):
        """记录错误信息"""
        self.logger.error(
            f"错误发生: {str(error)}",
            exc_info=True,
            extra={"error_context": context or {}}
        )


def configure_module_logging():
    """配置模块特定的日志记录"""
    # 第三方库日志级别调整
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    
    # 爬虫相关日志
    logging.getLogger("mercari_agent.scrapers").setLevel(logging.INFO)
    logging.getLogger("mercari_agent.services.scraper_service").setLevel(logging.INFO)
    
    # LLM相关日志
    logging.getLogger("mercari_agent.services.llm_service").setLevel(logging.INFO)
    
    # 分析相关日志
    logging.getLogger("mercari_agent.analyzers").setLevel(logging.DEBUG)
    logging.getLogger("mercari_agent.services.analysis_service").setLevel(logging.DEBUG)


# 模块级别的日志配置
def init_logging():
    """初始化日志系统"""
    # 从环境变量获取配置
    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_dir = os.getenv("LOG_DIR", DEFAULT_LOG_DIR)
    enable_json = os.getenv("LOG_JSON", "false").lower() == "true"
    
    # 设置日志
    setup_logging(
        log_level=log_level,
        log_dir=log_dir,
        enable_json=enable_json
    )
    
    # 配置模块日志
    configure_module_logging()


# 装饰器函数
def log_execution_time(func):
    """记录函数执行时间的装饰器"""
    import functools
    import asyncio
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        start_time = datetime.now()
        
        try:
            result = func(*args, **kwargs)
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.debug(f"函数 {func.__name__} 执行完成，耗时: {elapsed:.3f}s")
            return result
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.error(f"函数 {func.__name__} 执行失败，耗时: {elapsed:.3f}s", exc_info=True)
            raise
    
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        start_time = datetime.now()
        
        try:
            result = await func(*args, **kwargs)
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.debug(f"异步函数 {func.__name__} 执行完成，耗时: {elapsed:.3f}s")
            return result
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.error(f"异步函数 {func.__name__} 执行失败，耗时: {elapsed:.3f}s", exc_info=True)
            raise
    
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


# 上下文管理器
class LogContext:
    """日志上下文管理器"""
    
    def __init__(self, logger: logging.Logger, operation: str, **context):
        self.logger = logger
        self.operation = operation
        self.context = context
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.info(f"开始 {self.operation}", extra=self.context)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        if exc_type is None:
            self.logger.info(
                f"完成 {self.operation}，耗时: {elapsed:.3f}s",
                extra={**self.context, "elapsed_time": elapsed}
            )
        else:
            self.logger.error(
                f"失败 {self.operation}，耗时: {elapsed:.3f}s",
                exc_info=True,
                extra={**self.context, "elapsed_time": elapsed}
            )


# 初始化日志系统
init_logging()