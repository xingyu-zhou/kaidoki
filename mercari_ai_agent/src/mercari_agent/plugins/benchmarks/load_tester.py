"""
负载测试器

提供插件框架的负载测试功能，包括并发测试、压力测试、
稳定性测试等。

Author: Mercari AI Agent Team
"""

import asyncio
import time
import logging
import statistics
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import random

from mercari_agent.plugins.interfaces import IPlugin, PluginState


class LoadTestType(Enum):
    """负载测试类型"""
    CONSTANT_LOAD = "constant_load"
    RAMP_UP = "ramp_up"
    SPIKE = "spike"
    STRESS = "stress"
    ENDURANCE = "endurance"
    VOLUME = "volume"


@dataclass
class LoadTestConfig:
    """负载测试配置"""
    test_type: LoadTestType
    duration: float = 60.0  # 测试持续时间（秒）
    initial_users: int = 1  # 初始用户数
    max_users: int = 10  # 最大用户数
    ramp_up_time: float = 30.0  # 递增时间（秒）
    think_time: float = 1.0  # 思考时间（秒）
    timeout: float = 10.0  # 请求超时时间（秒）
    failure_threshold: float = 0.05  # 失败率阈值（5%）
    response_time_threshold: float = 2.0  # 响应时间阈值（秒）


@dataclass
class LoadTestResult:
    """负载测试结果"""
    test_type: LoadTestType
    start_time: datetime
    end_time: datetime
    duration: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    p95_response_time: float
    p99_response_time: float
    throughput: float  # 每秒请求数
    error_rate: float
    concurrent_users: int
    success: bool
    errors: List[str] = field(default_factory=list)
    detailed_stats: Dict[str, Any] = field(default_factory=dict)


class VirtualUser:
    """虚拟用户"""
    
    def __init__(self, user_id: int, plugins: List[IPlugin], config: LoadTestConfig):
        self.user_id = user_id
        self.plugins = plugins
        self.config = config
        self.logger = logging.getLogger(f"virtual_user_{user_id}")
        
        # 统计信息
        self.requests_sent = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.response_times = []
        self.errors = []
        
        # 运行状态
        self.running = False
        self.start_time = None
        self.end_time = None
    
    async def run(self, duration: float):
        """运行虚拟用户"""
        self.running = True
        self.start_time = datetime.now()
        end_time = time.time() + duration
        
        try:
            while time.time() < end_time and self.running:
                # 选择一个插件进行测试
                plugin = random.choice(self.plugins)
                
                # 执行请求
                await self._execute_request(plugin)
                
                # 思考时间
                if self.config.think_time > 0:
                    await asyncio.sleep(self.config.think_time + random.uniform(-0.1, 0.1))
        
        except Exception as e:
            self.logger.error(f"虚拟用户 {self.user_id} 运行异常: {e}")
            self.errors.append(f"Runtime error: {e}")
        
        finally:
            self.running = False
            self.end_time = datetime.now()
    
    async def _execute_request(self, plugin: IPlugin):
        """执行请求"""
        self.requests_sent += 1
        start_time = time.time()
        
        try:
            # 随机选择操作类型
            operation = random.choice([
                self._health_check_request,
                self._status_request,
                self._config_request
            ])
            
            await asyncio.wait_for(operation(plugin), timeout=self.config.timeout)
            
            response_time = time.time() - start_time
            self.response_times.append(response_time)
            self.successful_requests += 1
            
        except asyncio.TimeoutError:
            self.failed_requests += 1
            self.errors.append(f"Timeout for plugin {plugin.plugin_id}")
        except Exception as e:
            self.failed_requests += 1
            self.errors.append(f"Error for plugin {plugin.plugin_id}: {e}")
    
    async def _health_check_request(self, plugin: IPlugin):
        """健康检查请求"""
        return await plugin.health_check()
    
    async def _status_request(self, plugin: IPlugin):
        """状态请求"""
        return await plugin.get_status()
    
    async def _config_request(self, plugin: IPlugin):
        """配置请求"""
        if hasattr(plugin, 'reload_config'):
            test_config = {"test_param": random.randint(1, 100)}
            return await plugin.reload_config(test_config)
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "user_id": self.user_id,
            "requests_sent": self.requests_sent,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "error_rate": self.failed_requests / max(self.requests_sent, 1),
            "avg_response_time": statistics.mean(self.response_times) if self.response_times else 0,
            "min_response_time": min(self.response_times) if self.response_times else 0,
            "max_response_time": max(self.response_times) if self.response_times else 0,
            "errors": self.errors.copy()
        }


class LoadTester:
    """负载测试器"""
    
    def __init__(self):
        self.logger = logging.getLogger("load_tester")
        self.plugins: List[IPlugin] = []
        self.virtual_users: List[VirtualUser] = []
        self.test_results: List[LoadTestResult] = []
        
        # 实时统计
        self.real_time_stats = {
            "active_users": 0,
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "current_rps": 0.0,
            "avg_response_time": 0.0
        }
    
    def add_plugin(self, plugin: IPlugin):
        """添加要测试的插件"""
        if plugin not in self.plugins:
            self.plugins.append(plugin)
            self.logger.info(f"添加负载测试插件: {plugin.plugin_id}")
    
    def remove_plugin(self, plugin: IPlugin):
        """移除插件"""
        if plugin in self.plugins:
            self.plugins.remove(plugin)
            self.logger.info(f"移除负载测试插件: {plugin.plugin_id}")
    
    async def run_constant_load_test(self, config: LoadTestConfig) -> LoadTestResult:
        """运行恒定负载测试"""
        config.test_type = LoadTestType.CONSTANT_LOAD
        
        self.logger.info(f"开始恒定负载测试: {config.max_users} 用户, {config.duration}s")
        
        # 创建虚拟用户
        users = []
        for i in range(config.max_users):
            user = VirtualUser(i, self.plugins, config)
            users.append(user)
        
        # 启动所有用户
        start_time = datetime.now()
        user_tasks = []
        
        for user in users:
            task = asyncio.create_task(user.run(config.duration))
            user_tasks.append(task)
        
        # 启动实时监控
        monitor_task = asyncio.create_task(self._monitor_real_time_stats(users, config.duration))
        
        # 等待测试完成
        await asyncio.gather(*user_tasks, return_exceptions=True)
        monitor_task.cancel()
        
        end_time = datetime.now()
        
        # 收集结果
        return self._collect_results(config, users, start_time, end_time)
    
    async def run_ramp_up_test(self, config: LoadTestConfig) -> LoadTestResult:
        """运行递增负载测试"""
        config.test_type = LoadTestType.RAMP_UP
        
        self.logger.info(f"开始递增负载测试: {config.initial_users} -> {config.max_users} 用户")
        
        start_time = datetime.now()
        users = []
        user_tasks = []
        
        # 计算用户递增间隔
        user_increment = config.max_users - config.initial_users
        if user_increment > 0:
            increment_interval = config.ramp_up_time / user_increment
        else:
            increment_interval = 0
        
        # 启动初始用户
        for i in range(config.initial_users):
            user = VirtualUser(i, self.plugins, config)
            users.append(user)
            task = asyncio.create_task(user.run(config.duration))
            user_tasks.append(task)
        
        # 启动实时监控
        monitor_task = asyncio.create_task(self._monitor_real_time_stats(users, config.duration))
        
        # 递增用户
        for i in range(config.initial_users, config.max_users):
            await asyncio.sleep(increment_interval)
            
            user = VirtualUser(i, self.plugins, config)
            users.append(user)
            
            remaining_time = config.duration - (time.time() - start_time.timestamp())
            if remaining_time > 0:
                task = asyncio.create_task(user.run(remaining_time))
                user_tasks.append(task)
        
        # 等待测试完成
        await asyncio.gather(*user_tasks, return_exceptions=True)
        monitor_task.cancel()
        
        end_time = datetime.now()
        
        # 收集结果
        return self._collect_results(config, users, start_time, end_time)
    
    async def run_spike_test(self, config: LoadTestConfig) -> LoadTestResult:
        """运行尖峰负载测试"""
        config.test_type = LoadTestType.SPIKE
        
        self.logger.info(f"开始尖峰负载测试: {config.initial_users} -> {config.max_users} 用户")
        
        start_time = datetime.now()
        users = []
        user_tasks = []
        
        # 启动初始用户
        for i in range(config.initial_users):
            user = VirtualUser(i, self.plugins, config)
            users.append(user)
            task = asyncio.create_task(user.run(config.duration))
            user_tasks.append(task)
        
        # 启动实时监控
        monitor_task = asyncio.create_task(self._monitor_real_time_stats(users, config.duration))
        
        # 等待一段时间后产生尖峰
        await asyncio.sleep(config.duration * 0.3)  # 30%时间后产生尖峰
        
        # 快速增加用户（尖峰）
        spike_users = []
        for i in range(config.initial_users, config.max_users):
            user = VirtualUser(i, self.plugins, config)
            users.append(user)
            spike_users.append(user)
            
            remaining_time = config.duration - (time.time() - start_time.timestamp())
            if remaining_time > 0:
                task = asyncio.create_task(user.run(remaining_time * 0.4))  # 尖峰持续40%时间
                user_tasks.append(task)
        
        # 等待测试完成
        await asyncio.gather(*user_tasks, return_exceptions=True)
        monitor_task.cancel()
        
        end_time = datetime.now()
        
        # 收集结果
        return self._collect_results(config, users, start_time, end_time)
    
    async def run_stress_test(self, config: LoadTestConfig) -> LoadTestResult:
        """运行压力测试"""
        config.test_type = LoadTestType.STRESS
        
        # 压力测试使用更多用户和更少的思考时间
        stress_config = LoadTestConfig(
            test_type=LoadTestType.STRESS,
            duration=config.duration,
            initial_users=config.max_users,
            max_users=config.max_users * 2,  # 双倍用户
            think_time=config.think_time * 0.5,  # 一半思考时间
            timeout=config.timeout,
            failure_threshold=config.failure_threshold * 2,  # 放宽失败率
            response_time_threshold=config.response_time_threshold * 2  # 放宽响应时间
        )
        
        self.logger.info(f"开始压力测试: {stress_config.max_users} 用户")
        
        return await self.run_constant_load_test(stress_config)
    
    async def run_endurance_test(self, config: LoadTestConfig) -> LoadTestResult:
        """运行耐久测试"""
        config.test_type = LoadTestType.ENDURANCE
        
        # 耐久测试使用更长时间
        endurance_config = LoadTestConfig(
            test_type=LoadTestType.ENDURANCE,
            duration=config.duration * 10,  # 10倍时间
            initial_users=config.initial_users,
            max_users=config.max_users,
            think_time=config.think_time,
            timeout=config.timeout,
            failure_threshold=config.failure_threshold,
            response_time_threshold=config.response_time_threshold
        )
        
        self.logger.info(f"开始耐久测试: {endurance_config.duration}s")
        
        return await self.run_constant_load_test(endurance_config)
    
    async def run_volume_test(self, config: LoadTestConfig) -> LoadTestResult:
        """运行容量测试"""
        config.test_type = LoadTestType.VOLUME
        
        # 容量测试使用大量用户
        volume_config = LoadTestConfig(
            test_type=LoadTestType.VOLUME,
            duration=config.duration,
            initial_users=config.max_users,
            max_users=config.max_users * 5,  # 5倍用户
            think_time=config.think_time,
            timeout=config.timeout * 2,  # 放宽超时
            failure_threshold=config.failure_threshold * 3,  # 放宽失败率
            response_time_threshold=config.response_time_threshold * 3  # 放宽响应时间
        )
        
        self.logger.info(f"开始容量测试: {volume_config.max_users} 用户")
        
        return await self.run_constant_load_test(volume_config)
    
    async def _monitor_real_time_stats(self, users: List[VirtualUser], duration: float):
        """监控实时统计"""
        start_time = time.time()
        
        try:
            while time.time() - start_time < duration:
                # 收集统计信息
                active_users = sum(1 for user in users if user.running)
                total_requests = sum(user.requests_sent for user in users)
                successful_requests = sum(user.successful_requests for user in users)
                failed_requests = sum(user.failed_requests for user in users)
                
                # 计算RPS
                elapsed_time = time.time() - start_time
                current_rps = total_requests / max(elapsed_time, 1)
                
                # 计算平均响应时间
                all_response_times = []
                for user in users:
                    all_response_times.extend(user.response_times)
                
                avg_response_time = statistics.mean(all_response_times) if all_response_times else 0
                
                # 更新实时统计
                self.real_time_stats = {
                    "active_users": active_users,
                    "total_requests": total_requests,
                    "successful_requests": successful_requests,
                    "failed_requests": failed_requests,
                    "current_rps": current_rps,
                    "avg_response_time": avg_response_time,
                    "elapsed_time": elapsed_time
                }
                
                # 记录进度
                if int(elapsed_time) % 10 == 0:  # 每10秒记录一次
                    self.logger.info(f"负载测试进度: {elapsed_time:.0f}s, "
                                   f"活跃用户: {active_users}, "
                                   f"RPS: {current_rps:.2f}, "
                                   f"平均响应时间: {avg_response_time:.3f}s")
                
                await asyncio.sleep(1)
        
        except asyncio.CancelledError:
            pass
    
    def _collect_results(self, config: LoadTestConfig, users: List[VirtualUser], 
                        start_time: datetime, end_time: datetime) -> LoadTestResult:
        """收集测试结果"""
        # 汇总统计
        total_requests = sum(user.requests_sent for user in users)
        successful_requests = sum(user.successful_requests for user in users)
        failed_requests = sum(user.failed_requests for user in users)
        
        # 收集所有响应时间
        all_response_times = []
        all_errors = []
        
        for user in users:
            all_response_times.extend(user.response_times)
            all_errors.extend(user.errors)
        
        # 计算统计值
        duration = (end_time - start_time).total_seconds()
        error_rate = failed_requests / max(total_requests, 1)
        throughput = total_requests / max(duration, 1)
        
        if all_response_times:
            avg_response_time = statistics.mean(all_response_times)
            min_response_time = min(all_response_times)
            max_response_time = max(all_response_times)
            sorted_times = sorted(all_response_times)
            p95_response_time = sorted_times[int(len(sorted_times) * 0.95)]
            p99_response_time = sorted_times[int(len(sorted_times) * 0.99)]
        else:
            avg_response_time = 0
            min_response_time = 0
            max_response_time = 0
            p95_response_time = 0
            p99_response_time = 0
        
        # 判断测试是否成功
        success = (error_rate <= config.failure_threshold and 
                  avg_response_time <= config.response_time_threshold)
        
        # 创建结果对象
        result = LoadTestResult(
            test_type=config.test_type,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time=avg_response_time,
            min_response_time=min_response_time,
            max_response_time=max_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            throughput=throughput,
            error_rate=error_rate,
            concurrent_users=len(users),
            success=success,
            errors=all_errors[:100],  # 只保留前100个错误
            detailed_stats={
                "user_stats": [user.get_stats() for user in users],
                "config": {
                    "test_type": config.test_type.value,
                    "duration": config.duration,
                    "max_users": config.max_users,
                    "think_time": config.think_time,
                    "timeout": config.timeout
                }
            }
        )
        
        self.test_results.append(result)
        
        # 记录结果
        self.logger.info(f"负载测试完成: {config.test_type.value}")
        self.logger.info(f"总请求数: {total_requests}, 成功率: {(1-error_rate)*100:.1f}%")
        self.logger.info(f"平均响应时间: {avg_response_time:.3f}s, 吞吐量: {throughput:.2f} RPS")
        self.logger.info(f"测试结果: {'通过' if success else '失败'}")
        
        return result
    
    def get_real_time_stats(self) -> Dict[str, Any]:
        """获取实时统计"""
        return self.real_time_stats.copy()
    
    def get_test_results(self) -> List[LoadTestResult]:
        """获取测试结果"""
        return self.test_results.copy()
    
    def get_summary_report(self) -> Dict[str, Any]:
        """获取摘要报告"""
        if not self.test_results:
            return {"error": "没有测试结果"}
        
        # 按测试类型分组
        by_type = {}
        for result in self.test_results:
            test_type = result.test_type.value
            if test_type not in by_type:
                by_type[test_type] = []
            by_type[test_type].append(result)
        
        # 计算总体统计
        total_tests = len(self.test_results)
        successful_tests = sum(1 for r in self.test_results if r.success)
        
        avg_throughput = statistics.mean([r.throughput for r in self.test_results])
        avg_response_time = statistics.mean([r.avg_response_time for r in self.test_results])
        avg_error_rate = statistics.mean([r.error_rate for r in self.test_results])
        
        summary = {
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "success_rate": successful_tests / total_tests,
            "avg_throughput": avg_throughput,
            "avg_response_time": avg_response_time,
            "avg_error_rate": avg_error_rate,
            "by_type": {}
        }
        
        # 按类型统计
        for test_type, results in by_type.items():
            summary["by_type"][test_type] = {
                "count": len(results),
                "success_rate": sum(1 for r in results if r.success) / len(results),
                "avg_throughput": statistics.mean([r.throughput for r in results]),
                "avg_response_time": statistics.mean([r.avg_response_time for r in results]),
                "avg_error_rate": statistics.mean([r.error_rate for r in results]),
                "max_users": max([r.concurrent_users for r in results])
            }
        
        return summary
    
    async def run_comprehensive_test_suite(self, base_config: LoadTestConfig) -> Dict[str, LoadTestResult]:
        """运行综合测试套件"""
        self.logger.info("开始运行综合负载测试套件")
        
        results = {}
        
        try:
            # 1. 恒定负载测试
            self.logger.info("1/6 恒定负载测试")
            results["constant_load"] = await self.run_constant_load_test(base_config)
            
            # 2. 递增负载测试
            self.logger.info("2/6 递增负载测试")
            results["ramp_up"] = await self.run_ramp_up_test(base_config)
            
            # 3. 尖峰测试
            self.logger.info("3/6 尖峰负载测试")
            results["spike"] = await self.run_spike_test(base_config)
            
            # 4. 压力测试
            self.logger.info("4/6 压力测试")
            results["stress"] = await self.run_stress_test(base_config)
            
            # 5. 耐久测试（缩短时间）
            self.logger.info("5/6 耐久测试")
            endurance_config = LoadTestConfig(
                test_type=LoadTestType.ENDURANCE,
                duration=base_config.duration * 3,  # 3倍时间而不是10倍
                initial_users=base_config.initial_users,
                max_users=base_config.max_users,
                think_time=base_config.think_time,
                timeout=base_config.timeout,
                failure_threshold=base_config.failure_threshold,
                response_time_threshold=base_config.response_time_threshold
            )
            results["endurance"] = await self.run_endurance_test(endurance_config)
            
            # 6. 容量测试
            self.logger.info("6/6 容量测试")
            results["volume"] = await self.run_volume_test(base_config)
            
            self.logger.info("综合负载测试套件完成")
            
        except Exception as e:
            self.logger.error(f"测试套件执行失败: {e}")
            raise
        
        return results


# 使用示例
async def load_test_example():
    """负载测试示例"""
    from mercari_agent.plugins.examples.basic_plugin import BasicExamplePlugin
    from mercari_agent.plugins.examples.advanced_plugin import AdvancedExamplePlugin
    
    # 创建测试插件
    plugins = [
        BasicExamplePlugin(),
        AdvancedExamplePlugin()
    ]
    
    # 初始化插件
    for plugin in plugins:
        await plugin.initialize({"enabled": True, "timeout": 30})
        await plugin.start()
    
    # 创建负载测试器
    load_tester = LoadTester()
    
    # 添加插件
    for plugin in plugins:
        load_tester.add_plugin(plugin)
    
    # 配置测试
    config = LoadTestConfig(
        test_type=LoadTestType.CONSTANT_LOAD,
        duration=30.0,
        initial_users=2,
        max_users=8,
        ramp_up_time=15.0,
        think_time=0.5,
        timeout=5.0,
        failure_threshold=0.1,
        response_time_threshold=1.0
    )
    
    try:
        print("=== 负载测试示例 ===")
        
        # 运行恒定负载测试
        print("\n1. 恒定负载测试")
        result = await load_tester.run_constant_load_test(config)
        print(f"结果: {'通过' if result.success else '失败'}")
        print(f"吞吐量: {result.throughput:.2f} RPS")
        print(f"平均响应时间: {result.avg_response_time:.3f}s")
        print(f"错误率: {result.error_rate:.2%}")
        
        # 运行递增负载测试
        print("\n2. 递增负载测试")
        result = await load_tester.run_ramp_up_test(config)
        print(f"结果: {'通过' if result.success else '失败'}")
        print(f"吞吐量: {result.throughput:.2f} RPS")
        print(f"95%响应时间: {result.p95_response_time:.3f}s")
        
        # 运行尖峰测试
        print("\n3. 尖峰负载测试")
        result = await load_tester.run_spike_test(config)
        print(f"结果: {'通过' if result.success else '失败'}")
        print(f"最大响应时间: {result.max_response_time:.3f}s")
        
        # 获取摘要报告
        print("\n=== 摘要报告 ===")
        summary = load_tester.get_summary_report()
        print(f"总测试数: {summary['total_tests']}")
        print(f"成功率: {summary['success_rate']:.2%}")
        print(f"平均吞吐量: {summary['avg_throughput']:.2f} RPS")
        print(f"平均响应时间: {summary['avg_response_time']:.3f}s")
        print(f"平均错误率: {summary['avg_error_rate']:.2%}")
        
        # 按类型显示结果
        for test_type, stats in summary["by_type"].items():
            print(f"\n{test_type}:")
            print(f"  成功率: {stats['success_rate']:.2%}")
            print(f"  吞吐量: {stats['avg_throughput']:.2f} RPS")
            print(f"  响应时间: {stats['avg_response_time']:.3f}s")
    
    finally:
        # 清理插件
        for plugin in plugins:
            await plugin.stop()
            await plugin.cleanup()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(load_test_example())