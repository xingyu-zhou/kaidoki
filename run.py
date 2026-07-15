#!/usr/bin/env python3
"""
快速启动脚本 - 简化版本

使用方法:
  python run.py          # 默认搜索
  python run.py status    # 检查状态
  python run.py config    # 显示配置

Author: Kaidoki Team (Refactored)
"""

import sys
import subprocess
from pathlib import Path

def main():
    """主入口函数"""
    project_root = Path(__file__).parent
    main_script = project_root / "main.py"
    
    if not main_script.exists():
        print(f"错误: 主脚本不存在: {main_script}")
        sys.exit(1)
    
    # 获取命令行参数
    args = sys.argv[1:] if len(sys.argv) > 1 else ["search"]
    
    # 构建完整命令
    cmd = [sys.executable, str(main_script)] + args
    
    try:
        # 执行命令
        result = subprocess.run(cmd, cwd=project_root)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\n程序被用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"启动失败: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()