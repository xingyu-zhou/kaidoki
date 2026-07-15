"""
基础配置模块 - 最简版本
"""

from typing import Dict, Any, Optional
from enum import Enum


class ConfigSource(Enum):
    """配置源类型"""
    ENVIRONMENT = "environment"
    FILE = "file" 
    DICT = "dict"


class EnvironmentConfigSource:
    """环境变量配置源"""
    def __init__(self):
        pass
    
    def load(self) -> Dict[str, Any]:
        import os
        return dict(os.environ)


class FileConfigSource:
    """文件配置源"""
    def __init__(self, filepath: str):
        self.filepath = filepath
    
    def load(self) -> Dict[str, Any]:
        return {}


class DictConfigSource:
    """字典配置源"""
    def __init__(self, data: Dict[str, Any]):
        self.data = data
    
    def load(self) -> Dict[str, Any]:
        return self.data


class ConfigMetadata:
    """配置元数据"""
    def __init__(self, key: str, value: Any, source: str = "unknown"):
        self.key = key
        self.value = value
        self.source = source


class ConfigManager:
    """配置管理器 - 最简版本"""
    def __init__(self):
        self.data = {}
    
    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)
    
    def set(self, key: str, value: Any):
        self.data[key] = value


# 全局配置管理器
_global_config_manager = None


def get_global_config_manager() -> ConfigManager:
    global _global_config_manager
    if _global_config_manager is None:
        _global_config_manager = ConfigManager()
    return _global_config_manager


def setup_global_config(config_data: Dict[str, Any]):
    """设置全局配置"""
    manager = get_global_config_manager()
    for key, value in config_data.items():
        manager.set(key, value)


def get_config(key: str, default: Any = None) -> Any:
    """获取配置"""
    return get_global_config_manager().get(key, default)


def get_config_int(key: str, default: int = 0) -> int:
    """获取整数配置"""
    value = get_config(key, default)
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def get_config_bool(key: str, default: bool = False) -> bool:
    """获取布尔配置"""
    value = get_config(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes', 'on')
    return default


def get_config_str(key: str, default: str = "") -> str:
    """获取字符串配置"""
    value = get_config(key, default)
    return str(value) if value is not None else default