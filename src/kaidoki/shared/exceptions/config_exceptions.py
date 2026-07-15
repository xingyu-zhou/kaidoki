"""
配置异常模块

定义配置相关的异常类。

Author: Kaidoki Team (Refactored)
"""

class ConfigurationError(Exception):
    """配置错误异常"""
    pass

class ConfigValidationError(ConfigurationError):
    """配置验证错误异常"""
    pass

class MissingConfigError(ConfigurationError):
    """缺失配置错误异常"""
    pass