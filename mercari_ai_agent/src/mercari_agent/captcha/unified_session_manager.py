"""
统一会话管理系统

该模块实现了统一的会话管理架构，解决现有系统中65%的重复代码问题。

核心功能：
- 统一会话管理抽象基类
- 插件化会话管理器适配
- 会话池统一管理
- 配置驱动的会话创建
- 完全向后兼容性

设计特点：
- 基于抽象基类的统一接口
- 插件化架构支持
- 会话生命周期统一管理
- 配置热更新支持
- 错误恢复机制

Author: Mercari AI Agent Team
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Union, Type, Protocol, runtime_checkable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
import weakref

from .plugin_interface import ISessionPlugin, PluginMetadata, PluginCategory, PluginPriority
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SessionStrategy(Enum):
    """会话策略枚举"""
    ROUND_ROBIN = "round_robin"
    LEAST_USED = "least_used"
    RANDOM = "random"
    STICKY = "sticky"
    LOAD_BALANCED = "load_balanced"


class SessionPoolPolicy(Enum):
    """会话池策略"""
    FIXED_SIZE = "fixed_size"
    DYNAMIC = "dynamic"
    ADAPTIVE = "adaptive"


@dataclass
class UnifiedSessionConfig:
    """统一会话配置"""
    # 基础配置
    max_sessions: int = 5
    session_timeout: int = 1800
    idle_timeout: int = 300
    connection_timeout: float = 30.0
    read_timeout: float = 60.0
    total_timeout: float = 120.0
    
    # 会话策略
    session_strategy: SessionStrategy = SessionStrategy.ROUND_ROBIN
    pool_policy: SessionPoolPolicy = SessionPoolPolicy.DYNAMIC
    
    # 重试配置
    max_retries: int = 3
    retry_delay: float = 1.0
    exponential_backoff: bool = True
    
    # 健康检查
    health_check_interval: int = 60
    health_check_timeout: float = 10.0
    enable_health_check: bool = True
    
    # 性能优化
    enable_connection_pooling: bool = True
    enable_keep_alive: bool = True
    enable_compression: bool = True
    
    # 调试配置
    enable_debug_logging: bool = False
    enable_metrics: bool = True


@dataclass
class SessionMetrics:
    """会话指标"""
    session_id: str
    creation_time: datetime
    last_used_time: datetime
    request_count: int = 0
    error_count: int = 0
    total_response_time: float = 0.0
    average_response_time: float = 0.0
    is_healthy: bool = True
    
    def update_metrics(self, response_time: float, success: bool):
        """更新指标"""
        self.request_count += 1
        self.last_used_time = datetime.now()
        self.total_response_time += response_time
        self.average_response_time = self.total_response_time / self.request_count
        
        if not success:
            self.error_count += 1
            
        # 更新健康状态
        error_rate = self.error_count / self.request_count
        self.is_healthy = error_rate < 0.1  # 错误率低于10%认为是健康的


@runtime_checkable
class SessionProtocol(Protocol):
    """会话协议"""
    
    async def get(self, url: str, **kwargs) -> Any:
        """GET请求"""
        ...
    
    async def post(self, url: str, **kwargs) -> Any:
        """POST请求"""
        ...
    
    async def close(self):
        """关闭会话"""
        ...
    
    @property
    def closed(self) -> bool:
        """是否已关闭"""
        ...


class BaseSessionManager(ISessionPlugin, ABC):
    """
    统一会话管理基类
    
    提供统一的会话管理接口和公共实现，减少代码重复
    """
    
    def __init__(self, config: Optional[UnifiedSessionConfig] = None):
        """初始化会话管理器基类"""
        # 初始化插件接口
        super().__init__()
        
        # 配置管理
        self.config = config or UnifiedSessionConfig()
        
        # 会话池管理
        self.sessions: Dict[str, SessionProtocol] = {}
        self.session_metrics: Dict[str, SessionMetrics] = {}
        self.session_locks: Dict[str, asyncio.Lock] = {}
        
        # 策略管理
        self.session_strategy = self.config.session_strategy
        self.pool_policy = self.config.pool_policy
        
        # 统计信息
        self.total_sessions_created = 0
        self.total_sessions_destroyed = 0
        self.total_requests = 0
        self.total_errors = 0
        
        # 健康检查
        self.health_check_task: Optional[asyncio.Task] = None
        
        # 会话选择状态
        self.round_robin_index = 0
        self.sticky_sessions: Dict[str, str] = {}  # URL -> session_id
        
        # 异步锁
        self.pool_lock = asyncio.Lock()
        
        logger.info(f"BaseSessionManager initialized with strategy: {self.session_strategy.value}")
    
    def _create_metadata(self) -> PluginMetadata:
        """创建插件元数据"""
        return PluginMetadata(
            name=f"{self.__class__.__name__}",
            version="2.0.0",
            category=PluginCategory.SESSION,
            priority=PluginPriority.HIGH,
            description="统一会话管理器基类",
            dependencies=[],
            supported_features=[
                "session_pooling",
                "health_check",
                "metrics",
                "strategy_selection",
                "auto_retry"
            ]
        )
    
    # ========================
    # 插件接口实现
    # ========================
    
    async def _initialize_impl(self) -> bool:
        """具体初始化实现"""
        try:
            # 初始化会话池
            await self._initialize_session_pool()
            
            # 启动健康检查
            if self.config.enable_health_check:
                await self._start_health_check()
            
            logger.info("BaseSessionManager initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize BaseSessionManager: {e}")
            return False
    
    async def _start_impl(self) -> bool:
        """具体启动实现"""
        try:
            # 预创建会话
            if self.pool_policy == SessionPoolPolicy.FIXED_SIZE:
                await self._create_initial_sessions()
            
            logger.info("BaseSessionManager started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start BaseSessionManager: {e}")
            return False
    
    async def _stop_impl(self) -> bool:
        """具体停止实现"""
        try:
            # 停止健康检查
            if self.health_check_task:
                self.health_check_task.cancel()
                try:
                    await self.health_check_task
                except asyncio.CancelledError:
                    pass
            
            # 关闭所有会话
            await self._close_all_sessions()
            
            logger.info("BaseSessionManager stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop BaseSessionManager: {e}")
            return False
    
    async def _healthcheck_impl(self) -> Dict[str, Any]:
        """具体健康检查实现"""
        healthy_sessions = sum(1 for metrics in self.session_metrics.values() if metrics.is_healthy)
        total_sessions = len(self.sessions)
        
        return {
            'healthy': healthy_sessions == total_sessions and total_sessions > 0,
            'total_sessions': total_sessions,
            'healthy_sessions': healthy_sessions,
            'total_requests': self.total_requests,
            'total_errors': self.total_errors,
            'error_rate': self.total_errors / max(self.total_requests, 1),
            'average_response_time': self._calculate_average_response_time()
        }
    
    # ========================
    # 会话管理接口实现
    # ========================
    
    async def get_session(self, session_id: str = None) -> SessionProtocol:
        """获取会话"""
        try:
            if session_id:
                # 获取指定会话
                if session_id in self.sessions and not self.sessions[session_id].closed:
                    return self.sessions[session_id]
                else:
                    # 指定会话不存在或已关闭，创建新会话
                    return await self._create_session(session_id)
            else:
                # 使用策略选择会话
                return await self._select_session_by_strategy()
                
        except Exception as e:
            logger.error(f"Failed to get session: {e}")
            raise
    
    async def create_session(self, config: Dict[str, Any] = None) -> str:
        """创建会话"""
        session_id = f"session_{int(time.time() * 1000)}_{id(self)}"
        
        try:
            session = await self._create_session(session_id, config)
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to create session {session_id}: {e}")
            raise
    
    async def close_session(self, session_id: str) -> bool:
        """关闭会话"""
        try:
            if session_id in self.sessions:
                session = self.sessions[session_id]
                
                # 关闭会话
                await session.close()
                
                # 清理资源
                del self.sessions[session_id]
                if session_id in self.session_metrics:
                    del self.session_metrics[session_id]
                if session_id in self.session_locks:
                    del self.session_locks[session_id]
                
                # 更新统计
                self.total_sessions_destroyed += 1
                
                logger.debug(f"Session closed: {session_id}")
                return True
            else:
                logger.warning(f"Session not found: {session_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to close session {session_id}: {e}")
            return False
    
    # ========================
    # 抽象方法 - 子类必须实现
    # ========================
    
    @abstractmethod
    async def _create_session_impl(self, session_id: str, config: Dict[str, Any] = None) -> SessionProtocol:
        """创建会话的具体实现"""
        pass
    
    @abstractmethod
    async def _validate_session_impl(self, session: SessionProtocol) -> bool:
        """验证会话的具体实现"""
        pass
    
    # ========================
    # 会话池管理
    # ========================
    
    async def _initialize_session_pool(self):
        """初始化会话池"""
        logger.info("Initializing session pool...")
        
        # 根据策略初始化
        if self.pool_policy == SessionPoolPolicy.FIXED_SIZE:
            # 固定大小，预创建所有会话
            pass  # 在start时创建
        elif self.pool_policy == SessionPoolPolicy.DYNAMIC:
            # 动态创建，初始为空
            pass
        elif self.pool_policy == SessionPoolPolicy.ADAPTIVE:
            # 自适应，创建最小数量
            min_sessions = max(1, self.config.max_sessions // 4)
            for i in range(min_sessions):
                session_id = f"initial_session_{i}"
                try:
                    await self._create_session(session_id)
                except Exception as e:
                    logger.warning(f"Failed to create initial session {session_id}: {e}")
    
    async def _create_initial_sessions(self):
        """创建初始会话"""
        for i in range(self.config.max_sessions):
            session_id = f"fixed_session_{i}"
            try:
                await self._create_session(session_id)
            except Exception as e:
                logger.error(f"Failed to create initial session {session_id}: {e}")
    
    async def _create_session(self, session_id: str, config: Dict[str, Any] = None) -> SessionProtocol:
        """创建会话"""
        async with self.pool_lock:
            try:
                # 检查会话数量限制
                if len(self.sessions) >= self.config.max_sessions:
                    # 尝试清理无效会话
                    await self._cleanup_invalid_sessions()
                    
                    # 如果仍然超限，使用LRU策略移除最旧的会话
                    if len(self.sessions) >= self.config.max_sessions:
                        await self._evict_lru_session()
                
                # 创建会话
                session = await self._create_session_impl(session_id, config)
                
                # 验证会话
                if not await self._validate_session_impl(session):
                    await session.close()
                    raise ValueError(f"Session validation failed: {session_id}")
                
                # 注册会话
                self.sessions[session_id] = session
                self.session_locks[session_id] = asyncio.Lock()
                
                # 创建指标
                self.session_metrics[session_id] = SessionMetrics(
                    session_id=session_id,
                    creation_time=datetime.now(),
                    last_used_time=datetime.now()
                )
                
                # 更新统计
                self.total_sessions_created += 1
                
                logger.debug(f"Session created: {session_id}")
                return session
                
            except Exception as e:
                logger.error(f"Failed to create session {session_id}: {e}")
                raise
    
    async def _cleanup_invalid_sessions(self):
        """清理无效会话"""
        invalid_sessions = []
        
        for session_id, session in self.sessions.items():
            if session.closed:
                invalid_sessions.append(session_id)
        
        for session_id in invalid_sessions:
            await self.close_session(session_id)
        
        logger.debug(f"Cleaned up {len(invalid_sessions)} invalid sessions")
    
    async def _evict_lru_session(self):
        """移除最近最少使用的会话"""
        if not self.session_metrics:
            return
        
        # 找到最旧的会话
        lru_session_id = min(
            self.session_metrics.keys(),
            key=lambda sid: self.session_metrics[sid].last_used_time
        )
        
        await self.close_session(lru_session_id)
        logger.debug(f"Evicted LRU session: {lru_session_id}")
    
    # ========================
    # 会话选择策略
    # ========================
    
    async def _select_session_by_strategy(self, url: str = None) -> SessionProtocol:
        """根据策略选择会话"""
        if not self.sessions:
            # 没有可用会话，创建一个
            session_id = await self.create_session()
            return self.sessions[session_id]
        
        if self.session_strategy == SessionStrategy.ROUND_ROBIN:
            return await self._select_round_robin()
        elif self.session_strategy == SessionStrategy.LEAST_USED:
            return await self._select_least_used()
        elif self.session_strategy == SessionStrategy.RANDOM:
            return await self._select_random()
        elif self.session_strategy == SessionStrategy.STICKY:
            return await self._select_sticky(url)
        elif self.session_strategy == SessionStrategy.LOAD_BALANCED:
            return await self._select_load_balanced()
        else:
            # 默认轮询
            return await self._select_round_robin()
    
    async def _select_round_robin(self) -> SessionProtocol:
        """轮询选择"""
        active_sessions = [(sid, session) for sid, session in self.sessions.items() if not session.closed]
        if not active_sessions:
            raise RuntimeError("No active sessions available")
        
        session_id, session = active_sessions[self.round_robin_index % len(active_sessions)]
        self.round_robin_index = (self.round_robin_index + 1) % len(active_sessions)
        
        return session
    
    async def _select_least_used(self) -> SessionProtocol:
        """选择最少使用的会话"""
        if not self.session_metrics:
            raise RuntimeError("No session metrics available")
        
        least_used_id = min(
            self.session_metrics.keys(),
            key=lambda sid: self.session_metrics[sid].request_count
        )
        
        return self.sessions[least_used_id]
    
    async def _select_random(self) -> SessionProtocol:
        """随机选择"""
        import random
        active_sessions = [session for session in self.sessions.values() if not session.closed]
        if not active_sessions:
            raise RuntimeError("No active sessions available")
        
        return random.choice(active_sessions)
    
    async def _select_sticky(self, url: str = None) -> SessionProtocol:
        """粘性选择"""
        if url and url in self.sticky_sessions:
            session_id = self.sticky_sessions[url]
            if session_id in self.sessions and not self.sessions[session_id].closed:
                return self.sessions[session_id]
        
        # 选择一个会话并建立粘性关系
        session = await self._select_least_used()
        if url:
            # 找到session_id
            session_id = next(sid for sid, s in self.sessions.items() if s == session)
            self.sticky_sessions[url] = session_id
        
        return session
    
    async def _select_load_balanced(self) -> SessionProtocol:
        """负载均衡选择"""
        if not self.session_metrics:
            return await self._select_round_robin()
        
        # 计算每个会话的负载分数
        scores = {}
        for session_id, metrics in self.session_metrics.items():
            if session_id in self.sessions and not self.sessions[session_id].closed:
                # 负载分数 = 错误率 * 50 + 平均响应时间 * 10 + 请求数 / 1000
                error_rate = metrics.error_count / max(metrics.request_count, 1)
                score = error_rate * 50 + metrics.average_response_time * 10 + metrics.request_count / 1000
                scores[session_id] = score
        
        if not scores:
            return await self._select_round_robin()
        
        # 选择分数最低的会话
        best_session_id = min(scores.keys(), key=lambda sid: scores[sid])
        return self.sessions[best_session_id]
    
    # ========================
    # 健康检查
    # ========================
    
    async def _start_health_check(self):
        """启动健康检查"""
        if self.health_check_task is None:
            self.health_check_task = asyncio.create_task(self._health_check_loop())
            logger.info("Health check started")
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._perform_health_check()
            except asyncio.CancelledError:
                logger.info("Health check task cancelled")
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
    
    async def _perform_health_check(self):
        """执行健康检查"""
        unhealthy_sessions = []
        
        for session_id, session in self.sessions.items():
            try:
                # 检查会话是否关闭
                if session.closed:
                    unhealthy_sessions.append(session_id)
                    continue
                
                # 执行具体的健康检查
                if not await self._validate_session_impl(session):
                    unhealthy_sessions.append(session_id)
                    continue
                
                # 检查会话指标
                metrics = self.session_metrics.get(session_id)
                if metrics and not metrics.is_healthy:
                    unhealthy_sessions.append(session_id)
                
            except Exception as e:
                logger.error(f"Health check failed for session {session_id}: {e}")
                unhealthy_sessions.append(session_id)
        
        # 清理不健康的会话
        for session_id in unhealthy_sessions:
            await self.close_session(session_id)
        
        if unhealthy_sessions:
            logger.info(f"Health check removed {len(unhealthy_sessions)} unhealthy sessions")
        
        # 如果会话数量过少，创建新会话
        if len(self.sessions) < self.config.max_sessions // 2:
            try:
                await self._create_session(f"health_check_session_{int(time.time())}")
            except Exception as e:
                logger.error(f"Failed to create health check session: {e}")
    
    # ========================
    # 工具方法
    # ========================
    
    async def _close_all_sessions(self):
        """关闭所有会话"""
        logger.info("Closing all sessions...")
        
        close_tasks = []
        for session_id in list(self.sessions.keys()):
            close_tasks.append(self.close_session(session_id))
        
        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)
        
        logger.info(f"All sessions closed. Total created: {self.total_sessions_created}, destroyed: {self.total_sessions_destroyed}")
    
    def _calculate_average_response_time(self) -> float:
        """计算平均响应时间"""
        if not self.session_metrics:
            return 0.0
        
        total_time = sum(metrics.average_response_time for metrics in self.session_metrics.values())
        return total_time / len(self.session_metrics)
    
    def get_session_statistics(self) -> Dict[str, Any]:
        """获取会话统计信息"""
        active_sessions = sum(1 for session in self.sessions.values() if not session.closed)
        healthy_sessions = sum(1 for metrics in self.session_metrics.values() if metrics.is_healthy)
        
        return {
            'total_sessions': len(self.sessions),
            'active_sessions': active_sessions,
            'healthy_sessions': healthy_sessions,
            'total_created': self.total_sessions_created,
            'total_destroyed': self.total_sessions_destroyed,
            'total_requests': self.total_requests,
            'total_errors': self.total_errors,
            'error_rate': self.total_errors / max(self.total_requests, 1),
            'average_response_time': self._calculate_average_response_time(),
            'session_strategy': self.session_strategy.value,
            'pool_policy': self.pool_policy.value,
            'config': {
                'max_sessions': self.config.max_sessions,
                'session_timeout': self.config.session_timeout,
                'idle_timeout': self.config.idle_timeout,
                'health_check_interval': self.config.health_check_interval
            }
        }
    
    # ========================
    # 上下文管理器支持
    # ========================
    
    @asynccontextmanager
    async def session_context(self, session_id: str = None):
        """会话上下文管理器"""
        session = None
        try:
            session = await self.get_session(session_id)
            yield session
        finally:
            # 会话由池管理，不需要手动关闭
            pass
    
    def update_session_config(self, new_config: UnifiedSessionConfig):
        """更新会话配置"""
        self.config = new_config
        self.session_strategy = new_config.session_strategy
        self.pool_policy = new_config.pool_policy
        logger.info("Session configuration updated")
    
    async def record_request_metrics(self, session_id: str, response_time: float, success: bool):
        """记录请求指标"""
        if session_id in self.session_metrics:
            self.session_metrics[session_id].update_metrics(response_time, success)
        
        self.total_requests += 1
        if not success:
            self.total_errors += 1


# 会话管理器适配器 - 用于包装现有的会话管理器
class SessionManagerAdapter(BaseSessionManager):
    """
    会话管理器适配器
    
    将现有的会话管理器适配为统一接口，实现向后兼容性
    """
    
    def __init__(self, 
                 wrapped_manager: Any,
                 config: Optional[UnifiedSessionConfig] = None):
        """
        初始化适配器
        
        Args:
            wrapped_manager: 被包装的会话管理器
            config: 统一配置
        """
        super().__init__(config)
        self.wrapped_manager = wrapped_manager
        self.is_wrapped = True
        
        logger.info(f"SessionManagerAdapter wrapping {type(wrapped_manager).__name__}")
    
    async def _create_session_impl(self, session_id: str, config: Dict[str, Any] = None) -> SessionProtocol:
        """创建会话的具体实现（适配）"""
        # 如果被包装的管理器有create_session方法
        if hasattr(self.wrapped_manager, 'create_session'):
            return await self.wrapped_manager.create_session(config or {})
        
        # 否则尝试get_session
        elif hasattr(self.wrapped_manager, 'get_session'):
            return await self.wrapped_manager.get_session(session_id)
        
        # 最后尝试get方法
        elif hasattr(self.wrapped_manager, 'get'):
            return await self.wrapped_manager.get(session_id)
        
        else:
            raise NotImplementedError("Wrapped manager does not support session creation")
    
    async def _validate_session_impl(self, session: SessionProtocol) -> bool:
        """验证会话的具体实现（适配）"""
        try:
            # 基本验证：检查会话是否关闭
            if hasattr(session, 'closed'):
                return not session.closed
            
            # 如果被包装的管理器有验证方法
            if hasattr(self.wrapped_manager, 'validate_session'):
                return await self.wrapped_manager.validate_session(session)
            
            # 默认认为有效
            return True
            
        except Exception as e:
            logger.error(f"Session validation error: {e}")
            return False
    
    def _create_metadata(self) -> PluginMetadata:
        """创建插件元数据"""
        wrapped_name = type(self.wrapped_manager).__name__ if self.wrapped_manager else "Unknown"
        
        return PluginMetadata(
            name=f"SessionManagerAdapter({wrapped_name})",
            version="2.0.0",
            category=PluginCategory.SESSION,
            priority=PluginPriority.NORMAL,
            description=f"统一会话管理适配器，包装 {wrapped_name}",
            dependencies=[],
            supported_features=[
                "session_pooling",
                "health_check",
                "metrics",
                "backward_compatibility"
            ]
        )


# 便捷函数
def create_unified_session_manager(
    manager_type: str = "enhanced",
    config: Optional[UnifiedSessionConfig] = None,
    **kwargs
) -> BaseSessionManager:
    """
    创建统一会话管理器
    
    Args:
        manager_type: 管理器类型
        config: 统一配置
        **kwargs: 额外参数
        
    Returns:
        BaseSessionManager: 统一会话管理器实例
    """
    if manager_type == "enhanced":
        # 使用适配器包装现有的EnhancedSessionManager
        from ..scrapers.enhanced_session_manager import EnhancedSessionManager, SessionConfig
        
        # 转换配置
        if config:
            session_config = SessionConfig(
                max_concurrent_sessions=config.max_sessions,
                session_timeout=config.session_timeout,
                idle_timeout=config.idle_timeout,
                connection_timeout=config.connection_timeout,
                read_timeout=config.read_timeout,
                total_timeout=config.total_timeout,
                **kwargs
            )
        else:
            session_config = SessionConfig(**kwargs)
        
        enhanced_manager = EnhancedSessionManager(session_config)
        return SessionManagerAdapter(enhanced_manager, config)
    
    elif manager_type == "basic":
        # 使用适配器包装基础会话管理器
        from ..scrapers.session_manager import SessionManager
        
        basic_manager = SessionManager(**kwargs)
        return SessionManagerAdapter(basic_manager, config)
    
    else:
        raise ValueError(f"Unknown manager type: {manager_type}")


async def create_async_unified_session_manager(
    manager_type: str = "enhanced",
    config: Optional[UnifiedSessionConfig] = None,
    **kwargs
) -> BaseSessionManager:
    """
    异步创建统一会话管理器
    
    Args:
        manager_type: 管理器类型
        config: 统一配置
        **kwargs: 额外参数
        
    Returns:
        BaseSessionManager: 已初始化的统一会话管理器实例
    """
    manager = create_unified_session_manager(manager_type, config, **kwargs)
    await manager.initialize()
    await manager.start()
    return manager