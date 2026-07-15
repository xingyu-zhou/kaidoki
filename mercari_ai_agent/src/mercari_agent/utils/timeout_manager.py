"""
超时管理器

提供异步操作的超时控制和死锁预防机制
"""

import asyncio
import functools
import time
from typing import Any, Callable, Optional, TypeVar, Union
from contextlib import asynccontextmanager

from .logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class TimeoutManager:
    """超时管理器"""
    
    def __init__(self, default_timeout: int = 30):
        self.default_timeout = default_timeout
        self.active_tasks = {}
        
    async def with_timeout(
        self, 
        coro_or_func: Union[Callable, Any], 
        timeout: Optional[int] = None,
        task_name: str = "unknown"
    ) -> Any:
        """
        为异步操作添加超时控制
        
        Args:
            coro_or_func: 协程或可调用对象
            timeout: 超时时间（秒）
            task_name: 任务名称，用于日志记录
            
        Returns:
            操作结果
            
        Raises:
            asyncio.TimeoutError: 超时异常
        """
        timeout = timeout or self.default_timeout
        start_time = time.time()
        
        logger.info(f"⏱️ 开始执行任务 '{task_name}' (超时: {timeout}s)")
        
        try:
            # 如果是协程，直接等待
            if asyncio.iscoroutine(coro_or_func):
                task = asyncio.create_task(coro_or_func)
            # 如果是异步函数，先调用
            elif asyncio.iscoroutinefunction(coro_or_func):
                task = asyncio.create_task(coro_or_func())
            # 如果是普通函数，在线程池中执行
            else:
                loop = asyncio.get_event_loop()
                task = loop.run_in_executor(None, coro_or_func)
            
            # 记录活动任务
            self.active_tasks[task_name] = {
                'task': task,
                'start_time': start_time,
                'timeout': timeout
            }
            
            # 等待任务完成或超时
            result = await asyncio.wait_for(task, timeout=timeout)
            
            elapsed = time.time() - start_time
            logger.info(f"✅ 任务 '{task_name}' 完成 (耗时: {elapsed:.2f}s)")
            
            return result
            
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            logger.error(f"⏰ 任务 '{task_name}' 超时 (耗时: {elapsed:.2f}s, 超时设置: {timeout}s)")
            
            # 尝试取消任务
            if task_name in self.active_tasks:
                task = self.active_tasks[task_name]['task']
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        logger.info(f"任务 '{task_name}' 已取消")
                        
            raise
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"❌ 任务 '{task_name}' 失败 (耗时: {elapsed:.2f}s): {e}")
            raise
            
        finally:
            # 清理活动任务记录
            if task_name in self.active_tasks:
                del self.active_tasks[task_name]
    
    @asynccontextmanager
    async def timeout_context(self, timeout: int = None, task_name: str = "context"):
        """超时上下文管理器"""
        timeout = timeout or self.default_timeout
        start_time = time.time()
        
        logger.info(f"⏱️ 进入超时上下文 '{task_name}' (超时: {timeout}s)")
        
        try:
            # 创建超时任务
            timeout_task = asyncio.create_task(asyncio.sleep(timeout))
            
            # 使用yield让调用者在上下文中执行代码
            yield timeout_task
            
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            logger.error(f"⏰ 上下文 '{task_name}' 超时 (耗时: {elapsed:.2f}s)")
            raise
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"❌ 上下文 '{task_name}' 异常 (耗时: {elapsed:.2f}s): {e}")
            raise
            
        finally:
            # 取消超时任务
            if not timeout_task.done():
                timeout_task.cancel()
                
            elapsed = time.time() - start_time
            logger.info(f"✅ 退出超时上下文 '{task_name}' (耗时: {elapsed:.2f}s)")
    
    def get_active_tasks(self) -> dict:
        """获取活动任务状态"""
        current_time = time.time()
        status = {}
        
        for task_name, task_info in self.active_tasks.items():
            elapsed = current_time - task_info['start_time']
            remaining = task_info['timeout'] - elapsed
            
            status[task_name] = {
                'elapsed': elapsed,
                'remaining': remaining,
                'timeout': task_info['timeout'],
                'is_done': task_info['task'].done()
            }
            
        return status
    
    async def cancel_all_tasks(self):
        """取消所有活动任务"""
        logger.info("🛑 取消所有活动任务...")
        
        for task_name, task_info in self.active_tasks.items():
            task = task_info['task']
            if not task.done():
                logger.info(f"取消任务: {task_name}")
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        self.active_tasks.clear()
        logger.info("✅ 所有任务已取消")


def timeout_decorator(timeout: int = 30, task_name: str = None):
    """超时装饰器"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            name = task_name or func.__name__
            manager = TimeoutManager()
            
            if asyncio.iscoroutinefunction(func):
                return await manager.with_timeout(
                    func(*args, **kwargs), 
                    timeout=timeout,
                    task_name=name
                )
            else:
                return await manager.with_timeout(
                    functools.partial(func, *args, **kwargs),
                    timeout=timeout,
                    task_name=name
                )
        return wrapper
    return decorator


# 全局超时管理器实例
global_timeout_manager = TimeoutManager()