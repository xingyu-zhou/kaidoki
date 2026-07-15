"""
插件注册管理器

该模块实现了反检测系统的插件注册和管理机制，提供：
- 插件动态注册和发现
- 依赖关系解析
- 生命周期管理
- 插件间通信协调
- 配置管理和热更新
- 性能监控和统计

设计特点：
- 支持插件热插拔
- 自动依赖解析
- 事件驱动通信
- 完全向后兼容

Author: Mercari AI Agent Team
"""

import asyncio
import logging
import importlib
import inspect
import weakref
from typing import Dict, List, Optional, Any, Union, Type, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, OrderedDict
import json
import threading
from concurrent.futures import ThreadPoolExecutor

from .plugin_interface import (
    IAntiDetectionPlugin, PluginStatus, PluginPriority, PluginCategory,
    PluginMetadata, PluginEvent, IDetectionPlugin, ISessionPlugin,
    IFingerprintPlugin, IBehaviorPlugin, IEnvironmentPlugin
)
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PluginRegistration:
    """插件注册信息"""
    plugin_class: Type[IAntiDetectionPlugin]
    instance: Optional[IAntiDetectionPlugin] = None
    metadata: Optional[PluginMetadata] = None
    config: Dict[str, Any] = field(default_factory=dict)
    registration_time: datetime = field(default_factory=datetime.now)
    auto_start: bool = True
    singleton: bool = True
    
    def create_instance(self, config: Dict[str, Any] = None) -> IAntiDetectionPlugin:
        """创建插件实例"""
        if self.singleton and self.instance:
            return self.instance
        
        merged_config = {**self.config, **(config or {})}
        instance = self.plugin_class(merged_config)
        
        if self.singleton:
            self.instance = instance
            
        return instance


class DependencyResolver:
    """依赖解析器"""
    
    def __init__(self):
        self.dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_graph: Dict[str, Set[str]] = defaultdict(set)
    
    def add_dependency(self, plugin_name: str, dependency: str):
        """添加依赖关系"""
        self.dependency_graph[plugin_name].add(dependency)
        self.reverse_graph[dependency].add(plugin_name)
    
    def remove_dependency(self, plugin_name: str, dependency: str):
        """移除依赖关系"""
        self.dependency_graph[plugin_name].discard(dependency)
        self.reverse_graph[dependency].discard(plugin_name)
    
    def resolve_load_order(self, plugins: List[str]) -> List[str]:
        """解析加载顺序"""
        visited = set()
        visiting = set()
        result = []
        
        def visit(plugin_name: str):
            if plugin_name in visiting:
                raise ValueError(f"Circular dependency detected: {plugin_name}")
            
            if plugin_name in visited:
                return
            
            visiting.add(plugin_name)
            
            # 先访问依赖
            for dependency in self.dependency_graph[plugin_name]:
                if dependency in plugins:
                    visit(dependency)
            
            visiting.remove(plugin_name)
            visited.add(plugin_name)
            result.append(plugin_name)
        
        for plugin_name in plugins:
            if plugin_name not in visited:
                visit(plugin_name)
        
        return result
    
    def get_dependencies(self, plugin_name: str) -> Set[str]:
        """获取插件依赖"""
        return self.dependency_graph[plugin_name].copy()
    
    def get_dependents(self, plugin_name: str) -> Set[str]:
        """获取依赖该插件的其他插件"""
        return self.reverse_graph[plugin_name].copy()
    
    def can_unload(self, plugin_name: str) -> bool:
        """检查插件是否可以卸载（没有其他插件依赖它）"""
        return len(self.reverse_graph[plugin_name]) == 0


class PluginEventManager:
    """插件事件管理器"""
    
    def __init__(self):
        self.event_handlers: Dict[str, List[Callable]] = defaultdict(list)
        self.event_queue = asyncio.Queue()
        self.event_processor_task: Optional[asyncio.Task] = None
        self.running = False
    
    async def start(self):
        """启动事件处理器"""
        if not self.running:
            self.running = True
            self.event_processor_task = asyncio.create_task(self._process_events())
            logger.info("Plugin event manager started")
    
    async def stop(self):
        """停止事件处理器"""
        if self.running:
            self.running = False
            if self.event_processor_task:
                self.event_processor_task.cancel()
                try:
                    await self.event_processor_task
                except asyncio.CancelledError:
                    pass
            logger.info("Plugin event manager stopped")
    
    def register_handler(self, event_type: str, handler: Callable):
        """注册事件处理器"""
        self.event_handlers[event_type].append(handler)
        logger.debug(f"Registered handler for event type: {event_type}")
    
    def unregister_handler(self, event_type: str, handler: Callable):
        """注销事件处理器"""
        if handler in self.event_handlers[event_type]:
            self.event_handlers[event_type].remove(handler)
    
    async def emit_event(self, event: PluginEvent):
        """发送事件"""
        if self.running:
            await self.event_queue.put(event)
        else:
            logger.warning(f"Event manager not running, dropping event: {event.event_type}")
    
    async def _process_events(self):
        """处理事件队列"""
        while self.running:
            try:
                # 等待事件，设置超时避免无限等待
                event = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)
                
                # 处理事件
                handlers = self.event_handlers.get(event.event_type, [])
                for handler in handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(event)
                        else:
                            handler(event)
                    except Exception as e:
                        logger.error(f"Event handler error: {e}")
                
                event.processed = True
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Event processing error: {e}")


class PluginMonitor:
    """插件监控器"""
    
    def __init__(self):
        self.metrics: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self.health_checks: Dict[str, datetime] = {}
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.monitor_task: Optional[asyncio.Task] = None
        self.running = False
    
    async def start(self, check_interval: float = 60.0):
        """启动监控"""
        if not self.running:
            self.running = True
            self.monitor_task = asyncio.create_task(self._monitor_loop(check_interval))
            logger.info("Plugin monitor started")
    
    async def stop(self):
        """停止监控"""
        if self.running:
            self.running = False
            if self.monitor_task:
                self.monitor_task.cancel()
                try:
                    await self.monitor_task
                except asyncio.CancelledError:
                    pass
            logger.info("Plugin monitor stopped")
    
    def record_metric(self, plugin_name: str, metric_name: str, value: Any):
        """记录指标"""
        if plugin_name not in self.metrics:
            self.metrics[plugin_name] = {}
        
        self.metrics[plugin_name][metric_name] = {
            'value': value,
            'timestamp': datetime.now(),
            'type': type(value).__name__
        }
    
    def record_error(self, plugin_name: str, error: Exception):
        """记录错误"""
        self.error_counts[plugin_name] += 1
        self.record_metric(plugin_name, 'last_error', str(error))
        self.record_metric(plugin_name, 'error_count', self.error_counts[plugin_name])
    
    def get_metrics(self, plugin_name: str = None) -> Dict[str, Any]:
        """获取指标"""
        if plugin_name:
            return self.metrics.get(plugin_name, {})
        return dict(self.metrics)
    
    async def _monitor_loop(self, check_interval: float):
        """监控循环"""
        while self.running:
            try:
                await asyncio.sleep(check_interval)
                # 这里可以添加自动健康检查逻辑
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")


class PluginRegistry:
    """
    插件注册管理器
    
    核心功能：
    - 插件注册和发现
    - 依赖关系管理
    - 生命周期管理
    - 事件驱动通信
    - 配置热更新
    - 性能监控
    """
    
    _instance: Optional['PluginRegistry'] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> 'PluginRegistry':
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # 防止重复初始化
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # 插件注册表
        self.registrations: Dict[str, PluginRegistration] = {}
        self.instances: Dict[str, IAntiDetectionPlugin] = {}
        self.categories: Dict[PluginCategory, List[str]] = defaultdict(list)
        
        # 依赖和事件管理
        self.dependency_resolver = DependencyResolver()
        self.event_manager = PluginEventManager()
        self.monitor = PluginMonitor()
        
        # 状态管理
        self.registry_lock = asyncio.Lock()
        self.startup_order: List[str] = []
        self.running = False
        
        # 配置
        self.config = {
            'auto_start': True,
            'enable_monitoring': True,
            'health_check_interval': 60.0,
            'max_startup_time': 300.0,
            'enable_hot_reload': False
        }
        
        logger.info("PluginRegistry initialized")
    
    @classmethod
    def get_instance(cls) -> 'PluginRegistry':
        """获取单例实例"""
        return cls()
    
    def register_plugin(self, 
                       plugin_class: Type[IAntiDetectionPlugin],
                       plugin_name: str = None,
                       config: Dict[str, Any] = None,
                       auto_start: bool = True,
                       singleton: bool = True) -> bool:
        """
        注册插件
        
        Args:
            plugin_class: 插件类
            plugin_name: 插件名称（默认使用类名）
            config: 插件配置
            auto_start: 是否自动启动
            singleton: 是否单例模式
            
        Returns:
            bool: 注册是否成功
        """
        try:
            # 验证插件类
            if not issubclass(plugin_class, IAntiDetectionPlugin):
                raise ValueError(f"Plugin class must inherit from IAntiDetectionPlugin")
            
            # 确定插件名称
            if not plugin_name:
                plugin_name = plugin_class.__name__
            
            # 检查重复注册
            if plugin_name in self.registrations:
                logger.warning(f"Plugin {plugin_name} already registered, updating...")
            
            # 创建临时实例以获取元数据
            temp_instance = plugin_class(config or {})
            metadata = temp_instance.metadata
            metadata.plugin_id = plugin_name
            
            # 创建注册信息
            registration = PluginRegistration(
                plugin_class=plugin_class,
                metadata=metadata,
                config=config or {},
                auto_start=auto_start,
                singleton=singleton
            )
            
            # 注册插件
            self.registrations[plugin_name] = registration
            
            # 更新分类索引
            category = metadata.category
            if plugin_name not in self.categories[category]:
                self.categories[category].append(plugin_name)
            
            # 添加依赖关系
            for dependency in metadata.dependencies:
                self.dependency_resolver.add_dependency(plugin_name, dependency)
            
            logger.info(f"Plugin registered: {plugin_name} ({category.value})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register plugin {plugin_name}: {e}")
            return False
    
    def unregister_plugin(self, plugin_name: str) -> bool:
        """
        注销插件
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            bool: 注销是否成功
        """
        try:
            if plugin_name not in self.registrations:
                logger.warning(f"Plugin {plugin_name} not registered")
                return False
            
            # 检查是否可以卸载
            if not self.dependency_resolver.can_unload(plugin_name):
                dependents = self.dependency_resolver.get_dependents(plugin_name)
                raise ValueError(f"Cannot unload plugin {plugin_name}, still depended by: {dependents}")
            
            # 停止实例
            if plugin_name in self.instances:
                asyncio.create_task(self._stop_plugin_instance(plugin_name))
            
            # 清理注册信息
            registration = self.registrations[plugin_name]
            category = registration.metadata.category
            self.categories[category].remove(plugin_name)
            
            # 清理依赖关系
            for dependency in registration.metadata.dependencies:
                self.dependency_resolver.remove_dependency(plugin_name, dependency)
            
            # 移除注册
            del self.registrations[plugin_name]
            
            logger.info(f"Plugin unregistered: {plugin_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unregister plugin {plugin_name}: {e}")
            return False
    
    async def start_all_plugins(self) -> bool:
        """启动所有插件"""
        async with self.registry_lock:
            if self.running:
                logger.warning("Plugin registry already running")
                return True
            
            try:
                logger.info("Starting plugin registry...")
                
                # 启动事件管理器和监控器
                await self.event_manager.start()
                
                if self.config.get('enable_monitoring', True):
                    await self.monitor.start(self.config.get('health_check_interval', 60.0))
                
                # 解析启动顺序
                auto_start_plugins = [
                    name for name, reg in self.registrations.items() 
                    if reg.auto_start
                ]
                
                self.startup_order = self.dependency_resolver.resolve_load_order(auto_start_plugins)
                
                # 按顺序启动插件
                for plugin_name in self.startup_order:
                    success = await self._start_plugin_instance(plugin_name)
                    if not success:
                        logger.error(f"Failed to start plugin: {plugin_name}")
                        # 继续启动其他插件，而不是完全失败
                
                self.running = True
                logger.info(f"Plugin registry started with {len(self.instances)} plugins")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start plugin registry: {e}")
                await self.stop_all_plugins()
                return False
    
    async def stop_all_plugins(self) -> bool:
        """停止所有插件"""
        async with self.registry_lock:
            if not self.running:
                return True
            
            try:
                logger.info("Stopping plugin registry...")
                
                # 按反向顺序停止插件
                for plugin_name in reversed(self.startup_order):
                    await self._stop_plugin_instance(plugin_name)
                
                # 停止事件管理器和监控器
                await self.event_manager.stop()
                await self.monitor.stop()
                
                self.running = False
                logger.info("Plugin registry stopped")
                return True
                
            except Exception as e:
                logger.error(f"Failed to stop plugin registry: {e}")
                return False
    
    async def _start_plugin_instance(self, plugin_name: str) -> bool:
        """启动单个插件实例"""
        try:
            if plugin_name in self.instances:
                logger.debug(f"Plugin {plugin_name} already running")
                return True
            
            registration = self.registrations.get(plugin_name)
            if not registration:
                logger.error(f"Plugin {plugin_name} not registered")
                return False
            
            # 创建实例
            instance = registration.create_instance()
            instance.set_manager_reference(weakref.ref(self))
            
            # 初始化和启动
            if await instance.initialize():
                if await instance.start():
                    self.instances[plugin_name] = instance
                    logger.info(f"Plugin started: {plugin_name}")
                    
                    # 发送启动事件
                    await self.event_manager.emit_event(PluginEvent(
                        event_type='plugin_started',
                        source_plugin='registry',
                        data={'plugin_name': plugin_name}
                    ))
                    
                    return True
                else:
                    logger.error(f"Failed to start plugin: {plugin_name}")
            else:
                logger.error(f"Failed to initialize plugin: {plugin_name}")
            
            return False
            
        except Exception as e:
            logger.error(f"Error starting plugin {plugin_name}: {e}")
            self.monitor.record_error(plugin_name, e)
            return False
    
    async def _stop_plugin_instance(self, plugin_name: str) -> bool:
        """停止单个插件实例"""
        try:
            instance = self.instances.get(plugin_name)
            if not instance:
                return True
            
            # 停止插件
            success = await instance.stop()
            
            # 从实例列表中移除
            if plugin_name in self.instances:
                del self.instances[plugin_name]
            
            if success:
                logger.info(f"Plugin stopped: {plugin_name}")
                
                # 发送停止事件
                await self.event_manager.emit_event(PluginEvent(
                    event_type='plugin_stopped',
                    source_plugin='registry',
                    data={'plugin_name': plugin_name}
                ))
            else:
                logger.error(f"Failed to stop plugin: {plugin_name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error stopping plugin {plugin_name}: {e}")
            return False
    
    def get_plugin(self, plugin_name: str) -> Optional[IAntiDetectionPlugin]:
        """获取插件实例"""
        return self.instances.get(plugin_name)
    
    def get_plugins_by_category(self, category: PluginCategory) -> List[IAntiDetectionPlugin]:
        """按分类获取插件"""
        plugin_names = self.categories.get(category, [])
        return [self.instances[name] for name in plugin_names if name in self.instances]
    
    def get_plugin_status(self, plugin_name: str) -> Optional[PluginStatus]:
        """获取插件状态"""
        instance = self.instances.get(plugin_name)
        return instance.status if instance else None
    
    def list_plugins(self) -> Dict[str, Dict[str, Any]]:
        """列出所有插件"""
        result = {}
        for name, registration in self.registrations.items():
            instance = self.instances.get(name)
            result[name] = {
                'metadata': registration.metadata,
                'status': instance.status.value if instance else 'not_loaded',
                'config': registration.config,
                'auto_start': registration.auto_start,
                'singleton': registration.singleton
            }
        return result
    
    async def handle_plugin_event(self, event: PluginEvent):
        """处理插件事件"""
        await self.event_manager.emit_event(event)
    
    def update_plugin_config(self, plugin_name: str, config: Dict[str, Any]) -> bool:
        """更新插件配置"""
        try:
            if plugin_name in self.registrations:
                self.registrations[plugin_name].config.update(config)
            
            instance = self.instances.get(plugin_name)
            if instance:
                return instance.update_config(config)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update config for plugin {plugin_name}: {e}")
            return False
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """获取注册表统计信息"""
        return {
            'total_registered': len(self.registrations),
            'total_running': len(self.instances),
            'categories': {cat.value: len(plugins) for cat, plugins in self.categories.items()},
            'startup_order': self.startup_order,
            'running': self.running,
            'metrics': self.monitor.get_metrics()
        }


# 全局注册表实例
registry = PluginRegistry.get_instance()


# 便捷函数
def register_plugin(plugin_class: Type[IAntiDetectionPlugin], **kwargs) -> bool:
    """注册插件的便捷函数"""
    return registry.register_plugin(plugin_class, **kwargs)


def get_plugin(plugin_name: str) -> Optional[IAntiDetectionPlugin]:
    """获取插件的便捷函数"""
    return registry.get_plugin(plugin_name)


def get_plugins_by_category(category: PluginCategory) -> List[IAntiDetectionPlugin]:
    """按分类获取插件的便捷函数"""
    return registry.get_plugins_by_category(category)


async def start_registry() -> bool:
    """启动注册表的便捷函数"""
    return await registry.start_all_plugins()


async def stop_registry() -> bool:
    """停止注册表的便捷函数"""
    return await registry.stop_all_plugins()