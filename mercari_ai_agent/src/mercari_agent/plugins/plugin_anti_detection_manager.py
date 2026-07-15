"""
插件化反检测管理器

该模块是基于新插件框架的完全重写版本的反检测管理器，提供：
- 完全插件化的架构
- 统一的插件生命周期管理
- 动态插件加载和热插拔
- 高性能异步处理
- 全面的监控和统计
- 完全向后兼容的API

这是对原有AntiDetectionManager和EnhancedAntiDetectionManager的重大升级。

Author: Mercari AI Agent Team
"""

import asyncio
import time
import weakref
from typing import Dict, List, Optional, Any, Union, Callable, Type
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

from .framework import PluginFramework, FrameworkConfig, FrameworkStats
from .interfaces import (
    IPlugin, ISessionManagementPlugin, IFingerprintPlugin, 
    IBehaviorSimulationPlugin, IAntiDetectionPlugin, ICaptchaDetectionPlugin,
    PluginType, PluginCapability
)
from .registry import PluginRegistry
from .loader import PluginLoader
from .lifecycle import PluginLifecycleManager
from .config_manager import PluginConfigManager
from .session_plugin import SessionManagementPlugin
from .fingerprint_plugin import FingerprintPlugin
from .behavior_plugin import BehaviorSimulationPlugin

# 向后兼容导入
from ..captcha.plugin_interface import PluginStatus, PluginPriority, PluginCategory
from ..captcha.unified_captcha_detector import UnifiedCaptchaDetector, UnifiedDetectionResult
from ..captcha.captcha_types import CaptchaType, CaptchaDetectionResult
from ..captcha.anti_detection_manager import DetectionMode, SystemStatus, AntiDetectionStats, RequestMetrics
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ManagerOperationMode(Enum):
    """管理器操作模式"""
    FULL_PLUGIN = "full_plugin"        # 完全插件模式
    HYBRID = "hybrid"                  # 混合模式（插件+原有组件）
    COMPATIBILITY = "compatibility"    # 兼容模式（主要使用原有组件）


@dataclass
class PluginManagerConfig:
    """插件管理器配置"""
    # 操作模式
    operation_mode: ManagerOperationMode = ManagerOperationMode.HYBRID
    
    # 框架配置
    max_plugins: int = 50
    plugin_timeout: float = 30.0
    enable_hot_reload: bool = True
    enable_performance_monitoring: bool = True
    
    # 组件配置
    enable_session_management: bool = True
    enable_fingerprint_management: bool = True
    enable_behavior_simulation: bool = True
    enable_captcha_detection: bool = True
    enable_environment_spoofing: bool = True
    
    # 性能配置
    max_concurrent_operations: int = 20
    request_timeout: float = 120.0
    health_check_interval: float = 300.0
    
    # 兼容性配置
    fallback_to_legacy: bool = True
    legacy_timeout: float = 60.0
    
    # 存储配置
    config_storage_enabled: bool = True
    metrics_storage_enabled: bool = True
    
    def to_framework_config(self) -> FrameworkConfig:
        """转换为框架配置"""
        return FrameworkConfig(
            max_plugins=self.max_plugins,
            plugin_timeout=self.plugin_timeout,
            enable_hot_reload=self.enable_hot_reload,
            enable_performance_monitoring=self.enable_performance_monitoring,
            max_concurrent_operations=self.max_concurrent_operations,
            health_check_interval=self.health_check_interval
        )


@dataclass
class PluginManagerStats:
    """插件管理器统计"""
    # 基础统计
    total_plugins: int = 0
    active_plugins: int = 0
    failed_plugins: int = 0
    
    # 操作统计
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    average_operation_time: float = 0.0
    
    # 组件统计
    session_operations: int = 0
    fingerprint_operations: int = 0
    behavior_operations: int = 0
    captcha_detections: int = 0
    
    # 性能统计
    uptime: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    
    # 兼容性统计
    legacy_fallbacks: int = 0
    plugin_reloads: int = 0
    
    def update_operation_stats(self, success: bool, operation_time: float):
        """更新操作统计"""
        self.total_operations += 1
        if success:
            self.successful_operations += 1
        else:
            self.failed_operations += 1
        
        # 更新平均操作时间
        if self.total_operations > 0:
            current_total = self.average_operation_time * (self.total_operations - 1)
            self.average_operation_time = (current_total + operation_time) / self.total_operations


class PluginAntiDetectionManager:
    """
    插件化反检测管理器
    
    核心功能：
    1. 完全基于插件架构的反检测系统
    2. 动态插件管理和热插拔
    3. 高性能异步处理
    4. 全面的监控和统计
    5. 完全向后兼容
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化插件化反检测管理器
        
        Args:
            config: 配置字典
        """
        self.config = self._load_manager_config(config or {})
        self.status = SystemStatus.INITIALIZING
        self.start_time = time.time()
        
        # 插件框架
        framework_config = self.config.to_framework_config()
        self.plugin_framework = PluginFramework.get_instance(framework_config)
        
        # 核心插件管理组件
        self.plugin_registry: Optional[PluginRegistry] = None
        self.plugin_loader: Optional[PluginLoader] = None
        self.lifecycle_manager: Optional[PluginLifecycleManager] = None
        self.config_manager: Optional[PluginConfigManager] = None
        
        # 组件插件实例
        self.session_plugin: Optional[SessionManagementPlugin] = None
        self.fingerprint_plugin: Optional[FingerprintPlugin] = None
        self.behavior_plugin: Optional[BehaviorSimulationPlugin] = None
        self.captcha_plugin: Optional[ICaptchaDetectionPlugin] = None
        
        # 向后兼容组件（当插件不可用时的后备）
        self.legacy_components: Dict[str, Any] = {}
        
        # 统计和监控
        self.stats = PluginManagerStats()
        self.framework_stats: Optional[FrameworkStats] = None
        
        # 事件处理
        self.event_callbacks: Dict[str, List[Callable]] = {
            'plugin_loaded': [],
            'plugin_unloaded': [],
            'operation_completed': [],
            'error_occurred': [],
            'fallback_activated': []
        }
        
        # 监控任务
        self.monitoring_tasks: List[asyncio.Task] = []
        
        # 框架引用（用于插件）
        self._framework_ref = weakref.ref(self)
        
        logger.info(f"PluginAntiDetectionManager initialized with mode: {self.config.operation_mode.value}")
    
    def _load_manager_config(self, config: Dict[str, Any]) -> PluginManagerConfig:
        """加载管理器配置"""
        manager_config = PluginManagerConfig()
        
        # 加载配置
        for key, value in config.items():
            if hasattr(manager_config, key):
                setattr(manager_config, key, value)
        
        return manager_config
    
    async def initialize(self):
        """初始化管理器"""
        try:
            logger.info("Initializing PluginAntiDetectionManager...")
            self.status = SystemStatus.INITIALIZING
            
            # 1. 初始化插件框架
            await self.plugin_framework.initialize()
            
            # 2. 初始化核心组件
            await self._initialize_core_components()
            
            # 3. 根据操作模式初始化组件
            if self.config.operation_mode == ManagerOperationMode.FULL_PLUGIN:
                await self._initialize_full_plugin_mode()
            elif self.config.operation_mode == ManagerOperationMode.HYBRID:
                await self._initialize_hybrid_mode()
            else:  # COMPATIBILITY
                await self._initialize_compatibility_mode()
            
            # 4. 启动监控任务
            await self._start_monitoring_tasks()
            
            self.status = SystemStatus.READY
            logger.info("PluginAntiDetectionManager initialized successfully")
            
        except Exception as e:
            self.status = SystemStatus.ERROR
            logger.error(f"Failed to initialize PluginAntiDetectionManager: {e}")
            raise
    
    async def _initialize_core_components(self):
        """初始化核心组件"""
        # 获取框架组件的引用
        self.plugin_registry = self.plugin_framework.plugin_registry
        self.plugin_loader = self.plugin_framework.plugin_loader
        self.lifecycle_manager = self.plugin_framework.lifecycle_manager
        self.config_manager = self.plugin_framework.config_manager
        
        logger.info("Core plugin components initialized")
    
    async def _initialize_full_plugin_mode(self):
        """初始化完全插件模式"""
        try:
            logger.info("Initializing full plugin mode...")
            
            # 注册和加载所有插件
            await self._register_and_load_plugins()
            
            logger.info("Full plugin mode initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize full plugin mode: {e}")
            if self.config.fallback_to_legacy:
                logger.info("Falling back to hybrid mode")
                await self._initialize_hybrid_mode()
            else:
                raise
    
    async def _initialize_hybrid_mode(self):
        """初始化混合模式"""
        try:
            logger.info("Initializing hybrid mode...")
            
            # 优先尝试加载插件，失败时使用原有组件
            plugin_load_results = await self._register_and_load_plugins()
            
            # 为失败的插件初始化原有组件
            await self._initialize_legacy_fallbacks(plugin_load_results)
            
            logger.info("Hybrid mode initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize hybrid mode: {e}")
            if self.config.fallback_to_legacy:
                logger.info("Falling back to compatibility mode")
                await self._initialize_compatibility_mode()
            else:
                raise
    
    async def _initialize_compatibility_mode(self):
        """初始化兼容模式"""
        try:
            logger.info("Initializing compatibility mode...")
            
            # 主要使用原有组件
            await self._initialize_all_legacy_components()
            
            # 可选加载一些插件
            try:
                await self._register_and_load_plugins()
            except Exception as e:
                logger.warning(f"Plugin loading failed in compatibility mode: {e}")
            
            logger.info("Compatibility mode initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize compatibility mode: {e}")
            raise
    
    async def _register_and_load_plugins(self) -> Dict[str, bool]:
        """注册和加载插件"""
        load_results = {}
        
        try:
            # 会话管理插件
            if self.config.enable_session_management:
                session_config = await self.config_manager.load_plugin_config("session_management_plugin")
                self.session_plugin = SessionManagementPlugin(session_config)
                success = await self.plugin_framework.load_plugin(SessionManagementPlugin, session_config)
                load_results['session'] = success
                if success:
                    self.session_plugin = await self.plugin_framework.get_plugin("session_management_plugin")
            
            # 指纹管理插件
            if self.config.enable_fingerprint_management:
                fingerprint_config = await self.config_manager.load_plugin_config("fingerprint_plugin")
                success = await self.plugin_framework.load_plugin(FingerprintPlugin, fingerprint_config)
                load_results['fingerprint'] = success
                if success:
                    self.fingerprint_plugin = await self.plugin_framework.get_plugin("fingerprint_plugin")
            
            # 行为模拟插件
            if self.config.enable_behavior_simulation:
                behavior_config = await self.config_manager.load_plugin_config("behavior_simulation_plugin")
                success = await self.plugin_framework.load_plugin(BehaviorSimulationPlugin, behavior_config)
                load_results['behavior'] = success
                if success:
                    self.behavior_plugin = await self.plugin_framework.get_plugin("behavior_simulation_plugin")
            
            # CAPTCHA检测插件（使用现有的统一检测器包装）
            if self.config.enable_captcha_detection:
                try:
                    from ..captcha.unified_captcha_detector_plugin import UnifiedCaptchaDetectorPlugin
                    captcha_config = await self.config_manager.load_plugin_config("captcha_detector_plugin")
                    success = await self.plugin_framework.load_plugin(UnifiedCaptchaDetectorPlugin, captcha_config)
                    load_results['captcha'] = success
                    if success:
                        self.captcha_plugin = await self.plugin_framework.get_plugin("captcha_detector_plugin")
                except ImportError:
                    logger.warning("CAPTCHA detector plugin not available")
                    load_results['captcha'] = False
            
            # 更新统计
            successful_loads = sum(1 for success in load_results.values() if success)
            self.stats.total_plugins = len(load_results)
            self.stats.active_plugins = successful_loads
            self.stats.failed_plugins = self.stats.total_plugins - self.stats.active_plugins
            
            logger.info(f"Plugin loading completed: {successful_loads}/{len(load_results)} successful")
            return load_results
            
        except Exception as e:
            logger.error(f"Failed to register and load plugins: {e}")
            return load_results
    
    async def _initialize_legacy_fallbacks(self, plugin_results: Dict[str, bool]):
        """初始化原有组件作为后备"""
        try:
            # 会话管理后备
            if not plugin_results.get('session', False):
                await self._initialize_legacy_session_manager()
                self.stats.legacy_fallbacks += 1
            
            # 指纹管理后备
            if not plugin_results.get('fingerprint', False):
                await self._initialize_legacy_fingerprint_manager()
                self.stats.legacy_fallbacks += 1
            
            # 行为模拟后备
            if not plugin_results.get('behavior', False):
                await self._initialize_legacy_behavior_engine()
                self.stats.legacy_fallbacks += 1
            
            # CAPTCHA检测后备
            if not plugin_results.get('captcha', False):
                await self._initialize_legacy_captcha_detector()
                self.stats.legacy_fallbacks += 1
            
            logger.info(f"Legacy fallbacks initialized: {self.stats.legacy_fallbacks}")
            
        except Exception as e:
            logger.error(f"Failed to initialize legacy fallbacks: {e}")
    
    async def _initialize_all_legacy_components(self):
        """初始化所有原有组件"""
        await self._initialize_legacy_session_manager()
        await self._initialize_legacy_fingerprint_manager()
        await self._initialize_legacy_behavior_engine()
        await self._initialize_legacy_captcha_detector()
        
        self.stats.legacy_fallbacks = 4  # 所有组件都是legacy
    
    async def _initialize_legacy_session_manager(self):
        """初始化原有会话管理器"""
        try:
            from ..scrapers.enhanced_session_manager import EnhancedSessionManager, SessionConfig
            
            config = SessionConfig()
            session_manager = EnhancedSessionManager(config)
            await session_manager.initialize()
            
            self.legacy_components['session_manager'] = session_manager
            logger.debug("Legacy session manager initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize legacy session manager: {e}")
    
    async def _initialize_legacy_fingerprint_manager(self):
        """初始化原有指纹管理器"""
        try:
            from ..scrapers.enhanced_fingerprint_manager import EnhancedFingerprintManager
            
            fingerprint_manager = EnhancedFingerprintManager({})
            await fingerprint_manager.initialize()
            
            self.legacy_components['fingerprint_manager'] = fingerprint_manager
            logger.debug("Legacy fingerprint manager initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize legacy fingerprint manager: {e}")
    
    async def _initialize_legacy_behavior_engine(self):
        """初始化原有行为引擎"""
        try:
            from ..scrapers.enhanced_behavior_engine import EnhancedBehaviorEngine
            
            behavior_engine = EnhancedBehaviorEngine({})
            await behavior_engine.initialize()
            
            self.legacy_components['behavior_engine'] = behavior_engine
            logger.debug("Legacy behavior engine initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize legacy behavior engine: {e}")
    
    async def _initialize_legacy_captcha_detector(self):
        """初始化原有CAPTCHA检测器"""
        try:
            from ..captcha.unified_captcha_detector import UnifiedCaptchaDetector
            
            captcha_detector = UnifiedCaptchaDetector()
            
            self.legacy_components['captcha_detector'] = captcha_detector
            logger.debug("Legacy CAPTCHA detector initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize legacy CAPTCHA detector: {e}")
    
    async def start(self):
        """启动管理器"""
        if self.status != SystemStatus.READY:
            raise RuntimeError(f"Manager is not ready. Current status: {self.status.value}")
        
        try:
            logger.info("Starting PluginAntiDetectionManager...")
            self.status = SystemStatus.RUNNING
            
            # 启动插件框架（如果还没启动）
            # 框架在initialize时已经启动，这里主要是确保状态一致
            
            # 启动原有组件
            await self._start_legacy_components()
            
            logger.info("PluginAntiDetectionManager started successfully")
            
        except Exception as e:
            self.status = SystemStatus.ERROR
            logger.error(f"Failed to start PluginAntiDetectionManager: {e}")
            raise
    
    async def _start_legacy_components(self):
        """启动原有组件"""
        for component_name, component in self.legacy_components.items():
            try:
                if hasattr(component, 'start'):
                    await component.start()
                logger.debug(f"Legacy component started: {component_name}")
            except Exception as e:
                logger.error(f"Failed to start legacy component {component_name}: {e}")
    
    async def stop(self):
        """停止管理器"""
        logger.info("Stopping PluginAntiDetectionManager...")
        self.status = SystemStatus.STOPPING
        
        try:
            # 停止监控任务
            await self._stop_monitoring_tasks()
            
            # 停止原有组件
            await self._stop_legacy_components()
            
            # 停止插件框架
            await self.plugin_framework.stop()
            
            self.status = SystemStatus.STOPPED
            logger.info("PluginAntiDetectionManager stopped successfully")
            
        except Exception as e:
            self.status = SystemStatus.ERROR
            logger.error(f"Failed to stop PluginAntiDetectionManager: {e}")
            raise
    
    async def _stop_legacy_components(self):
        """停止原有组件"""
        for component_name, component in self.legacy_components.items():
            try:
                if hasattr(component, 'stop'):
                    await component.stop()
                logger.debug(f"Legacy component stopped: {component_name}")
            except Exception as e:
                logger.error(f"Failed to stop legacy component {component_name}: {e}")
    
    # 核心反检测功能接口（向后兼容）
    
    async def detect_captcha(self, 
                           content: str, 
                           response: Optional[Any] = None,
                           url: Optional[str] = None) -> UnifiedDetectionResult:
        """检测CAPTCHA（向后兼容接口）"""
        start_time = time.time()
        
        try:
            # 优先使用插件
            if self.captcha_plugin:
                result_dict = await self.captcha_plugin.detect_captcha(content, {'url': url})
                
                # 转换为统一结果格式
                result = UnifiedDetectionResult(
                    is_detected=result_dict.get('detected', False),
                    confidence=result_dict.get('confidence', 0.0),
                    detection_type=result_dict.get('captcha_type', CaptchaType.UNKNOWN),
                    detection_method=result_dict.get('detection_method', 'plugin'),
                    processing_time=time.time() - start_time
                )
            else:
                # 使用原有组件
                captcha_detector = self.legacy_components.get('captcha_detector')
                if captcha_detector:
                    result = await captcha_detector.detect_unified(content, response, url)
                else:
                    result = UnifiedDetectionResult(
                        is_detected=False,
                        confidence=0.0,
                        detection_type=CaptchaType.UNKNOWN,
                        detection_method='unavailable',
                        processing_time=time.time() - start_time
                    )
            
            # 更新统计
            self.stats.update_operation_stats(True, time.time() - start_time)
            self.stats.captcha_detections += 1
            
            return result
            
        except Exception as e:
            self.stats.update_operation_stats(False, time.time() - start_time)
            logger.error(f"CAPTCHA detection failed: {e}")
            
            # 触发错误事件
            await self._trigger_event('error_occurred', {'error': str(e), 'operation': 'detect_captcha'})
            raise
    
    async def get_optimized_session(self, url: str) -> Optional[Any]:
        """获取优化的会话（向后兼容接口）"""
        start_time = time.time()
        
        try:
            # 优先使用插件
            if self.session_plugin:
                session_id = await self.session_plugin.create_session({'url': url})
                session = await self.session_plugin.get_session(session_id)
                
                # 应用指纹
                if self.fingerprint_plugin and session:
                    fingerprint = await self.fingerprint_plugin.generate_fingerprint()
                    await self.fingerprint_plugin.apply_fingerprint(session, fingerprint)
                
                self.stats.session_operations += 1
                return session
            else:
                # 使用原有组件
                session_manager = self.legacy_components.get('session_manager')
                if session_manager:
                    session = await session_manager.get_session(url)
                    
                    # 应用指纹
                    fingerprint_manager = self.legacy_components.get('fingerprint_manager')
                    if fingerprint_manager and session:
                        fingerprint = await fingerprint_manager.get_fingerprint()
                        if fingerprint:
                            await fingerprint_manager.apply_fingerprint(session, fingerprint)
                    
                    self.stats.session_operations += 1
                    return session
                else:
                    return None
            
        except Exception as e:
            logger.error(f"Failed to get optimized session: {e}")
            await self._trigger_event('error_occurred', {'error': str(e), 'operation': 'get_optimized_session'})
            return None
        finally:
            self.stats.update_operation_stats(True, time.time() - start_time)
    
    async def simulate_user_behavior(self, session: Any, behavior_type: str = None) -> bool:
        """模拟用户行为"""
        start_time = time.time()
        
        try:
            # 优先使用插件
            if self.behavior_plugin:
                if behavior_type == 'mouse':
                    result = await self.behavior_plugin.simulate_mouse_behavior(session)
                elif behavior_type == 'keyboard':
                    result = await self.behavior_plugin.simulate_keyboard_behavior(session)
                elif behavior_type == 'page':
                    result = await self.behavior_plugin.simulate_page_behavior(session)
                else:
                    # 综合行为模拟
                    result = (await self.behavior_plugin.simulate_mouse_behavior(session) and
                             await self.behavior_plugin.simulate_page_behavior(session))
                
                self.stats.behavior_operations += 1
                return result
            else:
                # 使用原有组件
                behavior_engine = self.legacy_components.get('behavior_engine')
                if behavior_engine:
                    result = await behavior_engine.simulate_user_behavior(behavior_type)
                    self.stats.behavior_operations += 1
                    return result
                else:
                    return False
            
        except Exception as e:
            logger.error(f"Failed to simulate user behavior: {e}")
            await self._trigger_event('error_occurred', {'error': str(e), 'operation': 'simulate_user_behavior'})
            return False
        finally:
            self.stats.update_operation_stats(True, time.time() - start_time)
    
    # 插件管理接口
    
    async def load_plugin(self, plugin_class: Type[IPlugin], config: Dict[str, Any] = None) -> bool:
        """动态加载插件"""
        try:
            success = await self.plugin_framework.load_plugin(plugin_class, config)
            if success:
                self.stats.active_plugins += 1
                await self._trigger_event('plugin_loaded', {'plugin_class': plugin_class.__name__})
            return success
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_class.__name__}: {e}")
            return False
    
    async def unload_plugin(self, plugin_id: str) -> bool:
        """动态卸载插件"""
        try:
            success = await self.plugin_framework.unload_plugin(plugin_id)
            if success:
                self.stats.active_plugins -= 1
                await self._trigger_event('plugin_unloaded', {'plugin_id': plugin_id})
            return success
        except Exception as e:
            logger.error(f"Failed to unload plugin {plugin_id}: {e}")
            return False
    
    async def reload_plugin(self, plugin_id: str) -> bool:
        """热重载插件"""
        try:
            success = await self.plugin_loader.reload_plugin(plugin_id)
            if success:
                self.stats.plugin_reloads += 1
            return success
        except Exception as e:
            logger.error(f"Failed to reload plugin {plugin_id}: {e}")
            return False
    
    async def get_plugin(self, plugin_id: str) -> Optional[IPlugin]:
        """获取插件实例"""
        return await self.plugin_framework.get_plugin(plugin_id)
    
    async def list_plugins(self) -> List[Dict[str, Any]]:
        """列出所有插件"""
        plugins = []
        
        for plugin_id, plugin in self.plugin_framework.plugins.items():
            plugin_info = await plugin.get_plugin_info()
            plugins.append(plugin_info)
        
        return plugins
    
    # 统计和监控接口
    
    async def get_system_stats(self) -> Dict[str, Any]:
        """获取系统统计信息"""
        # 更新运行时间
        self.stats.uptime = time.time() - self.start_time
        
        # 获取框架统计
        framework_stats = await self.plugin_framework.get_framework_stats()
        
        return {
            'manager_status': self.status.value,
            'operation_mode': self.config.operation_mode.value,
            'uptime': self.stats.uptime,
            
            # 操作统计
            'total_operations': self.stats.total_operations,
            'successful_operations': self.stats.successful_operations,
            'failed_operations': self.stats.failed_operations,
            'average_operation_time': self.stats.average_operation_time,
            
            # 组件统计
            'session_operations': self.stats.session_operations,
            'fingerprint_operations': self.stats.fingerprint_operations,
            'behavior_operations': self.stats.behavior_operations,
            'captcha_detections': self.stats.captcha_detections,
            
            # 插件统计
            'total_plugins': self.stats.total_plugins,
            'active_plugins': self.stats.active_plugins,
            'failed_plugins': self.stats.failed_plugins,
            'legacy_fallbacks': self.stats.legacy_fallbacks,
            'plugin_reloads': self.stats.plugin_reloads,
            
            # 框架统计
            'framework_stats': framework_stats
        }
    
    async def get_health_status(self) -> Dict[str, Any]:
        """获取健康状态"""
        health_status = {
            'overall_healthy': True,
            'manager_status': self.status.value,
            'components': {}
        }
        
        # 检查插件健康状态
        for plugin_id, plugin in self.plugin_framework.plugins.items():
            try:
                plugin_health = await plugin.healthcheck()
                health_status['components'][plugin_id] = plugin_health
                
                if not plugin_health.get('healthy', False):
                    health_status['overall_healthy'] = False
                    
            except Exception as e:
                health_status['components'][plugin_id] = {
                    'healthy': False,
                    'error': str(e)
                }
                health_status['overall_healthy'] = False
        
        # 检查原有组件健康状态
        for component_name, component in self.legacy_components.items():
            try:
                if hasattr(component, 'health_check'):
                    component_health = await component.health_check()
                    health_status['components'][f"legacy_{component_name}"] = component_health
                else:
                    health_status['components'][f"legacy_{component_name}"] = {
                        'healthy': True,
                        'status': 'available'
                    }
            except Exception as e:
                health_status['components'][f"legacy_{component_name}"] = {
                    'healthy': False,
                    'error': str(e)
                }
                health_status['overall_healthy'] = False
        
        return health_status
    
    # 事件处理
    
    def register_event_callback(self, event_type: str, callback: Callable):
        """注册事件回调"""
        if event_type in self.event_callbacks:
            self.event_callbacks[event_type].append(callback)
    
    def unregister_event_callback(self, event_type: str, callback: Callable):
        """注销事件回调"""
        if event_type in self.event_callbacks and callback in self.event_callbacks[event_type]:
            self.event_callbacks[event_type].remove(callback)
    
    async def _trigger_event(self, event_type: str, data: Dict[str, Any]):
        """触发事件"""
        if event_type in self.event_callbacks:
            for callback in self.event_callbacks[event_type]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(data)
                    else:
                        callback(data)
                except Exception as e:
                    logger.error(f"Event callback error: {e}")
    
    # 监控任务
    
    async def _start_monitoring_tasks(self):
        """启动监控任务"""
        if self.config.enable_performance_monitoring:
            self.monitoring_tasks.append(
                asyncio.create_task(self._performance_monitoring_loop())
            )
        
        if self.config.health_check_interval > 0:
            self.monitoring_tasks.append(
                asyncio.create_task(self._health_monitoring_loop())
            )
    
    async def _stop_monitoring_tasks(self):
        """停止监控任务"""
        for task in self.monitoring_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self.monitoring_tasks.clear()
    
    async def _performance_monitoring_loop(self):
        """性能监控循环"""
        while True:
            try:
                await asyncio.sleep(60.0)  # 每分钟更新一次
                
                # 更新性能指标
                await self._update_performance_metrics()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Performance monitoring error: {e}")
                await asyncio.sleep(30.0)
    
    async def _health_monitoring_loop(self):
        """健康监控循环"""
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                
                # 执行健康检查
                health_status = await self.get_health_status()
                
                # 如果有不健康的组件，记录日志
                if not health_status['overall_healthy']:
                    unhealthy_components = [
                        comp_name for comp_name, comp_health in health_status['components'].items()
                        if not comp_health.get('healthy', False)
                    ]
                    logger.warning(f"Unhealthy components detected: {unhealthy_components}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(300.0)
    
    async def _update_performance_metrics(self):
        """更新性能指标"""
        try:
            import psutil
            import os
            
            # 获取内存和CPU使用情况
            process = psutil.Process(os.getpid())
            self.stats.memory_usage_mb = process.memory_info().rss / 1024 / 1024
            self.stats.cpu_usage_percent = process.cpu_percent()
            
        except Exception as e:
            logger.debug(f"Failed to update performance metrics: {e}")


# 全局实例和便利函数

_global_manager: Optional[PluginAntiDetectionManager] = None

def get_plugin_anti_detection_manager(config: Optional[Dict[str, Any]] = None) -> PluginAntiDetectionManager:
    """获取全局插件反检测管理器实例"""
    global _global_manager
    if _global_manager is None:
        _global_manager = PluginAntiDetectionManager(config)
    return _global_manager


async def initialize_plugin_anti_detection_system(config: Optional[Dict[str, Any]] = None):
    """初始化插件反检测系统"""
    manager = get_plugin_anti_detection_manager(config)
    await manager.initialize()
    await manager.start()
    return manager


async def shutdown_plugin_anti_detection_system():
    """关闭插件反检测系统"""
    global _global_manager
    if _global_manager:
        await _global_manager.stop()
        _global_manager = None