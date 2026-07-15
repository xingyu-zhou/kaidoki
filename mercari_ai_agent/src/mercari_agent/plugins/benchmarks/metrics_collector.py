"""
基准测试指标收集器

统一收集和管理插件框架的性能指标，提供标准化的
指标收集、存储和查询接口。

Author: Mercari AI Agent Team
"""

import asyncio
import time
import logging
import json
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from collections import defaultdict, deque
from enum import Enum
import statistics
import threading


class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"
    RATE = "rate"


@dataclass
class MetricPoint:
    """指标数据点"""
    timestamp: datetime
    value: Union[int, float]
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "value": self.value,
            "tags": self.tags
        }


@dataclass
class MetricSeries:
    """指标序列"""
    name: str
    metric_type: MetricType
    unit: str = ""
    description: str = ""
    points: deque = field(default_factory=lambda: deque(maxlen=10000))
    
    def add_point(self, value: Union[int, float], tags: Optional[Dict[str, str]] = None):
        """添加数据点"""
        point = MetricPoint(
            timestamp=datetime.now(),
            value=value,
            tags=tags or {}
        )
        self.points.append(point)
    
    def get_latest_value(self) -> Optional[Union[int, float]]:
        """获取最新值"""
        return self.points[-1].value if self.points else None
    
    def get_values_in_range(self, start_time: datetime, end_time: datetime) -> List[MetricPoint]:
        """获取时间范围内的值"""
        return [p for p in self.points if start_time <= p.timestamp <= end_time]
    
    def get_statistics(self, hours: float = 1.0) -> Dict[str, float]:
        """获取统计信息"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_points = [p for p in self.points if p.timestamp >= cutoff_time]
        
        if not recent_points:
            return {}
        
        values = [p.value for p in recent_points]
        
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0,
            "sum": sum(values),
            "first": values[0],
            "last": values[-1]
        }


class BenchmarkMetricsCollector:
    """基准测试指标收集器"""
    
    def __init__(self, retention_hours: int = 24):
        self.retention_hours = retention_hours
        self.logger = logging.getLogger("metrics_collector")
        self.lock = threading.RLock()
        
        # 指标存储
        self.metrics: Dict[str, MetricSeries] = {}
        
        # 预定义的基准指标
        self._register_standard_metrics()
        
        # 清理任务
        self.cleanup_task: Optional[asyncio.Task] = None
        self.cleanup_interval = 3600  # 1小时清理一次
    
    def _register_standard_metrics(self):
        """注册标准指标"""
        # 系统资源指标
        self.register_metric("system.cpu.usage", MetricType.GAUGE, "%", "CPU使用率")
        self.register_metric("system.memory.usage", MetricType.GAUGE, "%", "内存使用率")
        self.register_metric("system.memory.available", MetricType.GAUGE, "MB", "可用内存")
        self.register_metric("system.disk.usage", MetricType.GAUGE, "%", "磁盘使用率")
        
        # 插件生命周期指标
        self.register_metric("plugin.initialize.duration", MetricType.TIMER, "s", "插件初始化时间")
        self.register_metric("plugin.start.duration", MetricType.TIMER, "s", "插件启动时间")
        self.register_metric("plugin.stop.duration", MetricType.TIMER, "s", "插件停止时间")
        self.register_metric("plugin.cleanup.duration", MetricType.TIMER, "s", "插件清理时间")
        
        # 插件操作指标
        self.register_metric("plugin.health_check.duration", MetricType.TIMER, "s", "健康检查时间")
        self.register_metric("plugin.health_check.success", MetricType.COUNTER, "", "健康检查成功次数")
        self.register_metric("plugin.health_check.failure", MetricType.COUNTER, "", "健康检查失败次数")
        self.register_metric("plugin.get_status.duration", MetricType.TIMER, "s", "获取状态时间")
        self.register_metric("plugin.config_reload.duration", MetricType.TIMER, "s", "配置重载时间")
        
        # 框架操作指标
        self.register_metric("framework.plugin.count", MetricType.GAUGE, "", "插件数量")
        self.register_metric("framework.active_plugins", MetricType.GAUGE, "", "活跃插件数")
        self.register_metric("framework.get_status.duration", MetricType.TIMER, "s", "框架状态获取时间")
        self.register_metric("framework.health_check.duration", MetricType.TIMER, "s", "框架健康检查时间")
        
        # 负载测试指标
        self.register_metric("load_test.requests.total", MetricType.COUNTER, "", "总请求数")
        self.register_metric("load_test.requests.successful", MetricType.COUNTER, "", "成功请求数")
        self.register_metric("load_test.requests.failed", MetricType.COUNTER, "", "失败请求数")
        self.register_metric("load_test.response_time", MetricType.HISTOGRAM, "s", "响应时间")
        self.register_metric("load_test.throughput", MetricType.GAUGE, "rps", "吞吐量")
        self.register_metric("load_test.error_rate", MetricType.GAUGE, "%", "错误率")
        self.register_metric("load_test.concurrent_users", MetricType.GAUGE, "", "并发用户数")
        
        # 内存指标
        self.register_metric("memory.process.rss", MetricType.GAUGE, "MB", "进程内存使用")
        self.register_metric("memory.process.vms", MetricType.GAUGE, "MB", "虚拟内存使用")
        self.register_metric("memory.python.current", MetricType.GAUGE, "MB", "Python内存使用")
        self.register_metric("memory.python.peak", MetricType.GAUGE, "MB", "Python内存峰值")
        self.register_metric("memory.gc.collections", MetricType.COUNTER, "", "GC回收次数")
        self.register_metric("memory.objects.count", MetricType.GAUGE, "", "对象数量")
    
    def register_metric(self, name: str, metric_type: MetricType, unit: str = "", description: str = ""):
        """注册指标"""
        with self.lock:
            if name not in self.metrics:
                self.metrics[name] = MetricSeries(
                    name=name,
                    metric_type=metric_type,
                    unit=unit,
                    description=description
                )
                self.logger.debug(f"注册指标: {name} ({metric_type.value})")
    
    def record_counter(self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None):
        """记录计数器指标"""
        with self.lock:
            if name not in self.metrics:
                self.register_metric(name, MetricType.COUNTER)
            
            # 获取当前值并累加
            current_value = self.metrics[name].get_latest_value() or 0
            self.metrics[name].add_point(current_value + value, tags)
    
    def record_gauge(self, name: str, value: Union[int, float], tags: Optional[Dict[str, str]] = None):
        """记录仪表指标"""
        with self.lock:
            if name not in self.metrics:
                self.register_metric(name, MetricType.GAUGE)
            
            self.metrics[name].add_point(value, tags)
    
    def record_histogram(self, name: str, value: Union[int, float], tags: Optional[Dict[str, str]] = None):
        """记录直方图指标"""
        with self.lock:
            if name not in self.metrics:
                self.register_metric(name, MetricType.HISTOGRAM)
            
            self.metrics[name].add_point(value, tags)
    
    def record_timer(self, name: str, duration: float, tags: Optional[Dict[str, str]] = None):
        """记录定时器指标"""
        with self.lock:
            if name not in self.metrics:
                self.register_metric(name, MetricType.TIMER)
            
            self.metrics[name].add_point(duration, tags)
    
    def record_rate(self, name: str, value: Union[int, float], tags: Optional[Dict[str, str]] = None):
        """记录速率指标"""
        with self.lock:
            if name not in self.metrics:
                self.register_metric(name, MetricType.RATE)
            
            self.metrics[name].add_point(value, tags)
    
    def increment_counter(self, name: str, tags: Optional[Dict[str, str]] = None):
        """递增计数器"""
        self.record_counter(name, 1, tags)
    
    def timing_context(self, name: str, tags: Optional[Dict[str, str]] = None):
        """计时上下文管理器"""
        return TimingContext(self, name, tags)
    
    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """获取指标"""
        with self.lock:
            return self.metrics.get(name)
    
    def get_metric_value(self, name: str) -> Optional[Union[int, float]]:
        """获取指标最新值"""
        metric = self.get_metric(name)
        return metric.get_latest_value() if metric else None
    
    def get_metric_statistics(self, name: str, hours: float = 1.0) -> Dict[str, float]:
        """获取指标统计信息"""
        metric = self.get_metric(name)
        return metric.get_statistics(hours) if metric else {}
    
    def get_all_metrics(self) -> Dict[str, MetricSeries]:
        """获取所有指标"""
        with self.lock:
            return self.metrics.copy()
    
    def get_metric_names(self) -> List[str]:
        """获取所有指标名称"""
        with self.lock:
            return list(self.metrics.keys())
    
    def get_metrics_by_type(self, metric_type: MetricType) -> Dict[str, MetricSeries]:
        """根据类型获取指标"""
        with self.lock:
            return {name: metric for name, metric in self.metrics.items() 
                   if metric.metric_type == metric_type}
    
    def get_metrics_by_pattern(self, pattern: str) -> Dict[str, MetricSeries]:
        """根据模式获取指标"""
        import re
        with self.lock:
            regex = re.compile(pattern)
            return {name: metric for name, metric in self.metrics.items() 
                   if regex.search(name)}
    
    def get_current_snapshot(self) -> Dict[str, Any]:
        """获取当前快照"""
        with self.lock:
            snapshot = {
                "timestamp": datetime.now().isoformat(),
                "metrics": {}
            }
            
            for name, metric in self.metrics.items():
                latest_value = metric.get_latest_value()
                if latest_value is not None:
                    snapshot["metrics"][name] = {
                        "value": latest_value,
                        "type": metric.metric_type.value,
                        "unit": metric.unit,
                        "description": metric.description
                    }
            
            return snapshot
    
    def get_time_series_data(self, name: str, hours: float = 1.0) -> List[Dict[str, Any]]:
        """获取时间序列数据"""
        metric = self.get_metric(name)
        if not metric:
            return []
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_points = [p for p in metric.points if p.timestamp >= cutoff_time]
        
        return [point.to_dict() for point in recent_points]
    
    def clear_metric(self, name: str):
        """清除指标"""
        with self.lock:
            if name in self.metrics:
                self.metrics[name].points.clear()
                self.logger.debug(f"清除指标: {name}")
    
    def clear_all_metrics(self):
        """清除所有指标"""
        with self.lock:
            for metric in self.metrics.values():
                metric.points.clear()
            self.logger.info("清除所有指标")
    
    def export_metrics(self, format: str = "json", hours: float = 1.0) -> str:
        """导出指标数据"""
        if format.lower() == "json":
            return self._export_json(hours)
        elif format.lower() == "csv":
            return self._export_csv(hours)
        elif format.lower() == "prometheus":
            return self._export_prometheus()
        else:
            raise ValueError(f"不支持的导出格式: {format}")
    
    def _export_json(self, hours: float) -> str:
        """导出为JSON格式"""
        export_data = {
            "timestamp": datetime.now().isoformat(),
            "time_range_hours": hours,
            "metrics": {}
        }
        
        for name, metric in self.metrics.items():
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent_points = [p for p in metric.points if p.timestamp >= cutoff_time]
            
            export_data["metrics"][name] = {
                "type": metric.metric_type.value,
                "unit": metric.unit,
                "description": metric.description,
                "points": [point.to_dict() for point in recent_points],
                "statistics": metric.get_statistics(hours)
            }
        
        return json.dumps(export_data, indent=2, default=str)
    
    def _export_csv(self, hours: float) -> str:
        """导出为CSV格式"""
        lines = ["timestamp,metric_name,value,tags"]
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        for name, metric in self.metrics.items():
            for point in metric.points:
                if point.timestamp >= cutoff_time:
                    tags_str = ";".join(f"{k}={v}" for k, v in point.tags.items())
                    lines.append(f"{point.timestamp.isoformat()},{name},{point.value},{tags_str}")
        
        return "\n".join(lines)
    
    def _export_prometheus(self) -> str:
        """导出为Prometheus格式"""
        lines = []
        
        for name, metric in self.metrics.items():
            # 清理指标名称以符合Prometheus命名规范
            prom_name = name.replace(".", "_").replace("-", "_")
            
            # 添加元数据
            if metric.description:
                lines.append(f"# HELP {prom_name} {metric.description}")
            lines.append(f"# TYPE {prom_name} {metric.metric_type.value}")
            
            # 添加数据点
            latest_value = metric.get_latest_value()
            if latest_value is not None:
                lines.append(f"{prom_name} {latest_value}")
        
        return "\n".join(lines)
    
    def start_cleanup_task(self):
        """启动清理任务"""
        if self.cleanup_task is None:
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            self.logger.info("启动指标清理任务")
    
    def stop_cleanup_task(self):
        """停止清理任务"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            self.cleanup_task = None
            self.logger.info("停止指标清理任务")
    
    async def _cleanup_loop(self):
        """清理循环"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                self._cleanup_old_data()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"指标清理异常: {e}")
    
    def _cleanup_old_data(self):
        """清理过期数据"""
        cutoff_time = datetime.now() - timedelta(hours=self.retention_hours)
        cleaned_count = 0
        
        with self.lock:
            for metric in self.metrics.values():
                original_length = len(metric.points)
                # 使用deque的特性，移除旧数据
                while metric.points and metric.points[0].timestamp < cutoff_time:
                    metric.points.popleft()
                
                cleaned_count += original_length - len(metric.points)
        
        if cleaned_count > 0:
            self.logger.debug(f"清理了 {cleaned_count} 个过期数据点")
    
    def get_summary_statistics(self) -> Dict[str, Any]:
        """获取摘要统计"""
        with self.lock:
            summary = {
                "total_metrics": len(self.metrics),
                "total_data_points": sum(len(metric.points) for metric in self.metrics.values()),
                "metrics_by_type": defaultdict(int),
                "latest_values": {},
                "top_metrics": {}
            }
            
            # 按类型统计
            for metric in self.metrics.values():
                summary["metrics_by_type"][metric.metric_type.value] += 1
            
            # 最新值
            for name, metric in self.metrics.items():
                latest_value = metric.get_latest_value()
                if latest_value is not None:
                    summary["latest_values"][name] = latest_value
            
            # 热门指标（数据点最多的前10个）
            sorted_metrics = sorted(
                self.metrics.items(),
                key=lambda x: len(x[1].points),
                reverse=True
            )
            
            for name, metric in sorted_metrics[:10]:
                summary["top_metrics"][name] = {
                    "data_points": len(metric.points),
                    "type": metric.metric_type.value,
                    "unit": metric.unit
                }
            
            return summary


class TimingContext:
    """计时上下文管理器"""
    
    def __init__(self, collector: BenchmarkMetricsCollector, name: str, tags: Optional[Dict[str, str]] = None):
        self.collector = collector
        self.name = name
        self.tags = tags
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            self.collector.record_timer(self.name, duration, self.tags)


# 全局指标收集器实例
_global_collector = None


def get_global_collector() -> BenchmarkMetricsCollector:
    """获取全局指标收集器"""
    global _global_collector
    if _global_collector is None:
        _global_collector = BenchmarkMetricsCollector()
    return _global_collector


# 便捷函数
def record_counter(name: str, value: int = 1, tags: Optional[Dict[str, str]] = None):
    """记录计数器"""
    get_global_collector().record_counter(name, value, tags)


def record_gauge(name: str, value: Union[int, float], tags: Optional[Dict[str, str]] = None):
    """记录仪表"""
    get_global_collector().record_gauge(name, value, tags)


def record_histogram(name: str, value: Union[int, float], tags: Optional[Dict[str, str]] = None):
    """记录直方图"""
    get_global_collector().record_histogram(name, value, tags)


def record_timer(name: str, duration: float, tags: Optional[Dict[str, str]] = None):
    """记录定时器"""
    get_global_collector().record_timer(name, duration, tags)


def timing(name: str, tags: Optional[Dict[str, str]] = None):
    """计时装饰器"""
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                with get_global_collector().timing_context(name, tags):
                    return await func(*args, **kwargs)
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                with get_global_collector().timing_context(name, tags):
                    return func(*args, **kwargs)
            return sync_wrapper
    return decorator


# 使用示例
async def metrics_collector_example():
    """指标收集器示例"""
    # 创建收集器
    collector = BenchmarkMetricsCollector()
    
    # 启动清理任务
    collector.start_cleanup_task()
    
    try:
        print("=== 指标收集器示例 ===")
        
        # 记录各种类型的指标
        print("\n1. 记录指标...")
        
        # 计数器
        for i in range(10):
            collector.increment_counter("test.requests", {"method": "GET"})
            collector.increment_counter("test.requests", {"method": "POST"})
        
        # 仪表
        collector.record_gauge("test.cpu.usage", 75.5)
        collector.record_gauge("test.memory.usage", 1024.0)
        
        # 直方图
        import random
        for i in range(20):
            collector.record_histogram("test.response_time", random.uniform(0.1, 2.0))
        
        # 定时器
        for i in range(5):
            with collector.timing_context("test.operation"):
                await asyncio.sleep(0.1)
        
        # 获取当前快照
        print("\n2. 获取快照...")
        snapshot = collector.get_current_snapshot()
        print(f"指标数量: {len(snapshot['metrics'])}")
        
        # 获取统计信息
        print("\n3. 获取统计...")
        stats = collector.get_metric_statistics("test.response_time")
        if stats:
            print(f"响应时间统计: 平均={stats['mean']:.3f}s, 最小={stats['min']:.3f}s, 最大={stats['max']:.3f}s")
        
        # 获取时间序列数据
        print("\n4. 获取时间序列...")
        series_data = collector.get_time_series_data("test.cpu.usage", hours=1.0)
        print(f"CPU使用率数据点: {len(series_data)}")
        
        # 获取摘要统计
        print("\n5. 获取摘要...")
        summary = collector.get_summary_statistics()
        print(f"总指标数: {summary['total_metrics']}")
        print(f"总数据点: {summary['total_data_points']}")
        print(f"按类型统计: {dict(summary['metrics_by_type'])}")
        
        # 导出指标
        print("\n6. 导出指标...")
        json_export = collector.export_metrics("json", hours=1.0)
        print(f"JSON导出大小: {len(json_export)} 字符")
        
        prometheus_export = collector.export_metrics("prometheus")
        print(f"Prometheus导出行数: {len(prometheus_export.split('\\n'))}")
        
        # 使用装饰器
        print("\n7. 使用装饰器...")
        
        @timing("test.decorated_function")
        async def test_function():
            await asyncio.sleep(0.2)
            return "success"
        
        result = await test_function()
        print(f"装饰器测试结果: {result}")
        
        # 显示最终统计
        print("\n=== 最终统计 ===")
        final_summary = collector.get_summary_statistics()
        print(f"总指标数: {final_summary['total_metrics']}")
        print(f"总数据点: {final_summary['total_data_points']}")
        
        # 显示热门指标
        print("\n热门指标:")
        for name, info in final_summary["top_metrics"].items():
            print(f"  {name}: {info['data_points']} 数据点 ({info['type']})")
    
    finally:
        # 停止清理任务
        collector.stop_cleanup_task()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(metrics_collector_example())