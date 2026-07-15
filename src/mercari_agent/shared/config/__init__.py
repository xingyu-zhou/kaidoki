"""
共享配置模块

提供统一的配置管理接口和应用配置。

Author: Mercari AI Agent Team
"""

from .base import (
    ConfigSource,
    EnvironmentConfigSource,
    FileConfigSource,
    DictConfigSource,
    ConfigManager,
    ConfigMetadata,
    get_global_config_manager,
    setup_global_config,
    get_config,
    get_config_int,
    get_config_bool,
    get_config_str,
)

from .app_config import (
    ApplicationConfig,
    DatabaseConfig,
    LLMConfig,
    ScrapingConfig,
    CacheConfig,
    LoggingConfig,
    SecurityConfig,
    MonitoringConfig,
    load_application_config,
    get_app_config,
    set_app_config,
    get_database_config,
    get_llm_config,
    get_scraping_config,
    get_cache_config,
    get_logging_config,
    get_security_config,
    get_monitoring_config,
    is_development,
    is_production,
    is_testing,
)

__all__ = [
    # 基础配置类
    "ConfigSource",
    "EnvironmentConfigSource",
    "FileConfigSource",
    "DictConfigSource",
    "ConfigManager",
    "ConfigMetadata",
    
    # 基础配置函数
    "get_global_config_manager",
    "setup_global_config",
    "get_config",
    "get_config_int",
    "get_config_bool",
    "get_config_str",
    
    # 应用配置类
    "ApplicationConfig",
    "DatabaseConfig",
    "LLMConfig",
    "ScrapingConfig",
    "CacheConfig",
    "LoggingConfig",
    "SecurityConfig",
    "MonitoringConfig",
    
    # 应用配置函数
    "load_application_config",
    "get_app_config",
    "set_app_config",
    "get_database_config",
    "get_llm_config",
    "get_scraping_config",
    "get_cache_config",
    "get_logging_config",
    "get_security_config",
    "get_monitoring_config",
    "is_development",
    "is_production",
    "is_testing",
]