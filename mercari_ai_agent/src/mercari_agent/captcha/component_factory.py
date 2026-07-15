"""
组件工厂模式实现

该模块实现了反检测系统的组件工厂，提供统一的组件创建和管理接口。

核心功能：
- 统一的组件创建接口
- 组件配置管理
- 组件生命周期管理
- 组件间依赖注入
- 配置驱动的组件装配
- 向后兼容性保证

设计特点：
- 工厂模式 + 建造者模式
- 依赖注入支持
- 配置驱动装配
- 插件化扩展
- 完全向后兼容

Author: Mercari AI Agent Team
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union, Type, TypeVar, Generic, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
import inspect
from functools import wraps

from .plugin_interface import (
    IAntiDetectionPlugin, PluginCategory, PluginPriority,
    IDetectionPlugin, ISessionPlugin, IFingerprintPlugin, 
    IBehaviorPlugin, IEnvironmentPlugin
)
from .plugin_registry import PluginRegistry, register_plugin, get_plugin
from ..utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T', bound=IAntiDetectionPlugin)


class ComponentType(Enum):
    """组件类型枚举"""
    DETECTOR = "detector"
    SESSION_MANAGER = "session_manager"
    FINGERPRINT_MANAGER = "fingerprint_manager"
    BEHAVIOR_ENGINE = "behavior_engine"
    ENVIRONMENT_SPOOFING = "environment_spoofing"
    ANTI_DETECTION_MANAGER = "anti_detection_manager"


@dataclass
class ComponentConfig:
    """组件配置"""
    component_type: ComponentType
    implementation: str
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    priority: int = 50
    dependencies: List[str] = field(default_factory=list)
    
    # 工厂配置
    singleton: bool = True
    lazy_init: bool = False
    auto_inject: bool = True
    
    # 生命周期配置
    auto_start: bool = True
    timeout: float = 30.0
    retry_count: int = 3


@dataclass
class ComponentBlueprint:
    """组件蓝图"""
    name: str
    component_type: ComponentType
    factory_class: Type['ComponentFactory']
    default_config: ComponentConfig
    description: str = ""
    version: str = "1.0.0"
    
    def create_config(self, overrides: Dict[str, Any] = None) -> ComponentConfig:
        """创建配置实例"""
        config_dict = {
            'component_type': self.component_type,
            'implementation': self.name,
            'config': self.default_config.config.copy(),
            'enabled': self.default_config.enabled,
            'priority': self.default_config.priority,
            'dependencies': self.default_config.dependencies.copy(),
            'singleton': self.default_config.singleton,
            'lazy_init': self.default_config.lazy_init,
            'auto_inject': self.default_config.auto_inject,
            'auto_start': self.default_config.auto_start,
            'timeout': self.default_config.timeout,
            'retry_count': self.default_config.retry_count
        }
        
        if overrides:
            config_dict.update(overrides)
        
        return ComponentConfig(**config_dict)


class ComponentFactory(Generic[T], ABC):
    """
    组件工厂基类
    
    提供统一的组件创建接口和生命周期管理
    """
    
    def __init__(self, registry: Optional[PluginRegistry] = None):
        self.registry = registry or PluginRegistry.get_instance()
        self.instances: Dict[str, T] = {}
        self.configs: Dict[str, ComponentConfig] = {}
        self.blueprints: Dict[str, ComponentBlueprint] = {}
        self._lock = asyncio.Lock()
        
    @abstractmethod
    def get_component_type(self) -> ComponentType:
        """获取组件类型"""
        pass
    
    @abstractmethod
    def get_default_implementation(self) -> str:
        """获取默认实现"""
        pass
    
    @abstractmethod
    async def create_component_instance(self, config: ComponentConfig) -> T:
        """创建组件实例"""
        pass
    
    def register_blueprint(self, blueprint: ComponentBlueprint):
        """注册组件蓝图"""
        self.blueprints[blueprint.name] = blueprint
        logger.debug(f"Registered blueprint: {blueprint.name}")
    
    async def create_component(self, 
                             implementation: str = None,
                             config_overrides: Dict[str, Any] = None,
                             instance_id: str = None) -> T:
        """
        创建组件实例
        
        Args:
            implementation: 实现名称
            config_overrides: 配置覆盖
            instance_id: 实例ID
            
        Returns:
            T: 组件实例
        """
        async with self._lock:
            # 确定实现
            if not implementation:
                implementation = self.get_default_implementation()
            
            # 确定实例ID
            if not instance_id:
                instance_id = f"{self.get_component_type().value}_{implementation}"
            
            # 检查单例
            blueprint = self.blueprints.get(implementation)
            if blueprint and blueprint.default_config.singleton:
                if instance_id in self.instances:
                    logger.debug(f"Returning existing singleton instance: {instance_id}")
                    return self.instances[instance_id]
            
            # 创建配置
            if blueprint:
                config = blueprint.create_config(config_overrides)
            else:
                config = ComponentConfig(
                    component_type=self.get_component_type(),
                    implementation=implementation,
                    config=config_overrides or {}
                )
            
            # 创建实例
            try:
                instance = await self.create_component_instance(config)
                
                # 缓存实例和配置
                self.instances[instance_id] = instance
                self.configs[instance_id] = config
                
                logger.info(f"Created component instance: {instance_id}")
                return instance
                
            except Exception as e:
                logger.error(f"Failed to create component {instance_id}: {e}")
                raise
    
    async def get_or_create_component(self, 
                                    implementation: str = None,
                                    config_overrides: Dict[str, Any] = None,
                                    instance_id: str = None) -> T:
        """获取或创建组件实例"""
        if not implementation:
            implementation = self.get_default_implementation()
        
        if not instance_id:
            instance_id = f"{self.get_component_type().value}_{implementation}"
        
        if instance_id in self.instances:
            return self.instances[instance_id]
        
        return await self.create_component(implementation, config_overrides, instance_id)
    
    async def destroy_component(self, instance_id: str) -> bool:
        """销毁组件实例"""
        async with self._lock:
            if instance_id not in self.instances:
                return True
            
            try:
                instance = self.instances[instance_id]
                
                # 停止实例
                if hasattr(instance, 'stop'):
                    await instance.stop()
                
                # 移除缓存
                del self.instances[instance_id]
                if instance_id in self.configs:
                    del self.configs[instance_id]
                
                logger.info(f"Destroyed component instance: {instance_id}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to destroy component {instance_id}: {e}")
                return False
    
    def list_instances(self) -> Dict[str, Dict[str, Any]]:
        """列出所有实例"""
        return {
            instance_id: {
                'instance': instance,
                'config': self.configs.get(instance_id),
                'status': getattr(instance, 'status', None),
                'type': type(instance).__name__
            }
            for instance_id, instance in self.instances.items()
        }


class DetectorFactory(ComponentFactory[IDetectionPlugin]):
    """检测器工厂"""
    
    def get_component_type(self) -> ComponentType:
        return ComponentType.DETECTOR
    
    def get_default_implementation(self) -> str:
        return "unified_captcha_detector"
    
    async def create_component_instance(self, config: ComponentConfig) -> IDetectionPlugin:
        """创建检测器实例"""
        implementation = config.implementation
        
        if implementation == "unified_captcha_detector":
            from .unified_captcha_detector import UnifiedCaptchaDetector
            return UnifiedCaptchaDetector(**config.config)
        
        elif implementation == "captcha_detector":
            from .captcha_detector import CaptchaDetector
            return CaptchaDetector(config.config)
        
        else:
            # 尝试从插件注册表获取
            plugin = get_plugin(implementation)
            if plugin and isinstance(plugin, IDetectionPlugin):
                return plugin
            
            raise ValueError(f"Unknown detector implementation: {implementation}")


class SessionFactory(ComponentFactory[ISessionPlugin]):
    """会话管理器工厂"""
    
    def get_component_type(self) -> ComponentType:
        return ComponentType.SESSION_MANAGER
    
    def get_default_implementation(self) -> str:
        return "enhanced_session_manager"
    
    async def create_component_instance(self, config: ComponentConfig) -> ISessionPlugin:
        """创建会话管理器实例"""
        implementation = config.implementation
        
        if implementation == "enhanced_session_manager":
            from ..scrapers.enhanced_session_manager import EnhancedSessionManager
            from ..scrapers.enhanced_session_manager import SessionConfig
            
            # 转换配置
            session_config = SessionConfig(**config.config)
            return EnhancedSessionManager(session_config)
        
        elif implementation == "session_manager":
            from ..scrapers.session_manager import SessionManager
            return SessionManager(**config.config)
        
        else:
            # 尝试从插件注册表获取
            plugin = get_plugin(implementation)
            if plugin and isinstance(plugin, ISessionPlugin):
                return plugin
            
            raise ValueError(f"Unknown session manager implementation: {implementation}")


class FingerprintFactory(ComponentFactory[IFingerprintPlugin]):
    """指纹管理器工厂"""
    
    def get_component_type(self) -> ComponentType:
        return ComponentType.FINGERPRINT_MANAGER
    
    def get_default_implementation(self) -> str:
        return "enhanced_fingerprint_manager"
    
    async def create_component_instance(self, config: ComponentConfig) -> IFingerprintPlugin:
        """创建指纹管理器实例"""
        implementation = config.implementation
        
        if implementation == "enhanced_fingerprint_manager":
            from ..scrapers.enhanced_fingerprint_manager import EnhancedFingerprintManager
            return EnhancedFingerprintManager(config.config)
        
        elif implementation == "browser_fingerprint_manager":
            from ..scrapers.browser_fingerprint_manager import BrowserFingerprintManager
            from ..scrapers.browser_fingerprint_manager import FingerprintConfig
            
            fingerprint_config = FingerprintConfig(**config.config)
            return BrowserFingerprintManager(fingerprint_config)
        
        else:
            # 尝试从插件注册表获取
            plugin = get_plugin(implementation)
            if plugin and isinstance(plugin, IFingerprintPlugin):
                return plugin
            
            raise ValueError(f"Unknown fingerprint manager implementation: {implementation}")


class BehaviorFactory(ComponentFactory[IBehaviorPlugin]):
    """行为引擎工厂"""
    
    def get_component_type(self) -> ComponentType:
        return ComponentType.BEHAVIOR_ENGINE
    
    def get_default_implementation(self) -> str:
        return "enhanced_behavior_engine"
    
    async def create_component_instance(self, config: ComponentConfig) -> IBehaviorPlugin:
        """创建行为引擎实例"""
        implementation = config.implementation
        
        if implementation == "enhanced_behavior_engine":
            from ..scrapers.enhanced_behavior_engine import EnhancedBehaviorEngine
            return EnhancedBehaviorEngine(config.config)
        
        elif implementation == "behavior_simulation_engine":
            from ..scrapers.behavior_simulation_engine import BehaviorSimulationEngine
            from ..scrapers.behavior_simulation_engine import BehaviorConfig
            
            behavior_config = BehaviorConfig(**config.config)
            return BehaviorSimulationEngine(behavior_config)
        
        else:
            # 尝试从插件注册表获取
            plugin = get_plugin(implementation)
            if plugin and isinstance(plugin, IBehaviorPlugin):
                return plugin
            
            raise ValueError(f"Unknown behavior engine implementation: {implementation}")


class EnvironmentFactory(ComponentFactory[IEnvironmentPlugin]):
    """环境伪装工厂"""
    
    def get_component_type(self) -> ComponentType:
        return ComponentType.ENVIRONMENT_SPOOFING
    
    def get_default_implementation(self) -> str:
        return "browser_environment_spoofing"
    
    async def create_component_instance(self, config: ComponentConfig) -> IEnvironmentPlugin:
        """创建环境伪装实例"""
        implementation = config.implementation
        
        if implementation == "browser_environment_spoofing":
            from ..scrapers.browser_environment_spoofing import BrowserEnvironmentSpoofing
            return BrowserEnvironmentSpoofing(config.config)
        
        else:
            # 尝试从插件注册表获取
            plugin = get_plugin(implementation)
            if plugin and isinstance(plugin, IEnvironmentPlugin):
                return plugin
            
            raise ValueError(f"Unknown environment spoofing implementation: {implementation}")


class ComponentManager:
    """
    组件管理器
    
    统一管理所有组件工厂，提供高级的组件装配和管理功能
    """
    
    def __init__(self):
        self.factories: Dict[ComponentType, ComponentFactory] = {}
        self.global_config: Dict[str, Any] = {}
        self.component_instances: Dict[str, IAntiDetectionPlugin] = {}
        
        # 初始化内置工厂
        self._initialize_builtin_factories()
        
        # 注册内置蓝图
        self._register_builtin_blueprints()
    
    def _initialize_builtin_factories(self):
        """初始化内置工厂"""
        self.factories[ComponentType.DETECTOR] = DetectorFactory()
        self.factories[ComponentType.SESSION_MANAGER] = SessionFactory()
        self.factories[ComponentType.FINGERPRINT_MANAGER] = FingerprintFactory()
        self.factories[ComponentType.BEHAVIOR_ENGINE] = BehaviorFactory()
        self.factories[ComponentType.ENVIRONMENT_SPOOFING] = EnvironmentFactory()
    
    def _register_builtin_blueprints(self):
        """注册内置蓝图"""
        # 检测器蓝图
        detector_factory = self.factories[ComponentType.DETECTOR]
        detector_factory.register_blueprint(ComponentBlueprint(
            name="unified_captcha_detector",
            component_type=ComponentType.DETECTOR,
            factory_class=DetectorFactory,
            default_config=ComponentConfig(
                component_type=ComponentType.DETECTOR,
                implementation="unified_captcha_detector",
                config={
                    'confidence_threshold': 0.6,
                    'enable_context_analysis': True,
                    'enable_debug_logging': False,
                    'max_processing_time': 30.0
                }
            ),
            description="统一验证码检测器",
            version="2.0.0"
        ))
        
        # 会话管理器蓝图
        session_factory = self.factories[ComponentType.SESSION_MANAGER]
        session_factory.register_blueprint(ComponentBlueprint(
            name="enhanced_session_manager",
            component_type=ComponentType.SESSION_MANAGER,
            factory_class=SessionFactory,
            default_config=ComponentConfig(
                component_type=ComponentType.SESSION_MANAGER,
                implementation="enhanced_session_manager",
                config={
                    'max_concurrent_sessions': 3,
                    'session_timeout': 1800,
                    'idle_timeout': 300,
                    'max_requests_per_session': 1000,
                    'max_retries': 3,
                    'connection_timeout': 30.0,
                    'read_timeout': 60.0
                }
            ),
            description="增强会话管理器",
            version="2.0.0"
        ))
        
        # 指纹管理器蓝图
        fingerprint_factory = self.factories[ComponentType.FINGERPRINT_MANAGER]
        fingerprint_factory.register_blueprint(ComponentBlueprint(
            name="enhanced_fingerprint_manager",
            component_type=ComponentType.FINGERPRINT_MANAGER,
            factory_class=FingerprintFactory,
            default_config=ComponentConfig(
                component_type=ComponentType.FINGERPRINT_MANAGER,
                implementation="enhanced_fingerprint_manager",
                config={
                    'pool_size': 100,
                    'rotation_interval': 1800,
                    'max_usage_count': 50,
                    'enable_user_agent_rotation': True,
                    'enable_webgl_spoofing': True,
                    'enable_canvas_spoofing': True
                }
            ),
            description="增强指纹管理器",
            version="2.0.0"
        ))
        
        # 行为引擎蓝图
        behavior_factory = self.factories[ComponentType.BEHAVIOR_ENGINE]
        behavior_factory.register_blueprint(ComponentBlueprint(
            name="enhanced_behavior_engine",
            component_type=ComponentType.BEHAVIOR_ENGINE,
            factory_class=BehaviorFactory,
            default_config=ComponentConfig(
                component_type=ComponentType.BEHAVIOR_ENGINE,
                implementation="enhanced_behavior_engine",
                config={
                    'enable_mouse_simulation': True,
                    'enable_keyboard_simulation': True,
                    'enable_scroll_simulation': True,
                    'enable_adaptive_timing': True,
                    'humanization_level': 0.8
                }
            ),
            description="增强行为引擎",
            version="2.0.0"
        ))
        
        # 环境伪装蓝图
        env_factory = self.factories[ComponentType.ENVIRONMENT_SPOOFING]
        env_factory.register_blueprint(ComponentBlueprint(
            name="browser_environment_spoofing",
            component_type=ComponentType.ENVIRONMENT_SPOOFING,
            factory_class=EnvironmentFactory,
            default_config=ComponentConfig(
                component_type=ComponentType.ENVIRONMENT_SPOOFING,
                implementation="browser_environment_spoofing",
                config={
                    'spoofing_level': 'standard',
                    'enable_timezone_spoofing': True,
                    'enable_language_spoofing': True,
                    'enable_webrtc_spoofing': True
                }
            ),
            description="浏览器环境伪装",
            version="1.0.0"
        ))
    
    def register_factory(self, component_type: ComponentType, factory: ComponentFactory):
        """注册组件工厂"""
        self.factories[component_type] = factory
        logger.info(f"Registered factory for {component_type.value}")
    
    async def create_component(self, 
                             component_type: ComponentType,
                             implementation: str = None,
                             config_overrides: Dict[str, Any] = None,
                             instance_id: str = None) -> IAntiDetectionPlugin:
        """创建组件"""
        factory = self.factories.get(component_type)
        if not factory:
            raise ValueError(f"No factory registered for {component_type.value}")
        
        return await factory.create_component(implementation, config_overrides, instance_id)
    
    async def create_component_suite(self, 
                                   suite_config: Dict[ComponentType, Dict[str, Any]]) -> Dict[ComponentType, IAntiDetectionPlugin]:
        """创建组件套件"""
        components = {}
        
        # 按依赖关系排序创建
        creation_order = [
            ComponentType.DETECTOR,
            ComponentType.SESSION_MANAGER,
            ComponentType.FINGERPRINT_MANAGER,
            ComponentType.ENVIRONMENT_SPOOFING,
            ComponentType.BEHAVIOR_ENGINE
        ]
        
        for component_type in creation_order:
            if component_type in suite_config:
                config = suite_config[component_type]
                components[component_type] = await self.create_component(
                    component_type=component_type,
                    **config
                )
        
        return components
    
    def get_factory(self, component_type: ComponentType) -> Optional[ComponentFactory]:
        """获取组件工厂"""
        return self.factories.get(component_type)
    
    def list_components(self) -> Dict[ComponentType, Dict[str, Any]]:
        """列出所有组件"""
        result = {}
        for component_type, factory in self.factories.items():
            result[component_type] = factory.list_instances()
        return result
    
    async def destroy_all_components(self):
        """销毁所有组件"""
        for factory in self.factories.values():
            for instance_id in list(factory.instances.keys()):
                await factory.destroy_component(instance_id)


# 全局组件管理器
component_manager = ComponentManager()


# 便捷函数
async def create_detector(implementation: str = None, **config) -> IDetectionPlugin:
    """创建检测器的便捷函数"""
    return await component_manager.create_component(
        ComponentType.DETECTOR, implementation, config
    )


async def create_session_manager(implementation: str = None, **config) -> ISessionPlugin:
    """创建会话管理器的便捷函数"""
    return await component_manager.create_component(
        ComponentType.SESSION_MANAGER, implementation, config
    )


async def create_fingerprint_manager(implementation: str = None, **config) -> IFingerprintPlugin:
    """创建指纹管理器的便捷函数"""
    return await component_manager.create_component(
        ComponentType.FINGERPRINT_MANAGER, implementation, config
    )


async def create_behavior_engine(implementation: str = None, **config) -> IBehaviorPlugin:
    """创建行为引擎的便捷函数"""
    return await component_manager.create_component(
        ComponentType.BEHAVIOR_ENGINE, implementation, config
    )


async def create_environment_spoofing(implementation: str = None, **config) -> IEnvironmentPlugin:
    """创建环境伪装的便捷函数"""
    return await component_manager.create_component(
        ComponentType.ENVIRONMENT_SPOOFING, implementation, config
    )


# 装饰器函数
def component_factory(component_type: ComponentType):
    """组件工厂装饰器"""
    def decorator(cls):
        # 自动注册工厂
        if issubclass(cls, ComponentFactory):
            factory_instance = cls()
            component_manager.register_factory(component_type, factory_instance)
        return cls
    return decorator


def injectable_component(component_type: ComponentType, implementation: str = None):
    """可注入组件装饰器"""
    def decorator(cls):
        # 标记为可注入组件
        cls._component_type = component_type
        cls._implementation_name = implementation or cls.__name__.lower()
        
        # 自动注册到对应工厂
        factory = component_manager.get_factory(component_type)
        if factory:
            blueprint = ComponentBlueprint(
                name=cls._implementation_name,
                component_type=component_type,
                factory_class=type(factory),
                default_config=ComponentConfig(
                    component_type=component_type,
                    implementation=cls._implementation_name
                ),
                description=cls.__doc__ or "",
                version="1.0.0"
            )
            factory.register_blueprint(blueprint)
        
        return cls
    return decorator