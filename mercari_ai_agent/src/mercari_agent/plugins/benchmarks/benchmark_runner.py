"""
性能基准测试运行器

提供插件框架的综合性能测试功能，包括启动时间、内存使用、
吞吐量、响应时间等关键性能指标的测试。

Author: Mercari AI Agent Team
"""

import asyncio
import time
import logging
import statistics
import psutil
import gc
import tracemalloc
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from contextlib import asynccontextmanager

from mercari_agent.plugins.interfaces import IPlugin, PluginState
from mercari_agent.plugins.framework import PluginFramework


@dataclass
class BenchmarkResult:
    """基准测试结果"""
    test_name: str
    plugin_id: str
    duration: float
    memory_peak: float
    memory_avg: float
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class BenchmarkConfig:
    """基准测试配置"""
    iterations: int = 100
    warmup_iterations: int = 10
    timeout: float = 30.0
    memory_tracking: bool = True
    gc_between_tests: bool = True
    detailed_metrics: bool = False
    concurrent_plugins: int = 1
    load_test_duration: float = 60.0
    target_rps: int = 100


class BenchmarkRunner:
    """性能基准测试运行器"""
    
    def __init__(self, config: Optional[BenchmarkConfig] = None):
        self.config = config or BenchmarkConfig()
        self.logger = logging.getLogger("benchmark_runner")
        self.results: List[BenchmarkResult] = []
        self._setup_logging()
    
    def _setup_logging(self):
        """设置日志"""
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    async def run_all_benchmarks(self, plugins: List[IPlugin]) -> Dict[str, List[BenchmarkResult]]:
        """运行所有基准测试"""
        self.logger.info("开始运行基准测试套件")
        all_results = {}
        
        try:
            # 插件生命周期测试
            self.logger.info("运行插件生命周期基准测试")
            all_results["lifecycle"] = await self.benchmark_plugin_lifecycle(plugins)
            
            # 配置重载测试
            self.logger.info("运行配置重载基准测试")
            all_results["config_reload"] = await self.benchmark_config_reload(plugins)
            
            # 并发访问测试
            self.logger.info("运行并发访问基准测试")
            all_results["concurrent_access"] = await self.benchmark_concurrent_access(plugins)
            
            # 内存使用测试
            self.logger.info("运行内存使用基准测试")
            all_results["memory_usage"] = await self.benchmark_memory_usage(plugins)
            
            # 负载测试
            self.logger.info("运行负载测试")
            all_results["load_test"] = await self.benchmark_load_test(plugins)
            
            # 框架开销测试
            self.logger.info("运行框架开销基准测试")
            all_results["framework_overhead"] = await self.benchmark_framework_overhead(plugins)
            
            self.logger.info("基准测试套件完成")
            return all_results
            
        except Exception as e:
            self.logger.error(f"基准测试失败: {e}", exc_info=True)
            raise
    
    async def benchmark_plugin_lifecycle(self, plugins: List[IPlugin]) -> List[BenchmarkResult]:
        """基准测试插件生命周期"""
        results = []
        
        for plugin in plugins:
            # 初始化基准测试
            result = await self._benchmark_operation(
                f"initialize_{plugin.plugin_id}",
                plugin.plugin_id,
                lambda: plugin.initialize()
            )
            results.append(result)
            
            # 启动基准测试
            result = await self._benchmark_operation(
                f"start_{plugin.plugin_id}",
                plugin.plugin_id,
                lambda: plugin.start()
            )
            results.append(result)
            
            # 健康检查基准测试
            if plugin.state == PluginState.ACTIVE:
                result = await self._benchmark_operation(
                    f"health_check_{plugin.plugin_id}",
                    plugin.plugin_id,
                    lambda: plugin.health_check(),
                    iterations=self.config.iterations * 10  # 更多迭代
                )
                results.append(result)
                
                # 状态获取基准测试
                result = await self._benchmark_operation(
                    f"get_status_{plugin.plugin_id}",
                    plugin.plugin_id,
                    lambda: plugin.get_status(),
                    iterations=self.config.iterations * 5
                )
                results.append(result)
            
            # 停止基准测试
            result = await self._benchmark_operation(
                f"stop_{plugin.plugin_id}",
                plugin.plugin_id,
                lambda: plugin.stop()
            )
            results.append(result)
            
            # 清理基准测试
            result = await self._benchmark_operation(
                f"cleanup_{plugin.plugin_id}",
                plugin.plugin_id,
                lambda: plugin.cleanup()
            )
            results.append(result)
        
        return results
    
    async def benchmark_config_reload(self, plugins: List[IPlugin]) -> List[BenchmarkResult]:
        """基准测试配置重载"""
        results = []
        
        for plugin in plugins:
            if not hasattr(plugin, 'reload_config'):
                continue
            
            # 准备测试配置
            test_config = {
                "test_setting": "benchmark_value",
                "timeout": 30.0,
                "enabled": True
            }
            
            # 配置重载基准测试
            result = await self._benchmark_operation(
                f"config_reload_{plugin.plugin_id}",
                plugin.plugin_id,
                lambda: plugin.reload_config(test_config),
                iterations=50  # 配置重载通常较慢
            )
            results.append(result)
        
        return results
    
    async def benchmark_concurrent_access(self, plugins: List[IPlugin]) -> List[BenchmarkResult]:
        """基准测试并发访问"""
        results = []
        
        for plugin in plugins:
            if plugin.state != PluginState.ACTIVE:
                continue
            
            # 并发健康检查
            async def concurrent_health_checks():
                tasks = []
                for _ in range(self.config.concurrent_plugins):
                    task = asyncio.create_task(plugin.health_check())
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                return all(isinstance(r, bool) and r for r in results)
            
            result = await self._benchmark_operation(
                f"concurrent_health_check_{plugin.plugin_id}",
                plugin.plugin_id,
                concurrent_health_checks,
                iterations=20
            )
            results.append(result)
            
            # 并发状态获取
            async def concurrent_status_calls():
                tasks = []
                for _ in range(self.config.concurrent_plugins):
                    task = asyncio.create_task(plugin.get_status())
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                return all(isinstance(r, dict) for r in results)
            
            result = await self._benchmark_operation(
                f"concurrent_status_{plugin.plugin_id}",
                plugin.plugin_id,
                concurrent_status_calls,
                iterations=20
            )
            results.append(result)
        
        return results
    
    async def benchmark_memory_usage(self, plugins: List[IPlugin]) -> List[BenchmarkResult]:
        """基准测试内存使用"""
        results = []
        
        if not self.config.memory_tracking:
            return results
        
        for plugin in plugins:
            # 内存使用基准测试
            tracemalloc.start()
            gc.collect()  # 清理垃圾
            
            try:
                # 记录初始内存
                initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
                
                # 执行多次操作
                for _ in range(self.config.iterations):
                    if hasattr(plugin, 'health_check'):
                        await plugin.health_check()
                    if hasattr(plugin, 'get_status'):
                        await plugin.get_status()
                
                # 记录最终内存
                final_memory = psutil.Process().memory_info().rss / 1024 / 1024
                memory_diff = final_memory - initial_memory
                
                # 获取tracemalloc统计
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                
                result = BenchmarkResult(
                    test_name=f"memory_usage_{plugin.plugin_id}",
                    plugin_id=plugin.plugin_id,
                    duration=0.0,  # 内存测试不关注时间
                    memory_peak=peak / 1024 / 1024,  # 转换为MB
                    memory_avg=current / 1024 / 1024,
                    success=True,
                    metadata={
                        "memory_diff_mb": memory_diff,
                        "iterations": self.config.iterations
                    }
                )
                results.append(result)
                
            except Exception as e:
                tracemalloc.stop()
                result = BenchmarkResult(
                    test_name=f"memory_usage_{plugin.plugin_id}",
                    plugin_id=plugin.plugin_id,
                    duration=0.0,
                    memory_peak=0.0,
                    memory_avg=0.0,
                    success=False,
                    error=str(e)
                )
                results.append(result)
        
        return results
    
    async def benchmark_load_test(self, plugins: List[IPlugin]) -> List[BenchmarkResult]:
        """基准测试负载"""
        results = []
        
        for plugin in plugins:
            if plugin.state != PluginState.ACTIVE:
                continue
            
            # 负载测试 - 持续时间内的吞吐量
            async def load_test():
                start_time = time.time()
                end_time = start_time + self.config.load_test_duration
                operations = 0
                errors = 0
                
                while time.time() < end_time:
                    try:
                        # 模拟典型操作
                        if hasattr(plugin, 'health_check'):
                            await plugin.health_check()
                        if hasattr(plugin, 'get_status'):
                            await plugin.get_status()
                        operations += 2
                        
                        # 控制请求速率
                        if self.config.target_rps > 0:
                            await asyncio.sleep(1.0 / self.config.target_rps)
                    
                    except Exception:
                        errors += 1
                
                actual_duration = time.time() - start_time
                throughput = operations / actual_duration
                error_rate = errors / max(operations, 1)
                
                return {
                    "throughput": throughput,
                    "operations": operations,
                    "errors": errors,
                    "error_rate": error_rate,
                    "duration": actual_duration
                }
            
            start_time = time.time()
            load_result = await load_test()
            duration = time.time() - start_time
            
            result = BenchmarkResult(
                test_name=f"load_test_{plugin.plugin_id}",
                plugin_id=plugin.plugin_id,
                duration=duration,
                memory_peak=0.0,
                memory_avg=0.0,
                success=load_result["error_rate"] < 0.01,  # 错误率低于1%
                metadata=load_result
            )
            results.append(result)
        
        return results
    
    async def benchmark_framework_overhead(self, plugins: List[IPlugin]) -> List[BenchmarkResult]:
        """基准测试框架开销"""
        results = []
        
        try:
            framework = await PluginFramework.get_instance()
            
            # 插件注册开销
            dummy_plugin = type('DummyPlugin', (IPlugin,), {
                'plugin_id': 'benchmark_dummy',
                'plugin_type': 'unknown',
                'state': PluginState.INACTIVE,
                'config': {},
                'metadata': None,
                'initialize': lambda self, config=None: asyncio.create_task(asyncio.sleep(0.001)),
                'start': lambda self: asyncio.create_task(asyncio.sleep(0.001)),
                'stop': lambda self: asyncio.create_task(asyncio.sleep(0.001)),
                'cleanup': lambda self: asyncio.create_task(asyncio.sleep(0.001)),
                'health_check': lambda self: asyncio.create_task(asyncio.sleep(0.001)),
                'get_status': lambda self: {'status': 'ok'}
            })()
            
            # 注册基准测试
            result = await self._benchmark_operation(
                "framework_register_plugin",
                "framework",
                lambda: framework.register_plugin(dummy_plugin),
                iterations=10
            )
            results.append(result)
            
            # 获取插件基准测试
            result = await self._benchmark_operation(
                "framework_get_plugin",
                "framework", 
                lambda: framework.get_plugin("benchmark_dummy"),
                iterations=self.config.iterations
            )
            results.append(result)
            
            # 获取所有插件状态基准测试
            result = await self._benchmark_operation(
                "framework_get_plugins_status",
                "framework",
                lambda: framework.get_plugins_status(),
                iterations=50
            )
            results.append(result)
            
            # 健康检查所有插件基准测试
            result = await self._benchmark_operation(
                "framework_health_check_all",
                "framework",
                lambda: framework.health_check_all(),
                iterations=20
            )
            results.append(result)
            
            # 清理测试插件
            await framework.unregister_plugin("benchmark_dummy")
            
        except Exception as e:
            self.logger.error(f"框架开销测试失败: {e}")
        
        return results
    
    async def _benchmark_operation(
        self, 
        test_name: str, 
        plugin_id: str, 
        operation: Callable,
        iterations: Optional[int] = None
    ) -> BenchmarkResult:
        """基准测试单个操作"""
        iterations = iterations or self.config.iterations
        warmup_iterations = self.config.warmup_iterations
        
        # 预热
        for _ in range(warmup_iterations):
            try:
                await self._safe_call(operation)
            except:
                pass
            
            if self.config.gc_between_tests:
                gc.collect()
        
        # 实际测试
        durations = []
        memory_usage = []
        errors = 0
        
        if self.config.memory_tracking:
            tracemalloc.start()
        
        for i in range(iterations):
            if self.config.gc_between_tests and i % 10 == 0:
                gc.collect()
            
            start_time = time.time()
            memory_before = self._get_memory_usage()
            
            try:
                await asyncio.wait_for(
                    self._safe_call(operation), 
                    timeout=self.config.timeout
                )
                
                end_time = time.time()
                memory_after = self._get_memory_usage()
                
                durations.append(end_time - start_time)
                memory_usage.append(memory_after - memory_before)
                
            except Exception as e:
                errors += 1
                self.logger.debug(f"操作失败 {test_name}: {e}")
        
        # 计算统计信息
        success_rate = (iterations - errors) / iterations
        avg_duration = statistics.mean(durations) if durations else 0.0
        
        memory_peak = 0.0
        memory_avg = 0.0
        if self.config.memory_tracking:
            try:
                current, peak = tracemalloc.get_traced_memory()
                memory_peak = peak / 1024 / 1024  # 转换为MB
                memory_avg = current / 1024 / 1024
                tracemalloc.stop()
            except:
                pass
        
        # 创建结果
        result = BenchmarkResult(
            test_name=test_name,
            plugin_id=plugin_id,
            duration=avg_duration,
            memory_peak=memory_peak,
            memory_avg=memory_avg,
            success=success_rate > 0.95,  # 95%成功率
            metadata={
                "iterations": iterations,
                "success_rate": success_rate,
                "errors": errors,
                "min_duration": min(durations) if durations else 0.0,
                "max_duration": max(durations) if durations else 0.0,
                "median_duration": statistics.median(durations) if durations else 0.0,
                "std_duration": statistics.stdev(durations) if len(durations) > 1 else 0.0,
                "p95_duration": self._percentile(durations, 0.95) if durations else 0.0,
                "p99_duration": self._percentile(durations, 0.99) if durations else 0.0,
                "avg_memory_delta": statistics.mean(memory_usage) if memory_usage else 0.0
            }
        )
        
        self.results.append(result)
        return result
    
    async def _safe_call(self, operation: Callable):
        """安全调用操作"""
        if asyncio.iscoroutinefunction(operation):
            return await operation()
        else:
            result = operation()
            if asyncio.iscoroutine(result):
                return await result
            return result
    
    def _get_memory_usage(self) -> float:
        """获取当前内存使用量（MB）"""
        try:
            return psutil.Process().memory_info().rss / 1024 / 1024
        except:
            return 0.0
    
    def _percentile(self, data: List[float], percentile: float) -> float:
        """计算百分位数"""
        if not data:
            return 0.0
        
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile)
        index = min(index, len(sorted_data) - 1)
        return sorted_data[index]
    
    def get_summary_report(self) -> Dict[str, Any]:
        """获取摘要报告"""
        if not self.results:
            return {"error": "没有测试结果"}
        
        # 按测试类型分组
        by_type = {}
        for result in self.results:
            test_type = result.test_name.split('_')[0]
            if test_type not in by_type:
                by_type[test_type] = []
            by_type[test_type].append(result)
        
        # 生成摘要
        summary = {
            "total_tests": len(self.results),
            "successful_tests": sum(1 for r in self.results if r.success),
            "failed_tests": sum(1 for r in self.results if not r.success),
            "avg_duration": statistics.mean([r.duration for r in self.results]),
            "total_memory_peak": max([r.memory_peak for r in self.results]),
            "by_type": {}
        }
        
        for test_type, results in by_type.items():
            summary["by_type"][test_type] = {
                "count": len(results),
                "success_rate": sum(1 for r in results if r.success) / len(results),
                "avg_duration": statistics.mean([r.duration for r in results]),
                "min_duration": min([r.duration for r in results]),
                "max_duration": max([r.duration for r in results]),
                "avg_memory": statistics.mean([r.memory_avg for r in results])
            }
        
        return summary


# 示例使用
async def run_benchmark_example():
    """运行基准测试示例"""
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
    
    # 创建基准测试配置
    config = BenchmarkConfig(
        iterations=50,
        warmup_iterations=5,
        timeout=10.0,
        memory_tracking=True,
        concurrent_plugins=5,
        load_test_duration=30.0
    )
    
    # 运行基准测试
    runner = BenchmarkRunner(config)
    results = await runner.run_all_benchmarks(plugins)
    
    # 打印结果
    print("=== 基准测试结果 ===")
    summary = runner.get_summary_report()
    print(f"总测试数: {summary['total_tests']}")
    print(f"成功率: {summary['successful_tests'] / summary['total_tests']:.2%}")
    print(f"平均耗时: {summary['avg_duration']:.4f}s")
    print(f"内存峰值: {summary['total_memory_peak']:.2f}MB")
    
    # 按类型显示结果
    for test_type, stats in summary["by_type"].items():
        print(f"\n{test_type}:")
        print(f"  测试数量: {stats['count']}")
        print(f"  成功率: {stats['success_rate']:.2%}")
        print(f"  平均耗时: {stats['avg_duration']:.4f}s")
        print(f"  耗时范围: {stats['min_duration']:.4f}s - {stats['max_duration']:.4f}s")
    
    # 清理插件
    for plugin in plugins:
        await plugin.stop()
        await plugin.cleanup()


if __name__ == "__main__":
    asyncio.run(run_benchmark_example())