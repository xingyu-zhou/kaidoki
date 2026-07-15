"""
统一插件注册表

该模块实现了统一的插件注册管理机制，扩展了现有的插件注册表功能，提供：
- 统一的插件注册和发现
- 增强的依赖关系管理
- 插件版本兼容性检查
- 动态插件发现
- 插件状态管理
- 性能优化

基于现有的plugin_registry.py，增加了更多高级功能。

Author: Mercari AI Agent Team
"""

import asyncio
import importlib
import inspect
import pkgutil
import sys
from typing import Dict, List, Optional, Any, Type, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from collections import defaultdict
import weakref
import json
import threading
from concurrent.futures import ThreadPoolExecutor
import semantic_version

# 导入基础插件注册表
from ..captcha.plugin_registry import (
    PluginRegistry as BasePluginRegistry,
    PluginRegistration as BasePluginRegistration,
    DependencyResolver,
    PluginEventManager,
    PluginMonitor
)
from .interfaces import IPlugin, PluginType, PluginCapability, PluginConfiguration
from ..captcha.plugin_interface import PluginStatus, PluginPriority, PluginCategory
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PluginRegistration:
    """增强的插件注册信息"""
    plugin_class: Type[IPlugin]
    plugin_config: PluginConfiguration
    instance: Optional[IPlugin] = None
    registration_time: datetime = field(default_factory=datetime.now)
    last_access_time: Optional[datetime] = None
    access_count: int = 0
    auto_start: bool = True
    singleton: bool = True
    
    # 版本信息
    version: str = "1.0.0"
    min_framework_version: str = "1.0.0"
    max_framework_version: str = "2.0.0"
    
    # 插件状态
    status: PluginStatus = PluginStatus.UNINITIALIZED
    health_score: float = 1.0
    error_count: int = 0
    last_error: Optional[str] = None
    
    def create_instance(self, config: Dict[str, Any] = None) -> IPlugin:
        """创建插件实例"""
        if self.singleton and self.instance:
            self.last_access_time = datetime.now()
            self.access_count += 1
            return self.instance
        
        # 合并配置
        merged_config = {}
        merged_config.update(self.plugin_config.runtime_config)
        if config:
            merged_config.update(config)
        
        # 创建实例
        instance = self.plugin_class(merged_config)
        
        if self.singleton:
            self.instance = instance
        
        self.last_access_time = datetime.now()
        self.access_count += 1
        return instance
    
    def update_health_score(self, success: bool):
        """更新健康评分"""
        if success:
            self.health_score = min(1.0, self.health_score + 0.01)
        else:
            self.health_score = max(0.0, self.health_score - 0.1)
            self.error_count += 1


class VersionCompatibilityChecker:
    """版本兼容性检查器"""
    
    @staticmethod
    def is_compatible(plugin_version: str, 
                     framework_version: str,
                     min_framework_version: str = "1.0.0",
                     max_framework_version: str = "2.0.0") -> bool:
        """检查版本兼容性"""
        try:
            framework_ver = semantic_version.Version(framework_version)
            min_ver = semantic_version.Version(min_framework_version)
            max_ver = semantic_version.Version(max_framework_version)
            
            return min_ver <= framework_ver < max_ver
            
        except Exception as e:
            logger.warning(f"Version compatibility check failed: {e}")
            return True  # 默认兼容
    
    @staticmethod
    def get_compatibility_score(plugin_version: str, framework_version: str) -> float:
        """获取兼容性评分"""
        try:
            plugin_ver = semantic_version.Version(plugin_version)
            framework_ver = semantic_version.Version(framework_version)
            
            # 版本越接近，评分越高
            major_diff = abs(plugin_ver.major - framework_ver.major)
            minor_diff = abs(plugin_ver.minor - framework_ver.minor)
            patch_diff = abs(plugin_ver.patch - framework_ver.patch)
            
            score = 1.0 - (major_diff * 0.5 + minor_diff * 0.3 + patch_diff * 0.1)
            return max(0.0, min(1.0, score))
            
        except Exception:
            return 0.5  # 默认评分


class PluginDiscovery:
    """插件发现器"""
    
    def __init__(self):
        self.discovery_paths: List[Path] = []
        self.ignored_patterns: Set[str] = {
            '__pycache__',
            '*.pyc',
            '*.pyo',
            '.git',
            '.svn',
            'node_modules'
        }
    
    def add_discovery_path(self, path: str):
        """添加发现路径"""
        path_obj = Path(path)
        if path_obj.exists():
            self.discovery_paths.append(path_obj)
            logger.info(f"Added plugin discovery path: {path}")
        else:
            logger.warning(f"Plugin discovery path does not exist: {path}")
    
    async def discover_plugins(self) -> List[Type[IPlugin]]:
        """发现插件"""
        discovered_plugins = []
        
        for path in self.discovery_paths:
            try:
                plugins = await self._scan_directory(path)
                discovered_plugins.extend(plugins)
            except Exception as e:
                logger.error(f"Failed to scan directory {path}: {e}")
        
        logger.info(f"Discovered {len(discovered_plugins)} plugins")
        return discovered_plugins
    
    async def _scan_directory(self, directory: Path) -> List[Type[IPlugin]]:
        """扫描目录寻找插件"""
        plugins = []
        
        for python_file in directory.glob("**/*.py"):
            if self._should_ignore_file(python_file):
                continue
            
            try:
                plugin_classes = await self._extract_plugins_from_file(python_file)
                plugins.extend(plugin_classes)
            except Exception as e:
                logger.debug(f"No plugins found in {python_file}: {e}")
        
        return plugins
    
    def _should_ignore_file(self, file_path: Path) -> bool:
        """检查是否应该忽略文件"""
        for pattern in self.ignored_patterns:
            if pattern in str(file_path):
                return True
        return False
    
    async def _extract_plugins_from_file(self, file_path: Path) -> List[Type[IPlugin]]:
        """从文件中提取插件类"""
        plugins = []
        
        # 动态导入模块
        spec = importlib.util.spec_from_file_location("temp_module", file_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 查找插件类
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, IPlugin) and 
                    obj is not IPlugin):
                    plugins.append(obj)
        
        return plugins


class PluginRegistry:
    """
    统一插件注册表
    
    核心功能：
    1. 插件注册和管理
    2. 依赖关系解析
    3. 版本兼容性检查
    4. 动态插件发现
    5. 性能监控和统计
    6. 健康状态管理
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
        
        # 基础注册表（向后兼容）
        self.base_registry = BasePluginRegistry.get_instance()
        
        # 增强功能
        self.registrations: Dict[str, PluginRegistration] = {}
        self.plugin_types: Dict[PluginType, List[str]] = defaultdict(list)
        self.plugin_capabilities: Dict[PluginCapability, List[str]] = defaultdict(list)
        
        # 版本和兼容性管理
        self.framework_version = "1.0.0"
        self.compatibility_checker = VersionCompatibilityChecker()
        
        # 插件发现
        self.discovery = PluginDiscovery()
        
        # 依赖管理（扩展现有）
        self.dependency_resolver = DependencyResolver()
        
        # 事件和监控（复用现有）
        self.event_manager = PluginEventManager()
        self.monitor = PluginMonitor()
        
        # 状态管理
        self.running = False
        self.registry_lock = asyncio.Lock()
        
        # 性能统计
        self.stats = {
            'total_registrations': 0,
            'successful_registrations': 0,
            'failed_registrations': 0,
            'discovery_runs': 0,
            'compatibility_checks': 0,
            'health_checks': 0
        }
        
        logger.info("PluginRegistry initialized")
    
    @classmethod
    def get_instance(cls) -> 'PluginRegistry':
        """获取单例实例"""
        return cls()
    
    async def initialize(self):
        """初始化注册表"""
        async with self.registry_lock:
            if self.running:
                return
            
            try:
                logger.info("Initializing PluginRegistry...")
                
                # 启动基础注册表
                if not self.base_registry.running:
                    await self.base_registry.start_all_plugins()
                
                # 启动事件管理器
                await self.event_manager.start()
                
                # 启动监控器
                await self.monitor.start()
                
                self.running = True
                logger.info("PluginRegistry initialized successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize PluginRegistry: {e}")
                raise
    
    async def register_plugin(self, 
                             plugin_class: Type[IPlugin],
                             plugin_config: Optional[PluginConfiguration] = None,
                             auto_start: bool = True,
                             force_replace: bool = False) -> bool:
        """
        注册插件
        
        Args:
            plugin_class: 插件类
            plugin_config: 插件配置
            auto_start: 是否自动启动
            force_replace: 是否强制替换已存在的插件
            
        Returns:
            bool: 注册是否成功
        """
        try:
            self.stats['total_registrations'] += 1
            
            # 创建临时实例获取配置
            temp_instance = plugin_class()
            if not plugin_config:
                plugin_config = temp_instance.plugin_config
            
            plugin_id = plugin_config.plugin_id
            
            # 检查是否已注册
            if plugin_id in self.registrations and not force_replace:
                logger.warning(f"Plugin {plugin_id} already registered")
                return False
            
            # 版本兼容性检查
            self.stats['compatibility_checks'] += 1
            if not self.compatibility_checker.is_compatible(
                plugin_config.version,
                self.framework_version,
                plugin_config.min_framework_version,
                plugin_config.max_framework_version
            ):
                logger.error(f"Plugin {plugin_id} version {plugin_config.version} is not compatible with framework {self.framework_version}")
                return False
            
            # 创建注册信息
            registration = PluginRegistration(
                plugin_class=plugin_class,
                plugin_config=plugin_config,
                auto_start=auto_start,
                version=plugin_config.version,
                min_framework_version=plugin_config.min_framework_version,
                max_framework_version=plugin_config.max_framework_version
            )
            
            # 注册到基础注册表（向后兼容）
            base_success = self.base_registry.register_plugin(
                plugin_class,
                plugin_id,
                plugin_config.runtime_config,
                auto_start,
                registration.singleton
            )
            
            if not base_success:
                logger.error(f"Failed to register plugin {plugin_id} in base registry")
                return False
            
            # 注册到增强注册表
            self.registrations[plugin_id] = registration
            
            # 更新类型索引
            plugin_type = plugin_config.plugin_type
            if plugin_id not in self.plugin_types[plugin_type]:
                self.plugin_types[plugin_type].append(plugin_id)
            
            # 更新能力索引
            for capability in plugin_config.capabilities:
                if plugin_id not in self.plugin_capabilities[capability]:
                    self.plugin_capabilities[capability].append(plugin_id)
            
            # 更新依赖关系
            for dependency in plugin_config.dependencies:
                self.dependency_resolver.add_dependency(plugin_id, dependency)
            
            self.stats['successful_registrations'] += 1
            logger.info(f"Plugin {plugin_id} registered successfully")
            return True
            
        except Exception as e:
            self.stats['failed_registrations'] += 1
            logger.error(f"Failed to register plugin: {e}")
            return False
    
    async def unregister_plugin(self, plugin_id: str) -> bool:
        """注销插件"""
        try:
            if plugin_id not in self.registrations:
                logger.warning(f"Plugin {plugin_id} not registered")
                return False
            
            registration = self.registrations[plugin_id]
            
            # 检查依赖关系
            if not self.dependency_resolver.can_unload(plugin_id):
                dependents = self.dependency_resolver.get_dependents(plugin_id)
                logger.error(f"Cannot unregister plugin {plugin_id}, still depended by: {dependents}")
                return False
            
            # 从基础注册表注销
            base_success = self.base_registry.unregister_plugin(plugin_id)
            if not base_success:
                logger.warning(f"Failed to unregister plugin {plugin_id} from base registry")
            
            # 清理索引
            plugin_type = registration.plugin_config.plugin_type
            self.plugin_types[plugin_type].remove(plugin_id)
            
            for capability in registration.plugin_config.capabilities:
                self.plugin_capabilities[capability].remove(plugin_id)
            
            # 清理依赖关系
            for dependency in registration.plugin_config.dependencies:
                self.dependency_resolver.remove_dependency(plugin_id, dependency)
            
            # 移除注册
            del self.registrations[plugin_id]
            
            logger.info(f"Plugin {plugin_id} unregistered successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unregister plugin {plugin_id}: {e}")
            return False
    
    async def discover_and_register_plugins(self, 
                                          discovery_paths: List[str] = None) -> int:
        """发现并注册插件"""
        try:
            self.stats['discovery_runs'] += 1
            
            # 添加发现路径
            if discovery_paths:
                for path in discovery_paths:
                    self.discovery.add_discovery_path(path)
            
            # 发现插件
            discovered_plugins = await self.discovery.discover_plugins()
            
            # 注册发现的插件
            registered_count = 0
            for plugin_class in discovered_plugins:
                success = await self.register_plugin(plugin_class)
                if success:
                    registered_count += 1
            
            logger.info(f"Discovered and registered {registered_count} plugins")
            return registered_count
            
        except Exception as e:
            logger.error(f"Failed to discover and register plugins: {e}")
            return 0
    
    def get_plugin_registration(self, plugin_id: str) -> Optional[PluginRegistration]:
        """获取插件注册信息"""
        return self.registrations.get(plugin_id)
    
    def get_plugins_by_type(self, plugin_type: PluginType) -> List[str]:
        """按类型获取插件ID列表"""
        return self.plugin_types.get(plugin_type, []).copy()
    
    def get_plugins_by_capability(self, capability: PluginCapability) -> List[str]:
        """按能力获取插件ID列表"""
        return self.plugin_capabilities.get(capability, []).copy()
    
    def get_plugin_dependencies(self, plugin_id: str) -> Set[str]:
        """获取插件依赖"""
        return self.dependency_resolver.get_dependencies(plugin_id)
    
    def get_plugin_dependents(self, plugin_id: str) -> Set[str]:
        """获取依赖该插件的其他插件"""
        return self.dependency_resolver.get_dependents(plugin_id)
    
    def resolve_load_order(self, plugin_ids: List[str]) -> List[str]:
        """解析加载顺序"""
        return self.dependency_resolver.resolve_load_order(plugin_ids)
    
    async def perform_health_checks(self) -> Dict[str, Dict[str, Any]]:
        """执行健康检查"""
        health_results = {}
        self.stats['health_checks'] += 1
        
        for plugin_id, registration in self.registrations.items():
            try:
                if registration.instance:
                    health_result = await registration.instance.healthcheck()
                    health_results[plugin_id] = health_result
                    
                    # 更新健康评分
                    is_healthy = health_result.get('healthy', False)
                    registration.update_health_score(is_healthy)
                    
                else:
                    health_results[plugin_id] = {
                        'healthy': True,
                        'status': 'not_instantiated'
                    }
                    
            except Exception as e:
                health_results[plugin_id] = {
                    'healthy': False,
                    'error': str(e)
                }
                registration.update_health_score(False)
                registration.last_error = str(e)
        
        return health_results
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """获取注册表统计信息"""
        return {
            'total_plugins': len(self.registrations),
            'plugin_types': {
                plugin_type.value: len(plugin_ids)
                for plugin_type, plugin_ids in self.plugin_types.items()
            },
            'plugin_capabilities': {
                capability.value: len(plugin_ids)
                for capability, plugin_ids in self.plugin_capabilities.items()
            },
            'framework_version': self.framework_version,
            'stats': self.stats.copy(),
            'health_scores': {
                plugin_id: registration.health_score
                for plugin_id, registration in self.registrations.items()
            }
        }
    
    async def stop(self):
        """停止注册表"""
        async with self.registry_lock:
            if not self.running:
                return
            
            try:
                logger.info("Stopping PluginRegistry...")
                
                # 停止监控器
                await self.monitor.stop()
                
                # 停止事件管理器
                await self.event_manager.stop()
                
                # 停止基础注册表
                await self.base_registry.stop_all_plugins()
                
                self.running = False
                logger.info("PluginRegistry stopped")
                
            except Exception as e:
                logger.error(f"Failed to stop PluginRegistry: {e}")
                raise


# 全局注册表实例
_global_registry: Optional[PluginRegistry] = None

def get_registry() -> PluginRegistry:
    """获取全局注册表实例"""
    global _global_registry
    if _global_registry is None:
        _global_registry = PluginRegistry()
    return _global_registry


async def register_plugin(plugin_class: Type[IPlugin], 
                         plugin_config: Optional[PluginConfiguration] = None,
                         auto_start: bool = True) -> bool:
    """全局插件注册函数"""
    registry = get_registry()
    return await registry.register_plugin(plugin_class, plugin_config, auto_start)


async def get_plugin_by_id(plugin_id: str) -> Optional[IPlugin]:
    """按ID获取插件实例"""
    registry = get_registry()
    registration = registry.get_plugin_registration(plugin_id)
    if registration:
        return registration.create_instance()
    return None


async def get_plugins_by_type(plugin_type: PluginType) -> List[IPlugin]:
    """按类型获取插件实例列表"""
    registry = get_registry()
    plugin_ids = registry.get_plugins_by_type(plugin_type)
    
    plugins = []
    for plugin_id in plugin_ids:
        registration = registry.get_plugin_registration(plugin_id)
        if registration:
            plugins.append(registration.create_instance())
    
    return plugins