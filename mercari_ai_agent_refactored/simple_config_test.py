#!/usr/bin/env python3
"""
简化版配置验证测试

快速验证基础配置功能
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

def test_basic_imports():
    """测试基础导入"""
    print("🔍 测试基础导入...")
    
    results = []
    
    # 测试异常模块
    try:
        from mercari_agent.shared.exceptions.base import MercariAgentException
        results.append("✅ 基础异常模块导入成功")
    except Exception as e:
        results.append(f"❌ 基础异常模块导入失败: {e}")
    
    # 测试配置模块
    try:
        from mercari_agent.shared.config.app_config import AppConfig
        results.append("✅ 配置模块导入成功")
    except Exception as e:
        results.append(f"❌ 配置模块导入失败: {e}")
    
    # 测试环境变量
    try:
        config = AppConfig()
        results.append("✅ 配置对象创建成功")
        results.append(f"   环境: {config.environment.value}")
        results.append(f"   调试模式: {config.debug}")
    except Exception as e:
        results.append(f"❌ 配置对象创建失败: {e}")
    
    return results

def test_env_file():
    """测试.env文件"""
    print("🔍 测试.env文件...")
    
    results = []
    
    env_file = project_root / ".env"
    if env_file.exists():
        results.append("✅ .env文件存在")
        
        # 读取内容
        with open(env_file, 'r') as f:
            content = f.read()
            
        # 检查关键配置
        key_configs = ['ENVIRONMENT', 'DEBUG', 'OPENAI_API_KEY', 'LOG_LEVEL']
        found_configs = []
        
        for key in key_configs:
            if key in content:
                found_configs.append(key)
        
        results.append(f"✅ 找到配置项: {', '.join(found_configs)}")
        
        if len(found_configs) >= 3:
            results.append("✅ 基础配置充足")
        else:
            results.append("⚠️ 部分配置缺失")
    else:
        results.append("❌ .env文件不存在")
    
    return results

def test_directory_structure():
    """测试目录结构"""
    print("🔍 测试目录结构...")
    
    results = []
    
    # 检查关键目录
    key_dirs = [
        "src/mercari_agent",
        "src/mercari_agent/shared",
        "src/mercari_agent/shared/config",
        "src/mercari_agent/shared/exceptions",
        "src/mercari_agent/application",
        "src/mercari_agent/infrastructure",
        "src/mercari_agent/interfaces",
        "data/logs"
    ]
    
    existing_dirs = []
    missing_dirs = []
    
    for dir_path in key_dirs:
        full_path = project_root / dir_path
        if full_path.exists():
            existing_dirs.append(dir_path)
        else:
            missing_dirs.append(dir_path)
    
    results.append(f"✅ 存在目录: {len(existing_dirs)}/{len(key_dirs)}")
    
    if missing_dirs:
        results.append(f"⚠️ 缺失目录: {', '.join(missing_dirs)}")
    
    return results

def test_python_environment():
    """测试Python环境"""
    print("🔍 测试Python环境...")
    
    results = []
    
    # Python版本
    results.append(f"✅ Python版本: {sys.version}")
    
    # 路径
    results.append(f"✅ 当前路径: {os.getcwd()}")
    results.append(f"✅ 脚本路径: {project_root}")
    
    # 基础模块
    basic_modules = ['json', 'os', 'sys', 'pathlib', 'typing']
    for module in basic_modules:
        try:
            __import__(module)
            results.append(f"✅ {module} 模块可用")
        except ImportError:
            results.append(f"❌ {module} 模块不可用")
    
    return results

def main():
    """主函数"""
    print("🚀 简化版配置验证测试")
    print("=" * 50)
    
    os.chdir(project_root)
    
    all_results = []
    
    # 运行测试
    tests = [
        test_python_environment,
        test_directory_structure,
        test_env_file,
        test_basic_imports
    ]
    
    for test_func in tests:
        try:
            results = test_func()
            all_results.extend(results)
            for result in results:
                print(result)
            print()
        except Exception as e:
            error_msg = f"❌ 测试失败: {test_func.__name__} - {e}"
            print(error_msg)
            all_results.append(error_msg)
    
    # 统计结果
    passed = sum(1 for r in all_results if r.startswith("✅"))
    failed = sum(1 for r in all_results if r.startswith("❌"))
    warnings = sum(1 for r in all_results if r.startswith("⚠️"))
    
    print("=" * 50)
    print("📊 测试结果:")
    print(f"✅ 通过: {passed}")
    print(f"❌ 失败: {failed}")
    print(f"⚠️ 警告: {warnings}")
    
    if failed == 0:
        print("🎉 基础配置验证通过!")
        return 0
    else:
        print("🚨 存在配置问题，需要修复")
        return 1

if __name__ == "__main__":
    sys.exit(main())