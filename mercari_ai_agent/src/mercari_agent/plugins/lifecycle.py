"""
插件生命周期管理器

该模块实现了插件的完整生命周期管理，提供：
- 插件状态管理
- 生命周期事件处理
- 依赖关系管理
- 启动和停止序列
- 健康检查和恢复
- 状态转换监控

核心设计原则：
- 状态驱动的生命周期管理
- 自动依赖解析和启动顺序
- 故障隔离和自动恢复
- 完整的事件通知机制

Author: Mercari AI Agent Team
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict
import weakref

from .interfaces import IPlugin, PluginType, PluginCapability
from ..captcha.plugin_interface import PluginStatus, PluginEvent, PluginPriority
from ..utils.logger import get_logger

logger = get_logger(__name__)


class LifecycleState(Enum):
    """生命周期状态"""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    STARTING = "starting"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    RESUMING = "resuming"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    DESTROYED = "destroyed"


class LifecycleEvent(Enum):
    """生命周期事件"""
    BEFORE_INITIALIZE = "before_initialize"
    AFTER_INITIALIZE = "after_initialize"
    BEFORE_START = "before_start"
    AFTER_START = "after_start"
    BEFORE_PAUSE = "before_pause"
    AFTER_PAUSE = "after_pause"
    BEFORE_RESUME = "before_resume"
    AFTER_RESUME = "after_resume"
    BEFORE_STOP = "before_stop"
    AFTER_STOP = "after_stop"
    BEFORE_DESTROY = "before_destroy"
    AFTER_DESTROY = "after_destroy"
    STATE_CHANGED = "state_changed"
    ERROR_OCCURRED = "error_occurred"
    HEALTH_CHECK_FAILED = "health_check_failed"
    RECOVERY_STARTED = "recovery_started"
    RECOVERY_COMPLETED = "recovery_completed"


@dataclass
class LifecycleTransition:
    """生命周期转换"""
    plugin_id: str
    from_state: LifecycleState
    to_state: LifecycleState
    timestamp: datetime = field(default_factory=datetime.now)
    duration: float = 0.0
    success: bool = True
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.duration == 0.0:
            self.duration = 0.001  # 避免除零错误


@dataclass
class PluginLifecycleInfo:
    """插件生命周期信息"""
    plugin_id: str
    plugin_type: PluginType
    current_state: LifecycleState = LifecycleState.UNINITIALIZED
    previous_state: Optional[LifecycleState] = None
    
    # 时间戳
    creation_time: datetime = field(default_factory=datetime.now)
    last_state_change: datetime = field(default_factory=datetime.now)
    
    # 状态转换历史
    transitions: List[LifecycleTransition] = field(default_factory=list)
    
    # 依赖关系
    dependencies: Set[str] = field(default_factory=set)
    dependents: Set[str] = field(default_factory=set)
    
    # 健康状态
    health_status: str = "unknown"
    last_health_check: Optional[datetime] = None
    consecutive_failures: int = 0
    
    # 性能统计
    total_state_changes: int = 0
    average_transition_time: float = 0.0
    
    def add_transition(self, transition: LifecycleTransition):
        """添加状态转换"""
        self.transitions.append(transition)
        self.total_state_changes += 1
        
        # 更新平均转换时间
        total_time = sum(t.duration for t in self.transitions)
        self.average_transition_time = total_time / len(self.transitions)
        
        # 更新状态
        self.previous_state = self.current_state
        self.current_state = transition.to_state
        self.last_state_change = transition.timestamp
    
    def get_state_history(self, limit: int = 10) -> List[LifecycleTransition]:
        """获取状态历史"""
        return self.transitions[-limit:]
    
    def get_uptime(self) -> timedelta:
        """获取运行时间"""
        return datetime.now() - self.creation_time


@dataclass
class LifecycleConfig:
    """生命周期配置"""
    # 超时配置
    initialize_timeout: float = 30.0
    start_timeout: float = 30.0
    stop_timeout: float = 30.0
    pause_timeout: float = 10.0
    resume_timeout: float = 10.0
    
    # 健康检查配置
    health_check_interval: float = 60.0
    health_check_timeout: float = 10.0
    max_consecutive_failures: int = 3
    
    # 恢复配置
    enable_auto_recovery: bool = True
    recovery_timeout: float = 60.0
    max_recovery_attempts: int = 3
    
    # 依赖配置
    dependency_timeout: float = 300.0
    parallel_start: bool = True
    max_parallel_operations: int = 10


class PluginLifecycleManager:
    """
    插件生命周期管理器
    
    核心功能：
    1. 管理插件的完整生命周期
    2. 处理依赖关系和启动顺序
    3. 提供健康检查和自动恢复
    4. 监控状态转换和性能
    5. 事件通知和回调管理
    """
    
    def __init__(self, framework_ref: Optional[weakref.ref] = None):
        self.framework_ref = framework_ref
        self.config = LifecycleConfig()
        
        # 插件生命周期信息
        self.plugin_lifecycles: Dict[str, PluginLifecycleInfo] = {}
        self.plugin_instances: Dict[str, IPlugin] = {}
        
        # 依赖关系管理
        self.dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        
        # 状态管理
        self.state_locks: Dict[str, asyncio.Lock] = {}
        self.global_lock = asyncio.Lock()
        
        # 事件和回调
        self.lifecycle_callbacks: Dict[LifecycleEvent, List[Callable]] = defaultdict(list)
        
        # 后台任务
        self.background_tasks: List[asyncio.Task] = []
        self.running = False
        
        # 统计信息
        self.stats = {
            'total_plugins': 0,
            'active_plugins': 0,
            'failed_plugins': 0,
            'total_transitions': 0,
            'successful_transitions': 0,
            'failed_transitions': 0,
            'recovery_attempts': 0,
            'successful_recoveries': 0,
            'health_checks': 0,
            'health_check_failures': 0
        }
        
        logger.info("PluginLifecycleManager initialized")
    
    async def initialize(self):
        """初始化生命周期管理器"""
        async with self.global_lock:
            if self.running:
                return
            
            try:
                logger.info("Initializing PluginLifecycleManager...")
                
                # 启动后台任务
                self.background_tasks.append(
                    asyncio.create_task(self._health_check_loop())
                )
                
                self.background_tasks.append(
                    asyncio.create_task(self._recovery_loop())
                )
                
                self.running = True
                logger.info("PluginLifecycleManager initialized successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize PluginLifecycleManager: {e}")
                raise
    
    async def register_plugin(self, plugin: IPlugin) -> bool:
        """注册插件到生命周期管理"""
        plugin_id = plugin.plugin_config.plugin_id
        
        try:
            # 创建生命周期信息
            lifecycle_info = PluginLifecycleInfo(
                plugin_id=plugin_id,
                plugin_type=plugin.plugin_config.plugin_type,
                dependencies=set(plugin.plugin_config.dependencies)
            )
            
            # 注册插件
            self.plugin_lifecycles[plugin_id] = lifecycle_info
            self.plugin_instances[plugin_id] = plugin
            self.state_locks[plugin_id] = asyncio.Lock()
            
            # 更新依赖关系
            await self._update_dependencies(plugin_id, plugin.plugin_config.dependencies)
            
            self.stats['total_plugins'] += 1
            
            logger.info(f"Plugin {plugin_id} registered to lifecycle manager")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register plugin {plugin_id}: {e}")
            return False
    
    async def unregister_plugin(self, plugin_id: str) -> bool:
        """从生命周期管理中注销插件"""
        try:
            if plugin_id not in self.plugin_lifecycles:
                return True
            
            # 检查依赖关系
            dependents = self.reverse_dependency_graph.get(plugin_id, set())
            if dependents:
                logger.error(f"Cannot unregister plugin {plugin_id}, still depended by: {dependents}")
                return False
            
            # 停止插件
            await self.stop_plugin(plugin_id)
            
            # 清理依赖关系
            await self._cleanup_dependencies(plugin_id)
            
            # 移除注册
            del self.plugin_lifecycles[plugin_id]
            del self.plugin_instances[plugin_id]
            del self.state_locks[plugin_id]
            
            self.stats['total_plugins'] -= 1
            
            logger.info(f"Plugin {plugin_id} unregistered from lifecycle manager")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unregister plugin {plugin_id}: {e}")
            return False
    
    async def initialize_plugin(self, plugin_id: str) -> bool:
        """初始化插件"""
        return await self._transition_plugin_state(
            plugin_id,
            LifecycleState.INITIALIZED,
            self._initialize_plugin_impl
        )
    
    async def start_plugin(self, plugin_id: str) -> bool:
        """启动插件"""
        return await self._transition_plugin_state(
            plugin_id,
            LifecycleState.RUNNING,
            self._start_plugin_impl
        )
    
    async def stop_plugin(self, plugin_id: str) -> bool:
        """停止插件"""
        return await self._transition_plugin_state(
            plugin_id,
            LifecycleState.STOPPED,
            self._stop_plugin_impl
        )
    
    async def pause_plugin(self, plugin_id: str) -> bool:
        """暂停插件"""
        return await self._transition_plugin_state(
            plugin_id,
            LifecycleState.PAUSED,
            self._pause_plugin_impl
        )
    
    async def resume_plugin(self, plugin_id: str) -> bool:
        """恢复插件"""
        return await self._transition_plugin_state(
            plugin_id,
            LifecycleState.RUNNING,
            self._resume_plugin_impl
        )
    
    async def start_all_plugins(self) -> bool:
        """启动所有插件"""
        try:
            logger.info("Starting all plugins...")
            
            # 解析启动顺序
            plugin_ids = list(self.plugin_lifecycles.keys())
            start_order = self._resolve_startup_order(plugin_ids)
            
            # 按顺序启动
            for plugin_id in start_order:
                try:
                    # 先初始化
                    if not await self.initialize_plugin(plugin_id):
                        logger.error(f"Failed to initialize plugin {plugin_id}")
                        continue
                    
                    # 再启动
                    if not await self.start_plugin(plugin_id):
                        logger.error(f"Failed to start plugin {plugin_id}")
                        continue
                    
                    logger.info(f"Plugin {plugin_id} started successfully")
                    
                except Exception as e:
                    logger.error(f"Failed to start plugin {plugin_id}: {e}")
                    continue
            
            active_count = len([
                info for info in self.plugin_lifecycles.values()
                if info.current_state == LifecycleState.RUNNING
            ])
            
            logger.info(f"Started {active_count} plugins successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start all plugins: {e}")
            return False
    
    async def stop_all_plugins(self) -> bool:
        """停止所有插件"""
        try:
            logger.info("Stopping all plugins...")
            
            # 按反向顺序停止
            plugin_ids = list(self.plugin_lifecycles.keys())
            stop_order = self._resolve_shutdown_order(plugin_ids)
            
            for plugin_id in stop_order:
                try:
                    await self.stop_plugin(plugin_id)
                    logger.info(f"Plugin {plugin_id} stopped successfully")
                except Exception as e:
                    logger.error(f"Failed to stop plugin {plugin_id}: {e}")
            
            logger.info("All plugins stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop all plugins: {e}")
            return False
    
    async def _transition_plugin_state(self, 
                                     plugin_id: str,
                                     target_state: LifecycleState,
                                     implementation: Callable) -> bool:
        """执行插件状态转换"""
        if plugin_id not in self.plugin_lifecycles:
            logger.error(f"Plugin {plugin_id} not registered")
            return False
        
        lifecycle_info = self.plugin_lifecycles[plugin_id]
        plugin = self.plugin_instances[plugin_id]
        
        async with self.state_locks[plugin_id]:
            start_time = time.time()
            from_state = lifecycle_info.current_state
            
            try:
                # 检查状态转换是否有效
                if not self._is_valid_transition(from_state, target_state):
                    logger.error(f"Invalid state transition for plugin {plugin_id}: {from_state} -> {target_state}")
                    return False
                
                # 发送前置事件
                await self._emit_lifecycle_event(
                    self._get_before_event(target_state),
                    plugin_id,
                    {'from_state': from_state, 'to_state': target_state}
                )
                
                # 执行状态转换
                success = await implementation(plugin)
                
                # 记录转换
                duration = time.time() - start_time
                transition = LifecycleTransition(
                    plugin_id=plugin_id,
                    from_state=from_state,
                    to_state=target_state if success else LifecycleState.ERROR,
                    duration=duration,
                    success=success
                )
                
                lifecycle_info.add_transition(transition)
                
                # 更新统计
                self.stats['total_transitions'] += 1
                if success:
                    self.stats['successful_transitions'] += 1
                else:
                    self.stats['failed_transitions'] += 1
                
                # 发送后置事件
                await self._emit_lifecycle_event(
                    self._get_after_event(target_state),
                    plugin_id,
                    {
                        'from_state': from_state,
                        'to_state': target_state if success else LifecycleState.ERROR,
                        'success': success,
                        'duration': duration
                    }
                )
                
                # 发送状态变更事件
                await self._emit_lifecycle_event(
                    LifecycleEvent.STATE_CHANGED,
                    plugin_id,
                    {
                        'from_state': from_state,
                        'to_state': lifecycle_info.current_state,
                        'success': success
                    }
                )
                
                return success
                
            except Exception as e:
                # 记录错误转换
                duration = time.time() - start_time
                transition = LifecycleTransition(
                    plugin_id=plugin_id,
                    from_state=from_state,
                    to_state=LifecycleState.ERROR,
                    duration=duration,
                    success=False,
                    error=str(e)
                )
                
                lifecycle_info.add_transition(transition)
                
                # 更新统计
                self.stats['total_transitions'] += 1
                self.stats['failed_transitions'] += 1
                
                # 发送错误事件
                await self._emit_lifecycle_event(
                    LifecycleEvent.ERROR_OCCURRED,
                    plugin_id,
                    {
                        'error': str(e),
                        'from_state': from_state,
                        'target_state': target_state
                    }
                )
                
                logger.error(f"Plugin {plugin_id} state transition failed: {e}")
                return False
    
    async def _initialize_plugin_impl(self, plugin: IPlugin) -> bool:
        """初始化插件实现"""
        try:
            return await asyncio.wait_for(
                plugin.initialize(),
                timeout=self.config.initialize_timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Plugin {plugin.plugin_config.plugin_id} initialization timeout")
            return False
    
    async def _start_plugin_impl(self, plugin: IPlugin) -> bool:
        """启动插件实现"""
        try:
            return await asyncio.wait_for(
                plugin.start(),
                timeout=self.config.start_timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Plugin {plugin.plugin_config.plugin_id} start timeout")
            return False
    
    async def _stop_plugin_impl(self, plugin: IPlugin) -> bool:
        """停止插件实现"""
        try:
            return await asyncio.wait_for(
                plugin.stop(),
                timeout=self.config.stop_timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Plugin {plugin.plugin_config.plugin_id} stop timeout")
            return False
    
    async def _pause_plugin_impl(self, plugin: IPlugin) -> bool:
        """暂停插件实现"""
        try:
            return await asyncio.wait_for(
                plugin.pause(),
                timeout=self.config.pause_timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Plugin {plugin.plugin_config.plugin_id} pause timeout")
            return False
    
    async def _resume_plugin_impl(self, plugin: IPlugin) -> bool:
        """恢复插件实现"""
        try:
            return await asyncio.wait_for(
                plugin.resume(),
                timeout=self.config.resume_timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Plugin {plugin.plugin_config.plugin_id} resume timeout")
            return False
    
    def _is_valid_transition(self, from_state: LifecycleState, to_state: LifecycleState) -> bool:
        """检查状态转换是否有效"""
        valid_transitions = {
            LifecycleState.UNINITIALIZED: [LifecycleState.INITIALIZED],
            LifecycleState.INITIALIZED: [LifecycleState.RUNNING, LifecycleState.STOPPED],
            LifecycleState.RUNNING: [LifecycleState.PAUSED, LifecycleState.STOPPED],
            LifecycleState.PAUSED: [LifecycleState.RUNNING, LifecycleState.STOPPED],
            LifecycleState.STOPPED: [LifecycleState.INITIALIZED, LifecycleState.DESTROYED],
            LifecycleState.ERROR: [LifecycleState.INITIALIZED, LifecycleState.STOPPED]
        }
        
        return to_state in valid_transitions.get(from_state, [])
    
    def _get_before_event(self, state: LifecycleState) -> LifecycleEvent:
        """获取前置事件"""
        event_map = {
            LifecycleState.INITIALIZED: LifecycleEvent.BEFORE_INITIALIZE,
            LifecycleState.RUNNING: LifecycleEvent.BEFORE_START,
            LifecycleState.PAUSED: LifecycleEvent.BEFORE_PAUSE,
            LifecycleState.STOPPED: LifecycleEvent.BEFORE_STOP,
            LifecycleState.DESTROYED: LifecycleEvent.BEFORE_DESTROY
        }
        return event_map.get(state, LifecycleEvent.STATE_CHANGED)
    
    def _get_after_event(self, state: LifecycleState) -> LifecycleEvent:
        """获取后置事件"""
        event_map = {
            LifecycleState.INITIALIZED: LifecycleEvent.AFTER_INITIALIZE,
            LifecycleState.RUNNING: LifecycleEvent.AFTER_START,
            LifecycleState.PAUSED: LifecycleEvent.AFTER_PAUSE,
            LifecycleState.STOPPED: LifecycleEvent.AFTER_STOP,
            LifecycleState.DESTROYED: LifecycleEvent.AFTER_DESTROY
        }
        return event_map.get(state, LifecycleEvent.STATE_CHANGED)
    
    async def _update_dependencies(self, plugin_id: str, dependencies: List[str]):
        """更新依赖关系"""
        for dependency in dependencies:
            self.dependency_graph[plugin_id].add(dependency)
            self.reverse_dependency_graph[dependency].add(plugin_id)
    
    async def _cleanup_dependencies(self, plugin_id: str):
        """清理依赖关系"""
        # 清理该插件的依赖
        for dependency in self.dependency_graph[plugin_id]:
            self.reverse_dependency_graph[dependency].discard(plugin_id)
        
        # 清理依赖该插件的关系
        for dependent in self.reverse_dependency_graph[plugin_id]:
            self.dependency_graph[dependent].discard(plugin_id)
        
        # 清理映射
        del self.dependency_graph[plugin_id]
        del self.reverse_dependency_graph[plugin_id]
    
    def _resolve_startup_order(self, plugin_ids: List[str]) -> List[str]:
        """解析启动顺序"""
        # 简单的拓扑排序
        visited = set()
        visiting = set()
        result = []
        
        def visit(plugin_id: str):
            if plugin_id in visiting:
                raise ValueError(f"Circular dependency detected: {plugin_id}")
            
            if plugin_id in visited:
                return
            
            visiting.add(plugin_id)
            
            # 先访问依赖
            for dependency in self.dependency_graph[plugin_id]:
                if dependency in plugin_ids:
                    visit(dependency)
            
            visiting.remove(plugin_id)
            visited.add(plugin_id)
            result.append(plugin_id)
        
        for plugin_id in plugin_ids:
            if plugin_id not in visited:
                visit(plugin_id)
        
        return result
    
    def _resolve_shutdown_order(self, plugin_ids: List[str]) -> List[str]:
        """解析关闭顺序（启动顺序的反向）"""
        startup_order = self._resolve_startup_order(plugin_ids)
        return list(reversed(startup_order))
    
    async def _emit_lifecycle_event(self, event_type: LifecycleEvent, 
                                  plugin_id: str, data: Dict[str, Any]):
        """发送生命周期事件"""
        callbacks = self.lifecycle_callbacks.get(event_type, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(plugin_id, data)
                else:
                    callback(plugin_id, data)
            except Exception as e:
                logger.error(f"Lifecycle callback error: {e}")
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while self.running:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._perform_health_checks()
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
    
    async def _perform_health_checks(self):
        """执行健康检查"""
        for plugin_id, plugin in self.plugin_instances.items():
            try:
                lifecycle_info = self.plugin_lifecycles[plugin_id]
                
                # 只检查运行中的插件
                if lifecycle_info.current_state != LifecycleState.RUNNING:
                    continue
                
                # 执行健康检查
                health_result = await asyncio.wait_for(
                    plugin.healthcheck(),
                    timeout=self.config.health_check_timeout
                )
                
                is_healthy = health_result.get('healthy', False)
                lifecycle_info.health_status = 'healthy' if is_healthy else 'unhealthy'
                lifecycle_info.last_health_check = datetime.now()
                
                if not is_healthy:
                    lifecycle_info.consecutive_failures += 1
                    
                    # 发送健康检查失败事件
                    await self._emit_lifecycle_event(
                        LifecycleEvent.HEALTH_CHECK_FAILED,
                        plugin_id,
                        {
                            'consecutive_failures': lifecycle_info.consecutive_failures,
                            'health_result': health_result
                        }
                    )
                    
                    self.stats['health_check_failures'] += 1
                else:
                    lifecycle_info.consecutive_failures = 0
                
                self.stats['health_checks'] += 1
                
            except Exception as e:
                logger.error(f"Health check failed for plugin {plugin_id}: {e}")
                lifecycle_info.consecutive_failures += 1
                lifecycle_info.health_status = 'error'
                self.stats['health_check_failures'] += 1
    
    async def _recovery_loop(self):
        """恢复循环"""
        while self.running:
            try:
                await asyncio.sleep(30.0)  # 每30秒检查一次
                await self._attempt_recovery()
            except Exception as e:
                logger.error(f"Recovery loop error: {e}")
    
    async def _attempt_recovery(self):
        """尝试恢复失败的插件"""
        if not self.config.enable_auto_recovery:
            return
        
        for plugin_id, lifecycle_info in self.plugin_lifecycles.items():
            # 检查是否需要恢复
            if (lifecycle_info.consecutive_failures >= self.config.max_consecutive_failures and
                lifecycle_info.current_state in [LifecycleState.ERROR, LifecycleState.STOPPED]):
                
                try:
                    logger.info(f"Attempting recovery for plugin {plugin_id}")
                    self.stats['recovery_attempts'] += 1
                    
                    # 发送恢复开始事件
                    await self._emit_lifecycle_event(
                        LifecycleEvent.RECOVERY_STARTED,
                        plugin_id,
                        {'consecutive_failures': lifecycle_info.consecutive_failures}
                    )
                    
                    # 尝试重新启动
                    recovery_success = False
                    if await self.initialize_plugin(plugin_id):
                        if await self.start_plugin(plugin_id):
                            recovery_success = True
                    
                    if recovery_success:
                        lifecycle_info.consecutive_failures = 0
                        self.stats['successful_recoveries'] += 1
                        
                        # 发送恢复完成事件
                        await self._emit_lifecycle_event(
                            LifecycleEvent.RECOVERY_COMPLETED,
                            plugin_id,
                            {'success': True}
                        )
                        
                        logger.info(f"Plugin {plugin_id} recovered successfully")
                    else:
                        # 发送恢复失败事件
                        await self._emit_lifecycle_event(
                            LifecycleEvent.RECOVERY_COMPLETED,
                            plugin_id,
                            {'success': False}
                        )
                        
                        logger.error(f"Failed to recover plugin {plugin_id}")
                
                except Exception as e:
                    logger.error(f"Recovery attempt failed for plugin {plugin_id}: {e}")
    
    def register_lifecycle_callback(self, event_type: LifecycleEvent, callback: Callable):
        """注册生命周期回调"""
        self.lifecycle_callbacks[event_type].append(callback)
    
    def unregister_lifecycle_callback(self, event_type: LifecycleEvent, callback: Callable):
        """注销生命周期回调"""
        if callback in self.lifecycle_callbacks[event_type]:
            self.lifecycle_callbacks[event_type].remove(callback)
    
    def get_plugin_lifecycle_info(self, plugin_id: str) -> Optional[PluginLifecycleInfo]:
        """获取插件生命周期信息"""
        return self.plugin_lifecycles.get(plugin_id)
    
    def get_all_plugin_states(self) -> Dict[str, LifecycleState]:
        """获取所有插件状态"""
        return {
            plugin_id: info.current_state
            for plugin_id, info in self.plugin_lifecycles.items()
        }
    
    def get_lifecycle_stats(self) -> Dict[str, Any]:
        """获取生命周期统计信息"""
        return {
            'total_plugins': self.stats['total_plugins'],
            'active_plugins': len([
                info for info in self.plugin_lifecycles.values()
                if info.current_state == LifecycleState.RUNNING
            ]),
            'failed_plugins': len([
                info for info in self.plugin_lifecycles.values()
                if info.current_state == LifecycleState.ERROR
            ]),
            'total_transitions': self.stats['total_transitions'],
            'successful_transitions': self.stats['successful_transitions'],
            'failed_transitions': self.stats['failed_transitions'],
            'recovery_attempts': self.stats['recovery_attempts'],
            'successful_recoveries': self.stats['successful_recoveries'],
            'health_checks': self.stats['health_checks'],
            'health_check_failures': self.stats['health_check_failures'],
            'plugin_states': self.get_all_plugin_states()
        }
    
    async def stop(self):
        """停止生命周期管理器"""
        async with self.global_lock:
            if not self.running:
                return
            
            try:
                logger.info("Stopping PluginLifecycleManager...")
                
                # 停止所有插件
                await self.stop_all_plugins()
                
                # 停止后台任务
                for task in self.background_tasks:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                
                self.background_tasks.clear()
                self.running = False
                
                logger.info("PluginLifecycleManager stopped")
                
            except Exception as e:
                logger.error(f"Failed to stop PluginLifecycleManager: {e}")
                raise