#!/usr/bin/env python3
"""
验证运行器

统一的验证执行入口，可以运行所有验证测试或指定的验证类型。

使用方法:
    python run_validation.py --all                    # 运行所有验证
    python run_validation.py --e2e                    # 运行端到端验证
    python run_validation.py --cli                    # 运行CLI验证
    python run_validation.py --core                   # 运行核心模块验证
    python run_validation.py --parse-test             # 运行解析测试
    python run_validation.py --help                   # 显示帮助

Author: Mercari AI Agent Team
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, List

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def setup_environment():
    """设置环境"""
    # 设置工作目录
    project_dir = Path(__file__).parent.parent
    os.chdir(project_dir)
    
    # 设置Python路径
    src_path = project_dir / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    
    print(f"📁 工作目录: {project_dir}")
    print(f"🐍 Python版本: {sys.version}")
    print(f"📦 Python路径: {sys.path[:3]}...")


async def run_e2e_validation() -> Dict[str, Any]:
    """运行端到端验证"""
    print("\n🔄 启动端到端验证...")
    
    try:
        from e2e_validation import E2EValidator
        
        validator = E2EValidator()
        report = await validator.run_full_validation()
        
        return {
            "success": True,
            "report": report,
            "summary": {
                "total_tests": report.total_tests,
                "passed_tests": report.passed_tests,
                "failed_tests": report.failed_tests,
                "success_rate": report.passed_tests / report.total_tests * 100 if report.total_tests > 0 else 0
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "summary": {
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 1,
                "success_rate": 0
            }
        }


def run_cli_validation() -> Dict[str, Any]:
    """运行CLI验证"""
    print("\n🔄 启动CLI验证...")
    
    try:
        from cli_validation import main as cli_main
        
        # 临时重定向stdout来捕获输出
        import io
        import contextlib
        
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            exit_code = cli_main()
        
        output = f.getvalue()
        
        return {
            "success": exit_code == 0,
            "exit_code": exit_code,
            "output": output,
            "summary": {
                "cli_functional": exit_code == 0,
                "exit_code": exit_code
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "summary": {
                "cli_functional": False,
                "exit_code": -1
            }
        }


async def run_core_module_validation() -> Dict[str, Any]:
    """运行核心模块验证"""
    print("\n🔄 启动核心模块验证...")
    
    try:
        from e2e_validation import E2EValidator
        
        validator = E2EValidator()
        
        # 只运行核心模块验证
        await validator._validate_query_parser()
        await validator._validate_recommendation_engine()
        await validator._validate_output_formatter()
        await validator._validate_llm_service()
        await validator._validate_scraper_service()
        await validator._validate_analysis_service()
        
        # 生成简化报告
        passed = sum(1 for r in validator.results if r.status.value == "passed")
        failed = sum(1 for r in validator.results if r.status.value == "failed")
        total = len(validator.results)
        
        return {
            "success": failed == 0,
            "summary": {
                "total_tests": total,
                "passed_tests": passed,
                "failed_tests": failed,
                "success_rate": passed / total * 100 if total > 0 else 0
            },
            "results": validator.results
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "summary": {
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 1,
                "success_rate": 0
            }
        }


def run_parse_test() -> Dict[str, Any]:
    """运行解析测试 - 验证用户要求的核心功能"""
    print("\n🔄 启动解析功能测试...")
    
    try:
        import subprocess
        
        # 测试解析命令
        result = subprocess.run(
            [sys.executable, "cli.py", "parse", "iPhone 13 Pro 128GB 5万円以下"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        success = result.returncode == 0
        
        return {
            "success": success,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "summary": {
                "parse_command_functional": success,
                "has_output": len(result.stdout.strip()) > 0,
                "no_errors": len(result.stderr.strip()) == 0
            }
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "解析命令超时",
            "summary": {
                "parse_command_functional": False,
                "has_output": False,
                "no_errors": False
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "summary": {
                "parse_command_functional": False,
                "has_output": False,
                "no_errors": False
            }
        }


def print_summary(results: Dict[str, Any]):
    """打印验证摘要"""
    print("\n" + "="*60)
    print("📊 验证结果摘要")
    print("="*60)
    
    total_sections = len(results)
    successful_sections = sum(1 for r in results.values() if r.get("success", False))
    
    print(f"📈 总体结果: {successful_sections}/{total_sections} 验证通过")
    print(f"📊 成功率: {successful_sections/total_sections*100:.1f}%")
    
    print("\n📋 详细结果:")
    for section_name, result in results.items():
        status = "✅ 通过" if result.get("success", False) else "❌ 失败"
        print(f"  {status} {section_name}")
        
        # 显示摘要信息
        if "summary" in result:
            summary = result["summary"]
            for key, value in summary.items():
                if isinstance(value, (int, float)):
                    if "rate" in key or "percentage" in key:
                        print(f"    {key}: {value:.1f}%")
                    else:
                        print(f"    {key}: {value}")
                else:
                    print(f"    {key}: {value}")
        
        # 显示错误信息
        if not result.get("success", False) and "error" in result:
            print(f"    ❌ 错误: {result['error']}")
    
    print("\n" + "="*60)


def save_comprehensive_report(results: Dict[str, Any], output_file: str = None):
    """保存综合报告"""
    if output_file is None:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_file = f"comprehensive_validation_report_{timestamp}.json"
    
    # 准备报告数据
    report_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "validation_results": results,
        "overall_summary": {
            "total_sections": len(results),
            "successful_sections": sum(1 for r in results.values() if r.get("success", False)),
            "failed_sections": sum(1 for r in results.values() if not r.get("success", False)),
            "overall_success_rate": sum(1 for r in results.values() if r.get("success", False)) / len(results) * 100
        }
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"📄 综合报告已保存到: {output_file}")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Mercari AI Agent 验证系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
    python run_validation.py --all          # 运行所有验证
    python run_validation.py --e2e          # 运行端到端验证
    python run_validation.py --cli          # 运行CLI验证
    python run_validation.py --core         # 运行核心模块验证
    python run_validation.py --parse-test   # 运行解析测试
        """
    )
    
    parser.add_argument("--all", action="store_true", help="运行所有验证测试")
    parser.add_argument("--e2e", action="store_true", help="运行端到端验证")
    parser.add_argument("--cli", action="store_true", help="运行CLI验证")
    parser.add_argument("--core", action="store_true", help="运行核心模块验证")
    parser.add_argument("--parse-test", action="store_true", help="运行解析测试")
    parser.add_argument("--output", "-o", help="输出文件路径")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    # 如果没有指定参数，默认运行解析测试
    if not any([args.all, args.e2e, args.cli, args.core, args.parse_test]):
        args.parse_test = True
    
    print("🧪 Mercari AI Agent 验证系统")
    print("=" * 50)
    
    # 设置环境
    setup_environment()
    
    # 收集验证结果
    results = {}
    start_time = time.time()
    
    try:
        # 运行选定的验证
        if args.all or args.parse_test:
            results["parse_test"] = run_parse_test()
        
        if args.all or args.cli:
            results["cli_validation"] = run_cli_validation()
        
        if args.all or args.core:
            results["core_modules"] = await run_core_module_validation()
        
        if args.all or args.e2e:
            results["e2e_validation"] = await run_e2e_validation()
        
        total_time = time.time() - start_time
        
        # 显示结果
        print_summary(results)
        print(f"\n⏱️ 总执行时间: {total_time:.2f}s")
        
        # 保存报告
        save_comprehensive_report(results, args.output)
        
        # 确定退出代码
        all_success = all(r.get("success", False) for r in results.values())
        critical_failures = any(
            not r.get("success", False) and "parse_test" in k 
            for k, r in results.items()
        )
        
        if all_success:
            print("\n🎉 所有验证通过！系统准备就绪。")
            return 0
        elif critical_failures:
            print("\n💥 核心功能验证失败！请检查解析功能。")
            return 2
        else:
            print("\n⚠️ 部分验证失败，但核心功能正常。")
            return 1
    
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断验证")
        return 130
    except Exception as e:
        print(f"\n💥 验证过程异常: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)