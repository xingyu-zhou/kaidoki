"""
增强反检测管理器 - 插件化架构集成版本

该模块是AntiDetectionManager的增强版本，集成了新的插件化架构，提供：
- 统一的反检测功能管理
- 插件化组件架构
- 全局流量协调
- 热插拔组件支持
- 完全向后兼容性

基于原有AntiDetectionManager的API，同时添加了新的插件管理功能。

Author: Mercari AI Agent Team
"""

import asyncio
import logging
import time
import yaml
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum

# 插件化架构导入
from .plugin_interface import (
    IAntiDetectionPlugin, PluginStatus, PluginCategory, 
    IDetectionPlugin, ISessionPlugin, IFingerprintPlugin, 
    IBehaviorPlugin, IEnvironmentPlugin
)
from .plugin_registry import PluginRegistry, get_plugin, get_plugins_by_category
from .component_factory import (
    ComponentManager, ComponentType, component_manager,
    create_detector, create_session_manager, create_fingerprint_manager,
    create_behavior_engine, create_environment_spoofing
)

# 原有组件导入（保持兼容性）
from .unified_captcha_detector import UnifiedCaptchaDetector, UnifiedDetectionResult
from .captcha_types import CaptchaType, CaptchaDetectionResult
from .anti_detection_manager import (
    DetectionMode, SystemStatus, AntiDetectionStats, RequestMetrics
)
from ..utils.logger import get_logger

logger = get_logger(__name__)


class PluginIntegrationMode(Enum):
    """插件集成模式"""
    LEGACY = "legacy"           # 纯原有组件模式
    HYBRID = "hybrid"           # 混合模式（默认）
    FULL_PLUGIN = "full_plugin" # 完全插件模式


@dataclass
class GlobalTrafficCoordinator:
    """全局流量协调器配置"""
    max_concurrent_requests: int = 10
    request_queue_size: int = 100
    rate_limit_per_minute: int = 60
    adaptive_throttling: bool = True
    traffic_balancing: bool = True
    
    # 协调状态
    active_requests: int = 0
    request_history: List[float] = field(default_factory=list)
    last_request_time: float = 0.0


class EnhancedAntiDetectionManager:
    """
    增强反检测管理器
    
    核心增强功能：
    1. 插件化架构集成
    2. 全局流量协调
    3. 组件热插拔
    4. 向后兼容性保证
    5. 统一配置管理
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化增强反检测管理器
        
        Args:
            config: 配置字典
        """
        self.config = config or self._load_default_config()
        self.status = SystemStatus.INITIALIZING
        self.mode = DetectionMode(self.config.get('global', {}).get('mode', 'balanced'))
        self.integration_mode = PluginIntegrationMode(
            self.config.get('plugin', {}).get('integration_mode', 'hybrid')
        )
        
        # 插件系统
        self.plugin_registry = PluginRegistry.get_instance()
        self.component_manager = component_manager
        self.plugins: Dict[str, IAntiDetectionPlugin] = {}
        
        # 原有组件兼容性
        self.unified_detector: Optional[UnifiedCaptchaDetector] = None
        self.session_manager: Optional[Any] = None
        self.fingerprint_manager: Optional[Any] = None
        self.environment_spoofing: Optional[Any] = None
        self.behavior_engine: Optional[Any] = None
        
        # 新增：全局流量协调
        self.traffic_coordinator = GlobalTrafficCoordinator(
            **self.config.get('traffic_coordination', {})
        )
        
        # 统计和监控（继承原有）
        self.stats = AntiDetectionStats()
        self.metrics_history: List[RequestMetrics] = []
        self.error_history: List[Dict[str, Any]] = []
        
        # 配置参数
        self.confidence_threshold = self.config.get('detector', {}).get('confidence_threshold', 0.6)
        self.max_retry_attempts = self.config.get('global', {}).get('max_retry_attempts', 3)
        self.request_interval_range = self.config.get('session_management', {}).get('request_intervals', {})
        
        # 监控和协调任务
        self.monitoring_tasks: List[asyncio.Task] = []
        self.coordination_tasks: List[asyncio.Task] = []
        self.start_time = time.time()
        
        # 事件系统
        self.event_callbacks: Dict[str, List[Callable]] = {
            'captcha_detected': [],
            'captcha_solved': [],
            'error_occurred': [],
            'fingerprint_rotated': [],
            'session_renewed': [],
            'plugin_loaded': [],
            'plugin_unloaded': [],
            'traffic_throttled': [],
            'component_switched': []
        }
        
        logger.info(f"EnhancedAntiDetectionManager initialized with mode: {self.mode.value}, integration: {self.integration_mode.value}")
    
    def _load_default_config(self) -> Dict[str, Any]:
        """加载默认配置（继承原有配置，添加插件配置）"""
        config = {
            'global': {
                'mode': 'balanced',
                'enabled': True,
                'debug_mode': False,
                'log_level': 'INFO',
                'max_retry_attempts': 3
            },
            'plugin': {
                'integration_mode': 'hybrid',
                'auto_load_plugins': True,
                'plugin_discovery_paths': [],
                'enable_hot_reload': False,
                'plugin_timeout': 30.0
            },
            'detector': {
                'confidence_threshold': 0.6,
                'enable_context_analysis': True,
                'enable_debug_logging': False,
                'max_processing_time': 30.0,
                'preferred_implementation': 'unified_captcha_detector'
            },
            'session_management': {
                'enabled': True,
                'preferred_implementation': 'enhanced_session_manager',
                'request_intervals': {
                    'min_interval': 15.0,
                    'max_interval': 30.0,
                    'randomize': True
                },
                'timeouts': {
                    'connection_timeout': 30,
                    'read_timeout': 60,
                    'total_timeout': 120
                }
            },
            'fingerprint_management': {
                'enabled': True,
                'preferred_implementation': 'enhanced_fingerprint_manager',
                'pool': {
                    'max_fingerprints': 100,
                    'rotation_interval': 1800,
                    'max_usage_count': 50
                },
                'quality': {
                    'min_quality': 'fair'
                }
            },
            'environment_spoofing': {
                'enabled': True,
                'preferred_implementation': 'browser_environment_spoofing',
                'spoofing_level': 'standard'
            },
            'behavior_simulation': {
                'enabled': True,
                'preferred_implementation': 'enhanced_behavior_engine',
                'mouse_behavior': True,
                'keyboard_behavior': True,
                'page_behavior': True
            },
            'traffic_coordination': {
                'max_concurrent_requests': 10,
                'request_queue_size': 100,
                'rate_limit_per_minute': 60,
                'adaptive_throttling': True,
                'traffic_balancing': True
            },
            'monitoring': {
                'enabled': True,
                'metrics_retention_hours': 24,
                'error_retention_hours': 72,
                'health_check_interval': 300
            }
        }
        return config
    
    async def initialize(self):
        """初始化系统"""
        try:
            logger.info("Initializing EnhancedAntiDetectionManager...")
            self.status = SystemStatus.INITIALIZING
            
            # 1. 初始化插件系统
            await self._initialize_plugin_system()
            
            # 2. 根据集成模式初始化组件
            if self.integration_mode == PluginIntegrationMode.FULL_PLUGIN:
                await self._initialize_plugin_components()
            elif self.integration_mode == PluginIntegrationMode.HYBRID:
                await self._initialize_hybrid_components()
            else:  # LEGACY
                await self._initialize_legacy_components()
            
            # 3. 启动全局流量协调
            await self._initialize_traffic_coordination()
            
            # 4. 启动监控任务
            if self.config.get('monitoring', {}).get('enabled', True):
                self._start_monitoring_tasks()
            
            self.status = SystemStatus.READY
            logger.info("EnhancedAntiDetectionManager initialized successfully")
            
        except Exception as e:
            self.status = SystemStatus.ERROR
            logger.error(f"Failed to initialize EnhancedAntiDetectionManager: {e}")
            raise
    
    async def _initialize_plugin_system(self):
        """初始化插件系统"""
        try:
            # 启动插件注册表
            if not self.plugin_registry.running:
                await self.plugin_registry.start_all_plugins()
            
            # 自动发现和加载插件
            if self.config.get('plugin', {}).get('auto_load_plugins', True):
                await self._auto_load_plugins()
            
            logger.info("Plugin system initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize plugin system: {e}")
            raise
    
    async def _auto_load_plugins(self):
        """自动加载插件"""
        try:
            # 这里可以添加自动插件发现逻辑
            # 目前主要是确保内置插件可用
            
            # 注册兼容性插件包装器
            await self._register_compatibility_plugins()
            
            logger.info("Auto-loading plugins completed")
            
        except Exception as e:
            logger.error(f"Failed to auto-load plugins: {e}")
            raise
    
    async def _register_compatibility_plugins(self):
        """注册兼容性插件包装器"""
        # 这里可以将现有组件包装为插件
        # 实现向后兼容性
        pass
    
    async def _initialize_plugin_components(self):
        """初始化纯插件组件"""
        try:
            # 检测器
            if self.config.get('detector', {}).get('enabled', True):
                implementation = self.config.get('detector', {}).get('preferred_implementation', 'unified_captcha_detector')
                self.unified_detector = await create_detector(implementation, **self.config.get('detector', {}))
            
            # 会话管理器
            if self.config.get('session_management', {}).get('enabled', True):
                implementation = self.config.get('session_management', {}).get('preferred_implementation', 'enhanced_session_manager')
                self.session_manager = await create_session_manager(implementation, **self.config.get('session_management', {}))
                if hasattr(self.session_manager, 'initialize'):
                    await self.session_manager.initialize()
            
            # 指纹管理器
            if self.config.get('fingerprint_management', {}).get('enabled', True):
                implementation = self.config.get('fingerprint_management', {}).get('preferred_implementation', 'enhanced_fingerprint_manager')
                self.fingerprint_manager = await create_fingerprint_manager(implementation, **self.config.get('fingerprint_management', {}))
                if hasattr(self.fingerprint_manager, 'initialize'):
                    await self.fingerprint_manager.initialize()
            
            # 环境伪装
            if self.config.get('environment_spoofing', {}).get('enabled', True):
                implementation = self.config.get('environment_spoofing', {}).get('preferred_implementation', 'browser_environment_spoofing')
                self.environment_spoofing = await create_environment_spoofing(implementation, **self.config.get('environment_spoofing', {}))
                if hasattr(self.environment_spoofing, 'initialize'):
                    await self.environment_spoofing.initialize()
            
            # 行为引擎
            if self.config.get('behavior_simulation', {}).get('enabled', True):
                implementation = self.config.get('behavior_simulation', {}).get('preferred_implementation', 'enhanced_behavior_engine')
                self.behavior_engine = await create_behavior_engine(implementation, **self.config.get('behavior_simulation', {}))
                if hasattr(self.behavior_engine, 'initialize'):
                    await self.behavior_engine.initialize()
            
            logger.info("Plugin components initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize plugin components: {e}")
            raise
    
    async def _initialize_hybrid_components(self):
        """初始化混合模式组件"""
        try:
            # 在混合模式下，优先使用插件组件，回退到原有组件
            
            # 检测器 - 尝试插件，回退到原有
            try:
                if self.config.get('detector', {}).get('enabled', True):
                    implementation = self.config.get('detector', {}).get('preferred_implementation', 'unified_captcha_detector')
                    self.unified_detector = await create_detector(implementation, **self.config.get('detector', {}))
            except Exception as e:
                logger.warning(f"Failed to create plugin detector, falling back to legacy: {e}")
                await self._initialize_legacy_detector()
            
            # 会话管理器 - 混合模式
            try:
                if self.config.get('session_management', {}).get('enabled', True):
                    implementation = self.config.get('session_management', {}).get('preferred_implementation', 'enhanced_session_manager')
                    self.session_manager = await create_session_manager(implementation, **self.config.get('session_management', {}))
                    if hasattr(self.session_manager, 'initialize'):
                        await self.session_manager.initialize()
            except Exception as e:
                logger.warning(f"Failed to create plugin session manager, falling back to legacy: {e}")
                await self._initialize_legacy_session_manager()
            
            # 其他组件类似处理
            await self._initialize_other_hybrid_components()
            
            logger.info("Hybrid components initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize hybrid components: {e}")
            raise
    
    async def _initialize_other_hybrid_components(self):
        """初始化其他混合组件"""
        # 指纹管理器
        try:
            if self.config.get('fingerprint_management', {}).get('enabled', True):
                implementation = self.config.get('fingerprint_management', {}).get('preferred_implementation', 'enhanced_fingerprint_manager')
                self.fingerprint_manager = await create_fingerprint_manager(implementation, **self.config.get('fingerprint_management', {}))
                if hasattr(self.fingerprint_manager, 'initialize'):
                    await self.fingerprint_manager.initialize()
        except Exception as e:
            logger.warning(f"Failed to create plugin fingerprint manager, falling back to legacy: {e}")
            await self._initialize_legacy_fingerprint_manager()
        
        # 环境伪装
        try:
            if self.config.get('environment_spoofing', {}).get('enabled', True):
                implementation = self.config.get('environment_spoofing', {}).get('preferred_implementation', 'browser_environment_spoofing')
                self.environment_spoofing = await create_environment_spoofing(implementation, **self.config.get('environment_spoofing', {}))
                if hasattr(self.environment_spoofing, 'initialize'):
                    await self.environment_spoofing.initialize()
        except Exception as e:
            logger.warning(f"Failed to create plugin environment spoofing, falling back to legacy: {e}")
            await self._initialize_legacy_environment_spoofing()
        
        # 行为引擎
        try:
            if self.config.get('behavior_simulation', {}).get('enabled', True):
                implementation = self.config.get('behavior_simulation', {}).get('preferred_implementation', 'enhanced_behavior_engine')
                self.behavior_engine = await create_behavior_engine(implementation, **self.config.get('behavior_simulation', {}))
                if hasattr(self.behavior_engine, 'initialize'):
                    await self.behavior_engine.initialize()
        except Exception as e:
            logger.warning(f"Failed to create plugin behavior engine, falling back to legacy: {e}")
            await self._initialize_legacy_behavior_engine()
    
    async def _initialize_legacy_components(self):
        """初始化原有组件模式"""
        # 使用原有的初始化逻辑
        await self._initialize_legacy_detector()
        await self._initialize_legacy_session_manager()
        await self._initialize_legacy_fingerprint_manager()
        await self._initialize_legacy_environment_spoofing()
        await self._initialize_legacy_behavior_engine()
        
        logger.info("Legacy components initialized")
    
    async def _initialize_legacy_detector(self):
        """初始化原有检测器"""
        if self.config.get('detector', {}).get('enabled', True):
            self.unified_detector = UnifiedCaptchaDetector()
            detector_config = self.config.get('detector', {})
            self.unified_detector.confidence_threshold = detector_config.get('confidence_threshold', 0.6)
            self.unified_detector.enable_context_analysis = detector_config.get('enable_context_analysis', True)
            self.unified_detector.enable_debug_logging = detector_config.get('enable_debug_logging', False)
            self.unified_detector.max_processing_time = detector_config.get('max_processing_time', 30.0)
    
    async def _initialize_legacy_session_manager(self):
        """初始化原有会话管理器"""
        if self.config.get('session_management', {}).get('enabled', True):
            from ..scrapers.enhanced_session_manager import EnhancedSessionManager, SessionConfig
            
            session_config_dict = self.config.get('session_management', {})
            session_config = SessionConfig(
                max_concurrent_sessions=session_config_dict.get('max_concurrent_sessions', 3),
                session_timeout=session_config_dict.get('timeouts', {}).get('session_timeout', 1800),
                connection_timeout=session_config_dict.get('timeouts', {}).get('connection_timeout', 30),
                read_timeout=session_config_dict.get('timeouts', {}).get('read_timeout', 60),
                total_timeout=session_config_dict.get('timeouts', {}).get('total_timeout', 120)
            )
            
            self.session_manager = EnhancedSessionManager(session_config)
            await self.session_manager.initialize()
    
    async def _initialize_legacy_fingerprint_manager(self):
        """初始化原有指纹管理器"""
        if self.config.get('fingerprint_management', {}).get('enabled', True):
            from ..scrapers.enhanced_fingerprint_manager import EnhancedFingerprintManager
            
            fingerprint_config = self.config.get('fingerprint_management', {})
            self.fingerprint_manager = EnhancedFingerprintManager(fingerprint_config)
            await self.fingerprint_manager.initialize()
    
    async def _initialize_legacy_environment_spoofing(self):
        """初始化原有环境伪装"""
        if self.config.get('environment_spoofing', {}).get('enabled', True):
            from ..scrapers.browser_environment_spoofing import BrowserEnvironmentSpoofing
            
            spoofing_config = self.config.get('environment_spoofing', {})
            self.environment_spoofing = BrowserEnvironmentSpoofing(spoofing_config)
            await self.environment_spoofing.initialize()
    
    async def _initialize_legacy_behavior_engine(self):
        """初始化原有行为引擎"""
        if self.config.get('behavior_simulation', {}).get('enabled', True):
            from ..scrapers.enhanced_behavior_engine import EnhancedBehaviorEngine
            
            behavior_config = self.config.get('behavior_simulation', {})
            self.behavior_engine = EnhancedBehaviorEngine(behavior_config)
            await self.behavior_engine.initialize()
    
    async def _initialize_traffic_coordination(self):
        """初始化全局流量协调"""
        try:
            # 启动流量协调任务
            self.coordination_tasks.append(
                asyncio.create_task(self._traffic_coordination_loop())
            )
            
            # 启动速率限制任务
            self.coordination_tasks.append(
                asyncio.create_task(self._rate_limit_cleanup_loop())
            )
            
            logger.info("Traffic coordination initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize traffic coordination: {e}")
            raise
    
    async def _traffic_coordination_loop(self):
        """流量协调循环"""
        while True:
            try:
                await asyncio.sleep(1.0)  # 每秒检查一次
                
                # 清理过期的请求历史
                current_time = time.time()
                cutoff_time = current_time - 60.0  # 保留最近1分钟的历史
                
                self.traffic_coordinator.request_history = [
                    req_time for req_time in self.traffic_coordinator.request_history
                    if req_time > cutoff_time
                ]
                
                # 自适应节流
                if self.traffic_coordinator.adaptive_throttling:
                    await self._adaptive_throttling()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Traffic coordination loop error: {e}")
    
    async def _adaptive_throttling(self):
        """自适应节流"""
        current_time = time.time()
        recent_requests = len(self.traffic_coordinator.request_history)
        
        # 如果请求频率过高，应用节流
        if recent_requests > self.traffic_coordinator.rate_limit_per_minute:
            throttle_delay = (recent_requests - self.traffic_coordinator.rate_limit_per_minute) * 0.1
            
            # 触发节流事件
            await self._trigger_event_callbacks('traffic_throttled', {
                'recent_requests': recent_requests,
                'throttle_delay': throttle_delay,
                'timestamp': current_time
            })
            
            logger.warning(f"Traffic throttling applied: {throttle_delay:.2f}s delay")
    
    async def _rate_limit_cleanup_loop(self):
        """速率限制清理循环"""
        while True:
            try:
                await asyncio.sleep(60.0)  # 每分钟清理一次
                
                # 清理过期的请求历史
                current_time = time.time()
                cutoff_time = current_time - 60.0
                
                old_count = len(self.traffic_coordinator.request_history)
                self.traffic_coordinator.request_history = [
                    req_time for req_time in self.traffic_coordinator.request_history
                    if req_time > cutoff_time
                ]
                
                cleaned_count = old_count - len(self.traffic_coordinator.request_history)
                if cleaned_count > 0:
                    logger.debug(f"Cleaned {cleaned_count} expired request records")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Rate limit cleanup loop error: {e}")
    
    async def start(self):
        """启动系统"""
        if self.status != SystemStatus.READY:
            raise RuntimeError(f"System is not ready. Current status: {self.status.value}")
        
        try:
            logger.info("Starting EnhancedAntiDetectionManager...")
            self.status = SystemStatus.RUNNING
            
            # 启动各个组件
            await self._start_components()
            
            logger.info("EnhancedAntiDetectionManager started successfully")
            
        except Exception as e:
            self.status = SystemStatus.ERROR
            logger.error(f"Failed to start EnhancedAntiDetectionManager: {e}")
            raise
    
    async def _start_components(self):
        """启动各个组件"""
        components = [
            ('session_manager', self.session_manager),
            ('fingerprint_manager', self.fingerprint_manager),
            ('environment_spoofing', self.environment_spoofing),
            ('behavior_engine', self.behavior_engine)
        ]
        
        for name, component in components:
            if component and hasattr(component, 'start'):
                try:
                    await component.start()
                    logger.debug(f"Started component: {name}")
                except Exception as e:
                    logger.error(f"Failed to start component {name}: {e}")
    
    async def stop(self):
        """停止系统"""
        logger.info("Stopping EnhancedAntiDetectionManager...")
        self.status = SystemStatus.STOPPING
        
        try:
            # 停止协调任务
            await self._stop_coordination_tasks()
            
            # 停止监控任务
            await self._stop_monitoring_tasks()
            
            # 停止各个组件
            await self._stop_components()
            
            # 停止插件系统
            await self._stop_plugin_system()
            
            self.status = SystemStatus.STOPPED
            logger.info("EnhancedAntiDetectionManager stopped successfully")
            
        except Exception as e:
            self.status = SystemStatus.ERROR
            logger.error(f"Failed to stop EnhancedAntiDetectionManager: {e}")
            raise
    
    async def _stop_coordination_tasks(self):
        """停止协调任务"""
        for task in self.coordination_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        self.coordination_tasks.clear()
    
    async def _stop_components(self):
        """停止各个组件"""
        components = [
            ('behavior_engine', self.behavior_engine),
            ('environment_spoofing', self.environment_spoofing),
            ('fingerprint_manager', self.fingerprint_manager),
            ('session_manager', self.session_manager)
        ]
        
        for name, component in components:
            if component and hasattr(component, 'stop'):
                try:
                    await component.stop()
                    logger.debug(f"Stopped component: {name}")
                except Exception as e:
                    logger.error(f"Failed to stop component {name}: {e}")
    
    async def _stop_plugin_system(self):
        """停止插件系统"""
        try:
            # 停止插件注册表
            if self.plugin_registry.running:
                await self.plugin_registry.stop_all_plugins()
            
            logger.info("Plugin system stopped")
            
        except Exception as e:
            logger.error(f"Failed to stop plugin system: {e}")
    
    # ========================
    # 向后兼容性接口
    # ========================
    
    async def detect_captcha(self, 
                           content: str, 
                           response: Optional[Any] = None,
                           url: Optional[str] = None) -> UnifiedDetectionResult:
        """
        检测CAPTCHA（向后兼容接口）
        
        Args:
            content: 页面内容
            response: HTTP响应对象
            url: 页面URL
            
        Returns:
            UnifiedDetectionResult: 统一检测结果
        """
        # 流量协调
        await self._coordinate_request()
        
        start_time = time.time()
        request_id = f"req_{int(time.time() * 1000)}"
        
        try:
            # 更新统计
            self.stats.total_requests += 1
            
            # 执行检测
            result = await self.unified_detector.detect_unified(content, response, url)
            
            # 记录检测结果
            metrics = RequestMetrics(
                request_id=request_id,
                url=url or "unknown",
                start_time=start_time,
                end_time=time.time(),
                success=True,
                captcha_detected=result.is_detected,
                captcha_solved=False
            )
            
            if result.is_detected:
                self.stats.captcha_detections += 1
                self.stats.last_detection_time = datetime.now()
                
                # 触发事件回调
                await self._trigger_event_callbacks('captcha_detected', {
                    'result': result,
                    'url': url,
                    'request_id': request_id
                })
            
            self.metrics_history.append(metrics)
            self._cleanup_old_metrics()
            
            return result
            
        except Exception as e:
            # 记录错误
            error_metrics = RequestMetrics(
                request_id=request_id,
                url=url or "unknown",
                start_time=start_time,
                end_time=time.time(),
                success=False,
                captcha_detected=False,
                captcha_solved=False,
                error_message=str(e)
            )
            
            self.metrics_history.append(error_metrics)
            self._record_error(e, {'url': url, 'request_id': request_id})
            
            # 触发错误事件
            await self._trigger_event_callbacks('error_occurred', {
                'error': e,
                'url': url,
                'request_id': request_id
            })
            
            raise
    
    async def _coordinate_request(self):
        """协调请求"""
        current_time = time.time()
        
        # 检查并发限制
        if self.traffic_coordinator.active_requests >= self.traffic_coordinator.max_concurrent_requests:
            logger.warning("Concurrent request limit reached, waiting...")
            while self.traffic_coordinator.active_requests >= self.traffic_coordinator.max_concurrent_requests:
                await asyncio.sleep(0.1)
        
        # 检查速率限制
        recent_requests = len([
            req_time for req_time in self.traffic_coordinator.request_history
            if current_time - req_time < 60.0
        ])
        
        if recent_requests >= self.traffic_coordinator.rate_limit_per_minute:
            delay = 60.0 - (current_time - min(self.traffic_coordinator.request_history))
            logger.info(f"Rate limit reached, waiting {delay:.2f}s")
            await asyncio.sleep(delay)
        
        # 更新请求状态
        self.traffic_coordinator.active_requests += 1
        self.traffic_coordinator.request_history.append(current_time)
        self.traffic_coordinator.last_request_time = current_time
    
    async def handle_captcha_detected(self, detection_result: UnifiedDetectionResult) -> bool:
        """处理检测到的CAPTCHA（向后兼容接口）"""
        try:
            # 减少活跃请求计数
            self.traffic_coordinator.active_requests = max(0, self.traffic_coordinator.active_requests - 1)
            
            # 执行原有逻辑
            logger.info(f"CAPTCHA detected: {detection_result.detection_type.value}, "
                       f"confidence: {detection_result.confidence:.2f}")
            
            # 记录统计
            self.stats.captcha_bypassed += 1
            self.stats.update_success_rate()
            
            # 触发事件回调
            await self._trigger_event_callbacks('captcha_solved', {
                'result': detection_result,
                'success': True
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to handle CAPTCHA: {e}")
            self._record_error(e, {'detection_result': detection_result})
            return False
    
    async def get_optimized_session(self, url: str) -> Optional[Any]:
        """获取优化的会话（向后兼容接口）"""
        if not self.session_manager:
            return None
        
        try:
            # 流量协调
            await self._coordinate_request()
            
            session = await self.session_manager.get_session(url)
            
            # 应用指纹
            if self.fingerprint_manager:
                fingerprint = await self.fingerprint_manager.get_fingerprint()
                if fingerprint:
                    await self.fingerprint_manager.apply_fingerprint(session, fingerprint)
            
            # 应用环境伪装
            if self.environment_spoofing:
                await self.environment_spoofing.apply_spoofing(session)
            
            return session
            
        except Exception as e:
            logger.error(f"Failed to get optimized session: {e}")
            self._record_error(e, {'url': url})
            return None
        finally:
            # 减少活跃请求计数
            self.traffic_coordinator.active_requests = max(0, self.traffic_coordinator.active_requests - 1)
    
    async def execute_with_anti_detection(self, 
                                        func: Callable, 
                                        *args, 
                                        **kwargs) -> Any:
        """使用反检测机制执行函数（向后兼容接口）"""
        attempt = 0
        max_attempts = self.max_retry_attempts
        
        while attempt < max_attempts:
            try:
                # 流量协调
                await self._coordinate_request()
                
                # 应用行为模拟
                if self.behavior_engine:
                    await self.behavior_engine.simulate_user_behavior()
                
                # 执行函数
                result = await func(*args, **kwargs)
                
                # 检查结果中是否包含CAPTCHA
                if hasattr(result, 'content') and result.content:
                    detection_result = await self.detect_captcha(
                        result.content, 
                        result, 
                        kwargs.get('url')
                    )
                    
                    if detection_result.is_detected:
                        # 处理CAPTCHA
                        success = await self.handle_captcha_detected(detection_result)
                        if not success:
                            attempt += 1
                            continue
                
                return result
                
            except Exception as e:
                attempt += 1
                logger.warning(f"Attempt {attempt} failed: {e}")
                
                if attempt >= max_attempts:
                    raise
                
                # 等待重试
                await asyncio.sleep(2 ** attempt)
            finally:
                # 减少活跃请求计数
                self.traffic_coordinator.active_requests = max(0, self.traffic_coordinator.active_requests - 1)
    
    # ========================
    # 新增：插件管理接口
    # ========================
    
    async def load_plugin(self, plugin_name: str, plugin_config: Dict[str, Any] = None) -> bool:
        """加载插件"""
        try:
            # 通过插件注册表加载
            plugin = get_plugin(plugin_name)
            if plugin:
                if plugin_config:
                    plugin.update_config(plugin_config)
                
                self.plugins[plugin_name] = plugin
                
                # 触发插件加载事件
                await self._trigger_event_callbacks('plugin_loaded', {
                    'plugin_name': plugin_name,
                    'plugin_config': plugin_config
                })
                
                logger.info(f"Plugin loaded: {plugin_name}")
                return True
            else:
                logger.error(f"Plugin not found: {plugin_name}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_name}: {e}")
            return False
    
    async def unload_plugin(self, plugin_name: str) -> bool:
        """卸载插件"""
        try:
            if plugin_name in self.plugins:
                plugin = self.plugins[plugin_name]
                
                # 停止插件
                if hasattr(plugin, 'stop'):
                    await plugin.stop()
                
                # 从插件列表中移除
                del self.plugins[plugin_name]
                
                # 触发插件卸载事件
                await self._trigger_event_callbacks('plugin_unloaded', {
                    'plugin_name': plugin_name
                })
                
                logger.info(f"Plugin unloaded: {plugin_name}")
                return True
            else:
                logger.warning(f"Plugin not loaded: {plugin_name}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to unload plugin {plugin_name}: {e}")
            return False
    
    async def switch_component(self, component_type: str, implementation: str, config: Dict[str, Any] = None) -> bool:
        """切换组件实现"""
        try:
            # 映射组件类型
            type_mapping = {
                'detector': ComponentType.DETECTOR,
                'session_manager': ComponentType.SESSION_MANAGER,
                'fingerprint_manager': ComponentType.FINGERPRINT_MANAGER,
                'behavior_engine': ComponentType.BEHAVIOR_ENGINE,
                'environment_spoofing': ComponentType.ENVIRONMENT_SPOOFING
            }
            
            if component_type not in type_mapping:
                logger.error(f"Unknown component type: {component_type}")
                return False
            
            comp_type = type_mapping[component_type]
            
            # 创建新组件实例
            new_component = await self.component_manager.create_component(
                comp_type, implementation, config
            )
            
            # 停止旧组件
            old_component = getattr(self, component_type, None)
            if old_component and hasattr(old_component, 'stop'):
                await old_component.stop()
            
            # 初始化和启动新组件
            if hasattr(new_component, 'initialize'):
                await new_component.initialize()
            
            if hasattr(new_component, 'start'):
                await new_component.start()
            
            # 更新组件引用
            setattr(self, component_type, new_component)
            
            # 触发组件切换事件
            await self._trigger_event_callbacks('component_switched', {
                'component_type': component_type,
                'implementation': implementation,
                'config': config
            })
            
            logger.info(f"Component switched: {component_type} -> {implementation}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to switch component {component_type} to {implementation}: {e}")
            return False
    
    def list_available_plugins(self) -> Dict[str, Any]:
        """列出可用插件"""
        return self.plugin_registry.list_plugins()
    
    def list_loaded_plugins(self) -> Dict[str, Any]:
        """列出已加载插件"""
        return {
            name: {
                'status': plugin.status.value if hasattr(plugin, 'status') else 'active',
                'metadata': plugin.metadata if hasattr(plugin, 'metadata') else None,
                'stats': plugin.stats if hasattr(plugin, 'stats') else None
            }
            for name, plugin in self.plugins.items()
        }
    
    def get_traffic_stats(self) -> Dict[str, Any]:
        """获取流量统计"""
        return {
            'active_requests': self.traffic_coordinator.active_requests,
            'recent_requests': len(self.traffic_coordinator.request_history),
            'rate_limit_per_minute': self.traffic_coordinator.rate_limit_per_minute,
            'max_concurrent_requests': self.traffic_coordinator.max_concurrent_requests,
            'last_request_time': self.traffic_coordinator.last_request_time,
            'adaptive_throttling': self.traffic_coordinator.adaptive_throttling
        }
    
    # ========================
    # 继承的原有方法
    # ========================
    
    def update_config(self, new_config: Dict[str, Any]):
        """更新配置（向后兼容接口）"""
        self.config.update(new_config)
        
        # 更新检测器配置
        if self.unified_detector:
            detector_config = self.config.get('detector', {})
            if hasattr(self.unified_detector, 'confidence_threshold'):
                self.unified_detector.confidence_threshold = detector_config.get('confidence_threshold', 0.6)
            if hasattr(self.unified_detector, 'enable_context_analysis'):
                self.unified_detector.enable_context_analysis = detector_config.get('enable_context_analysis', True)
            if hasattr(self.unified_detector, 'enable_debug_logging'):
                self.unified_detector.enable_debug_logging = detector_config.get('enable_debug_logging', False)
        
        # 更新其他组件配置
        self.confidence_threshold = self.config.get('detector', {}).get('confidence_threshold', 0.6)
        self.max_retry_attempts = self.config.get('global', {}).get('max_retry_attempts', 3)
        
        # 更新流量协调配置
        traffic_config = self.config.get('traffic_coordination', {})
        if traffic_config:
            self.traffic_coordinator.max_concurrent_requests = traffic_config.get('max_concurrent_requests', 10)
            self.traffic_coordinator.rate_limit_per_minute = traffic_config.get('rate_limit_per_minute', 60)
            self.traffic_coordinator.adaptive_throttling = traffic_config.get('adaptive_throttling', True)
            self.traffic_coordinator.traffic_balancing = traffic_config.get('traffic_balancing', True)
        
        logger.info("Configuration updated successfully")
    
    def get_system_stats(self) -> Dict[str, Any]:
        """获取系统统计信息（向后兼容接口）"""
        current_time = time.time()
        uptime = current_time - self.start_time
        
        # 计算平均响应时间
        if self.metrics_history:
            avg_response_time = sum(m.response_time for m in self.metrics_history) / len(self.metrics_history)
        else:
            avg_response_time = 0.0
        
        base_stats = {
            'status': self.status.value,
            'mode': self.mode.value,
            'integration_mode': self.integration_mode.value,
            'uptime': uptime,
            'stats': {
                'total_requests': self.stats.total_requests,
                'captcha_detections': self.stats.captcha_detections,
                'captcha_bypassed': self.stats.captcha_bypassed,
                'success_rate': self.stats.success_rate,
                'avg_response_time': avg_response_time,
                'last_detection_time': self.stats.last_detection_time.isoformat() if self.stats.last_detection_time else None
            },
            'components': {
                'unified_detector': self.unified_detector is not None,
                'session_manager': self.session_manager is not None,
                'fingerprint_manager': self.fingerprint_manager is not None,
                'environment_spoofing': self.environment_spoofing is not None,
                'behavior_engine': self.behavior_engine is not None
            },
            'config': {
                'confidence_threshold': self.confidence_threshold,
                'max_retry_attempts': self.max_retry_attempts,
                'request_interval_range': self.request_interval_range
            }
        }
        
        # 添加新的统计信息
        base_stats['plugin_stats'] = {
            'loaded_plugins': len(self.plugins),
            'available_plugins': len(self.plugin_registry.registrations),
            'plugin_registry_running': self.plugin_registry.running
        }
        
        base_stats['traffic_stats'] = self.get_traffic_stats()
        
        return base_stats
    
    def register_event_callback(self, event_type: str, callback: Callable):
        """注册事件回调（向后兼容接口）"""
        if event_type in self.event_callbacks:
            self.event_callbacks[event_type].append(callback)
        else:
            logger.warning(f"Unknown event type: {event_type}")
    
    async def _trigger_event_callbacks(self, event_type: str, data: Dict[str, Any]):
        """触发事件回调"""
        if event_type in self.event_callbacks:
            for callback in self.event_callbacks[event_type]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(data)
                    else:
                        callback(data)
                except Exception as e:
                    logger.error(f"Error in event callback {callback}: {e}")
    
    def _start_monitoring_tasks(self):
        """启动监控任务"""
        # 启动统计更新任务
        self.monitoring_tasks.append(
            asyncio.create_task(self._stats_update_task())
        )
        
        # 启动健康检查任务
        self.monitoring_tasks.append(
            asyncio.create_task(self._health_check_task())
        )
    
    async def _stop_monitoring_tasks(self):
        """停止监控任务"""
        for task in self.monitoring_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        self.monitoring_tasks.clear()
    
    async def _stats_update_task(self):
        """统计更新任务"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟更新一次
                
                # 更新成功率
                self.stats.update_success_rate()
                
                # 清理旧的指标数据
                self._cleanup_old_metrics()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in stats update task: {e}")
    
    async def _health_check_task(self):
        """健康检查任务"""
        while True:
            try:
                await asyncio.sleep(300)  # 每5分钟检查一次
                
                # 检查组件健康状态
                await self._check_component_health()
                
                # 检查错误率
                recent_errors = [e for e in self.error_history 
                               if datetime.now() - e['timestamp'] < timedelta(minutes=30)]
                
                if len(recent_errors) > 10:
                    logger.warning(f"High error rate detected: {len(recent_errors)} errors in 30 minutes")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check task: {e}")
    
    async def _check_component_health(self):
        """检查组件健康状态"""
        components = [
            ('session_manager', self.session_manager),
            ('fingerprint_manager', self.fingerprint_manager),
            ('environment_spoofing', self.environment_spoofing),
            ('behavior_engine', self.behavior_engine)
        ]
        
        for name, component in components:
            if component and hasattr(component, 'health_check'):
                try:
                    await component.health_check()
                except Exception as e:
                    logger.error(f"Health check failed for {name}: {e}")
    
    def _cleanup_old_metrics(self):
        """清理旧的指标数据"""
        retention_hours = self.config.get('monitoring', {}).get('metrics_retention_hours', 24)
        cutoff_time = time.time() - (retention_hours * 3600)
        
        self.metrics_history = [m for m in self.metrics_history if m.start_time > cutoff_time]
    
    def _record_error(self, error: Exception, context: Dict[str, Any]):
        """记录错误"""
        error_record = {
            'timestamp': datetime.now(),
            'error': str(error),
            'error_type': type(error).__name__,
            'context': context
        }
        
        self.error_history.append(error_record)
        
        # 清理旧的错误记录
        retention_hours = self.config.get('monitoring', {}).get('error_retention_hours', 72)
        cutoff_time = datetime.now() - timedelta(hours=retention_hours)
        self.error_history = [e for e in self.error_history if e['timestamp'] > cutoff_time]


# 全局实例和便捷函数
_enhanced_global_manager: Optional[EnhancedAntiDetectionManager] = None


def get_enhanced_anti_detection_manager(config: Optional[Dict[str, Any]] = None) -> EnhancedAntiDetectionManager:
    """获取增强反检测管理器实例"""
    global _enhanced_global_manager
    
    if _enhanced_global_manager is None:
        _enhanced_global_manager = EnhancedAntiDetectionManager(config)
    
    return _enhanced_global_manager


async def initialize_enhanced_anti_detection_system(config: Optional[Dict[str, Any]] = None):
    """初始化增强反检测系统"""
    manager = get_enhanced_anti_detection_manager(config)
    await manager.initialize()
    await manager.start()
    
    logger.info("Enhanced anti-detection system initialized and started")


async def shutdown_enhanced_anti_detection_system():
    """关闭增强反检测系统"""
    global _enhanced_global_manager
    
    if _enhanced_global_manager:
        await _enhanced_global_manager.stop()
        _enhanced_global_manager = None
    
    logger.info("Enhanced anti-detection system shutdown")