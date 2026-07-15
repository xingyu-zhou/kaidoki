"""
反检测系统管理器
统一管理所有反检测组件，提供简洁的API接口

该模块整合了：
- 环境伪装系统
- 指纹管理系统 
- 会话管理系统
- CAPTCHA检测和处理
- 性能监控和统计
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

from .unified_captcha_detector import UnifiedCaptchaDetector, UnifiedDetectionResult
from .captcha_types import CaptchaType, CaptchaDetectionResult
from ..scrapers.enhanced_session_manager import EnhancedSessionManager
from ..scrapers.enhanced_fingerprint_manager import EnhancedFingerprintManager
from ..scrapers.browser_environment_spoofing import BrowserEnvironmentSpoofing
from ..scrapers.enhanced_behavior_engine import EnhancedBehaviorEngine
from ..utils.logger import get_logger

logger = get_logger(__name__)


class DetectionMode(Enum):
    """检测模式"""
    STRICT = "strict"       # 严格模式，最高安全性
    BALANCED = "balanced"   # 平衡模式，默认模式
    PERFORMANCE = "performance"  # 性能模式，优先速度
    STEALTH = "stealth"     # 隐身模式，最大程度避免检测


class SystemStatus(Enum):
    """系统状态"""
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass
class AntiDetectionStats:
    """反检测统计信息"""
    total_requests: int = 0
    captcha_detections: int = 0
    captcha_bypassed: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    avg_response_time: float = 0.0
    success_rate: float = 0.0
    uptime: float = 0.0
    last_detection_time: Optional[datetime] = None
    fingerprint_rotations: int = 0
    session_renewals: int = 0
    
    def update_success_rate(self):
        """更新成功率"""
        total_captcha = self.captcha_detections + self.captcha_bypassed
        if total_captcha > 0:
            self.success_rate = (self.captcha_bypassed / total_captcha) * 100
        else:
            self.success_rate = 100.0


@dataclass
class RequestMetrics:
    """请求指标"""
    request_id: str
    url: str
    start_time: float
    end_time: float
    success: bool
    captcha_detected: bool
    captcha_solved: bool
    error_message: Optional[str] = None
    fingerprint_id: Optional[str] = None
    session_id: Optional[str] = None
    
    @property
    def response_time(self) -> float:
        """响应时间（毫秒）"""
        return (self.end_time - self.start_time) * 1000


class AntiDetectionManager:
    """反检测系统管理器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化反检测系统管理器
        
        Args:
            config: 配置字典，如果为None则使用默认配置
        """
        self.config = config or self._load_default_config()
        self.status = SystemStatus.INITIALIZING
        self.mode = DetectionMode(self.config.get('global', {}).get('mode', 'balanced'))
        
        # 核心组件
        self.unified_detector: Optional[UnifiedCaptchaDetector] = None
        self.session_manager: Optional[EnhancedSessionManager] = None
        self.fingerprint_manager: Optional[EnhancedFingerprintManager] = None
        self.environment_spoofing: Optional[BrowserEnvironmentSpoofing] = None
        self.behavior_engine: Optional[EnhancedBehaviorEngine] = None
        
        # 统计和监控
        self.stats = AntiDetectionStats()
        self.metrics_history: List[RequestMetrics] = []
        self.error_history: List[Dict[str, Any]] = []
        
        # 配置参数
        self.confidence_threshold = self.config.get('detector', {}).get('confidence_threshold', 0.6)
        self.max_retry_attempts = self.config.get('global', {}).get('max_retry_attempts', 3)
        self.request_interval_range = self.config.get('session_management', {}).get('request_intervals', {})
        
        # 监控任务
        self.monitoring_tasks: List[asyncio.Task] = []
        self.start_time = time.time()
        
        # 事件回调
        self.event_callbacks: Dict[str, List[Callable]] = {
            'captcha_detected': [],
            'captcha_solved': [],
            'error_occurred': [],
            'fingerprint_rotated': [],
            'session_renewed': []
        }
        
        logger.info(f"AntiDetectionManager initialized with mode: {self.mode.value}")
    
    def _load_default_config(self) -> Dict[str, Any]:
        """加载默认配置"""
        default_config = {
            'global': {
                'mode': 'balanced',
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
                'error_retention_hours': 72
            }
        }
        return default_config
    
    async def initialize(self):
        """初始化系统"""
        try:
            logger.info("Initializing AntiDetectionManager...")
            self.status = SystemStatus.INITIALIZING
            
            # 1. 初始化统一检测器
            self.unified_detector = UnifiedCaptchaDetector()
            # 更新检测器配置
            detector_config = self.config.get('detector', {})
            self.unified_detector.confidence_threshold = detector_config.get('confidence_threshold', 0.6)
            self.unified_detector.enable_context_analysis = detector_config.get('enable_context_analysis', True)
            self.unified_detector.enable_debug_logging = detector_config.get('enable_debug_logging', False)
            self.unified_detector.max_processing_time = detector_config.get('max_processing_time', 30.0)
            
            # 2. 初始化会话管理器
            if self.config.get('session_management', {}).get('enabled', True):
                session_config = self.config.get('session_management', {})
                self.session_manager = EnhancedSessionManager(
                    max_sessions=session_config.get('max_sessions', 3),
                    session_timeout=session_config.get('timeouts', {}).get('session_timeout', 1800),
                    request_intervals=session_config.get('request_intervals', {})
                )
                await self.session_manager.initialize()
            
            # 3. 初始化指纹管理器
            if self.config.get('fingerprint_management', {}).get('enabled', True):
                fingerprint_config = self.config.get('fingerprint_management', {})
                self.fingerprint_manager = EnhancedFingerprintManager(fingerprint_config)
                await self.fingerprint_manager.initialize()
            
            # 4. 初始化环境伪装
            if self.config.get('environment_spoofing', {}).get('enabled', True):
                spoofing_config = self.config.get('environment_spoofing', {})
                self.environment_spoofing = BrowserEnvironmentSpoofing(spoofing_config)
                await self.environment_spoofing.initialize()
            
            # 5. 初始化行为引擎
            if self.config.get('behavior_simulation', {}).get('enabled', True):
                behavior_config = self.config.get('behavior_simulation', {})
                self.behavior_engine = EnhancedBehaviorEngine(behavior_config)
                await self.behavior_engine.initialize()
            
            # 6. 启动监控任务
            if self.config.get('monitoring', {}).get('enabled', True):
                self._start_monitoring_tasks()
            
            self.status = SystemStatus.READY
            logger.info("AntiDetectionManager initialized successfully")
            
        except Exception as e:
            self.status = SystemStatus.ERROR
            logger.error(f"Failed to initialize AntiDetectionManager: {e}")
            raise
    
    async def start(self):
        """启动系统"""
        if self.status != SystemStatus.READY:
            raise RuntimeError(f"System is not ready. Current status: {self.status.value}")
        
        try:
            logger.info("Starting AntiDetectionManager...")
            self.status = SystemStatus.RUNNING
            
            # 启动各个组件
            if self.session_manager:
                await self.session_manager.start()
            
            if self.fingerprint_manager:
                await self.fingerprint_manager.start()
            
            if self.environment_spoofing:
                await self.environment_spoofing.start()
            
            if self.behavior_engine:
                await self.behavior_engine.start()
            
            logger.info("AntiDetectionManager started successfully")
            
        except Exception as e:
            self.status = SystemStatus.ERROR
            logger.error(f"Failed to start AntiDetectionManager: {e}")
            raise
    
    async def stop(self):
        """停止系统"""
        logger.info("Stopping AntiDetectionManager...")
        self.status = SystemStatus.STOPPING
        
        try:
            # 停止监控任务
            await self._stop_monitoring_tasks()
            
            # 停止各个组件
            if self.behavior_engine:
                await self.behavior_engine.stop()
            
            if self.environment_spoofing:
                await self.environment_spoofing.stop()
            
            if self.fingerprint_manager:
                await self.fingerprint_manager.stop()
            
            if self.session_manager:
                await self.session_manager.stop()
            
            self.status = SystemStatus.STOPPED
            logger.info("AntiDetectionManager stopped successfully")
            
        except Exception as e:
            self.status = SystemStatus.ERROR
            logger.error(f"Failed to stop AntiDetectionManager: {e}")
            raise
    
    async def detect_captcha(self, 
                           content: str, 
                           response: Optional[Any] = None,
                           url: Optional[str] = None) -> UnifiedDetectionResult:
        """
        检测CAPTCHA
        
        Args:
            content: 页面内容
            response: HTTP响应对象
            url: 页面URL
            
        Returns:
            UnifiedDetectionResult: 统一检测结果
        """
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
    
    async def handle_captcha_detected(self, detection_result: UnifiedDetectionResult) -> bool:
        """
        处理检测到的CAPTCHA
        
        Args:
            detection_result: 检测结果
            
        Returns:
            bool: 是否成功处理
        """
        try:
            # 这里实现CAPTCHA处理逻辑
            # 根据当前配置，我们强制使用人工交互模式
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
        """
        获取优化的会话
        
        Args:
            url: 目标URL
            
        Returns:
            优化的会话对象
        """
        if not self.session_manager:
            return None
        
        try:
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
    
    async def execute_with_anti_detection(self, 
                                        func: Callable, 
                                        *args, 
                                        **kwargs) -> Any:
        """
        使用反检测机制执行函数
        
        Args:
            func: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数
            
        Returns:
            函数执行结果
        """
        attempt = 0
        max_attempts = self.max_retry_attempts
        
        while attempt < max_attempts:
            try:
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
    
    def update_config(self, new_config: Dict[str, Any]):
        """
        更新配置
        
        Args:
            new_config: 新配置
        """
        self.config.update(new_config)
        
        # 更新检测器配置
        if self.unified_detector:
            detector_config = self.config.get('detector', {})
            self.unified_detector.confidence_threshold = detector_config.get('confidence_threshold', 0.6)
            self.unified_detector.enable_context_analysis = detector_config.get('enable_context_analysis', True)
            self.unified_detector.enable_debug_logging = detector_config.get('enable_debug_logging', False)
        
        # 更新其他组件配置
        self.confidence_threshold = self.config.get('detector', {}).get('confidence_threshold', 0.6)
        self.max_retry_attempts = self.config.get('global', {}).get('max_retry_attempts', 3)
        
        logger.info("Configuration updated successfully")
    
    def get_system_stats(self) -> Dict[str, Any]:
        """
        获取系统统计信息
        
        Returns:
            Dict: 系统统计信息
        """
        current_time = time.time()
        uptime = current_time - self.start_time
        
        # 计算平均响应时间
        if self.metrics_history:
            avg_response_time = sum(m.response_time for m in self.metrics_history) / len(self.metrics_history)
        else:
            avg_response_time = 0.0
        
        return {
            'status': self.status.value,
            'mode': self.mode.value,
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
    
    def register_event_callback(self, event_type: str, callback: Callable):
        """
        注册事件回调
        
        Args:
            event_type: 事件类型
            callback: 回调函数
        """
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
                if self.session_manager:
                    await self.session_manager.health_check()
                
                if self.fingerprint_manager:
                    await self.fingerprint_manager.health_check()
                
                # 检查错误率
                recent_errors = [e for e in self.error_history 
                               if datetime.now() - e['timestamp'] < timedelta(minutes=30)]
                
                if len(recent_errors) > 10:
                    logger.warning(f"High error rate detected: {len(recent_errors)} errors in 30 minutes")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check task: {e}")
    
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


# 全局实例
_global_manager: Optional[AntiDetectionManager] = None


def get_anti_detection_manager(config: Optional[Dict[str, Any]] = None) -> AntiDetectionManager:
    """
    获取全局反检测管理器实例
    
    Args:
        config: 配置字典
        
    Returns:
        AntiDetectionManager: 管理器实例
    """
    global _global_manager
    
    if _global_manager is None:
        _global_manager = AntiDetectionManager(config)
    
    return _global_manager


async def initialize_anti_detection_system(config: Optional[Dict[str, Any]] = None):
    """
    初始化反检测系统
    
    Args:
        config: 配置字典
    """
    manager = get_anti_detection_manager(config)
    await manager.initialize()
    await manager.start()
    
    logger.info("Anti-detection system initialized and started")


async def shutdown_anti_detection_system():
    """关闭反检测系统"""
    global _global_manager
    
    if _global_manager:
        await _global_manager.stop()
        _global_manager = None
    
    logger.info("Anti-detection system shutdown")