"""
统一重试协调器模块

该模块提供集中化的重试决策和任务管理功能，解决多层重试冲突问题：
- 统一重试决策逻辑
- 智能重试策略（基于CAPTCHA类型、失败原因、历史成功率）
- 任务生命周期管理
- 重试历史记录和分析
- 断路器模式防止无效重试
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json
import random
from collections import defaultdict, deque

from .captcha_types import CaptchaType
from .error_handler import ErrorCategory, ErrorSeverity
from ..utils.logger import get_logger

logger = get_logger(__name__)


class RetryDecision(Enum):
    """重试决策枚举"""
    RETRY = "retry"
    ABORT = "abort"
    ESCALATE = "escalate"
    PAUSE = "pause"


class FailureReason(Enum):
    """失败原因枚举"""
    DETECTION_FAILED = "detection_failed"
    SOLVING_FAILED = "solving_failed"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    VALIDATION_ERROR = "validation_error"
    USER_CANCELLED = "user_cancelled"
    SYSTEM_ERROR = "system_error"
    UNKNOWN = "unknown"


@dataclass
class RetryAttempt:
    """重试尝试记录"""
    attempt_number: int
    timestamp: datetime
    failure_reason: FailureReason
    captcha_type: Optional[CaptchaType] = None
    error_details: Optional[str] = None
    retry_delay: float = 0.0
    success: bool = False
    duration: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'attempt_number': self.attempt_number,
            'timestamp': self.timestamp.isoformat(),
            'failure_reason': self.failure_reason.value,
            'captcha_type': self.captcha_type.value if self.captcha_type else None,
            'error_details': self.error_details,
            'retry_delay': self.retry_delay,
            'success': self.success,
            'duration': self.duration
        }


@dataclass
class TaskRetryHistory:
    """任务重试历史"""
    task_id: str
    created_at: datetime
    captcha_type: Optional[CaptchaType] = None
    attempts: List[RetryAttempt] = field(default_factory=list)
    total_attempts: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_duration: float = 0.0
    final_success: bool = False
    
    def add_attempt(self, attempt: RetryAttempt):
        """添加重试尝试"""
        self.attempts.append(attempt)
        self.total_attempts += 1
        self.total_duration += attempt.duration
        
        if attempt.success:
            self.success_count += 1
            self.final_success = True
        else:
            self.failure_count += 1
    
    def get_success_rate(self) -> float:
        """获取成功率"""
        if self.total_attempts == 0:
            return 0.0
        return self.success_count / self.total_attempts
    
    def get_average_duration(self) -> float:
        """获取平均持续时间"""
        if self.total_attempts == 0:
            return 0.0
        return self.total_duration / self.total_attempts
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'task_id': self.task_id,
            'created_at': self.created_at.isoformat(),
            'captcha_type': self.captcha_type.value if self.captcha_type else None,
            'attempts': [attempt.to_dict() for attempt in self.attempts],
            'total_attempts': self.total_attempts,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'total_duration': self.total_duration,
            'final_success': self.final_success,
            'success_rate': self.get_success_rate(),
            'average_duration': self.get_average_duration()
        }


@dataclass
class RetryStrategy:
    """重试策略配置"""
    max_attempts: int = 3
    base_delay: float = 2.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter_factor: float = 0.1
    timeout_multiplier: float = 1.5
    
    # 基于失败原因的策略调整
    failure_reason_multipliers: Dict[FailureReason, float] = field(default_factory=lambda: {
        FailureReason.DETECTION_FAILED: 1.0,
        FailureReason.SOLVING_FAILED: 1.5,
        FailureReason.TIMEOUT: 2.0,
        FailureReason.NETWORK_ERROR: 0.8,
        FailureReason.VALIDATION_ERROR: 0.5,
        FailureReason.USER_CANCELLED: 0.0,  # 不重试
        FailureReason.SYSTEM_ERROR: 1.2,
        FailureReason.UNKNOWN: 1.0
    })
    
    def should_retry(self, attempt_count: int, failure_reason: FailureReason) -> bool:
        """判断是否应该重试"""
        if attempt_count >= self.max_attempts:
            return False
        
        multiplier = self.failure_reason_multipliers.get(failure_reason, 1.0)
        if multiplier == 0.0:
            return False
        
        # 某些失败原因的重试次数限制
        if failure_reason == FailureReason.USER_CANCELLED:
            return False
        elif failure_reason == FailureReason.VALIDATION_ERROR and attempt_count >= 1:
            return False
        elif failure_reason == FailureReason.SYSTEM_ERROR and attempt_count >= 2:
            return False
        
        return True
    
    def calculate_delay(self, attempt_count: int, failure_reason: FailureReason) -> float:
        """计算重试延迟"""
        base_delay = self.base_delay
        multiplier = self.failure_reason_multipliers.get(failure_reason, 1.0)
        
        # 指数退避
        delay = min(
            base_delay * (self.exponential_base ** attempt_count) * multiplier,
            self.max_delay
        )
        
        # 添加随机抖动
        if self.jitter_factor > 0:
            jitter = delay * self.jitter_factor * (random.random() - 0.5)
            delay = max(0.1, delay + jitter)
        
        return delay


@dataclass
class CircuitBreakerConfig:
    """断路器配置"""
    failure_threshold: int = 5  # 失败阈值
    recovery_timeout: float = 300.0  # 恢复超时（秒）
    success_threshold: int = 3  # 成功阈值
    min_request_threshold: int = 10  # 最小请求阈值


class CircuitBreakerState(Enum):
    """断路器状态"""
    CLOSED = "closed"  # 正常状态
    OPEN = "open"  # 断路状态
    HALF_OPEN = "half_open"  # 半开状态


class CircuitBreaker:
    """断路器实现"""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.request_count = 0
        
        logger.info(f"Circuit breaker initialized with config: {config}")
    
    def can_execute(self) -> bool:
        """判断是否可以执行"""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            if self.last_failure_time and \
               (datetime.now() - self.last_failure_time).total_seconds() > self.config.recovery_timeout:
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
                logger.info("Circuit breaker changed to HALF_OPEN state")
                return True
            return False
        elif self.state == CircuitBreakerState.HALF_OPEN:
            return True
        
        return False
    
    def record_success(self):
        """记录成功"""
        self.request_count += 1
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                logger.info("Circuit breaker changed to CLOSED state")
    
    def record_failure(self):
        """记录失败"""
        self.request_count += 1
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
            logger.info("Circuit breaker changed to OPEN state")
        elif self.state == CircuitBreakerState.CLOSED:
            if (self.request_count >= self.config.min_request_threshold and
                self.failure_count >= self.config.failure_threshold):
                self.state = CircuitBreakerState.OPEN
                logger.info("Circuit breaker changed to OPEN state")
    
    def get_state(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'request_count': self.request_count,
            'last_failure_time': self.last_failure_time.isoformat() if self.last_failure_time else None
        }


class CentralizedRetryCoordinator:
    """统一重试协调器"""
    
    def __init__(self, max_history_size: int = 1000):
        """
        初始化重试协调器
        
        Args:
            max_history_size: 最大历史记录数量
        """
        self.max_history_size = max_history_size
        
        # 重试策略配置（按CAPTCHA类型）
        self.retry_strategies: Dict[CaptchaType, RetryStrategy] = {
            CaptchaType.IMAGE_TEXT: RetryStrategy(
                max_attempts=3,
                base_delay=2.0,
                max_delay=30.0,
                exponential_base=1.5
            ),
            CaptchaType.SLIDE_PUZZLE: RetryStrategy(
                max_attempts=2,
                base_delay=3.0,
                max_delay=45.0,
                exponential_base=2.0
            ),
            CaptchaType.CLICK_SEQUENCE: RetryStrategy(
                max_attempts=2,
                base_delay=2.5,
                max_delay=40.0,
                exponential_base=1.8
            ),
            CaptchaType.RECAPTCHA_V2: RetryStrategy(
                max_attempts=1,
                base_delay=5.0,
                max_delay=60.0,
                exponential_base=2.0
            ),
            CaptchaType.GEETEST: RetryStrategy(
                max_attempts=2,
                base_delay=3.0,
                max_delay=50.0,
                exponential_base=2.0
            )
        }
        
        # 默认策略
        self.default_strategy = RetryStrategy()
        
        # 断路器（按CAPTCHA类型）
        self.circuit_breakers: Dict[CaptchaType, CircuitBreaker] = {}
        self.circuit_breaker_config = CircuitBreakerConfig()
        
        # 重试历史记录
        self.retry_history: Dict[str, TaskRetryHistory] = {}
        self.global_statistics = {
            'total_tasks': 0,
            'successful_tasks': 0,
            'failed_tasks': 0,
            'total_attempts': 0,
            'average_attempts_per_task': 0.0,
            'success_rate_by_type': defaultdict(float),
            'failure_reasons': defaultdict(int)
        }
        
        # 实时统计窗口（滑动窗口）
        self.recent_results: deque = deque(maxlen=100)
        
        # 任务状态跟踪
        self.active_tasks: Dict[str, datetime] = {}
        
        logger.info("CentralizedRetryCoordinator initialized")
    
    def get_circuit_breaker(self, captcha_type: CaptchaType) -> CircuitBreaker:
        """获取断路器"""
        if captcha_type not in self.circuit_breakers:
            self.circuit_breakers[captcha_type] = CircuitBreaker(self.circuit_breaker_config)
        return self.circuit_breakers[captcha_type]
    
    def should_retry(self, task_id: str, failure_reason: FailureReason,
                    captcha_type: Optional[CaptchaType] = None) -> Tuple[bool, RetryDecision]:
        """
        判断是否应该重试
        
        Args:
            task_id: 任务ID
            failure_reason: 失败原因
            captcha_type: 验证码类型
            
        Returns:
            Tuple[bool, RetryDecision]: (是否重试, 重试决策)
        """
        # 获取任务历史
        history = self.retry_history.get(task_id)
        if not history:
            # 首次尝试，创建历史记录
            history = TaskRetryHistory(
                task_id=task_id,
                created_at=datetime.now(),
                captcha_type=captcha_type
            )
            self.retry_history[task_id] = history
        
        # 检查断路器状态
        if captcha_type:
            circuit_breaker = self.get_circuit_breaker(captcha_type)
            if not circuit_breaker.can_execute():
                logger.warning(f"Circuit breaker OPEN for {captcha_type.value}, aborting task {task_id}")
                return False, RetryDecision.ABORT
        
        # 获取重试策略
        strategy = self.retry_strategies.get(captcha_type, self.default_strategy)
        
        # 检查是否应该重试
        should_retry = strategy.should_retry(history.total_attempts, failure_reason)
        
        if not should_retry:
            if history.total_attempts >= strategy.max_attempts:
                logger.info(f"Task {task_id} reached max attempts ({strategy.max_attempts})")
                return False, RetryDecision.ABORT
            elif failure_reason == FailureReason.USER_CANCELLED:
                logger.info(f"Task {task_id} cancelled by user")
                return False, RetryDecision.ABORT
            else:
                logger.info(f"Task {task_id} should not retry due to failure reason: {failure_reason.value}")
                return False, RetryDecision.ESCALATE
        
        # 检查动态成功率
        if captcha_type:
            success_rate = self._get_recent_success_rate(captcha_type)
            if success_rate < 0.1 and history.total_attempts >= 1:
                logger.warning(f"Low success rate ({success_rate:.2%}) for {captcha_type.value}, pausing task {task_id}")
                return False, RetryDecision.PAUSE
        
        logger.info(f"Task {task_id} should retry (attempt {history.total_attempts + 1})")
        return True, RetryDecision.RETRY
    
    def get_retry_delay(self, task_id: str, failure_reason: FailureReason,
                       captcha_type: Optional[CaptchaType] = None) -> float:
        """
        获取重试延迟
        
        Args:
            task_id: 任务ID
            failure_reason: 失败原因
            captcha_type: 验证码类型
            
        Returns:
            float: 重试延迟（秒）
        """
        history = self.retry_history.get(task_id)
        if not history:
            return self.default_strategy.base_delay
        
        strategy = self.retry_strategies.get(captcha_type, self.default_strategy)
        delay = strategy.calculate_delay(history.total_attempts, failure_reason)
        
        logger.debug(f"Calculated retry delay for task {task_id}: {delay:.2f}s")
        return delay
    
    def record_attempt(self, task_id: str, success: bool, failure_reason: FailureReason,
                      captcha_type: Optional[CaptchaType] = None,
                      duration: float = 0.0, error_details: Optional[str] = None):
        """
        记录重试尝试
        
        Args:
            task_id: 任务ID
            success: 是否成功
            failure_reason: 失败原因
            captcha_type: 验证码类型
            duration: 持续时间
            error_details: 错误详情
        """
        history = self.retry_history.get(task_id)
        if not history:
            history = TaskRetryHistory(
                task_id=task_id,
                created_at=datetime.now(),
                captcha_type=captcha_type
            )
            self.retry_history[task_id] = history
        
        # 创建尝试记录
        attempt = RetryAttempt(
            attempt_number=history.total_attempts + 1,
            timestamp=datetime.now(),
            failure_reason=failure_reason,
            captcha_type=captcha_type,
            error_details=error_details,
            success=success,
            duration=duration
        )
        
        # 添加到历史记录
        history.add_attempt(attempt)
        
        # 更新断路器状态
        if captcha_type:
            circuit_breaker = self.get_circuit_breaker(captcha_type)
            if success:
                circuit_breaker.record_success()
            else:
                circuit_breaker.record_failure()
        
        # 更新全局统计
        self._update_global_statistics(success, failure_reason, captcha_type)
        
        # 添加到实时统计窗口
        self.recent_results.append({
            'timestamp': datetime.now(),
            'success': success,
            'captcha_type': captcha_type.value if captcha_type else None,
            'failure_reason': failure_reason.value,
            'duration': duration
        })
        
        # 管理任务状态
        if success or not self.should_retry(task_id, failure_reason, captcha_type)[0]:
            self.active_tasks.pop(task_id, None)
            if success:
                logger.info(f"Task {task_id} completed successfully after {history.total_attempts} attempts")
            else:
                logger.info(f"Task {task_id} failed after {history.total_attempts} attempts")
        
        # 清理历史记录
        if len(self.retry_history) > self.max_history_size:
            oldest_tasks = sorted(self.retry_history.keys(), 
                                key=lambda x: self.retry_history[x].created_at)
            for old_task in oldest_tasks[:self.max_history_size // 2]:
                del self.retry_history[old_task]
    
    def update_retry_strategy(self, captcha_type: CaptchaType, success_rate: float):
        """
        根据成功率动态调整重试策略
        
        Args:
            captcha_type: 验证码类型
            success_rate: 成功率
        """
        if captcha_type not in self.retry_strategies:
            return
        
        strategy = self.retry_strategies[captcha_type]
        
        # 根据成功率调整策略
        if success_rate < 0.3:
            # 成功率低，增加重试次数，减少延迟
            strategy.max_attempts = min(strategy.max_attempts + 1, 5)
            strategy.base_delay = max(strategy.base_delay * 0.8, 1.0)
        elif success_rate > 0.8:
            # 成功率高，减少重试次数，增加延迟
            strategy.max_attempts = max(strategy.max_attempts - 1, 1)
            strategy.base_delay = min(strategy.base_delay * 1.2, 10.0)
        
        logger.info(f"Updated retry strategy for {captcha_type.value}: "
                   f"max_attempts={strategy.max_attempts}, base_delay={strategy.base_delay:.2f}")
    
    def _get_recent_success_rate(self, captcha_type: CaptchaType) -> float:
        """获取最近的成功率"""
        recent_results = [r for r in self.recent_results 
                         if r['captcha_type'] == captcha_type.value]
        
        if not recent_results:
            return 0.5  # 默认成功率
        
        success_count = sum(1 for r in recent_results if r['success'])
        return success_count / len(recent_results)
    
    def _update_global_statistics(self, success: bool, failure_reason: FailureReason,
                                 captcha_type: Optional[CaptchaType]):
        """更新全局统计"""
        self.global_statistics['total_attempts'] += 1
        
        if success:
            self.global_statistics['successful_tasks'] += 1
        else:
            self.global_statistics['failed_tasks'] += 1
            self.global_statistics['failure_reasons'][failure_reason.value] += 1
        
        if captcha_type:
            total_for_type = self.global_statistics['success_rate_by_type'].get(f"{captcha_type.value}_total", 0)
            success_for_type = self.global_statistics['success_rate_by_type'].get(f"{captcha_type.value}_success", 0)
            
            self.global_statistics['success_rate_by_type'][f"{captcha_type.value}_total"] = total_for_type + 1
            if success:
                self.global_statistics['success_rate_by_type'][f"{captcha_type.value}_success"] = success_for_type + 1
    
    def get_task_history(self, task_id: str) -> Optional[TaskRetryHistory]:
        """获取任务历史记录"""
        return self.retry_history.get(task_id)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        # 计算每种类型的成功率
        success_rates = {}
        for key, value in self.global_statistics['success_rate_by_type'].items():
            if key.endswith('_total') and value > 0:
                captcha_type = key.replace('_total', '')
                success_key = f"{captcha_type}_success"
                success_count = self.global_statistics['success_rate_by_type'].get(success_key, 0)
                success_rates[captcha_type] = success_count / value
        
        # 计算平均尝试次数
        total_tasks = len(self.retry_history)
        if total_tasks > 0:
            total_attempts = sum(history.total_attempts for history in self.retry_history.values())
            avg_attempts = total_attempts / total_tasks
        else:
            avg_attempts = 0.0
        
        return {
            'total_tasks': total_tasks,
            'active_tasks': len(self.active_tasks),
            'successful_tasks': self.global_statistics['successful_tasks'],
            'failed_tasks': self.global_statistics['failed_tasks'],
            'total_attempts': self.global_statistics['total_attempts'],
            'average_attempts_per_task': avg_attempts,
            'success_rates_by_type': success_rates,
            'failure_reasons': dict(self.global_statistics['failure_reasons']),
            'circuit_breaker_states': {
                captcha_type.value: breaker.get_state()
                for captcha_type, breaker in self.circuit_breakers.items()
            },
            'recent_success_rate': self._calculate_recent_success_rate()
        }
    
    def _calculate_recent_success_rate(self) -> float:
        """计算最近的成功率"""
        if not self.recent_results:
            return 0.0
        
        success_count = sum(1 for r in self.recent_results if r['success'])
        return success_count / len(self.recent_results)
    
    def reset_circuit_breaker(self, captcha_type: CaptchaType):
        """重置断路器"""
        if captcha_type in self.circuit_breakers:
            self.circuit_breakers[captcha_type] = CircuitBreaker(self.circuit_breaker_config)
            logger.info(f"Circuit breaker reset for {captcha_type.value}")
    
    def clear_history(self):
        """清空历史记录"""
        self.retry_history.clear()
        self.global_statistics = {
            'total_tasks': 0,
            'successful_tasks': 0,
            'failed_tasks': 0,
            'total_attempts': 0,
            'average_attempts_per_task': 0.0,
            'success_rate_by_type': defaultdict(float),
            'failure_reasons': defaultdict(int)
        }
        self.recent_results.clear()
        self.active_tasks.clear()
        logger.info("Retry coordinator history cleared")


# 全局重试协调器实例
_retry_coordinator = None

def get_retry_coordinator() -> CentralizedRetryCoordinator:
    """获取全局重试协调器实例"""
    global _retry_coordinator
    if _retry_coordinator is None:
        _retry_coordinator = CentralizedRetryCoordinator()
    return _retry_coordinator