"""
向后兼容性保证模块

该模块提供完整的向后兼容性支持，确保现有代码在新的插件化架构下正常工作。

核心功能：
- API兼容性适配器
- 方法迁移和重定向
- 弃用警告管理
- 自动配置迁移
- 行为保持一致性
- 渐进式迁移支持

设计原则：
- 100%向后兼容
- 零破坏性变更
- 渐进式迁移路径
- 清晰的迁移指南
- 性能影响最小化

Author: Mercari AI Agent Team
"""

import asyncio
import logging
import warnings
import functools
from typing import Dict, List, Optional, Any, Union, Callable, Type
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .enhanced_anti_detection_manager import EnhancedAntiDetectionManager, get_enhanced_anti_detection_manager
from .unified_config_manager import UnifiedConfigManager, config_manager
from .plugin_registry import PluginRegistry, registry
from .component_factory import component_manager
from ..utils.logger import get_logger

logger = get_logger(__name__)


class DeprecationLevel(Enum):
    """弃用级别"""
    INFO = "info"           # 信息性弃用，功能仍然完全可用
    WARNING = "warning"     # 警告级弃用，建议迁移
    DEPRECATED = "deprecated" # 正式弃用，将在未来版本移除
    CRITICAL = "critical"   # 关键弃用，强烈建议立即迁移


@dataclass
class DeprecationInfo:
    """弃用信息"""
    feature: str
    level: DeprecationLevel
    since_version: str
    removal_version: Optional[str] = None
    replacement: Optional[str] = None
    migration_guide: Optional[str] = None
    reason: str = ""
    
    def get_message(self) -> str:
        """获取弃用消息"""
        msg = f"{self.feature} is {self.level.value}"
        if self.since_version:
            msg += f" since version {self.since_version}"
        if self.removal_version:
            msg += f" and will be removed in version {self.removal_version}"
        if self.replacement:
            msg += f". Use {self.replacement} instead"
        if self.migration_guide:
            msg += f". Migration guide: {self.migration_guide}"
        if self.reason:
            msg += f". Reason: {self.reason}"
        return msg


class DeprecationManager:
    """弃用管理器"""
    
    def __init__(self):
        self.deprecations: Dict[str, DeprecationInfo] = {}
        self.warned_features: set = set()
        self.warning_enabled = True
        self.strict_mode = False
        
        # 注册内置弃用信息
        self._register_builtin_deprecations()
    
    def register_deprecation(self, deprecation: DeprecationInfo):
        """注册弃用信息"""
        self.deprecations[deprecation.feature] = deprecation
        logger.debug(f"Registered deprecation: {deprecation.feature}")
    
    def warn_if_deprecated(self, feature: str, stacklevel: int = 2):
        """如果功能被弃用，发出警告"""
        if not self.warning_enabled:
            return
        
        if feature in self.deprecations and feature not in self.warned_features:
            deprecation = self.deprecations[feature]
            message = deprecation.get_message()
            
            if self.strict_mode and deprecation.level in [DeprecationLevel.DEPRECATED, DeprecationLevel.CRITICAL]:
                raise DeprecationWarning(message)
            
            if deprecation.level == DeprecationLevel.INFO:
                logger.info(message)
            elif deprecation.level == DeprecationLevel.WARNING:
                warnings.warn(message, UserWarning, stacklevel=stacklevel)
            elif deprecation.level == DeprecationLevel.DEPRECATED:
                warnings.warn(message, DeprecationWarning, stacklevel=stacklevel)
            elif deprecation.level == DeprecationLevel.CRITICAL:
                warnings.warn(message, FutureWarning, stacklevel=stacklevel)
            
            self.warned_features.add(feature)
    
    def _register_builtin_deprecations(self):
        """注册内置弃用信息"""
        # 示例弃用信息
        self.register_deprecation(DeprecationInfo(
            feature="AntiDetectionManager.direct_instantiation",
            level=DeprecationLevel.INFO,
            since_version="2.0.0",
            replacement="get_enhanced_anti_detection_manager()",
            migration_guide="Replace direct instantiation with factory function",
            reason="Enhanced version provides better plugin support"
        ))
        
        self.register_deprecation(DeprecationInfo(
            feature="legacy_session_manager_import",
            level=DeprecationLevel.WARNING,
            since_version="2.0.0",
            replacement="unified_session_manager",
            migration_guide="Import from unified_session_manager module",
            reason="Unified interface reduces code duplication"
        ))


# 全局弃用管理器
deprecation_manager = DeprecationManager()


def deprecated(
    since: str = None,
    removal: str = None,
    replacement: str = None,
    reason: str = "",
    level: DeprecationLevel = DeprecationLevel.WARNING
):
    """弃用装饰器"""
    def decorator(func):
        feature_name = f"{func.__module__}.{func.__qualname__}"
        
        # 注册弃用信息
        deprecation_manager.register_deprecation(DeprecationInfo(
            feature=feature_name,
            level=level,
            since_version=since,
            removal_version=removal,
            replacement=replacement,
            reason=reason
        ))
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            deprecation_manager.warn_if_deprecated(feature_name, stacklevel=2)
            return func(*args, **kwargs)
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            deprecation_manager.warn_if_deprecated(feature_name, stacklevel=2)
            return await func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper
    
    return decorator


class LegacyAntiDetectionManager:
    """
    遗留反检测管理器兼容性包装器
    
    提供与原始AntiDetectionManager完全相同的API，
    内部使用增强版本实现，确保向后兼容性。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化兼容性包装器
        
        Args:
            config: 配置字典
        """
        # 发出兼容性提示
        deprecation_manager.warn_if_deprecated("AntiDetectionManager.direct_instantiation")
        
        # 内部使用增强版本
        self._enhanced_manager = EnhancedAntiDetectionManager(config)
        
        # 保持原始属性引用
        self.config = self._enhanced_manager.config
        self.status = self._enhanced_manager.status
        self.mode = self._enhanced_manager.mode
        self.stats = self._enhanced_manager.stats
        self.metrics_history = self._enhanced_manager.metrics_history
        self.error_history = self._enhanced_manager.error_history
        self.confidence_threshold = self._enhanced_manager.confidence_threshold
        self.max_retry_attempts = self._enhanced_manager.max_retry_attempts
        self.request_interval_range = self._enhanced_manager.request_interval_range
        self.monitoring_tasks = self._enhanced_manager.monitoring_tasks
        self.start_time = self._enhanced_manager.start_time
        self.event_callbacks = self._enhanced_manager.event_callbacks
        
        # 组件引用
        self.unified_detector = self._enhanced_manager.unified_detector
        self.session_manager = self._enhanced_manager.session_manager
        self.fingerprint_manager = self._enhanced_manager.fingerprint_manager
        self.environment_spoofing = self._enhanced_manager.environment_spoofing
        self.behavior_engine = self._enhanced_manager.behavior_engine
        
        logger.debug("LegacyAntiDetectionManager initialized with EnhancedAntiDetectionManager")
    
    # ========================
    # 原始API方法的完全兼容实现
    # ========================
    
    async def initialize(self):
        """初始化系统（兼容性方法）"""
        return await self._enhanced_manager.initialize()
    
    async def start(self):
        """启动系统（兼容性方法）"""
        return await self._enhanced_manager.start()
    
    async def stop(self):
        """停止系统（兼容性方法）"""
        return await self._enhanced_manager.stop()
    
    async def detect_captcha(self, content: str, response: Optional[Any] = None, url: Optional[str] = None):
        """检测CAPTCHA（兼容性方法）"""
        return await self._enhanced_manager.detect_captcha(content, response, url)
    
    async def handle_captcha_detected(self, detection_result) -> bool:
        """处理检测到的CAPTCHA（兼容性方法）"""
        return await self._enhanced_manager.handle_captcha_detected(detection_result)
    
    async def get_optimized_session(self, url: str):
        """获取优化的会话（兼容性方法）"""
        return await self._enhanced_manager.get_optimized_session(url)
    
    async def execute_with_anti_detection(self, func: Callable, *args, **kwargs):
        """使用反检测机制执行函数（兼容性方法）"""
        return await self._enhanced_manager.execute_with_anti_detection(func, *args, **kwargs)
    
    def update_config(self, new_config: Dict[str, Any]):
        """更新配置（兼容性方法）"""
        return self._enhanced_manager.update_config(new_config)
    
    def get_system_stats(self) -> Dict[str, Any]:
        """获取系统统计信息（兼容性方法）"""
        return self._enhanced_manager.get_system_stats()
    
    def register_event_callback(self, event_type: str, callback: Callable):
        """注册事件回调（兼容性方法）"""
        return self._enhanced_manager.register_event_callback(event_type, callback)
    
    def _load_default_config(self) -> Dict[str, Any]:
        """加载默认配置（兼容性方法）"""
        return self._enhanced_manager._load_default_config()
    
    def _start_monitoring_tasks(self):
        """启动监控任务（兼容性方法）"""
        return self._enhanced_manager._start_monitoring_tasks()
    
    async def _stop_monitoring_tasks(self):
        """停止监控任务（兼容性方法）"""
        return await self._enhanced_manager._stop_monitoring_tasks()
    
    def _cleanup_old_metrics(self):
        """清理旧的指标数据（兼容性方法）"""
        return self._enhanced_manager._cleanup_old_metrics()
    
    def _record_error(self, error: Exception, context: Dict[str, Any]):
        """记录错误（兼容性方法）"""
        return self._enhanced_manager._record_error(error, context)
    
    async def _trigger_event_callbacks(self, event_type: str, data: Dict[str, Any]):
        """触发事件回调（兼容性方法）"""
        return await self._enhanced_manager._trigger_event_callbacks(event_type, data)


class ConfigMigrator:
    """配置迁移器"""
    
    def __init__(self):
        self.migration_rules: Dict[str, Callable] = {}
        self.version_mappings: Dict[str, str] = {}
        
        # 注册内置迁移规则
        self._register_builtin_migrations()
    
    def register_migration(self, from_path: str, to_path: str, transformer: Callable = None):
        """注册配置迁移规则"""
        if transformer is None:
            transformer = lambda x: x  # 默认不变换
        
        self.migration_rules[from_path] = transformer
        self.version_mappings[from_path] = to_path
        
        logger.debug(f"Registered migration: {from_path} -> {to_path}")
    
    def migrate_config(self, old_config: Dict[str, Any]) -> Dict[str, Any]:
        """迁移配置"""
        new_config = {}
        
        for old_path, value in self._flatten_dict(old_config).items():
            if old_path in self.version_mappings:
                new_path = self.version_mappings[old_path]
                transformer = self.migration_rules.get(old_path, lambda x: x)
                
                try:
                    new_value = transformer(value)
                    self._set_nested_value(new_config, new_path, new_value)
                    logger.debug(f"Migrated config: {old_path} -> {new_path}")
                except Exception as e:
                    logger.error(f"Failed to migrate config {old_path}: {e}")
                    # 使用原始值
                    self._set_nested_value(new_config, old_path, value)
            else:
                # 保持原有配置
                self._set_nested_value(new_config, old_path, value)
        
        return new_config
    
    def _register_builtin_migrations(self):
        """注册内置迁移规则"""
        # 示例：旧的配置路径迁移到新的路径
        self.register_migration(
            "captcha_detector.threshold",
            "detector.confidence_threshold"
        )
        
        self.register_migration(
            "session.max_connections",
            "session_management.max_sessions"
        )
        
        self.register_migration(
            "fingerprint.enabled",
            "fingerprint_management.enabled"
        )
        
        # 复杂迁移：将旧的布尔值转换为新的字符串值
        self.register_migration(
            "global.strict_mode",
            "global.mode",
            lambda x: "strict" if x else "balanced"
        )
    
    def _flatten_dict(self, d: Dict[str, Any], parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
        """扁平化字典"""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep).items())
            else:
                items.append((new_key, v))
        return dict(items)
    
    def _set_nested_value(self, d: Dict[str, Any], path: str, value: Any):
        """设置嵌套字典值"""
        keys = path.split('.')
        current = d
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value


class CompatibilityAdapter:
    """兼容性适配器"""
    
    def __init__(self):
        self.migrator = ConfigMigrator()
        self.legacy_managers: Dict[str, LegacyAntiDetectionManager] = {}
    
    def get_legacy_manager(self, config: Optional[Dict[str, Any]] = None) -> LegacyAntiDetectionManager:
        """获取遗留管理器实例"""
        # 配置迁移
        if config:
            config = self.migrator.migrate_config(config)
        
        # 创建或获取实例
        config_key = str(hash(str(config))) if config else "default"
        
        if config_key not in self.legacy_managers:
            self.legacy_managers[config_key] = LegacyAntiDetectionManager(config)
        
        return self.legacy_managers[config_key]
    
    def create_legacy_session_manager(self, config: Dict[str, Any] = None):
        """创建遗留会话管理器"""
        deprecation_manager.warn_if_deprecated("legacy_session_manager_import")
        
        from .unified_session_manager import create_unified_session_manager, UnifiedSessionConfig
        
        if config:
            # 配置迁移
            migrated_config = self.migrator.migrate_config(config)
            unified_config = UnifiedSessionConfig(**migrated_config)
        else:
            unified_config = UnifiedSessionConfig()
        
        return create_unified_session_manager("enhanced", unified_config)
    
    def wrap_legacy_detector(self, detector):
        """包装遗留检测器"""
        class LegacyDetectorWrapper:
            def __init__(self, detector):
                self._detector = detector
            
            async def detect_captcha(self, content: str, response=None, url=None):
                # 调用原始检测器方法
                if hasattr(self._detector, 'detect_captcha'):
                    return await self._detector.detect_captcha(content, response, url)
                elif hasattr(self._detector, 'detect_unified'):
                    return await self._detector.detect_unified(content, response, url)
                else:
                    raise NotImplementedError("Detector does not implement detection method")
        
        return LegacyDetectorWrapper(detector)


# 全局兼容性适配器
compatibility_adapter = CompatibilityAdapter()


# ========================
# 兼容性工厂函数
# ========================

def get_anti_detection_manager(config: Optional[Dict[str, Any]] = None):
    """
    获取反检测管理器实例（兼容性函数）
    
    这个函数提供与原始函数相同的接口，但内部使用增强版本
    """
    return compatibility_adapter.get_legacy_manager(config)


async def initialize_anti_detection_system(config: Optional[Dict[str, Any]] = None):
    """
    初始化反检测系统（兼容性函数）
    
    Args:
        config: 配置字典
    """
    manager = get_anti_detection_manager(config)
    await manager.initialize()
    await manager.start()
    
    logger.info("Anti-detection system initialized and started (legacy compatibility mode)")


async def shutdown_anti_detection_system():
    """关闭反检测系统（兼容性函数）"""
    # 关闭所有遗留管理器
    for manager in compatibility_adapter.legacy_managers.values():
        await manager.stop()
    
    compatibility_adapter.legacy_managers.clear()
    
    logger.info("Anti-detection system shutdown (legacy compatibility mode)")


# ========================
# 兼容性导入重定向
# ========================

class LegacyImportRedirect:
    """遗留导入重定向"""
    
    def __init__(self, new_module: str, new_class: str, migration_guide: str = ""):
        self.new_module = new_module
        self.new_class = new_class
        self.migration_guide = migration_guide
    
    def __call__(self, *args, **kwargs):
        # 发出迁移警告
        message = f"Importing from legacy location. Use {self.new_module}.{self.new_class} instead."
        if self.migration_guide:
            message += f" Migration guide: {self.migration_guide}"
        
        warnings.warn(message, DeprecationWarning, stacklevel=2)
        
        # 动态导入新模块
        module = __import__(self.new_module, fromlist=[self.new_class])
        new_class = getattr(module, self.new_class)
        
        return new_class(*args, **kwargs)


# ========================
# 兼容性类型别名
# ========================

# 为了完全兼容，我们需要确保所有原始类型都可用
try:
    from .anti_detection_manager import DetectionMode, SystemStatus, AntiDetectionStats, RequestMetrics
    from .captcha_types import CaptchaType, CaptchaDetectionResult
    from .unified_captcha_detector import UnifiedDetectionResult
    
    # 创建类型别名以确保兼容性
    LegacyDetectionMode = DetectionMode
    LegacySystemStatus = SystemStatus
    LegacyAntiDetectionStats = AntiDetectionStats
    LegacyRequestMetrics = RequestMetrics
    LegacyCaptchaType = CaptchaType
    LegacyCaptchaDetectionResult = CaptchaDetectionResult
    LegacyUnifiedDetectionResult = UnifiedDetectionResult
    
except ImportError as e:
    logger.warning(f"Could not import legacy types: {e}")
    
    # 创建兼容性存根
    class LegacyDetectionMode:
        pass
    
    class LegacySystemStatus:
        pass


# ========================
# 兼容性测试工具
# ========================

class CompatibilityTester:
    """兼容性测试工具"""
    
    def __init__(self):
        self.test_results: Dict[str, bool] = {}
    
    async def test_api_compatibility(self) -> Dict[str, bool]:
        """测试API兼容性"""
        tests = {
            "manager_creation": self._test_manager_creation,
            "initialization": self._test_initialization,
            "captcha_detection": self._test_captcha_detection,
            "session_management": self._test_session_management,
            "configuration": self._test_configuration,
            "event_callbacks": self._test_event_callbacks
        }
        
        for test_name, test_func in tests.items():
            try:
                result = await test_func()
                self.test_results[test_name] = result
                logger.info(f"Compatibility test {test_name}: {'PASSED' if result else 'FAILED'}")
            except Exception as e:
                self.test_results[test_name] = False
                logger.error(f"Compatibility test {test_name} failed: {e}")
        
        return self.test_results
    
    async def _test_manager_creation(self) -> bool:
        """测试管理器创建"""
        try:
            # 测试原始方式创建
            manager = get_anti_detection_manager()
            return manager is not None
        except Exception as e:
            logger.error(f"Manager creation test failed: {e}")
            return False
    
    async def _test_initialization(self) -> bool:
        """测试初始化"""
        try:
            manager = get_anti_detection_manager()
            await manager.initialize()
            await manager.start()
            await manager.stop()
            return True
        except Exception as e:
            logger.error(f"Initialization test failed: {e}")
            return False
    
    async def _test_captcha_detection(self) -> bool:
        """测试验证码检测"""
        try:
            manager = get_anti_detection_manager()
            await manager.initialize()
            await manager.start()
            
            # 测试检测方法
            result = await manager.detect_captcha("<html></html>")
            
            await manager.stop()
            return result is not None
        except Exception as e:
            logger.error(f"Captcha detection test failed: {e}")
            return False
    
    async def _test_session_management(self) -> bool:
        """测试会话管理"""
        try:
            manager = get_anti_detection_manager()
            await manager.initialize()
            await manager.start()
            
            # 测试会话获取
            session = await manager.get_optimized_session("https://example.com")
            
            await manager.stop()
            return session is not None
        except Exception as e:
            logger.error(f"Session management test failed: {e}")
            return False
    
    async def _test_configuration(self) -> bool:
        """测试配置"""
        try:
            config = {"global": {"mode": "balanced"}}
            manager = get_anti_detection_manager(config)
            
            # 测试配置更新
            manager.update_config({"global": {"mode": "strict"}})
            
            # 测试统计获取
            stats = manager.get_system_stats()
            
            return stats is not None
        except Exception as e:
            logger.error(f"Configuration test failed: {e}")
            return False
    
    async def _test_event_callbacks(self) -> bool:
        """测试事件回调"""
        try:
            manager = get_anti_detection_manager()
            
            callback_called = False
            
            def test_callback(data):
                nonlocal callback_called
                callback_called = True
            
            # 注册回调
            manager.register_event_callback("captcha_detected", test_callback)
            
            return True  # 注册成功即可
        except Exception as e:
            logger.error(f"Event callbacks test failed: {e}")
            return False


# 全局兼容性测试器
compatibility_tester = CompatibilityTester()


# ========================
# 兼容性帮助函数
# ========================

def get_migration_guide() -> str:
    """获取迁移指南"""
    return """
    反检测系统迁移指南 (v1.x -> v2.x)
    
    1. 管理器创建
       旧: AntiDetectionManager(config)
       新: get_enhanced_anti_detection_manager(config)
    
    2. 会话管理
       旧: 直接导入 EnhancedSessionManager
       新: 使用 unified_session_manager.create_unified_session_manager()
    
    3. 配置管理
       旧: 手动管理配置字典
       新: 使用 unified_config_manager.config_manager
    
    4. 插件系统
       新功能: 使用 plugin_registry.register_plugin() 注册插件
       新功能: 使用 component_factory.create_* 创建组件
    
    5. 向后兼容
       所有旧API仍然可用，但会发出弃用警告
       建议逐步迁移到新API
    
    详细迁移指南请参考文档。
    """


def check_compatibility() -> Dict[str, Any]:
    """检查兼容性状态"""
    return {
        "version": "2.0.0",
        "legacy_support": True,
        "migration_available": True,
        "deprecation_warnings": deprecation_manager.warning_enabled,
        "strict_mode": deprecation_manager.strict_mode,
        "warned_features": list(deprecation_manager.warned_features),
        "migration_guide": get_migration_guide()
    }


def enable_strict_deprecation_mode():
    """启用严格弃用模式"""
    deprecation_manager.strict_mode = True
    logger.info("Strict deprecation mode enabled")


def disable_deprecation_warnings():
    """禁用弃用警告"""
    deprecation_manager.warning_enabled = False
    logger.info("Deprecation warnings disabled")


def enable_deprecation_warnings():
    """启用弃用警告"""
    deprecation_manager.warning_enabled = True
    logger.info("Deprecation warnings enabled")


# ========================
# 兼容性版本别名
# ========================

# 为了完全兼容，创建原始模块的别名
AntiDetectionManager = LegacyAntiDetectionManager