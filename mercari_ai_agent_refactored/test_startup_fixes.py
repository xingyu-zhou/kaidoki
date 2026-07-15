#!/usr/bin/env python3
"""
启动修复测试脚本

验证核心启动问题的修复效果。

Author: Mercari AI Agent Team (Refactored)
"""

import sys
import os
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_path))

def test_config_loading():
    """测试配置加载"""
    print("🔧 测试配置加载...")
    
    try:
        from mercari_agent.shared.config.app_config import AppConfig, get_config
        
        # 测试配置初始化
        config = get_config()
        print(f"✅ 配置加载成功: {config}")
        
        # 测试新添加的方法
        has_openai = config.has_openai_config()
        has_anthropic = config.has_anthropic_config()
        has_azure = config.has_azure_config()
        
        print(f"✅ OpenAI 配置: {'已配置' if has_openai else '未配置'}")
        print(f"✅ Anthropic 配置: {'已配置' if has_anthropic else '未配置'}")
        print(f"✅ Azure 配置: {'已配置' if has_azure else '未配置'}")
        
        return True
        
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return False

def test_llm_service_import():
    """测试LLM服务导入"""
    print("\n🤖 测试LLM服务导入...")
    
    try:
        from mercari_agent.infrastructure.llm.llm_service import LLMService
        print("✅ LLMService 导入成功")
        
        # 测试初始化
        from mercari_agent.shared.config.app_config import get_config
        config = get_config()
        llm_service = LLMService(config)
        print("✅ LLMService 初始化成功")
        
        return True
        
    except Exception as e:
        print(f"❌ LLM服务导入失败: {e}")
        return False

def test_dependencies():
    """测试依赖导入"""
    print("\n📦 测试依赖导入...")
    
    dependencies = [
        ("CacheManager", "mercari_agent.infrastructure.storage.cache.cache_manager"),
        ("ToolRegistry", "mercari_agent.tools.framework.tool_registry"),
        ("BaseTool", "mercari_agent.tools.framework.base_tool"),
        ("logger_utils", "mercari_agent.shared.utils.logger_utils"),
    ]
    
    success_count = 0
    for dep_name, module_path in dependencies:
        try:
            module = __import__(module_path, fromlist=[dep_name])
            getattr(module, dep_name.split('.')[-1] if '.' in dep_name else dep_name)
            print(f"✅ {dep_name}: 导入成功")
            success_count += 1
        except Exception as e:
            print(f"❌ {dep_name}: 导入失败 - {e}")
    
    return success_count == len(dependencies)

def test_directory_structure():
    """测试目录结构"""
    print("\n📁 测试目录结构...")
    
    required_dirs = [
        "data",
        "data/logs", 
        "data/cache",
        "logs",
        "src/mercari_agent/shared/exceptions"
    ]
    
    success_count = 0
    for dir_path in required_dirs:
        full_path = project_root / dir_path
        if full_path.exists():
            print(f"✅ {dir_path}: 存在")
            success_count += 1
        else:
            print(f"❌ {dir_path}: 不存在")
    
    return success_count == len(required_dirs)

def test_exception_files():
    """测试异常文件"""
    print("\n🚨 测试异常文件...")
    
    try:
        from mercari_agent.shared.exceptions.config_exceptions import (
            ConfigurationError,
            ConfigValidationError,
            MissingConfigError
        )
        print("✅ 配置异常类导入成功")
        
        # 测试异常创建
        error = ConfigurationError("测试异常")
        print(f"✅ 异常创建成功: {error}")
        
        return True
        
    except Exception as e:
        print(f"❌ 异常文件测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始启动修复验证测试...\n")
    
    # 运行所有测试
    tests = [
        ("目录结构", test_directory_structure),
        ("异常文件", test_exception_files),
        ("配置加载", test_config_loading),
        ("依赖导入", test_dependencies),
        ("LLM服务导入", test_llm_service_import),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"{'='*50}")
        result = test_func()
        results.append((test_name, result))
        print(f"{'='*50}\n")
    
    # 汇总结果
    print("📊 测试结果汇总:")
    passed = 0
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 总计: {passed}/{len(tests)} 个测试通过")
    
    if passed == len(tests):
        print("🎉 所有启动修复验证测试通过！")
        return 0
    else:
        print("⚠️  部分测试失败，需要进一步修复。")
        return 1

if __name__ == '__main__':
    sys.exit(main())