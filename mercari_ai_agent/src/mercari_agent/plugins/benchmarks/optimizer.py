"""
插件框架性能优化器

整合所有基准测试组件，提供一站式性能优化解决方案，
包括性能测试、监控、分析和优化建议。

Author: Mercari AI Agent Team
"""

import asyncio
import logging
import time
import os
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field

from .benchmark_runner import BenchmarkRunner, BenchmarkConfig
from .performance_monitor import PerformanceMonitor
from .memory_profiler import MemoryProfiler
from .load_tester import LoadTester, LoadTestConfig
from .metrics_collector import BenchmarkMetricsCollector
from .report_generator import BenchmarkReportGenerator, ReportConfig
from mercari_agent.plugins.interfaces import IPlugin


@dataclass
class OptimizationConfig:
    """优化配置"""
    # 基准测试配置
    benchmark_iterations: int = 50
    benchmark_warmup: int = 5
    benchmark_timeout: float = 30.0
    
    # 负载测试配置
    load_test_duration: float = 60.0
    load_test_users: int = 10
    load_test_ramp_time: float = 30.0
    
    # 监控配置
    monitor_interval: float = 2.0
    monitor_duration: float = 300.0  # 5分钟
    
    # 内存分析配置
    memory_sampling_interval: float = 5.0
    memory_leak_detection: bool = True
    
    # 报告配置
    generate_report: bool = True
    report_output_dir: str = "optimization_reports"
    
    # 优化策略
    enable_gc_optimization: bool = True
    enable_memory_optimization: bool = True
    enable_async_optimization: bool = True


class PerformanceOptimizer:
    """性能优化器"""
    
    def __init__(self, config: Optional[OptimizationConfig] = None):
        self.config = config or OptimizationConfig()
        self.logger = logging.getLogger("performance_optimizer")
        
        # 创建组件
        self.benchmark_runner = BenchmarkRunner()
        self.performance_monitor = PerformanceMonitor(
            collection_interval=self.config.monitor_interval
        )
        self.memory_profiler = MemoryProfiler(
            sampling_interval=self.config.memory_sampling_interval
        )
        self.load_tester = LoadTester()
        self.metrics_collector = BenchmarkMetricsCollector()
        self.report_generator = BenchmarkReportGenerator(
            ReportConfig(output_dir=self.config.report_output_dir)
        )
        
        # 插件列表
        self.plugins: List[IPlugin] = []
        
        # 优化结果
        self.optimization_results = {}
        
        # 设置日志
        self._setup_logging()
    
    def _setup_logging(self):
        """设置日志"""
        # 确保日志目录存在
        os.makedirs("logs", exist_ok=True)
        
        # 创建文件处理器
        file_handler = logging.FileHandler(
            f"logs/performance_optimization_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        file_handler.setLevel(logging.INFO)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 创建格式器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 添加处理器
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        self.logger.setLevel(logging.INFO)
    
    def add_plugin(self, plugin: IPlugin):
        """添加要优化的插件"""
        self.plugins.append(plugin)
        
        # 添加到各个组件
        self.performance_monitor.add_plugin(plugin)
        self.memory_profiler.add_plugin(plugin)
        self.load_tester.add_plugin(plugin)
        
        self.logger.info(f"添加插件到性能优化器: {plugin.plugin_id}")
    
    async def run_comprehensive_optimization(self) -> Dict[str, Any]:
        """运行综合性能优化"""
        self.logger.info("开始综合性能优化")
        
        optimization_start = time.time()
        results = {
            "start_time": datetime.now().isoformat(),
            "config": self.config.__dict__,
            "plugins": [p.plugin_id for p in self.plugins],
            "phases": {}
        }
        
        try:
            # 第1阶段：基线测试
            self.logger.info("=== 第1阶段：基线测试 ===")
            baseline_results = await self._run_baseline_tests()
            results["phases"]["baseline"] = baseline_results
            
            # 第2阶段：性能监控
            self.logger.info("=== 第2阶段：性能监控 ===")
            monitoring_results = await self._run_performance_monitoring()
            results["phases"]["monitoring"] = monitoring_results
            
            # 第3阶段：内存分析
            self.logger.info("=== 第3阶段：内存分析 ===")
            memory_results = await self._run_memory_analysis()
            results["phases"]["memory_analysis"] = memory_results
            
            # 第4阶段：负载测试
            self.logger.info("=== 第4阶段：负载测试 ===")
            load_test_results = await self._run_load_tests()
            results["phases"]["load_tests"] = load_test_results
            
            # 第5阶段：性能优化
            self.logger.info("=== 第5阶段：性能优化 ===")
            optimization_results = await self._apply_optimizations()
            results["phases"]["optimization"] = optimization_results
            
            # 第6阶段：验证测试
            self.logger.info("=== 第6阶段：验证测试 ===")
            validation_results = await self._run_validation_tests()
            results["phases"]["validation"] = validation_results
            
            # 第7阶段：报告生成
            if self.config.generate_report:
                self.logger.info("=== 第7阶段：报告生成 ===")
                report_results = await self._generate_reports()
                results["phases"]["report"] = report_results
            
            # 计算总体改进
            improvement = self._calculate_improvement(baseline_results, validation_results)
            results["improvement"] = improvement
            
            results["success"] = True
            results["duration"] = time.time() - optimization_start
            results["end_time"] = datetime.now().isoformat()
            
            self.logger.info(f"综合性能优化完成，耗时: {results['duration']:.2f}秒")
            
        except Exception as e:
            self.logger.error(f"性能优化失败: {e}", exc_info=True)
            results["success"] = False
            results["error"] = str(e)
            results["duration"] = time.time() - optimization_start
            results["end_time"] = datetime.now().isoformat()
        
        self.optimization_results = results
        return results
    
    async def _run_baseline_tests(self) -> Dict[str, Any]:
        """运行基线测试"""
        self.logger.info("运行基线基准测试")
        
        # 配置基准测试
        benchmark_config = BenchmarkConfig(
            iterations=self.config.benchmark_iterations,
            warmup_iterations=self.config.benchmark_warmup,
            timeout=self.config.benchmark_timeout,
            memory_tracking=True
        )
        
        # 运行基准测试
        benchmark_results = await self.benchmark_runner.run_all_benchmarks(self.plugins)
        
        # 收集基线指标
        baseline_metrics = {}
        for plugin in self.plugins:
            if hasattr(plugin, 'health_check'):
                start_time = time.time()
                await plugin.health_check()
                baseline_metrics[f"{plugin.plugin_id}_health_check"] = time.time() - start_time
            
            if hasattr(plugin, 'get_status'):
                start_time = time.time()
                await plugin.get_status()
                baseline_metrics[f"{plugin.plugin_id}_get_status"] = time.time() - start_time
        
        return {
            "benchmark_results": benchmark_results,
            "baseline_metrics": baseline_metrics,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _run_performance_monitoring(self) -> Dict[str, Any]:
        """运行性能监控"""
        self.logger.info("启动性能监控")
        
        # 启动监控
        await self.performance_monitor.start_monitoring()
        
        # 运行一些典型操作
        self.logger.info("执行典型操作以收集性能数据")
        operations_count = 0
        
        try:
            end_time = time.time() + self.config.monitor_duration
            
            while time.time() < end_time:
                for plugin in self.plugins:
                    try:
                        if hasattr(plugin, 'health_check'):
                            await plugin.health_check()
                            operations_count += 1
                        
                        if hasattr(plugin, 'get_status'):
                            await plugin.get_status()
                            operations_count += 1
                    except Exception as e:
                        self.logger.warning(f"插件操作失败: {e}")
                
                await asyncio.sleep(self.config.monitor_interval)
        
        finally:
            # 停止监控
            await self.performance_monitor.stop_monitoring()
        
        # 获取监控报告
        performance_report = self.performance_monitor.get_performance_report()
        
        return {
            "operations_count": operations_count,
            "performance_report": performance_report,
            "alerts": self.performance_monitor.get_alerts(hours=1),
            "timestamp": datetime.now().isoformat()
        }
    
    async def _run_memory_analysis(self) -> Dict[str, Any]:
        """运行内存分析"""
        self.logger.info("启动内存分析")
        
        # 启动内存分析
        await self.memory_profiler.start_profiling()
        
        # 启用泄漏检测
        if self.config.memory_leak_detection:
            self.memory_profiler.enable_leak_detection()
        
        # 运行内存测试
        try:
            # 执行一些内存密集型操作
            for i in range(10):
                for plugin in self.plugins:
                    try:
                        if hasattr(plugin, 'health_check'):
                            await plugin.health_check()
                        
                        if hasattr(plugin, 'get_status'):
                            status = await plugin.get_status()
                            # 故意创建一些对象来测试内存
                            temp_data = [status for _ in range(100)]
                            del temp_data
                    except Exception as e:
                        self.logger.warning(f"内存测试操作失败: {e}")
                
                await asyncio.sleep(1)
            
            # 强制垃圾回收测试
            gc_result = self.memory_profiler.force_gc_and_measure()
            
        finally:
            # 停止内存分析
            await self.memory_profiler.stop_profiling()
        
        # 获取内存报告
        memory_report = self.memory_profiler.get_comprehensive_report()
        
        return {
            "memory_report": memory_report,
            "gc_test_result": gc_result,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _run_load_tests(self) -> Dict[str, Any]:
        """运行负载测试"""
        self.logger.info("运行负载测试")
        
        # 配置负载测试
        load_config = LoadTestConfig(
            duration=self.config.load_test_duration,
            initial_users=1,
            max_users=self.config.load_test_users,
            ramp_up_time=self.config.load_test_ramp_time,
            think_time=0.5,
            timeout=10.0,
            failure_threshold=0.05,
            response_time_threshold=2.0
        )
        
        # 运行各种负载测试
        results = {}
        
        # 恒定负载测试
        results["constant_load"] = await self.load_tester.run_constant_load_test(load_config)
        
        # 递增负载测试
        results["ramp_up"] = await self.load_tester.run_ramp_up_test(load_config)
        
        # 尖峰测试
        results["spike"] = await self.load_tester.run_spike_test(load_config)
        
        # 获取摘要
        summary = self.load_tester.get_summary_report()
        
        return {
            "test_results": results,
            "summary": summary,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _apply_optimizations(self) -> Dict[str, Any]:
        """应用性能优化"""
        self.logger.info("应用性能优化策略")
        
        optimization_results = {
            "applied_optimizations": [],
            "optimization_effects": {},
            "timestamp": datetime.now().isoformat()
        }
        
        # 1. 垃圾回收优化
        if self.config.enable_gc_optimization:
            gc_optimization = await self._apply_gc_optimization()
            optimization_results["applied_optimizations"].append("gc_optimization")
            optimization_results["optimization_effects"]["gc"] = gc_optimization
        
        # 2. 内存优化
        if self.config.enable_memory_optimization:
            memory_optimization = await self._apply_memory_optimization()
            optimization_results["applied_optimizations"].append("memory_optimization")
            optimization_results["optimization_effects"]["memory"] = memory_optimization
        
        # 3. 异步优化
        if self.config.enable_async_optimization:
            async_optimization = await self._apply_async_optimization()
            optimization_results["applied_optimizations"].append("async_optimization")
            optimization_results["optimization_effects"]["async"] = async_optimization
        
        return optimization_results
    
    async def _apply_gc_optimization(self) -> Dict[str, Any]:
        """应用垃圾回收优化"""
        self.logger.info("应用垃圾回收优化")
        
        import gc
        
        # 记录优化前状态
        before_stats = {
            "collections": gc.get_count(),
            "threshold": gc.get_threshold(),
            "objects": len(gc.get_objects())
        }
        
        # 调整GC阈值
        original_threshold = gc.get_threshold()
        # 提高threshold来减少GC频率
        gc.set_threshold(700, 10, 10)
        
        # 执行一次完整的垃圾回收
        collected = [gc.collect(i) for i in range(3)]
        
        # 记录优化后状态
        after_stats = {
            "collections": gc.get_count(),
            "threshold": gc.get_threshold(),
            "objects": len(gc.get_objects()),
            "collected_objects": collected
        }
        
        return {
            "before_stats": before_stats,
            "after_stats": after_stats,
            "original_threshold": original_threshold,
            "new_threshold": gc.get_threshold(),
            "objects_collected": sum(collected)
        }
    
    async def _apply_memory_optimization(self) -> Dict[str, Any]:
        """应用内存优化"""
        self.logger.info("应用内存优化")
        
        import psutil
        
        # 记录优化前内存
        before_memory = psutil.Process().memory_info().rss / 1024 / 1024
        
        # 清理插件缓存（如果有）
        cache_cleared = 0
        for plugin in self.plugins:
            if hasattr(plugin, 'cache') and hasattr(plugin.cache, 'clear'):
                try:
                    await plugin.cache.clear()
                    cache_cleared += 1
                except:
                    pass
        
        # 强制垃圾回收
        import gc
        gc.collect()
        
        # 记录优化后内存
        after_memory = psutil.Process().memory_info().rss / 1024 / 1024
        memory_freed = before_memory - after_memory
        
        return {
            "before_memory_mb": before_memory,
            "after_memory_mb": after_memory,
            "memory_freed_mb": memory_freed,
            "cache_cleared_count": cache_cleared
        }
    
    async def _apply_async_optimization(self) -> Dict[str, Any]:
        """应用异步优化"""
        self.logger.info("应用异步优化")
        
        # 测试并发性能
        concurrent_tasks = 5
        
        # 测试单个调用
        start_time = time.time()
        for plugin in self.plugins:
            if hasattr(plugin, 'health_check'):
                await plugin.health_check()
        sequential_time = time.time() - start_time
        
        # 测试并发调用
        start_time = time.time()
        tasks = []
        for plugin in self.plugins:
            if hasattr(plugin, 'health_check'):
                for _ in range(concurrent_tasks):
                    task = asyncio.create_task(plugin.health_check())
                    tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        concurrent_time = time.time() - start_time
        
        # 计算并发效率
        expected_time = sequential_time * concurrent_tasks
        efficiency = (expected_time - concurrent_time) / expected_time if expected_time > 0 else 0
        
        return {
            "sequential_time": sequential_time,
            "concurrent_time": concurrent_time,
            "expected_time": expected_time,
            "concurrent_efficiency": efficiency,
            "concurrent_tasks": concurrent_tasks * len(self.plugins)
        }
    
    async def _run_validation_tests(self) -> Dict[str, Any]:
        """运行验证测试"""
        self.logger.info("运行验证测试")
        
        # 重新运行基线测试进行对比
        validation_results = await self._run_baseline_tests()
        
        # 运行快速负载测试
        quick_load_config = LoadTestConfig(
            duration=30.0,  # 更短的测试时间
            initial_users=1,
            max_users=5,
            ramp_up_time=10.0,
            think_time=0.5,
            timeout=5.0
        )
        
        quick_load_result = await self.load_tester.run_constant_load_test(quick_load_config)
        validation_results["quick_load_test"] = quick_load_result
        
        return validation_results
    
    async def _generate_reports(self) -> Dict[str, Any]:
        """生成报告"""
        self.logger.info("生成优化报告")
        
        # 收集所有结果
        all_benchmark_results = []
        all_load_test_results = []
        
        # 从各个阶段收集结果
        phases = self.optimization_results.get("phases", {})
        
        # 基线测试结果
        baseline = phases.get("baseline", {})
        if "benchmark_results" in baseline:
            for category, results in baseline["benchmark_results"].items():
                all_benchmark_results.extend(results)
        
        # 验证测试结果
        validation = phases.get("validation", {})
        if "benchmark_results" in validation:
            for category, results in validation["benchmark_results"].items():
                all_benchmark_results.extend(results)
        
        # 负载测试结果
        load_tests = phases.get("load_tests", {})
        if "test_results" in load_tests:
            for test_type, result in load_tests["test_results"].items():
                all_load_test_results.append(result)
        
        # 验证负载测试结果
        if "quick_load_test" in validation:
            all_load_test_results.append(validation["quick_load_test"])
        
        # 生成报告
        report_files = self.report_generator.generate_comprehensive_report(
            benchmark_results=all_benchmark_results,
            load_test_results=all_load_test_results,
            metrics_collector=self.metrics_collector,
            performance_monitor=self.performance_monitor,
            memory_profiler=self.memory_profiler
        )
        
        return {
            "report_files": report_files,
            "benchmark_results_count": len(all_benchmark_results),
            "load_test_results_count": len(all_load_test_results)
        }
    
    def _calculate_improvement(self, baseline: Dict[str, Any], validation: Dict[str, Any]) -> Dict[str, Any]:
        """计算性能改进"""
        improvement = {
            "overall_improvement": 0.0,
            "metrics_improvement": {},
            "summary": "无显著改进"
        }
        
        try:
            # 比较基线指标
            baseline_metrics = baseline.get("baseline_metrics", {})
            validation_metrics = validation.get("baseline_metrics", {})
            
            if baseline_metrics and validation_metrics:
                improvements = []
                
                for metric_name in baseline_metrics:
                    if metric_name in validation_metrics:
                        baseline_value = baseline_metrics[metric_name]
                        validation_value = validation_metrics[metric_name]
                        
                        if baseline_value > 0:
                            improvement_pct = (baseline_value - validation_value) / baseline_value * 100
                            improvements.append(improvement_pct)
                            improvement["metrics_improvement"][metric_name] = improvement_pct
                
                if improvements:
                    improvement["overall_improvement"] = sum(improvements) / len(improvements)
                    
                    if improvement["overall_improvement"] > 5:
                        improvement["summary"] = "显著性能改进"
                    elif improvement["overall_improvement"] > 1:
                        improvement["summary"] = "轻微性能改进"
                    elif improvement["overall_improvement"] < -5:
                        improvement["summary"] = "性能退化"
                    else:
                        improvement["summary"] = "性能稳定"
        
        except Exception as e:
            self.logger.warning(f"计算改进时出错: {e}")
        
        return improvement
    
    def get_optimization_summary(self) -> Dict[str, Any]:
        """获取优化摘要"""
        if not self.optimization_results:
            return {"error": "没有优化结果"}
        
        summary = {
            "success": self.optimization_results.get("success", False),
            "duration": self.optimization_results.get("duration", 0),
            "plugins_optimized": len(self.plugins),
            "phases_completed": len(self.optimization_results.get("phases", {})),
            "improvement": self.optimization_results.get("improvement", {}),
            "report_generated": "report" in self.optimization_results.get("phases", {}),
            "timestamp": self.optimization_results.get("end_time", "unknown")
        }
        
        return summary


# 使用示例
async def optimizer_example():
    """性能优化器示例"""
    from mercari_agent.plugins.examples.basic_plugin import BasicExamplePlugin
    from mercari_agent.plugins.examples.advanced_plugin import AdvancedExamplePlugin
    
    # 创建插件
    plugins = [
        BasicExamplePlugin(),
        AdvancedExamplePlugin()
    ]
    
    # 初始化插件
    for plugin in plugins:
        await plugin.initialize({"enabled": True, "timeout": 30})
        await plugin.start()
    
    # 创建优化器
    config = OptimizationConfig(
        benchmark_iterations=20,  # 减少迭代次数用于演示
        load_test_duration=30.0,  # 减少测试时间
        load_test_users=5,
        monitor_duration=60.0,    # 减少监控时间
        generate_report=True
    )
    
    optimizer = PerformanceOptimizer(config)
    
    # 添加插件
    for plugin in plugins:
        optimizer.add_plugin(plugin)
    
    try:
        print("=== 性能优化器演示 ===")
        print(f"优化 {len(plugins)} 个插件")
        
        # 运行综合优化
        results = await optimizer.run_comprehensive_optimization()
        
        # 显示结果
        if results["success"]:
            print(f"\n✅ 优化成功完成，耗时: {results['duration']:.2f}秒")
            
            # 显示改进情况
            improvement = results.get("improvement", {})
            print(f"总体改进: {improvement.get('overall_improvement', 0):.2f}%")
            print(f"改进摘要: {improvement.get('summary', '无')}")
            
            # 显示各阶段结果
            phases = results.get("phases", {})
            print(f"\n完成阶段: {len(phases)}")
            for phase_name, phase_data in phases.items():
                print(f"  - {phase_name}: ✅")
            
            # 显示报告文件
            if "report" in phases:
                report_files = phases["report"].get("report_files", {})
                if report_files:
                    print(f"\n📊 生成报告:")
                    for format_type, file_path in report_files.items():
                        print(f"  - {format_type.upper()}: {file_path}")
        else:
            print(f"\n❌ 优化失败: {results.get('error', '未知错误')}")
        
        # 获取优化摘要
        summary = optimizer.get_optimization_summary()
        print(f"\n=== 优化摘要 ===")
        print(f"插件数量: {summary['plugins_optimized']}")
        print(f"完成阶段: {summary['phases_completed']}")
        print(f"报告生成: {'是' if summary['report_generated'] else '否'}")
    
    finally:
        # 清理插件
        for plugin in plugins:
            await plugin.stop()
            await plugin.cleanup()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(optimizer_example())