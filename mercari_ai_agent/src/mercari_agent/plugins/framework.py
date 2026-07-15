"""
统一插件框架核心管理器

该模块实现了插件框架的核心功能，提供：
- 插件的统一生命周期管理
- 插件间通信协调
- 热插拔支持
- 性能监控和统计
- 配置管理和版本控制
- 故障隔离和恢复

核心设计原则：
- 松耦合架构
- 事件驱动通信
- 高性能异步处理
- 完全向后兼容

Author: Mercari AI Agent Team
"""

import asyncio
import logging
import time
import threading
from typing import Dict, List, Optional, Any, Union, Callable, Type, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import weakref
from concurrent.futures import ThreadPoolExecutor
import json
from enum import Enum

from .interfaces import (
    IPlugin, PluginType, PluginCapability, PluginConfiguration, 
    PluginPerformanceMetrics, plugin_context
)
from .registry import PluginRegistry
from .loader import PluginLoader
from .lifecycle import PluginLifecycleManager
from .config_manager import PluginConfigManager

# 导入现有的基础设施
from ..captcha.plugin_interface import PluginStatus, PluginPriority, PluginEvent
from ..captcha.plugin_registry import PluginEventManager, PluginMonitor
from ..utils.logger import get_logger

logger = get_logger(__name__)


class FrameworkStatus(Enum):
    """框架状态"""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class FrameworkConfig:
    """框架配置"""
    # 基础配置
    max_plugins: int = 100
    plugin_timeout: float = 30.0
    enable_hot_reload: bool = True
    enable_performance_monitoring: bool = True
    enable_health_checks: bool = True
    
    # 通信配置
    max_concurrent_operations: int = 50
    event_queue_size: int = 1000
    inter_plugin_timeout: float = 10.0
    
    # 性能配置
    metrics_collection_interval: float = 60.0
    health_check_interval: float = 300.0
    plugin_gc_interval: float = 3600.0
    
    # 故障处理
    max_retry_attempts: int = 3
    failure_threshold: int = 5
    recovery_timeout: float = 300.0
    
    # 存储配置
    enable_persistent_config: bool = True
    config_storage_path: str = "config/plugins"
    metrics_storage_path: str = "data/plugin_metrics"


@dataclass
class FrameworkStats:
    """框架统计信息"""
    total_plugins: int = 0
    active_plugins: int = 0
    failed_plugins: int = 0
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    average_response_time: float = 0.0
    uptime: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    
    # 插件类型统计
    plugin_type_stats: Dict[str, int] = field(default_factory=dict)
    
    # 性能统计
    performance_metrics: Dict[str, PluginPerformanceMetrics] = field(default_factory=dict)
    
    def update_operation_stats(self, success: bool, response_time: float):
        """更新操作统计"""
        self.total_operations += 1
        if success:
            self.successful_operations += 1
        else:
            self.failed_operations += 1
        
        # 更新平均响应时间
        current_total = self.average_response_time * (self.total_operations - 1)
        self.average_response_time = (current_total + response_time) / self.total_operations


class PluginFramework:
    """
    统一插件框架管理器
    
    核心功能：
    1. 插件生命周期管理
    2. 插件间通信协调
    3. 热插拔支持
    4. 性能监控和统计
    5. 配置管理和版本控制
    6. 故障隔离和恢复
    """
    
    _instance: Optional['PluginFramework'] = None
    _lock = threading.Lock()
    
    def __new__(cls, config: Optional[FrameworkConfig] = None) -> 'PluginFramework':
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, config: Optional[FrameworkConfig] = None):
        # 防止重复初始化
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self.config = config or FrameworkConfig()
        self.status = FrameworkStatus.UNINITIALIZED
        self.start_time = time.time()
        
        # 核心组件
        self.plugin_registry = PluginRegistry()
        self.plugin_loader = PluginLoader(self)
        self.lifecycle_manager = PluginLifecycleManager(self)
        self.config_manager = PluginConfigManager(self)
        
        # 事件和监控系统
        self.event_manager = PluginEventManager()
        self.monitor = PluginMonitor()
        
        # 插件管理
        self.plugins: Dict[str, IPlugin] = {}
        self.plugin_dependencies: Dict[str, Set[str]] = defaultdict(set)
        self.plugin_dependents: Dict[str, Set[str]] = defaultdict(set)
        
        # 通信和协调
        self.operation_queue = asyncio.Queue(maxsize=self.config.max_concurrent_operations)
        self.inter_plugin_channels: Dict[str, asyncio.Queue] = {}
        
        # 统计和监控
        self.stats = FrameworkStats()
        self.health_status: Dict[str, Dict[str, Any]] = {}
        
        # 任务管理
        self.background_tasks: List[asyncio.Task] = []
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        
        # 事件回调
        self.event_callbacks: Dict[str, List[Callable]] = defaultdict(list)
        
        # 框架级别的锁
        self.framework_lock = asyncio.Lock()
        
        logger.info("PluginFramework initialized")
    
    @classmethod
    def get_instance(cls, config: Optional[FrameworkConfig] = None) -> 'PluginFramework':
        """获取单例实例"""
        return cls(config)
    
    async def initialize(self):
        """初始化框架"""
        async with self.framework_lock:
            if self.status != FrameworkStatus.UNINITIALIZED:
                logger.warning("Framework already initialized")
                return
            
            try:
                logger.info("Initializing PluginFramework...")
                self.status = FrameworkStatus.INITIALIZING
                
                # 1. 初始化核心组件
                await self._initialize_core_components()
                
                # 2. 启动事件管理器
                await self.event_manager.start()
                
                # 3. 启动监控系统
                if self.config.enable_performance_monitoring:
                    await self.monitor.start(self.config.metrics_collection_interval)
                
                # 4. 启动背景任务
                self._start_background_tasks()
                
                # 5. 加载配置
                await self.config_manager.load_configurations()
                
                self.status = FrameworkStatus.RUNNING
                logger.info("PluginFramework initialized successfully")
                
            except Exception as e:
                self.status = FrameworkStatus.ERROR
                logger.error(f"Failed to initialize PluginFramework: {e}")
                raise
    
    async def _initialize_core_components(self):
        """初始化核心组件"""
        # 初始化插件注册表
        if not self.plugin_registry.running:
            await self.plugin_registry.start_all_plugins()
        
        # 初始化加载器
        await self.plugin_loader.initialize()
        
        # 初始化生命周期管理器
        await self.lifecycle_manager.initialize()
        
        # 初始化配置管理器
        await self.config_manager.initialize()
        
        logger.info("Core components initialized")
    
    def _start_background_tasks(self):
        """启动背景任务"""
        # 操作队列处理器
        self.background_tasks.append(
            asyncio.create_task(self._operation_queue_processor())
        )
        
        # 健康检查任务
        if self.config.enable_health_checks:
            self.background_tasks.append(
                asyncio.create_task(self._health_check_loop())
            )
        
        # 垃圾回收任务
        self.background_tasks.append(
            asyncio.create_task(self._garbage_collection_loop())
        )
        
        # 统计更新任务
        self.background_tasks.append(
            asyncio.create_task(self._stats_update_loop())
        )
        
        logger.info("Background tasks started")
    
    async def stop(self):
        """停止框架"""
        async with self.framework_lock:
            if self.status == FrameworkStatus.STOPPED:
                return
            
            try:
                logger.info("Stopping PluginFramework...")
                self.status = FrameworkStatus.STOPPING
                
                # 1. 停止所有插件
                await self._stop_all_plugins()
                
                # 2. 停止背景任务
                await self._stop_background_tasks()
                
                # 3. 停止监控系统
                await self.monitor.stop()
                
                # 4. 停止事件管理器
                await self.event_manager.stop()
                
                # 5. 保存配置
                await self.config_manager.save_configurations()
                
                # 6. 清理资源
                await self._cleanup_resources()
                
                self.status = FrameworkStatus.STOPPED
                logger.info("PluginFramework stopped successfully")
                
            except Exception as e:
                self.status = FrameworkStatus.ERROR
                logger.error(f"Failed to stop PluginFramework: {e}")
                raise
    
    async def load_plugin(self, plugin_class: Type[IPlugin], 
                         plugin_config: Dict[str, Any] = None) -> bool:
        """加载插件"""
        try:
            # 1. 创建插件实例
            plugin_instance = plugin_class(plugin_config)
            plugin_id = plugin_instance.plugin_config.plugin_id
            
            # 2. 检查依赖
            if not await self._check_plugin_dependencies(plugin_instance):
                logger.error(f"Plugin {plugin_id} dependencies not satisfied")
                return False
            
            # 3. 加载插件
            success = await self.plugin_loader.load_plugin(plugin_instance)
            if not success:
                return False
            
            # 4. 注册插件
            self.plugins[plugin_id] = plugin_instance
            
            # 5. 更新依赖关系
            await self._update_plugin_dependencies(plugin_instance)
            
            # 6. 触发事件
            await self._trigger_plugin_event('plugin_loaded', {
                'plugin_id': plugin_id,
                'plugin_type': plugin_instance.plugin_config.plugin_type.value
            })
            
            # 7. 更新统计
            self.stats.total_plugins += 1
            self.stats.active_plugins += 1
            
            logger.info(f"Plugin {plugin_id} loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load plugin: {e}")
            return False
    
    async def unload_plugin(self, plugin_id: str) -> bool:
        """卸载插件"""
        try:
            if plugin_id not in self.plugins:
                logger.warning(f"Plugin {plugin_id} not found")
                return False
            
            plugin = self.plugins[plugin_id]
            
            # 1. 检查依赖关系
            if not await self._can_unload_plugin(plugin_id):
                logger.error(f"Plugin {plugin_id} cannot be unloaded due to dependencies")
                return False
            
            # 2. 卸载插件
            success = await self.plugin_loader.unload_plugin(plugin)
            if not success:
                return False
            
            # 3. 清理注册
            del self.plugins[plugin_id]
            
            # 4. 更新依赖关系
            await self._cleanup_plugin_dependencies(plugin_id)
            
            # 5. 触发事件
            await self._trigger_plugin_event('plugin_unloaded', {
                'plugin_id': plugin_id
            })
            
            # 6. 更新统计
            self.stats.total_plugins -= 1
            self.stats.active_plugins -= 1
            
            logger.info(f"Plugin {plugin_id} unloaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unload plugin {plugin_id}: {e}")
            return False
    
    async def get_plugin(self, plugin_id: str) -> Optional[IPlugin]:
        """获取插件"""
        return self.plugins.get(plugin_id)
    
    async def get_plugins_by_type(self, plugin_type: PluginType) -> List[IPlugin]:
        """按类型获取插件"""
        return [
            plugin for plugin in self.plugins.values()
            if plugin.plugin_config.plugin_type == plugin_type
        ]
    
    async def get_plugins_by_capability(self, capability: PluginCapability) -> List[IPlugin]:
        """按能力获取插件"""
        return [
            plugin for plugin in self.plugins.values()
            if capability in plugin.capabilities
        ]
    
    async def execute_plugin_operation(self, plugin_id: str, operation: str, 
                                     *args, **kwargs) -> Any:
        """执行插件操作"""
        plugin = self.plugins.get(plugin_id)
        if not plugin:
            raise ValueError(f"Plugin {plugin_id} not found")
        
        if not hasattr(plugin, operation):
            raise ValueError(f"Operation {operation} not supported by plugin {plugin_id}")
        
        method = getattr(plugin, operation)
        return await plugin.execute_with_metrics(method, *args, **kwargs)
    
    async def send_inter_plugin_message(self, source_plugin_id: str, 
                                      target_plugin_id: str, 
                                      message: Dict[str, Any]) -> bool:
        """发送插件间消息"""
        try:
            # 创建插件事件
            event = PluginEvent(
                event_type='inter_plugin_message',
                source_plugin=source_plugin_id,
                target_plugin=target_plugin_id,
                data=message
            )
            
            # 发送事件
            await self.event_manager.emit_event(event)
            
            # 如果目标插件存在，直接通知
            target_plugin = self.plugins.get(target_plugin_id)
            if target_plugin:
                await target_plugin.handle_event(event)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send inter-plugin message: {e}")
            return False
    
    async def get_framework_stats(self) -> Dict[str, Any]:
        """获取框架统计信息"""
        # 更新运行时间
        self.stats.uptime = time.time() - self.start_time
        
        # 更新插件类型统计
        self.stats.plugin_type_stats.clear()
        for plugin in self.plugins.values():
            plugin_type = plugin.plugin_config.plugin_type.value
            self.stats.plugin_type_stats[plugin_type] = self.stats.plugin_type_stats.get(plugin_type, 0) + 1
        
        # 更新性能指标
        self.stats.performance_metrics.clear()
        for plugin_id, plugin in self.plugins.items():
            self.stats.performance_metrics[plugin_id] = plugin.performance_metrics
        
        return {
            'framework_status': self.status.value,
            'uptime': self.stats.uptime,
            'total_plugins': self.stats.total_plugins,
            'active_plugins': self.stats.active_plugins,
            'failed_plugins': self.stats.failed_plugins,
            'total_operations': self.stats.total_operations,
            'successful_operations': self.stats.successful_operations,
            'failed_operations': self.stats.failed_operations,
            'average_response_time': self.stats.average_response_time,
            'memory_usage_mb': self.stats.memory_usage_mb,
            'cpu_usage_percent': self.stats.cpu_usage_percent,
            'plugin_type_stats': self.stats.plugin_type_stats,
            'performance_metrics': {
                plugin_id: {
                    'initialization_time': metrics.initialization_time,
                    'average_execution_time': metrics.average_execution_time,
                    'total_executions': metrics.total_executions,
                    'success_rate': metrics.success_rate,
                    'memory_usage_mb': metrics.memory_usage_mb,
                    'cpu_usage_percent': metrics.cpu_usage_percent
                }
                for plugin_id, metrics in self.stats.performance_metrics.items()
            }
        }
    
    async def _check_plugin_dependencies(self, plugin: IPlugin) -> bool:
        """检查插件依赖"""
        for dependency in plugin.plugin_config.dependencies:
            if dependency not in self.plugins:
                logger.error(f"Dependency {dependency} not found for plugin {plugin.plugin_config.plugin_id}")
                return False
        return True
    
    async def _update_plugin_dependencies(self, plugin: IPlugin):
        """更新插件依赖关系"""
        plugin_id = plugin.plugin_config.plugin_id
        
        for dependency in plugin.plugin_config.dependencies:
            self.plugin_dependencies[plugin_id].add(dependency)
            self.plugin_dependents[dependency].add(plugin_id)
    
    async def _can_unload_plugin(self, plugin_id: str) -> bool:
        """检查是否可以卸载插件"""
        return len(self.plugin_dependents[plugin_id]) == 0
    
    async def _cleanup_plugin_dependencies(self, plugin_id: str):
        """清理插件依赖关系"""
        # 清理该插件的依赖
        for dependency in self.plugin_dependencies[plugin_id]:
            self.plugin_dependents[dependency].discard(plugin_id)
        
        # 清理依赖该插件的关系
        for dependent in self.plugin_dependents[plugin_id]:
            self.plugin_dependencies[dependent].discard(plugin_id)
        
        # 清理映射
        del self.plugin_dependencies[plugin_id]
        del self.plugin_dependents[plugin_id]
    
    async def _trigger_plugin_event(self, event_type: str, data: Dict[str, Any]):
        """触发插件事件"""
        event = PluginEvent(
            event_type=event_type,
            source_plugin='framework',
            data=data
        )
        await self.event_manager.emit_event(event)
    
    async def _operation_queue_processor(self):
        """操作队列处理器"""
        while self.status == FrameworkStatus.RUNNING:
            try:
                # 等待操作
                operation = await asyncio.wait_for(
                    self.operation_queue.get(),
                    timeout=1.0
                )
                
                # 处理操作
                await self._process_operation(operation)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Operation queue processor error: {e}")
    
    async def _process_operation(self, operation: Dict[str, Any]):
        """处理操作"""
        # 这里可以添加具体的操作处理逻辑
        pass
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while self.status == FrameworkStatus.RUNNING:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._perform_health_checks()
            except Exception as e:
                logger.error(f"Health check error: {e}")
    
    async def _perform_health_checks(self):
        """执行健康检查"""
        for plugin_id, plugin in self.plugins.items():
            try:
                health_result = await plugin.healthcheck()
                self.health_status[plugin_id] = health_result
                
                # 检查健康状态
                if not health_result.get('healthy', False):
                    logger.warning(f"Plugin {plugin_id} health check failed")
                    
            except Exception as e:
                logger.error(f"Health check failed for plugin {plugin_id}: {e}")
                self.health_status[plugin_id] = {
                    'healthy': False,
                    'error': str(e)
                }
    
    async def _garbage_collection_loop(self):
        """垃圾回收循环"""
        while self.status == FrameworkStatus.RUNNING:
            try:
                await asyncio.sleep(self.config.plugin_gc_interval)
                await self._perform_garbage_collection()
            except Exception as e:
                logger.error(f"Garbage collection error: {e}")
    
    async def _perform_garbage_collection(self):
        """执行垃圾回收"""
        # 清理失效的插件引用
        # 清理过期的事件
        # 清理过期的指标数据
        pass
    
    async def _stats_update_loop(self):
        """统计更新循环"""
        while self.status == FrameworkStatus.RUNNING:
            try:
                await asyncio.sleep(self.config.metrics_collection_interval)
                await self._update_stats()
            except Exception as e:
                logger.error(f"Stats update error: {e}")
    
    async def _update_stats(self):
        """更新统计信息"""
        # 更新内存使用
        # 更新CPU使用
        # 更新其他系统指标
        pass
    
    async def _stop_all_plugins(self):
        """停止所有插件"""
        for plugin_id, plugin in self.plugins.items():
            try:
                await plugin.stop()
                logger.info(f"Plugin {plugin_id} stopped")
            except Exception as e:
                logger.error(f"Failed to stop plugin {plugin_id}: {e}")
    
    async def _stop_background_tasks(self):
        """停止背景任务"""
        for task in self.background_tasks:
            try:
                task.cancel()
                await task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Failed to stop background task: {e}")
        
        self.background_tasks.clear()
    
    async def _cleanup_resources(self):
        """清理资源"""
        # 关闭线程池
        self.thread_pool.shutdown(wait=False)
        
        # 清理队列
        while not self.operation_queue.empty():
            try:
                self.operation_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        
        # 清理其他资源
        self.plugins.clear()
        self.plugin_dependencies.clear()
        self.plugin_dependents.clear()
        self.health_status.clear()