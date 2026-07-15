"""
反检测插件接口定义

该模块定义了反检测系统的插件化架构接口，提供统一的组件管理和扩展机制。

核心设计理念：
- 插件化架构，支持组件的热插拔
- 统一的生命周期管理
- 事件驱动的组件通信
- 配置驱动的功能开关
- 完全向后兼容

Author: Mercari AI Agent Team
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union, Callable, Type
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import weakref
from contextlib import asynccontextmanager

from ..utils.logger import get_logger

logger = get_logger(__name__)


class PluginStatus(Enum):
    """插件状态枚举"""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
    STOPPING = "stopping"
    STOPPED = "stopped"


class PluginPriority(Enum):
    """插件优先级"""
    CRITICAL = 1      # 关键组件，系统无法运行
    HIGH = 10         # 高优先级
    NORMAL = 50       # 普通优先级
    LOW = 100         # 低优先级
    OPTIONAL = 1000   # 可选组件


class PluginCategory(Enum):
    """插件分类"""
    CORE = "core"                    # 核心组件
    DETECTION = "detection"          # 检测组件
    SESSION = "session"              # 会话管理
    FINGERPRINT = "fingerprint"      # 指纹管理
    BEHAVIOR = "behavior"            # 行为模拟
    ENVIRONMENT = "environment"      # 环境伪装
    CAPTCHA = "captcha"             # 验证码处理
    MONITORING = "monitoring"        # 监控组件
    UTILITY = "utility"             # 工具组件


@dataclass
class PluginMetadata:
    """插件元数据"""
    name: str
    version: str
    category: PluginCategory
    priority: PluginPriority = PluginPriority.NORMAL
    author: str = ""
    description: str = ""
    dependencies: List[str] = field(default_factory=list)
    config_schema: Optional[Dict[str, Any]] = None
    supported_features: List[str] = field(default_factory=list)
    minimum_system_version: str = "1.0.0"
    
    # 运行时信息
    plugin_id: Optional[str] = None
    load_time: Optional[datetime] = None
    status: PluginStatus = PluginStatus.UNINITIALIZED
    error_count: int = 0
    last_error: Optional[str] = None


@dataclass
class PluginEvent:
    """插件事件"""
    event_type: str
    source_plugin: str
    target_plugin: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    processed: bool = False


class IAntiDetectionPlugin(ABC):
    """
    反检测插件接口
    
    所有反检测组件都应该实现此接口，以便统一管理。
    该接口定义了插件的基本生命周期和功能接口。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化插件
        
        Args:
            config: 插件配置
        """
        self._metadata = self._create_metadata()
        self._config = config or {}
        self._status = PluginStatus.UNINITIALIZED
        self._event_listeners: Dict[str, List[Callable]] = {}
        self._manager_ref: Optional[weakref.ref] = None
        self._lock = asyncio.Lock()
        
        # 性能统计
        self._stats = {
            'total_operations': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'average_response_time': 0.0,
            'last_operation_time': None
        }
    
    @abstractmethod
    def _create_metadata(self) -> PluginMetadata:
        """创建插件元数据"""
        pass
    
    @property
    def metadata(self) -> PluginMetadata:
        """获取插件元数据"""
        return self._metadata
    
    @property
    def status(self) -> PluginStatus:
        """获取插件状态"""
        return self._status
    
    @property
    def config(self) -> Dict[str, Any]:
        """获取插件配置"""
        return self._config
    
    @property
    def stats(self) -> Dict[str, Any]:
        """获取插件统计信息"""
        return self._stats.copy()
    
    async def initialize(self) -> bool:
        """
        初始化插件
        
        Returns:
            bool: 初始化是否成功
        """
        async with self._lock:
            if self._status != PluginStatus.UNINITIALIZED:
                logger.warning(f"Plugin {self.metadata.name} already initialized")
                return True
            
            try:
                self._status = PluginStatus.INITIALIZING
                logger.info(f"Initializing plugin: {self.metadata.name}")
                
                # 验证配置
                if not await self._validate_config():
                    raise ValueError("Configuration validation failed")
                
                # 执行具体初始化逻辑
                success = await self._initialize_impl()
                
                if success:
                    self._status = PluginStatus.ACTIVE
                    self.metadata.load_time = datetime.now()
                    logger.info(f"Plugin {self.metadata.name} initialized successfully")
                else:
                    self._status = PluginStatus.ERROR
                    logger.error(f"Plugin {self.metadata.name} initialization failed")
                
                return success
                
            except Exception as e:
                self._status = PluginStatus.ERROR
                self.metadata.last_error = str(e)
                self.metadata.error_count += 1
                logger.error(f"Plugin {self.metadata.name} initialization error: {e}")
                return False
    
    async def start(self) -> bool:
        """
        启动插件
        
        Returns:
            bool: 启动是否成功
        """
        async with self._lock:
            if self._status != PluginStatus.ACTIVE:
                logger.warning(f"Plugin {self.metadata.name} not ready for start")
                return False
            
            try:
                success = await self._start_impl()
                
                if success:
                    logger.info(f"Plugin {self.metadata.name} started successfully")
                else:
                    self._status = PluginStatus.ERROR
                    logger.error(f"Plugin {self.metadata.name} start failed")
                
                return success
                
            except Exception as e:
                self._status = PluginStatus.ERROR
                self.metadata.last_error = str(e)
                self.metadata.error_count += 1
                logger.error(f"Plugin {self.metadata.name} start error: {e}")
                return False
    
    async def stop(self) -> bool:
        """
        停止插件
        
        Returns:
            bool: 停止是否成功
        """
        async with self._lock:
            if self._status in [PluginStatus.STOPPED, PluginStatus.STOPPING]:
                return True
            
            try:
                self._status = PluginStatus.STOPPING
                logger.info(f"Stopping plugin: {self.metadata.name}")
                
                success = await self._stop_impl()
                
                if success:
                    self._status = PluginStatus.STOPPED
                    logger.info(f"Plugin {self.metadata.name} stopped successfully")
                else:
                    self._status = PluginStatus.ERROR
                    logger.error(f"Plugin {self.metadata.name} stop failed")
                
                return success
                
            except Exception as e:
                self._status = PluginStatus.ERROR
                self.metadata.last_error = str(e)
                self.metadata.error_count += 1
                logger.error(f"Plugin {self.metadata.name} stop error: {e}")
                return False
    
    async def pause(self) -> bool:
        """暂停插件"""
        async with self._lock:
            if self._status != PluginStatus.ACTIVE:
                return False
            
            try:
                success = await self._pause_impl()
                if success:
                    self._status = PluginStatus.PAUSED
                return success
            except Exception as e:
                logger.error(f"Plugin {self.metadata.name} pause error: {e}")
                return False
    
    async def resume(self) -> bool:
        """恢复插件"""
        async with self._lock:
            if self._status != PluginStatus.PAUSED:
                return False
            
            try:
                success = await self._resume_impl()
                if success:
                    self._status = PluginStatus.ACTIVE
                return success
            except Exception as e:
                logger.error(f"Plugin {self.metadata.name} resume error: {e}")
                return False
    
    async def healthcheck(self) -> Dict[str, Any]:
        """
        健康检查
        
        Returns:
            Dict[str, Any]: 健康检查结果
        """
        try:
            result = await self._healthcheck_impl()
            result['status'] = self._status.value
            result['metadata'] = self.metadata
            result['stats'] = self.stats
            return result
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'metadata': self.metadata,
                'stats': self.stats
            }
    
    def update_config(self, new_config: Dict[str, Any]) -> bool:
        """
        更新配置
        
        Args:
            new_config: 新配置
            
        Returns:
            bool: 更新是否成功
        """
        try:
            # 合并配置
            self._config.update(new_config)
            
            # 应用配置变更
            self._apply_config_changes()
            
            logger.info(f"Plugin {self.metadata.name} config updated")
            return True
        except Exception as e:
            logger.error(f"Plugin {self.metadata.name} config update error: {e}")
            return False
    
    def register_event_listener(self, event_type: str, callback: Callable):
        """注册事件监听器"""
        if event_type not in self._event_listeners:
            self._event_listeners[event_type] = []
        self._event_listeners[event_type].append(callback)
    
    def unregister_event_listener(self, event_type: str, callback: Callable):
        """注销事件监听器"""
        if event_type in self._event_listeners:
            self._event_listeners[event_type].remove(callback)
    
    async def emit_event(self, event: PluginEvent):
        """发送事件"""
        if self._manager_ref and self._manager_ref():
            manager = self._manager_ref()
            await manager.handle_plugin_event(event)
    
    async def handle_event(self, event: PluginEvent):
        """处理事件"""
        listeners = self._event_listeners.get(event.event_type, [])
        for callback in listeners:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Event handler error in {self.metadata.name}: {e}")
    
    def set_manager_reference(self, manager_ref: weakref.ref):
        """设置管理器引用"""
        self._manager_ref = manager_ref
    
    # 抽象方法，需要子类实现
    @abstractmethod
    async def _initialize_impl(self) -> bool:
        """具体初始化实现"""
        pass
    
    @abstractmethod
    async def _start_impl(self) -> bool:
        """具体启动实现"""
        pass
    
    @abstractmethod
    async def _stop_impl(self) -> bool:
        """具体停止实现"""
        pass
    
    async def _pause_impl(self) -> bool:
        """具体暂停实现"""
        return True
    
    async def _resume_impl(self) -> bool:
        """具体恢复实现"""
        return True
    
    async def _healthcheck_impl(self) -> Dict[str, Any]:
        """具体健康检查实现"""
        return {
            'healthy': True,
            'last_check': datetime.now().isoformat()
        }
    
    async def _validate_config(self) -> bool:
        """验证配置"""
        return True
    
    def _apply_config_changes(self):
        """应用配置变更"""
        pass
    
    def _update_stats(self, operation_type: str, success: bool, response_time: float):
        """更新统计信息"""
        self._stats['total_operations'] += 1
        if success:
            self._stats['successful_operations'] += 1
        else:
            self._stats['failed_operations'] += 1
        
        # 更新平均响应时间
        total_ops = self._stats['total_operations']
        current_avg = self._stats['average_response_time']
        self._stats['average_response_time'] = (current_avg * (total_ops - 1) + response_time) / total_ops
        self._stats['last_operation_time'] = datetime.now()


class IDetectionPlugin(IAntiDetectionPlugin):
    """检测插件接口"""
    
    @abstractmethod
    async def detect(self, content: str, response: Any = None, url: str = None) -> Dict[str, Any]:
        """执行检测"""
        pass


class ISessionPlugin(IAntiDetectionPlugin):
    """会话管理插件接口"""
    
    @abstractmethod
    async def get_session(self, session_id: str = None) -> Any:
        """获取会话"""
        pass
    
    @abstractmethod
    async def create_session(self, config: Dict[str, Any] = None) -> str:
        """创建会话"""
        pass
    
    @abstractmethod
    async def close_session(self, session_id: str) -> bool:
        """关闭会话"""
        pass


class IFingerprintPlugin(IAntiDetectionPlugin):
    """指纹管理插件接口"""
    
    @abstractmethod
    async def get_fingerprint(self) -> Dict[str, Any]:
        """获取指纹"""
        pass
    
    @abstractmethod
    async def apply_fingerprint(self, session: Any, fingerprint: Dict[str, Any]) -> bool:
        """应用指纹"""
        pass


class IBehaviorPlugin(IAntiDetectionPlugin):
    """行为模拟插件接口"""
    
    @abstractmethod
    async def simulate_user_behavior(self, behavior_type: str = None) -> bool:
        """模拟用户行为"""
        pass


class IEnvironmentPlugin(IAntiDetectionPlugin):
    """环境伪装插件接口"""
    
    @abstractmethod
    async def apply_spoofing(self, session: Any) -> bool:
        """应用环境伪装"""
        pass


# 插件装饰器
def anti_detection_plugin(
    category: PluginCategory,
    priority: PluginPriority = PluginPriority.NORMAL,
    dependencies: List[str] = None
):
    """
    反检测插件装饰器
    
    Args:
        category: 插件分类
        priority: 插件优先级
        dependencies: 依赖列表
    """
    def decorator(cls):
        cls._plugin_category = category
        cls._plugin_priority = priority
        cls._plugin_dependencies = dependencies or []
        return cls
    
    return decorator


# 插件上下文管理器
@asynccontextmanager
async def plugin_context(plugin: IAntiDetectionPlugin):
    """插件上下文管理器"""
    try:
        await plugin.initialize()
        await plugin.start()
        yield plugin
    finally:
        await plugin.stop()