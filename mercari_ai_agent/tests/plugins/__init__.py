"""
插件框架单元测试

该模块包含插件框架的完整测试套件，覆盖：
- 核心框架组件测试
- 插件接口和生命周期测试
- 版本控制和兼容性测试
- 配置管理和Schema验证测试
- 依赖解析和冲突检测测试
- 性能和稳定性测试

Author: Mercari AI Agent Team
"""

# Test utilities and fixtures
from .conftest import *

# Test modules
from . import (
    test_framework,
    test_interfaces,
    test_version_control,
    test_config_manager,
    test_schemas,
    test_lifecycle,
    test_registry,
    test_loader
)

__version__ = "1.0.0"
__author__ = "Mercari AI Agent Team"