"""
系统相关的API数据模型

定义系统状态、监控和管理功能的请求和响应模型。

功能：
- 系统状态响应模型
- 健康检查响应模型
- 服务指标响应模型
- 配置响应模型
- 数据验证和序列化

Author: Mercari AI Agent Team (Refactored)
"""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from enum import Enum
import time


class HealthStatus(str, Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ServiceStatus(str, Enum):
    """服务状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNAVAILABLE = "unavailable"


class HealthCheckResponse(BaseModel):
    """健康检查响应模型"""
    status: HealthStatus = Field(..., description="整体健康状态")
    timestamp: float = Field(..., description="检查时间戳")
    services: Dict[str, str] = Field(..., description="各服务状态")
    issues: List[str] = Field(default_factory=list, description="发现的问题")
    uptime: Optional[float] = Field(None, description="运行时间（秒）")
    
    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": 1640995200.0,
                "services": {
                    "query_parser": "healthy",
                    "recommendation": "healthy",
                    "llm": "healthy",
                    "scraper": "healthy"
                },
                "issues": [],
                "uptime": 3600.0
            }
        }


class SystemResourceInfo(BaseModel):
    """系统资源信息模型"""
    cpu: Dict[str, Union[float, int]] = Field(..., description="CPU信息")
    memory: Dict[str, Union[float, int]] = Field(..., description="内存信息")
    disk: Dict[str, Union[float, int]] = Field(..., description="磁盘信息")
    
    class Config:
        schema_extra = {
            "example": {
                "cpu": {
                    "percent": 25.5,
                    "count": 8
                },
                "memory": {
                    "total": 16777216000,
                    "available": 8388608000,
                    "percent": 50.0,
                    "used": 8388608000
                },
                "disk": {
                    "total": 1000000000000,
                    "free": 500000000000,
                    "used": 500000000000,
                    "percent": 50.0
                }
            }
        }


class ProcessInfo(BaseModel):
    """进程信息模型"""
    pid: int = Field(..., description="进程ID")
    memory_info: Dict[str, int] = Field(..., description="内存信息")
    cpu_percent: float = Field(..., description="CPU使用率")
    create_time: float = Field(..., description="创建时间")
    num_threads: int = Field(..., description="线程数")
    
    class Config:
        schema_extra = {
            "example": {
                "pid": 12345,
                "memory_info": {
                    "rss": 104857600,
                    "vms": 209715200
                },
                "cpu_percent": 5.2,
                "create_time": 1640991600.0,
                "num_threads": 15
            }
        }


class ServiceStatistics(BaseModel):
    """服务统计信息模型"""
    status: str = Field(..., description="服务状态")
    total_requests: Optional[int] = Field(None, description="总请求数")
    success_rate: Optional[float] = Field(None, description="成功率")
    average_response_time: Optional[float] = Field(None, description="平均响应时间")
    last_activity: Optional[float] = Field(None, description="最后活动时间")
    
    class Config:
        schema_extra = {
            "example": {
                "status": "active",
                "total_requests": 1500,
                "success_rate": 0.95,
                "average_response_time": 150.5,
                "last_activity": 1640995200.0
            }
        }


class SystemStatusResponse(BaseModel):
    """系统状态响应模型"""
    uptime: float = Field(..., description="运行时间（秒）")
    system_resources: SystemResourceInfo = Field(..., description="系统资源信息")
    process_info: ProcessInfo = Field(..., description="进程信息")
    service_statistics: Dict[str, Any] = Field(..., description="服务统计")
    configuration: Dict[str, Any] = Field(..., description="配置信息")
    timestamp: float = Field(..., description="状态时间戳")
    
    class Config:
        schema_extra = {
            "example": {
                "uptime": 3600.0,
                "system_resources": {},
                "process_info": {},
                "service_statistics": {},
                "configuration": {
                    "environment": "development",
                    "debug": True,
                    "version": "2.0.0"
                },
                "timestamp": 1640995200.0
            }
        }


class ResponseTimeMetrics(BaseModel):
    """响应时间指标模型"""
    average: float = Field(..., description="平均响应时间")
    p50: float = Field(..., description="50%分位数")
    p90: float = Field(..., description="90%分位数")
    p95: float = Field(..., description="95%分位数")
    p99: float = Field(..., description="99%分位数")
    
    class Config:
        schema_extra = {
            "example": {
                "average": 150.5,
                "p50": 120.0,
                "p90": 250.0,
                "p95": 400.0,
                "p99": 800.0
            }
        }


class EndpointStatistics(BaseModel):
    """端点统计信息模型"""
    count: int = Field(..., description="请求次数")
    avg_time: float = Field(..., description="平均响应时间")
    error_count: Optional[int] = Field(0, description="错误次数")
    last_accessed: Optional[float] = Field(None, description="最后访问时间")
    
    class Config:
        schema_extra = {
            "example": {
                "count": 450,
                "avg_time": 180.2,
                "error_count": 5,
                "last_accessed": 1640995200.0
            }
        }


class ErrorInfo(BaseModel):
    """错误信息模型"""
    timestamp: float = Field(..., description="错误时间戳")
    error_type: str = Field(..., description="错误类型")
    message: str = Field(..., description="错误消息")
    endpoint: Optional[str] = Field(None, description="相关端点")
    count: Optional[int] = Field(1, description="错误次数")
    
    class Config:
        schema_extra = {
            "example": {
                "timestamp": 1640995200.0,
                "error_type": "ValidationError",
                "message": "Invalid input data",
                "endpoint": "/api/v1/search",
                "count": 3
            }
        }


class ServiceMetricsResponse(BaseModel):
    """服务指标响应模型"""
    total_requests: int = Field(..., description="总请求数")
    error_count: int = Field(..., description="错误总数")
    error_rate: float = Field(..., description="错误率")
    response_times: ResponseTimeMetrics = Field(..., description="响应时间指标")
    endpoint_statistics: Dict[str, EndpointStatistics] = Field(..., description="端点统计")
    recent_errors: List[ErrorInfo] = Field(default_factory=list, description="最近错误")
    collected_at: float = Field(..., description="收集时间戳")
    
    class Config:
        schema_extra = {
            "example": {
                "total_requests": 1000,
                "error_count": 25,
                "error_rate": 0.025,
                "response_times": {
                    "average": 150.5,
                    "p50": 120.0,
                    "p90": 250.0,
                    "p95": 400.0,
                    "p99": 800.0
                },
                "endpoint_statistics": {},
                "recent_errors": [],
                "collected_at": 1640995200.0
            }
        }


class ConfigurationInfo(BaseModel):
    """配置信息模型"""
    environment: str = Field(..., description="环境")
    debug: bool = Field(..., description="调试模式")
    api: Dict[str, Any] = Field(..., description="API配置")
    logging: Dict[str, Any] = Field(..., description="日志配置")
    llm: Dict[str, Any] = Field(..., description="LLM配置")
    scraping: Dict[str, Any] = Field(..., description="爬虫配置")
    
    class Config:
        schema_extra = {
            "example": {
                "environment": "development",
                "debug": True,
                "api": {
                    "host": "localhost",
                    "port": 8000,
                    "rate_limit": 60
                },
                "logging": {
                    "level": "INFO",
                    "log_dir": "logs"
                },
                "llm": {
                    "default_provider": "openai",
                    "timeout": 30.0
                },
                "scraping": {
                    "timeout": 10.0,
                    "max_concurrent": 5
                }
            }
        }


class ConfigResponse(BaseModel):
    """配置响应模型"""
    environment: str = Field(..., description="环境")
    debug_mode: bool = Field(..., description="调试模式")
    configuration: Dict[str, Any] = Field(..., description="配置信息")
    loaded_at: float = Field(..., description="加载时间戳")
    
    class Config:
        schema_extra = {
            "example": {
                "environment": "development",
                "debug_mode": True,
                "configuration": {},
                "loaded_at": 1640995200.0
            }
        }


class AlertLevel(str, Enum):
    """告警级别枚举"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class SystemAlert(BaseModel):
    """系统告警模型"""
    level: AlertLevel = Field(..., description="告警级别")
    message: str = Field(..., description="告警消息")
    source: str = Field(..., description="告警来源")
    timestamp: float = Field(..., description="告警时间戳")
    resolved: bool = Field(False, description="是否已解决")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    
    class Config:
        schema_extra = {
            "example": {
                "level": "warning",
                "message": "High memory usage detected",
                "source": "system_monitor",
                "timestamp": 1640995200.0,
                "resolved": False,
                "metadata": {
                    "memory_percent": 85.5,
                    "threshold": 80.0
                }
            }
        }


class PerformanceMetrics(BaseModel):
    """性能指标模型"""
    requests_per_second: float = Field(..., description="每秒请求数")
    average_response_time: float = Field(..., description="平均响应时间")
    throughput: float = Field(..., description="吞吐量")
    concurrent_users: int = Field(..., description="并发用户数")
    cache_hit_rate: float = Field(..., description="缓存命中率")
    
    class Config:
        schema_extra = {
            "example": {
                "requests_per_second": 25.5,
                "average_response_time": 150.2,
                "throughput": 1000.0,
                "concurrent_users": 50,
                "cache_hit_rate": 0.85
            }
        }


class SystemLog(BaseModel):
    """系统日志模型"""
    level: str = Field(..., description="日志级别")
    message: str = Field(..., description="日志消息")
    timestamp: float = Field(..., description="时间戳")
    module: str = Field(..., description="模块名称")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    
    class Config:
        schema_extra = {
            "example": {
                "level": "INFO",
                "message": "API request processed successfully",
                "timestamp": 1640995200.0,
                "module": "api.search",
                "metadata": {
                    "endpoint": "/api/v1/search",
                    "response_time": 150.2
                }
            }
        }


class MaintenanceMode(BaseModel):
    """维护模式模型"""
    enabled: bool = Field(..., description="是否启用维护模式")
    start_time: Optional[float] = Field(None, description="开始时间")
    end_time: Optional[float] = Field(None, description="结束时间")
    message: Optional[str] = Field(None, description="维护消息")
    affected_services: List[str] = Field(default_factory=list, description="受影响的服务")
    
    class Config:
        schema_extra = {
            "example": {
                "enabled": True,
                "start_time": 1640995200.0,
                "end_time": 1640998800.0,
                "message": "System maintenance in progress",
                "affected_services": ["search", "recommendation"]
            }
        }