"""
CAPTCHA检测错误处理和日志记录模块
用于统一处理CAPTCHA检测过程中的错误和日志记录
"""

import asyncio
import logging
import traceback
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import json

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ErrorSeverity(Enum):
    """错误严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """错误类别"""
    DETECTION_ERROR = "detection_error"
    WORKFLOW_ERROR = "workflow_error"
    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"
    VALIDATION_ERROR = "validation_error"
    CONFIGURATION_ERROR = "configuration_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class ErrorContext:
    """错误上下文"""
    task_id: Optional[str] = None
    url: Optional[str] = None
    detection_method: Optional[str] = None
    captcha_type: Optional[str] = None
    session_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    additional_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ErrorRecord:
    """错误记录"""
    error_id: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    exception: Optional[Exception] = None
    context: Optional[ErrorContext] = None
    traceback_str: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'error_id': self.error_id,
            'category': self.category.value,
            'severity': self.severity.value,
            'message': self.message,
            'exception_type': self.exception.__class__.__name__ if self.exception else None,
            'exception_message': str(self.exception) if self.exception else None,
            'context': self.context.__dict__ if self.context else None,
            'traceback': self.traceback_str,
            'timestamp': self.timestamp.isoformat()
        }


class CaptchaErrorHandler:
    """CAPTCHA错误处理器"""
    
    def __init__(self):
        """初始化错误处理器"""
        self.error_history: List[ErrorRecord] = []
        self.error_stats = {
            'total_errors': 0,
            'errors_by_category': {},
            'errors_by_severity': {},
            'recent_errors': []
        }
        
        # 错误模式识别
        self.error_patterns = {
            'connection_timeout': r'(timeout|connection|network).*error',
            'detection_failure': r'(detection|captcha).*failed',
            'invalid_response': r'(invalid|malformed).*response',
            'configuration_error': r'(config|setting).*error'
        }
        
        logger.info("CaptchaErrorHandler initialized")
    
    async def handle_error(self, 
                         error: Exception,
                         category: ErrorCategory = ErrorCategory.UNKNOWN_ERROR,
                         severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                         context: Optional[ErrorContext] = None,
                         custom_message: Optional[str] = None) -> ErrorRecord:
        """
        处理错误
        
        Args:
            error: 异常对象
            category: 错误类别
            severity: 错误严重程度
            context: 错误上下文
            custom_message: 自定义错误消息
            
        Returns:
            ErrorRecord: 错误记录
        """
        # 生成错误ID
        error_id = f"ERR_{int(datetime.now().timestamp() * 1000)}"
        
        # 自动分类错误
        if category == ErrorCategory.UNKNOWN_ERROR:
            category = self._classify_error(error)
        
        # 自动评估严重程度
        if severity == ErrorSeverity.MEDIUM:
            severity = self._assess_severity(error, category)
        
        # 构建错误消息
        message = custom_message or str(error)
        
        # 获取堆栈跟踪
        traceback_str = traceback.format_exc() if error else None
        
        # 创建错误记录
        error_record = ErrorRecord(
            error_id=error_id,
            category=category,
            severity=severity,
            message=message,
            exception=error,
            context=context,
            traceback_str=traceback_str
        )
        
        # 记录错误
        self._record_error(error_record)
        
        # 记录日志
        self._log_error(error_record)
        
        # 触发错误处理策略
        await self._execute_error_strategy(error_record)
        
        return error_record
    
    def _classify_error(self, error: Exception) -> ErrorCategory:
        """自动分类错误"""
        error_str = str(error).lower()
        
        if any(keyword in error_str for keyword in ['timeout', 'connection', 'network']):
            return ErrorCategory.NETWORK_ERROR
        elif any(keyword in error_str for keyword in ['detection', 'captcha']):
            return ErrorCategory.DETECTION_ERROR
        elif any(keyword in error_str for keyword in ['workflow', 'process']):
            return ErrorCategory.WORKFLOW_ERROR
        elif any(keyword in error_str for keyword in ['validation', 'invalid']):
            return ErrorCategory.VALIDATION_ERROR
        elif any(keyword in error_str for keyword in ['config', 'setting']):
            return ErrorCategory.CONFIGURATION_ERROR
        else:
            return ErrorCategory.UNKNOWN_ERROR
    
    def _assess_severity(self, error: Exception, category: ErrorCategory) -> ErrorSeverity:
        """评估错误严重程度"""
        # 基于错误类型的严重程度映射
        severity_map = {
            ErrorCategory.NETWORK_ERROR: ErrorSeverity.MEDIUM,
            ErrorCategory.DETECTION_ERROR: ErrorSeverity.HIGH,
            ErrorCategory.WORKFLOW_ERROR: ErrorSeverity.HIGH,
            ErrorCategory.TIMEOUT_ERROR: ErrorSeverity.MEDIUM,
            ErrorCategory.VALIDATION_ERROR: ErrorSeverity.LOW,
            ErrorCategory.CONFIGURATION_ERROR: ErrorSeverity.CRITICAL,
            ErrorCategory.UNKNOWN_ERROR: ErrorSeverity.MEDIUM
        }
        
        base_severity = severity_map.get(category, ErrorSeverity.MEDIUM)
        
        # 基于异常类型调整严重程度
        if isinstance(error, (ConnectionError, TimeoutError)):
            return ErrorSeverity.MEDIUM
        elif isinstance(error, (ValueError, TypeError)):
            return ErrorSeverity.HIGH
        elif isinstance(error, (SystemError, MemoryError)):
            return ErrorSeverity.CRITICAL
        
        return base_severity
    
    def _record_error(self, error_record: ErrorRecord):
        """记录错误到历史"""
        self.error_history.append(error_record)
        
        # 限制历史记录大小
        if len(self.error_history) > 1000:
            self.error_history = self.error_history[-500:]
        
        # 更新统计信息
        self.error_stats['total_errors'] += 1
        
        # 按类别统计
        category_key = error_record.category.value
        self.error_stats['errors_by_category'][category_key] = \
            self.error_stats['errors_by_category'].get(category_key, 0) + 1
        
        # 按严重程度统计
        severity_key = error_record.severity.value
        self.error_stats['errors_by_severity'][severity_key] = \
            self.error_stats['errors_by_severity'].get(severity_key, 0) + 1
        
        # 最近错误
        self.error_stats['recent_errors'].append(error_record.to_dict())
        if len(self.error_stats['recent_errors']) > 50:
            self.error_stats['recent_errors'] = self.error_stats['recent_errors'][-25:]
    
    def _log_error(self, error_record: ErrorRecord):
        """记录错误日志"""
        log_data = {
            'error_id': error_record.error_id,
            'category': error_record.category.value,
            'severity': error_record.severity.value,
            'context': error_record.context.__dict__ if error_record.context else None
        }
        
        # 根据严重程度选择日志级别
        if error_record.severity == ErrorSeverity.CRITICAL:
            logger.critical(f"[{error_record.error_id}] {error_record.message}", extra=log_data)
        elif error_record.severity == ErrorSeverity.HIGH:
            logger.error(f"[{error_record.error_id}] {error_record.message}", extra=log_data)
        elif error_record.severity == ErrorSeverity.MEDIUM:
            logger.warning(f"[{error_record.error_id}] {error_record.message}", extra=log_data)
        else:
            logger.info(f"[{error_record.error_id}] {error_record.message}", extra=log_data)
    
    async def _execute_error_strategy(self, error_record: ErrorRecord):
        """执行错误处理策略"""
        try:
            # 根据错误类别执行不同的处理策略
            if error_record.category == ErrorCategory.NETWORK_ERROR:
                await self._handle_network_error(error_record)
            elif error_record.category == ErrorCategory.DETECTION_ERROR:
                await self._handle_detection_error(error_record)
            elif error_record.category == ErrorCategory.WORKFLOW_ERROR:
                await self._handle_workflow_error(error_record)
            elif error_record.severity == ErrorSeverity.CRITICAL:
                await self._handle_critical_error(error_record)
                
        except Exception as e:
            logger.error(f"Error strategy execution failed: {e}")
    
    async def _handle_network_error(self, error_record: ErrorRecord):
        """处理网络错误"""
        logger.info(f"Handling network error: {error_record.error_id}")
        # 可以实现重试逻辑、切换代理等
        pass
    
    async def _handle_detection_error(self, error_record: ErrorRecord):
        """处理检测错误"""
        logger.info(f"Handling detection error: {error_record.error_id}")
        # 可以实现降级检测、切换检测方法等
        pass
    
    async def _handle_workflow_error(self, error_record: ErrorRecord):
        """处理工作流错误"""
        logger.info(f"Handling workflow error: {error_record.error_id}")
        # 可以实现工作流重置、状态恢复等
        pass
    
    async def _handle_critical_error(self, error_record: ErrorRecord):
        """处理关键错误"""
        logger.critical(f"Handling critical error: {error_record.error_id}")
        # 可以实现紧急停止、通知管理员等
        pass
    
    def get_error_stats(self) -> Dict[str, Any]:
        """获取错误统计信息"""
        return {
            **self.error_stats,
            'error_rate': self._calculate_error_rate(),
            'top_error_categories': self._get_top_error_categories(),
            'recent_error_trend': self._analyze_recent_error_trend()
        }
    
    def _calculate_error_rate(self) -> float:
        """计算错误率"""
        if not self.error_history:
            return 0.0
        
        # 计算最近一小时的错误率
        recent_errors = [
            error for error in self.error_history
            if (datetime.now() - error.timestamp).total_seconds() < 3600
        ]
        
        return len(recent_errors) / max(len(self.error_history), 1) * 100
    
    def _get_top_error_categories(self) -> List[Dict[str, Any]]:
        """获取主要错误类别"""
        return [
            {'category': category, 'count': count}
            for category, count in sorted(
                self.error_stats['errors_by_category'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
        ]
    
    def _analyze_recent_error_trend(self) -> Dict[str, Any]:
        """分析最近错误趋势"""
        recent_errors = self.error_stats['recent_errors'][-10:]
        
        if not recent_errors:
            return {'trend': 'stable', 'frequency': 0}
        
        # 简单的趋势分析
        timestamps = [
            datetime.fromisoformat(error['timestamp'])
            for error in recent_errors
        ]
        
        if len(timestamps) > 1:
            time_diffs = [
                (timestamps[i] - timestamps[i-1]).total_seconds()
                for i in range(1, len(timestamps))
            ]
            avg_interval = sum(time_diffs) / len(time_diffs)
            
            if avg_interval < 60:  # 错误间隔小于1分钟
                trend = 'increasing'
            elif avg_interval > 300:  # 错误间隔大于5分钟
                trend = 'decreasing'
            else:
                trend = 'stable'
        else:
            trend = 'stable'
        
        return {
            'trend': trend,
            'frequency': len(recent_errors),
            'avg_interval': avg_interval if len(timestamps) > 1 else 0
        }
    
    def clear_error_history(self):
        """清空错误历史"""
        self.error_history.clear()
        self.error_stats = {
            'total_errors': 0,
            'errors_by_category': {},
            'errors_by_severity': {},
            'recent_errors': []
        }
        logger.info("Error history cleared")


# 全局错误处理器实例
_error_handler = None

def get_error_handler() -> CaptchaErrorHandler:
    """获取错误处理器实例"""
    global _error_handler
    if _error_handler is None:
        _error_handler = CaptchaErrorHandler()
    return _error_handler


async def handle_captcha_error(error: Exception, 
                             context: Optional[ErrorContext] = None,
                             custom_message: Optional[str] = None) -> ErrorRecord:
    """便捷的错误处理函数"""
    error_handler = get_error_handler()
    return await error_handler.handle_error(
        error=error,
        context=context,
        custom_message=custom_message
    )