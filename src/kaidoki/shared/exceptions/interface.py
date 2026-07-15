"""
接口异常类

定义接口层相关的异常，如API错误、认证错误等。

Author: Kaidoki Team
"""

from typing import Any, Dict, Optional
from .base import InterfaceException


class APIError(InterfaceException):
    """API错误异常"""
    
    def __init__(
        self,
        message: str = "API error",
        endpoint: Optional[str] = None,
        method: Optional[str] = None,
        status_code: int = 500,
        **kwargs
    ) -> None:
        details = {
            "endpoint": endpoint,
            "method": method,
        }
        super().__init__(message, "API_ERROR", details, status_code=status_code, **kwargs)


class AuthenticationError(InterfaceException):
    """认证错误异常"""
    
    def __init__(
        self,
        message: str = "Authentication failed",
        auth_type: Optional[str] = None,
        **kwargs
    ) -> None:
        details = {"auth_type": auth_type}
        super().__init__(message, "AUTHENTICATION_ERROR", details, status_code=401, **kwargs)


class AuthorizationError(InterfaceException):
    """授权错误异常"""
    
    def __init__(
        self,
        message: str = "Authorization failed",
        resource: Optional[str] = None,
        action: Optional[str] = None,
        **kwargs
    ) -> None:
        details = {
            "resource": resource,
            "action": action,
        }
        super().__init__(message, "AUTHORIZATION_ERROR", details, status_code=403, **kwargs)


class RateLimitError(InterfaceException):
    """限流错误异常"""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        limit: Optional[int] = None,
        reset_time: Optional[str] = None,
        **kwargs
    ) -> None:
        details = {
            "limit": limit,
            "reset_time": reset_time,
        }
        super().__init__(message, "RATE_LIMIT_ERROR", details, status_code=429, **kwargs)


class ValidationError(InterfaceException):
    """API验证错误异常"""
    
    def __init__(
        self,
        message: str = "Validation error",
        field: Optional[str] = None,
        value: Optional[Any] = None,
        **kwargs
    ) -> None:
        details = {
            "field": field,
            "value": value,
        }
        super().__init__(message, "API_VALIDATION_ERROR", details, status_code=400, **kwargs)
