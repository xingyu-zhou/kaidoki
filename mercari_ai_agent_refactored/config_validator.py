#!/usr/bin/env python3
"""
配置验证和修复脚本

验证并修复Mercari AI Agent的配置，确保所有必要的目录和文件存在。

Author: Mercari AI Agent Team (Refactored)
"""

import os
import sys
from pathlib import Path

def create_directories():
    """创建必要的目录结构"""
    project_root = Path(__file__).parent
    
    directories = [
        "data",
        "data/logs",
        "data/cache",
        "data/models",
        "logs",
        "src/mercari_agent/shared/exceptions",
    ]
    
    for dir_name in directories:
        dir_path = project_root / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"✅ 目录已创建: {dir_path}")

def validate_config():
    """验证配置文件"""
    project_root = Path(__file__).parent
    env_file = project_root / ".env"
    
    if not env_file.exists():
        print("❌ .env 文件不存在")
        return False
    
    print("✅ .env 文件存在")
    
    # 检查必要的环境变量
    required_vars = [
        "ENVIRONMENT",
        "OPENAI_API_KEY",
        "LOG_LEVEL",
        "LOG_DIR"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            # 尝试从.env文件读取
            with open(env_file, 'r') as f:
                content = f.read()
                if f"{var}=" not in content:
                    missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ 缺少必要的环境变量: {', '.join(missing_vars)}")
        return False
    
    print("✅ 所有必要的环境变量都已配置")
    return True

def create_missing_files():
    """创建缺失的必要文件"""
    project_root = Path(__file__).parent
    
    # 创建异常文件
    exceptions_dir = project_root / "src/mercari_agent/shared/exceptions"
    exceptions_dir.mkdir(parents=True, exist_ok=True)
    
    config_exceptions_file = exceptions_dir / "config_exceptions.py"
    if not config_exceptions_file.exists():
        config_exceptions_content = '''"""
配置异常模块

定义配置相关的异常类。
"""

class ConfigurationError(Exception):
    """配置错误异常"""
    pass

class ConfigValidationError(ConfigurationError):
    """配置验证错误异常"""
    pass

class MissingConfigError(ConfigurationError):
    """缺失配置错误异常"""
    pass
'''
        with open(config_exceptions_file, 'w', encoding='utf-8') as f:
            f.write(config_exceptions_content)
        print(f"✅ 已创建: {config_exceptions_file}")
    
    # 创建 __init__.py 文件
    init_files = [
        "src/mercari_agent/shared/exceptions/__init__.py",
        "src/mercari_agent/shared/__init__.py",
        "src/mercari_agent/__init__.py",
    ]
    
    for init_file in init_files:
        init_path = project_root / init_file
        init_path.parent.mkdir(parents=True, exist_ok=True)
        if not init_path.exists():
            with open(init_path, 'w', encoding='utf-8') as f:
                f.write('"""初始化模块"""\n')
            print(f"✅ 已创建: {init_path}")

def main():
    """主函数"""
    print("🔧 开始配置验证和修复...")
    
    # 创建目录结构
    print("\n📁 创建目录结构...")
    create_directories()
    
    # 创建缺失文件
    print("\n📄 创建缺失文件...")
    create_missing_files()
    
    # 验证配置
    print("\n⚙️ 验证配置...")
    config_valid = validate_config()
    
    if config_valid:
        print("\n✅ 配置验证通过！")
        return 0
    else:
        print("\n❌ 配置验证失败！")
        print("请检查上述错误并修复后重试。")
        return 1

if __name__ == '__main__':
    sys.exit(main())