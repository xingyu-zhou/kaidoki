#!/usr/bin/env python3
"""
Mercari AI Agent - 主启动脚本

标准化的启动入口，解决导入路径问题并提供统一的启动接口。

使用方法:
  python main.py search --query "iPhone 15 Pro Max 1TB 10万円以下"
  python main.py status
  python main.py config
  python main.py test

Author: Mercari AI Agent Team (Refactored)
"""

import sys
import os
from pathlib import Path

# 添加项目根目录和src目录到Python路径
project_root = Path(__file__).parent
src_path = project_root / "src"

# 确保路径存在
if not src_path.exists():
    print(f"错误: 源代码目录不存在: {src_path}")
    sys.exit(1)

# 添加到Python路径
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_path))

# 设置环境变量
os.environ.setdefault('PYTHONPATH', f"{project_root}:{src_path}")

def main():
    """主入口函数"""
    try:
        # 导入CLI模块
        from mercari_agent.interfaces.cli.main import cli
        
        # 启动CLI
        cli()
        
    except ImportError as e:
        print(f"导入错误: {e}")
        print("请确保所有依赖都已安装：")
        print("  pip install -r requirements.txt")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n程序被用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"启动失败: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()