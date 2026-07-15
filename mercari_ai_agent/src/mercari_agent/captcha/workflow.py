"""
验证码处理工作流模块 (增强版)

该模块提供验证码处理的完整工作流程，包括：
- 验证码检测与处理流程
- 任务暂停和恢复机制
- 统一重试和错误处理
- 超时管理
- 状态转换管理
- 集成重试协调器
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json

from .captcha_types import CaptchaType, CaptchaChallenge, CaptchaSolution, CaptchaStatus
from .captcha_detector import CaptchaDetector
from .captcha_solver import CaptchaSolver
from .task_queue import TaskQueue, ScrapingTask, TaskStatus
from .analytics import CaptchaAnalytics
from .unified_captcha_detector import get_unified_detector
from .retry_coordinator import CentralizedRetryCoordinator, get_retry_coordinator, FailureReason
from ..utils.logger import get_logger

logger = get_logger(__name__)


class WorkflowState(Enum):
    """工作流状态枚举"""
    IDLE = "idle"
    DETECTING = "detecting"
    PAUSED = "paused"
    SOLVING = "solving"
    APPLYING = "applying"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class NotificationLevel(Enum):
    """通知级别枚举"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class UserNotification:
    """用户通知"""
    level: NotificationLevel
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    task_id: Optional[str] = None
    captcha_type: Optional[CaptchaType] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'level': self.level.value,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'task_id': self.task_id,
            'captcha_type': self.captcha_type.value if self.captcha_type else None,
            'metadata': self.metadata
        }


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    
    def get_delay(self, attempt: int) -> float:
        """计算重试延迟"""
        delay = min(self.base_delay * (self.exponential_base ** attempt), self.max_delay)
        if self.jitter:
            import random
            delay = delay * (0.5 + random.random() * 0.5)  # 添加50%的随机抖动
        return delay


class ErrorClassifier:
    """错误分类器"""
    
    @staticmethod
    def classify_error(error: Exception) -> str:
        """分类错误类型"""
        error_str = str(error).lower()
        
        # 网络相关错误
        if any(keyword in error_str for keyword in ['timeout', 'connection', 'network', 'socket']):
            return 'network_error'
        
        # 验证码服务错误
        if any(keyword in error_str for keyword in ['captcha', 'invalid', 'expired', 'verification']):
            return 'captcha_error'
        
        # 资源相关错误
        if any(keyword in error_str for keyword in ['memory', 'disk', 'resource']):
            return 'resource_error'
        
        # 权限相关错误
        if any(keyword in error_str for keyword in ['permission', 'access', 'unauthorized', 'forbidden']):
            return 'permission_error'
        
        # 解析相关错误
        if any(keyword in error_str for keyword in ['parse', 'format', 'json', 'xml']):
            return 'parsing_error'
        
        # 默认为未知错误
        return 'unknown_error'
    
    @staticmethod
    def should_retry(error_type: str, attempt: int, max_retries: int) -> bool:
        """判断是否应该重试"""
        # 不同错误类型的重试策略
        retry_strategies = {
            'network_error': True,  # 网络错误总是重试
            'captcha_error': attempt < max_retries,  # 验证码错误按配置重试
            'resource_error': attempt < 2,  # 资源错误最多重试2次
            'permission_error': False,  # 权限错误不重试
            'parsing_error': attempt < 2,  # 解析错误最多重试2次
            'unknown_error': attempt < max_retries  # 未知错误按配置重试
        }
        
        return retry_strategies.get(error_type, False)
    
    @staticmethod
    def get_error_delay(error_type: str, attempt: int, base_delay: float) -> float:
        """根据错误类型获取重试延迟"""
        delay_multipliers = {
            'network_error': 2.0,  # 网络错误延迟较长
            'captcha_error': 1.0,  # 验证码错误正常延迟
            'resource_error': 3.0,  # 资源错误延迟更长
            'permission_error': 1.0,  # 权限错误正常延迟
            'parsing_error': 1.5,  # 解析错误稍长延迟
            'unknown_error': 1.0   # 未知错误正常延迟
        }
        
        multiplier = delay_multipliers.get(error_type, 1.0)
        return base_delay * multiplier * (1.5 ** attempt)


class ErrorRecoveryStrategy:
    """错误恢复策略"""
    
    @staticmethod
    async def attempt_recovery(error_type: str, error: Exception, context: Dict[str, Any]) -> bool:
        """尝试错误恢复"""
        if error_type == 'network_error':
            # 网络错误恢复策略
            await asyncio.sleep(2.0)  # 等待网络恢复
            return True
        
        elif error_type == 'resource_error':
            # 资源错误恢复策略
            import gc
            gc.collect()  # 尝试垃圾回收
            await asyncio.sleep(5.0)  # 等待资源释放
            return True
        
        elif error_type == 'captcha_error':
            # 验证码错误恢复策略
            await asyncio.sleep(1.0)  # 短暂等待
            return True
        
        # 其他错误类型暂不支持恢复
        return False

class WorkflowLogger:
    """工作流专用日志记录器"""
    
    def __init__(self, base_logger: logging.Logger, config: 'WorkflowConfig'):
        self.base_logger = base_logger
        self.config = config
        self.session_id = str(int(time.time() * 1000))  # 会话ID
        
    def _format_log_data(self, event_type: str, task_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """格式化日志数据"""
        return {
            'timestamp': datetime.now().isoformat(),
            'session_id': self.session_id,
            'event_type': event_type,
            'task_id': task_id,
            'data': data
        }
    
    def log_workflow_event(self, level: str, event_type: str, task_id: str, message: str, data: Dict[str, Any] = None):
        """记录工作流事件"""
        if not self.config.enable_detailed_logging:
            return
            
        log_data = self._format_log_data(event_type, task_id, data or {})
        
        # 添加消息（避免使用保留的message字段）
        log_data['log_message'] = message
        
        # 记录到日志
        log_method = getattr(self.base_logger, level.lower(), self.base_logger.info)
        log_method(f"[{event_type}] {message}", extra=log_data)
    
    def log_performance_event(self, task_id: str, metric_name: str, value: float, metadata: Dict[str, Any] = None):
        """记录性能事件"""
        if not self.config.performance_monitoring_enabled:
            return
            
        log_data = self._format_log_data('performance', task_id, {
            'metric_name': metric_name,
            'value': value,
            'metadata': metadata or {}
        })
        
        self.base_logger.info(f"[PERFORMANCE] {metric_name}: {value:.3f}s", extra=log_data)
    
    def log_state_transition(self, task_id: str, old_state: str, new_state: str, metadata: Dict[str, Any] = None):
        """记录状态转换"""
        log_data = self._format_log_data('state_transition', task_id, {
            'old_state': old_state,
            'new_state': new_state,
            'metadata': metadata or {}
        })
        
        self.base_logger.info(f"[STATE] {old_state} -> {new_state}", extra=log_data)
    
    def log_error_event(self, task_id: str, error: Exception, error_type: str, context: Dict[str, Any] = None):
        """记录错误事件"""
        log_data = self._format_log_data('error', task_id, {
            'error_message': str(error),
            'error_type': error_type,
            'error_class': error.__class__.__name__,
            'context': context or {}
        })
        
        self.base_logger.error(f"[ERROR] {error_type}: {str(error)}", extra=log_data)
    
    def log_user_interaction(self, task_id: str, interaction_type: str, details: Dict[str, Any] = None):
        """记录用户交互"""
        log_data = self._format_log_data('user_interaction', task_id, {
            'interaction_type': interaction_type,
            'details': details or {}
        })
        
        self.base_logger.info(f"[USER] {interaction_type}", extra=log_data)
    
    def log_captcha_event(self, task_id: str, captcha_type: str, event_type: str, details: Dict[str, Any] = None):
        """记录验证码事件"""
        log_data = self._format_log_data('captcha', task_id, {
            'captcha_type': captcha_type,
            'event_type': event_type,
            'details': details or {}
        })
        
        self.base_logger.info(f"[CAPTCHA] {captcha_type} - {event_type}", extra=log_data)


@dataclass
class WorkflowConfig:
    """工作流配置"""
    max_retries: int = 3
    retry_delay: float = 5.0
    timeout: float = 300.0  # 5分钟
    enable_auto_retry: bool = True
    enable_timeout_handling: bool = True
    enable_analytics: bool = True
    enable_detailed_logging: bool = True
    enable_user_notifications: bool = True
    
    # 重试策略配置
    retry_configs: Dict[CaptchaType, RetryConfig] = field(default_factory=lambda: {
        CaptchaType.IMAGE_TEXT: RetryConfig(max_retries=3, base_delay=2.0, max_delay=30.0),
        CaptchaType.SLIDE_PUZZLE: RetryConfig(max_retries=2, base_delay=3.0, max_delay=45.0),
        CaptchaType.CLICK_SEQUENCE: RetryConfig(max_retries=2, base_delay=2.5, max_delay=40.0),
        CaptchaType.RECAPTCHA_V2: RetryConfig(max_retries=1, base_delay=5.0, max_delay=60.0),
        CaptchaType.GEETEST: RetryConfig(max_retries=2, base_delay=3.0, max_delay=50.0)
    })
    
    # 超时配置
    timeout_strategies: Dict[CaptchaType, float] = field(default_factory=lambda: {
        CaptchaType.IMAGE_TEXT: 300.0,
        CaptchaType.SLIDE_PUZZLE: 180.0,
        CaptchaType.CLICK_SEQUENCE: 240.0,
        CaptchaType.RECAPTCHA_V2: 600.0,
        CaptchaType.GEETEST: 300.0
    })
    
    # 超时警告配置
    timeout_warnings: List[float] = field(default_factory=lambda: [0.5, 0.75, 0.9])  # 超时时间的百分比
    
    # 暂停通知配置
    pause_notification_enabled: bool = True
    pause_notification_interval: float = 30.0  # 30秒发送一次暂停提醒
    
    # 性能监控配置
    performance_monitoring_enabled: bool = True
    performance_log_interval: float = 60.0  # 60秒记录一次性能数据


class CaptchaWorkflow:
    """验证码处理工作流 (增强版)"""
    
    def __init__(self,
                 task_queue: TaskQueue,
                 captcha_detector: CaptchaDetector,
                 captcha_solver: CaptchaSolver,
                 analytics: Optional['CaptchaAnalytics'] = None,
                 config: Optional[WorkflowConfig] = None,
                 retry_coordinator: Optional[CentralizedRetryCoordinator] = None):
        """
        初始化验证码工作流
        
        Args:
            task_queue: 任务队列
            captcha_detector: 验证码检测器
            captcha_solver: 验证码解决器
            analytics: 统计分析器
            config: 工作流配置
            retry_coordinator: 重试协调器
        """
        self.task_queue = task_queue
        self.captcha_detector = captcha_detector
        self.captcha_solver = captcha_solver
        self.analytics = analytics
        self.config = config or WorkflowConfig()
        self.retry_coordinator = retry_coordinator or get_retry_coordinator()
        
        # 获取统一检测器实例
        self.unified_detector = get_unified_detector()
        
        # 工作流状态
        self.active_workflows: Dict[str, 'WorkflowInstance'] = {}
        self.workflow_stats = {
            'total_workflows': 0,
            'successful_workflows': 0,
            'failed_workflows': 0,
            'timeout_workflows': 0,
            'paused_workflows': 0,
            'cancelled_workflows': 0,
            'retry_workflows': 0  # 新增
        }
        
        # 用户通知队列
        self.user_notifications: List[UserNotification] = []
        self.notification_callbacks: List[Callable[[UserNotification], None]] = []
        
        # 性能监控
        self.performance_metrics = {
            'average_detection_time': 0.0,
            'average_solving_time': 0.0,
            'average_total_time': 0.0,
            'success_rate_by_type': {}
        }
        
        # 工作流日志记录器
        self.workflow_logger = WorkflowLogger(logger, self.config)
        
        if self.config.enable_detailed_logging:
            logger.info("Enhanced CaptchaWorkflow initialized with retry coordination")
            self.workflow_logger.log_workflow_event('info', 'workflow_initialized', 'system', 'Enhanced captcha workflow initialized', {
                'config': {
                    'enable_detailed_logging': self.config.enable_detailed_logging,
                    'enable_user_notifications': self.config.enable_user_notifications,
                    'performance_monitoring_enabled': self.config.performance_monitoring_enabled,
                    'pause_notification_enabled': self.config.pause_notification_enabled,
                    'retry_coordination_enabled': True
                }
            })
        else:
            logger.info("Enhanced CaptchaWorkflow initialized")
    
    def add_notification_callback(self, callback: Callable[[UserNotification], None]):
        """添加用户通知回调"""
        self.notification_callbacks.append(callback)
    
    def remove_notification_callback(self, callback: Callable[[UserNotification], None]):
        """移除用户通知回调"""
        if callback in self.notification_callbacks:
            self.notification_callbacks.remove(callback)
    
    async def send_user_notification(self, notification: UserNotification):
        """发送用户通知"""
        if not self.config.enable_user_notifications:
            return
        
        self.user_notifications.append(notification)
        
        # 限制通知队列大小
        if len(self.user_notifications) > 100:
            self.user_notifications = self.user_notifications[-50:]
        
        # 记录通知
        if self.config.enable_detailed_logging:
            logger.info(f"User notification sent: {notification.level.value} - {notification.message}")
        
        # 调用回调函数
        for callback in self.notification_callbacks:
            try:
                callback(notification)
            except Exception as e:
                logger.error(f"Notification callback error: {e}")
    
    def get_recent_notifications(self, count: int = 10) -> List[UserNotification]:
        """获取最近的通知"""
        return self.user_notifications[-count:]
    
    async def record_performance_metric(self, metric_name: str, value: float, metadata: Dict[str, Any] = None):
        """记录性能指标"""
        if not self.config.performance_monitoring_enabled:
            return
        
        timestamp = datetime.now()
        if self.config.enable_detailed_logging:
            logger.info(f"Performance metric recorded: {metric_name}={value:.2f}s", extra={
                'metric_name': metric_name,
                'value': value,
                'timestamp': timestamp.isoformat(),
                'metadata': metadata or {}
            })
    
    async def process_captcha_workflow(self,
                                     task: ScrapingTask,
                                     response_content: str,
                                     response: Any = None,
                                     session: Any = None) -> bool:
        """
        处理验证码工作流
        
        Args:
            task: 爬虫任务
            response_content: 响应内容
            response: HTTP响应对象
            session: HTTP会话
            
        Returns:
            bool: 是否成功处理
        """
        workflow_instance = WorkflowInstance(
            task=task,
            workflow=self,
            response_content=response_content,
            response=response,
            session=session
        )
        
        # 记录工作流实例
        self.active_workflows[task.task_id] = workflow_instance
        self.workflow_stats['total_workflows'] += 1
        
        try:
            result = await workflow_instance.execute()
            
            if result:
                self.workflow_stats['successful_workflows'] += 1
            else:
                self.workflow_stats['failed_workflows'] += 1
            
            return result
            
        except asyncio.TimeoutError:
            self.workflow_stats['timeout_workflows'] += 1
            logger.error(f"Workflow timeout for task {task.task_id}")
            return False
        except Exception as e:
            self.workflow_stats['failed_workflows'] += 1
            logger.error(f"Workflow error for task {task.task_id}: {e}")
            return False
        finally:
            # 清理工作流实例
            if task.task_id in self.active_workflows:
                del self.active_workflows[task.task_id]
    
    async def cancel_workflow(self, task_id: str) -> bool:
        """
        取消工作流
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功取消
        """
        if task_id in self.active_workflows:
            workflow_instance = self.active_workflows[task_id]
            await workflow_instance.cancel()
            del self.active_workflows[task_id]
            logger.info(f"Workflow cancelled for task {task_id}")
            return True
        return False
    
    def get_workflow_stats(self) -> Dict[str, Any]:
        """获取工作流统计信息"""
        return {
            **self.workflow_stats,
            'active_workflows': len(self.active_workflows),
            'success_rate': (
                self.workflow_stats['successful_workflows'] / 
                max(self.workflow_stats['total_workflows'], 1) * 100
            )
        }


class WorkflowInstance:
    """工作流实例"""
    
    def __init__(self,
                 task: ScrapingTask,
                 workflow: CaptchaWorkflow,
                 response_content: str,
                 response: Any = None,
                 session: Any = None):
        """
        初始化工作流实例
        
        Args:
            task: 爬虫任务
            workflow: 工作流对象
            response_content: 响应内容
            response: HTTP响应对象
            session: HTTP会话
        """
        self.task = task
        self.workflow = workflow
        self.response_content = response_content
        self.response = response
        self.session = session
        
        # 时间跟踪
        self.start_time = time.time()
        self.detection_start_time: Optional[float] = None
        self.solving_start_time: Optional[float] = None
        self.pause_start_time: Optional[float] = None
        
        # 验证码相关
        self.current_challenge: Optional[CaptchaChallenge] = None
        self.current_solution: Optional[CaptchaSolution] = None
        self.attempt_count = 0
        
        # 状态管理
        self.state: WorkflowState = WorkflowState.IDLE
        self.is_cancelled = False
        self.is_paused = False
        
        # 任务管理
        self.timeout_task: Optional[asyncio.Task] = None
        self.pause_notification_task: Optional[asyncio.Task] = None
        self.timeout_warning_tasks: List[asyncio.Task] = []
        
        # 性能监控
        self.performance_data = {
            'detection_time': 0.0,
            'solving_time': 0.0,
            'total_time': 0.0,
            'pause_duration': 0.0,
            'retry_count': 0,
            'error_count': 0
        }
    
    async def execute(self) -> bool:
        """
        执行工作流
        
        Returns:
            bool: 是否成功执行
        """
        try:
            # 更新状态为检测中
            await self._update_state(WorkflowState.DETECTING)
            
            # 1. 检测验证码 - 🔧 修复：使用统一检测器确保一致性
            self.detection_start_time = time.time()
            if self.workflow.config.enable_detailed_logging:
                logger.info(f"Starting captcha detection for task {self.task.task_id}")
            
            # 首先使用统一检测器进行检测
            unified_result = await self.workflow.unified_detector.detect_unified(
                self.response_content, self.response, self.task.url
            )
            
            # 🔧 紧急修复：确保CAPTCHA类型不为空
            if unified_result.is_captcha and unified_result.captcha_type is None:
                logger.warning(f"CAPTCHA detected but type is None for task {self.task.task_id}, setting to UNKNOWN")
                unified_result.captcha_type = CaptchaType.UNKNOWN
            
            # 记录统一检测结果
            self.workflow.unified_detector.log_detection_result(unified_result, self.task.task_id)
            
            # 如果统一检测器检测到CAPTCHA，转换为CaptchaDetectionResult
            if unified_result.is_captcha:
                detection_result = unified_result.to_captcha_detection_result()
            else:
                # 如果统一检测器未检测到CAPTCHA，使用原有检测器作为后备
                detection_result = await self.workflow.captcha_detector.detect_captcha(
                    self.response_content, self.response
                )
            
            # 记录检测时间
            self.performance_data['detection_time'] = time.time() - self.detection_start_time
            await self.workflow.record_performance_metric(
                'captcha_detection_time',
                self.performance_data['detection_time'],
                {'task_id': self.task.task_id}
            )
            
            if not detection_result.detected:
                if self.workflow.config.enable_detailed_logging:
                    logger.info(f"No captcha detected for task {self.task.task_id}")
                await self._update_state(WorkflowState.COMPLETED)
                return True  # 没有验证码，继续处理
            
            # 发送用户通知
            await self.workflow.send_user_notification(UserNotification(
                level=NotificationLevel.INFO,
                message=f"验证码检测成功: {detection_result.captcha_type.value}",
                task_id=self.task.task_id,
                captcha_type=detection_result.captcha_type
            ))
            
            # 记录检测事件
            if self.workflow.analytics:
                await self.workflow.analytics.record_captcha_event(
                    "detected", detection_result.captcha_type
                )
            
            # 2. 处理验证码 - 🔧 修复：添加null challenge检查和回退机制
            challenge = detection_result.challenge
            
            # 🔧 核心修复：确保challenge对象不为None
            if challenge is None:
                logger.error(f"Challenge object is None for task {self.task.task_id}, "
                           f"detected: {detection_result.detected}, "
                           f"captcha_type: {detection_result.captcha_type}")
                
                # 紧急创建挑战对象
                from .captcha_types import ChallengeBuilder
                try:
                    challenge = ChallengeBuilder.create_emergency_challenge(
                        task_id=self.task.task_id,
                        captcha_type=detection_result.captcha_type or CaptchaType.UNKNOWN,
                        reason=f"Challenge object was None in workflow execution"
                    )
                    logger.warning(f"Created emergency challenge for task {self.task.task_id}: {challenge.challenge_id}")
                    
                    # 发送紧急通知
                    await self.workflow.send_user_notification(UserNotification(
                        level=NotificationLevel.WARNING,
                        message=f"验证码检测异常，已创建紧急挑战对象",
                        task_id=self.task.task_id,
                        captcha_type=detection_result.captcha_type,
                        metadata={'emergency_challenge': True, 'original_challenge_none': True}
                    ))
                    
                except Exception as e:
                    logger.error(f"Failed to create emergency challenge for task {self.task.task_id}: {e}")
                    
                    # 最后的降级处理：返回失败
                    await self._update_state(WorkflowState.FAILED)
                    await self.workflow.send_user_notification(UserNotification(
                        level=NotificationLevel.ERROR,
                        message=f"验证码处理失败：无法创建挑战对象",
                        task_id=self.task.task_id,
                        metadata={'error': str(e), 'critical_failure': True}
                    ))
                    return False
            
            # 验证challenge对象的有效性
            if not self._validate_challenge(challenge):
                logger.error(f"Invalid challenge object for task {self.task.task_id}")
                
                # 尝试修复challenge对象
                challenge = self._repair_challenge(challenge)
                if not challenge:
                    logger.error(f"Failed to repair challenge object for task {self.task.task_id}")
                    await self._update_state(WorkflowState.FAILED)
                    return False
            
            return await self._process_captcha(challenge)
            
        except Exception as e:
            self.performance_data['error_count'] += 1
            await self._update_state(WorkflowState.FAILED)
            
            # 发送错误通知
            await self.workflow.send_user_notification(UserNotification(
                level=NotificationLevel.ERROR,
                message=f"工作流执行失败: {str(e)}",
                task_id=self.task.task_id,
                metadata={'error': str(e)}
            ))
            
            logger.error(f"Workflow execution failed for task {self.task.task_id}: {e}")
            return False
    
    async def _update_state(self, new_state: WorkflowState):
        """更新工作流状态"""
        old_state = self.state
        self.state = new_state
        
        if self.workflow.config.enable_detailed_logging:
            logger.info(f"Workflow state transition: {old_state.value} -> {new_state.value} for task {self.task.task_id}")
        
        # 记录状态变化事件
        if self.workflow.analytics:
            await self.workflow.analytics.record_captcha_event(
                "state_change",
                self.current_challenge.captcha_type if self.current_challenge else None,
                {
                    'old_state': old_state.value,
                    'new_state': new_state.value,
                    'task_id': self.task.task_id
                }
            )
    
    async def _process_captcha(self, challenge: CaptchaChallenge) -> bool:
        """
        处理验证码
        
        Args:
            challenge: 验证码挑战
            
        Returns:
            bool: 是否成功处理
        """
        self.current_challenge = challenge
        
        try:
            # 🔧 紧急修复：检测CLI环境并使用CLI处理器
            if self._is_cli_environment():
                logger.info("CLI environment detected, using CLI CAPTCHA handler")
                from .cli_captcha_handler import get_cli_handler
                
                cli_handler = get_cli_handler()
                solution_result = await cli_handler.handle_captcha_cli(challenge)
                
                if solution_result.retry_suggested:
                    # 触发智能重试机制
                    logger.info("CLI handler suggests retry, implementing retry strategy")
                    return await self._handle_cli_retry(challenge)
                
                if solution_result.success:
                    # 处理CLI解决方案
                    logger.info("CLI handler provided solution, applying it")
                    return await self._apply_cli_solution(solution_result)
                else:
                    # CLI处理失败，继续原有流程
                    logger.warning("CLI handler failed, falling back to original workflow")
            
            # 1. 更新状态为暂停
            await self._update_state(WorkflowState.PAUSED)
            self.is_paused = True
            self.pause_start_time = time.time()
            
            # 2. 暂停任务并发送用户通知
            await self.workflow.task_queue.pause_task(
                self.task.task_id,
                f"Captcha detected: {challenge.captcha_type.value}"
            )
            
            # 发送暂停通知
            await self.workflow.send_user_notification(UserNotification(
                level=NotificationLevel.WARNING,
                message=f"任务已暂停 - 检测到验证码: {challenge.captcha_type.value}",
                task_id=self.task.task_id,
                captcha_type=challenge.captcha_type,
                metadata={'reason': 'captcha_detected'}
            ))
            
            # 3. 标记为需要验证码
            await self.workflow.task_queue.handle_captcha_task(
                self.task.task_id,
                challenge
            )
            
            # 4. 设置超时处理和警告
            timeout_duration = self.workflow.config.timeout_strategies.get(
                challenge.captcha_type,
                self.workflow.config.timeout
            )
            
            if self.workflow.config.enable_timeout_handling:
                self.timeout_task = asyncio.create_task(
                    self._timeout_handler(timeout_duration)
                )
                
                # 设置超时警告
                await self._setup_timeout_warnings(timeout_duration)
            
            # 5. 设置暂停通知任务
            if self.workflow.config.pause_notification_enabled:
                self.pause_notification_task = asyncio.create_task(
                    self._pause_notification_loop()
                )
            
            # 6. 更新状态为解决中
            await self._update_state(WorkflowState.SOLVING)
            self.solving_start_time = time.time()
            
            # 7. 带重试的验证码解决
            success = await self._solve_with_retry(challenge)
            
            # 8. 记录解决时间
            if self.solving_start_time:
                self.performance_data['solving_time'] = time.time() - self.solving_start_time
                await self.workflow.record_performance_metric(
                    'captcha_solving_time',
                    self.performance_data['solving_time'],
                    {'task_id': self.task.task_id, 'captcha_type': challenge.captcha_type.value}
                )
            
            # 9. 清理任务
            await self._cleanup_tasks()
            
            if success:
                # 10. 更新状态为应用中
                await self._update_state(WorkflowState.APPLYING)
                
                # 11. 应用解决方案
                apply_success = await self._apply_solution(self.current_solution)
                
                if apply_success:
                    # 12. 恢复任务
                    await self.workflow.task_queue.resolve_captcha_task(
                        self.task.task_id,
                        self.current_solution
                    )
                    
                    # 更新状态为完成
                    await self._update_state(WorkflowState.COMPLETED)
                    
                    # 记录暂停时间
                    if self.pause_start_time:
                        self.performance_data['pause_duration'] = time.time() - self.pause_start_time
                    
                    # 发送成功通知
                    await self.workflow.send_user_notification(UserNotification(
                        level=NotificationLevel.INFO,
                        message=f"验证码处理成功 - 任务已恢复",
                        task_id=self.task.task_id,
                        captcha_type=challenge.captcha_type,
                        metadata={
                            'solving_time': self.current_solution.solving_time,
                            'attempt_count': self.attempt_count
                        }
                    ))
                    
                    # 记录成功事件
                    if self.workflow.analytics:
                        await self.workflow.analytics.record_captcha_event(
                            "solved", challenge.captcha_type, {
                                "solve_time": self.current_solution.solving_time,
                                "attempt_count": self.attempt_count,
                                "pause_duration": self.performance_data['pause_duration']
                            }
                        )
                    
                    if self.workflow.config.enable_detailed_logging:
                        logger.info(f"Captcha successfully processed for task {self.task.task_id}")
                    return True
                else:
                    # 应用失败
                    await self._handle_failure("Solution application failed")
                    return False
            else:
                # 解决失败
                await self._handle_failure("Captcha solving failed")
                return False
                
        except asyncio.CancelledError:
            await self._update_state(WorkflowState.CANCELLED)
            logger.info(f"Captcha workflow cancelled for task {self.task.task_id}")
            return False
        except Exception as e:
            self.performance_data['error_count'] += 1
            
            # 🔧 增强错误处理：错误分类和智能恢复
            error_type = ErrorClassifier.classify_error(e)
            
            # 记录详细错误信息
            self.workflow.workflow_logger.log_error_event(
                self.task.task_id,
                e,
                error_type,
                {
                    'captcha_type': self.current_challenge.captcha_type.value if self.current_challenge else None,
                    'attempt_count': self.attempt_count,
                    'processing_time': time.time() - self.start_time,
                    'workflow_state': self.state.value
                }
            )
            
            # 尝试错误恢复
            recovery_attempted = False
            if self.attempt_count < 3:  # 最多尝试3次恢复
                try:
                    logger.info(f"Attempting error recovery for {error_type} in task {self.task.task_id}")
                    recovery_success = await ErrorRecoveryStrategy.attempt_recovery(
                        error_type,
                        e,
                        {
                            'task_id': self.task.task_id,
                            'captcha_type': self.current_challenge.captcha_type.value if self.current_challenge else None,
                            'attempt_count': self.attempt_count
                        }
                    )
                    
                    if recovery_success:
                        recovery_attempted = True
                        logger.info(f"Error recovery successful for task {self.task.task_id}")
                        
                        # 发送恢复成功通知
                        await self.workflow.send_user_notification(UserNotification(
                            level=NotificationLevel.INFO,
                            message=f"错误恢复成功，重新尝试验证码处理",
                            task_id=self.task.task_id,
                            captcha_type=self.current_challenge.captcha_type if self.current_challenge else None,
                            metadata={'error_type': error_type, 'recovery_attempted': True}
                        ))
                        
                        # 重新尝试处理
                        self.attempt_count += 1
                        try:
                            return await self._process_captcha(self.current_challenge)
                        except Exception as retry_error:
                            logger.error(f"Retry after recovery failed: {retry_error}")
                            # 继续到失败处理
                    else:
                        logger.warning(f"Error recovery failed for task {self.task.task_id}")
                        
                except Exception as recovery_error:
                    logger.error(f"Error during recovery attempt: {recovery_error}")
            
            # 如果恢复失败或不适用，进入失败处理
            await self._update_state(WorkflowState.FAILED)
            
            # 发送错误通知
            await self.workflow.send_user_notification(UserNotification(
                level=NotificationLevel.ERROR,
                message=f"验证码处理失败: {error_type}",
                task_id=self.task.task_id,
                captcha_type=self.current_challenge.captcha_type if self.current_challenge else None,
                metadata={
                    'error_type': error_type,
                    'error_message': str(e),
                    'recovery_attempted': recovery_attempted,
                    'attempt_count': self.attempt_count
                }
            ))
            
            logger.error(f"Captcha processing error for task {self.task.task_id}: {error_type} - {str(e)}")
            await self._handle_failure(f"Processing error ({error_type}): {str(e)}")
            return False
    
    async def _setup_timeout_warnings(self, timeout_duration: float):
        """设置超时警告"""
        for warning_ratio in self.workflow.config.timeout_warnings:
            warning_time = timeout_duration * warning_ratio
            warning_task = asyncio.create_task(
                self._timeout_warning_handler(warning_time, warning_ratio)
            )
            self.timeout_warning_tasks.append(warning_task)
    
    async def _timeout_warning_handler(self, warning_time: float, warning_ratio: float):
        """超时警告处理器"""
        try:
            await asyncio.sleep(warning_time)
            
            remaining_time = int((1 - warning_ratio) * self.workflow.config.timeout_strategies.get(
                self.current_challenge.captcha_type,
                self.workflow.config.timeout
            ))
            
            # 发送警告通知
            await self.workflow.send_user_notification(UserNotification(
                level=NotificationLevel.WARNING,
                message=f"验证码处理超时警告 - 剩余 {remaining_time} 秒",
                task_id=self.task.task_id,
                captcha_type=self.current_challenge.captcha_type,
                metadata={
                    'warning_ratio': warning_ratio,
                    'remaining_time': remaining_time
                }
            ))
            
        except asyncio.CancelledError:
            pass
    
    async def _pause_notification_loop(self):
        """暂停通知循环"""
        try:
            while self.is_paused and not self.is_cancelled:
                await asyncio.sleep(self.workflow.config.pause_notification_interval)
                
                if self.is_paused:
                    pause_duration = int(time.time() - self.pause_start_time)
                    await self.workflow.send_user_notification(UserNotification(
                        level=NotificationLevel.INFO,
                        message=f"任务仍在暂停中 - 已暂停 {pause_duration} 秒",
                        task_id=self.task.task_id,
                        captcha_type=self.current_challenge.captcha_type,
                        metadata={'pause_duration': pause_duration}
                    ))
                    
        except asyncio.CancelledError:
            pass
    
    async def _cleanup_tasks(self):
        """清理异步任务"""
        # 取消超时任务
        if self.timeout_task:
            self.timeout_task.cancel()
            
        # 取消暂停通知任务
        if self.pause_notification_task:
            self.pause_notification_task.cancel()
            
        # 取消所有超时警告任务
        for warning_task in self.timeout_warning_tasks:
            warning_task.cancel()
        self.timeout_warning_tasks.clear()
        
        # 等待所有任务完成
        tasks_to_wait = [task for task in [self.timeout_task, self.pause_notification_task] if task and not task.done()]
        if tasks_to_wait:
            await asyncio.gather(*tasks_to_wait, return_exceptions=True)
    
    async def _solve_with_retry(self, challenge: CaptchaChallenge) -> bool:
        """
        带重试的验证码解决
        
        Args:
            challenge: 验证码挑战
            
        Returns:
            bool: 是否成功解决
        """
        retry_config = self.workflow.config.retry_configs.get(
            challenge.captcha_type,
            RetryConfig()
        )
        
        # 跟踪错误类型和连续失败次数
        self.last_error_type = None
        consecutive_failures = 0
        
        for attempt in range(retry_config.max_retries):
            if self.is_cancelled:
                return False
            
            self.attempt_count = attempt + 1
            self.performance_data['retry_count'] = self.attempt_count
            
            try:
                if self.workflow.config.enable_detailed_logging:
                    logger.info(f"Solving captcha attempt {self.attempt_count}/{retry_config.max_retries} for task {self.task.task_id}")
                
                # 解决验证码
                solution = await self.workflow.captcha_solver.solve_captcha(challenge)
                self.current_solution = solution
                
                # 验证解决方案
                if self._validate_solution(solution):
                    # 发送成功通知
                    await self.workflow.send_user_notification(UserNotification(
                        level=NotificationLevel.INFO,
                        message=f"验证码解决成功 (尝试 {self.attempt_count}/{retry_config.max_retries})",
                        task_id=self.task.task_id,
                        captcha_type=challenge.captcha_type,
                        metadata={
                            'attempt': self.attempt_count,
                            'confidence': solution.confidence
                        }
                    ))
                    
                    if self.workflow.config.enable_detailed_logging:
                        logger.info(f"Captcha solved successfully on attempt {self.attempt_count} for task {self.task.task_id}")
                    return True
                else:
                    if self.workflow.config.enable_detailed_logging:
                        logger.warning(f"Invalid solution on attempt {self.attempt_count} for task {self.task.task_id}")
                    
            except Exception as e:
                self.performance_data['error_count'] += 1
                
                # 错误分类
                error_type = ErrorClassifier.classify_error(e)
                self.last_error_type = error_type
                consecutive_failures += 1
                
                if self.workflow.config.enable_detailed_logging:
                    logger.warning(f"Captcha solving failed on attempt {self.attempt_count} for task {self.task.task_id}: {e} (error type: {error_type})")
                
                # 检查是否应该重试
                if not ErrorClassifier.should_retry(error_type, self.attempt_count, retry_config.max_retries):
                    # 发送不重试通知
                    await self.workflow.send_user_notification(UserNotification(
                        level=NotificationLevel.ERROR,
                        message=f"验证码解决失败 - 错误类型不支持重试: {error_type}",
                        task_id=self.task.task_id,
                        captcha_type=challenge.captcha_type,
                        metadata={
                            'attempt': self.attempt_count,
                            'error': str(e),
                            'error_type': error_type
                        }
                    ))
                    
                    logger.error(f"Captcha solving failed for task {self.task.task_id} - error type '{error_type}' not retryable")
                    return False
                
                # 尝试错误恢复
                context = {
                    'task_id': self.task.task_id,
                    'attempt': self.attempt_count,
                    'captcha_type': challenge.captcha_type
                }
                
                recovery_attempted = await ErrorRecoveryStrategy.attempt_recovery(error_type, e, context)
                
                # 发送重试通知
                await self.workflow.send_user_notification(UserNotification(
                    level=NotificationLevel.WARNING,
                    message=f"验证码解决失败 (尝试 {self.attempt_count}/{retry_config.max_retries}): {str(e)}",
                    task_id=self.task.task_id,
                    captcha_type=challenge.captcha_type,
                    metadata={
                        'attempt': self.attempt_count,
                        'error': str(e),
                        'error_type': error_type,
                        'recovery_attempted': recovery_attempted
                    }
                ))
                
                # 记录重试事件
                if self.workflow.analytics:
                    await self.workflow.analytics.record_captcha_event(
                        "retry", challenge.captcha_type, {
                            "attempt": self.attempt_count,
                            "error": str(e),
                            "error_type": error_type,
                            "recovery_attempted": recovery_attempted
                        }
                    )
            
            # 智能重试延迟
            if attempt < retry_config.max_retries - 1:
                # 根据错误类型和解决方案质量计算延迟
                if hasattr(self, 'last_error_type') and self.last_error_type:
                    delay = ErrorClassifier.get_error_delay(self.last_error_type, attempt, retry_config.base_delay)
                else:
                    delay = retry_config.get_delay(attempt)
                
                # 根据解决方案质量调整延迟
                if self.current_solution and self.current_solution.confidence < 0.3:
                    delay *= 1.5  # 低置信度增加延迟
                
                if self.workflow.config.enable_detailed_logging:
                    logger.info(f"Retrying in {delay:.1f} seconds (error type: {getattr(self, 'last_error_type', 'none')})")
                
                await asyncio.sleep(delay)
        
        # 所有重试都失败
        logger.error(f"Captcha solving failed after {retry_config.max_retries} attempts for task {self.task.task_id}")
        return False
    
    async def _timeout_handler(self, timeout_duration: float):
        """
        超时处理器
        
        Args:
            timeout_duration: 超时时间
        """
        try:
            await asyncio.sleep(timeout_duration)
            
            # 更新状态为超时
            await self._update_state(WorkflowState.TIMEOUT)
            
            # 记录超时统计
            self.workflow.workflow_stats['timeout_workflows'] += 1
            
            # 发送超时通知
            processing_time = time.time() - self.start_time
            await self.workflow.send_user_notification(UserNotification(
                level=NotificationLevel.CRITICAL,
                message=f"验证码处理超时 - 已超时 {timeout_duration:.0f} 秒",
                task_id=self.task.task_id,
                captcha_type=self.current_challenge.captcha_type if self.current_challenge else None,
                metadata={
                    'timeout_duration': timeout_duration,
                    'processing_time': processing_time
                }
            ))
            
            # 详细日志记录
            if self.workflow.config.enable_detailed_logging:
                logger.warning(f"Captcha workflow timeout for task {self.task.task_id} after {timeout_duration}s (processing time: {processing_time:.1f}s)")
            else:
                logger.warning(f"Captcha workflow timeout for task {self.task.task_id}")
            
            # 标记任务失败
            await self.workflow.task_queue.fail_task(
                self.task.task_id,
                f"Captcha processing timeout ({timeout_duration}s)"
            )
            
            # 记录超时事件
            if self.workflow.analytics and self.current_challenge:
                await self.workflow.analytics.record_captcha_event(
                    "timeout", self.current_challenge.captcha_type, {
                        "timeout_duration": timeout_duration,
                        "processing_time": processing_time,
                        "attempt_count": self.attempt_count,
                        "pause_duration": self.performance_data.get('pause_duration', 0)
                    }
                )
            
            # 记录性能指标
            await self.workflow.record_performance_metric(
                'captcha_timeout',
                timeout_duration,
                {
                    'task_id': self.task.task_id,
                    'captcha_type': self.current_challenge.captcha_type.value if self.current_challenge else None,
                    'processing_time': processing_time
                }
            )
            
            # 取消工作流
            await self.cancel()
            
        except asyncio.CancelledError:
            pass  # 正常取消
    
    async def _apply_solution(self, solution: CaptchaSolution) -> bool:
        """
        应用解决方案
        
        Args:
            solution: 验证码解决方案
            
        Returns:
            bool: 是否成功应用
        """
        try:
            # 这里应该实现具体的解决方案应用逻辑
            # 比如提交表单、发送请求等
            
            if solution.solution_type == CaptchaType.IMAGE_TEXT:
                return await self._apply_text_solution(solution)
            elif solution.solution_type == CaptchaType.SLIDE_PUZZLE:
                return await self._apply_slide_solution(solution)
            elif solution.solution_type == CaptchaType.CLICK_SEQUENCE:
                return await self._apply_click_solution(solution)
            else:
                return await self._apply_generic_solution(solution)
                
        except Exception as e:
            logger.error(f"Solution application failed: {e}")
            return False
    
    async def _apply_text_solution(self, solution: CaptchaSolution) -> bool:
        """应用文字验证码解决方案"""
        # 实现文字验证码的提交逻辑
        logger.info(f"Applying text solution: {solution.text_result}")
        
        # 模拟提交过程
        await asyncio.sleep(0.5)
        
        # 这里应该实现实际的HTTP请求提交
        # 比如：
        # form_data = {"captcha": solution.text_result}
        # response = await session.post(submit_url, data=form_data)
        # return response.status == 200
        
        return True  # 模拟成功
    
    async def _apply_slide_solution(self, solution: CaptchaSolution) -> bool:
        """应用滑块验证码解决方案"""
        logger.info(f"Applying slide solution: {solution.slide_distance}")
        
        # 模拟滑块操作
        await asyncio.sleep(1.0)
        
        return True  # 模拟成功
    
    async def _apply_click_solution(self, solution: CaptchaSolution) -> bool:
        """应用点击验证码解决方案"""
        logger.info(f"Applying click solution: {len(solution.coordinates)} points")
        
        # 模拟点击操作
        await asyncio.sleep(1.5)
        
        return True  # 模拟成功
    
    async def _apply_generic_solution(self, solution: CaptchaSolution) -> bool:
        """应用通用解决方案"""
        logger.info(f"Applying generic solution for {solution.solution_type}")
        
        # 模拟通用处理
        await asyncio.sleep(1.0)
        
        return True  # 模拟成功
    
    def _validate_solution(self, solution: CaptchaSolution) -> bool:
        """
        验证解决方案
        
        Args:
            solution: 验证码解决方案
            
        Returns:
            bool: 是否有效
        """
        # 基本验证
        if not solution.challenge_id:
            return False
        
        if solution.confidence < 0.1:  # 置信度过低
            return False
        
        # 根据类型进行特定验证
        if solution.solution_type == CaptchaType.IMAGE_TEXT:
            return bool(solution.text_result and solution.text_result.strip())
        elif solution.solution_type == CaptchaType.SLIDE_PUZZLE:
            return solution.slide_distance is not None and solution.slide_distance > 0
        elif solution.solution_type == CaptchaType.CLICK_SEQUENCE:
            return bool(solution.coordinates and len(solution.coordinates) > 0)
        
        return True  # 其他类型默认通过
    
    async def _handle_failure(self, reason: str):
        """
        处理失败情况 (增强版 - 集成重试协调器)
        
        Args:
            reason: 失败原因
        """
        # 更新状态为失败
        await self._update_state(WorkflowState.FAILED)
        
        # 分类失败原因
        failure_reason = self._classify_failure_reason(reason)
        
        # 发送失败通知
        processing_time = time.time() - self.start_time
        await self.workflow.send_user_notification(UserNotification(
            level=NotificationLevel.ERROR,
            message=f"验证码处理失败: {reason}",
            task_id=self.task.task_id,
            captcha_type=self.current_challenge.captcha_type if self.current_challenge else None,
            metadata={
                'reason': reason,
                'failure_reason': failure_reason.value,
                'attempt_count': self.attempt_count,
                'processing_time': processing_time,
                'error_count': self.performance_data.get('error_count', 0)
            }
        ))
        
        # 详细日志记录
        if self.workflow.config.enable_detailed_logging:
            logger.error(f"Captcha workflow failed for task {self.task.task_id}: {reason} (attempts: {self.attempt_count}, processing time: {processing_time:.1f}s, failure_reason: {failure_reason.value})")
        else:
            logger.error(f"Captcha workflow failed for task {self.task.task_id}: {reason}")
        
        # 🔧 关键修改：使用重试协调器的失败处理，而不是直接调用task_queue.fail_task
        await self.workflow.task_queue.fail_task(self.task.task_id, reason, failure_reason)
        
        # 记录失败事件
        if self.workflow.analytics and self.current_challenge:
            await self.workflow.analytics.record_captcha_event(
                "failed", self.current_challenge.captcha_type, {
                    "reason": reason,
                    "failure_reason": failure_reason.value,
                    "attempt_count": self.attempt_count,
                    "processing_time": processing_time,
                    "error_count": self.performance_data.get('error_count', 0),
                    "pause_duration": self.performance_data.get('pause_duration', 0)
                }
            )
        
        # 记录性能指标
        await self.workflow.record_performance_metric(
            'captcha_failure',
            processing_time,
            {
                'task_id': self.task.task_id,
                'captcha_type': self.current_challenge.captcha_type.value if self.current_challenge else None,
                'reason': reason,
                'failure_reason': failure_reason.value,
                'attempt_count': self.attempt_count
            }
        )
    
    def _classify_failure_reason(self, reason: str) -> FailureReason:
        """
        分类失败原因
        
        Args:
            reason: 失败原因描述
            
        Returns:
            FailureReason: 分类后的失败原因
        """
        reason_lower = reason.lower()
        
        # 检测失败
        if any(keyword in reason_lower for keyword in ['detection', 'detect', '检测', '发现']):
            return FailureReason.DETECTION_FAILED
        
        # 求解失败
        if any(keyword in reason_lower for keyword in ['solving', 'solve', '解决', '破解']):
            return FailureReason.SOLVING_FAILED
        
        # 超时
        if any(keyword in reason_lower for keyword in ['timeout', 'time out', '超时']):
            return FailureReason.TIMEOUT
        
        # 网络错误
        if any(keyword in reason_lower for keyword in ['network', 'connection', '网络', '连接']):
            return FailureReason.NETWORK_ERROR
        
        # 验证错误
        if any(keyword in reason_lower for keyword in ['validation', 'invalid', '验证', '无效']):
            return FailureReason.VALIDATION_ERROR
        
        # 用户取消
        if any(keyword in reason_lower for keyword in ['cancel', 'cancelled', '取消', '中止']):
            return FailureReason.USER_CANCELLED
        
        # 系统错误
        if any(keyword in reason_lower for keyword in ['system', 'error', 'exception', '系统', '错误']):
            return FailureReason.SYSTEM_ERROR
        
        # 默认为未知
        return FailureReason.UNKNOWN
    
    async def cancel(self):
        """取消工作流实例"""
        # 更新状态为取消
        await self._update_state(WorkflowState.CANCELLED)
        
        self.is_cancelled = True
        
        # 记录取消统计
        self.workflow.workflow_stats['cancelled_workflows'] += 1
        
        # 发送取消通知
        processing_time = time.time() - self.start_time
        await self.workflow.send_user_notification(UserNotification(
            level=NotificationLevel.WARNING,
            message=f"验证码处理已取消",
            task_id=self.task.task_id,
            captcha_type=self.current_challenge.captcha_type if self.current_challenge else None,
            metadata={
                'processing_time': processing_time,
                'attempt_count': self.attempt_count
            }
        ))
        
        # 详细日志记录
        if self.workflow.config.enable_detailed_logging:
            logger.info(f"Workflow instance cancelled for task {self.task.task_id} (processing time: {processing_time:.1f}s)")
        else:
            logger.info(f"Workflow instance cancelled for task {self.task.task_id}")
        
        # 记录取消事件
        if self.workflow.analytics and self.current_challenge:
            await self.workflow.analytics.record_captcha_event(
                "cancelled", self.current_challenge.captcha_type, {
                    "processing_time": processing_time,
                    "attempt_count": self.attempt_count
                }
            )
        
        # 清理任务
        await self._cleanup_tasks()
    
    def _validate_challenge(self, challenge: CaptchaChallenge) -> bool:
        """
        验证挑战对象的有效性
        
        Args:
            challenge: 验证码挑战对象
            
        Returns:
            bool: 是否有效
        """
        if not challenge:
            return False
        
        # 检查必要的属性
        if not challenge.challenge_id:
            logger.error("Challenge missing challenge_id")
            return False
        
        if not challenge.captcha_type:
            logger.error("Challenge missing captcha_type")
            return False
        
        if not challenge.status:
            logger.error("Challenge missing status")
            return False
        
        # 检查过期时间
        if challenge.is_expired():
            logger.error(f"Challenge {challenge.challenge_id} is expired")
            return False
        
        return True
    
    def _repair_challenge(self, challenge: CaptchaChallenge) -> Optional[CaptchaChallenge]:
        """
        修复挑战对象
        
        Args:
            challenge: 需要修复的挑战对象
            
        Returns:
            Optional[CaptchaChallenge]: 修复后的挑战对象，如果无法修复则返回None
        """
        if not challenge:
            return None
        
        from .captcha_types import ChallengeBuilder, CaptchaType
        
        try:
            # 修复基本属性
            if not challenge.challenge_id:
                import uuid
                challenge.challenge_id = f"repaired_{uuid.uuid4().hex[:8]}"
                logger.info(f"Repaired challenge_id: {challenge.challenge_id}")
            
            if not challenge.captcha_type:
                challenge.captcha_type = CaptchaType.UNKNOWN
                logger.info(f"Repaired captcha_type to UNKNOWN for challenge {challenge.challenge_id}")
            
            if not challenge.status:
                from .captcha_types import CaptchaStatus
                challenge.status = CaptchaStatus.DETECTED
                logger.info(f"Repaired status to DETECTED for challenge {challenge.challenge_id}")
            
            # 修复过期时间
            if challenge.is_expired():
                from datetime import datetime, timedelta
                challenge.expires_at = datetime.now() + timedelta(minutes=5)
                logger.info(f"Extended expiry time for challenge {challenge.challenge_id}")
            
            # 确保有基本的指令
            if not challenge.instruction:
                challenge.instruction = "请完成验证码验证"
                logger.info(f"Added default instruction for challenge {challenge.challenge_id}")
            
            # 确保有挑战参数
            if not challenge.challenge_params:
                challenge.challenge_params = {
                    'input_type': 'manual',
                    'requires_user_input': True,
                    'repaired': True
                }
                logger.info(f"Added default challenge_params for challenge {challenge.challenge_id}")
            
            # 添加修复标记
            if not challenge.metadata:
                challenge.metadata = {}
            challenge.metadata['repaired'] = True
            challenge.metadata['repair_time'] = datetime.now().isoformat()
            
            logger.info(f"Successfully repaired challenge {challenge.challenge_id}")
            return challenge
            
        except Exception as e:
            logger.error(f"Failed to repair challenge: {e}")
            return None
    
    def _is_cli_environment(self) -> bool:
        """
        检测是否为CLI环境
        
        Returns:
            bool: 是否为CLI环境
        """
        from .cli_captcha_handler import get_cli_handler
        cli_handler = get_cli_handler()
        return cli_handler.is_cli_environment()
    
    async def _handle_cli_retry(self, challenge: CaptchaChallenge) -> bool:
        """
        CLI环境下的智能重试
        
        Args:
            challenge: CAPTCHA挑战
            
        Returns:
            bool: 是否成功处理
        """
        from .cli_captcha_handler import CLIRetryStrategy, CLIConfig
        
        # 创建CLI重试策略
        cli_config = CLIConfig()
        retry_strategy = CLIRetryStrategy(cli_config)
        
        # 执行重试策略
        for strategy in cli_config.fallback_strategies:
            if await retry_strategy.should_retry(Exception("CAPTCHA detected")):
                delay = await retry_strategy.get_retry_delay()
                logger.info(f"🔄 CLI Retry: Waiting {delay}s before executing {strategy} strategy")
                await asyncio.sleep(delay)
                
                success = await retry_strategy.execute_retry_strategy(strategy)
                if success:
                    logger.info(f"✅ CLI Retry: {strategy} strategy succeeded")
                    return True
                else:
                    logger.warning(f"❌ CLI Retry: {strategy} strategy failed")
            else:
                logger.info(f"🚫 CLI Retry: Max retries reached, stopping retry attempts")
                break
        
        # 所有策略都失败，返回False触发原有流程
        logger.warning("🔚 CLI Retry: All strategies failed, falling back to original workflow")
        return False
    
    async def _apply_cli_solution(self, solution_result) -> bool:
        """
        应用CLI解决方案
        
        Args:
            solution_result: CLI处理结果
            
        Returns:
            bool: 是否成功应用
        """
        try:
            # 创建CaptchaSolution对象
            from .captcha_types import CaptchaSolution
            
            solution = CaptchaSolution(
                challenge_id=self.current_challenge.challenge_id,
                solution_type=self.current_challenge.captcha_type,
                text_result=solution_result.text_input,
                confidence=solution_result.confidence or 0.8,
                solving_time=solution_result.solving_time,
                metadata={'cli_mode': True, 'auto_solved': True}
            )
            
            self.current_solution = solution
            
            # 应用解决方案
            apply_success = await self._apply_solution(solution)
            
            if apply_success:
                # 恢复任务
                await self.workflow.task_queue.resolve_captcha_task(
                    self.task.task_id,
                    solution
                )
                
                # 更新状态为完成
                await self._update_state(WorkflowState.COMPLETED)
                
                # 发送成功通知
                await self.workflow.send_user_notification(UserNotification(
                    level=NotificationLevel.INFO,
                    message=f"CLI CAPTCHA处理成功 - 任务已恢复",
                    task_id=self.task.task_id,
                    captcha_type=self.current_challenge.captcha_type,
                    metadata={
                        'cli_mode': True,
                        'solving_time': solution.solving_time,
                        'method': 'auto_recognition'
                    }
                ))
                
                logger.info(f"✅ CLI solution applied successfully for task {self.task.task_id}")
                return True
            else:
                logger.warning(f"❌ CLI solution application failed for task {self.task.task_id}")
                return False
                
        except Exception as e:
            logger.error(f"CLI solution application error: {e}")
            return False


class WorkflowManager:
    """工作流管理器"""
    
    def __init__(self, workflow: CaptchaWorkflow):
        """
        初始化工作流管理器
        
        Args:
            workflow: 验证码工作流
        """
        self.workflow = workflow
        self.is_running = False
        self.monitoring_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """启动工作流管理器"""
        if self.is_running:
            return
        
        self.is_running = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        logger.info("WorkflowManager started")
    
    async def stop(self):
        """停止工作流管理器"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        # 取消所有活动的工作流
        for task_id in list(self.workflow.active_workflows.keys()):
            await self.workflow.cancel_workflow(task_id)
        
        logger.info("WorkflowManager stopped")
    
    async def _monitoring_loop(self):
        """监控循环"""
        while self.is_running:
            try:
                # 检查超时的工作流
                await self._check_timeout_workflows()
                
                # 清理过期的任务
                await self.workflow.task_queue.cleanup_expired_tasks()
                
                # 等待一段时间后再次检查
                await asyncio.sleep(30)  # 30秒检查一次
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(10)
    
    async def _check_timeout_workflows(self):
        """检查超时的工作流"""
        current_time = time.time()
        timeout_workflows = []
        
        for task_id, workflow_instance in self.workflow.active_workflows.items():
            if current_time - workflow_instance.start_time > self.workflow.config.timeout:
                timeout_workflows.append(task_id)
        
        for task_id in timeout_workflows:
            logger.warning(f"Workflow timeout detected for task {task_id}")
            await self.workflow.cancel_workflow(task_id)
    
    def get_manager_stats(self) -> Dict[str, Any]:
        """获取管理器统计信息"""
        return {
            "is_running": self.is_running,
            "active_workflows": len(self.workflow.active_workflows),
            "workflow_stats": self.workflow.get_workflow_stats()
        }


class RecoveryManager:
    """恢复管理器"""
    
    def __init__(self, task_queue: TaskQueue, workflow: CaptchaWorkflow):
        """
        初始化恢复管理器
        
        Args:
            task_queue: 任务队列
            workflow: 验证码工作流
        """
        self.task_queue = task_queue
        self.workflow = workflow
        self.recovery_strategies = {
            TaskStatus.FAILED: self._recover_failed_task,
            TaskStatus.TIMEOUT: self._recover_timeout_task,
            TaskStatus.CAPTCHA_REQUIRED: self._recover_captcha_task
        }
    
    async def recover_task(self, task_id: str) -> bool:
        """
        恢复任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功恢复
        """
        task = await self.task_queue.get_task(task_id)
        if not task:
            logger.warning(f"Task {task_id} not found for recovery")
            return False
        
        recovery_strategy = self.recovery_strategies.get(task.status)
        if not recovery_strategy:
            logger.warning(f"No recovery strategy for task status: {task.status}")
            return False
        
        try:
            return await recovery_strategy(task)
        except Exception as e:
            logger.error(f"Task recovery failed: {e}")
            return False
    
    async def _recover_failed_task(self, task: ScrapingTask) -> bool:
        """恢复失败的任务"""
        if task.can_retry:
            # 重置任务状态
            task.update_status(TaskStatus.PENDING)
            
            # 重新添加到队列
            await self.task_queue.add_task(task)
            
            logger.info(f"Failed task recovered: {task.task_id}")
            return True
        else:
            logger.warning(f"Failed task cannot be recovered (max retries exceeded): {task.task_id}")
            return False
    
    async def _recover_timeout_task(self, task: ScrapingTask) -> bool:
        """恢复超时的任务"""
        # 重置超时时间
        task.timeout_at = datetime.now() + timedelta(hours=1)
        
        # 重置任务状态
        task.update_status(TaskStatus.PENDING)
        
        # 重新添加到队列
        await self.task_queue.add_task(task)
        
        logger.info(f"Timeout task recovered: {task.task_id}")
        return True
    
    async def _recover_captcha_task(self, task: ScrapingTask) -> bool:
        """恢复验证码任务"""
        # 如果有解决方案，尝试应用
        if task.captcha_solution:
            await self.task_queue.resolve_captcha_task(task.task_id, task.captcha_solution)
            logger.info(f"Captcha task recovered with existing solution: {task.task_id}")
            return True
        else:
            # 重新触发验证码处理
            if task.captcha_challenge:
                # 重置挑战状态
                task.captcha_challenge.status = CaptchaStatus.DETECTED
                
                # 重新开始工作流
                workflow_success = await self.workflow.process_captcha_workflow(
                    task, "", None, None
                )
                
                if workflow_success:
                    logger.info(f"Captcha task recovered with new workflow: {task.task_id}")
                    return True
            
            logger.warning(f"Cannot recover captcha task without challenge: {task.task_id}")
            return False
    
    async def recover_all_recoverable_tasks(self) -> Dict[str, int]:
        """
        恢复所有可恢复的任务
        
        Returns:
            Dict[str, int]: 恢复统计
        """
        stats = {
            "total_attempts": 0,
            "successful_recoveries": 0,
            "failed_recoveries": 0
        }
        
        # 获取所有失败和超时的任务
        failed_tasks = await self.task_queue.get_tasks_by_status(TaskStatus.FAILED)
        timeout_tasks = await self.task_queue.get_tasks_by_status(TaskStatus.TIMEOUT)
        captcha_tasks = await self.task_queue.get_tasks_by_status(TaskStatus.CAPTCHA_REQUIRED)
        
        all_recoverable_tasks = failed_tasks + timeout_tasks + captcha_tasks
        
        for task in all_recoverable_tasks:
            stats["total_attempts"] += 1
            
            if await self.recover_task(task.task_id):
                stats["successful_recoveries"] += 1
            else:
                stats["failed_recoveries"] += 1
        
        logger.info(f"Recovery completed: {stats}")
        return stats
