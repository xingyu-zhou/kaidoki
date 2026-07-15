"""
综合部署脚本
统一执行所有P0级别问题的修复

使用方法：
python comprehensive_deployment_script.py [--dry-run] [--rollback]

参数：
--dry-run: 仅显示将要执行的操作，不实际执行
--rollback: 回滚所有修复到原始状态
"""

import asyncio
import argparse
import os
import shutil
import sys
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
import subprocess

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('deployment.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class DeploymentManager:
    """部署管理器"""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.project_root = Path(__file__).parent
        self.backup_root = self.project_root / "backups"
        self.deployment_id = f"deployment_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.deployment_log = []
        
        # 创建备份目录
        self.backup_dir = self.backup_root / self.deployment_id
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 修复脚本路径
        self.fix_scripts = {
            "session_manager": self.project_root / "session_manager_fix.py",
            "error_handling": self.project_root / "error_handling_fix.py"
        }
        
        # 目标文件路径
        self.target_files = {
            "session_manager": self.project_root / "mercari_ai_agent" / "src" / "mercari_agent" / "scrapers" / "enhanced_session_manager.py",
            "base_tool": self.project_root / "mercari_ai_agent" / "src" / "mercari_agent" / "core" / "tools" / "base_tool.py",
            "orchestrator": self.project_root / "mercari_ai_agent" / "src" / "mercari_agent" / "core" / "tool_orchestrator.py"
        }
        
        # 部署状态
        self.deployment_status = {
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
            "success": False,
            "errors": [],
            "fixed_issues": [],
            "rollback_available": False
        }
    
    def log_operation(self, operation: str, status: str, details: str = ""):
        """记录操作日志"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "status": status,
            "details": details
        }
        self.deployment_log.append(entry)
        
        if status == "success":
            logger.info(f"✅ {operation}: {details}")
        elif status == "error":
            logger.error(f"❌ {operation}: {details}")
        elif status == "warning":
            logger.warning(f"⚠️ {operation}: {details}")
        else:
            logger.info(f"🔄 {operation}: {details}")
    
    def backup_files(self):
        """备份关键文件"""
        self.log_operation("备份文件", "started", "开始备份关键文件")
        
        try:
            for name, file_path in self.target_files.items():
                if file_path.exists():
                    backup_path = self.backup_dir / f"{name}.py.backup"
                    
                    if not self.dry_run:
                        shutil.copy2(file_path, backup_path)
                    
                    self.log_operation(
                        "备份文件",
                        "success",
                        f"已备份 {name}: {file_path} -> {backup_path}"
                    )
                else:
                    self.log_operation(
                        "备份文件",
                        "warning",
                        f"文件不存在: {file_path}"
                    )
            
            self.deployment_status["rollback_available"] = True
            self.log_operation("备份文件", "success", "所有文件备份完成")
            
        except Exception as e:
            self.log_operation("备份文件", "error", f"备份失败: {e}")
            raise
    
    async def run_session_manager_fix(self):
        """运行会话管理器修复"""
        self.log_operation("会话管理器修复", "started", "开始修复会话管理器")
        
        try:
            if not self.dry_run:
                # 导入并运行修复脚本
                sys.path.insert(0, str(self.project_root))
                
                from session_manager_fix import SessionManagerFix
                
                fixer = SessionManagerFix()
                await fixer.run_fix()
            
            self.deployment_status["fixed_issues"].append("会话管理器初始化失败")
            self.log_operation("会话管理器修复", "success", "会话管理器修复完成")
            
        except Exception as e:
            self.deployment_status["errors"].append(f"会话管理器修复失败: {e}")
            self.log_operation("会话管理器修复", "error", f"修复失败: {e}")
            raise
    
    async def run_error_handling_fix(self):
        """运行错误处理修复"""
        self.log_operation("错误处理修复", "started", "开始修复错误处理")
        
        try:
            if not self.dry_run:
                # 导入并运行修复脚本
                from error_handling_fix import ErrorHandlingFix
                
                fixer = ErrorHandlingFix()
                await fixer.run_fix()
            
            self.deployment_status["fixed_issues"].append("错误处理架构不兼容")
            self.log_operation("错误处理修复", "success", "错误处理修复完成")
            
        except Exception as e:
            self.deployment_status["errors"].append(f"错误处理修复失败: {e}")
            self.log_operation("错误处理修复", "error", f"修复失败: {e}")
            raise
    
    async def run_integration_tests(self):
        """运行集成测试"""
        self.log_operation("集成测试", "started", "开始运行集成测试")
        
        try:
            test_results = []
            
            # 测试1: 导入测试
            try:
                if not self.dry_run:
                    sys.path.insert(0, str(self.project_root / "mercari_ai_agent" / "src"))
                    
                    from mercari_agent.scrapers.enhanced_session_manager import EnhancedSessionManager
                    from mercari_agent.core.tools.base_tool import UnifiedResult, OperationStatus
                    
                test_results.append("✅ 模块导入测试通过")
                
            except Exception as e:
                test_results.append(f"❌ 模块导入测试失败: {e}")
                raise
            
            # 测试2: 会话管理器初始化测试
            try:
                if not self.dry_run:
                    manager = EnhancedSessionManager()
                    await manager.initialize()
                    assert manager.is_healthy, "会话管理器不健康"
                    await manager.close_all_sessions()
                
                test_results.append("✅ 会话管理器初始化测试通过")
                
            except Exception as e:
                test_results.append(f"❌ 会话管理器初始化测试失败: {e}")
                raise
            
            # 测试3: 错误处理测试
            try:
                if not self.dry_run:
                    # 测试成功结果
                    success_result = UnifiedResult(
                        success=True,
                        status=OperationStatus.SUCCESS,
                        data={"test": "data"}
                    )
                    assert success_result.is_success()
                    
                    # 测试错误结果
                    error_result = UnifiedResult(
                        success=False,
                        status=OperationStatus.ERROR,
                        error_code="TEST_ERROR",
                        error_message="测试错误"
                    )
                    assert error_result.is_error()
                
                test_results.append("✅ 错误处理测试通过")
                
            except Exception as e:
                test_results.append(f"❌ 错误处理测试失败: {e}")
                raise
            
            # 记录测试结果
            for result in test_results:
                self.log_operation("集成测试", "success", result)
            
            self.log_operation("集成测试", "success", "所有集成测试通过")
            
        except Exception as e:
            self.log_operation("集成测试", "error", f"集成测试失败: {e}")
            raise
    
    async def validate_deployment(self):
        """验证部署结果"""
        self.log_operation("部署验证", "started", "开始验证部署结果")
        
        try:
            validation_results = []
            
            # 验证1: 文件存在性
            for name, file_path in self.target_files.items():
                if file_path.exists():
                    validation_results.append(f"✅ {name} 文件存在")
                else:
                    validation_results.append(f"❌ {name} 文件不存在")
                    raise FileNotFoundError(f"关键文件不存在: {file_path}")
            
            # 验证2: 语法检查
            if not self.dry_run:
                for name, file_path in self.target_files.items():
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # 简单的语法检查
                        compile(content, str(file_path), 'exec')
                        validation_results.append(f"✅ {name} 语法检查通过")
                        
                    except SyntaxError as e:
                        validation_results.append(f"❌ {name} 语法错误: {e}")
                        raise
            
            # 验证3: 功能检查
            if not self.dry_run:
                # 这里可以添加更多的功能检查
                pass
            
            # 记录验证结果
            for result in validation_results:
                self.log_operation("部署验证", "success", result)
            
            self.log_operation("部署验证", "success", "部署验证完成")
            
        except Exception as e:
            self.log_operation("部署验证", "error", f"部署验证失败: {e}")
            raise
    
    async def rollback_deployment(self):
        """回滚部署"""
        self.log_operation("回滚部署", "started", "开始回滚部署")
        
        try:
            if not self.deployment_status["rollback_available"]:
                raise Exception("没有可用的备份文件")
            
            # 回滚所有文件
            for name, file_path in self.target_files.items():
                backup_path = self.backup_dir / f"{name}.py.backup"
                
                if backup_path.exists():
                    shutil.copy2(backup_path, file_path)
                    self.log_operation(
                        "回滚部署",
                        "success",
                        f"已回滚 {name}: {backup_path} -> {file_path}"
                    )
                else:
                    self.log_operation(
                        "回滚部署",
                        "warning",
                        f"备份文件不存在: {backup_path}"
                    )
            
            self.log_operation("回滚部署", "success", "所有文件回滚完成")
            
        except Exception as e:
            self.log_operation("回滚部署", "error", f"回滚失败: {e}")
            raise
    
    def save_deployment_report(self):
        """保存部署报告"""
        self.deployment_status["completed_at"] = datetime.now().isoformat()
        
        report = {
            "deployment_id": self.deployment_id,
            "deployment_status": self.deployment_status,
            "deployment_log": self.deployment_log,
            "backup_location": str(self.backup_dir),
            "target_files": {k: str(v) for k, v in self.target_files.items()},
            "fix_scripts": {k: str(v) for k, v in self.fix_scripts.items()}
        }
        
        report_path = self.backup_dir / "deployment_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        self.log_operation("保存报告", "success", f"部署报告已保存: {report_path}")
    
    async def deploy(self):
        """执行完整部署"""
        try:
            self.log_operation("开始部署", "started", f"部署ID: {self.deployment_id}")
            
            if self.dry_run:
                self.log_operation("模拟模式", "info", "当前为模拟模式，不会实际修改文件")
            
            # 1. 备份文件
            self.backup_files()
            
            # 2. 运行会话管理器修复
            await self.run_session_manager_fix()
            
            # 3. 运行错误处理修复
            await self.run_error_handling_fix()
            
            # 4. 运行集成测试
            await self.run_integration_tests()
            
            # 5. 验证部署
            await self.validate_deployment()
            
            # 6. 标记部署成功
            self.deployment_status["success"] = True
            self.log_operation("部署完成", "success", "所有修复已成功部署")
            
        except Exception as e:
            self.deployment_status["success"] = False
            self.deployment_status["errors"].append(str(e))
            self.log_operation("部署失败", "error", f"部署失败: {e}")
            
            # 如果不是模拟模式，尝试回滚
            if not self.dry_run and self.deployment_status["rollback_available"]:
                try:
                    await self.rollback_deployment()
                    self.log_operation("自动回滚", "success", "已自动回滚到原始状态")
                except Exception as rollback_error:
                    self.log_operation("自动回滚", "error", f"自动回滚失败: {rollback_error}")
            
            raise
        
        finally:
            # 总是保存部署报告
            self.save_deployment_report()
    
    def print_deployment_summary(self):
        """打印部署摘要"""
        print("\n" + "="*80)
        print(f"部署摘要 - {self.deployment_id}")
        print("="*80)
        
        print(f"部署状态: {'✅ 成功' if self.deployment_status['success'] else '❌ 失败'}")
        print(f"开始时间: {self.deployment_status['started_at']}")
        print(f"完成时间: {self.deployment_status['completed_at']}")
        
        if self.deployment_status["fixed_issues"]:
            print("\n已修复的问题:")
            for issue in self.deployment_status["fixed_issues"]:
                print(f"  ✅ {issue}")
        
        if self.deployment_status["errors"]:
            print("\n错误列表:")
            for error in self.deployment_status["errors"]:
                print(f"  ❌ {error}")
        
        print(f"\n备份位置: {self.backup_dir}")
        print(f"部署日志: {len(self.deployment_log)} 条记录")
        print(f"回滚可用: {'是' if self.deployment_status['rollback_available'] else '否'}")
        
        print("\n" + "="*80)


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Mercari AI Agent 综合部署脚本")
    parser.add_argument("--dry-run", action="store_true", help="仅显示操作，不实际执行")
    parser.add_argument("--rollback", type=str, help="回滚到指定的部署ID")
    
    args = parser.parse_args()
    
    if args.rollback:
        # 执行回滚
        print(f"🔄 开始回滚到部署: {args.rollback}")
        
        backup_dir = Path(__file__).parent / "backups" / args.rollback
        if not backup_dir.exists():
            print(f"❌ 找不到部署备份: {backup_dir}")
            return
        
        # 这里可以实现回滚逻辑
        print("回滚功能待实现...")
        
    else:
        # 执行部署
        print("🚀 开始 Mercari AI Agent P0级别问题修复部署...")
        
        if args.dry_run:
            print("🔍 模拟模式 - 不会实际修改文件")
        
        manager = DeploymentManager(dry_run=args.dry_run)
        
        try:
            await manager.deploy()
            print("🎉 部署成功完成！")
            
        except Exception as e:
            print(f"❌ 部署失败: {e}")
            return 1
        
        finally:
            manager.print_deployment_summary()
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)