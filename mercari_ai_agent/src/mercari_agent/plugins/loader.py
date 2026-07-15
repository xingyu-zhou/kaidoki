"""
插件动态加载器

该模块实现了插件的动态加载、卸载和热插拔功能，提供：
- 安全的插件加载和卸载
- 热插拔支持
- 加载状态监控
- 错误隔离和恢复
- 资源管理
- 性能优化

核心设计原则：
- 安全第一，确保插件错误不影响主系统
- 支持热插拔，无需重启服务
- 资源隔离，防止内存泄漏
- 异步处理，不阻塞主流程

Author: Mercari AI Agent Team
"""

import asyncio
import importlib
import sys
import threading
import time
import gc
import traceback
from typing import Dict, List, Optional, Any, Type, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import asynccontextmanager
import weakref
from concurrent.futures import ThreadPoolExecutor
import resource
import psutil
import os

from .interfaces import IPlugin, PluginType, PluginCapability
from ..captcha.plugin_interface import PluginStatus, PluginEvent
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LoadingContext:
    """插件加载上下文"""
    plugin_id: str
    plugin_class: Type[IPlugin]
    config: Dict[str, Any]
    start_time: float = field(default_factory=time.time)
    
    # 资源使用情况
    initial_memory_mb: float = 0.0
    final_memory_mb: float = 0.0
    cpu_time: float = 0.0
    
    # 加载状态
    status: str = "loading"
    error: Optional[Exception] = None
    
    def get_memory_usage(self) -> float:
        """获取内存使用情况"""
        return self.final_memory_mb - self.initial_memory_mb
    
    def get_loading_time(self) -> float:
        """获取加载时间"""
        return time.time() - self.start_time


@dataclass
class LoaderStats:
    """加载器统计信息"""
    total_loads: int = 0
    successful_loads: int = 0
    failed_loads: int = 0
    total_unloads: int = 0
    successful_unloads: int = 0
    failed_unloads: int = 0
    hot_reloads: int = 0
    average_load_time: float = 0.0
    average_memory_usage: float = 0.0
    
    def update_load_stats(self, success: bool, load_time: float, memory_usage: float):
        """更新加载统计"""
        self.total_loads += 1
        if success:
            self.successful_loads += 1
        else:
            self.failed_loads += 1
        
        # 更新平均加载时间
        total_successful = self.successful_loads
        if total_successful > 0:
            current_total_time = self.average_load_time * (total_successful - 1)
            self.average_load_time = (current_total_time + load_time) / total_successful
            
            # 更新平均内存使用
            current_total_memory = self.average_memory_usage * (total_successful - 1)
            self.average_memory_usage = (current_total_memory + memory_usage) / total_successful
    
    def update_unload_stats(self, success: bool):
        """更新卸载统计"""
        self.total_unloads += 1
        if success:
            self.successful_unloads += 1
        else:
            self.failed_unloads += 1


class ResourceMonitor:
    """资源监控器"""
    
    def __init__(self):
        self.process = psutil.Process(os.getpid())
    
    def get_memory_usage_mb(self) -> float:
        """获取当前内存使用（MB）"""
        try:
            memory_info = self.process.memory_info()
            return memory_info.rss / 1024 / 1024
        except Exception:
            return 0.0
    
    def get_cpu_usage_percent(self) -> float:
        """获取CPU使用率"""
        try:
            return self.process.cpu_percent()
        except Exception:
            return 0.0
    
    def get_thread_count(self) -> int:
        """获取线程数"""
        try:
            return self.process.num_threads()
        except Exception:
            return 0
    
    def get_open_files_count(self) -> int:
        """获取打开的文件数"""
        try:
            return len(self.process.open_files())
        except Exception:
            return 0


class PluginIsolation:
    """插件隔离器"""
    
    @staticmethod
    @asynccontextmanager
    async def isolated_execution(plugin_id: str, timeout: float = 30.0):
        """隔离执行上下文"""
        original_modules = set(sys.modules.keys())
        start_time = time.time()
        
        try:
            yield
        except asyncio.TimeoutError:
            logger.error(f"Plugin {plugin_id} execution timeout after {timeout}s")
            raise
        except Exception as e:
            logger.error(f"Plugin {plugin_id} execution error: {e}")
            raise
        finally:
            # 清理新加载的模块（如果需要）
            execution_time = time.time() - start_time
            logger.debug(f"Plugin {plugin_id} execution completed in {execution_time:.2f}s")
    
    @staticmethod
    def cleanup_plugin_modules(plugin_id: str, original_modules: set):
        """清理插件相关模块"""
        try:
            current_modules = set(sys.modules.keys())
            new_modules = current_modules - original_modules
            
            for module_name in new_modules:
                if plugin_id.lower() in module_name.lower():
                    try:
                        del sys.modules[module_name]
                        logger.debug(f"Cleaned up module: {module_name}")
                    except KeyError:
                        pass
            
            # 强制垃圾回收
            gc.collect()
            
        except Exception as e:
            logger.warning(f"Failed to cleanup modules for plugin {plugin_id}: {e}")


class PluginLoader:
    """
    插件动态加载器
    
    核心功能：
    1. 安全的插件加载和卸载
    2. 热插拔支持
    3. 资源监控和管理
    4. 错误隔离和恢复
    5. 性能统计
    """
    
    def __init__(self, framework_ref: Optional[weakref.ref] = None):
        self.framework_ref = framework_ref
        
        # 加载状态管理
        self.loaded_plugins: Dict[str, IPlugin] = {}
        self.loading_contexts: Dict[str, LoadingContext] = {}
        self.plugin_modules: Dict[str, set] = {}  # 插件相关模块
        
        # 资源监控
        self.resource_monitor = ResourceMonitor()
        
        # 统计信息
        self.stats = LoaderStats()
        
        # 加载配置
        self.config = {
            'max_load_time': 30.0,
            'max_memory_usage_mb': 100.0,
            'enable_resource_monitoring': True,
            'enable_module_cleanup': True,
            'isolation_timeout': 30.0,
            'max_concurrent_loads': 5
        }
        
        # 并发控制
        self.load_semaphore = asyncio.Semaphore(self.config['max_concurrent_loads'])
        self.loading_lock = asyncio.Lock()
        
        # 线程池
        self.thread_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="plugin_loader")
        
        logger.info("PluginLoader initialized")
    
    async def initialize(self):
        """初始化加载器"""
        try:
            logger.info("Initializing PluginLoader...")
            
            # 初始化资源监控
            if self.config['enable_resource_monitoring']:
                initial_memory = self.resource_monitor.get_memory_usage_mb()
                logger.info(f"Initial memory usage: {initial_memory:.2f} MB")
            
            logger.info("PluginLoader initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize PluginLoader: {e}")
            raise
    
    async def load_plugin(self, plugin: IPlugin) -> bool:
        """
        加载插件
        
        Args:
            plugin: 插件实例
            
        Returns:
            bool: 加载是否成功
        """
        plugin_id = plugin.plugin_config.plugin_id
        
        async with self.load_semaphore:
            try:
                logger.info(f"Loading plugin: {plugin_id}")
                
                # 检查是否已加载
                if plugin_id in self.loaded_plugins:
                    logger.warning(f"Plugin {plugin_id} already loaded")
                    return True
                
                # 创建加载上下文
                context = LoadingContext(
                    plugin_id=plugin_id,
                    plugin_class=type(plugin),
                    config=plugin.config
                )
                
                # 记录初始资源使用
                if self.config['enable_resource_monitoring']:
                    context.initial_memory_mb = self.resource_monitor.get_memory_usage_mb()
                
                self.loading_contexts[plugin_id] = context
                
                # 执行加载
                success = await self._load_plugin_impl(plugin, context)
                
                # 记录最终资源使用
                if self.config['enable_resource_monitoring']:
                    context.final_memory_mb = self.resource_monitor.get_memory_usage_mb()
                
                # 更新统计
                load_time = context.get_loading_time()
                memory_usage = context.get_memory_usage()
                self.stats.update_load_stats(success, load_time, memory_usage)
                
                if success:
                    self.loaded_plugins[plugin_id] = plugin
                    context.status = "loaded"
                    logger.info(f"Plugin {plugin_id} loaded successfully in {load_time:.2f}s, memory usage: {memory_usage:.2f}MB")
                else:
                    context.status = "failed"
                    logger.error(f"Failed to load plugin {plugin_id}")
                
                return success
                
            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_id}: {e}")
                if plugin_id in self.loading_contexts:
                    self.loading_contexts[plugin_id].error = e
                    self.loading_contexts[plugin_id].status = "error"
                return False
            finally:
                # 清理加载上下文（保留一段时间用于调试）
                asyncio.create_task(self._cleanup_loading_context(plugin_id, delay=300))
    
    async def _load_plugin_impl(self, plugin: IPlugin, context: LoadingContext) -> bool:
        """插件加载实现"""
        plugin_id = context.plugin_id
        
        try:
            # 记录加载前的模块状态
            original_modules = set(sys.modules.keys())
            self.plugin_modules[plugin_id] = original_modules
            
            # 在隔离环境中执行加载
            async with PluginIsolation.isolated_execution(
                plugin_id, 
                self.config['isolation_timeout']
            ):
                # 设置框架引用
                if self.framework_ref:
                    plugin.set_framework_reference(self.framework_ref)
                
                # 初始化插件
                success = await plugin.initialize()
                if not success:
                    return False
                
                # 启动插件
                success = await plugin.start()
                if not success:
                    return False
                
                # 验证插件状态
                if plugin.status != PluginStatus.ACTIVE:
                    logger.error(f"Plugin {plugin_id} not in active state after loading")
                    return False
                
                return True
                
        except Exception as e:
            logger.error(f"Plugin loading implementation failed for {plugin_id}: {e}")
            context.error = e
            return False
    
    async def unload_plugin(self, plugin: IPlugin) -> bool:
        """
        卸载插件
        
        Args:
            plugin: 插件实例
            
        Returns:
            bool: 卸载是否成功
        """
        plugin_id = plugin.plugin_config.plugin_id
        
        async with self.loading_lock:
            try:
                logger.info(f"Unloading plugin: {plugin_id}")
                
                # 检查是否已加载
                if plugin_id not in self.loaded_plugins:
                    logger.warning(f"Plugin {plugin_id} not loaded")
                    return True
                
                # 执行卸载
                success = await self._unload_plugin_impl(plugin)
                
                if success:
                    # 移除引用
                    del self.loaded_plugins[plugin_id]
                    
                    # 清理模块（如果启用）
                    if self.config['enable_module_cleanup']:
                        original_modules = self.plugin_modules.get(plugin_id, set())
                        await self._cleanup_plugin_modules(plugin_id, original_modules)
                    
                    logger.info(f"Plugin {plugin_id} unloaded successfully")
                else:
                    logger.error(f"Failed to unload plugin {plugin_id}")
                
                # 更新统计
                self.stats.update_unload_stats(success)
                
                return success
                
            except Exception as e:
                logger.error(f"Failed to unload plugin {plugin_id}: {e}")
                self.stats.update_unload_stats(False)
                return False
    
    async def _unload_plugin_impl(self, plugin: IPlugin) -> bool:
        """插件卸载实现"""
        plugin_id = plugin.plugin_config.plugin_id
        
        try:
            # 停止插件
            stop_success = await plugin.stop()
            if not stop_success:
                logger.warning(f"Plugin {plugin_id} stop failed, continuing with unload")
            
            # 验证插件状态
            if plugin.status not in [PluginStatus.STOPPED, PluginStatus.ERROR]:
                logger.warning(f"Plugin {plugin_id} not in expected state after stop: {plugin.status}")
            
            return True
            
        except Exception as e:
            logger.error(f"Plugin unloading implementation failed for {plugin_id}: {e}")
            return False
    
    async def reload_plugin(self, plugin_id: str) -> bool:
        """
        重新加载插件（热插拔）
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            bool: 重新加载是否成功
        """
        try:
            logger.info(f"Reloading plugin: {plugin_id}")
            
            # 获取当前插件
            current_plugin = self.loaded_plugins.get(plugin_id)
            if not current_plugin:
                logger.error(f"Plugin {plugin_id} not found for reload")
                return False
            
            # 保存配置
            current_config = current_plugin.config.copy()
            plugin_class = type(current_plugin)
            
            # 卸载当前插件
            unload_success = await self.unload_plugin(current_plugin)
            if not unload_success:
                logger.error(f"Failed to unload plugin {plugin_id} for reload")
                return False
            
            # 创建新实例
            new_plugin = plugin_class(current_config)
            
            # 加载新插件
            load_success = await self.load_plugin(new_plugin)
            if not load_success:
                logger.error(f"Failed to load new instance of plugin {plugin_id}")
                return False
            
            self.stats.hot_reloads += 1
            logger.info(f"Plugin {plugin_id} reloaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reload plugin {plugin_id}: {e}")
            return False
    
    async def _cleanup_plugin_modules(self, plugin_id: str, original_modules: set):
        """清理插件相关模块"""
        try:
            await asyncio.get_event_loop().run_in_executor(
                self.thread_pool,
                PluginIsolation.cleanup_plugin_modules,
                plugin_id,
                original_modules
            )
            
            # 清理模块记录
            if plugin_id in self.plugin_modules:
                del self.plugin_modules[plugin_id]
                
        except Exception as e:
            logger.warning(f"Failed to cleanup modules for plugin {plugin_id}: {e}")
    
    async def _cleanup_loading_context(self, plugin_id: str, delay: float = 0):
        """清理加载上下文"""
        if delay > 0:
            await asyncio.sleep(delay)
        
        if plugin_id in self.loading_contexts:
            del self.loading_contexts[plugin_id]
    
    def get_loaded_plugins(self) -> Dict[str, IPlugin]:
        """获取已加载的插件"""
        return self.loaded_plugins.copy()
    
    def get_plugin_by_id(self, plugin_id: str) -> Optional[IPlugin]:
        """根据ID获取插件"""
        return self.loaded_plugins.get(plugin_id)
    
    def get_plugins_by_type(self, plugin_type: PluginType) -> List[IPlugin]:
        """根据类型获取插件"""
        return [
            plugin for plugin in self.loaded_plugins.values()
            if plugin.plugin_config.plugin_type == plugin_type
        ]
    
    def get_plugins_by_capability(self, capability: PluginCapability) -> List[IPlugin]:
        """根据能力获取插件"""
        return [
            plugin for plugin in self.loaded_plugins.values()
            if capability in plugin.capabilities
        ]
    
    def get_loading_context(self, plugin_id: str) -> Optional[LoadingContext]:
        """获取加载上下文"""
        return self.loading_contexts.get(plugin_id)
    
    def get_loader_stats(self) -> Dict[str, Any]:
        """获取加载器统计信息"""
        return {
            'loaded_plugins_count': len(self.loaded_plugins),
            'loading_contexts_count': len(self.loading_contexts),
            'total_loads': self.stats.total_loads,
            'successful_loads': self.stats.successful_loads,
            'failed_loads': self.stats.failed_loads,
            'total_unloads': self.stats.total_unloads,
            'successful_unloads': self.stats.successful_unloads,
            'failed_unloads': self.stats.failed_unloads,
            'hot_reloads': self.stats.hot_reloads,
            'average_load_time': self.stats.average_load_time,
            'average_memory_usage': self.stats.average_memory_usage,
            'current_memory_usage_mb': self.resource_monitor.get_memory_usage_mb(),
            'current_cpu_usage_percent': self.resource_monitor.get_cpu_usage_percent(),
            'thread_count': self.resource_monitor.get_thread_count(),
            'open_files_count': self.resource_monitor.get_open_files_count()
        }
    
    async def perform_health_check(self) -> Dict[str, Any]:
        """执行健康检查"""
        health_results = {}
        
        for plugin_id, plugin in self.loaded_plugins.items():
            try:
                health_result = await plugin.healthcheck()
                health_results[plugin_id] = health_result
            except Exception as e:
                health_results[plugin_id] = {
                    'healthy': False,
                    'error': str(e)
                }
        
        return {
            'loader_healthy': True,
            'plugin_health': health_results,
            'resource_usage': {
                'memory_mb': self.resource_monitor.get_memory_usage_mb(),
                'cpu_percent': self.resource_monitor.get_cpu_usage_percent(),
                'threads': self.resource_monitor.get_thread_count(),
                'open_files': self.resource_monitor.get_open_files_count()
            }
        }
    
    async def cleanup(self):
        """清理资源"""
        try:
            logger.info("Cleaning up PluginLoader...")
            
            # 卸载所有插件
            for plugin_id, plugin in list(self.loaded_plugins.items()):
                try:
                    await self.unload_plugin(plugin)
                except Exception as e:
                    logger.error(f"Failed to unload plugin {plugin_id} during cleanup: {e}")
            
            # 关闭线程池
            self.thread_pool.shutdown(wait=False)
            
            # 清理上下文
            self.loading_contexts.clear()
            self.plugin_modules.clear()
            
            # 强制垃圾回收
            gc.collect()
            
            logger.info("PluginLoader cleanup completed")
            
        except Exception as e:
            logger.error(f"PluginLoader cleanup failed: {e}")
            raise


# 工具函数
async def load_plugin_from_class(plugin_class: Type[IPlugin], 
                                config: Dict[str, Any] = None) -> Optional[IPlugin]:
    """从类加载插件"""
    try:
        plugin = plugin_class(config)
        loader = PluginLoader()
        await loader.initialize()
        
        success = await loader.load_plugin(plugin)
        if success:
            return plugin
        return None
        
    except Exception as e:
        logger.error(f"Failed to load plugin from class {plugin_class.__name__}: {e}")
        return None


async def load_plugin_from_module(module_path: str, 
                                 class_name: str,
                                 config: Dict[str, Any] = None) -> Optional[IPlugin]:
    """从模块加载插件"""
    try:
        # 动态导入模块
        module = importlib.import_module(module_path)
        plugin_class = getattr(module, class_name)
        
        if not issubclass(plugin_class, IPlugin):
            raise TypeError(f"{class_name} is not a valid plugin class")
        
        return await load_plugin_from_class(plugin_class, config)
        
    except Exception as e:
        logger.error(f"Failed to load plugin from module {module_path}.{class_name}: {e}")
        return None