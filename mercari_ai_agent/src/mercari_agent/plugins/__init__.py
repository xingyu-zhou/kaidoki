"""
统一模块化插件架构

该模块提供了一个完整的插件框架，支持：
- 所有反检测组件的插件化
- 插件的动态加载和热插拔
- 统一的生命周期管理
- 插件配置管理和版本控制
- Schema验证和配置模板生成
- 配置热加载和实时监控
- 插件间的松耦合通信

架构设计：
- 基于现有plugin_interface.py和plugin_registry.py
- 扩展到所有反检测组件
- 保持向后兼容性
- 支持热插拔和动态加载

Author: Mercari AI Agent Team
"""

from .framework import PluginFramework
from .interfaces import (
    IPlugin, 
    ISessionManagementPlugin,
    IFingerprintPlugin,
    IBehaviorSimulationPlugin,
    IAntiDetectionPlugin,
    ICaptchaDetectionPlugin
)
from .registry import PluginRegistry
from .loader import PluginLoader
from .lifecycle import PluginLifecycleManager
from .config_manager import PluginConfigManager

# Schema验证和配置模板
from .schemas import (
    SchemaValidator, ConfigTemplateGenerator,
    validate_plugin_config, get_plugin_default_config,
    generate_plugin_template, get_schema_validator, get_template_generator,
    PLUGIN_SCHEMAS, SCHEMA_METADATA
)

# 版本控制和兼容性检查
from .version_control import (
    PluginVersionManager, SemanticVersion, VersionConstraint,
    PluginVersionInfo, PluginDependency, VersionConstraintType,
    VersionCompatibility, UpgradeStrategy, get_version_manager
)

# 重新导出核心插件接口（向后兼容）
from ..captcha.plugin_interface import (
    IAntiDetectionPlugin as BaseAntiDetectionPlugin,
    PluginStatus,
    PluginPriority,
    PluginCategory,
    PluginMetadata,
    PluginEvent,
    anti_detection_plugin
)

__all__ = [
    # 核心框架
    'PluginFramework',
    'PluginRegistry',
    'PluginLoader',
    'PluginLifecycleManager',
    'PluginConfigManager',
    
    # Schema验证和配置
    'SchemaValidator', 'ConfigTemplateGenerator',
    'validate_plugin_config', 'get_plugin_default_config',
    'generate_plugin_template', 'get_schema_validator', 'get_template_generator',
    'PLUGIN_SCHEMAS', 'SCHEMA_METADATA',
    
    # 版本控制和兼容性
    'PluginVersionManager', 'SemanticVersion', 'VersionConstraint',
    'PluginVersionInfo', 'PluginDependency', 'VersionConstraintType',
    'VersionCompatibility', 'UpgradeStrategy', 'get_version_manager',
    
    # 插件接口
    'IPlugin',
    'ISessionManagementPlugin',
    'IFingerprintPlugin',
    'IBehaviorSimulationPlugin',
    'IAntiDetectionPlugin',
    'ICaptchaDetectionPlugin',
    
    # 向后兼容
    'BaseAntiDetectionPlugin',
    'PluginStatus',
    'PluginPriority',
    'PluginCategory',
    'PluginMetadata',
    'PluginEvent',
    'anti_detection_plugin'
]

# 版本信息
__version__ = "1.0.0"
__author__ = "Mercari AI Agent Team"