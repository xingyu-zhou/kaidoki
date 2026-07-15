#!/usr/bin/env python3
"""
依赖检查测试脚本

检查项目依赖是否正确安装和可用
"""

import sys
import importlib
from pathlib import Path

def test_core_dependencies():
    """测试核心依赖"""
    print("🔍 测试核心依赖...")
    
    results = []
    
    # 核心Python库
    core_deps = [
        ('json', 'JSON处理'),
        ('os', '操作系统接口'),
        ('sys', '系统接口'),
        ('pathlib', '路径处理'),
        ('typing', '类型提示'),
        ('datetime', '日期时间'),
        ('logging', '日志记录'),
        ('asyncio', '异步编程'),
        ('dataclasses', '数据类'),
        ('enum', '枚举类型'),
        ('re', '正则表达式'),
    ]
    
    for module_name, description in core_deps:
        try:
            importlib.import_module(module_name)
            results.append(f"✅ {module_name} ({description})")
        except ImportError:
            results.append(f"❌ {module_name} ({description}) - 导入失败")
    
    return results

def test_web_framework_dependencies():
    """测试Web框架依赖"""
    print("🔍 测试Web框架依赖...")
    
    results = []
    
    web_deps = [
        ('fastapi', 'FastAPI框架'),
        ('pydantic', 'Pydantic数据验证'),
        ('uvicorn', 'ASGI服务器'),
        ('starlette', 'Starlette框架'),
    ]
    
    for module_name, description in web_deps:
        try:
            importlib.import_module(module_name)
            results.append(f"✅ {module_name} ({description})")
        except ImportError:
            results.append(f"❌ {module_name} ({description}) - 未安装")
    
    return results

def test_http_client_dependencies():
    """测试HTTP客户端依赖"""
    print("🔍 测试HTTP客户端依赖...")
    
    results = []
    
    http_deps = [
        ('requests', 'HTTP请求库'),
        ('httpx', '异步HTTP客户端'),
        ('aiohttp', '异步HTTP库'),
    ]
    
    for module_name, description in http_deps:
        try:
            importlib.import_module(module_name)
            results.append(f"✅ {module_name} ({description})")
        except ImportError:
            results.append(f"❌ {module_name} ({description}) - 未安装")
    
    return results

def test_scraping_dependencies():
    """测试爬虫依赖"""
    print("🔍 测试爬虫依赖...")
    
    results = []
    
    scraping_deps = [
        ('bs4', 'Beautiful Soup'),
        ('lxml', 'XML/HTML解析'),
        ('selenium', 'Web自动化'),
        ('fake_useragent', '用户代理伪装'),
    ]
    
    for module_name, description in scraping_deps:
        try:
            importlib.import_module(module_name)
            results.append(f"✅ {module_name} ({description})")
        except ImportError:
            results.append(f"❌ {module_name} ({description}) - 未安装")
    
    return results

def test_ai_dependencies():
    """测试AI相关依赖"""
    print("🔍 测试AI相关依赖...")
    
    results = []
    
    ai_deps = [
        ('openai', 'OpenAI API客户端'),
        ('anthropic', 'Anthropic API客户端'),
    ]
    
    for module_name, description in ai_deps:
        try:
            importlib.import_module(module_name)
            results.append(f"✅ {module_name} ({description})")
        except ImportError:
            results.append(f"❌ {module_name} ({description}) - 未安装")
    
    return results

def test_data_processing_dependencies():
    """测试数据处理依赖"""
    print("🔍 测试数据处理依赖...")
    
    results = []
    
    data_deps = [
        ('yaml', 'YAML处理'),
        ('toml', 'TOML处理'),
        ('orjson', '快速JSON处理'),
    ]
    
    for module_name, description in data_deps:
        try:
            importlib.import_module(module_name)
            results.append(f"✅ {module_name} ({description})")
        except ImportError:
            results.append(f"❌ {module_name} ({description}) - 未安装")
    
    return results

def test_cli_dependencies():
    """测试CLI依赖"""
    print("🔍 测试CLI依赖...")
    
    results = []
    
    cli_deps = [
        ('click', 'CLI框架'),
        ('rich', '富文本输出'),
    ]
    
    for module_name, description in cli_deps:
        try:
            importlib.import_module(module_name)
            results.append(f"✅ {module_name} ({description})")
        except ImportError:
            results.append(f"❌ {module_name} ({description}) - 未安装")
    
    return results

def test_logging_dependencies():
    """测试日志依赖"""
    print("🔍 测试日志依赖...")
    
    results = []
    
    logging_deps = [
        ('loguru', 'Loguru日志库'),
    ]
    
    for module_name, description in logging_deps:
        try:
            importlib.import_module(module_name)
            results.append(f"✅ {module_name} ({description})")
        except ImportError:
            results.append(f"❌ {module_name} ({description}) - 未安装")
    
    return results

def test_optional_dependencies():
    """测试可选依赖"""
    print("🔍 测试可选依赖...")
    
    results = []
    
    optional_deps = [
        ('psutil', '系统监控'),
        ('redis', 'Redis客户端'),
        ('sqlalchemy', 'ORM框架'),
        ('PIL', '图像处理'),
        ('numpy', '数值计算'),
        ('pandas', '数据分析'),
    ]
    
    for module_name, description in optional_deps:
        try:
            importlib.import_module(module_name)
            results.append(f"✅ {module_name} ({description})")
        except ImportError:
            results.append(f"⚠️ {module_name} ({description}) - 可选，未安装")
    
    return results

def check_python_version():
    """检查Python版本"""
    print("🔍 检查Python版本...")
    
    results = []
    
    version = sys.version_info
    results.append(f"✅ Python版本: {version.major}.{version.minor}.{version.micro}")
    
    # 检查版本要求
    if version >= (3, 11):
        results.append("✅ Python版本满足要求 (>=3.11)")
    elif version >= (3, 9):
        results.append("⚠️ Python版本可能工作但建议升级到3.11+")
    else:
        results.append("❌ Python版本过低，需要3.11+")
    
    return results

def main():
    """主函数"""
    print("🚀 Mercari AI Agent 依赖检查测试")
    print("=" * 60)
    
    # 切换到项目目录
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root / "src"))
    
    all_results = []
    
    # 运行测试
    test_functions = [
        check_python_version,
        test_core_dependencies,
        test_web_framework_dependencies,
        test_http_client_dependencies,
        test_scraping_dependencies,
        test_ai_dependencies,
        test_data_processing_dependencies,
        test_cli_dependencies,
        test_logging_dependencies,
        test_optional_dependencies,
    ]
    
    for test_func in test_functions:
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
    
    print("=" * 60)
    print("📊 依赖检查结果摘要:")
    print(f"✅ 可用: {passed}")
    print(f"❌ 缺失: {failed}")
    print(f"⚠️ 警告: {warnings}")
    print(f"📊 总计: {len(all_results)}")
    
    # 计算成功率
    critical_count = sum(1 for r in all_results if (r.startswith("✅") or r.startswith("❌")))
    success_rate = (passed / critical_count * 100) if critical_count > 0 else 0
    
    print(f"🎯 关键依赖成功率: {success_rate:.1f}%")
    
    # 评估结果
    if failed == 0:
        print("🎉 所有关键依赖都已安装!")
        status = "PASS"
    elif success_rate >= 80:
        print("⚠️ 大部分依赖已安装，少数缺失不影响核心功能")
        status = "PARTIAL"
    else:
        print("🚨 关键依赖缺失，需要安装")
        status = "FAIL"
    
    # 生成安装建议
    if failed > 0:
        print("\n📝 安装建议:")
        print("pip install -r requirements.txt")
        print("或者:")
        print("pip install -e .")
    
    return 0 if status != "FAIL" else 1

if __name__ == "__main__":
    sys.exit(main())