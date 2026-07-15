"""
插件框架测试配置和Fixture

该模块提供了插件框架测试的共享配置和fixture，包括：
- 测试环境设置
- 模拟数据和对象
- 测试工具函数
- 共享的测试fixture

Author: Mercari AI Agent Team
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock
from typing import Dict, Any, Optional, List
from datetime import datetime

# 导入插件框架组件
from mercari_agent.plugins.framework import PluginFramework
from mercari_agent.plugins.interfaces import (
    IPlugin, PluginType, PluginConfiguration, PluginMetadata,
    PluginCapability, PluginState
)
from mercari_agent.plugins.version_control import (
    PluginVersionManager, SemanticVersion, VersionConstraint,
    PluginVersionInfo, PluginDependency
)
from mercari_agent.plugins.config_manager import PluginConfigManager
from mercari_agent.plugins.schemas import SchemaValidator, get_plugin_default_config
from mercari_agent.plugins.registry import PluginRegistry
from mercari_agent.plugins.loader import PluginLoader
from mercari_agent.plugins.lifecycle import PluginLifecycleManager


# 测试数据
TEST_PLUGIN_ID = "test_plugin"
TEST_PLUGIN_VERSION = "1.0.0"
TEST_PLUGIN_TYPE = PluginType.SESSION_MANAGEMENT


@pytest.fixture
def temp_dir():
    """创建临时目录fixture"""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def mock_plugin_config():
    """模拟插件配置"""
    return {
        "enabled": True,
        "priority": "NORMAL",
        "version": "1.0.0",
        "log_level": "INFO",
        "timeout": 30.0,
        "retry_count": 3,
        "health_check_interval": 60.0
    }


@pytest.fixture
def mock_plugin_metadata():
    """模拟插件元数据"""
    return PluginMetadata(
        plugin_id=TEST_PLUGIN_ID,
        name="Test Plugin",
        version=TEST_PLUGIN_VERSION,
        description="Test plugin for unit testing",
        author="Test Author",
        homepage="https://test.com",
        plugin_type=TEST_PLUGIN_TYPE,
        capabilities=[PluginCapability.CONFIGURABLE, PluginCapability.MONITORABLE],
        supported_platforms=["windows", "linux", "macos"],
        min_framework_version="1.0.0",
        max_framework_version="2.0.0"
    )


@pytest.fixture
def mock_plugin_version_info():
    """模拟插件版本信息"""
    return PluginVersionInfo(
        plugin_id=TEST_PLUGIN_ID,
        plugin_type=TEST_PLUGIN_TYPE,
        version=SemanticVersion.parse(TEST_PLUGIN_VERSION),
        description="Test plugin version",
        author="Test Author",
        stability="stable",
        supported_platforms=["windows", "linux", "macos"],
        min_framework_version=SemanticVersion.parse("1.0.0"),
        max_framework_version=SemanticVersion.parse("2.0.0")
    )


class MockPlugin(IPlugin):
    """模拟插件类"""
    
    def __init__(self, plugin_id: str = TEST_PLUGIN_ID, 
                 plugin_type: PluginType = TEST_PLUGIN_TYPE,
                 config: Optional[Dict[str, Any]] = None):
        self.plugin_id = plugin_id
        self.plugin_type = plugin_type
        self.config = config or {}
        self.state = PluginState.INACTIVE
        self.metadata = PluginMetadata(
            plugin_id=plugin_id,
            name=f"Mock {plugin_id}",
            version="1.0.0",
            description="Mock plugin for testing",
            author="Test Suite",
            plugin_type=plugin_type,
            capabilities=[PluginCapability.CONFIGURABLE]
        )
        self.initialize_called = False
        self.start_called = False
        self.stop_called = False
        self.cleanup_called = False
        self.config_reloaded = False
        
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """初始化插件"""
        self.initialize_called = True
        if config:
            self.config.update(config)
        self.state = PluginState.READY
        return True
    
    async def start(self) -> bool:
        """启动插件"""
        self.start_called = True
        self.state = PluginState.ACTIVE
        return True
    
    async def stop(self) -> bool:
        """停止插件"""
        self.stop_called = True
        self.state = PluginState.INACTIVE
        return True
    
    async def cleanup(self) -> bool:
        """清理插件"""
        self.cleanup_called = True
        self.state = PluginState.UNLOADED
        return True
    
    async def reload_config(self, config: Dict[str, Any]) -> bool:
        """重新加载配置"""
        self.config.update(config)
        self.config_reloaded = True
        return True
    
    async def get_status(self) -> Dict[str, Any]:
        """获取插件状态"""
        return {
            "plugin_id": self.plugin_id,
            "state": self.state.value,
            "healthy": True,
            "last_heartbeat": datetime.now().isoformat()
        }
    
    async def health_check(self) -> bool:
        """健康检查"""
        return True


@pytest.fixture
def mock_plugin():
    """模拟插件实例"""
    return MockPlugin()


@pytest.fixture
def mock_plugin_factory():
    """模拟插件工厂"""
    def create_plugin(plugin_id: str = None, 
                     plugin_type: PluginType = None,
                     config: Dict[str, Any] = None) -> MockPlugin:
        return MockPlugin(
            plugin_id=plugin_id or f"test_plugin_{len(plugins)}",
            plugin_type=plugin_type or TEST_PLUGIN_TYPE,
            config=config
        )
    
    plugins = []
    
    def factory(count: int = 1, **kwargs) -> List[MockPlugin]:
        for i in range(count):
            plugin = create_plugin(**kwargs)
            plugins.append(plugin)
        return plugins[-count:] if count > 1 else plugins[-1]
    
    return factory


@pytest.fixture
async def plugin_framework(temp_dir):
    """插件框架实例"""
    framework = PluginFramework()
    await framework.initialize()
    yield framework
    await framework.shutdown()


@pytest.fixture
def plugin_registry():
    """插件注册表实例"""
    registry = PluginRegistry()
    return registry


@pytest.fixture
def plugin_loader():
    """插件加载器实例"""
    loader = PluginLoader()
    return loader


@pytest.fixture
def plugin_lifecycle_manager():
    """插件生命周期管理器实例"""
    lifecycle_manager = PluginLifecycleManager()
    return lifecycle_manager


@pytest.fixture
async def plugin_config_manager(temp_dir):
    """插件配置管理器实例"""
    config_manager = PluginConfigManager()
    config_manager.config_dir = temp_dir / "config"
    config_manager.config_dir.mkdir(exist_ok=True)
    await config_manager.initialize()
    yield config_manager
    await config_manager.stop()


@pytest.fixture
def plugin_version_manager():
    """插件版本管理器实例"""
    version_manager = PluginVersionManager()
    return version_manager


@pytest.fixture
def schema_validator():
    """Schema验证器实例"""
    validator = SchemaValidator()
    return validator


@pytest.fixture
def sample_versions():
    """示例版本数据"""
    return {
        "1.0.0": SemanticVersion.parse("1.0.0"),
        "1.1.0": SemanticVersion.parse("1.1.0"),
        "1.2.0": SemanticVersion.parse("1.2.0"),
        "2.0.0": SemanticVersion.parse("2.0.0"),
        "2.0.0-beta.1": SemanticVersion.parse("2.0.0-beta.1"),
        "2.1.0-alpha.1": SemanticVersion.parse("2.1.0-alpha.1")
    }


@pytest.fixture
def sample_version_constraints():
    """示例版本约束"""
    return {
        "exact": VersionConstraint.parse("==1.0.0"),
        "minimum": VersionConstraint.parse(">=1.0.0"),
        "compatible": VersionConstraint.parse("~=1.0.0"),
        "range": VersionConstraint.parse(">=1.0.0,<2.0.0"),
        "latest": VersionConstraint.parse("*")
    }


@pytest.fixture
def sample_plugin_dependencies():
    """示例插件依赖"""
    return [
        PluginDependency(
            plugin_id="dependency_a",
            plugin_type=PluginType.SESSION_MANAGEMENT,
            version_constraint=VersionConstraint.parse(">=1.0.0"),
            required=True,
            description="Session management dependency"
        ),
        PluginDependency(
            plugin_id="dependency_b",
            plugin_type=PluginType.FINGERPRINT,
            version_constraint=VersionConstraint.parse("~=1.2.0"),
            required=False,
            description="Optional fingerprint dependency"
        )
    ]


@pytest.fixture
def sample_config_schemas():
    """示例配置Schema"""
    return {
        PluginType.SESSION_MANAGEMENT: {
            "type": "object",
            "properties": {
                "max_sessions": {"type": "integer", "minimum": 1, "default": 10},
                "session_timeout": {"type": "number", "minimum": 0, "default": 1800},
                "pool_size": {"type": "integer", "minimum": 1, "default": 5}
            },
            "required": ["max_sessions"]
        },
        PluginType.FINGERPRINT: {
            "type": "object",
            "properties": {
                "max_fingerprints": {"type": "integer", "minimum": 10, "default": 100},
                "rotation_interval": {"type": "number", "minimum": 300, "default": 1800}
            },
            "required": ["max_fingerprints"]
        }
    }


# 测试工具函数
def create_test_config_file(path: Path, content: Dict[str, Any], format: str = "yaml"):
    """创建测试配置文件"""
    import json
    import yaml
    
    path.parent.mkdir(parents=True, exist_ok=True)
    
    if format == "json":
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(content, f, indent=2)
    elif format == "yaml":
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(content, f, default_flow_style=False, indent=2)
    else:
        raise ValueError(f"Unsupported format: {format}")


def assert_plugin_state(plugin: IPlugin, expected_state: PluginState):
    """断言插件状态"""
    assert plugin.state == expected_state, f"Expected {expected_state}, got {plugin.state}"


def assert_config_valid(config: Dict[str, Any], expected_keys: List[str]):
    """断言配置有效性"""
    for key in expected_keys:
        assert key in config, f"Missing required config key: {key}"
    
    for key, value in config.items():
        assert value is not None, f"Config value for {key} is None"


def assert_version_constraint_satisfied(constraint: VersionConstraint, 
                                      version: SemanticVersion,
                                      should_satisfy: bool = True):
    """断言版本约束满足"""
    satisfies = constraint.satisfies(version)
    if should_satisfy:
        assert satisfies, f"Version {version} should satisfy constraint {constraint.specifier}"
    else:
        assert not satisfies, f"Version {version} should not satisfy constraint {constraint.specifier}"


# 异步测试支持
@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# 测试标记
pytest_plugins = ["pytest_asyncio"]


# 自定义pytest标记
def pytest_configure(config):
    """配置pytest标记"""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "slow: Slow tests")
    config.addinivalue_line("markers", "network: Tests requiring network")
    config.addinivalue_line("markers", "filesystem: Tests that access filesystem")