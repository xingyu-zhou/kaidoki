"""
统一配置管理系统

该模块实现了反检测系统的统一配置管理，提供：
- 集中化配置管理
- 配置热更新支持
- 配置验证和校验
- 环境配置分离
- 插件配置管理
- 配置继承和覆盖
- 配置加密和安全

核心功能：
- 多层次配置系统
- 配置热重载
- 配置变更监听
- 配置模板系统
- 配置备份和恢复
- 配置审计日志

Author: Mercari AI Agent Team
"""

import asyncio
import logging
import json
import yaml
import os
from typing import Dict, List, Optional, Any, Union, Callable, Type
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from abc import ABC, abstractmethod
import threading
from contextlib import asynccontextmanager
import hashlib
import base64
import jsonschema
from jsonschema import validate, ValidationError

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ConfigLevel(Enum):
    """配置级别枚举"""
    SYSTEM = "system"           # 系统级别配置
    ENVIRONMENT = "environment" # 环境级别配置
    APPLICATION = "application" # 应用级别配置
    PLUGIN = "plugin"          # 插件级别配置
    RUNTIME = "runtime"        # 运行时配置
    USER = "user"              # 用户级别配置


class ConfigFormat(Enum):
    """配置格式枚举"""
    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    INI = "ini"
    ENV = "env"


@dataclass
class ConfigSource:
    """配置源"""
    name: str
    source_type: str  # file, env, database, remote
    location: str
    format: ConfigFormat
    level: ConfigLevel
    priority: int = 50
    enabled: bool = True
    readonly: bool = False
    encrypted: bool = False
    last_modified: Optional[datetime] = None
    checksum: Optional[str] = None


@dataclass
class ConfigChange:
    """配置变更记录"""
    path: str
    old_value: Any
    new_value: Any
    timestamp: datetime
    source: str
    user: str = "system"
    reason: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'path': self.path,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source,
            'user': self.user,
            'reason': self.reason
        }


class ConfigValidator:
    """配置验证器"""
    
    def __init__(self):
        self.schemas: Dict[str, Dict[str, Any]] = {}
        self.validators: Dict[str, Callable] = {}
    
    def register_schema(self, config_path: str, schema: Dict[str, Any]):
        """注册配置模式"""
        self.schemas[config_path] = schema
        logger.debug(f"Registered schema for {config_path}")
    
    def register_validator(self, config_path: str, validator: Callable):
        """注册自定义验证器"""
        self.validators[config_path] = validator
        logger.debug(f"Registered validator for {config_path}")
    
    def validate_config(self, config_path: str, value: Any) -> bool:
        """验证配置值"""
        try:
            # JSON Schema验证
            if config_path in self.schemas:
                validate(instance=value, schema=self.schemas[config_path])
            
            # 自定义验证器
            if config_path in self.validators:
                return self.validators[config_path](value)
            
            return True
            
        except ValidationError as e:
            logger.error(f"Config validation failed for {config_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"Config validation error for {config_path}: {e}")
            return False


class ConfigLoader:
    """配置加载器"""
    
    def __init__(self, encryption_key: Optional[str] = None):
        self.encryption_key = encryption_key
        self.cipher = None
        if encryption_key:
            try:
                from cryptography.fernet import Fernet
                self.cipher = Fernet(encryption_key.encode())
            except ImportError:
                logger.warning("cryptography not available, encryption disabled")
    
    def load_from_file(self, source: ConfigSource) -> Dict[str, Any]:
        """从文件加载配置"""
        try:
            file_path = Path(source.location)
            if not file_path.exists():
                logger.warning(f"Config file not found: {source.location}")
                return {}
            
            # 检查文件修改时间
            stat = file_path.stat()
            last_modified = datetime.fromtimestamp(stat.st_mtime)
            
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解密（如果需要）
            if source.encrypted and self.cipher:
                try:
                    content = self.cipher.decrypt(content.encode()).decode()
                except Exception as e:
                    logger.error(f"Failed to decrypt config file {source.location}: {e}")
                    return {}
            
            # 解析配置
            config_data = self._parse_content(content, source.format)
            
            # 更新源信息
            source.last_modified = last_modified
            source.checksum = self._calculate_checksum(content)
            
            return config_data
            
        except Exception as e:
            logger.error(f"Failed to load config from {source.location}: {e}")
            return {}
    
    def load_from_env(self, source: ConfigSource) -> Dict[str, Any]:
        """从环境变量加载配置"""
        try:
            env_vars = {}
            prefix = source.location + "_" if source.location else ""
            
            for key, value in os.environ.items():
                if key.startswith(prefix):
                    config_key = key[len(prefix):].lower()
                    env_vars[config_key] = self._parse_env_value(value)
            
            return env_vars
            
        except Exception as e:
            logger.error(f"Failed to load config from environment: {e}")
            return {}
    
    def _parse_content(self, content: str, format: ConfigFormat) -> Dict[str, Any]:
        """解析配置内容"""
        if format == ConfigFormat.JSON:
            return json.loads(content)
        elif format == ConfigFormat.YAML:
            return yaml.safe_load(content)
        elif format == ConfigFormat.TOML:
            try:
                import toml
                return toml.loads(content)
            except ImportError:
                logger.warning("toml not available, using json fallback")
                return json.loads(content)
        elif format == ConfigFormat.INI:
            try:
                import configparser
                parser = configparser.ConfigParser()
                parser.read_string(content)
                return {section: dict(parser[section]) for section in parser.sections()}
            except Exception as e:
                logger.error(f"Failed to parse INI content: {e}")
                return {}
        else:
            raise ValueError(f"Unsupported config format: {format}")
    
    def _parse_env_value(self, value: str) -> Any:
        """解析环境变量值"""
        # 尝试解析为JSON
        try:
            return json.loads(value)
        except:
            pass
        
        # 尝试解析为布尔值
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        # 尝试解析为数字
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except:
            pass
        
        # 返回字符串
        return value
    
    def _calculate_checksum(self, content: str) -> str:
        """计算内容校验和"""
        return hashlib.md5(content.encode()).hexdigest()


class ConfigWatcher:
    """配置文件监视器"""
    
    def __init__(self, callback: Callable[[ConfigSource], None]):
        self.callback = callback
        self.watchers: Dict[str, Any] = {}
        self.running = False
    
    def start_watching(self, source: ConfigSource):
        """开始监视配置文件"""
        if source.source_type == "file":
            try:
                from watchdog.observers import Observer
                from watchdog.events import FileSystemEventHandler
                
                class ConfigFileHandler(FileSystemEventHandler):
                    def __init__(self, source, callback):
                        self.source = source
                        self.callback = callback
                    
                    def on_modified(self, event):
                        if not event.is_directory and event.src_path == self.source.location:
                            logger.info(f"Config file changed: {event.src_path}")
                            self.callback(self.source)
                
                observer = Observer()
                handler = ConfigFileHandler(source, self.callback)
                observer.schedule(handler, os.path.dirname(source.location), recursive=False)
                observer.start()
                
                self.watchers[source.name] = observer
                logger.info(f"Started watching config file: {source.location}")
                
            except ImportError:
                logger.warning("watchdog not available, file watching disabled")
            except Exception as e:
                logger.error(f"Failed to start watching {source.location}: {e}")
    
    def stop_watching(self, source_name: str):
        """停止监视配置文件"""
        if source_name in self.watchers:
            try:
                self.watchers[source_name].stop()
                del self.watchers[source_name]
                logger.info(f"Stopped watching config: {source_name}")
            except Exception as e:
                logger.error(f"Failed to stop watching {source_name}: {e}")
    
    def stop_all(self):
        """停止所有监视器"""
        for source_name in list(self.watchers.keys()):
            self.stop_watching(source_name)


class UnifiedConfigManager:
    """
    统一配置管理器
    
    核心功能：
    1. 多层次配置管理
    2. 配置热更新
    3. 配置验证
    4. 配置备份和恢复
    5. 配置审计日志
    """
    
    _instance: Optional['UnifiedConfigManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> 'UnifiedConfigManager':
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # 防止重复初始化
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # 配置存储
        self.configs: Dict[ConfigLevel, Dict[str, Any]] = {level: {} for level in ConfigLevel}
        self.merged_config: Dict[str, Any] = {}
        
        # 配置源管理
        self.sources: Dict[str, ConfigSource] = {}
        self.source_data: Dict[str, Dict[str, Any]] = {}
        
        # 组件
        self.loader = ConfigLoader()
        self.validator = ConfigValidator()
        self.watcher = ConfigWatcher(self._on_config_changed)
        
        # 监听器和回调
        self.change_listeners: List[Callable[[str, Any, Any], None]] = []
        self.validation_listeners: List[Callable[[str, Any, bool], None]] = []
        
        # 审计日志
        self.change_history: List[ConfigChange] = []
        self.audit_enabled = True
        self.max_history_size = 1000
        
        # 备份管理
        self.backup_configs: Dict[str, Dict[str, Any]] = {}
        self.max_backups = 10
        
        # 线程安全
        self.config_lock = threading.RLock()
        
        # 注册内置验证器和模式
        self._register_builtin_validators()
        
        logger.info("UnifiedConfigManager initialized")
    
    @classmethod
    def get_instance(cls) -> 'UnifiedConfigManager':
        """获取单例实例"""
        return cls()
    
    def add_source(self, source: ConfigSource):
        """添加配置源"""
        with self.config_lock:
            self.sources[source.name] = source
            
            # 加载配置
            config_data = self._load_source_data(source)
            if config_data:
                self.source_data[source.name] = config_data
                self._merge_configs()
                
                # 开始监视（如果支持）
                if not source.readonly:
                    self.watcher.start_watching(source)
            
            logger.info(f"Added config source: {source.name} ({source.level.value})")
    
    def remove_source(self, source_name: str):
        """移除配置源"""
        with self.config_lock:
            if source_name in self.sources:
                # 停止监视
                self.watcher.stop_watching(source_name)
                
                # 移除配置
                del self.sources[source_name]
                if source_name in self.source_data:
                    del self.source_data[source_name]
                
                # 重新合并配置
                self._merge_configs()
                
                logger.info(f"Removed config source: {source_name}")
    
    def get(self, path: str, default: Any = None) -> Any:
        """获取配置值"""
        try:
            keys = path.split('.')
            value = self.merged_config
            
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return default
            
            return value
            
        except Exception as e:
            logger.error(f"Failed to get config {path}: {e}")
            return default
    
    def set(self, path: str, value: Any, source_name: str = "runtime", user: str = "system", reason: str = ""):
        """设置配置值"""
        with self.config_lock:
            try:
                # 获取旧值
                old_value = self.get(path)
                
                # 验证新值
                if not self.validator.validate_config(path, value):
                    raise ValueError(f"Config validation failed for {path}")
                
                # 创建备份
                self._create_backup(f"before_set_{path}")
                
                # 设置配置
                keys = path.split('.')
                target_config = self.merged_config
                
                # 导航到目标位置
                for key in keys[:-1]:
                    if key not in target_config:
                        target_config[key] = {}
                    target_config = target_config[key]
                
                # 设置值
                target_config[keys[-1]] = value
                
                # 记录变更
                if self.audit_enabled:
                    change = ConfigChange(
                        path=path,
                        old_value=old_value,
                        new_value=value,
                        timestamp=datetime.now(),
                        source=source_name,
                        user=user,
                        reason=reason
                    )
                    self.change_history.append(change)
                    self._cleanup_history()
                
                # 触发监听器
                self._trigger_change_listeners(path, old_value, value)
                
                logger.debug(f"Config set: {path} = {value}")
                
            except Exception as e:
                logger.error(f"Failed to set config {path}: {e}")
                raise
    
    def update(self, config_dict: Dict[str, Any], source_name: str = "runtime", user: str = "system"):
        """批量更新配置"""
        with self.config_lock:
            try:
                # 创建备份
                self._create_backup(f"before_batch_update")
                
                # 批量更新
                for path, value in self._flatten_dict(config_dict).items():
                    self.set(path, value, source_name, user, "batch_update")
                
                logger.info(f"Batch updated {len(config_dict)} config items")
                
            except Exception as e:
                logger.error(f"Failed to batch update config: {e}")
                # 尝试恢复备份
                self.restore_backup(f"before_batch_update")
                raise
    
    def reload_source(self, source_name: str):
        """重新加载配置源"""
        with self.config_lock:
            if source_name in self.sources:
                source = self.sources[source_name]
                
                # 重新加载数据
                config_data = self._load_source_data(source)
                if config_data:
                    old_data = self.source_data.get(source_name, {})
                    self.source_data[source_name] = config_data
                    
                    # 重新合并配置
                    self._merge_configs()
                    
                    # 记录变更
                    if self.audit_enabled:
                        self._record_source_reload(source_name, old_data, config_data)
                    
                    logger.info(f"Reloaded config source: {source_name}")
                else:
                    logger.warning(f"Failed to reload config source: {source_name}")
    
    def validate_all(self) -> Dict[str, List[str]]:
        """验证所有配置"""
        errors = {}
        
        for path, value in self._flatten_dict(self.merged_config).items():
            if not self.validator.validate_config(path, value):
                if path not in errors:
                    errors[path] = []
                errors[path].append(f"Validation failed for value: {value}")
        
        return errors
    
    def get_schema(self, path: str) -> Optional[Dict[str, Any]]:
        """获取配置模式"""
        return self.validator.schemas.get(path)
    
    def register_schema(self, path: str, schema: Dict[str, Any]):
        """注册配置模式"""
        self.validator.register_schema(path, schema)
    
    def register_validator(self, path: str, validator: Callable):
        """注册配置验证器"""
        self.validator.register_validator(path, validator)
    
    def register_change_listener(self, listener: Callable[[str, Any, Any], None]):
        """注册配置变更监听器"""
        self.change_listeners.append(listener)
        logger.debug("Registered config change listener")
    
    def unregister_change_listener(self, listener: Callable[[str, Any, Any], None]):
        """注销配置变更监听器"""
        if listener in self.change_listeners:
            self.change_listeners.remove(listener)
    
    def create_backup(self, backup_name: str) -> bool:
        """创建配置备份"""
        try:
            self._create_backup(backup_name)
            return True
        except Exception as e:
            logger.error(f"Failed to create backup {backup_name}: {e}")
            return False
    
    def restore_backup(self, backup_name: str) -> bool:
        """恢复配置备份"""
        try:
            if backup_name in self.backup_configs:
                with self.config_lock:
                    # 创建当前配置的备份
                    self._create_backup(f"before_restore_{backup_name}")
                    
                    # 恢复配置
                    self.merged_config = self.backup_configs[backup_name].copy()
                    
                    # 触发监听器
                    self._trigger_change_listeners("*", None, self.merged_config)
                    
                    logger.info(f"Restored backup: {backup_name}")
                    return True
            else:
                logger.error(f"Backup not found: {backup_name}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to restore backup {backup_name}: {e}")
            return False
    
    def list_backups(self) -> List[str]:
        """列出所有备份"""
        return list(self.backup_configs.keys())
    
    def get_change_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取配置变更历史"""
        return [change.to_dict() for change in self.change_history[-limit:]]
    
    def export_config(self, format: ConfigFormat = ConfigFormat.YAML) -> str:
        """导出配置"""
        try:
            if format == ConfigFormat.JSON:
                return json.dumps(self.merged_config, indent=2, default=str)
            elif format == ConfigFormat.YAML:
                return yaml.dump(self.merged_config, default_flow_style=False)
            else:
                raise ValueError(f"Unsupported export format: {format}")
                
        except Exception as e:
            logger.error(f"Failed to export config: {e}")
            raise
    
    def import_config(self, config_data: str, format: ConfigFormat, source_name: str = "import"):
        """导入配置"""
        try:
            # 解析配置数据
            if format == ConfigFormat.JSON:
                imported_config = json.loads(config_data)
            elif format == ConfigFormat.YAML:
                imported_config = yaml.safe_load(config_data)
            else:
                raise ValueError(f"Unsupported import format: {format}")
            
            # 批量更新配置
            self.update(imported_config, source_name, "import")
            
            logger.info(f"Imported config from {format.value}")
            
        except Exception as e:
            logger.error(f"Failed to import config: {e}")
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """获取配置管理器状态"""
        return {
            'sources': len(self.sources),
            'total_configs': len(self._flatten_dict(self.merged_config)),
            'change_history_size': len(self.change_history),
            'backups': len(self.backup_configs),
            'validation_errors': len(self.validate_all()),
            'watchers_active': len(self.watcher.watchers),
            'listeners': len(self.change_listeners)
        }
    
    # ========================
    # 私有方法
    # ========================
    
    def _load_source_data(self, source: ConfigSource) -> Dict[str, Any]:
        """加载配置源数据"""
        try:
            if source.source_type == "file":
                return self.loader.load_from_file(source)
            elif source.source_type == "env":
                return self.loader.load_from_env(source)
            else:
                logger.warning(f"Unsupported source type: {source.source_type}")
                return {}
                
        except Exception as e:
            logger.error(f"Failed to load source {source.name}: {e}")
            return {}
    
    def _merge_configs(self):
        """合并所有配置源"""
        # 按优先级排序源
        sorted_sources = sorted(
            self.sources.items(),
            key=lambda x: (x[1].level.value, x[1].priority)
        )
        
        # 合并配置
        merged = {}
        for source_name, source in sorted_sources:
            if source.enabled and source_name in self.source_data:
                source_config = self.source_data[source_name]
                merged = self._deep_merge(merged, source_config)
        
        self.merged_config = merged
        logger.debug("Merged all config sources")
    
    def _deep_merge(self, base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
        """深度合并字典"""
        result = base.copy()
        
        for key, value in overlay.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _flatten_dict(self, d: Dict[str, Any], parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
        """扁平化字典"""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep).items())
            else:
                items.append((new_key, v))
        return dict(items)
    
    def _on_config_changed(self, source: ConfigSource):
        """配置文件变更回调"""
        logger.info(f"Config source changed: {source.name}")
        
        try:
            # 重新加载配置
            self.reload_source(source.name)
            
        except Exception as e:
            logger.error(f"Failed to handle config change for {source.name}: {e}")
    
    def _trigger_change_listeners(self, path: str, old_value: Any, new_value: Any):
        """触发配置变更监听器"""
        for listener in self.change_listeners:
            try:
                listener(path, old_value, new_value)
            except Exception as e:
                logger.error(f"Config change listener error: {e}")
    
    def _create_backup(self, backup_name: str):
        """创建配置备份"""
        with self.config_lock:
            # 清理旧备份
            if len(self.backup_configs) >= self.max_backups:
                oldest_backup = min(self.backup_configs.keys())
                del self.backup_configs[oldest_backup]
            
            # 创建新备份
            self.backup_configs[backup_name] = self.merged_config.copy()
            logger.debug(f"Created backup: {backup_name}")
    
    def _cleanup_history(self):
        """清理变更历史"""
        if len(self.change_history) > self.max_history_size:
            self.change_history = self.change_history[-self.max_history_size:]
    
    def _record_source_reload(self, source_name: str, old_data: Dict[str, Any], new_data: Dict[str, Any]):
        """记录配置源重载"""
        if self.audit_enabled:
            change = ConfigChange(
                path=f"source.{source_name}",
                old_value=old_data,
                new_value=new_data,
                timestamp=datetime.now(),
                source=source_name,
                user="system",
                reason="source_reload"
            )
            self.change_history.append(change)
    
    def _register_builtin_validators(self):
        """注册内置验证器"""
        # 注册常用配置的验证器
        self.register_validator("global.mode", lambda x: x in ["strict", "balanced", "performance", "stealth"])
        self.register_validator("detector.confidence_threshold", lambda x: 0.0 <= x <= 1.0)
        self.register_validator("session_management.max_sessions", lambda x: isinstance(x, int) and x > 0)
        self.register_validator("fingerprint_management.pool.max_fingerprints", lambda x: isinstance(x, int) and x > 0)
        
        # 注册常用配置的JSON Schema
        self.register_schema("global", {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["strict", "balanced", "performance", "stealth"]},
                "enabled": {"type": "boolean"},
                "debug_mode": {"type": "boolean"},
                "max_retry_attempts": {"type": "integer", "minimum": 1}
            }
        })
        
        self.register_schema("detector", {
            "type": "object",
            "properties": {
                "confidence_threshold": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "enable_context_analysis": {"type": "boolean"},
                "max_processing_time": {"type": "number", "minimum": 0.1}
            }
        })


# 全局配置管理器实例
config_manager = UnifiedConfigManager.get_instance()


# 便捷函数
def get_config(path: str, default: Any = None) -> Any:
    """获取配置值的便捷函数"""
    return config_manager.get(path, default)


def set_config(path: str, value: Any, user: str = "system", reason: str = "") -> None:
    """设置配置值的便捷函数"""
    config_manager.set(path, value, "runtime", user, reason)


def load_config_file(file_path: str, level: ConfigLevel = ConfigLevel.APPLICATION, priority: int = 50) -> bool:
    """加载配置文件的便捷函数"""
    try:
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            logger.error(f"Config file not found: {file_path}")
            return False
        
        # 确定格式
        format_map = {
            '.json': ConfigFormat.JSON,
            '.yaml': ConfigFormat.YAML,
            '.yml': ConfigFormat.YAML,
            '.toml': ConfigFormat.TOML,
            '.ini': ConfigFormat.INI
        }
        
        format = format_map.get(file_path_obj.suffix.lower(), ConfigFormat.YAML)
        
        # 创建配置源
        source = ConfigSource(
            name=file_path_obj.stem,
            source_type="file",
            location=str(file_path_obj.absolute()),
            format=format,
            level=level,
            priority=priority
        )
        
        # 添加到配置管理器
        config_manager.add_source(source)
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to load config file {file_path}: {e}")
        return False


@asynccontextmanager
async def config_context(backup_name: str = None):
    """配置上下文管理器"""
    if backup_name is None:
        backup_name = f"context_{int(datetime.now().timestamp())}"
    
    # 创建备份
    config_manager.create_backup(backup_name)
    
    try:
        yield config_manager
    except Exception:
        # 出现异常时恢复配置
        config_manager.restore_backup(backup_name)
        raise