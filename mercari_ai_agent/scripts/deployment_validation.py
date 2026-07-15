"""
插件框架部署验证脚本

验证插件框架在部署环境中的正确性，包括环境检查、依赖验证、
功能测试和性能基准。

Author: Mercari AI Agent Team
"""

import os
import sys
import asyncio
import logging
import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

try:
    from mercari_agent.plugins.framework import PluginFramework
    from mercari_agent.plugins.examples.basic_plugin import BasicExamplePlugin
    from mercari_agent.plugins.examples.advanced_plugin import AdvancedExamplePlugin
except ImportError as e:
    print(f"导入插件模块失败: {e}")
    sys.exit(1)


class DeploymentValidator:
    """部署验证器"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.logger = logging.getLogger("deployment_validator")
        self.config = self._load_config(config_file)
        self.validation_results = {}
        self.start_time = None
        
        # 验证状态
        self.environment_valid = False
        self.dependencies_valid = False
        self.functionality_valid = False
        self.performance_valid = False
        
    def _load_config(self, config_file: Optional[str]) -> Dict[str, Any]:
        """加载配置"""
        default_config = {
            "environment": {
                "python_version": "3.8",
                "required_packages": [
                    "asyncio", "logging", "json", "dataclasses", 
                    "typing", "datetime", "pathlib"
                ],
                "optional_packages": ["psutil", "aiohttp", "requests"]
            },
            "functionality": {
                "test_plugin_count": 3,
                "test_timeout": 30.0,
                "required_success_rate": 0.95
            },
            "performance": {
                "max_initialization_time": 5.0,
                "max_health_check_time": 1.0,
                "max_memory_usage_mb": 500,
                "min_throughput_rps": 10.0
            },
            "deployment": {
                "check_file_permissions": True,
                "check_directory_structure": True,
                "validate_imports": True,
                "run_smoke_tests": True
            }
        }
        
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    loaded_config = json.load(f)
                    # 合并配置
                    for key, value in loaded_config.items():
                        if key in default_config and isinstance(value, dict):
                            default_config[key].update(value)
                        else:
                            default_config[key] = value
            except Exception as e:
                self.logger.warning(f"加载配置文件失败，使用默认配置: {e}")
        
        return default_config
    
    async def run_full_validation(self) -> Dict[str, Any]:
        """运行完整验证"""
        self.logger.info("开始部署验证")
        self.start_time = time.time()
        
        validation_results = {
            "timestamp": datetime.now().isoformat(),
            "validation_phases": {},
            "summary": {},
            "overall_success": False,
            "duration": 0.0,
            "errors": []
        }
        
        try:
            # 第1阶段：环境验证
            self.logger.info("=== 第1阶段：环境验证 ===")
            env_results = await self._validate_environment()
            validation_results["validation_phases"]["environment"] = env_results
            self.environment_valid = env_results.get("success", False)
            
            # 第2阶段：依赖验证
            self.logger.info("=== 第2阶段：依赖验证 ===")
            dep_results = await self._validate_dependencies()
            validation_results["validation_phases"]["dependencies"] = dep_results
            self.dependencies_valid = dep_results.get("success", False)
            
            # 第3阶段：功能验证
            self.logger.info("=== 第3阶段：功能验证 ===")
            func_results = await self._validate_functionality()
            validation_results["validation_phases"]["functionality"] = func_results
            self.functionality_valid = func_results.get("success", False)
            
            # 第4阶段：性能验证
            self.logger.info("=== 第4阶段：性能验证 ===")
            perf_results = await self._validate_performance()
            validation_results["validation_phases"]["performance"] = perf_results
            self.performance_valid = perf_results.get("success", False)
            
            # 第5阶段：部署验证
            self.logger.info("=== 第5阶段：部署验证 ===")
            deploy_results = await self._validate_deployment()
            validation_results["validation_phases"]["deployment"] = deploy_results
            
            # 生成摘要
            validation_results["summary"] = self._generate_validation_summary()
            validation_results["overall_success"] = self._is_validation_successful()
            
        except Exception as e:
            self.logger.error(f"验证过程中出现异常: {e}", exc_info=True)
            validation_results["errors"].append(str(e))
            validation_results["overall_success"] = False
        
        finally:
            validation_results["duration"] = time.time() - self.start_time
            self.validation_results = validation_results
        
        return validation_results
    
    async def _validate_environment(self) -> Dict[str, Any]:
        """验证环境"""
        results = {"success": True, "checks": [], "errors": []}
        
        try:
            # 检查Python版本
            python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
            required_version = self.config["environment"]["python_version"]
            
            version_check = python_version >= required_version
            results["checks"].append({
                "name": "python_version",
                "success": version_check,
                "actual": python_version,
                "required": required_version,
                "description": "Python版本检查"
            })
            
            if not version_check:
                results["success"] = False
                results["errors"].append(f"Python版本不符合要求: {python_version} < {required_version}")
            
            # 检查操作系统
            import platform
            os_info = {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine()
            }
            
            results["checks"].append({
                "name": "operating_system",
                "success": True,
                "info": os_info,
                "description": "操作系统信息"
            })
            
            # 检查可用内存
            try:
                import psutil
                memory_info = psutil.virtual_memory()
                available_mb = memory_info.available / 1024 / 1024
                required_mb = self.config["performance"]["max_memory_usage_mb"]
                
                memory_check = available_mb >= required_mb * 2
                results["checks"].append({
                    "name": "available_memory",
                    "success": memory_check,
                    "available_mb": available_mb,
                    "required_mb": required_mb,
                    "description": "可用内存检查"
                })
                
                if not memory_check:
                    results["success"] = False
                    results["errors"].append(f"可用内存不足: {available_mb:.1f}MB < {required_mb * 2}MB")
            
            except ImportError:
                results["checks"].append({
                    "name": "available_memory",
                    "success": False,
                    "error": "psutil未安装，无法检查内存",
                    "description": "可用内存检查"
                })
            
            # 检查文件权限
            if self.config["deployment"]["check_file_permissions"]:
                permission_check = self._check_file_permissions()
                results["checks"].append({
                    "name": "file_permissions",
                    "success": permission_check,
                    "description": "文件权限检查"
                })
                
                if not permission_check:
                    results["success"] = False
                    results["errors"].append("文件权限不足")
            
        except Exception as e:
            results["success"] = False
            results["errors"].append(f"环境验证异常: {e}")
        
        return results
    
    async def _validate_dependencies(self) -> Dict[str, Any]:
        """验证依赖"""
        results = {"success": True, "checks": [], "errors": []}
        
        try:
            # 检查必需包
            required_packages = self.config["environment"]["required_packages"]
            
            for package in required_packages:
                try:
                    __import__(package)
                    results["checks"].append({
                        "name": f"package_{package}",
                        "success": True,
                        "package": package,
                        "description": f"必需包 {package} 检查"
                    })
                except ImportError:
                    results["success"] = False
                    results["errors"].append(f"必需包 {package} 未安装")
                    results["checks"].append({
                        "name": f"package_{package}",
                        "success": False,
                        "package": package,
                        "description": f"必需包 {package} 检查"
                    })
            
            # 检查项目导入
            if self.config["deployment"]["validate_imports"]:
                import_check = await self._check_project_imports()
                results["checks"].append({
                    "name": "project_imports",
                    "success": import_check,
                    "description": "项目导入检查"
                })
                
                if not import_check:
                    results["success"] = False
                    results["errors"].append("项目导入失败")
            
        except Exception as e:
            results["success"] = False
            results["errors"].append(f"依赖验证异常: {e}")
        
        return results
    
    async def _validate_functionality(self) -> Dict[str, Any]:
        """验证功能"""
        results = {"success": True, "checks": [], "errors": []}
        
        try:
            # 测试框架初始化
            framework = await PluginFramework.get_instance()
            
            results["checks"].append({
                "name": "framework_initialization",
                "success": framework is not None,
                "description": "框架初始化检查"
            })
            
            # 测试插件注册和生命周期
            test_plugins = []
            plugin_count = min(self.config["functionality"]["test_plugin_count"], 3)
            
            for i in range(plugin_count):
                if i % 2 == 0:
                    plugin = BasicExamplePlugin()
                else:
                    plugin = AdvancedExamplePlugin()
                
                plugin.plugin_id = f"validation_test_plugin_{i}"
                test_plugins.append(plugin)
            
            # 注册插件
            registration_success = True
            for plugin in test_plugins:
                success = await framework.register_plugin(plugin)
                if not success:
                    registration_success = False
                    break
            
            results["checks"].append({
                "name": "plugin_registration",
                "success": registration_success,
                "plugin_count": len(test_plugins),
                "description": "插件注册检查"
            })
            
            if not registration_success:
                results["success"] = False
                results["errors"].append("插件注册失败")
                return results
            
            # 初始化插件
            initialization_success = True
            for plugin in test_plugins:
                success = await framework.initialize_plugin(plugin.plugin_id, {"enabled": True})
                if not success:
                    initialization_success = False
                    break
            
            results["checks"].append({
                "name": "plugin_initialization",
                "success": initialization_success,
                "description": "插件初始化检查"
            })
            
            # 启动插件
            startup_success = True
            for plugin in test_plugins:
                success = await framework.start_plugin(plugin.plugin_id)
                if not success:
                    startup_success = False
                    break
            
            results["checks"].append({
                "name": "plugin_startup",
                "success": startup_success,
                "description": "插件启动检查"
            })
            
            # 健康检查
            health_results = await framework.health_check_all()
            healthy_plugins = sum(1 for is_healthy in health_results.values() if is_healthy)
            required_success_rate = self.config["functionality"]["required_success_rate"]
            actual_success_rate = healthy_plugins / len(test_plugins) if test_plugins else 0
            
            health_check_success = actual_success_rate >= required_success_rate
            
            results["checks"].append({
                "name": "plugin_health_check",
                "success": health_check_success,
                "healthy_plugins": healthy_plugins,
                "total_plugins": len(test_plugins),
                "success_rate": actual_success_rate,
                "required_rate": required_success_rate,
                "description": "插件健康检查"
            })
            
            if not health_check_success:
                results["success"] = False
                results["errors"].append(f"健康检查成功率不足: {actual_success_rate:.2%} < {required_success_rate:.2%}")
            
            # 清理插件
            cleanup_success = True
            for plugin in test_plugins:
                try:
                    await framework.stop_plugin(plugin.plugin_id)
                    await framework.cleanup_plugin(plugin.plugin_id)
                    await framework.unregister_plugin(plugin.plugin_id)
                except Exception as e:
                    cleanup_success = False
                    self.logger.warning(f"插件清理失败: {e}")
            
            results["checks"].append({
                "name": "plugin_cleanup",
                "success": cleanup_success,
                "description": "插件清理检查"
            })
            
        except Exception as e:
            results["success"] = False
            results["errors"].append(f"功能验证异常: {e}")
        
        return results
    
    async def _validate_performance(self) -> Dict[str, Any]:
        """验证性能"""
        results = {"success": True, "checks": [], "errors": []}
        
        try:
            # 创建性能测试插件
            test_plugin = BasicExamplePlugin()
            test_plugin.plugin_id = "performance_validation_plugin"
            
            framework = await PluginFramework.get_instance()
            await framework.register_plugin(test_plugin)
            
            # 测试初始化时间
            start_time = time.time()
            await framework.initialize_plugin(test_plugin.plugin_id, {"enabled": True})
            await framework.start_plugin(test_plugin.plugin_id)
            initialization_time = time.time() - start_time
            
            max_init_time = self.config["performance"]["max_initialization_time"]
            init_time_check = initialization_time <= max_init_time
            
            results["checks"].append({
                "name": "initialization_time",
                "success": init_time_check,
                "actual_time": initialization_time,
                "max_time": max_init_time,
                "description": "初始化时间检查"
            })
            
            if not init_time_check:
                results["success"] = False
                results["errors"].append(f"初始化时间过长: {initialization_time:.3f}s > {max_init_time}s")
            
            # 测试健康检查时间
            health_times = []
            for _ in range(10):
                start_time = time.time()
                await test_plugin.health_check()
                health_time = time.time() - start_time
                health_times.append(health_time)
            
            avg_health_time = sum(health_times) / len(health_times)
            max_health_time = self.config["performance"]["max_health_check_time"]
            health_time_check = avg_health_time <= max_health_time
            
            results["checks"].append({
                "name": "health_check_time",
                "success": health_time_check,
                "average_time": avg_health_time,
                "max_time": max_health_time,
                "description": "健康检查时间检查"
            })
            
            if not health_time_check:
                results["success"] = False
                results["errors"].append(f"健康检查时间过长: {avg_health_time:.3f}s > {max_health_time}s")
            
            # 测试吞吐量
            operations_count = 100
            start_time = time.time()
            
            for _ in range(operations_count):
                await test_plugin.health_check()
            
            duration = time.time() - start_time
            throughput = operations_count / duration
            min_throughput = self.config["performance"]["min_throughput_rps"]
            throughput_check = throughput >= min_throughput
            
            results["checks"].append({
                "name": "throughput",
                "success": throughput_check,
                "actual_rps": throughput,
                "min_rps": min_throughput,
                "description": "吞吐量检查"
            })
            
            if not throughput_check:
                results["success"] = False
                results["errors"].append(f"吞吐量过低: {throughput:.1f} RPS < {min_throughput} RPS")
            
            # 清理测试插件
            await framework.stop_plugin(test_plugin.plugin_id)
            await framework.cleanup_plugin(test_plugin.plugin_id)
            await framework.unregister_plugin(test_plugin.plugin_id)
            
        except Exception as e:
            results["success"] = False
            results["errors"].append(f"性能验证异常: {e}")
        
        return results
    
    async def _validate_deployment(self) -> Dict[str, Any]:
        """验证部署"""
        results = {"success": True, "checks": [], "errors": []}
        
        try:
            # 检查目录结构
            if self.config["deployment"]["check_directory_structure"]:
                structure_check = self._check_directory_structure()
                results["checks"].append({
                    "name": "directory_structure",
                    "success": structure_check,
                    "description": "目录结构检查"
                })
                
                if not structure_check:
                    results["success"] = False
                    results["errors"].append("目录结构不完整")
            
            # 运行冒烟测试
            if self.config["deployment"]["run_smoke_tests"]:
                smoke_test_success = await self._run_smoke_tests()
                results["checks"].append({
                    "name": "smoke_tests",
                    "success": smoke_test_success,
                    "description": "冒烟测试"
                })
                
                if not smoke_test_success:
                    results["success"] = False
                    results["errors"].append("冒烟测试失败")
            
        except Exception as e:
            results["success"] = False
            results["errors"].append(f"部署验证异常: {e}")
        
        return results
    
    def _check_file_permissions(self) -> bool:
        """检查文件权限"""
        try:
            test_file = project_root / "temp_permission_test.txt"
            
            with open(test_file, 'w') as f:
                f.write("permission test")
            
            with open(test_file, 'r') as f:
                content = f.read()
            
            test_file.unlink()
            
            return content == "permission test"
        
        except Exception as e:
            self.logger.warning(f"文件权限检查失败: {e}")
            return False
    
    async def _check_project_imports(self) -> bool:
        """检查项目导入"""
        try:
            from mercari_agent.plugins.framework import PluginFramework
            from mercari_agent.plugins.interfaces import IPlugin
            from mercari_agent.plugins.registry import PluginRegistry
            from mercari_agent.plugins.examples.basic_plugin import BasicExamplePlugin
            
            return True
        
        except Exception as e:
            self.logger.error(f"项目导入检查失败: {e}")
            return False
    
    def _check_directory_structure(self) -> bool:
        """检查目录结构"""
        required_dirs = [
            "src/mercari_agent/plugins",
            "src/mercari_agent/plugins/examples",
            "tests/plugins",
            "docs/plugins"
        ]
        
        for dir_path in required_dirs:
            full_path = project_root / dir_path
            if not full_path.exists():
                self.logger.error(f"缺少必需目录: {dir_path}")
                return False
        
        return True
    
    async def _run_smoke_tests(self) -> bool:
        """运行冒烟测试"""
        try:
            plugin = BasicExamplePlugin()
            plugin.plugin_id = "smoke_test_plugin"
            
            framework = await PluginFramework.get_instance()
            
            await framework.register_plugin(plugin)
            await framework.initialize_plugin(plugin.plugin_id, {"enabled": True})
            await framework.start_plugin(plugin.plugin_id)
            
            health_ok = await plugin.health_check()
            status = await plugin.get_status()
            
            await framework.stop_plugin(plugin.plugin_id)
            await framework.cleanup_plugin(plugin.plugin_id)
            await framework.unregister_plugin(plugin.plugin_id)
            
            return health_ok and isinstance(status, dict)
        
        except Exception as e:
            self.logger.error(f"冒烟测试失败: {e}")
            return False
    
    def _is_validation_successful(self) -> bool:
        """判断验证是否成功"""
        return (
            self.environment_valid and
            self.dependencies_valid and
            self.functionality_valid and
            self.performance_valid
        )
    
    def _generate_validation_summary(self) -> Dict[str, Any]:
        """生成验证摘要"""
        phases = self.validation_results.get("validation_phases", {})
        
        total_checks = 0
        successful_checks = 0
        
        for phase_result in phases.values():
            checks = phase_result.get("checks", [])
            total_checks += len(checks)
            successful_checks += sum(1 for check in checks if check.get("success", False))
        
        return {
            "environment_valid": self.environment_valid,
            "dependencies_valid": self.dependencies_valid,
            "functionality_valid": self.functionality_valid,
            "performance_valid": self.performance_valid,
            "total_phases": len(phases),
            "successful_phases": sum(1 for phase in phases.values() if phase.get("success", False)),
            "total_checks": total_checks,
            "successful_checks": successful_checks,
            "success_rate": successful_checks / total_checks if total_checks > 0 else 0,
            "overall_success": self._is_validation_successful()
        }
    
    def generate_report(self) -> str:
        """生成验证报告"""
        if not self.validation_results:
            return "验证尚未运行"
        
        report = []
        report.append("=" * 60)
        report.append("插件框架部署验证报告")
        report.append("=" * 60)
        
        # 基本信息
        report.append(f"验证时间: {self.validation_results['timestamp']}")
        report.append(f"验证持续时间: {self.validation_results['duration']:.2f}秒")
        report.append(f"总体结果: {'✅ 成功' if self.validation_results['overall_success'] else '❌ 失败'}")
        report.append("")
        
        # 摘要
        summary = self.validation_results.get("summary", {})
        report.append("验证摘要:")
        report.append(f"  环境验证: {'✅' if summary.get('environment_valid', False) else '❌'}")
        report.append(f"  依赖验证: {'✅' if summary.get('dependencies_valid', False) else '❌'}")
        report.append(f"  功能验证: {'✅' if summary.get('functionality_valid', False) else '❌'}")
        report.append(f"  性能验证: {'✅' if summary.get('performance_valid', False) else '❌'}")
        report.append(f"  总检查数: {summary.get('total_checks', 0)}")
        report.append(f"  成功检查数: {summary.get('successful_checks', 0)}")
        report.append(f"  成功率: {summary.get('success_rate', 0):.2%}")
        report.append("")
        
        # 详细结果
        phases = self.validation_results.get("validation_phases", {})
        for phase_name, phase_result in phases.items():
            report.append(f"=== {phase_name.upper()} ===")
            report.append(f"阶段状态: {'✅ 成功' if phase_result.get('success', False) else '❌ 失败'}")
            
            checks = phase_result.get("checks", [])
            for check in checks:
                status = "✅" if check.get("success", False) else "❌"
                report.append(f"  {status} {check.get('name', 'unknown')}: {check.get('description', '')}")
            
            errors = phase_result.get("errors", [])
            if errors:
                report.append("  错误:")
                for error in errors:
                    report.append(f"    - {error}")
            
            report.append("")
        
        report.append("=" * 60)
        
        return "\n".join(report)


async def main():
    """主函数"""
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 60)
    print("插件框架部署验证")
    print("=" * 60)
    
    # 创建验证器
    validator = DeploymentValidator()
    
    try:
        # 运行验证
        results = await validator.run_full_validation()
        
        # 生成并打印报告
        report = validator.generate_report()
        print(report)
        
        # 保存报告
        report_file = project_root / "deployment_validation_report.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\n报告已保存到: {report_file}")
        
        # 根据结果设置退出码
        exit_code = 0 if results["overall_success"] else 1
        return exit_code
        
    except Exception as e:
        print(f"验证过程中发生异常: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
