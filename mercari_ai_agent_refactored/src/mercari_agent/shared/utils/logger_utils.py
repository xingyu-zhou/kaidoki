"""
日志工具模块
提供统一的日志配置和管理功能
"""

import logging
import sys
from pathlib import Path
from typing import Optional

# 全局日志配置
_logger_configured = False
_loggers = {}


def setup_logging(log_level: str = "INFO", log_dir: str = "./logs") -> None:
    """设置日志配置"""
    global _logger_configured
    
    if _logger_configured:
        return
    
    # 创建日志目录
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # 配置根日志记录器
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path / "mercari_agent.log", encoding='utf-8')
        ]
    )
    
    _logger_configured = True


def get_logger(name: str) -> logging.Logger:
    """获取日志记录器"""
    if name not in _loggers:
        _loggers[name] = logging.getLogger(name)
    return _loggers[name]