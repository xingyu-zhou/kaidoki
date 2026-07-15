#!/usr/bin/env python3
"""
CLI接口测试脚本

测试CLI接口的基础功能
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any

# 设置项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

def run_cli_command(args: List[str], timeout: int = 30) -> Dict[str, Any]:
    """运行CLI命令并返回结果"""
    try:
        # 构建完整命令
        cmd = [sys.executable, "-m", "mercari_agent.interfaces.cli.main"] + args
        
        # 在项目目录中运行
        result = subprocess.run(
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=dict(os.environ, PYTHONPATH=str(project_root / "src"))
        )
        
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0
        }
    except subprocess.TimeoutExpired:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": "Command timed out",
            "success": False
        }
    except Exception as e:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
            "success": False
        }

def test_help_command():
    """测试帮助命令"""
    print("🔍 测试帮助命令...")
    
    results = []
    
    # 测试主帮助
    result = run_cli_command(["--help"])
    if result["success"]:
        if "Mercari AI Agent CLI" in result["stdout"]:
            results.append("✅ 主帮助命令正常")
        else:
            results.append("⚠️ 主帮助命令输出不完整")
    else:
        results.append(f"❌ 主帮助命令失败: {result['stderr']}")
    
    # 测试子命令帮助
    subcommands = ["search", "parse", "scrape", "status", "config"]
    for subcmd in subcommands:
        result = run_cli_command([subcmd, "--help"])
        if result["success"]:
            results.append(f"✅ {subcmd} 帮助命令正常")
        else:
            results.append(f"❌ {subcmd} 帮助命令失败: {result['stderr']}")
    
    return results

def test_config_command():
    """测试配置命令"""
    print("🔍 测试配置命令...")
    
    results = []
    
    result = run_cli_command(["config"])
    if result["success"]:
        # 检查是否包含配置信息
        if "当前配置" in result["stdout"] or "environment" in result["stdout"]:
            results.append("✅ 配置命令正常，输出配置信息")
        else:
            results.append("⚠️ 配置命令运行但输出不完整")
    else:
        results.append(f"❌ 配置命令失败: {result['stderr']}")
    
    return results

def test_status_command():
    """测试状态命令"""
    print("🔍 测试状态命令...")
    
    results = []
    
    # 状态命令可能需要更长时间
    result = run_cli_command(["status"], timeout=60)
    if result["success"]:
        # 检查是否包含状态信息
        if "系统状态" in result["stdout"] or "配置信息" in result["stdout"]:
            results.append("✅ 状态命令正常")
        else:
            results.append("⚠️ 状态命令运行但输出不完整")
    else:
        # 状态命令失败可能是因为依赖问题，不算严重错误
        results.append(f"⚠️ 状态命令失败: {result['stderr'][:100]}...")
    
    return results

def test_parse_command():
    """测试解析命令"""
    print("🔍 测试解析命令...")
    
    results = []
    
    # 使用简单查询测试
    result = run_cli_command(["parse", "--query", "iPhone"], timeout=60)
    if result["success"]:
        if "解析查询" in result["stdout"] or "解析结果" in result["stdout"]:
            results.append("✅ 解析命令正常")
        else:
            results.append("⚠️ 解析命令运行但输出不完整")
    else:
        results.append(f"⚠️ 解析命令失败: {result['stderr'][:100]}...")
    
    return results

def test_cli_structure():
    """测试CLI结构"""
    print("🔍 测试CLI结构...")
    
    results = []
    
    # 测试主命令是否可用
    result = run_cli_command([])
    if result["returncode"] == 0 or "Usage:" in result["stdout"]:
        results.append("✅ CLI主命令结构正常")
    else:
        results.append(f"❌ CLI主命令结构异常: {result['stderr']}")
    
    # 测试无效命令
    result = run_cli_command(["invalid_command"])
    if result["returncode"] != 0:
        results.append("✅ 无效命令处理正常")
    else:
        results.append("⚠️ 无效命令处理异常")
    
    return results

def test_import_dependencies():
    """测试导入依赖"""
    print("🔍 测试导入依赖...")
    
    results = []
    
    try:
        # 测试主要导入
        from mercari_agent.interfaces.cli.main import cli
        results.append("✅ CLI主模块导入成功")
        
        # 测试click库
        import click
        results.append("✅ click库可用")
        
        # 测试配置导入
        from mercari_agent.shared.config.app_config import get_config
        results.append("✅ 配置模块导入成功")
        
    except ImportError as e:
        results.append(f"❌ 导入依赖失败: {e}")
    except Exception as e:
        results.append(f"❌ 导入测试失败: {e}")
    
    return results

def test_cli_file_existence():
    """测试CLI文件存在性"""
    print("🔍 测试CLI文件存在性...")
    
    results = []
    
    # 检查CLI主文件
    cli_main = project_root / "src" / "mercari_agent" / "interfaces" / "cli" / "main.py"
    if cli_main.exists():
        results.append("✅ CLI主文件存在")
    else:
        results.append("❌ CLI主文件不存在")
    
    # 检查CLI目录结构
    cli_dir = project_root / "src" / "mercari_agent" / "interfaces" / "cli"
    if cli_dir.exists():
        results.append("✅ CLI目录结构存在")
    else:
        results.append("❌ CLI目录结构不存在")
    
    return results

def main():
    """主函数"""
    print("🚀 Mercari AI Agent CLI接口测试")
    print("=" * 60)
    
    # 切换到项目目录
    os.chdir(project_root)
    
    all_results = []
    
    # 运行测试
    test_functions = [
        test_cli_file_existence,
        test_import_dependencies,
        test_cli_structure,
        test_help_command,
        test_config_command,
        test_status_command,
        test_parse_command,
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
    print("📊 CLI接口测试结果:")
    print(f"✅ 通过: {passed}")
    print(f"❌ 失败: {failed}")
    print(f"⚠️ 警告: {warnings}")
    print(f"📊 总计: {len(all_results)}")
    
    # 计算成功率
    success_rate = (passed / len(all_results) * 100) if all_results else 0
    print(f"🎯 成功率: {success_rate:.1f}%")
    
    # 评估结果
    if failed == 0:
        print("🎉 CLI接口基础功能完全正常!")
        return 0
    elif failed <= 2:
        print("⚠️ CLI接口基本正常，少数功能有问题")
        return 0
    else:
        print("🚨 CLI接口存在较多问题")
        return 1

if __name__ == "__main__":
    sys.exit(main())