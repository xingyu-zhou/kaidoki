"""
技术异常类

定义技术相关的异常，如服务不可用、配置错误、网络错误等。

Author: Kaidoki Team
"""

from typing import Any, Dict, Optional
from .base import ApplicationException, InfrastructureException


class ServiceUnavailableError(ApplicationException):
    """服务不可用异常"""
    
    def __init__(
        self,
        message: str = "Service unavailable",
        service_name: Optional[str] = None,
        **kwargs
    ) -> None:
        details = {"service_name": service_name}
        super().__init__(message, "SERVICE_UNAVAILABLE", details, **kwargs)


class ConfigurationError(ApplicationException):
    """配置错误异常"""
    
    def __init__(
        self,
        message: str = "Configuration error",
        config_key: Optional[str] = None,
        config_value: Optional[Any] = None,
        **kwargs
    ) -> None:
        details = {
            "config_key": config_key,
            "config_value": config_value,
        }
        super().__init__(message, "CONFIGURATION_ERROR", details, **kwargs)


class DatabaseError(InfrastructureException):
    """数据库错误异常"""
    
    def __init__(
        self,
        message: str = "Database error",
        operation: Optional[str] = None,
        table: Optional[str] = None,
        **kwargs
    ) -> None:
        details = {
            "operation": operation,
            "table": table,
        }
        super().__init__(message, "DATABASE_ERROR", details, **kwargs)


class NetworkError(InfrastructureException):
    """网络错误异常"""
    
    def __init__(
        self,
        message: str = "Network error",
        url: Optional[str] = None,
        status_code: Optional[int] = None,
        **kwargs
    ) -> None:
        details = {
            "url": url,
            "status_code": status_code,
        }
        super().__init__(message, "NETWORK_ERROR", details, **kwargs)


class ExternalServiceError(InfrastructureException):
    """外部服务错误异常"""
    
    def __init__(
        self,
        message: str = "External service error",
        service_name: Optional[str] = None,
        error_code: Optional[str] = None,
        **kwargs
    ) -> None:
        details = {
            "service_name": service_name,
            "external_error_code": error_code,
        }
        super().__init__(message, "EXTERNAL_SERVICE_ERROR", details, **kwargs)


class LLMServiceError(InfrastructureException):
    """LLM服务错误异常"""
    
    def __init__(
        self,
        message: str = "LLM service error",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> None:
        details = {
            "provider": provider,
            "model": model,
        }
        super().__init__(message, "LLM_SERVICE_ERROR", details, **kwargs)


class ScrapingError(InfrastructureException):
    """爬虫错误异常"""
    
    def __init__(
        self,
        message: str = "Scraping error",
        url: Optional[str] = None,
        scraper_type: Optional[str] = None,
        **kwargs
    ) -> None:
        details = {
            "url": url,
            "scraper_type": scraper_type,
        }
        super().__init__(message, "SCRAPING_ERROR", details, **kwargs)


class CaptchaError(InfrastructureException):
    """验证码错误异常"""
    
    def __init__(
        self,
        message: str = "Captcha error",
        captcha_type: Optional[str] = None,
        **kwargs
    ) -> None:
        details = {"captcha_type": captcha_type}
        super().__init__(message, "CAPTCHA_ERROR", details, **kwargs)


class PluginError(ApplicationException):
    """插件错误异常"""
    
    def __init__(
        self,
        message: str = "Plugin error",
        plugin_name: Optional[str] = None,
        plugin_version: Optional[str] = None,
        **kwargs
    ) -> None:
        details = {
            "plugin_name": plugin_name,
            "plugin_version": plugin_version,
        }
        super().__init__(message, "PLUGIN_ERROR", details, **kwargs)


class ToolExecutionError(ApplicationException):
    """工具执行错误异常"""
    
    def __init__(
        self,
        message: str = "Tool execution error",
        tool_name: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> None:
        details = {
            "tool_name": tool_name,
            "parameters": parameters or {},
        }
        super().__init__(message, "TOOL_EXECUTION_ERROR", details, **kwargs)
