#!/usr/bin/env python3
"""
测试运行脚本

该脚本提供了便捷的测试运行方式，支持不同类型的测试。

使用方法：
    python scripts/run_tests.py --help
    python scripts/run_tests.py --unit
    python scripts/run_tests.py --integration
    python scripts/run_tests.py --all
    python scripts/run_tests.py --coverage

Author: Mercari AI Agent Team
"""

import argparse
import os
import sys
import subprocess
from pathlib import Path
from typing import List, Optional

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def run_command(cmd: List[str], cwd: Optional[Path] = None) -> int:
    """运行命令并返回退出码"""
    if cwd is None:
        cwd = PROJECT_ROOT
    
    print(f"运行命令: {' '.join(cmd)}")
    print(f"工作目录: {cwd}")
    print("-" * 50)
    
    try:
        result = subprocess.run(cmd, cwd=cwd, check=False)
        return result.returncode
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        return 1
    except Exception as e:
        print(f"运行命令时出错: {e}")
        return 1

def setup_environment():
    """设置测试环境"""
    # 设置环境变量
    os.environ["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    os.environ["ENVIRONMENT"] = "test"
    
    # 创建必要的目录
    (PROJECT_ROOT / "tests" / "data").mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "tests" / "cache").mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "tests" / "logs").mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "htmlcov").mkdir(parents=True, exist_ok=True)

def install_test_dependencies():
    """安装测试依赖"""
    print("检查测试依赖...")
    
    requirements_file = PROJECT_ROOT / "requirements_test.txt"
    if requirements_file.exists():
        cmd = [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)]
        return run_command(cmd)
    else:
        print("未找到requirements_test.txt，跳过依赖安装")
        return 0

def run_unit_tests():
    """运行单元测试"""
    print("运行单元测试...")
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/unit/",
        "-v",
        "--tb=short",
        "-m", "unit"
    ]
    return run_command(cmd)

def run_integration_tests():
    """运行集成测试"""
    print("运行集成测试...")
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/integration/",
        "-v",
        "--tb=short",
        "-m", "integration"
    ]
    return run_command(cmd)

def run_e2e_tests():
    """运行端到端测试"""
    print("运行端到端测试...")
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/e2e/",
        "-v",
        "--tb=short",
        "-m", "e2e"
    ]
    return run_command(cmd)

def run_all_tests():
    """运行所有测试"""
    print("运行所有测试...")
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--tb=short"
    ]
    return run_command(cmd)

def run_coverage_tests():
    """运行测试并生成覆盖率报告"""
    print("运行测试并生成覆盖率报告...")
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "--cov=mercari_agent",
        "--cov-report=html",
        "--cov-report=term-missing",
        "--cov-report=xml"
    ]
    return run_command(cmd)

def run_performance_tests():
    """运行性能测试"""
    print("运行性能测试...")
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "-m", "performance"
    ]
    return run_command(cmd)

def run_smoke_tests():
    """运行冒烟测试"""
    print("运行冒烟测试...")
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "-m", "smoke"
    ]
    return run_command(cmd)

def run_specific_test(test_path: str):
    """运行特定测试"""
    print(f"运行特定测试: {test_path}")
    cmd = [
        sys.executable, "-m", "pytest",
        test_path,
        "-v",
        "--tb=short"
    ]
    return run_command(cmd)

def run_tests_parallel():
    """并行运行测试"""
    print("并行运行测试...")
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "-n", "auto"
    ]
    return run_command(cmd)

def clean_test_artifacts():
    """清理测试产物"""
    print("清理测试产物...")
    
    # 清理缓存
    cache_dirs = [
        PROJECT_ROOT / "__pycache__",
        PROJECT_ROOT / ".pytest_cache",
        PROJECT_ROOT / "tests" / "__pycache__",
        PROJECT_ROOT / "tests" / "cache",
        PROJECT_ROOT / "htmlcov"
    ]
    
    for cache_dir in cache_dirs:
        if cache_dir.exists():
            import shutil
            shutil.rmtree(cache_dir)
            print(f"已清理: {cache_dir}")
    
    # 清理coverage文件
    coverage_files = [
        PROJECT_ROOT / ".coverage",
        PROJECT_ROOT / "coverage.xml"
    ]
    
    for coverage_file in coverage_files:
        if coverage_file.exists():
            coverage_file.unlink()
            print(f"已清理: {coverage_file}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Mercari AI Agent 测试运行脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python scripts/run_tests.py --unit              # 只运行单元测试
    python scripts/run_tests.py --integration       # 只运行集成测试
    python scripts/run_tests.py --e2e               # 只运行端到端测试
    python scripts/run_tests.py --all               # 运行所有测试
    python scripts/run_tests.py --coverage          # 运行测试并生成覆盖率报告
    python scripts/run_tests.py --performance       # 运行性能测试
    python scripts/run_tests.py --smoke             # 运行冒烟测试
    python scripts/run_tests.py --parallel          # 并行运行测试
    python scripts/run_tests.py --test tests/unit/test_tools.py  # 运行特定测试
    python scripts/run_tests.py --clean             # 清理测试产物
        """
    )
    
    # 测试类型选项
    parser.add_argument("--unit", action="store_true", help="运行单元测试")
    parser.add_argument("--integration", action="store_true", help="运行集成测试")
    parser.add_argument("--e2e", action="store_true", help="运行端到端测试")
    parser.add_argument("--all", action="store_true", help="运行所有测试")
    parser.add_argument("--coverage", action="store_true", help="运行测试并生成覆盖率报告")
    parser.add_argument("--performance", action="store_true", help="运行性能测试")
    parser.add_argument("--smoke", action="store_true", help="运行冒烟测试")
    parser.add_argument("--parallel", action="store_true", help="并行运行测试")
    
    # 其他选项
    parser.add_argument("--test", type=str, help="运行特定测试文件或目录")
    parser.add_argument("--clean", action="store_true", help="清理测试产物")
    parser.add_argument("--install-deps", action="store_true", help="安装测试依赖")
    parser.add_argument("--no-setup", action="store_true", help="跳过环境设置")
    
    args = parser.parse_args()
    
    # 如果没有指定任何选项，显示帮助
    if not any(vars(args).values()):
        parser.print_help()
        return 0
    
    # 设置环境
    if not args.no_setup:
        setup_environment()
    
    # 安装依赖
    if args.install_deps:
        exit_code = install_test_dependencies()
        if exit_code != 0:
            return exit_code
    
    # 清理测试产物
    if args.clean:
        clean_test_artifacts()
        return 0
    
    # 运行测试
    exit_code = 0
    
    if args.unit:
        exit_code = run_unit_tests()
    elif args.integration:
        exit_code = run_integration_tests()
    elif args.e2e:
        exit_code = run_e2e_tests()
    elif args.all:
        exit_code = run_all_tests()
    elif args.coverage:
        exit_code = run_coverage_tests()
    elif args.performance:
        exit_code = run_performance_tests()
    elif args.smoke:
        exit_code = run_smoke_tests()
    elif args.parallel:
        exit_code = run_tests_parallel()
    elif args.test:
        exit_code = run_specific_test(args.test)
    
    # 打印结果
    if exit_code == 0:
        print("\n" + "="*50)
        print("✅ 测试运行成功!")
        print("="*50)
    else:
        print("\n" + "="*50)
        print("❌ 测试运行失败!")
        print("="*50)
    
    return exit_code

if __name__ == "__main__":
    sys.exit(main())