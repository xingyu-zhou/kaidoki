"""
超时管理工具模块

提供异步操作的超时控制、死锁预防和任务管理功能。
简化版本，专注于核心功能和可靠性。

Author: Kaidoki Team
"""

import asyncio
import functools
import time
import logging
from typing import Any, Callable, Optional, TypeVar, Union, Dict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..exceptions import (
    ServiceUnavailableError,
    ValidationError
)

# 配置日志
logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class TaskInfo:
    """任务信息"""
    task: asyncio.Task
    name: str
    start_time: datetime
    timeout_seconds: float
    
    @property
    def elapsed_time(self) -> float:
        """已耗时（秒）"""
        return (datetime.now() - self.start_time).total_seconds()
    
    @property
    def remaining_time(self) -> float:
        """剩余时间（秒）"""
        return max(0, self.timeout_seconds - self.elapsed_time)
    
    @property
    def is_timeout(self) -> bool:
        """是否超时"""
        return self.elapsed_time >= self.timeout_seconds
    
    @property
    def is_done(self) -> bool:
        """任务是否完成"""
        return self.task.done()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "start_time": self.start_time.isoformat(),
            "timeout_seconds": self.timeout_seconds,
            "elapsed_time": self.elapsed_time,
            "remaining_time": self.remaining_time,
            "is_timeout": self.is_timeout,
            "is_done": self.is_done
        }


class TimeoutManager:
    """
    超时管理器
    
    提供异步操作的超时控制和任务管理功能。
    """
    
    def __init__(self, default_timeout: float = 30.0):
        """
        初始化超时管理器
        
        Args:
            default_timeout: 默认超时时间（秒）
        """
        if default_timeout <= 0:
            raise ValidationError(
                "默认超时时间必须大于0",
                field="default_timeout",
                value=default_timeout
            )
        
        self.default_timeout = default_timeout
        self.active_tasks: Dict[str, TaskInfo] = {}
        self._cleanup_interval = 60.0  # 清理间隔（秒）
        self._last_cleanup = datetime.now()
        
        logger.info(f"TimeoutManager initialized with default timeout: {default_timeout}s")
    
    async def execute_with_timeout(
        self,
        coro_or_func: Union[Callable, Any],
        timeout: Optional[float] = None,
        task_name: Optional[str] = None
    ) -> Any:
        """
        执行异步操作并应用超时控制
        
        Args:
            coro_or_func: 协程或可调用对象
            timeout: 超时时间（秒），None 使用默认值
            task_name: 任务名称，用于日志和监控
            
        Returns:
            操作结果
            
        Raises:
            asyncio.TimeoutError: 超时异常
            ServiceUnavailableError: 服务不可用异常
        """
        timeout = timeout or self.default_timeout
        task_name = task_name or self._generate_task_name(coro_or_func)
        start_time = datetime.now()
        
        # 定期清理已完成的任务
        await self._cleanup_if_needed()
        
        logger.debug(f"开始执行任务 '{task_name}' (超时: {timeout}s)")
        
        try:
            # 准备任务
            if asyncio.iscoroutine(coro_or_func):
                task = asyncio.create_task(coro_or_func)
            elif asyncio.iscoroutinefunction(coro_or_func):
                task = asyncio.create_task(coro_or_func())
            else:
                # 同步函数在线程池中执行
                loop = asyncio.get_event_loop()
                task = loop.run_in_executor(None, coro_or_func)
                task = asyncio.create_task(task)
            
            # 注册任务
            task_info = TaskInfo(
                task=task,
                name=task_name,
                start_time=start_time,
                timeout_seconds=timeout
            )
            self.active_tasks[task_name] = task_info
            
            # 等待任务完成或超时
            try:
                result = await asyncio.wait_for(task, timeout=timeout)
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.debug(f"任务 '{task_name}' 完成 (耗时: {elapsed:.2f}s)")
                return result
                
            except asyncio.TimeoutError:
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.warning(f"任务 '{task_name}' 超时 (耗时: {elapsed:.2f}s, 超时设置: {timeout}s)")
                
                # 尝试取消任务
                await self._cancel_task(task, task_name)
                
                raise asyncio.TimeoutError(f"Task '{task_name}' timed out after {timeout}s")
                
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            
            if isinstance(e, asyncio.TimeoutError):
                logger.error(f"任务 '{task_name}' 超时: {e}")
                raise
            else:
                logger.error(f"任务 '{task_name}' 失败 (耗时: {elapsed:.2f}s): {e}")
                raise ServiceUnavailableError(
                    f"Task '{task_name}' failed: {str(e)}",
                    service_name=task_name
                ) from e
                
        finally:
            # 清理任务记录
            if task_name in self.active_tasks:
                del self.active_tasks[task_name]
    
    @asynccontextmanager
    async def timeout_context(
        self,
        timeout: Optional[float] = None,
        context_name: str = "context"
    ):
        """
        超时上下文管理器
        
        Args:
            timeout: 超时时间（秒）
            context_name: 上下文名称
        """
        timeout = timeout or self.default_timeout
        start_time = datetime.now()
        
        logger.debug(f"进入超时上下文 '{context_name}' (超时: {timeout}s)")
        
        try:
            # 创建超时任务
            timeout_task = asyncio.create_task(asyncio.sleep(timeout))
            
            # 使用 yield 让调用者在上下文中执行代码
            yield timeout_task
            
        except asyncio.TimeoutError:
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.error(f"上下文 '{context_name}' 超时 (耗时: {elapsed:.2f}s)")
            raise
            
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.error(f"上下文 '{context_name}' 异常 (耗时: {elapsed:.2f}s): {e}")
            raise
            
        finally:
            # 取消超时任务
            if 'timeout_task' in locals() and not timeout_task.done():
                timeout_task.cancel()
                
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.debug(f"退出超时上下文 '{context_name}' (耗时: {elapsed:.2f}s)")
    
    async def cancel_task(self, task_name: str) -> bool:
        """
        取消指定任务
        
        Args:
            task_name: 任务名称
            
        Returns:
            bool: 是否成功取消
        """
        if task_name not in self.active_tasks:
            logger.warning(f"任务 '{task_name}' 不存在或已完成")
            return False
        
        task_info = self.active_tasks[task_name]
        success = await self._cancel_task(task_info.task, task_name)
        
        if success:
            del self.active_tasks[task_name]
        
        return success
    
    async def cancel_all_tasks(self) -> int:
        """
        取消所有活动任务
        
        Returns:
            int: 成功取消的任务数量
        """
        if not self.active_tasks:
            logger.info("没有活动任务需要取消")
            return 0
        
        logger.info(f"取消所有活动任务 (共 {len(self.active_tasks)} 个)...")
        
        cancelled_count = 0
        task_names = list(self.active_tasks.keys())
        
        for task_name in task_names:
            task_info = self.active_tasks[task_name]
            success = await self._cancel_task(task_info.task, task_name)
            if success:
                cancelled_count += 1
                del self.active_tasks[task_name]
        
        logger.info(f"已取消 {cancelled_count} 个任务")
        return cancelled_count
    
    def get_active_tasks(self) -> Dict[str, Dict[str, Any]]:
        """
        获取活动任务状态
        
        Returns:
            Dict: 任务状态信息
        """
        return {
            name: task_info.to_dict()
            for name, task_info in self.active_tasks.items()
        }
    
    def get_task_count(self) -> int:
        """获取活动任务数量"""
        return len(self.active_tasks)
    
    def has_active_tasks(self) -> bool:
        """是否有活动任务"""
        return len(self.active_tasks) > 0
    
    def get_timeout_tasks(self) -> Dict[str, TaskInfo]:
        """获取已超时的任务"""
        return {
            name: task_info
            for name, task_info in self.active_tasks.items()
            if task_info.is_timeout
        }
    
    async def cleanup_completed_tasks(self) -> int:
        """
        清理已完成的任务
        
        Returns:
            int: 清理的任务数量
        """
        completed_tasks = [
            name for name, task_info in self.active_tasks.items()
            if task_info.is_done
        ]
        
        for task_name in completed_tasks:
            del self.active_tasks[task_name]
        
        if completed_tasks:
            logger.debug(f"清理了 {len(completed_tasks)} 个已完成的任务")
        
        return len(completed_tasks)
    
    async def _cancel_task(self, task: asyncio.Task, task_name: str) -> bool:
        """
        取消单个任务
        
        Args:
            task: 任务对象
            task_name: 任务名称
            
        Returns:
            bool: 是否成功取消
        """
        if task.done():
            logger.debug(f"任务 '{task_name}' 已完成，无需取消")
            return True
        
        try:
            logger.debug(f"取消任务: {task_name}")
            task.cancel()
            
            # 等待任务真正取消
            try:
                await task
            except asyncio.CancelledError:
                logger.debug(f"任务 '{task_name}' 已成功取消")
                return True
            except Exception as e:
                logger.warning(f"任务 '{task_name}' 取消时发生异常: {e}")
                return True  # 任务已结束，算作成功
            
        except Exception as e:
            logger.error(f"取消任务 '{task_name}' 失败: {e}")
            return False
        
        return False
    
    async def _cleanup_if_needed(self) -> None:
        """定期清理已完成的任务"""
        now = datetime.now()
        if (now - self._last_cleanup).total_seconds() >= self._cleanup_interval:
            await self.cleanup_completed_tasks()
            self._last_cleanup = now
    
    def _generate_task_name(self, coro_or_func: Any) -> str:
        """生成任务名称"""
        if hasattr(coro_or_func, '__name__'):
            base_name = coro_or_func.__name__
        elif hasattr(coro_or_func, '_coro') and hasattr(coro_or_func._coro, 'cr_code'):
            base_name = coro_or_func._coro.cr_code.co_name
        else:
            base_name = "unknown"
        
        # 添加时间戳确保唯一性
        timestamp = int(time.time() * 1000) % 10000
        return f"{base_name}_{timestamp}"
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        active_count = len(self.active_tasks)
        timeout_count = len(self.get_timeout_tasks())
        
        return {
            "default_timeout": self.default_timeout,
            "active_tasks_count": active_count,
            "timeout_tasks_count": timeout_count,
            "last_cleanup": self._last_cleanup.isoformat(),
            "cleanup_interval": self._cleanup_interval
        }


def timeout_decorator(
    timeout: float = 30.0,
    task_name: Optional[str] = None
):
    """
    超时装饰器
    
    Args:
        timeout: 超时时间（秒）
        task_name: 任务名称
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            name = task_name or func.__name__
            manager = TimeoutManager(default_timeout=timeout)
            
            if asyncio.iscoroutinefunction(func):
                coro = func(*args, **kwargs)
            else:
                coro = functools.partial(func, *args, **kwargs)
            
            return await manager.execute_with_timeout(
                coro,
                timeout=timeout,
                task_name=name
            )
        
        return wrapper
    return decorator


class TimeoutConfig:
    """超时配置类"""
    
    # 默认超时配置
    DEFAULT_TIMEOUT = 30.0
    NETWORK_TIMEOUT = 10.0
    DATABASE_TIMEOUT = 5.0
    FILE_OPERATION_TIMEOUT = 15.0
    SCRAPING_TIMEOUT = 60.0
    LLM_TIMEOUT = 120.0
    
    @classmethod
    def get_timeout_for_operation(cls, operation_type: str) -> float:
        """
        根据操作类型获取推荐的超时时间
        
        Args:
            operation_type: 操作类型
            
        Returns:
            float: 推荐的超时时间（秒）
        """
        timeout_map = {
            'network': cls.NETWORK_TIMEOUT,
            'database': cls.DATABASE_TIMEOUT,
            'file': cls.FILE_OPERATION_TIMEOUT,
            'scraping': cls.SCRAPING_TIMEOUT,
            'llm': cls.LLM_TIMEOUT,
            'default': cls.DEFAULT_TIMEOUT
        }
        
        return timeout_map.get(operation_type.lower(), cls.DEFAULT_TIMEOUT)


# 全局超时管理器实例
_global_timeout_manager = None


def get_global_timeout_manager() -> TimeoutManager:
    """获取全局超时管理器实例"""
    global _global_timeout_manager
    if _global_timeout_manager is None:
        _global_timeout_manager = TimeoutManager()
    return _global_timeout_manager


# 便利函数
async def execute_with_timeout(
    coro_or_func: Union[Callable, Any],
    timeout: Optional[float] = None,
    task_name: Optional[str] = None
) -> Any:
    """
    执行异步操作并应用超时控制
    
    Args:
        coro_or_func: 协程或可调用对象
        timeout: 超时时间（秒）
        task_name: 任务名称
        
    Returns:
        操作结果
    """
    manager = get_global_timeout_manager()
    return await manager.execute_with_timeout(coro_or_func, timeout, task_name)


async def with_timeout_context(
    timeout: Optional[float] = None,
    context_name: str = "context"
):
    """
    超时上下文管理器的便利函数
    
    Args:
        timeout: 超时时间（秒）
        context_name: 上下文名称
    """
    manager = get_global_timeout_manager()
    return manager.timeout_context(timeout, context_name)


async def cancel_all_global_tasks() -> int:
    """
    取消所有全局任务
    
    Returns:
        int: 成功取消的任务数量
    """
    manager = get_global_timeout_manager()
    return await manager.cancel_all_tasks()


def get_global_task_statistics() -> Dict[str, Any]:
    """获取全局任务统计信息"""
    manager = get_global_timeout_manager()
    return manager.get_statistics()