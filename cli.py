#!/usr/bin/env python3
"""
Mercari AI Agent CLI 入口脚本

简化的CLI入口，用于快速访问主要功能。

使用方法:
    python cli.py search "iPhone 13"
    python cli.py parse "安い iPhone"
    python cli.py status
    python cli.py config

Author: Mercari AI Agent Team (Refactored)
"""

import sys
import os
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 导入CLI主模块
try:
    from src.mercari_agent.interfaces.cli.main import cli
    
    if __name__ == '__main__':
        cli()
except ImportError as e:
    print(f"❌ 导入CLI模块失败: {e}")
    print("请确保已安装所有依赖包")
    sys.exit(1)