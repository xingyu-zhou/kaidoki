"""
统一配置管理系统
提供运行时配置调整、A/B测试、参数调优等功能

该模块提供：
- 统一的配置管理接口
- 运行时配置热更新
- 不同场景的预设配置模式
- A/B测试配置支持
- 配置验证和健康检查
- 配置变更历史记录
"""

import asyncio
import json
import yaml
import logging
import time
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import copy
import threading
import os

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ConfigMode(Enum):
    """配置模式"""
    PRODUCTION = "production"
    DEVELOPMENT = "development"
    TESTING = "testing"
    STEALTH = "stealth"
    PERFORMANCE = "performance"
    EMERGENCY = "emergency"


class ConfigSource(Enum):
    """配置源"""
    FILE = "file"
    RUNTIME = "runtime"
    ENVIRONMENT = "environment"
    DEFAULT = "default"
    A_B_TEST = "ab_test"


@dataclass
class ConfigChange:
    """配置变更记录"""
    timestamp: datetime
    path: str
    old_value: Any
    new_value: Any
    source: ConfigSource
    user: Optional[str] = None
    reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'path': self.path,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'source': self.source.value,
            'user': self.user,
            'reason': self.reason
        }


@dataclass
class ABTestConfig:
    """A/B测试配置"""
    test_id: str
    name: str
    description: str
    enabled: bool
    traffic_percentage: float
    start_time: datetime
    end_time: datetime
    variants: Dict[str, Dict[str, Any]]
    metrics: List[str]
    
    def is_active(self) -> bool:
        """检查A/B测试是否活跃"""
        now = datetime.now()
        return self.enabled and self.start_time <= now <= self.end_time


class ConfigValidator:
    """配置验证器"""
    
    def __init__(self):
        self.validation_rules = {
            # 检测器配置验证
            'detector.confidence_threshold': self._validate_confidence,
            'detector.max_processing_time': self._validate_processing_time,
            'detector.enable_context_analysis': self._validate_boolean,
            'detector.enable_debug_logging': self._validate_boolean,
            
            # 会话管理配置验证
            'session_management.request_intervals.min_interval': self._validate_interval,
            'session_management.request_intervals.max_interval': self._validate_interval,
            'session_management.timeouts.connection_timeout': self._validate_timeout,
            'session_management.timeouts.read_timeout': self._validate_timeout,
            
            # 指纹管理配置验证
            'fingerprint_management.pool.max_fingerprints': self._validate_positive_int,
            'fingerprint_management.pool.rotation_interval': self._validate_positive_int,
            'fingerprint_management.pool.max_usage_count': self._validate_positive_int,
            
            # 全局配置验证
            'global.mode': self._validate_mode,
            'global.enabled': self._validate_boolean,
            'global.max_retry_attempts': self._validate_positive_int,
        }
    
    def validate_config(self, config: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        验证配置
        
        Args:
            config: 配置字典
            
        Returns:
            Dict[str, List[str]]: 验证错误，键为配置路径，值为错误列表
        """
        errors = {}
        
        def validate_recursive(obj: Any, path: str = ""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    
                    # 检查是否有特定的验证规则
                    if current_path in self.validation_rules:
                        try:
                            self.validation_rules[current_path](value)
                        except ValueError as e:
                            if current_path not in errors:
                                errors[current_path] = []
                            errors[current_path].append(str(e))
                    
                    # 递归验证
                    validate_recursive(value, current_path)
        
        validate_recursive(config)
        return errors
    
    def _validate_confidence(self, value: Any):
        """验证置信度值"""
        if not isinstance(value, (int, float)):
            raise ValueError("Confidence must be a number")
        if not 0.0 <= value <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
    
    def _validate_processing_time(self, value: Any):
        """验证处理时间"""
        if not isinstance(value, (int, float)):
            raise ValueError("Processing time must be a number")
        if value <= 0:
            raise ValueError("Processing time must be positive")
        if value > 300:  # 5分钟最大限制
            raise ValueError("Processing time cannot exceed 300 seconds")
    
    def _validate_boolean(self, value: Any):
        """验证布尔值"""
        if not isinstance(value, bool):
            raise ValueError("Value must be boolean")
    
    def _validate_interval(self, value: Any):
        """验证时间间隔"""
        if not isinstance(value, (int, float)):
            raise ValueError("Interval must be a number")
        if value < 0:
            raise ValueError("Interval cannot be negative")
        if value > 300:
            raise ValueError("Interval cannot exceed 300 seconds")
    
    def _validate_timeout(self, value: Any):
        """验证超时时间"""
        if not isinstance(value, (int, float)):
            raise ValueError("Timeout must be a number")
        if value <= 0:
            raise ValueError("Timeout must be positive")
        if value > 600:
            raise ValueError("Timeout cannot exceed 600 seconds")
    
    def _validate_positive_int(self, value: Any):
        """验证正整数"""
        if not isinstance(value, int):
            raise ValueError("Value must be an integer")
        if value <= 0:
            raise ValueError("Value must be positive")
    
    def _validate_mode(self, value: Any):
        """验证配置模式"""
        if not isinstance(value, str):
            raise ValueError("Mode must be a string")
        valid_modes = [mode.value for mode in ConfigMode]
        if value not in valid_modes:
            raise ValueError(f"Mode must be one of: {', '.join(valid_modes)}")


class UnifiedConfigManager:
    """统一配置管理器"""
    
    def __init__(self, config_dir: str = "config"):
        """
        初始化配置管理器
        
        Args:
            config_dir: 配置文件目录
        """
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        
        # 核心配置
        self._config: Dict[str, Any] = {}
        self._default_config: Dict[str, Any] = {}
        self._runtime_config: Dict[str, Any] = {}
        
        # 配置模式
        self.current_mode = ConfigMode.PRODUCTION
        self.preset_configs: Dict[ConfigMode, Dict[str, Any]] = {}
        
        # 变更管理
        self.change_history: List[ConfigChange] = []
        self.max_history_size = 1000
        
        # A/B测试
        self.ab_tests: Dict[str, ABTestConfig] = {}
        self.user_assignments: Dict[str, Dict[str, str]] = {}
        
        # 验证器
        self.validator = ConfigValidator()
        
        # 监控
        self.config_callbacks: Dict[str, List[Callable]] = {}
        self.last_reload_time = 0.0
        
        # 线程锁
        self._lock = threading.RLock()
        
        logger.info(f"UnifiedConfigManager initialized with config dir: {config_dir}")
    
    async def initialize(self):
        """初始化配置管理器"""
        try:
            # 加载默认配置
            await self._load_default_config()
            
            # 加载文件配置
            await self._load_file_configs()
            
            # 加载环境变量配置
            self._load_environment_config()
            
            # 加载预设配置
            await self._load_preset_configs()
            
            # 合并配置
            self._merge_configs()
            
            # 验证配置
            errors = self.validator.validate_config(self._config)
            if errors:
                logger.warning(f"Configuration validation errors: {errors}")
            
            logger.info("UnifiedConfigManager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize config manager: {e}")
            raise
    
    async def _load_default_config(self):
        """加载默认配置"""
        self._default_config = {
            'global': {
                'mode': 'production',
                'enabled': True,
                'debug_mode': False,
                'log_level': 'INFO',
                'max_retry_attempts': 3
            },
            'detector': {
                'confidence_threshold': 0.6,
                'enable_context_analysis': True,
                'enable_debug_logging': False,
                'max_processing_time': 30.0
            },
            'session_management': {
                'enabled': True,
                'request_intervals': {
                    'min_interval': 15.0,
                    'max_interval': 30.0,
                    'randomize': True,
                    'adaptive_intervals': True,
                    'captcha_delay_multiplier': 2.0,
                    'error_delay_multiplier': 1.5
                },
                'timeouts': {
                    'connection_timeout': 30,
                    'read_timeout': 60,
                    'total_timeout': 120
                },
                'concurrency': {
                    'max_concurrent_sessions': 3,
                    'max_connections': 10,
                    'max_connections_per_host': 3
                }
            },
            'fingerprint_management': {
                'enabled': True,
                'pool': {
                    'max_fingerprints': 100,
                    'pregenerate_count': 20,
                    'rotation_interval': 1800,
                    'max_usage_count': 50
                },
                'quality': {
                    'min_quality': 'fair'
                }
            },
            'environment_spoofing': {
                'enabled': True,
                'spoofing_level': 'standard'
            },
            'behavior_simulation': {
                'enabled': True,
                'mouse_behavior': True,
                'keyboard_behavior': True,
                'page_behavior': True
            },
            'monitoring': {
                'enabled': True,
                'metrics_retention_hours': 24,
                'error_retention_hours': 72,
                'health_check_interval': 300
            }
        }
    
    async def _load_file_configs(self):
        """加载文件配置"""
        config_files = [
            'anti_detection_config.yaml',
            'captcha_system.yaml',
            'mercari_specific.yaml'
        ]
        
        for config_file in config_files:
            config_path = self.config_dir / config_file
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        file_config = yaml.safe_load(f)
                        if file_config:
                            self._deep_merge(self._config, file_config)
                            logger.debug(f"Loaded config from {config_file}")
                except Exception as e:
                    logger.error(f"Failed to load config from {config_file}: {e}")
    
    def _load_environment_config(self):
        """从环境变量加载配置"""
        env_prefix = "MERCARI_AGENT_"
        
        for key, value in os.environ.items():
            if key.startswith(env_prefix):
                # 转换环境变量名为配置路径
                config_key = key[len(env_prefix):].lower().replace('_', '.')
                
                # 尝试转换值类型
                try:
                    if value.lower() in ['true', 'false']:
                        value = value.lower() == 'true'
                    elif value.isdigit():
                        value = int(value)
                    elif '.' in value and all(part.isdigit() for part in value.split('.')):
                        value = float(value)
                except:
                    pass
                
                # 设置配置值
                self._set_nested_value(self._config, config_key, value)
                logger.debug(f"Set config from environment: {config_key} = {value}")
    
    async def _load_preset_configs(self):
        """加载预设配置"""
        # 紧急模式配置 - 最严格的反检测设置
        self.preset_configs[ConfigMode.EMERGENCY] = {
            'detector': {
                'confidence_threshold': 0.4,  # 更低的阈值，更敏感
                'enable_context_analysis': True,
                'enable_debug_logging': True
            },
            'session_management': {
                'request_intervals': {
                    'min_interval': 30.0,  # 更长的间隔
                    'max_interval': 60.0,
                    'captcha_delay_multiplier': 3.0,
                    'error_delay_multiplier': 2.5
                }
            },
            'fingerprint_management': {
                'pool': {
                    'rotation_interval': 300,  # 更频繁的轮换
                    'max_usage_count': 10
                }
            }
        }
        
        # 隐身模式配置
        self.preset_configs[ConfigMode.STEALTH] = {
            'detector': {
                'confidence_threshold': 0.5,
                'enable_context_analysis': True
            },
            'session_management': {
                'request_intervals': {
                    'min_interval': 20.0,
                    'max_interval': 40.0,
                    'captcha_delay_multiplier': 2.5
                }
            },
            'environment_spoofing': {
                'spoofing_level': 'aggressive'
            }
        }
        
        # 性能模式配置
        self.preset_configs[ConfigMode.PERFORMANCE] = {
            'detector': {
                'confidence_threshold': 0.7,
                'enable_context_analysis': False,
                'max_processing_time': 15.0
            },
            'session_management': {
                'request_intervals': {
                    'min_interval': 10.0,
                    'max_interval': 20.0
                },
                'concurrency': {
                    'max_concurrent_sessions': 10
                }
            },
            'monitoring': {
                'metrics_retention_hours': 6
            }
        }
        
        # 开发模式配置
        self.preset_configs[ConfigMode.DEVELOPMENT] = {
            'global': {
                'debug_mode': True,
                'log_level': 'DEBUG'
            },
            'detector': {
                'enable_debug_logging': True
            },
            'monitoring': {
                'health_check_interval': 60
            }
        }
        
        # 测试模式配置
        self.preset_configs[ConfigMode.TESTING] = {
            'global': {
                'debug_mode': True
            },
            'session_management': {
                'request_intervals': {
                    'min_interval': 1.0,
                    'max_interval': 3.0
                }
            },
            'fingerprint_management': {
                'pool': {
                    'max_fingerprints': 10
                }
            }
        }
    
    def _merge_configs(self):
        """合并所有配置源"""
        with self._lock:
            # 从默认配置开始
            merged_config = copy.deepcopy(self._default_config)
            
            # 合并文件配置
            if self._config:
                self._deep_merge(merged_config, self._config)
            
            # 应用预设配置
            if self.current_mode in self.preset_configs:
                preset_config = self.preset_configs[self.current_mode]
                self._deep_merge(merged_config, preset_config)
            
            # 合并运行时配置
            if self._runtime_config:
                self._deep_merge(merged_config, self._runtime_config)
            
            self._config = merged_config
    
    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]):
        """深度合并字典"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = copy.deepcopy(value)
    
    def get_config(self, path: Optional[str] = None) -> Any:
        """
        获取配置值
        
        Args:
            path: 配置路径，如 'detector.confidence_threshold'
            
        Returns:
            配置值
        """
        with self._lock:
            if path is None:
                return copy.deepcopy(self._config)
            
            return self._get_nested_value(self._config, path)
    
    async def set_config(self, path: str, value: Any, source: ConfigSource = ConfigSource.RUNTIME,
                         user: Optional[str] = None, reason: Optional[str] = None) -> bool:
        """
        设置配置值
        
        Args:
            path: 配置路径
            value: 新值
            source: 配置源
            user: 用户
            reason: 变更原因
            
        Returns:
            bool: 是否成功
        """
        with self._lock:
            try:
                # 获取旧值
                old_value = self._get_nested_value(self._config, path)
                
                # 验证新值
                temp_config = copy.deepcopy(self._config)
                self._set_nested_value(temp_config, path, value)
                errors = self.validator.validate_config(temp_config)
                
                if errors and path in errors:
                    logger.error(f"Config validation failed for {path}: {errors[path]}")
                    return False
                
                # 设置新值
                self._set_nested_value(self._config, path, value)
                
                # 如果是运行时配置，也保存到运行时配置中
                if source == ConfigSource.RUNTIME:
                    self._set_nested_value(self._runtime_config, path, value)
                
                # 记录变更
                change = ConfigChange(
                    timestamp=datetime.now(),
                    path=path,
                    old_value=old_value,
                    new_value=value,
                    source=source,
                    user=user,
                    reason=reason
                )
                
                self.change_history.append(change)
                
                # 限制历史记录大小
                if len(self.change_history) > self.max_history_size:
                    self.change_history = self.change_history[-self.max_history_size:]
                
                # 触发回调
                await self._trigger_config_callbacks(path, old_value, value)
                
                logger.info(f"Config updated: {path} = {value} (source: {source.value})")
                return True
                
            except Exception as e:
                logger.error(f"Failed to set config {path}: {e}")
                return False
    
    async def switch_mode(self, mode: ConfigMode, user: Optional[str] = None) -> bool:
        """
        切换配置模式
        
        Args:
            mode: 新模式
            user: 用户
            
        Returns:
            bool: 是否成功
        """
        try:
            old_mode = self.current_mode
            self.current_mode = mode
            
            # 重新合并配置
            self._merge_configs()
            
            # 记录模式变更
            change = ConfigChange(
                timestamp=datetime.now(),
                path='global.mode',
                old_value=old_mode.value,
                new_value=mode.value,
                source=ConfigSource.RUNTIME,
                user=user,
                reason=f"Mode switch to {mode.value}"
            )
            
            self.change_history.append(change)
            
            # 触发回调
            await self._trigger_config_callbacks('global.mode', old_mode.value, mode.value)
            
            logger.info(f"Config mode switched from {old_mode.value} to {mode.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to switch mode to {mode.value}: {e}")
            return False
    
    async def reload_config(self) -> bool:
        """重新加载配置"""
        try:
            # 重新加载文件配置
            await self._load_file_configs()
            
            # 重新加载环境配置
            self._load_environment_config()
            
            # 重新合并配置
            self._merge_configs()
            
            # 验证配置
            errors = self.validator.validate_config(self._config)
            if errors:
                logger.warning(f"Configuration validation errors after reload: {errors}")
            
            self.last_reload_time = time.time()
            logger.info("Configuration reloaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
            return False
    
    def register_callback(self, path: str, callback: Callable):
        """
        注册配置变更回调
        
        Args:
            path: 配置路径
            callback: 回调函数
        """
        if path not in self.config_callbacks:
            self.config_callbacks[path] = []
        
        self.config_callbacks[path].append(callback)
        logger.debug(f"Registered callback for config path: {path}")
    
    async def _trigger_config_callbacks(self, path: str, old_value: Any, new_value: Any):
        """触发配置变更回调"""
        # 检查精确路径匹配
        if path in self.config_callbacks:
            for callback in self.config_callbacks[path]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(path, old_value, new_value)
                    else:
                        callback(path, old_value, new_value)
                except Exception as e:
                    logger.error(f"Error in config callback for {path}: {e}")
        
        # 检查通配符匹配
        for callback_path, callbacks in self.config_callbacks.items():
            if callback_path.endswith('*') and path.startswith(callback_path[:-1]):
                for callback in callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(path, old_value, new_value)
                        else:
                            callback(path, old_value, new_value)
                    except Exception as e:
                        logger.error(f"Error in wildcard config callback for {path}: {e}")
    
    def get_change_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取配置变更历史
        
        Args:
            limit: 限制返回数量
            
        Returns:
            List[Dict]: 变更历史
        """
        history = self.change_history[-limit:] if limit else self.change_history
        return [change.to_dict() for change in history]
    
    def export_config(self, path: Optional[str] = None) -> str:
        """
        导出配置为YAML字符串
        
        Args:
            path: 导出路径，None表示导出所有配置
            
        Returns:
            str: YAML字符串
        """
        config_to_export = self.get_config(path)
        return yaml.dump(config_to_export, default_flow_style=False, allow_unicode=True)
    
    async def save_runtime_config(self, file_path: Optional[str] = None):
        """保存运行时配置到文件"""
        if not file_path:
            file_path = self.config_dir / "runtime_config.yaml"
        
        try:
            config_path = Path(file_path)
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self._runtime_config, f, default_flow_style=False, allow_unicode=True)
            
            logger.info(f"Runtime config saved to {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to save runtime config: {e}")
    
    def _get_nested_value(self, obj: Dict[str, Any], path: str) -> Any:
        """获取嵌套字典值"""
        keys = path.split('.')
        current = obj
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current
    
    def _set_nested_value(self, obj: Dict[str, Any], path: str, value: Any):
        """设置嵌套字典值"""
        keys = path.split('.')
        current = obj
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
    
    def get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        return {
            'current_mode': self.current_mode.value,
            'last_reload_time': self.last_reload_time,
            'config_callbacks_count': sum(len(callbacks) for callbacks in self.config_callbacks.values()),
            'change_history_size': len(self.change_history),
            'runtime_config_size': len(self._runtime_config),
            'available_modes': [mode.value for mode in ConfigMode]
        }


# 全局实例
_global_config_manager: Optional[UnifiedConfigManager] = None


def get_config_manager(config_dir: str = "config") -> UnifiedConfigManager:
    """
    获取全局配置管理器实例
    
    Args:
        config_dir: 配置目录
        
    Returns:
        UnifiedConfigManager: 配置管理器实例
    """
    global _global_config_manager
    
    if _global_config_manager is None:
        _global_config_manager = UnifiedConfigManager(config_dir)
    
    return _global_config_manager


async def initialize_config_system(config_dir: str = "config"):
    """
    初始化配置系统
    
    Args:
        config_dir: 配置目录
    """
    manager = get_config_manager(config_dir)
    await manager.initialize()
    
    logger.info("Unified config system initialized")


def get_config(path: Optional[str] = None) -> Any:
    """
    获取配置值的便捷函数
    
    Args:
        path: 配置路径
        
    Returns:
        配置值
    """
    global _global_config_manager
    
    if _global_config_manager is None:
        logger.warning("Config manager not initialized, returning None")
        return None
    
    return _global_config_manager.get_config(path)


async def set_config(path: str, value: Any, user: Optional[str] = None, reason: Optional[str] = None) -> bool:
    """
    设置配置值的便捷函数
    
    Args:
        path: 配置路径
        value: 新值
        user: 用户
        reason: 变更原因
        
    Returns:
        bool: 是否成功
    """
    global _global_config_manager
    
    if _global_config_manager is None:
        logger.warning("Config manager not initialized")
        return False
    
    return await _global_config_manager.set_config(path, value, ConfigSource.RUNTIME, user, reason)