#!/usr/bin/env python3
"""
CLI验证脚本

测试实际的CLI命令执行，验证端到端工作流程。
这个脚本专门用于验证用户提到的 `python cli.py parse "iPhone 13 Pro 128GB 5万円以下"` 命令。

Author: Mercari AI Agent Team
"""

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any, List

def run_cli_command(command: List[str], cwd: str = None, timeout: int = 30) -> Dict[str, Any]:
    """
    运行CLI命令并返回结果
    
    Args:
        command: 命令列表
        cwd: 工作目录
        timeout: 超时时间（秒）
        
    Returns:
        Dict[str, Any]: 命令执行结果
    """
    try:
        start_time = time.time()
        
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8'
        )
        
        execution_time = time.time() - start_time
        
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "execution_time": execution_time,
            "command": " ".join(command)
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"命令执行超时 ({timeout}s)",
            "execution_time": timeout,
            "command": " ".join(command)
        }
    except Exception as e:
        return {
            "success": False,
            "returncode": -2,
            "stdout": "",
            "stderr": f"命令执行异常: {e}",
            "execution_time": 0,
            "command": " ".join(command)
        }


def validate_cli_environment() -> Dict[str, Any]:
    """验证CLI环境"""
    print("🔍 验证CLI环境...")
    
    results = {}
    base_dir = Path(__file__).parent.parent
    
    # 检查Python环境
    python_check = run_cli_command([sys.executable, "--version"])
    results["python_version"] = python_check
    print(f"Python版本: {python_check['stdout'].strip() if python_check['success'] else 'Failed'}")
    
    # 检查项目结构
    required_paths = [
        "src/mercari_agent",
        "cli.py",
        "src/mercari_agent/__init__.py"
    ]
    
    path_checks = {}
    for path in required_paths:
        full_path = base_dir / path
        exists = full_path.exists()
        path_checks[path] = exists
        status = "✅" if exists else "❌"
        print(f"{status} {path}: {'存在' if exists else '不存在'}")
    
    results["path_checks"] = path_checks
    
    # 检查CLI脚本
    cli_path = base_dir / "cli.py"
    if cli_path.exists():
        # 检查CLI帮助
        help_check = run_cli_command([sys.executable, "cli.py", "--help"], str(base_dir))
        results["cli_help"] = help_check
        
        if help_check["success"]:
            print("✅ CLI脚本可访问")
        else:
            print("❌ CLI脚本访问失败")
            print(f"错误: {help_check['stderr']}")
    else:
        print("❌ cli.py文件不存在")
        results["cli_help"] = {"success": False, "stderr": "cli.py file not found"}
    
    return results


def test_parse_command() -> Dict[str, Any]:
    """测试解析命令"""
    print("\n📝 测试查询解析命令...")
    
    base_dir = Path(__file__).parent.parent
    test_query = "iPhone 13 Pro 128GB 5万円以下"
    
    # 测试parse命令
    parse_result = run_cli_command(
        [sys.executable, "cli.py", "parse", test_query],
        str(base_dir),
        timeout=60
    )
    
    print(f"命令: python cli.py parse \"{test_query}\"")
    print(f"执行时间: {parse_result['execution_time']:.2f}s")
    
    if parse_result["success"]:
        print("✅ 解析命令执行成功")
        if parse_result["stdout"]:
            print("📄 输出内容:")
            # 限制输出长度
            output = parse_result["stdout"]
            if len(output) > 1000:
                print(output[:1000] + "...(截断)")
            else:
                print(output)
    else:
        print("❌ 解析命令执行失败")
        print(f"返回码: {parse_result['returncode']}")
        if parse_result["stderr"]:
            print(f"错误信息: {parse_result['stderr']}")
    
    return parse_result


def test_search_command() -> Dict[str, Any]:
    """测试搜索命令"""
    print("\n🔍 测试搜索命令...")
    
    base_dir = Path(__file__).parent.parent
    test_query = "iPhone 13"
    
    # 测试search命令
    search_result = run_cli_command(
        [sys.executable, "cli.py", "search", test_query, "--max-results", "5"],
        str(base_dir),
        timeout=120
    )
    
    print(f"命令: python cli.py search \"{test_query}\" --max-results 5")
    print(f"执行时间: {search_result['execution_time']:.2f}s")
    
    if search_result["success"]:
        print("✅ 搜索命令执行成功")
        if search_result["stdout"]:
            print("📄 输出内容预览:")
            output = search_result["stdout"]
            # 只显示前500字符
            print(output[:500] + ("...(截断)" if len(output) > 500 else ""))
    else:
        print("❌ 搜索命令执行失败")
        print(f"返回码: {search_result['returncode']}")
        if search_result["stderr"]:
            print(f"错误信息: {search_result['stderr']}")
    
    return search_result


def test_analyze_command() -> Dict[str, Any]:
    """测试分析命令"""
    print("\n📊 测试分析命令...")
    
    base_dir = Path(__file__).parent.parent
    test_query = "iPhone"
    
    # 测试analyze命令
    analyze_result = run_cli_command(
        [sys.executable, "cli.py", "analyze", test_query, "--analysis-type", "basic"],
        str(base_dir),
        timeout=60
    )
    
    print(f"命令: python cli.py analyze \"{test_query}\" --analysis-type basic")
    print(f"执行时间: {analyze_result['execution_time']:.2f}s")
    
    if analyze_result["success"]:
        print("✅ 分析命令执行成功")
    else:
        print("❌ 分析命令执行失败")
        print(f"返回码: {analyze_result['returncode']}")
        if analyze_result["stderr"]:
            print(f"错误信息: {analyze_result['stderr']}")
    
    return analyze_result


def validate_output_quality(result: Dict[str, Any]) -> Dict[str, Any]:
    """验证输出质量"""
    if not result["success"]:
        return {"quality_score": 0, "issues": ["命令执行失败"]}
    
    output = result["stdout"]
    issues = []
    quality_indicators = []
    
    # 检查输出内容质量
    if not output or len(output.strip()) == 0:
        issues.append("输出为空")
    else:
        quality_indicators.append("有输出内容")
    
    # 检查是否包含错误信息
    if "error" in output.lower() or "exception" in output.lower():
        issues.append("输出包含错误信息")
    else:
        quality_indicators.append("无明显错误")
    
    # 检查是否是结构化输出
    if "title" in output.lower() or "price" in output.lower() or "¥" in output:
        quality_indicators.append("包含产品信息")
    
    # 检查是否是Markdown格式
    if "#" in output or "|" in output or "**" in output:
        quality_indicators.append("结构化输出格式")
    
    # 检查执行时间
    if result["execution_time"] < 30:
        quality_indicators.append("执行时间合理")
    else:
        issues.append("执行时间过长")
    
    # 计算质量评分
    total_checks = len(quality_indicators) + len(issues)
    if total_checks == 0:
        quality_score = 0
    else:
        quality_score = len(quality_indicators) / total_checks * 100
    
    return {
        "quality_score": quality_score,
        "quality_indicators": quality_indicators,
        "issues": issues
    }


def main():
    """主函数"""
    print("🧪 Mercari AI Agent CLI验证")
    print("=" * 50)
    
    start_time = time.time()
    results = {}
    
    try:
        # 1. 验证环境
        env_results = validate_cli_environment()
        results["environment"] = env_results
        
        # 2. 测试核心命令
        if env_results.get("cli_help", {}).get("success", False):
            # 测试解析命令（用户要求的核心命令）
            parse_results = test_parse_command()
            results["parse_command"] = parse_results
            results["parse_quality"] = validate_output_quality(parse_results)
            
            # 测试其他命令
            search_results = test_search_command()
            results["search_command"] = search_results
            results["search_quality"] = validate_output_quality(search_results)
            
            analyze_results = test_analyze_command()
            results["analyze_command"] = analyze_results
            results["analyze_quality"] = validate_output_quality(analyze_results)
        else:
            print("⏭️ 跳过命令测试（CLI不可用）")
        
        # 3. 生成验证报告
        total_time = time.time() - start_time
        print(f"\n📊 CLI验证摘要")
        print("=" * 30)
        
        # 环境检查摘要
        path_checks = env_results.get("path_checks", {})
        missing_paths = [p for p, exists in path_checks.items() if not exists]
        
        print(f"环境检查: {'✅ 通过' if not missing_paths else f'❌ 缺失{len(missing_paths)}个路径'}")
        
        # 命令测试摘要
        commands_tested = []
        commands_passed = []
        
        for cmd in ["parse_command", "search_command", "analyze_command"]:
            if cmd in results:
                commands_tested.append(cmd)
                if results[cmd]["success"]:
                    commands_passed.append(cmd)
        
        if commands_tested:
            success_rate = len(commands_passed) / len(commands_tested) * 100
            print(f"命令测试: {len(commands_passed)}/{len(commands_tested)} 通过 ({success_rate:.1f}%)")
            
            # 显示关键命令结果
            if "parse_command" in results:
                parse_success = results["parse_command"]["success"]
                parse_quality = results.get("parse_quality", {}).get("quality_score", 0)
                print(f"解析命令: {'✅ 通过' if parse_success else '❌ 失败'} (质量: {parse_quality:.1f}%)")
        
        print(f"总执行时间: {total_time:.2f}s")
        
        # 保存详细结果
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        report_file = f"cli_validation_report_{timestamp}.json"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"📄 详细报告已保存到: {report_file}")
        
        # 确定退出代码
        if env_results.get("cli_help", {}).get("success", False):
            if results.get("parse_command", {}).get("success", False):
                print("\n🎉 CLI验证成功！核心功能正常工作。")
                return 0
            else:
                print("\n⚠️ CLI部分功能异常，但基本可用。")
                return 1
        else:
            print("\n❌ CLI环境异常，无法正常使用。")
            return 2
    
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断验证")
        return 130
    except Exception as e:
        print(f"\n💥 验证过程异常: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())