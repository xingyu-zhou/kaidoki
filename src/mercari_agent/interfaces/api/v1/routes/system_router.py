"""
系统路由
"""

from fastapi import APIRouter
from pydantic import BaseModel
import time
import psutil
import os

from ....shared.utils.logger_utils import get_logger

logger = get_logger(__name__)

router = APIRouter()


class SystemStatus(BaseModel):
    status: str
    version: str
    uptime: float
    memory_usage: dict
    cpu_usage: float
    timestamp: float


@router.get("/system/status", response_model=SystemStatus)
async def get_system_status():
    """获取系统状态"""
    try:
        # 获取系统信息
        memory_info = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=1)
        
        return SystemStatus(
            status="healthy",
            version="2.0.0",
            uptime=time.time(),
            memory_usage={
                "total": memory_info.total,
                "used": memory_info.used,
                "percent": memory_info.percent
            },
            cpu_usage=cpu_percent,
            timestamp=time.time()
        )
    except Exception as e:
        logger.error(f"获取系统状态失败: {e}")
        return SystemStatus(
            status="error",
            version="2.0.0",
            uptime=time.time(),
            memory_usage={},
            cpu_usage=0.0,
            timestamp=time.time()
        )


@router.get("/system/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": time.time()}