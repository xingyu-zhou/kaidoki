"""
服务异常模块
"""

from .base import MercariAgentException


class BaseServiceException(MercariAgentException):
    """基础服务异常"""
    
    def __init__(self, message: str, service_name: str = None, **kwargs):
        details = {"service_name": service_name} if service_name else {}
        super().__init__(message, "SERVICE_ERROR", details, **kwargs)


class ServiceInitializationError(BaseServiceException):
    """服务初始化异常"""
    
    def __init__(self, message: str, service_name: str = None, **kwargs):
        super().__init__(message, service_name, **kwargs)
        self.error_code = "SERVICE_INITIALIZATION_ERROR"


class ServiceUnavailableError(BaseServiceException):
    """服务不可用异常"""
    
    def __init__(self, message: str, service_name: str = None, **kwargs):
        super().__init__(message, service_name, **kwargs)
        self.error_code = "SERVICE_UNAVAILABLE_ERROR"