#!/usr/bin/env python3
"""
Mercari AI Agent 性能基准测试脚本

该脚本对重构后的系统进行全面的性能评估，包括：
- 启动性能分析
- 运行时性能评估
- 并发处理能力测试
- 内存和资源使用监控
- 网络性能和超时处理
- 性能数据收集和分析

Author: Mercari AI Agent Team
Date: 2025-01-27
"""

import asyncio
import json
import time
import psutil
import threading
import statistics
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import gc
import sys
import tracemalloc
import concurrent.futures
import resource

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

# 导入核心组件
from src.mercari_agent.main import MercariAIAgent
from src.mercari_agent.config.settings import load_settings
from src.mercari_agent.utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class PerformanceMetrics:
    """性能指标数据结构"""
    timestamp: str
    component_name: str
    operation: str
    duration: float
    memory_usage: float
    cpu_usage: float
    success: bool
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None

@dataclass
class ComponentInitMetrics:
    """组件初始化性能指标"""
    component_name: str
    init_duration: float
    memory_before: float
    memory_after: float
    memory_delta: float
    cpu_percent: float
    success: bool
    error_message: Optional[str] = None

@dataclass
class ConcurrencyTestResult:
    """并发测试结果"""
    concurrent_requests: int
    total_duration: float
    success_rate: float
    average_response_time: float
    min_response_time: float
    max_response_time: float
    throughput: float
    errors: List[str]

@dataclass
class MemoryProfile:
    """内存分析结果"""
    peak_memory_mb: float
    average_memory_mb: float
    memory_leaks_detected: bool
    gc_collections: Dict[str, int]
    top_memory_consumers: List[Dict[str, Any]]

class PerformanceBenchmark:
    """性能基准测试类"""
    
    def __init__(self):
        self.metrics: List[PerformanceMetrics] = []
        self.process = psutil.Process()
        self.start_time = time.time()
        self.memory_snapshots = []
        self.tracemalloc_started = False
        
    def start_memory_tracing(self):
        """开始内存追踪"""
        if not self.tracemalloc_started:
            tracemalloc.start()
            self.tracemalloc_started = True
            logger.info("📊 内存追踪已启动")
    
    def stop_memory_tracing(self):
        """停止内存追踪"""
        if self.tracemalloc_started:
            tracemalloc.stop()
            self.tracemalloc_started = False
            logger.info("📊 内存追踪已停止")
    
    def get_memory_usage(self) -> float:
        """获取当前内存使用量(MB)"""
        return self.process.memory_info().rss / 1024 / 1024
    
    def get_cpu_usage(self) -> float:
        """获取当前CPU使用率"""
        return self.process.cpu_percent()
    
    def record_metric(self, 
                     component_name: str, 
                     operation: str,
                     duration: float,
                     success: bool,
                     error_message: Optional[str] = None,
                     metadata: Dict[str, Any] = None):
        """记录性能指标"""
        metric = PerformanceMetrics(
            timestamp=datetime.now().isoformat(),
            component_name=component_name,
            operation=operation,
            duration=duration,
            memory_usage=self.get_memory_usage(),
            cpu_usage=self.get_cpu_usage(),
            success=success,
            error_message=error_message,
            metadata=metadata or {}
        )
        self.metrics.append(metric)
        
        status = "✅" if success else "❌"
        logger.info(f"{status} {component_name}.{operation}: {duration:.3f}s")
    
    async def measure_component_init(self, component_name: str, init_func) -> ComponentInitMetrics:
        """测量组件初始化性能"""
        logger.info(f"🔧 测量组件初始化: {component_name}")
        
        # 记录初始状态
        memory_before = self.get_memory_usage()
        cpu_before = self.get_cpu_usage()
        
        start_time = time.time()
        success = True
        error_message = None
        
        try:
            # 执行初始化
            if asyncio.iscoroutinefunction(init_func):
                await init_func()
            else:
                init_func()
                
        except Exception as e:
            success = False
            error_message = str(e)
            logger.error(f"❌ 组件初始化失败 {component_name}: {e}")
        
        # 记录结束状态
        duration = time.time() - start_time
        memory_after = self.get_memory_usage()
        cpu_after = self.get_cpu_usage()
        
        metrics = ComponentInitMetrics(
            component_name=component_name,
            init_duration=duration,
            memory_before=memory_before,
            memory_after=memory_after,
            memory_delta=memory_after - memory_before,
            cpu_percent=(cpu_before + cpu_after) / 2,
            success=success,
            error_message=error_message
        )
        
        self.record_metric(component_name, "initialization", duration, success, error_message)
        return metrics
    
    async def test_startup_performance(self) -> Dict[str, ComponentInitMetrics]:
        """测试启动性能"""
        logger.info("🚀 开始启动性能测试")
        
        results = {}
        
        # 测试整体初始化
        agent = MercariAIAgent()
        overall_metrics = await self.measure_component_init(
            "MercariAIAgent",
            agent.initialize
        )
        results["overall"] = overall_metrics
        
        # 测试各个组件的初始化时间
        if agent.initialized:
            # LLM服务初始化
            llm_metrics = await self.measure_component_init(
                "LLMService",
                lambda: agent.llm_service
            )
            results["llm_service"] = llm_metrics
            
            # 爬虫服务初始化
            scraper_metrics = await self.measure_component_init(
                "ScraperService", 
                lambda: agent.scraper_service
            )
            results["scraper_service"] = scraper_metrics
            
            # 分析服务初始化
            analysis_metrics = await self.measure_component_init(
                "AnalysisService",
                lambda: agent.analysis_service
            )
            results["analysis_service"] = analysis_metrics
            
            # 工具注册
            tool_metrics = await self.measure_component_init(
                "ToolRegistry",
                lambda: agent.tool_registry
            )
            results["tool_registry"] = tool_metrics
        
        logger.info("✅ 启动性能测试完成")
        return results
    
    async def test_runtime_performance(self, test_queries: List[str]) -> Dict[str, List[PerformanceMetrics]]:
        """测试运行时性能"""
        logger.info("⚡ 开始运行时性能测试")
        
        results = {}
        agent = MercariAIAgent()
        await agent.initialize()
        
        for query in test_queries:
            logger.info(f"📝 测试查询: {query}")
            
            # 记录内存快照
            memory_before = self.get_memory_usage()
            
            start_time = time.time()
            success = True
            error_message = None
            
            try:
                # 执行查询处理
                result = await agent.process_query(query)
                success = result.get("success", False)
                if not success:
                    error_message = result.get("error", "Unknown error")
                    
            except Exception as e:
                success = False
                error_message = str(e)
                logger.error(f"❌ 查询处理失败: {e}")
            
            duration = time.time() - start_time
            memory_after = self.get_memory_usage()
            
            # 记录指标
            self.record_metric(
                "QueryProcessing",
                f"query_{hash(query) % 10000}",
                duration,
                success,
                error_message,
                {
                    "query": query,
                    "memory_delta": memory_after - memory_before
                }
            )
            
            if query not in results:
                results[query] = []
            results[query].append(self.metrics[-1])
            
            # 等待一段时间避免过度负载
            await asyncio.sleep(0.5)
        
        logger.info("✅ 运行时性能测试完成")
        return results
    
    async def test_concurrency(self, query: str, concurrent_count: int = 5) -> ConcurrencyTestResult:
        """测试并发处理能力"""
        logger.info(f"🔄 开始并发测试: {concurrent_count} 个并发请求")
        
        agent = MercariAIAgent()
        await agent.initialize()
        
        # 准备并发任务
        async def single_request():
            start_time = time.time()
            try:
                result = await agent.process_query(query)
                duration = time.time() - start_time
                return {
                    "success": result.get("success", False),
                    "duration": duration,
                    "error": result.get("error") if not result.get("success") else None
                }
            except Exception as e:
                duration = time.time() - start_time
                return {
                    "success": False,
                    "duration": duration,
                    "error": str(e)
                }
        
        # 执行并发请求
        total_start = time.time()
        tasks = [single_request() for _ in range(concurrent_count)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_duration = time.time() - total_start
        
        # 分析结果
        successful_results = []
        errors = []
        
        for result in results:
            if isinstance(result, Exception):
                errors.append(str(result))
            elif result["success"]:
                successful_results.append(result)
            else:
                errors.append(result["error"])
        
        success_rate = len(successful_results) / concurrent_count
        durations = [r["duration"] for r in successful_results]
        
        concurrency_result = ConcurrencyTestResult(
            concurrent_requests=concurrent_count,
            total_duration=total_duration,
            success_rate=success_rate,
            average_response_time=statistics.mean(durations) if durations else 0,
            min_response_time=min(durations) if durations else 0,
            max_response_time=max(durations) if durations else 0,
            throughput=len(successful_results) / total_duration,
            errors=errors
        )
        
        logger.info(f"✅ 并发测试完成: 成功率 {success_rate:.2%}")
        return concurrency_result
    
    def analyze_memory_usage(self) -> MemoryProfile:
        """分析内存使用情况"""
        logger.info("🧠 开始内存使用分析")
        
        # 获取内存快照
        memory_snapshots = [m.memory_usage for m in self.metrics]
        
        # 检测内存泄漏
        if len(memory_snapshots) > 10:
            # 简单的内存泄漏检测：内存使用量持续增长
            recent_memory = memory_snapshots[-10:]
            early_memory = memory_snapshots[:10]
            memory_leaks_detected = statistics.mean(recent_memory) > statistics.mean(early_memory) * 1.2
        else:
            memory_leaks_detected = False
        
        # 获取GC统计信息
        gc_stats = {
            f"generation_{i}": gc.get_count()[i] for i in range(len(gc.get_count()))
        }
        
        # 获取内存消耗大户
        top_consumers = []
        if self.tracemalloc_started:
            try:
                snapshot = tracemalloc.take_snapshot()
                top_stats = snapshot.statistics('lineno')[:10]
                
                for stat in top_stats:
                    top_consumers.append({
                        "filename": stat.traceback.format()[-1],
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count
                    })
            except Exception as e:
                logger.warning(f"无法获取内存追踪信息: {e}")
        
        profile = MemoryProfile(
            peak_memory_mb=max(memory_snapshots) if memory_snapshots else 0,
            average_memory_mb=statistics.mean(memory_snapshots) if memory_snapshots else 0,
            memory_leaks_detected=memory_leaks_detected,
            gc_collections=gc_stats,
            top_memory_consumers=top_consumers
        )
        
        logger.info("✅ 内存使用分析完成")
        return profile
    
    def generate_report(self, 
                       startup_metrics: Dict[str, ComponentInitMetrics],
                       runtime_metrics: Dict[str, List[PerformanceMetrics]],
                       concurrency_results: List[ConcurrencyTestResult],
                       memory_profile: MemoryProfile) -> Dict[str, Any]:
        """生成性能分析报告"""
        logger.info("📋 生成性能分析报告")
        
        # 启动性能摘要
        startup_summary = {
            "total_components": len(startup_metrics),
            "successful_inits": sum(1 for m in startup_metrics.values() if m.success),
            "total_init_time": sum(m.init_duration for m in startup_metrics.values()),
            "memory_overhead": sum(m.memory_delta for m in startup_metrics.values()),
            "component_details": {name: asdict(metrics) for name, metrics in startup_metrics.items()}
        }
        
        # 运行时性能摘要
        all_runtime_metrics = []
        for query_metrics in runtime_metrics.values():
            all_runtime_metrics.extend(query_metrics)
        
        runtime_summary = {
            "total_queries": len(all_runtime_metrics),
            "success_rate": sum(1 for m in all_runtime_metrics if m.success) / len(all_runtime_metrics) if all_runtime_metrics else 0,
            "average_response_time": statistics.mean([m.duration for m in all_runtime_metrics]) if all_runtime_metrics else 0,
            "min_response_time": min([m.duration for m in all_runtime_metrics]) if all_runtime_metrics else 0,
            "max_response_time": max([m.duration for m in all_runtime_metrics]) if all_runtime_metrics else 0,
            "query_details": {query: [asdict(m) for m in metrics] for query, metrics in runtime_metrics.items()}
        }
        
        # 并发性能摘要
        concurrency_summary = {
            "test_count": len(concurrency_results),
            "average_throughput": statistics.mean([r.throughput for r in concurrency_results]) if concurrency_results else 0,
            "best_success_rate": max([r.success_rate for r in concurrency_results]) if concurrency_results else 0,
            "worst_success_rate": min([r.success_rate for r in concurrency_results]) if concurrency_results else 0,
            "test_details": [asdict(r) for r in concurrency_results]
        }
        
        # 系统资源摘要
        resource_summary = {
            "memory_profile": asdict(memory_profile),
            "cpu_usage": {
                "average": statistics.mean([m.cpu_usage for m in self.metrics]) if self.metrics else 0,
                "peak": max([m.cpu_usage for m in self.metrics]) if self.metrics else 0
            },
            "resource_limits": {
                "max_memory_mb": resource.getrlimit(resource.RLIMIT_RSS)[0] / 1024 / 1024,
                "max_processes": resource.getrlimit(resource.RLIMIT_NPROC)[0],
                "max_open_files": resource.getrlimit(resource.RLIMIT_NOFILE)[0]
            }
        }
        
        # 生成综合报告
        report = {
            "test_metadata": {
                "timestamp": datetime.now().isoformat(),
                "test_duration": time.time() - self.start_time,
                "total_metrics": len(self.metrics),
                "python_version": sys.version,
                "platform": sys.platform
            },
            "startup_performance": startup_summary,
            "runtime_performance": runtime_summary,
            "concurrency_performance": concurrency_summary,
            "resource_usage": resource_summary,
            "performance_recommendations": self._generate_recommendations(
                startup_metrics, runtime_metrics, concurrency_results, memory_profile
            )
        }
        
        logger.info("✅ 性能分析报告生成完成")
        return report
    
    def _generate_recommendations(self,
                                startup_metrics: Dict[str, ComponentInitMetrics],
                                runtime_metrics: Dict[str, List[PerformanceMetrics]],
                                concurrency_results: List[ConcurrencyTestResult],
                                memory_profile: MemoryProfile) -> List[str]:
        """生成性能优化建议"""
        recommendations = []
        
        # 启动性能建议
        slow_components = [name for name, metrics in startup_metrics.items() 
                          if metrics.init_duration > 1.0]
        if slow_components:
            recommendations.append(f"启动优化: 以下组件初始化较慢: {', '.join(slow_components)}")
        
        # 内存使用建议
        if memory_profile.memory_leaks_detected:
            recommendations.append("内存优化: 检测到潜在的内存泄漏，建议检查对象生命周期管理")
        
        if memory_profile.peak_memory_mb > 500:
            recommendations.append("内存优化: 内存使用量较高，考虑实现更有效的缓存策略")
        
        # 并发性能建议
        if concurrency_results:
            avg_success_rate = statistics.mean([r.success_rate for r in concurrency_results])
            if avg_success_rate < 0.8:
                recommendations.append("并发优化: 并发成功率较低，建议增加错误处理和重试机制")
        
        # 运行时性能建议
        all_runtime_metrics = []
        for query_metrics in runtime_metrics.values():
            all_runtime_metrics.extend(query_metrics)
        
        if all_runtime_metrics:
            avg_response_time = statistics.mean([m.duration for m in all_runtime_metrics])
            if avg_response_time > 5.0:
                recommendations.append("响应时间优化: 平均响应时间较长，建议优化查询处理流程")
        
        return recommendations


async def main():
    """主测试函数"""
    print("🚀 开始Mercari AI Agent性能基准测试")
    print("=" * 60)
    
    # 创建性能测试实例
    benchmark = PerformanceBenchmark()
    benchmark.start_memory_tracing()
    
    try:
        # 测试查询列表
        test_queries = [
            "iPhone 16",
            "MacBook Pro",
            "Nintendo Switch",
            "ナイキのスニーカー",
            "村上春樹の小説"
        ]
        
        # 1. 启动性能测试
        print("\n1️⃣ 启动性能测试")
        startup_metrics = await benchmark.test_startup_performance()
        
        # 2. 运行时性能测试
        print("\n2️⃣ 运行时性能测试")
        runtime_metrics = await benchmark.test_runtime_performance(test_queries)
        
        # 3. 并发性能测试
        print("\n3️⃣ 并发性能测试")
        concurrency_results = []
        for concurrent_count in [3, 5, 10]:
            result = await benchmark.test_concurrency("iPhone 16", concurrent_count)
            concurrency_results.append(result)
        
        # 4. 内存使用分析
        print("\n4️⃣ 内存使用分析")
        memory_profile = benchmark.analyze_memory_usage()
        
        # 5. 生成报告
        print("\n5️⃣ 生成性能报告")
        report = benchmark.generate_report(
            startup_metrics, runtime_metrics, concurrency_results, memory_profile
        )
        
        # 保存报告
        report_file = f"performance_report_{int(time.time())}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 性能报告已保存: {report_file}")
        
        # 打印关键指标摘要
        print("\n📊 关键性能指标摘要:")
        print("=" * 40)
        print(f"总初始化时间: {report['startup_performance']['total_init_time']:.2f}s")
        print(f"平均响应时间: {report['runtime_performance']['average_response_time']:.2f}s")
        print(f"查询成功率: {report['runtime_performance']['success_rate']:.2%}")
        print(f"峰值内存使用: {report['resource_usage']['memory_profile']['peak_memory_mb']:.2f}MB")
        print(f"平均吞吐量: {report['concurrency_performance']['average_throughput']:.2f} req/s")
        
        if report['performance_recommendations']:
            print("\n💡 性能优化建议:")
            for i, rec in enumerate(report['performance_recommendations'], 1):
                print(f"{i}. {rec}")
        
    except Exception as e:
        logger.error(f"❌ 性能测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        benchmark.stop_memory_tracing()
        print("\n🎉 性能基准测试完成!")


if __name__ == "__main__":
    asyncio.run(main())