"""
插件框架综合集成测试

测试整个插件框架系统的端到端功能，包括所有组件的协同工作、
真实场景模拟和系统稳定性验证。

Author: Mercari AI Agent Team
"""

import asyncio
import pytest
import logging
import os
import sys
import tempfile
import shutil
from typing import Dict, List, Any
from datetime import datetime
import json

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from mercari_agent.plugins.framework import PluginFramework
from mercari_agent.plugins.interfaces import IPlugin, PluginType, PluginState, PluginMetadata
from mercari_agent.plugins.registry import PluginRegistry
from mercari_agent.plugins.loader import PluginLoader
from mercari_agent.plugins.lifecycle import PluginLifecycleManager
from mercari_agent.plugins.config_manager import PluginConfigManager
from mercari_agent.plugins.schemas import PluginSchemaValidator
from mercari_agent.plugins.version_control import PluginVersionManager
from mercari_agent.plugins.examples.basic_plugin import BasicExamplePlugin
from mercari_agent.plugins.examples.advanced_plugin import AdvancedExamplePlugin
from mercari_agent.plugins.examples.integration_example import (
    SessionManagementPluginAdapter,
    FingerprintManagementPluginAdapter, 
    BehaviorSimulationPluginAdapter,
    IntegratedAntiDetectionSystem
)
from mercari_agent.plugins.benchmarks.optimizer import PerformanceOptimizer, OptimizationConfig


class IntegrationTestSuite:
    """集成测试套件"""
    
    def __init__(self):
        self.logger = logging.getLogger("integration_test")
        self.temp_dir = None
        self.test_results = {}
        self.framework = None
        self.plugins = []
        
    async def setup(self):
        """测试环境设置"""
        self.logger.info("设置集成测试环境")
        
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp(prefix="plugin_integration_test_")
        
        # 创建必要的子目录
        os.makedirs(os.path.join(self.temp_dir, "configs"), exist_ok=True)
        os.makedirs(os.path.join(self.temp_dir, "plugins"), exist_ok=True)
        os.makedirs(os.path.join(self.temp_dir, "logs"), exist_ok=True)
        
        # 初始化框架
        self.framework = await PluginFramework.get_instance()
        
        self.logger.info(f"测试环境设置完成，临时目录: {self.temp_dir}")
    
    async def teardown(self):
        """测试环境清理"""
        self.logger.info("清理集成测试环境")
        
        # 清理插件
        if self.framework:
            for plugin in self.plugins:
                try:
                    await self.framework.stop_plugin(plugin.plugin_id)
                    await self.framework.cleanup_plugin(plugin.plugin_id)
                    await self.framework.unregister_plugin(plugin.plugin_id)
                except:
                    pass
        
        # 清理临时目录
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        
        self.logger.info("测试环境清理完成")
    
    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """运行综合测试"""
        self.logger.info("开始运行综合集成测试")
        
        test_start_time = datetime.now()
        results = {
            "start_time": test_start_time.isoformat(),
            "test_phases": {},
            "summary": {},
            "success": True,
            "errors": []
        }
        
        try:
            # 测试阶段1：框架基础功能测试
            self.logger.info("=== 阶段1: 框架基础功能测试 ===")
            phase1_results = await self._test_framework_basics()
            results["test_phases"]["framework_basics"] = phase1_results
            
            # 测试阶段2：插件生命周期测试
            self.logger.info("=== 阶段2: 插件生命周期测试 ===")
            phase2_results = await self._test_plugin_lifecycle()
            results["test_phases"]["plugin_lifecycle"] = phase2_results
            
            # 测试阶段3：配置管理测试
            self.logger.info("=== 阶段3: 配置管理测试 ===")
            phase3_results = await self._test_configuration_management()
            results["test_phases"]["configuration_management"] = phase3_results
            
            # 测试阶段4：版本控制测试
            self.logger.info("=== 阶段4: 版本控制测试 ===")
            phase4_results = await self._test_version_control()
            results["test_phases"]["version_control"] = phase4_results
            
            # 测试阶段5：并发和性能测试
            self.logger.info("=== 阶段5: 并发和性能测试 ===")
            phase5_results = await self._test_concurrent_operations()
            results["test_phases"]["concurrent_operations"] = phase5_results
            
            # 测试阶段6：集成场景测试
            self.logger.info("=== 阶段6: 集成场景测试 ===")
            phase6_results = await self._test_integration_scenarios()
            results["test_phases"]["integration_scenarios"] = phase6_results
            
            # 测试阶段7：故障恢复测试
            self.logger.info("=== 阶段7: 故障恢复测试 ===")
            phase7_results = await self._test_fault_tolerance()
            results["test_phases"]["fault_tolerance"] = phase7_results
            
            # 测试阶段8: 性能基准测试
            self.logger.info("=== 阶段8: 性能基准测试 ===")
            phase8_results = await self._test_performance_benchmarks()
            results["test_phases"]["performance_benchmarks"] = phase8_results
            
        except Exception as e:
            self.logger.error(f"集成测试失败: {e}", exc_info=True)
            results["success"] = False
            results["errors"].append(str(e))
        
        # 生成测试摘要
        results["end_time"] = datetime.now().isoformat()
        results["duration"] = (datetime.now() - test_start_time).total_seconds()
        results["summary"] = self._generate_test_summary(results)
        
        self.test_results = results
        return results
    
    async def _test_framework_basics(self) -> Dict[str, Any]:
        """测试框架基础功能"""
        test_results = {"success": True, "tests": [], "errors": []}
        
        try:
            # 测试框架单例
            framework1 = await PluginFramework.get_instance()
            framework2 = await PluginFramework.get_instance()
            
            test_results["tests"].append({
                "name": "framework_singleton",
                "success": framework1 is framework2,
                "description": "框架单例模式测试"
            })
            
            # 测试插件注册
            test_plugin = BasicExamplePlugin()
            success = await framework1.register_plugin(test_plugin)
            self.plugins.append(test_plugin)
            
            test_results["tests"].append({
                "name": "plugin_registration",
                "success": success,
                "description": "插件注册测试"
            })
            
            # 测试插件获取
            retrieved_plugin = await framework1.get_plugin(test_plugin.plugin_id)
            
            test_results["tests"].append({
                "name": "plugin_retrieval",
                "success": retrieved_plugin is test_plugin,
                "description": "插件获取测试"
            })
            
            # 测试按类型获取插件
            plugins_by_type = await framework1.get_plugins_by_type(test_plugin.plugin_type)
            
            test_results["tests"].append({
                "name": "plugins_by_type",
                "success": test_plugin in plugins_by_type,
                "description": "按类型获取插件测试"
            })
            
            # 测试插件状态获取
            status = await framework1.get_plugins_status()
            
            test_results["tests"].append({
                "name": "plugins_status",
                "success": test_plugin.plugin_id in status,
                "description": "插件状态获取测试"
            })
            
        except Exception as e:
            test_results["success"] = False
            test_results["errors"].append(str(e))
            self.logger.error(f"框架基础功能测试失败: {e}")
        
        return test_results
    
    async def _test_plugin_lifecycle(self) -> Dict[str, Any]:
        """测试插件生命周期"""
        test_results = {"success": True, "tests": [], "errors": []}
        
        try:
            # 创建测试插件
            test_plugin = AdvancedExamplePlugin()
            await self.framework.register_plugin(test_plugin)
            self.plugins.append(test_plugin)
            
            # 测试初始化
            init_success = await self.framework.initialize_plugin(
                test_plugin.plugin_id,
                {"enabled": True, "timeout": 30}
            )
            
            test_results["tests"].append({
                "name": "plugin_initialization",
                "success": init_success and test_plugin.state == PluginState.READY,
                "description": "插件初始化测试"
            })
            
            # 测试启动
            start_success = await self.framework.start_plugin(test_plugin.plugin_id)
            
            test_results["tests"].append({
                "name": "plugin_start",
                "success": start_success and test_plugin.state == PluginState.ACTIVE,
                "description": "插件启动测试"
            })
            
            # 测试健康检查
            health_status = await self.framework.health_check_all()
            
            test_results["tests"].append({
                "name": "plugin_health_check",
                "success": health_status.get(test_plugin.plugin_id, False),
                "description": "插件健康检查测试"
            })
            
            # 测试配置重载
            new_config = {"enabled": True, "timeout": 60, "debug": True}
            reload_success = await self.framework.reload_plugin_config(
                test_plugin.plugin_id, new_config
            )
            
            test_results["tests"].append({
                "name": "plugin_config_reload",
                "success": reload_success,
                "description": "插件配置重载测试"
            })
            
            # 测试停止
            stop_success = await self.framework.stop_plugin(test_plugin.plugin_id)
            
            test_results["tests"].append({
                "name": "plugin_stop",
                "success": stop_success and test_plugin.state == PluginState.INACTIVE,
                "description": "插件停止测试"
            })
            
            # 测试清理
            cleanup_success = await self.framework.cleanup_plugin(test_plugin.plugin_id)
            
            test_results["tests"].append({
                "name": "plugin_cleanup",
                "success": cleanup_success and test_plugin.state == PluginState.UNLOADED,
                "description": "插件清理测试"
            })
            
        except Exception as e:
            test_results["success"] = False
            test_results["errors"].append(str(e))
            self.logger.error(f"插件生命周期测试失败: {e}")
        
        return test_results
    
    async def _test_configuration_management(self) -> Dict[str, Any]:
        """测试配置管理"""
        test_results = {"success": True, "tests": [], "errors": []}
        
        try:
            # 创建配置管理器
            config_manager = PluginConfigManager()
            
            # 创建测试配置文件
            test_config = {
                "enabled": True,
                "timeout": 30.0,
                "retries": 3,
                "debug": False,
                "features": {
                    "caching": True,
                    "monitoring": True
                }
            }
            
            config_file = os.path.join(self.temp_dir, "configs", "test_plugin_config.json")
            with open(config_file, 'w') as f:
                json.dump(test_config, f, indent=2)
            
            # 测试配置加载
            loaded_config = await config_manager.load_config("test_plugin", config_file)
            
            test_results["tests"].append({
                "name": "config_loading",
                "success": loaded_config == test_config,
                "description": "配置文件加载测试"
            })
            
            # 测试配置保存
            modified_config = test_config.copy()
            modified_config["timeout"] = 60.0
            modified_config["debug"] = True
            
            save_success = await config_manager.save_config("test_plugin", modified_config, config_file)
            
            test_results["tests"].append({
                "name": "config_saving",
                "success": save_success,
                "description": "配置文件保存测试"
            })
            
            # 测试配置验证
            schema_validator = PluginSchemaValidator()
            
            # 创建测试schema
            test_schema = {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean"},
                    "timeout": {"type": "number", "minimum": 0},
                    "retries": {"type": "integer", "minimum": 0}
                },
                "required": ["enabled", "timeout"]
            }
            
            validation_success = await schema_validator.validate_config(modified_config, test_schema)
            
            test_results["tests"].append({
                "name": "config_validation",
                "success": validation_success,
                "description": "配置验证测试"
            })
            
            # 测试无效配置验证
            invalid_config = {"enabled": "not_boolean", "timeout": -1}
            invalid_validation = await schema_validator.validate_config(invalid_config, test_schema)
            
            test_results["tests"].append({
                "name": "invalid_config_validation",
                "success": not invalid_validation,
                "description": "无效配置验证测试"
            })
            
        except Exception as e:
            test_results["success"] = False
            test_results["errors"].append(str(e))
            self.logger.error(f"配置管理测试失败: {e}")
        
        return test_results
    
    async def _test_version_control(self) -> Dict[str, Any]:
        """测试版本控制"""
        test_results = {"success": True, "tests": [], "errors": []}
        
        try:
            # 创建版本管理器
            version_manager = PluginVersionManager()
            
            # 测试版本注册
            test_metadata = {
                "name": "测试插件",
                "description": "用于版本控制测试的插件",
                "author": "测试作者",
                "min_framework_version": "1.0.0",
                "dependencies": ["base_plugin:>=1.0.0"]
            }
            
            register_success = await version_manager.register_plugin_version(
                "test_plugin", "1.0.0", test_metadata
            )
            
            test_results["tests"].append({
                "name": "version_registration",
                "success": register_success,
                "description": "版本注册测试"
            })
            
            # 测试版本获取
            version = await version_manager.get_plugin_version("test_plugin")
            
            test_results["tests"].append({
                "name": "version_retrieval",
                "success": version == "1.0.0",
                "description": "版本获取测试"
            })
            
            # 测试兼容性检查
            compatibility = await version_manager.check_compatibility("test_plugin", "1.0.0")
            
            test_results["tests"].append({
                "name": "compatibility_check",
                "success": compatibility,
                "description": "兼容性检查测试"
            })
            
            # 注册新版本
            await version_manager.register_plugin_version("test_plugin", "1.1.0", test_metadata)
            
            # 测试版本列表
            versions = await version_manager.get_plugin_versions("test_plugin")
            
            test_results["tests"].append({
                "name": "version_list",
                "success": "1.0.0" in versions and "1.1.0" in versions,
                "description": "版本列表测试"
            })
            
            # 测试依赖解析
            dependencies = await version_manager.resolve_dependencies("test_plugin", "1.1.0")
            
            test_results["tests"].append({
                "name": "dependency_resolution",
                "success": isinstance(dependencies, list),
                "description": "依赖解析测试"
            })
            
        except Exception as e:
            test_results["success"] = False
            test_results["errors"].append(str(e))
            self.logger.error(f"版本控制测试失败: {e}")
        
        return test_results
    
    async def _test_concurrent_operations(self) -> Dict[str, Any]:
        """测试并发操作"""
        test_results = {"success": True, "tests": [], "errors": []}
        
        try:
            # 创建多个测试插件
            plugins = []
            for i in range(5):
                plugin = BasicExamplePlugin()
                plugin.plugin_id = f"concurrent_test_plugin_{i}"
                await self.framework.register_plugin(plugin)
                plugins.append(plugin)
                self.plugins.append(plugin)
            
            # 测试并发初始化
            init_tasks = []
            for plugin in plugins:
                task = asyncio.create_task(
                    self.framework.initialize_plugin(plugin.plugin_id, {"enabled": True})
                )
                init_tasks.append(task)
            
            init_results = await asyncio.gather(*init_tasks, return_exceptions=True)
            init_success = all(result is True for result in init_results if not isinstance(result, Exception))
            
            test_results["tests"].append({
                "name": "concurrent_initialization",
                "success": init_success,
                "description": "并发初始化测试"
            })
            
            # 测试并发启动
            start_tasks = []
            for plugin in plugins:
                task = asyncio.create_task(
                    self.framework.start_plugin(plugin.plugin_id)
                )
                start_tasks.append(task)
            
            start_results = await asyncio.gather(*start_tasks, return_exceptions=True)
            start_success = all(result is True for result in start_results if not isinstance(result, Exception))
            
            test_results["tests"].append({
                "name": "concurrent_start",
                "success": start_success,
                "description": "并发启动测试"
            })
            
            # 测试并发健康检查
            health_tasks = []
            for _ in range(10):  # 每个插件调用多次
                for plugin in plugins:
                    task = asyncio.create_task(plugin.health_check())
                    health_tasks.append(task)
            
            health_results = await asyncio.gather(*health_tasks, return_exceptions=True)
            health_success = sum(1 for result in health_results if result is True) >= len(health_results) * 0.9
            
            test_results["tests"].append({
                "name": "concurrent_health_check",
                "success": health_success,
                "description": "并发健康检查测试"
            })
            
            # 测试并发状态获取
            status_tasks = []
            for _ in range(10):
                for plugin in plugins:
                    task = asyncio.create_task(plugin.get_status())
                    status_tasks.append(task)
            
            status_results = await asyncio.gather(*status_tasks, return_exceptions=True)
            status_success = sum(1 for result in status_results if isinstance(result, dict)) >= len(status_results) * 0.9
            
            test_results["tests"].append({
                "name": "concurrent_status_check",
                "success": status_success,
                "description": "并发状态获取测试"
            })
            
            # 测试并发停止
            stop_tasks = []
            for plugin in plugins:
                task = asyncio.create_task(
                    self.framework.stop_plugin(plugin.plugin_id)
                )
                stop_tasks.append(task)
            
            stop_results = await asyncio.gather(*stop_tasks, return_exceptions=True)
            stop_success = all(result is True for result in stop_results if not isinstance(result, Exception))
            
            test_results["tests"].append({
                "name": "concurrent_stop",
                "success": stop_success,
                "description": "并发停止测试"
            })
            
        except Exception as e:
            test_results["success"] = False
            test_results["errors"].append(str(e))
            self.logger.error(f"并发操作测试失败: {e}")
        
        return test_results
    
    async def _test_integration_scenarios(self) -> Dict[str, Any]:
        """测试集成场景"""
        test_results = {"success": True, "tests": [], "errors": []}
        
        try:
            # 测试集成反检测系统
            integrated_system = IntegratedAntiDetectionSystem()
            
            # 初始化系统
            init_success = await integrated_system.initialize()
            
            test_results["tests"].append({
                "name": "integrated_system_init",
                "success": init_success,
                "description": "集成系统初始化测试"
            })
            
            if init_success:
                # 测试请求处理
                test_requests = [
                    {
                        "session_id": "test_session_001",
                        "user_agent": "Mozilla/5.0 (Test Browser 1)",
                        "platform": "Windows"
                    },
                    {
                        "session_id": "test_session_002", 
                        "user_agent": "Mozilla/5.0 (Test Browser 2)",
                        "platform": "Linux"
                    }
                ]
                
                request_results = []
                for request_data in test_requests:
                    result = await integrated_system.process_request(request_data)
                    request_results.append(result)
                
                process_success = all(
                    result.get("status") == "success" 
                    for result in request_results
                )
                
                test_results["tests"].append({
                    "name": "integrated_request_processing",
                    "success": process_success,
                    "description": "集成请求处理测试"
                })
                
                # 测试系统状态获取
                system_status = await integrated_system.get_system_status()
                status_success = (
                    system_status.get("system") == "integrated_anti_detection" and
                    system_status.get("healthy", False)
                )
                
                test_results["tests"].append({
                    "name": "integrated_system_status",
                    "success": status_success,
                    "description": "集成系统状态测试"
                })
                
                # 清理集成系统
                await integrated_system.cleanup()
            
        except Exception as e:
            test_results["success"] = False
            test_results["errors"].append(str(e))
            self.logger.error(f"集成场景测试失败: {e}")
        
        return test_results
    
    async def _test_fault_tolerance(self) -> Dict[str, Any]:
        """测试故障容错"""
        test_results = {"success": True, "tests": [], "errors": []}
        
        try:
            # 创建一个会故意失败的插件
            class FaultyPlugin(IPlugin):
                def __init__(self):
                    self.plugin_id = "faulty_test_plugin"
                    self.plugin_type = PluginType.ANTI_DETECTION
                    self.state = PluginState.INACTIVE
                    self.config = {}
                    self.metadata = PluginMetadata(
                        plugin_id=self.plugin_id,
                        name="故障测试插件",
                        version="1.0.0",
                        description="用于测试故障容错的插件",
                        author="测试",
                        plugin_type=self.plugin_type
                    )
                    self._fail_initialization = False
                    self._fail_health_check = False
                
                async def initialize(self, config=None):
                    if self._fail_initialization:
                        raise Exception("故意的初始化失败")
                    self.config = config or {}
                    self.state = PluginState.READY
                    return True
                
                async def start(self):
                    self.state = PluginState.ACTIVE
                    return True
                
                async def stop(self):
                    self.state = PluginState.INACTIVE
                    return True
                
                async def cleanup(self):
                    self.state = PluginState.UNLOADED
                    return True
                
                async def health_check(self):
                    if self._fail_health_check:
                        raise Exception("故意的健康检查失败")
                    return self.state == PluginState.ACTIVE
                
                async def get_status(self):
                    return {
                        "plugin_id": self.plugin_id,
                        "state": self.state.value
                    }
            
            faulty_plugin = FaultyPlugin()
            await self.framework.register_plugin(faulty_plugin)
            self.plugins.append(faulty_plugin)
            
            # 测试初始化失败的容错
            faulty_plugin._fail_initialization = True
            init_result = await self.framework.initialize_plugin(faulty_plugin.plugin_id)
            
            test_results["tests"].append({
                "name": "initialization_failure_tolerance",
                "success": not init_result,  # 应该返回False而不是抛出异常
                "description": "初始化失败容错测试"
            })
            
            # 重置并成功初始化
            faulty_plugin._fail_initialization = False
            await self.framework.initialize_plugin(faulty_plugin.plugin_id)
            await self.framework.start_plugin(faulty_plugin.plugin_id)
            
            # 测试健康检查失败的容错
            faulty_plugin._fail_health_check = True
            health_results = await self.framework.health_check_all()
            
            test_results["tests"].append({
                "name": "health_check_failure_tolerance",
                "success": not health_results.get(faulty_plugin.plugin_id, True),
                "description": "健康检查失败容错测试"
            })
            
            # 测试批量操作中的部分失败
            normal_plugin = BasicExamplePlugin()
            normal_plugin.plugin_id = "normal_test_plugin"
            await self.framework.register_plugin(normal_plugin)
            await self.framework.initialize_plugin(normal_plugin.plugin_id)
            await self.framework.start_plugin(normal_plugin.plugin_id)
            self.plugins.append(normal_plugin)
            
            # 批量健康检查
            all_health = await self.framework.health_check_all()
            
            test_results["tests"].append({
                "name": "partial_failure_handling",
                "success": (
                    not all_health.get(faulty_plugin.plugin_id, True) and  # 故障插件应该失败
                    all_health.get(normal_plugin.plugin_id, False)          # 正常插件应该成功
                ),
                "description": "部分失败处理测试"
            })
            
        except Exception as e:
            test_results["success"] = False
            test_results["errors"].append(str(e))
            self.logger.error(f"故障容错测试失败: {e}")
        
        return test_results
    
    async def _test_performance_benchmarks(self) -> Dict[str, Any]:
        """测试性能基准"""
        test_results = {"success": True, "tests": [], "errors": []}
        
        try:
            # 创建性能优化器
            config = OptimizationConfig(
                benchmark_iterations=10,  # 减少迭代次数用于测试
                load_test_duration=15.0,  # 缩短测试时间
                load_test_users=3,
                monitor_duration=30.0,
                generate_report=False  # 测试中不生成报告
            )
            
            optimizer = PerformanceOptimizer(config)
            
            # 添加一些测试插件
            test_plugins = []
            for i in range(2):
                plugin = BasicExamplePlugin()
                plugin.plugin_id = f"perf_test_plugin_{i}"
                await plugin.initialize({"enabled": True})
                await plugin.start()
                optimizer.add_plugin(plugin)
                test_plugins.append(plugin)
                self.plugins.append(plugin)
            
            # 运行简化的性能测试
            perf_results = await optimizer.run_comprehensive_optimization()
            
            test_results["tests"].append({
                "name": "performance_optimization_execution",
                "success": perf_results.get("success", False),
                "description": "性能优化执行测试"
            })
            
            # 检查是否完成了主要阶段
            phases = perf_results.get("phases", {})
            required_phases = ["baseline", "monitoring", "memory_analysis", "load_tests"]
            completed_phases = sum(1 for phase in required_phases if phase in phases)
            
            test_results["tests"].append({
                "name": "performance_phases_completion",
                "success": completed_phases >= len(required_phases) * 0.75,  # 至少75%的阶段完成
                "description": "性能测试阶段完成度测试"
            })
            
            # 检查优化摘要
            summary = optimizer.get_optimization_summary()
            
            test_results["tests"].append({
                "name": "performance_summary_generation",
                "success": "plugins_optimized" in summary and summary["plugins_optimized"] > 0,
                "description": "性能摘要生成测试"
            })
            
            # 清理测试插件
            for plugin in test_plugins:
                await plugin.stop()
                await plugin.cleanup()
            
        except Exception as e:
            test_results["success"] = False
            test_results["errors"].append(str(e))
            self.logger.error(f"性能基准测试失败: {e}")
        
        return test_results
    
    def _generate_test_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """生成测试摘要"""
        total_phases = len(results["test_phases"])
        successful_phases = sum(
            1 for phase_result in results["test_phases"].values()
            if phase_result.get("success", False)
        )
        
        total_tests = 0
        successful_tests = 0
        
        for phase_result in results["test_phases"].values():
            phase_tests = phase_result.get("tests", [])
            total_tests += len(phase_tests)
            successful_tests += sum(1 for test in phase_tests if test.get("success", False))
        
        return {
            "total_phases": total_phases,
            "successful_phases": successful_phases,
            "phase_success_rate": successful_phases / total_phases if total_phases > 0 else 0,
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "test_success_rate": successful_tests / total_tests if total_tests > 0 else 0,
            "overall_success": results["success"] and successful_phases == total_phases,
            "total_errors": len(results["errors"])
        }


# pytest 测试函数
class TestPluginFrameworkIntegration:
    """插件框架集成测试类"""
    
    @pytest.fixture
    async def test_suite(self):
        """测试套件fixture"""
        suite = IntegrationTestSuite()
        await suite.setup()
        yield suite
        await suite.teardown()
    
    @pytest.mark.asyncio
    async def test_comprehensive_integration(self, test_suite):
        """综合集成测试"""
        results = await test_suite.run_comprehensive_test()
        
        # 断言测试成功
        assert results["success"], f"集成测试失败: {results.get('errors', [])}"
        
        # 检查测试摘要
        summary = results["summary"]
        assert summary["overall_success"], f"测试摘要显示失败: {summary}"
        assert summary["test_success_rate"] > 0.8, f"测试成功率过低: {summary['test_success_rate']}"
        
        # 检查各个阶段
        phases = results["test_phases"]
        assert len(phases) >= 6, f"测试阶段不足: {len(phases)}"
        
        # 重要阶段必须成功
        critical_phases = ["framework_basics", "plugin_lifecycle", "configuration_management"]
        for phase_name in critical_phases:
            assert phase_name in phases, f"缺少关键阶段: {phase_name}"
            assert phases[phase_name]["success"], f"关键阶段失败: {phase_name}"


# 独立运行脚本
async def run_integration_tests():
    """运行集成测试"""
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建并运行测试套件
    suite = IntegrationTestSuite()
    
    try:
        await suite.setup()
        
        print("=== 插件框架综合集成测试 ===")
        results = await suite.run_comprehensive_test()
        
        # 打印结果
        print(f"\n=== 测试结果 ===")
        print(f"测试成功: {results['success']}")
        print(f"测试持续时间: {results['duration']:.2f}秒")
        
        summary = results["summary"]
        print(f"\n=== 测试摘要 ===")
        print(f"总阶段数: {summary['total_phases']}")
        print(f"成功阶段数: {summary['successful_phases']}")
        print(f"阶段成功率: {summary['phase_success_rate']:.2%}")
        print(f"总测试数: {summary['total_tests']}")
        print(f"成功测试数: {summary['successful_tests']}")
        print(f"测试成功率: {summary['test_success_rate']:.2%}")
        print(f"总体成功: {summary['overall_success']}")
        
        # 详细阶段结果
        print(f"\n=== 阶段详情 ===")
        for phase_name, phase_result in results["test_phases"].items():
            status = "✅" if phase_result.get("success", False) else "❌"
            test_count = len(phase_result.get("tests", []))
            successful_count = sum(1 for test in phase_result.get("tests", []) if test.get("success", False))
            
            print(f"{status} {phase_name}: {successful_count}/{test_count} 测试通过")
            
            # 显示失败的测试
            for test in phase_result.get("tests", []):
                if not test.get("success", False):
                    print(f"    ❌ {test['name']}: {test.get('description', '')}")
        
        # 显示错误
        if results["errors"]:
            print(f"\n=== 错误信息 ===")
            for error in results["errors"]:
                print(f"❌ {error}")
        
        return results["success"]
    
    finally:
        await suite.teardown()


if __name__ == "__main__":
    success = asyncio.run(run_integration_tests())
    sys.exit(0 if success else 1)