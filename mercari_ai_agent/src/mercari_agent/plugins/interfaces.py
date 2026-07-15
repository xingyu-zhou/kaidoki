"""
统一插件接口定义

该模块定义了统一的插件接口，扩展了现有的反检测插件接口，
支持所有反检测组件的插件化，包括：
- 会话管理插件
- 指纹管理插件
- 行为模拟插件
- 反检测策略插件
- 验证码检测插件

核心设计理念：
- 统一的插件生命周期管理
- 标准化的配置接口
- 事件驱动的组件通信
- 热插拔支持
- 向后兼容性

Author: Mercari AI Agent Team
"""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union, Callable, Set, Type
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import weakref
from contextlib import asynccontextmanager

# 导入现有的基础接口
from ..captcha.plugin_interface import (
    IAntiDetectionPlugin as BaseAntiDetectionPlugin,
    PluginStatus,
    PluginPriority,
    PluginCategory,
    PluginMetadata,
    PluginEvent,
    IDetectionPlugin,
    ISessionPlugin,
    IFingerprintPlugin,
    IBehaviorPlugin,
    IEnvironmentPlugin
)

# 为了保持向后兼容性，创建PluginState别名
PluginState = PluginStatus
from ..utils.logger import get_logger

logger = get_logger(__name__)


class PluginType(Enum):
    """插件类型枚举"""
    CORE = "core"
    DETECTION = "detection"
    SESSION_MANAGEMENT = "session_management"
    FINGERPRINT = "fingerprint"
    BEHAVIOR_SIMULATION = "behavior_simulation"
    ANTI_DETECTION = "anti_detection"
    CAPTCHA_DETECTION = "captcha_detection"
    ENVIRONMENT = "environment"
    MONITORING = "monitoring"
    UTILITY = "utility"


class PluginCapability(Enum):
    """插件能力枚举"""
    HOT_RELOAD = "hot_reload"
    CONFIGURATION_MANAGEMENT = "configuration_management"
    HEALTH_CHECK = "health_check"
    METRICS_COLLECTION = "metrics_collection"
    EVENT_HANDLING = "event_handling"
    DEPENDENCY_MANAGEMENT = "dependency_management"
    ASYNC_PROCESSING = "async_processing"
    BATCH_PROCESSING = "batch_processing"


@dataclass
class PluginPerformanceMetrics:
    """插件性能指标"""
    initialization_time: float = 0.0
    average_execution_time: float = 0.0
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    last_execution_time: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_executions == 0:
            return 0.0
        return (self.successful_executions / self.total_executions) * 100
    
    def record_execution(self, success: bool, execution_time: float):
        """记录执行统计"""
        self.total_executions += 1
        if success:
            self.successful_executions += 1
        else:
            self.failed_executions += 1
        
        # 更新平均执行时间
        current_total_time = self.average_execution_time * (self.total_executions - 1)
        self.average_execution_time = (current_total_time + execution_time) / self.total_executions
        self.last_execution_time = datetime.now()


@dataclass
class PluginConfiguration:
    """插件配置"""
    plugin_id: str
    plugin_type: PluginType
    enabled: bool = True
    priority: PluginPriority = PluginPriority.NORMAL
    capabilities: Set[PluginCapability] = field(default_factory=set)
    dependencies: List[str] = field(default_factory=list)
    config_schema: Optional[Dict[str, Any]] = None
    runtime_config: Dict[str, Any] = field(default_factory=dict)
    version: str = "1.0.0"
    min_framework_version: str = "1.0.0"
    max_framework_version: str = "2.0.0"
    
    def validate_config(self) -> bool:
        """验证配置"""
        if not self.plugin_id:
            return False
        if self.config_schema and self.runtime_config:
            # 这里可以添加schema验证逻辑
            pass
        return True


class IPlugin(BaseAntiDetectionPlugin):
    """
    统一插件接口
    
    所有插件都应该实现此接口，提供统一的生命周期管理和功能接口。
    该接口扩展了BaseAntiDetectionPlugin，添加了更多统一的功能。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._plugin_config = self._create_plugin_configuration()
        self._performance_metrics = PluginPerformanceMetrics()
        self._capabilities = set()
        self._framework_ref: Optional[weakref.ref] = None
        
    @abstractmethod
    def _create_plugin_configuration(self) -> PluginConfiguration:
        """创建插件配置"""
        pass
    
    @property
    def plugin_config(self) -> PluginConfiguration:
        """获取插件配置"""
        return self._plugin_config
    
    @property
    def performance_metrics(self) -> PluginPerformanceMetrics:
        """获取性能指标"""
        return self._performance_metrics
    
    @property
    def capabilities(self) -> Set[PluginCapability]:
        """获取插件能力"""
        return self._capabilities
    
    def set_framework_reference(self, framework_ref: weakref.ref):
        """设置框架引用"""
        self._framework_ref = framework_ref
    
    async def reload_config(self, new_config: Dict[str, Any]) -> bool:
        """重新加载配置"""
        try:
            # 验证新配置
            if not self._validate_new_config(new_config):
                return False
            
            # 应用新配置
            self._plugin_config.runtime_config.update(new_config)
            self._config.update(new_config)
            
            # 重新应用配置
            await self._apply_config_reload()
            
            logger.info(f"Plugin {self.metadata.name} config reloaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Plugin {self.metadata.name} config reload failed: {e}")
            return False
    
    async def get_plugin_info(self) -> Dict[str, Any]:
        """获取插件信息"""
        return {
            'plugin_id': self._plugin_config.plugin_id,
            'plugin_type': self._plugin_config.plugin_type.value,
            'version': self._plugin_config.version,
            'status': self.status.value,
            'capabilities': [cap.value for cap in self._capabilities],
            'dependencies': self._plugin_config.dependencies,
            'performance_metrics': {
                'initialization_time': self._performance_metrics.initialization_time,
                'average_execution_time': self._performance_metrics.average_execution_time,
                'total_executions': self._performance_metrics.total_executions,
                'success_rate': self._performance_metrics.success_rate,
                'memory_usage_mb': self._performance_metrics.memory_usage_mb,
                'cpu_usage_percent': self._performance_metrics.cpu_usage_percent,
                'last_execution_time': self._performance_metrics.last_execution_time.isoformat() if self._performance_metrics.last_execution_time else None
            },
            'metadata': self.metadata
        }
    
    async def execute_with_metrics(self, operation: Callable, *args, **kwargs) -> Any:
        """执行操作并收集指标"""
        start_time = time.time()
        success = False
        result = None
        
        try:
            if asyncio.iscoroutinefunction(operation):
                result = await operation(*args, **kwargs)
            else:
                result = operation(*args, **kwargs)
            success = True
            return result
            
        except Exception as e:
            logger.error(f"Plugin {self.metadata.name} operation failed: {e}")
            raise
        finally:
            execution_time = time.time() - start_time
            self._performance_metrics.record_execution(success, execution_time)
    
    def _validate_new_config(self, new_config: Dict[str, Any]) -> bool:
        """验证新配置"""
        # 这里可以添加具体的配置验证逻辑
        return True
    
    async def _apply_config_reload(self):
        """应用配置重新加载"""
        # 子类可以重写此方法来处理配置重新加载
        pass


class ISessionManagementPlugin(IPlugin):
    """会话管理插件接口"""
    
    def _create_plugin_configuration(self) -> PluginConfiguration:
        return PluginConfiguration(
            plugin_id=self.__class__.__name__,
            plugin_type=PluginType.SESSION_MANAGEMENT,
            capabilities={
                PluginCapability.HOT_RELOAD,
                PluginCapability.CONFIGURATION_MANAGEMENT,
                PluginCapability.HEALTH_CHECK,
                PluginCapability.METRICS_COLLECTION
            }
        )
    
    @abstractmethod
    async def create_session(self, session_config: Dict[str, Any] = None) -> str:
        """创建会话"""
        pass
    
    @abstractmethod
    async def get_session(self, session_id: str) -> Any:
        """获取会话"""
        pass
    
    @abstractmethod
    async def close_session(self, session_id: str) -> bool:
        """关闭会话"""
        pass
    
    @abstractmethod
    async def get_session_stats(self) -> Dict[str, Any]:
        """获取会话统计"""
        pass
    
    @abstractmethod
    async def optimize_session_pool(self) -> bool:
        """优化会话池"""
        pass


class IFingerprintPlugin(IPlugin):
    """指纹管理插件接口"""
    
    def _create_plugin_configuration(self) -> PluginConfiguration:
        return PluginConfiguration(
            plugin_id=self.__class__.__name__,
            plugin_type=PluginType.FINGERPRINT,
            capabilities={
                PluginCapability.HOT_RELOAD,
                PluginCapability.CONFIGURATION_MANAGEMENT,
                PluginCapability.HEALTH_CHECK,
                PluginCapability.BATCH_PROCESSING
            }
        )
    
    @abstractmethod
    async def generate_fingerprint(self, fingerprint_type: str = None) -> Dict[str, Any]:
        """生成指纹"""
        pass
    
    @abstractmethod
    async def apply_fingerprint(self, session: Any, fingerprint: Dict[str, Any]) -> bool:
        """应用指纹"""
        pass
    
    @abstractmethod
    async def get_fingerprint_pool_stats(self) -> Dict[str, Any]:
        """获取指纹池统计"""
        pass
    
    @abstractmethod
    async def refresh_fingerprint_pool(self) -> bool:
        """刷新指纹池"""
        pass


# 为了保持向后兼容性，创建指纹管理插件别名
IFingerprintManagementPlugin = IFingerprintPlugin


class IBehaviorSimulationPlugin(IPlugin):
    """行为模拟插件接口"""
    
    def _create_plugin_configuration(self) -> PluginConfiguration:
        return PluginConfiguration(
            plugin_id=self.__class__.__name__,
            plugin_type=PluginType.BEHAVIOR_SIMULATION,
            capabilities={
                PluginCapability.HOT_RELOAD,
                PluginCapability.CONFIGURATION_MANAGEMENT,
                PluginCapability.ASYNC_PROCESSING,
                PluginCapability.METRICS_COLLECTION
            }
        )
    
    @abstractmethod
    async def simulate_mouse_behavior(self, session: Any, behavior_config: Dict[str, Any] = None) -> bool:
        """模拟鼠标行为"""
        pass
    
    @abstractmethod
    async def simulate_keyboard_behavior(self, session: Any, behavior_config: Dict[str, Any] = None) -> bool:
        """模拟键盘行为"""
        pass
    
    @abstractmethod
    async def simulate_page_behavior(self, session: Any, behavior_config: Dict[str, Any] = None) -> bool:
        """模拟页面行为"""
        pass
    
    @abstractmethod
    async def get_behavior_stats(self) -> Dict[str, Any]:
        """获取行为统计"""
        pass


class IAntiDetectionPlugin(IPlugin):
    """反检测策略插件接口"""
    
    def _create_plugin_configuration(self) -> PluginConfiguration:
        return PluginConfiguration(
            plugin_id=self.__class__.__name__,
            plugin_type=PluginType.ANTI_DETECTION,
            capabilities={
                PluginCapability.HOT_RELOAD,
                PluginCapability.CONFIGURATION_MANAGEMENT,
                PluginCapability.HEALTH_CHECK,
                PluginCapability.EVENT_HANDLING,
                PluginCapability.ASYNC_PROCESSING
            }
        )
    
    @abstractmethod
    async def apply_anti_detection_strategy(self, session: Any, strategy_config: Dict[str, Any] = None) -> bool:
        """应用反检测策略"""
        pass
    
    @abstractmethod
    async def detect_bot_detection(self, content: str, response: Any = None) -> Dict[str, Any]:
        """检测机器人检测"""
        pass
    
    @abstractmethod
    async def get_detection_stats(self) -> Dict[str, Any]:
        """获取检测统计"""
        pass


class ICaptchaDetectionPlugin(IPlugin):
    """验证码检测插件接口"""
    
    def _create_plugin_configuration(self) -> PluginConfiguration:
        return PluginConfiguration(
            plugin_id=self.__class__.__name__,
            plugin_type=PluginType.CAPTCHA_DETECTION,
            capabilities={
                PluginCapability.HOT_RELOAD,
                PluginCapability.CONFIGURATION_MANAGEMENT,
                PluginCapability.HEALTH_CHECK,
                PluginCapability.BATCH_PROCESSING,
                PluginCapability.ASYNC_PROCESSING
            }
        )
    
    @abstractmethod
    async def detect_captcha(self, content: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """检测验证码"""
        pass
    
    @abstractmethod
    async def get_supported_captcha_types(self) -> Set[str]:
        """获取支持的验证码类型"""
        pass
    
    @abstractmethod
    async def validate_detection_result(self, result: Dict[str, Any]) -> bool:
        """验证检测结果"""
        pass


# 插件装饰器
def unified_plugin(
    plugin_type: PluginType,
    priority: PluginPriority = PluginPriority.NORMAL,
    capabilities: Set[PluginCapability] = None,
    dependencies: List[str] = None,
    version: str = "1.0.0"
):
    """
    统一插件装饰器
    
    Args:
        plugin_type: 插件类型
        priority: 插件优先级
        capabilities: 插件能力
        dependencies: 依赖列表
        version: 插件版本
    """
    def decorator(cls):
        cls._plugin_type = plugin_type
        cls._plugin_priority = priority
        cls._plugin_capabilities = capabilities or set()
        cls._plugin_dependencies = dependencies or []
        cls._plugin_version = version
        
        # 确保实现了必要的接口
        if not issubclass(cls, IPlugin):
            raise TypeError(f"Plugin {cls.__name__} must implement IPlugin")
        
        return cls
    
    return decorator


# 插件上下文管理器
@asynccontextmanager
async def plugin_context(plugin: IPlugin):
    """插件上下文管理器"""
    try:
        await plugin.initialize()
        await plugin.start()
        yield plugin
    finally:
        await plugin.stop()


# 插件性能监控装饰器
def monitor_performance(func):
    """插件性能监控装饰器"""
    async def wrapper(self, *args, **kwargs):
        if isinstance(self, IPlugin):
            return await self.execute_with_metrics(func, self, *args, **kwargs)
        else:
            return await func(self, *args, **kwargs)
    return wrapper