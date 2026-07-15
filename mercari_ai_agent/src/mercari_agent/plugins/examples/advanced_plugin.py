"""
高级插件示例

该示例展示了高级插件开发模式，包括：
1. 依赖注入和服务管理
2. 事件系统集成
3. 缓存和状态管理
4. 资源池管理
5. 指标收集和监控
6. 高级配置模式
7. 异步任务调度

Author: Mercari AI Agent Team
"""

import asyncio
import logging
import time
import weakref
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable, TypeVar, Generic, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import json

from mercari_agent.plugins.interfaces import (
    IPlugin, PluginType, PluginState, PluginCapability, PluginMetadata
)


# 事件系统
class EventType(Enum):
    """事件类型枚举"""
    PLUGIN_STARTED = "plugin.started"
    PLUGIN_STOPPED = "plugin.stopped"
    PLUGIN_ERROR = "plugin.error"
    DATA_PROCESSED = "data.processed"
    RESOURCE_ALLOCATED = "resource.allocated"
    RESOURCE_RELEASED = "resource.released"
    METRIC_UPDATED = "metric.updated"


@dataclass
class PluginEvent:
    """插件事件数据结构"""
    event_type: EventType
    plugin_id: str
    timestamp: datetime
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class EventHandler(ABC):
    """事件处理器抽象基类"""
    
    @abstractmethod
    async def handle_event(self, event: PluginEvent) -> bool:
        """处理事件
        
        Args:
            event: 事件对象
            
        Returns:
            bool: 是否处理成功
        """
        pass


class EventBus:
    """事件总线"""
    
    def __init__(self):
        self._handlers: Dict[EventType, List[EventHandler]] = defaultdict(list)
        self._event_queue: deque = deque()
        self._processing = False
        self.logger = logging.getLogger("event_bus")
    
    def subscribe(self, event_type: EventType, handler: EventHandler):
        """订阅事件"""
        self._handlers[event_type].append(handler)
        self.logger.debug(f"已订阅事件 {event_type.value}: {handler.__class__.__name__}")
    
    def unsubscribe(self, event_type: EventType, handler: EventHandler):
        """取消订阅事件"""
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
            self.logger.debug(f"已取消订阅事件 {event_type.value}: {handler.__class__.__name__}")
    
    async def emit(self, event: PluginEvent):
        """发出事件"""
        self._event_queue.append(event)
        if not self._processing:
            await self._process_events()
    
    async def _process_events(self):
        """处理事件队列"""
        self._processing = True
        try:
            while self._event_queue:
                event = self._event_queue.popleft()
                handlers = self._handlers.get(event.event_type, [])
                
                # 并发处理所有处理器
                tasks = []
                for handler in handlers:
                    task = asyncio.create_task(self._safe_handle_event(handler, event))
                    tasks.append(task)
                
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            self._processing = False
    
    async def _safe_handle_event(self, handler: EventHandler, event: PluginEvent):
        """安全地处理事件"""
        try:
            await handler.handle_event(event)
        except Exception as e:
            self.logger.error(f"事件处理器 {handler.__class__.__name__} 处理事件 {event.event_type.value} 时异常: {e}")


# 资源管理
T = TypeVar('T')


class ResourcePool(Generic[T]):
    """资源池管理器"""
    
    def __init__(self, factory: Callable[[], T], max_size: int = 10, 
                 cleanup_func: Optional[Callable[[T], None]] = None):
        self.factory = factory
        self.max_size = max_size
        self.cleanup_func = cleanup_func
        self._pool: List[T] = []
        self._in_use: set = set()
        self._lock = asyncio.Lock()
        self.logger = logging.getLogger("resource_pool")
    
    async def acquire(self) -> T:
        """获取资源"""
        async with self._lock:
            if self._pool:
                resource = self._pool.pop()
            else:
                resource = self.factory()
            
            self._in_use.add(id(resource))
            self.logger.debug(f"已分配资源，池大小: {len(self._pool)}, 使用中: {len(self._in_use)}")
            return resource
    
    async def release(self, resource: T):
        """释放资源"""
        async with self._lock:
            resource_id = id(resource)
            if resource_id not in self._in_use:
                return
            
            self._in_use.remove(resource_id)
            
            if len(self._pool) < self.max_size:
                self._pool.append(resource)
            else:
                # 超出池大小限制，清理资源
                if self.cleanup_func:
                    self.cleanup_func(resource)
            
            self.logger.debug(f"已释放资源，池大小: {len(self._pool)}, 使用中: {len(self._in_use)}")
    
    async def cleanup_all(self):
        """清理所有资源"""
        async with self._lock:
            if self.cleanup_func:
                for resource in self._pool:
                    self.cleanup_func(resource)
            self._pool.clear()
            self._in_use.clear()


# 缓存管理
@dataclass
class CacheEntry:
    """缓存条目"""
    value: Any
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    ttl: Optional[timedelta] = None
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.ttl is None:
            return False
        return datetime.now() - self.created_at > self.ttl
    
    def access(self):
        """访问缓存项"""
        self.last_accessed = datetime.now()
        self.access_count += 1


class LRUCache:
    """LRU缓存实现"""
    
    def __init__(self, max_size: int = 100, default_ttl: Optional[timedelta] = None):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._access_order: deque = deque()
        self._lock = asyncio.Lock()
        self.logger = logging.getLogger("lru_cache")
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            
            if entry.is_expired():
                await self._remove_key(key)
                return None
            
            # 更新访问信息
            entry.access()
            
            # 更新访问顺序
            self._access_order.remove(key)
            self._access_order.append(key)
            
            return entry.value
    
    async def set(self, key: str, value: Any, ttl: Optional[timedelta] = None):
        """设置缓存值"""
        async with self._lock:
            now = datetime.now()
            entry = CacheEntry(
                value=value,
                created_at=now,
                last_accessed=now,
                ttl=ttl or self.default_ttl
            )
            
            # 如果键已存在，更新位置
            if key in self._cache:
                self._access_order.remove(key)
            
            self._cache[key] = entry
            self._access_order.append(key)
            
            # 检查大小限制
            while len(self._cache) > self.max_size:
                oldest_key = self._access_order.popleft()
                del self._cache[oldest_key]
    
    async def delete(self, key: str) -> bool:
        """删除缓存项"""
        async with self._lock:
            return await self._remove_key(key)
    
    async def clear(self):
        """清空缓存"""
        async with self._lock:
            self._cache.clear()
            self._access_order.clear()
    
    async def _remove_key(self, key: str) -> bool:
        """删除键"""
        if key in self._cache:
            del self._cache[key]
            self._access_order.remove(key)
            return True
        return False
    
    def stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hit_rate": self._calculate_hit_rate(),
            "memory_usage": self._estimate_memory_usage()
        }
    
    def _calculate_hit_rate(self) -> float:
        """计算命中率"""
        total_accesses = sum(entry.access_count for entry in self._cache.values())
        if total_accesses == 0:
            return 0.0
        return len(self._cache) / total_accesses
    
    def _estimate_memory_usage(self) -> int:
        """估算内存使用量"""
        try:
            import sys
            total_size = 0
            for key, entry in self._cache.items():
                total_size += sys.getsizeof(key)
                total_size += sys.getsizeof(entry.value)
            return total_size
        except:
            return -1  # 无法计算


# 指标收集
@dataclass
class Metric:
    """指标数据"""
    name: str
    value: Union[int, float]
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self):
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._timings: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self.logger = logging.getLogger("metrics")
    
    async def increment_counter(self, name: str, value: int = 1):
        """增加计数器"""
        async with self._lock:
            self._counters[name] += value
    
    async def set_gauge(self, name: str, value: float):
        """设置测量值"""
        async with self._lock:
            self._gauges[name] = value
    
    async def record_histogram(self, name: str, value: float):
        """记录直方图值"""
        async with self._lock:
            self._histograms[name].append(value)
            # 限制历史数据大小
            if len(self._histograms[name]) > 1000:
                self._histograms[name] = self._histograms[name][-500:]
    
    async def record_timing(self, name: str, duration: float):
        """记录时间度量"""
        await self.record_histogram(f"{name}_duration", duration)
    
    async def get_metrics(self) -> Dict[str, Any]:
        """获取所有指标"""
        async with self._lock:
            metrics = {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {},
                "timings": {}
            }
            
            # 计算直方图统计
            for name, values in self._histograms.items():
                if values:
                    metrics["histograms"][name] = {
                        "count": len(values),
                        "min": min(values),
                        "max": max(values),
                        "avg": sum(values) / len(values),
                        "p50": self._percentile(values, 0.5),
                        "p95": self._percentile(values, 0.95),
                        "p99": self._percentile(values, 0.99)
                    }
            
            return metrics
    
    def _percentile(self, values: List[float], p: float) -> float:
        """计算百分位数"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * p)
        return sorted_values[min(index, len(sorted_values) - 1)]


# 任务调度器
class TaskScheduler:
    """异步任务调度器"""
    
    def __init__(self):
        self._tasks: Dict[str, asyncio.Task] = {}
        self._intervals: Dict[str, float] = {}
        self._running = False
        self.logger = logging.getLogger("task_scheduler")
    
    def schedule_interval(self, name: str, coro: Callable, interval: float):
        """调度定时任务"""
        self._intervals[name] = interval
        self.logger.info(f"已调度定时任务 {name}，间隔: {interval}秒")
    
    def schedule_once(self, name: str, coro: Callable, delay: float = 0):
        """调度一次性任务"""
        async def delayed_task():
            if delay > 0:
                await asyncio.sleep(delay)
            await coro()
        
        task = asyncio.create_task(delayed_task())
        self._tasks[name] = task
        self.logger.info(f"已调度一次性任务 {name}，延迟: {delay}秒")
    
    async def start(self):
        """启动调度器"""
        if self._running:
            return
        
        self._running = True
        self.logger.info("任务调度器已启动")
        
        # 启动定时任务
        for name, interval in self._intervals.items():
            task = asyncio.create_task(self._run_interval_task(name, interval))
            self._tasks[f"{name}_interval"] = task
    
    async def stop(self):
        """停止调度器"""
        if not self._running:
            return
        
        self._running = False
        self.logger.info("正在停止任务调度器")
        
        # 取消所有任务
        for name, task in self._tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        self._tasks.clear()
        self.logger.info("任务调度器已停止")
    
    async def _run_interval_task(self, name: str, interval: float):
        """运行定时任务"""
        while self._running:
            try:
                await asyncio.sleep(interval)
                if not self._running:
                    break
                # 这里应该调用实际的任务函数
                self.logger.debug(f"执行定时任务: {name}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"定时任务 {name} 执行异常: {e}")


# 高级插件实现
class AdvancedExamplePlugin(IPlugin, EventHandler):
    """高级示例插件
    
    展示了高级插件开发模式，包括依赖注入、事件处理、
    资源管理、缓存、指标收集等功能。
    """
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        """初始化高级插件"""
        # 基础属性
        self.plugin_id = "advanced_example_plugin"
        self.plugin_type = PluginType.BEHAVIOR_SIMULATION
        self.state = PluginState.INACTIVE
        self.config = {}
        
        # 插件元数据
        self.metadata = PluginMetadata(
            plugin_id=self.plugin_id,
            name="高级示例插件",
            version="2.0.0",
            description="展示高级插件开发模式的综合示例",
            author="Mercari AI Agent Team",
            homepage="https://example.com/plugins/advanced",
            plugin_type=self.plugin_type,
            capabilities=[
                PluginCapability.CONFIGURABLE,
                PluginCapability.MONITORABLE,
                PluginCapability.HOT_RELOADABLE,
                PluginCapability.DEPENDENCY_INJECTION,
                PluginCapability.EVENT_DRIVEN,
                PluginCapability.RESOURCE_POOLING,
                PluginCapability.CACHING
            ],
            supported_platforms=["windows", "linux", "macos"],
            min_framework_version="2.0.0",
            dependencies=["requests", "aiohttp"]
        )
        
        # 高级组件
        self.event_bus = event_bus or EventBus()
        self.cache = LRUCache(max_size=200, default_ttl=timedelta(minutes=30))
        self.metrics = MetricsCollector()
        self.scheduler = TaskScheduler()
        
        # 资源池
        self.connection_pool: Optional[ResourcePool] = None
        
        # 内部状态
        self._services: Dict[str, Any] = {}
        self._weak_refs: Dict[str, Any] = {}
        self._performance_stats = {
            "requests_processed": 0,
            "errors_count": 0,
            "avg_response_time": 0.0,
            "cache_hit_rate": 0.0
        }
        
        # 日志记录
        self.logger = logging.getLogger(f"plugin.{self.plugin_id}")
        self.logger.info(f"高级插件 {self.plugin_id} 创建完成")
        
        # 订阅事件
        self.event_bus.subscribe(EventType.DATA_PROCESSED, self)
        self.event_bus.subscribe(EventType.PLUGIN_ERROR, self)
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """初始化插件"""
        try:
            self.logger.info(f"正在初始化高级插件 {self.plugin_id}")
            
            # 更新配置
            if config:
                self.config.update(config)
            
            # 设置默认配置
            self._set_default_config()
            
            # 验证配置
            if not await self._validate_advanced_config():
                return False
            
            # 初始化服务
            await self._initialize_services()
            
            # 初始化资源池
            await self._initialize_resource_pools()
            
            # 启动指标收集
            await self._start_metrics_collection()
            
            # 调度定期任务
            self.scheduler.schedule_interval("health_check", self._periodic_health_check, 30.0)
            self.scheduler.schedule_interval("metrics_update", self._update_metrics, 10.0)
            self.scheduler.schedule_interval("cache_cleanup", self._cleanup_cache, 300.0)
            
            self.state = PluginState.READY
            await self._emit_event(EventType.PLUGIN_STARTED, {"initialization": "success"})
            
            self.logger.info(f"高级插件 {self.plugin_id} 初始化成功")
            return True
            
        except Exception as e:
            self.logger.error(f"高级插件初始化失败: {e}", exc_info=True)
            await self._emit_event(EventType.PLUGIN_ERROR, {"error": str(e), "phase": "initialization"})
            self.state = PluginState.INACTIVE
            return False
    
    async def start(self) -> bool:
        """启动插件"""
        try:
            if self.state != PluginState.READY:
                self.logger.error("插件未就绪，无法启动")
                return False
            
            if not self.config.get('enabled', True):
                self.logger.info("插件已禁用，跳过启动")
                return True
            
            self.logger.info(f"正在启动高级插件 {self.plugin_id}")
            
            # 启动任务调度器
            await self.scheduler.start()
            
            # 启动服务
            await self._start_services()
            
            # 预热缓存
            await self._warm_cache()
            
            self.state = PluginState.ACTIVE
            await self._emit_event(EventType.PLUGIN_STARTED, {"startup": "success"})
            
            self.logger.info(f"高级插件 {self.plugin_id} 启动成功")
            return True
            
        except Exception as e:
            self.logger.error(f"高级插件启动失败: {e}", exc_info=True)
            await self._emit_event(EventType.PLUGIN_ERROR, {"error": str(e), "phase": "startup"})
            self.state = PluginState.INACTIVE
            return False
    
    async def stop(self) -> bool:
        """停止插件"""
        try:
            if self.state != PluginState.ACTIVE:
                self.logger.info("插件未激活，无需停止")
                return True
            
            self.logger.info(f"正在停止高级插件 {self.plugin_id}")
            
            # 停止任务调度器
            await self.scheduler.stop()
            
            # 停止服务
            await self._stop_services()
            
            self.state = PluginState.INACTIVE
            await self._emit_event(EventType.PLUGIN_STOPPED, {"shutdown": "success"})
            
            self.logger.info(f"高级插件 {self.plugin_id} 停止成功")
            return True
            
        except Exception as e:
            self.logger.error(f"高级插件停止失败: {e}", exc_info=True)
            await self._emit_event(EventType.PLUGIN_ERROR, {"error": str(e), "phase": "shutdown"})
            return False
    
    async def cleanup(self) -> bool:
        """清理插件资源"""
        try:
            self.logger.info(f"正在清理高级插件 {self.plugin_id}")
            
            # 确保插件已停止
            if self.state == PluginState.ACTIVE:
                await self.stop()
            
            # 清理资源池
            if self.connection_pool:
                await self.connection_pool.cleanup_all()
            
            # 清理缓存
            await self.cache.clear()
            
            # 清理服务
            await self._cleanup_services()
            
            # 取消事件订阅
            self.event_bus.unsubscribe(EventType.DATA_PROCESSED, self)
            self.event_bus.unsubscribe(EventType.PLUGIN_ERROR, self)
            
            self.state = PluginState.UNLOADED
            self.logger.info(f"高级插件 {self.plugin_id} 清理完成")
            
            return True
            
        except Exception as e:
            self.logger.error(f"高级插件清理失败: {e}", exc_info=True)
            return False
    
    async def handle_event(self, event: PluginEvent) -> bool:
        """处理事件"""
        try:
            if event.event_type == EventType.DATA_PROCESSED:
                await self._handle_data_processed_event(event)
            elif event.event_type == EventType.PLUGIN_ERROR:
                await self._handle_error_event(event)
            return True
        except Exception as e:
            self.logger.error(f"事件处理失败: {e}")
            return False
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            # 基础检查
            if self.state not in [PluginState.READY, PluginState.ACTIVE]:
                return False
            
            # 服务健康检查
            for name, service in self._services.items():
                if hasattr(service, 'health_check'):
                    if not await service.health_check():
                        self.logger.warning(f"服务 {name} 健康检查失败")
                        return False
            
            # 资源池检查
            if self.connection_pool and len(self.connection_pool._in_use) > 50:
                self.logger.warning("资源池使用率过高")
                return False
            
            # 性能指标检查
            error_rate = self._performance_stats["errors_count"] / max(self._performance_stats["requests_processed"], 1)
            if error_rate > 0.1:  # 错误率超过10%
                self.logger.warning(f"错误率过高: {error_rate:.2%}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"健康检查异常: {e}")
            return False
    
    async def get_status(self) -> Dict[str, Any]:
        """获取插件状态"""
        try:
            metrics = await self.metrics.get_metrics()
            cache_stats = self.cache.stats()
            
            return {
                "plugin_id": self.plugin_id,
                "plugin_type": self.plugin_type.value,
                "state": self.state.value,
                "healthy": await self.health_check(),
                "performance": self._performance_stats.copy(),
                "metrics": metrics,
                "cache": cache_stats,
                "services": list(self._services.keys()),
                "resource_pools": {
                    "connections": {
                        "size": len(self.connection_pool._pool) if self.connection_pool else 0,
                        "in_use": len(self.connection_pool._in_use) if self.connection_pool else 0
                    }
                },
                "config": self.config.copy(),
                "metadata": {
                    "name": self.metadata.name,
                    "version": self.metadata.version,
                    "capabilities": [cap.value for cap in self.metadata.capabilities]
                }
            }
            
        except Exception as e:
            self.logger.error(f"获取状态失败: {e}")
            return {"plugin_id": self.plugin_id, "state": "error", "error": str(e)}
    
    # 依赖注入
    def inject_service(self, name: str, service: Any, weak_ref: bool = False):
        """注入服务依赖"""
        if weak_ref:
            self._weak_refs[name] = weakref.ref(service)
        else:
            self._services[name] = service
        self.logger.info(f"已注入服务: {name}")
    
    def get_service(self, name: str) -> Optional[Any]:
        """获取注入的服务"""
        # 优先从强引用中获取
        if name in self._services:
            return self._services[name]
        
        # 从弱引用中获取
        if name in self._weak_refs:
            ref = self._weak_refs[name]
            service = ref()
            if service is not None:
                return service
            else:
                # 弱引用已失效，清理
                del self._weak_refs[name]
        
        return None
    
    # 内部辅助方法
    
    def _set_default_config(self):
        """设置默认配置"""
        defaults = {
            "enabled": True,
            "timeout": 30.0,
            "max_connections": 20,
            "cache_size": 200,
            "cache_ttl": 1800,  # 30分钟
            "metrics_interval": 10,
            "health_check_interval": 30,
            "performance_monitoring": True,
            "debug": False
        }
        
        for key, value in defaults.items():
            if key not in self.config:
                self.config[key] = value
    
    async def _validate_advanced_config(self) -> bool:
        """验证高级配置"""
        try:
            required_keys = ["enabled", "timeout", "max_connections", "cache_size"]
            for key in required_keys:
                if key not in self.config:
                    self.logger.error(f"缺少必需的配置项: {key}")
                    return False
            
            # 类型和范围检查
            if not isinstance(self.config["max_connections"], int) or self.config["max_connections"] <= 0:
                self.logger.error("max_connections 必须是正整数")
                return False
            
            if not isinstance(self.config["cache_size"], int) or self.config["cache_size"] <= 0:
                self.logger.error("cache_size 必须是正整数")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"配置验证异常: {e}")
            return False
    
    async def _initialize_services(self):
        """初始化服务"""
        # 这里可以初始化各种服务，如HTTP客户端、数据库连接等
        self.logger.debug("初始化服务组件")
    
    async def _initialize_resource_pools(self):
        """初始化资源池"""
        # 创建连接池
        def create_connection():
            # 模拟创建连接对象
            return {"id": id({}), "created_at": datetime.now()}
        
        def cleanup_connection(conn):
            # 模拟清理连接
            pass
        
        self.connection_pool = ResourcePool(
            factory=create_connection,
            max_size=self.config["max_connections"],
            cleanup_func=cleanup_connection
        )
        
        self.logger.info(f"已初始化连接池，最大连接数: {self.config['max_connections']}")
    
    async def _start_metrics_collection(self):
        """启动指标收集"""
        await self.metrics.set_gauge("plugin.initialized", 1)
        await self.metrics.increment_counter("plugin.initializations")
    
    async def _start_services(self):
        """启动服务"""
        self.logger.debug("启动服务组件")
    
    async def _stop_services(self):
        """停止服务"""
        self.logger.debug("停止服务组件")
    
    async def _cleanup_services(self):
        """清理服务"""
        self._services.clear()
        self._weak_refs.clear()
        self.logger.debug("已清理服务组件")
    
    async def _warm_cache(self):
        """预热缓存"""
        # 预加载一些常用数据到缓存
        await self.cache.set("plugin_start_time", datetime.now().isoformat())
        self.logger.debug("缓存预热完成")
    
    async def _emit_event(self, event_type: EventType, data: Dict[str, Any]):
        """发出事件"""
        event = PluginEvent(
            event_type=event_type,
            plugin_id=self.plugin_id,
            timestamp=datetime.now(),
            data=data
        )
        await self.event_bus.emit(event)
    
    async def _handle_data_processed_event(self, event: PluginEvent):
        """处理数据处理事件"""
        await self.metrics.increment_counter("data.processed")
        self._performance_stats["requests_processed"] += 1
    
    async def _handle_error_event(self, event: PluginEvent):
        """处理错误事件"""
        await self.metrics.increment_counter("plugin.errors")
        self._performance_stats["errors_count"] += 1
    
    async def _periodic_health_check(self):
        """定期健康检查"""
        healthy = await self.health_check()
        await self.metrics.set_gauge("plugin.healthy", 1 if healthy else 0)
    
    async def _update_metrics(self):
        """更新指标"""
        # 更新缓存命中率
        cache_stats = self.cache.stats()
        self._performance_stats["cache_hit_rate"] = cache_stats.get("hit_rate", 0.0)
        await self.metrics.set_gauge("cache.hit_rate", self._performance_stats["cache_hit_rate"])
        
        # 更新响应时间（模拟）
        import random
        response_time = random.uniform(0.1, 2.0)
        await self.metrics.record_timing("request.processing", response_time)
        self._performance_stats["avg_response_time"] = response_time
    
    async def _cleanup_cache(self):
        """清理过期缓存"""
        # 缓存会自动处理过期，这里可以执行额外的清理逻辑
        self.logger.debug("执行缓存清理")


# 演示使用
async def demo_advanced_plugin():
    """演示高级插件的使用"""
    print("=== 高级插件演示 ===")
    
    # 创建事件总线
    event_bus = EventBus()
    
    # 创建插件实例
    plugin = AdvancedExamplePlugin(event_bus)
    print(f"创建高级插件: {plugin.plugin_id}")
    
    # 注入依赖服务
    mock_service = {"name": "MockService", "version": "1.0"}
    plugin.inject_service("mock_service", mock_service)
    
    # 高级配置
    config = {
        "enabled": True,
        "timeout": 60.0,
        "max_connections": 50,
        "cache_size": 500,
        "cache_ttl": 3600,
        "performance_monitoring": True,
        "debug": True
    }
    
    try:
        # 初始化
        print("\n1. 初始化高级插件...")
        success = await plugin.initialize(config)
        print(f"初始化结果: {success}")
        
        # 启动
        print("\n2. 启动高级插件...")
        success = await plugin.start()
        print(f"启动结果: {success}")
        
        # 模拟一些活动
        print("\n3. 模拟插件活动...")
        
        # 触发事件
        await event_bus.emit(PluginEvent(
            event_type=EventType.DATA_PROCESSED,
            plugin_id=plugin.plugin_id,
            timestamp=datetime.now(),
            data={"processed_items": 100}
        ))
        
        # 使用缓存
        await plugin.cache.set("test_data", {"value": 42, "name": "test"})
        cached_value = await plugin.cache.get("test_data")
        print(f"缓存测试: {cached_value}")
        
        # 使用资源池
        if plugin.connection_pool:
            connection = await plugin.connection_pool.acquire()
            print(f"获取连接: {connection}")
            await plugin.connection_pool.release(connection)
        
        # 等待一段时间让定时任务执行
        print("\n4. 等待定时任务执行...")
        await asyncio.sleep(2)
        
        # 获取详细状态
        print("\n5. 获取插件状态...")
        status = await plugin.get_status()
        print(f"插件状态: {json.dumps(status, indent=2, default=str)}")
        
        # 健康检查
        print("\n6. 执行健康检查...")
        healthy = await plugin.health_check()
        print(f"健康状态: {healthy}")
        
        # 停止
        print("\n7. 停止高级插件...")
        success = await plugin.stop()
        print(f"停止结果: {success}")
        
        # 清理
        print("\n8. 清理高级插件...")
        success = await plugin.cleanup()
        print(f"清理结果: {success}")
        
    except Exception as e:
        print(f"演示过程中发生错误: {e}")
        await plugin.cleanup()
    
    print("\n=== 高级插件演示完成 ===")


if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 运行演示
    asyncio.run(demo_advanced_plugin())