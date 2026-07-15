"""
基础异常类

定义系统中所有异常的基类和主要异常类别。
遵循异常层次结构设计，便于异常处理和错误追踪。

Author: Mercari AI Agent Team
"""

from typing import Any, Dict, Optional, Union
import traceback
from datetime import datetime


class MercariAgentException(Exception):
    """
    Mercari AI Agent 系统基础异常类
    
    所有系统异常的基类，提供统一的异常处理接口。
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ) -> None:
        """
        初始化异常
        
        Args:
            message: 错误消息
            error_code: 错误代码
            details: 错误详细信息
            cause: 原始异常
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.cause = cause
        self.timestamp = datetime.now()
        self.traceback_info = traceback.format_exc() if cause else None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "traceback": self.traceback_info,
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"[{self.error_code}] {self.message}"
    
    def __repr__(self) -> str:
        """详细字符串表示"""
        return (
            f"{self.__class__.__name__}("
            f"message='{self.message}', "
            f"error_code='{self.error_code}', "
            f"details={self.details})"
        )


class DomainException(MercariAgentException):
    """
    领域异常基类
    
    用于表示业务领域中的异常情况，如业务规则违反、验证失败等。
    这类异常通常是可预期的，需要向用户提供友好的错误信息。
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ) -> None:
        super().__init__(message, error_code, details, cause)
        self.category = "domain"


class ApplicationException(MercariAgentException):
    """
    应用异常基类
    
    用于表示应用层的异常情况，如服务不可用、配置错误等。
    这类异常通常需要系统管理员介入处理。
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ) -> None:
        super().__init__(message, error_code, details, cause)
        self.category = "application"


class InfrastructureException(MercariAgentException):
    """
    基础设施异常基类
    
    用于表示基础设施层的异常情况，如数据库连接失败、网络错误等。
    这类异常通常是临时性的，可以通过重试解决。
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        is_retryable: bool = True,
    ) -> None:
        super().__init__(message, error_code, details, cause)
        self.category = "infrastructure"
        self.is_retryable = is_retryable


class InterfaceException(MercariAgentException):
    """
    接口异常基类
    
    用于表示接口层的异常情况，如API调用失败、认证错误等。
    这类异常通常需要向客户端返回适当的HTTP状态码。
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        status_code: int = 500,
    ) -> None:
        super().__init__(message, error_code, details, cause)
        self.category = "interface"
        self.status_code = status_code


# 异常工厂函数
def create_exception(
    exception_type: str,
    message: str,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    cause: Optional[Exception] = None,
    **kwargs: Any,
) -> MercariAgentException:
    """
    异常工厂函数
    
    根据异常类型创建相应的异常实例。
    
    Args:
        exception_type: 异常类型 (domain, application, infrastructure, interface)
        message: 错误消息
        error_code: 错误代码
        details: 错误详细信息
        cause: 原始异常
        **kwargs: 其他参数
    
    Returns:
        相应的异常实例
    """
    exception_classes = {
        "domain": DomainException,
        "application": ApplicationException,
        "infrastructure": InfrastructureException,
        "interface": InterfaceException,
    }
    
    exception_class = exception_classes.get(exception_type, MercariAgentException)
    return exception_class(message, error_code, details, cause, **kwargs)


# 异常处理装饰器
def handle_exceptions(
    exception_types: Union[Exception, tuple] = Exception,
    default_message: str = "An unexpected error occurred",
    reraise: bool = True,
):
    """
    异常处理装饰器
    
    用于统一处理函数中的异常。
    
    Args:
        exception_types: 要捕获的异常类型
        default_message: 默认错误消息
        reraise: 是否重新抛出异常
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exception_types as e:
                if isinstance(e, MercariAgentException):
                    if reraise:
                        raise
                    return None
                
                # 将普通异常转换为系统异常
                system_exception = MercariAgentException(
                    message=str(e) or default_message,
                    cause=e,
                )
                
                if reraise:
                    raise system_exception
                return None
        
        return wrapper
    return decorator
