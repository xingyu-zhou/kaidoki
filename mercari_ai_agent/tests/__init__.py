"""
测试模块

该模块包含系统的所有测试代码。
包括单元测试、集成测试和端到端测试。

测试结构：
- unit/: 单元测试
- integration/: 集成测试
- e2e/: 端到端测试
- fixtures/: 测试装置
- utils/: 测试工具

Author: Mercari AI Agent Team
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 测试配置
TEST_CONFIG = {
    "test_data_dir": project_root / "tests" / "data",
    "test_cache_dir": project_root / "tests" / "cache",
    "test_logs_dir": project_root / "tests" / "logs",
}

# 创建测试目录
for dir_path in TEST_CONFIG.values():
    dir_path.mkdir(parents=True, exist_ok=True)