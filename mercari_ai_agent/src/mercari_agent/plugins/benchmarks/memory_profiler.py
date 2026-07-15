"""
内存分析器

提供详细的内存使用分析，包括内存泄漏检测、对象分配跟踪、
垃圾回收监控等功能。

Author: Mercari AI Agent Team
"""

import gc
import sys
import time
import asyncio
import logging
import tracemalloc
import psutil
from typing import Dict, List, Any, Optional, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict, Counter
import weakref


@dataclass
class MemorySnapshot:
    """内存快照"""
    timestamp: datetime
    total_memory: float  # MB
    process_memory: float  # MB
    python_memory: float  # MB
    gc_stats: Dict[str, int]
    object_counts: Dict[str, int]
    tracemalloc_stats: Optional[Dict[str, Any]] = None


@dataclass
class MemoryLeak:
    """内存泄漏信息"""
    object_type: str
    count_increase: int
    size_increase: float  # MB
    first_detected: datetime
    last_updated: datetime
    stack_traces: List[str] = field(default_factory=list)


class MemoryProfiler:
    """内存分析器"""
    
    def __init__(self, sampling_interval: float = 5.0, snapshot_retention: int = 100):
        self.sampling_interval = sampling_interval
        self.snapshot_retention = snapshot_retention
        self.logger = logging.getLogger("memory_profiler")
        
        # 快照存储
        self.snapshots: List[MemorySnapshot] = []
        
        # 泄漏检测
        self.leak_detection_enabled = False
        self.baseline_counts: Dict[str, int] = {}
        self.detected_leaks: Dict[str, MemoryLeak] = {}
        
        # 对象跟踪
        self.tracked_objects: Set[weakref.ref] = set()
        self.object_allocation_stats: Dict[str, int] = defaultdict(int)
        
        # 监控状态
        self.profiling = False
        self.profile_task: Optional[asyncio.Task] = None
        
        # 插件引用
        self.plugins: List[Any] = []
        
        # 回调
        self.leak_callbacks: List[Callable] = []
    
    def enable_leak_detection(self, baseline_snapshots: int = 5):
        """启用内存泄漏检测"""
        self.leak_detection_enabled = True
        
        # 建立基线
        if len(self.snapshots) >= baseline_snapshots:
            baseline_snapshot = self.snapshots[-baseline_snapshots]
            self.baseline_counts = baseline_snapshot.object_counts.copy()
        
        self.logger.info("内存泄漏检测已启用")
    
    def disable_leak_detection(self):
        """禁用内存泄漏检测"""
        self.leak_detection_enabled = False
        self.baseline_counts.clear()
        self.detected_leaks.clear()
        self.logger.info("内存泄漏检测已禁用")
    
    def add_plugin(self, plugin: Any):
        """添加要分析的插件"""
        self.plugins.append(plugin)
        
        # 跟踪插件对象
        try:
            ref = weakref.ref(plugin, self._object_deleted_callback)
            self.tracked_objects.add(ref)
        except TypeError:
            # 某些对象不支持弱引用
            pass
        
        self.logger.info(f"添加插件内存分析: {getattr(plugin, 'plugin_id', 'unknown')}")
    
    def add_leak_callback(self, callback: Callable[[MemoryLeak], None]):
        """添加泄漏检测回调"""
        self.leak_callbacks.append(callback)
    
    def _object_deleted_callback(self, ref: weakref.ref):
        """对象删除回调"""
        self.tracked_objects.discard(ref)
    
    async def start_profiling(self):
        """开始内存分析"""
        if self.profiling:
            return
        
        # 启用tracemalloc
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        
        self.profiling = True
        self.profile_task = asyncio.create_task(self._profile_loop())
        
        # 初始快照
        await self._take_snapshot()
        
        self.logger.info("内存分析已启动")
    
    async def stop_profiling(self):
        """停止内存分析"""
        if not self.profiling:
            return
        
        self.profiling = False
        
        if self.profile_task:
            self.profile_task.cancel()
            try:
                await self.profile_task
            except asyncio.CancelledError:
                pass
        
        # 停用tracemalloc
        if tracemalloc.is_tracing():
            tracemalloc.stop()
        
        self.logger.info("内存分析已停止")
    
    async def _profile_loop(self):
        """分析循环"""
        while self.profiling:
            try:
                await self._take_snapshot()
                
                if self.leak_detection_enabled:
                    await self._detect_leaks()
                
                await self._analyze_gc_behavior()
                
                # 清理旧快照
                self._cleanup_snapshots()
                
                await asyncio.sleep(self.sampling_interval)
                
            except Exception as e:
                self.logger.error(f"内存分析循环异常: {e}", exc_info=True)
                await asyncio.sleep(self.sampling_interval)
    
    async def _take_snapshot(self) -> MemorySnapshot:
        """拍摄内存快照"""
        try:
            # 获取内存信息
            process = psutil.Process()
            memory_info = process.memory_info()
            
            # 获取Python内存统计
            python_memory = 0
            if tracemalloc.is_tracing():
                current, peak = tracemalloc.get_traced_memory()
                python_memory = current / 1024 / 1024  # 转换为MB
            
            # 获取GC统计
            gc_stats = {
                "collections_0": gc.get_count()[0],
                "collections_1": gc.get_count()[1],
                "collections_2": gc.get_count()[2],
                "total_objects": len(gc.get_objects())
            }
            
            # 获取对象计数
            object_counts = self._count_objects()
            
            # 获取tracemalloc统计
            tracemalloc_stats = None
            if tracemalloc.is_tracing():
                tracemalloc_stats = self._get_tracemalloc_stats()
            
            snapshot = MemorySnapshot(
                timestamp=datetime.now(),
                total_memory=psutil.virtual_memory().total / 1024 / 1024,
                process_memory=memory_info.rss / 1024 / 1024,
                python_memory=python_memory,
                gc_stats=gc_stats,
                object_counts=object_counts,
                tracemalloc_stats=tracemalloc_stats
            )
            
            self.snapshots.append(snapshot)
            return snapshot
            
        except Exception as e:
            self.logger.error(f"拍摄快照失败: {e}")
            raise
    
    def _count_objects(self) -> Dict[str, int]:
        """计算对象数量"""
        object_counts = Counter()
        
        try:
            # 计算所有对象
            for obj in gc.get_objects():
                obj_type = type(obj).__name__
                object_counts[obj_type] += 1
            
            # 添加插件特定对象
            for plugin in self.plugins:
                if hasattr(plugin, '__dict__'):
                    for attr_name, attr_value in plugin.__dict__.items():
                        if hasattr(attr_value, '__class__'):
                            key = f"plugin_{plugin.plugin_id}_{attr_value.__class__.__name__}"
                            object_counts[key] += 1
            
            return dict(object_counts)
            
        except Exception as e:
            self.logger.error(f"对象计数失败: {e}")
            return {}
    
    def _get_tracemalloc_stats(self) -> Dict[str, Any]:
        """获取tracemalloc统计"""
        try:
            current, peak = tracemalloc.get_traced_memory()
            stats = tracemalloc.take_snapshot().statistics('lineno')
            
            # 获取前10个内存使用最多的位置
            top_stats = []
            for stat in stats[:10]:
                top_stats.append({
                    "filename": stat.traceback.format()[0] if stat.traceback.format() else "unknown",
                    "size": stat.size,
                    "count": stat.count
                })
            
            return {
                "current_memory": current,
                "peak_memory": peak,
                "top_allocations": top_stats,
                "total_traces": len(stats)
            }
            
        except Exception as e:
            self.logger.error(f"获取tracemalloc统计失败: {e}")
            return {}
    
    async def _detect_leaks(self):
        """检测内存泄漏"""
        if not self.snapshots or not self.baseline_counts:
            return
        
        current_snapshot = self.snapshots[-1]
        current_counts = current_snapshot.object_counts
        
        # 检查对象数量增长
        for obj_type, current_count in current_counts.items():
            baseline_count = self.baseline_counts.get(obj_type, 0)
            count_increase = current_count - baseline_count
            
            # 泄漏检测阈值（可配置）
            threshold = max(100, baseline_count * 0.5)  # 至少100个或基线的50%
            
            if count_increase > threshold:
                await self._handle_potential_leak(obj_type, count_increase)
    
    async def _handle_potential_leak(self, obj_type: str, count_increase: int):
        """处理潜在内存泄漏"""
        now = datetime.now()
        
        if obj_type in self.detected_leaks:
            # 更新现有泄漏
            leak = self.detected_leaks[obj_type]
            leak.count_increase = count_increase
            leak.last_updated = now
        else:
            # 新检测到的泄漏
            leak = MemoryLeak(
                object_type=obj_type,
                count_increase=count_increase,
                size_increase=0.0,  # 暂时无法精确计算
                first_detected=now,
                last_updated=now
            )
            
            # 获取调用栈
            if tracemalloc.is_tracing():
                leak.stack_traces = self._get_allocation_traces(obj_type)
            
            self.detected_leaks[obj_type] = leak
            
            # 触发回调
            for callback in self.leak_callbacks:
                try:
                    callback(leak)
                except Exception as e:
                    self.logger.error(f"泄漏回调失败: {e}")
            
            self.logger.warning(f"检测到潜在内存泄漏: {obj_type}, 增加数量: {count_increase}")
    
    def _get_allocation_traces(self, obj_type: str, limit: int = 5) -> List[str]:
        """获取对象分配的调用栈"""
        try:
            snapshot = tracemalloc.take_snapshot()
            stats = snapshot.statistics('traceback')
            
            traces = []
            for stat in stats[:limit]:
                if obj_type.lower() in str(stat.traceback).lower():
                    traces.append('\n'.join(stat.traceback.format()))
            
            return traces
            
        except Exception as e:
            self.logger.error(f"获取分配跟踪失败: {e}")
            return []
    
    async def _analyze_gc_behavior(self):
        """分析垃圾回收行为"""
        if len(self.snapshots) < 2:
            return
        
        current = self.snapshots[-1]
        previous = self.snapshots[-2]
        
        # 检查GC频率
        for gen in range(3):
            current_collections = current.gc_stats[f"collections_{gen}"]
            previous_collections = previous.gc_stats[f"collections_{gen}"]
            collections_diff = current_collections - previous_collections
            
            if collections_diff > 10:  # 阈值可配置
                self.logger.info(f"GC第{gen}代回收频繁: {collections_diff}次")
        
        # 检查对象总数变化
        current_objects = current.gc_stats["total_objects"]
        previous_objects = previous.gc_stats["total_objects"]
        objects_diff = current_objects - previous_objects
        
        if abs(objects_diff) > 1000:  # 阈值可配置
            self.logger.info(f"对象总数变化显著: {objects_diff}")
    
    def _cleanup_snapshots(self):
        """清理旧快照"""
        if len(self.snapshots) > self.snapshot_retention:
            self.snapshots = self.snapshots[-self.snapshot_retention:]
    
    def get_current_memory_usage(self) -> Dict[str, float]:
        """获取当前内存使用"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            
            usage = {
                "process_memory_mb": memory_info.rss / 1024 / 1024,
                "virtual_memory_mb": memory_info.vms / 1024 / 1024,
                "memory_percent": process.memory_percent()
            }
            
            if tracemalloc.is_tracing():
                current, peak = tracemalloc.get_traced_memory()
                usage.update({
                    "python_memory_mb": current / 1024 / 1024,
                    "python_peak_mb": peak / 1024 / 1024
                })
            
            return usage
            
        except Exception as e:
            self.logger.error(f"获取内存使用失败: {e}")
            return {}
    
    def get_memory_trend(self, hours: float = 1.0) -> Dict[str, Any]:
        """获取内存使用趋势"""
        if not self.snapshots:
            return {}
        
        # 筛选指定时间范围的快照
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_snapshots = [s for s in self.snapshots if s.timestamp >= cutoff_time]
        
        if len(recent_snapshots) < 2:
            return {}
        
        # 计算趋势
        first_snapshot = recent_snapshots[0]
        last_snapshot = recent_snapshots[-1]
        
        memory_growth = last_snapshot.process_memory - first_snapshot.process_memory
        python_growth = last_snapshot.python_memory - first_snapshot.python_memory
        objects_growth = last_snapshot.gc_stats["total_objects"] - first_snapshot.gc_stats["total_objects"]
        
        time_span_minutes = (last_snapshot.timestamp - first_snapshot.timestamp).total_seconds() / 60
        
        return {
            "time_span_minutes": time_span_minutes,
            "memory_growth_mb": memory_growth,
            "memory_growth_rate_mb_per_hour": memory_growth / (time_span_minutes / 60) if time_span_minutes > 0 else 0,
            "python_growth_mb": python_growth,
            "objects_growth": objects_growth,
            "snapshots_count": len(recent_snapshots),
            "growth_trend": "increasing" if memory_growth > 0 else "decreasing" if memory_growth < 0 else "stable"
        }
    
    def get_object_growth_analysis(self) -> Dict[str, Dict[str, Any]]:
        """获取对象增长分析"""
        if len(self.snapshots) < 2:
            return {}
        
        first_snapshot = self.snapshots[0]
        last_snapshot = self.snapshots[-1]
        
        growth_analysis = {}
        
        for obj_type, last_count in last_snapshot.object_counts.items():
            first_count = first_snapshot.object_counts.get(obj_type, 0)
            growth = last_count - first_count
            
            if abs(growth) > 10:  # 只分析变化较大的对象类型
                growth_analysis[obj_type] = {
                    "first_count": first_count,
                    "last_count": last_count,
                    "growth": growth,
                    "growth_rate": growth / first_count if first_count > 0 else float('inf')
                }
        
        # 按增长数量排序
        sorted_analysis = dict(sorted(
            growth_analysis.items(),
            key=lambda x: abs(x[1]["growth"]),
            reverse=True
        ))
        
        return sorted_analysis
    
    def get_leak_report(self) -> Dict[str, Any]:
        """获取内存泄漏报告"""
        return {
            "detection_enabled": self.leak_detection_enabled,
            "detected_leaks": {
                leak_type: {
                    "count_increase": leak.count_increase,
                    "first_detected": leak.first_detected.isoformat(),
                    "last_updated": leak.last_updated.isoformat(),
                    "stack_traces_count": len(leak.stack_traces)
                }
                for leak_type, leak in self.detected_leaks.items()
            },
            "baseline_objects": len(self.baseline_counts),
            "tracked_objects": len(self.tracked_objects)
        }
    
    def get_gc_analysis(self) -> Dict[str, Any]:
        """获取垃圾回收分析"""
        if not self.snapshots:
            return {}
        
        latest = self.snapshots[-1]
        
        analysis = {
            "current_stats": latest.gc_stats,
            "thresholds": gc.get_threshold(),
            "is_enabled": gc.isenabled()
        }
        
        # 计算GC频率（如果有多个快照）
        if len(self.snapshots) > 1:
            first = self.snapshots[0]
            time_span = (latest.timestamp - first.timestamp).total_seconds() / 60  # 分钟
            
            if time_span > 0:
                analysis["gc_frequency"] = {
                    "gen0_per_minute": (latest.gc_stats["collections_0"] - first.gc_stats["collections_0"]) / time_span,
                    "gen1_per_minute": (latest.gc_stats["collections_1"] - first.gc_stats["collections_1"]) / time_span,
                    "gen2_per_minute": (latest.gc_stats["collections_2"] - first.gc_stats["collections_2"]) / time_span
                }
        
        return analysis
    
    def get_comprehensive_report(self) -> Dict[str, Any]:
        """获取综合内存报告"""
        from datetime import timedelta
        
        return {
            "timestamp": datetime.now().isoformat(),
            "profiling_active": self.profiling,
            "snapshots_count": len(self.snapshots),
            "plugins_count": len(self.plugins),
            "current_usage": self.get_current_memory_usage(),
            "memory_trend": self.get_memory_trend(hours=1.0),
            "object_growth": dict(list(self.get_object_growth_analysis().items())[:10]),  # 前10个
            "leak_report": self.get_leak_report(),
            "gc_analysis": self.get_gc_analysis()
        }
    
    def force_gc_and_measure(self) -> Dict[str, Any]:
        """强制垃圾回收并测量效果"""
        before_stats = self.get_current_memory_usage()
        
        # 执行垃圾回收
        collected_counts = [0, 0, 0]
        for generation in range(3):
            collected_counts[generation] = gc.collect(generation)
        
        # 等待一小会让系统稳定
        time.sleep(0.1)
        
        after_stats = self.get_current_memory_usage()
        
        memory_freed = before_stats.get("process_memory_mb", 0) - after_stats.get("process_memory_mb", 0)
        
        return {
            "before_memory_mb": before_stats.get("process_memory_mb", 0),
            "after_memory_mb": after_stats.get("process_memory_mb", 0),
            "memory_freed_mb": memory_freed,
            "objects_collected": {
                "gen0": collected_counts[0],
                "gen1": collected_counts[1], 
                "gen2": collected_counts[2],
                "total": sum(collected_counts)
            }
        }


# 内存泄漏处理器示例
class MemoryLeakHandler:
    """内存泄漏处理器"""
    
    def __init__(self):
        self.logger = logging.getLogger("memory_leak_handler")
    
    def handle_leak(self, leak: MemoryLeak):
        """处理内存泄漏"""
        self.logger.error(f"检测到内存泄漏: {leak.object_type}")
        self.logger.error(f"对象数量增加: {leak.count_increase}")
        self.logger.error(f"首次检测时间: {leak.first_detected}")
        
        # 记录调用栈
        if leak.stack_traces:
            self.logger.error("调用栈信息:")
            for i, trace in enumerate(leak.stack_traces):
                self.logger.error(f"Stack trace {i+1}:\n{trace}")
        
        # 可以添加更多处理逻辑，如发送告警、自动重启等


# 使用示例
async def memory_profiler_example():
    """内存分析示例"""
    from mercari_agent.plugins.examples.basic_plugin import BasicExamplePlugin
    
    # 创建内存分析器
    profiler = MemoryProfiler(sampling_interval=3.0, snapshot_retention=20)
    
    # 添加泄漏处理器
    leak_handler = MemoryLeakHandler()
    profiler.add_leak_callback(leak_handler.handle_leak)
    
    # 创建插件
    plugin = BasicExamplePlugin()
    await plugin.initialize({"enabled": True})
    await plugin.start()
    
    profiler.add_plugin(plugin)
    
    try:
        # 开始分析
        await profiler.start_profiling()
        
        # 启用泄漏检测
        profiler.enable_leak_detection()
        
        print("内存分析运行中...")
        
        # 模拟一些活动
        for i in range(10):
            await plugin.health_check()
            await plugin.get_status()
            await asyncio.sleep(1)
            
            # 每隔几次打印内存状态
            if i % 3 == 0:
                usage = profiler.get_current_memory_usage()
                print(f"当前内存使用: {usage.get('process_memory_mb', 0):.2f}MB")
        
        # 强制GC测试
        print("\n执行强制垃圾回收...")
        gc_result = profiler.force_gc_and_measure()
        print(f"GC释放内存: {gc_result['memory_freed_mb']:.2f}MB")
        print(f"收集对象: {gc_result['objects_collected']['total']}")
        
        # 获取综合报告
        print("\n=== 内存分析报告 ===")
        report = profiler.get_comprehensive_report()
        
        print(f"快照数量: {report['snapshots_count']}")
        print(f"当前内存: {report['current_usage'].get('process_memory_mb', 0):.2f}MB")
        
        trend = report['memory_trend']
        if trend:
            print(f"内存增长: {trend.get('memory_growth_mb', 0):.2f}MB")
            print(f"增长趋势: {trend.get('growth_trend', 'unknown')}")
        
        # 对象增长分析
        object_growth = report['object_growth']
        if object_growth:
            print("\n主要对象增长:")
            for obj_type, growth_info in list(object_growth.items())[:5]:
                print(f"  {obj_type}: {growth_info['growth']} (+{growth_info['growth_rate']:.1%})")
        
        # 泄漏报告
        leak_report = report['leak_report']
        if leak_report['detected_leaks']:
            print(f"\n检测到 {len(leak_report['detected_leaks'])} 个潜在内存泄漏")
        else:
            print("\n未检测到内存泄漏")
    
    finally:
        # 停止分析
        await profiler.stop_profiling()
        await plugin.stop()
        await plugin.cleanup()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(memory_profiler_example())