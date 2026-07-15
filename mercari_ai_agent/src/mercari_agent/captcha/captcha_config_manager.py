"""
验证码检测器配置管理器

该模块提供统一的配置管理和热更新支持，包括：
- 动态配置加载和更新
- 配置验证和校验
- 热更新通知机制
- 配置版本管理
- 性能参数调优

Author: Mercari AI Agent Team
"""

import asyncio
import json
import yaml
import logging
import os
import hashlib
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .captcha_detector_plugin import CaptchaDetectorConfig, DetectionPipeline, DetectionStageType
from .captcha_plugin_integration import CaptchaPluginConfig
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ConfigValidationResult:
    """配置验证结果"""
    valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class ConfigVersion:
    """配置版本信息"""
    version: str
    timestamp: datetime
    config_hash: str
    changes: List[str] = field(default_factory=list)
    performance_impact: str = "low"  # low, medium, high


class ConfigFileHandler(FileSystemEventHandler):
    """配置文件监控处理器"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.last_modified = {}
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        if file_path.suffix in ['.yaml', '.yml', '.json']:
            # 防止重复触发
            current_time = datetime.now()
            if file_path in self.last_modified:
                if current_time - self.last_modified[file_path] < timedelta(seconds=1):
                    return
            
            self.last_modified[file_path] = current_time
            
            # 异步处理文件更新
            asyncio.create_task(
                self.config_manager._handle_config_file_change(str(file_path))
            )


class CaptchaConfigManager:
    """
    验证码配置管理器
    
    核心功能：
    1. 统一配置管理
    2. 热更新支持
    3. 配置验证和校验
    4. 版本管理
    5. 性能参数调优
    """
    
    def __init__(self, 
                 config_dir: str = "config",
                 enable_hot_reload: bool = True,
                 enable_validation: bool = True):
        """
        初始化配置管理器
        
        Args:
            config_dir: 配置文件目录
            enable_hot_reload: 是否启用热重载
            enable_validation: 是否启用配置验证
        """
        self.config_dir = Path(config_dir)
        self.enable_hot_reload = enable_hot_reload
        self.enable_validation = enable_validation
        
        # 配置数据
        self.detector_config: Optional[CaptchaDetectorConfig] = None
        self.plugin_config: Optional[CaptchaPluginConfig] = None
        self.performance_config: Dict[str, Any] = {}
        
        # 版本管理
        self.config_versions: List[ConfigVersion] = []
        self.current_version: str = "1.0.0"
        
        # 热更新监控
        self.file_observer: Optional[Observer] = None
        self.file_handler: Optional[ConfigFileHandler] = None
        
        # 更新回调
        self.update_callbacks: Dict[str, List[Callable]] = {
            'detector_config': [],
            'plugin_config': [],
            'performance_config': []
        }
        
        # 缓存和性能
        self.config_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_timestamps: Dict[str, datetime] = {}
        
        logger.info(f"CaptchaConfigManager initialized with config_dir: {config_dir}")
    
    async def initialize(self) -> bool:
        """初始化配置管理器"""
        try:
            logger.info("Initializing CaptchaConfigManager...")
            
            # 创建配置目录
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            # 加载默认配置
            await self._load_default_configs()
            
            # 加载用户配置
            await self._load_user_configs()
            
            # 启动文件监控
            if self.enable_hot_reload:
                await self._start_file_monitoring()
            
            logger.info("CaptchaConfigManager initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize CaptchaConfigManager: {e}")
            return False
    
    async def _load_default_configs(self):
        """加载默认配置"""
        # 默认检测器配置
        self.detector_config = CaptchaDetectorConfig(
            confidence_threshold=0.6,
            enable_context_analysis=True,
            enable_debug_logging=False,
            max_processing_time=30.0,
            detection_pipeline=DetectionPipeline.STANDARD,
            enable_detection_cache=True,
            cache_ttl=300,
            max_cache_size=1000,
            enable_parallel_detection=True,
            max_concurrent_detections=5,
            detection_timeout=10.0,
            require_human_interaction=True,
            disable_auto_solving=True,
            enable_compliance_check=True
        )
        
        # 默认插件配置
        self.plugin_config = CaptchaPluginConfig(
            enable_unified_detector=True,
            enable_legacy_detector=True,
            plugin_switching_enabled=True,
            max_concurrent_detections=5,
            detection_timeout=30.0,
            enable_detection_cache=True,
            cache_ttl=300,
            confidence_threshold=0.6,
            detection_pipeline="standard",
            enable_context_analysis=True,
            enable_debug_logging=False,
            enable_hot_reload=True,
            plugin_health_check_interval=60.0,
            auto_fallback_on_failure=True,
            maintain_legacy_api=True,
            convert_results_format=True
        )
        
        # 默认性能配置
        self.performance_config = {
            'memory_optimization': {
                'enable_garbage_collection': True,
                'gc_threshold': 1000,
                'cache_cleanup_interval': 300
            },
            'processing_optimization': {
                'enable_async_processing': True,
                'thread_pool_size': 3,
                'process_pool_size': 1
            },
            'network_optimization': {
                'connection_timeout': 10,
                'read_timeout': 30,
                'max_retries': 3
            }
        }
    
    async def _load_user_configs(self):
        """加载用户配置"""
        try:
            # 检测器配置
            detector_config_file = self.config_dir / "captcha_detector.yaml"
            if detector_config_file.exists():
                user_detector_config = await self._load_config_file(detector_config_file)
                await self._merge_detector_config(user_detector_config)
            
            # 插件配置
            plugin_config_file = self.config_dir / "captcha_plugin.yaml"
            if plugin_config_file.exists():
                user_plugin_config = await self._load_config_file(plugin_config_file)
                await self._merge_plugin_config(user_plugin_config)
            
            # 性能配置
            performance_config_file = self.config_dir / "performance.yaml"
            if performance_config_file.exists():
                user_performance_config = await self._load_config_file(performance_config_file)
                await self._merge_performance_config(user_performance_config)
            
            logger.info("User configs loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load user configs: {e}")
    
    async def _load_config_file(self, file_path: Path) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_path.suffix in ['.yaml', '.yml']:
                    config = yaml.safe_load(f)
                elif file_path.suffix == '.json':
                    config = json.load(f)
                else:
                    raise ValueError(f"Unsupported config file format: {file_path.suffix}")
            
            # 缓存配置
            config_key = str(file_path)
            self.config_cache[config_key] = config
            self.cache_timestamps[config_key] = datetime.now()
            
            return config
            
        except Exception as e:
            logger.error(f"Failed to load config file {file_path}: {e}")
            return {}
    
    async def _merge_detector_config(self, user_config: Dict[str, Any]):
        """合并检测器配置"""
        if not user_config:
            return
        
        try:
            # 创建新的配置对象
            merged_config = asdict(self.detector_config)
            
            # 递归合并配置
            self._deep_merge_dict(merged_config, user_config)
            
            # 验证配置
            if self.enable_validation:
                validation_result = await self._validate_detector_config(merged_config)
                if not validation_result.valid:
                    logger.error(f"Invalid detector config: {validation_result.errors}")
                    return
            
            # 应用配置
            self.detector_config = CaptchaDetectorConfig(**merged_config)
            
            # 记录版本
            await self._record_config_version("detector_config", merged_config)
            
            logger.info("Detector config merged successfully")
            
        except Exception as e:
            logger.error(f"Failed to merge detector config: {e}")
    
    async def _merge_plugin_config(self, user_config: Dict[str, Any]):
        """合并插件配置"""
        if not user_config:
            return
        
        try:
            # 创建新的配置对象
            merged_config = asdict(self.plugin_config)
            
            # 递归合并配置
            self._deep_merge_dict(merged_config, user_config)
            
            # 验证配置
            if self.enable_validation:
                validation_result = await self._validate_plugin_config(merged_config)
                if not validation_result.valid:
                    logger.error(f"Invalid plugin config: {validation_result.errors}")
                    return
            
            # 应用配置
            self.plugin_config = CaptchaPluginConfig(**merged_config)
            
            # 记录版本
            await self._record_config_version("plugin_config", merged_config)
            
            logger.info("Plugin config merged successfully")
            
        except Exception as e:
            logger.error(f"Failed to merge plugin config: {e}")
    
    async def _merge_performance_config(self, user_config: Dict[str, Any]):
        """合并性能配置"""
        if not user_config:
            return
        
        try:
            # 深度合并性能配置
            self._deep_merge_dict(self.performance_config, user_config)
            
            # 记录版本
            await self._record_config_version("performance_config", self.performance_config)
            
            logger.info("Performance config merged successfully")
            
        except Exception as e:
            logger.error(f"Failed to merge performance config: {e}")
    
    def _deep_merge_dict(self, base_dict: Dict[str, Any], update_dict: Dict[str, Any]):
        """深度合并字典"""
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_merge_dict(base_dict[key], value)
            else:
                base_dict[key] = value
    
    async def _validate_detector_config(self, config: Dict[str, Any]) -> ConfigValidationResult:
        """验证检测器配置"""
        result = ConfigValidationResult()
        
        try:
            # 基本类型验证
            if not isinstance(config.get('confidence_threshold'), (int, float)):
                result.errors.append("confidence_threshold must be a number")
            elif not (0.0 <= config.get('confidence_threshold', 0.6) <= 1.0):
                result.errors.append("confidence_threshold must be between 0.0 and 1.0")
            
            # 超时配置验证
            if not isinstance(config.get('max_processing_time'), (int, float)):
                result.errors.append("max_processing_time must be a number")
            elif config.get('max_processing_time', 30.0) <= 0:
                result.errors.append("max_processing_time must be positive")
            
            # 流水线配置验证
            pipeline = config.get('detection_pipeline')
            if pipeline and pipeline not in [p.value for p in DetectionPipeline]:
                result.errors.append(f"Invalid detection_pipeline: {pipeline}")
            
            # 缓存配置验证
            cache_ttl = config.get('cache_ttl', 300)
            if not isinstance(cache_ttl, int) or cache_ttl <= 0:
                result.errors.append("cache_ttl must be a positive integer")
            
            # 并发配置验证
            max_concurrent = config.get('max_concurrent_detections', 5)
            if not isinstance(max_concurrent, int) or max_concurrent <= 0:
                result.errors.append("max_concurrent_detections must be a positive integer")
            
            # 性能建议
            if config.get('confidence_threshold', 0.6) < 0.5:
                result.warnings.append("Low confidence_threshold may increase false positives")
            
            if config.get('max_processing_time', 30.0) > 60:
                result.warnings.append("High max_processing_time may impact performance")
            
        except Exception as e:
            result.errors.append(f"Validation error: {str(e)}")
        
        result.valid = len(result.errors) == 0
        return result
    
    async def _validate_plugin_config(self, config: Dict[str, Any]) -> ConfigValidationResult:
        """验证插件配置"""
        result = ConfigValidationResult()
        
        try:
            # 基本启用状态验证
            if not config.get('enable_unified_detector') and not config.get('enable_legacy_detector'):
                result.errors.append("At least one detector must be enabled")
            
            # 超时配置验证
            detection_timeout = config.get('detection_timeout', 30.0)
            if not isinstance(detection_timeout, (int, float)) or detection_timeout <= 0:
                result.errors.append("detection_timeout must be a positive number")
            
            # 健康检查间隔验证
            health_check_interval = config.get('plugin_health_check_interval', 60.0)
            if health_check_interval < 10:
                result.warnings.append("Very short health_check_interval may impact performance")
            
        except Exception as e:
            result.errors.append(f"Validation error: {str(e)}")
        
        result.valid = len(result.errors) == 0
        return result
    
    async def _record_config_version(self, config_type: str, config_data: Dict[str, Any]):
        """记录配置版本"""
        try:
            config_hash = hashlib.md5(
                json.dumps(config_data, sort_keys=True).encode()
            ).hexdigest()[:8]
            
            # 检查是否有变化
            if self.config_versions:
                last_version = self.config_versions[-1]
                if last_version.config_hash == config_hash:
                    return  # 配置没有变化
            
            # 创建新版本
            version_parts = self.current_version.split('.')
            patch_version = int(version_parts[2]) + 1
            new_version = f"{version_parts[0]}.{version_parts[1]}.{patch_version}"
            
            version = ConfigVersion(
                version=new_version,
                timestamp=datetime.now(),
                config_hash=config_hash,
                changes=[f"Updated {config_type}"]
            )
            
            self.config_versions.append(version)
            self.current_version = new_version
            
            # 保持最近50个版本
            if len(self.config_versions) > 50:
                self.config_versions = self.config_versions[-50:]
            
            logger.info(f"Config version recorded: {new_version} for {config_type}")
            
        except Exception as e:
            logger.error(f"Failed to record config version: {e}")
    
    async def _start_file_monitoring(self):
        """启动文件监控"""
        try:
            self.file_handler = ConfigFileHandler(self)
            self.file_observer = Observer()
            self.file_observer.schedule(
                self.file_handler,
                str(self.config_dir),
                recursive=True
            )
            self.file_observer.start()
            
            logger.info(f"File monitoring started for: {self.config_dir}")
            
        except Exception as e:
            logger.error(f"Failed to start file monitoring: {e}")
    
    async def _handle_config_file_change(self, file_path: str):
        """处理配置文件变更"""
        try:
            logger.info(f"Config file changed: {file_path}")
            
            file_path_obj = Path(file_path)
            
            # 加载更新的配置
            updated_config = await self._load_config_file(file_path_obj)
            
            # 根据文件类型应用配置
            if "detector" in file_path_obj.name:
                await self._merge_detector_config(updated_config)
                await self._notify_config_update("detector_config", self.detector_config)
                
            elif "plugin" in file_path_obj.name:
                await self._merge_plugin_config(updated_config)
                await self._notify_config_update("plugin_config", self.plugin_config)
                
            elif "performance" in file_path_obj.name:
                await self._merge_performance_config(updated_config)
                await self._notify_config_update("performance_config", self.performance_config)
            
        except Exception as e:
            logger.error(f"Failed to handle config file change: {e}")
    
    async def _notify_config_update(self, config_type: str, new_config: Any):
        """通知配置更新"""
        callbacks = self.update_callbacks.get(config_type, [])
        
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(new_config)
                else:
                    callback(new_config)
            except Exception as e:
                logger.error(f"Config update callback error: {e}")
    
    def register_update_callback(self, config_type: str, callback: Callable):
        """注册配置更新回调"""
        if config_type in self.update_callbacks:
            self.update_callbacks[config_type].append(callback)
            logger.info(f"Registered update callback for {config_type}")
        else:
            logger.warning(f"Invalid config type for callback: {config_type}")
    
    def unregister_update_callback(self, config_type: str, callback: Callable):
        """注销配置更新回调"""
        if config_type in self.update_callbacks:
            try:
                self.update_callbacks[config_type].remove(callback)
                logger.info(f"Unregistered update callback for {config_type}")
            except ValueError:
                logger.warning(f"Callback not found for {config_type}")
    
    async def save_config(self, config_type: str, config_data: Optional[Dict[str, Any]] = None):
        """保存配置到文件"""
        try:
            if config_type == "detector_config":
                data = config_data or asdict(self.detector_config)
                file_path = self.config_dir / "captcha_detector.yaml"
                
            elif config_type == "plugin_config":
                data = config_data or asdict(self.plugin_config)
                file_path = self.config_dir / "captcha_plugin.yaml"
                
            elif config_type == "performance_config":
                data = config_data or self.performance_config
                file_path = self.config_dir / "performance.yaml"
                
            else:
                raise ValueError(f"Invalid config type: {config_type}")
            
            # 保存到文件
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
            
            logger.info(f"Config saved: {config_type} -> {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to save config {config_type}: {e}")
    
    def get_config_versions(self) -> List[ConfigVersion]:
        """获取配置版本历史"""
        return self.config_versions.copy()
    
    async def rollback_config(self, version: str) -> bool:
        """回滚配置到指定版本"""
        try:
            # 查找指定版本
            target_version = None
            for ver in self.config_versions:
                if ver.version == version:
                    target_version = ver
                    break
            
            if not target_version:
                logger.error(f"Config version not found: {version}")
                return False
            
            # 这里需要实现实际的回滚逻辑
            # 由于版本记录中没有保存完整的配置数据，
            # 实际实现中可能需要保存配置快照
            
            logger.info(f"Config rollback to version {version} (placeholder)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rollback config: {e}")
            return False
    
    def get_config_stats(self) -> Dict[str, Any]:
        """获取配置统计信息"""
        return {
            'current_version': self.current_version,
            'total_versions': len(self.config_versions),
            'config_dir': str(self.config_dir),
            'hot_reload_enabled': self.enable_hot_reload,
            'validation_enabled': self.enable_validation,
            'cache_entries': len(self.config_cache),
            'detector_config': {
                'confidence_threshold': self.detector_config.confidence_threshold,
                'detection_pipeline': self.detector_config.detection_pipeline.value,
                'cache_enabled': self.detector_config.enable_detection_cache,
                'parallel_enabled': self.detector_config.enable_parallel_detection
            } if self.detector_config else None,
            'plugin_config': {
                'unified_detector_enabled': self.plugin_config.enable_unified_detector,
                'legacy_detector_enabled': self.plugin_config.enable_legacy_detector,
                'hot_reload_enabled': self.plugin_config.enable_hot_reload,
                'health_check_interval': self.plugin_config.plugin_health_check_interval
            } if self.plugin_config else None
        }
    
    async def shutdown(self):
        """关闭配置管理器"""
        try:
            # 停止文件监控
            if self.file_observer:
                self.file_observer.stop()
                self.file_observer.join(timeout=5)
            
            # 清理缓存
            self.config_cache.clear()
            self.cache_timestamps.clear()
            
            logger.info("CaptchaConfigManager shut down successfully")
            
        except Exception as e:
            logger.error(f"Error during config manager shutdown: {e}")


# 全局配置管理器实例
_config_manager: Optional[CaptchaConfigManager] = None


def get_captcha_config_manager(config_dir: str = "config", 
                             enable_hot_reload: bool = True) -> CaptchaConfigManager:
    """获取验证码配置管理器实例"""
    global _config_manager
    
    if _config_manager is None:
        _config_manager = CaptchaConfigManager(
            config_dir=config_dir,
            enable_hot_reload=enable_hot_reload
        )
    
    return _config_manager


async def initialize_captcha_config_manager(config_dir: str = "config", 
                                          enable_hot_reload: bool = True) -> bool:
    """初始化验证码配置管理器"""
    manager = get_captcha_config_manager(config_dir, enable_hot_reload)
    return await manager.initialize()


async def shutdown_captcha_config_manager():
    """关闭验证码配置管理器"""
    global _config_manager
    
    if _config_manager:
        await _config_manager.shutdown()
        _config_manager = None