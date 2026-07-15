"""
性能监控器

实时监控插件框架的性能指标，包括CPU使用率、内存使用、
响应时间、错误率等关键指标。

Author: Mercari AI Agent Team
"""

import asyncio
import time
import logging
import psutil
import threading
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque, defaultdict
import json

from mercari_agent.plugins.interfaces import IPlugin, PluginState


@dataclass
class PerformanceMetric:
    """性能指标数据点"""
    timestamp: datetime
    metric_name: str
    value: float
    plugin_id: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class PerformanceAlert:
    """性能告警"""
    timestamp: datetime
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    message: str
    metric_name: str
    current_value: float
    threshold_value: float
    plugin_id: Optional[str] = None


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, collection_interval: float = 1.0, retention_hours: int = 24):
        self.collection_interval = collection_interval
        self.retention_hours = retention_hours
        self.logger = logging.getLogger("performance_monitor")
        
        # 指标存储
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=int(3600 * retention_hours / collection_interval)))
        self.alerts: deque = deque(maxlen=1000)
        
        # 阈值配置
        self.thresholds = {
            "cpu_usage": {"warning": 70.0, "critical": 90.0},
            "memory_usage": {"warning": 80.0, "critical": 95.0},
            "response_time": {"warning": 1.0, "critical": 5.0},
            "error_rate": {"warning": 0.05, "critical": 0.10},
            "plugin_count": {"warning": 50, "critical": 100}
        }
        
        # 监控状态
        self.monitoring = False
        self.monitor_task: Optional[asyncio.Task] = None
        self.plugins: List[IPlugin] = []
        
        # 性能统计
        self.performance_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "avg_response_time": 0.0,
            "last_updated": datetime.now()
        }
        
        # 告警回调
        self.alert_callbacks: List[Callable] = []
    
    def add_plugin(self, plugin: IPlugin):
        """添加要监控的插件"""
        if plugin not in self.plugins:
            self.plugins.append(plugin)
            self.logger.info(f"添加插件监控: {plugin.plugin_id}")
    
    def remove_plugin(self, plugin: IPlugin):
        """移除插件监控"""
        if plugin in self.plugins:
            self.plugins.remove(plugin)
            self.logger.info(f"移除插件监控: {plugin.plugin_id}")
    
    def add_alert_callback(self, callback: Callable[[PerformanceAlert], None]):
        """添加告警回调"""
        self.alert_callbacks.append(callback)
    
    def set_threshold(self, metric_name: str, warning: float, critical: float):
        """设置阈值"""
        self.thresholds[metric_name] = {
            "warning": warning,
            "critical": critical
        }
    
    async def start_monitoring(self):
        """开始监控"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        self.logger.info("性能监控已启动")
    
    async def stop_monitoring(self):
        """停止监控"""
        if not self.monitoring:
            return
        
        self.monitoring = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("性能监控已停止")
    
    async def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                # 收集系统指标
                await self._collect_system_metrics()
                
                # 收集插件指标
                await self._collect_plugin_metrics()
                
                # 收集框架指标
                await self._collect_framework_metrics()
                
                # 检查告警
                await self._check_alerts()
                
                # 清理过期数据
                self._cleanup_old_data()
                
                await asyncio.sleep(self.collection_interval)
                
            except Exception as e:
                self.logger.error(f"监控循环异常: {e}", exc_info=True)
                await asyncio.sleep(self.collection_interval)
    
    async def _collect_system_metrics(self):
        """收集系统指标"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=None)
            await self._record_metric("cpu_usage", cpu_percent)
            
            # 内存使用率
            memory = psutil.virtual_memory()
            await self._record_metric("memory_usage", memory.percent)
            await self._record_metric("memory_available", memory.available / 1024 / 1024)  # MB
            
            # 磁盘使用率
            disk = psutil.disk_usage('/')
            await self._record_metric("disk_usage", disk.percent)
            
            # 网络IO
            net_io = psutil.net_io_counters()
            await self._record_metric("network_bytes_sent", net_io.bytes_sent)
            await self._record_metric("network_bytes_recv", net_io.bytes_recv)
            
        except Exception as e:
            self.logger.error(f"系统指标收集失败: {e}")
    
    async def _collect_plugin_metrics(self):
        """收集插件指标"""
        for plugin in self.plugins:
            try:
                plugin_id = plugin.plugin_id
                
                # 插件状态
                state_value = 1 if plugin.state == PluginState.ACTIVE else 0
                await self._record_metric("plugin_active", state_value, plugin_id)
                
                # 健康检查
                health_start = time.time()
                try:
                    is_healthy = await asyncio.wait_for(plugin.health_check(), timeout=5.0)
                    health_duration = time.time() - health_start
                    
                    await self._record_metric("plugin_health_check_duration", health_duration, plugin_id)
                    await self._record_metric("plugin_healthy", 1 if is_healthy else 0, plugin_id)
                    
                except asyncio.TimeoutError:
                    await self._record_metric("plugin_health_check_timeout", 1, plugin_id)
                    await self._record_metric("plugin_healthy", 0, plugin_id)
                
                # 状态获取性能
                status_start = time.time()
                try:
                    status = await asyncio.wait_for(plugin.get_status(), timeout=5.0)
                    status_duration = time.time() - status_start
                    
                    await self._record_metric("plugin_status_duration", status_duration, plugin_id)
                    
                    # 从状态中提取额外指标
                    if isinstance(status, dict):
                        if "error_count" in status:
                            await self._record_metric("plugin_error_count", status["error_count"], plugin_id)
                        if "request_count" in status:
                            await self._record_metric("plugin_request_count", status["request_count"], plugin_id)
                        if "cache_hit_rate" in status:
                            await self._record_metric("plugin_cache_hit_rate", status["cache_hit_rate"], plugin_id)
                
                except asyncio.TimeoutError:
                    await self._record_metric("plugin_status_timeout", 1, plugin_id)
                
            except Exception as e:
                self.logger.error(f"插件 {plugin.plugin_id} 指标收集失败: {e}")
    
    async def _collect_framework_metrics(self):
        """收集框架指标"""
        try:
            from mercari_agent.plugins.framework import PluginFramework
            
            framework = await PluginFramework.get_instance()
            
            # 插件数量
            plugin_count = len(framework.plugins)
            await self._record_metric("framework_plugin_count", plugin_count)
            
            # 活跃插件数量
            active_plugins = len([p for p in framework.plugins.values() if p.state == PluginState.ACTIVE])
            await self._record_metric("framework_active_plugins", active_plugins)
            
            # 框架状态获取性能
            status_start = time.time()
            try:
                status = await asyncio.wait_for(framework.get_plugins_status(), timeout=10.0)
                status_duration = time.time() - status_start
                
                await self._record_metric("framework_status_duration", status_duration)
                
                # 健康检查性能
                health_start = time.time()
                health_results = await asyncio.wait_for(framework.health_check_all(), timeout=15.0)
                health_duration = time.time() - health_start
                
                await self._record_metric("framework_health_check_duration", health_duration)
                
                # 健康插件数量
                healthy_count = sum(1 for is_healthy in health_results.values() if is_healthy)
                await self._record_metric("framework_healthy_plugins", healthy_count)
                
            except asyncio.TimeoutError:
                await self._record_metric("framework_timeout", 1)
                
        except Exception as e:
            self.logger.error(f"框架指标收集失败: {e}")
    
    async def _record_metric(self, metric_name: str, value: float, plugin_id: Optional[str] = None):
        """记录指标"""
        metric = PerformanceMetric(
            timestamp=datetime.now(),
            metric_name=metric_name,
            value=value,
            plugin_id=plugin_id
        )
        
        key = f"{metric_name}_{plugin_id}" if plugin_id else metric_name
        self.metrics[key].append(metric)
        
        # 更新性能统计
        self._update_performance_stats(metric_name, value)
    
    def _update_performance_stats(self, metric_name: str, value: float):
        """更新性能统计"""
        if metric_name.endswith("_duration"):
            # 响应时间统计
            current_avg = self.performance_stats["avg_response_time"]
            current_count = self.performance_stats["total_requests"]
            
            new_avg = (current_avg * current_count + value) / (current_count + 1)
            self.performance_stats["avg_response_time"] = new_avg
            self.performance_stats["total_requests"] += 1
            
            if metric_name.endswith("_timeout"):
                self.performance_stats["failed_requests"] += 1
            else:
                self.performance_stats["successful_requests"] += 1
        
        self.performance_stats["last_updated"] = datetime.now()
    
    async def _check_alerts(self):
        """检查告警"""
        for metric_key, metric_queue in self.metrics.items():
            if not metric_queue:
                continue
            
            latest_metric = metric_queue[-1]
            metric_name = latest_metric.metric_name
            
            if metric_name not in self.thresholds:
                continue
            
            thresholds = self.thresholds[metric_name]
            value = latest_metric.value
            
            # 检查临界告警
            if value >= thresholds["critical"]:
                alert = PerformanceAlert(
                    timestamp=datetime.now(),
                    severity="CRITICAL",
                    message=f"{metric_name} 达到临界值",
                    metric_name=metric_name,
                    current_value=value,
                    threshold_value=thresholds["critical"],
                    plugin_id=latest_metric.plugin_id
                )
                await self._trigger_alert(alert)
            
            # 检查警告告警
            elif value >= thresholds["warning"]:
                alert = PerformanceAlert(
                    timestamp=datetime.now(),
                    severity="WARNING",
                    message=f"{metric_name} 超过警告阈值",
                    metric_name=metric_name,
                    current_value=value,
                    threshold_value=thresholds["warning"],
                    plugin_id=latest_metric.plugin_id
                )
                await self._trigger_alert(alert)
    
    async def _trigger_alert(self, alert: PerformanceAlert):
        """触发告警"""
        # 避免重复告警
        recent_alerts = [a for a in self.alerts if 
                        a.metric_name == alert.metric_name and 
                        a.plugin_id == alert.plugin_id and
                        (datetime.now() - a.timestamp).total_seconds() < 300]  # 5分钟内
        
        if recent_alerts:
            return
        
        self.alerts.append(alert)
        
        # 记录告警
        self.logger.warning(f"性能告警: {alert.message} - 当前值: {alert.current_value}, 阈值: {alert.threshold_value}")
        
        # 调用告警回调
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                self.logger.error(f"告警回调失败: {e}")
    
    def _cleanup_old_data(self):
        """清理过期数据"""
        cutoff_time = datetime.now() - timedelta(hours=self.retention_hours)
        
        for metric_key, metric_queue in self.metrics.items():
            while metric_queue and metric_queue[0].timestamp < cutoff_time:
                metric_queue.popleft()
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """获取当前指标"""
        current_metrics = {}
        
        for metric_key, metric_queue in self.metrics.items():
            if metric_queue:
                latest = metric_queue[-1]
                current_metrics[metric_key] = {
                    "value": latest.value,
                    "timestamp": latest.timestamp.isoformat(),
                    "plugin_id": latest.plugin_id
                }
        
        return current_metrics
    
    def get_metric_history(self, metric_name: str, plugin_id: Optional[str] = None, 
                          hours: int = 1) -> List[Dict[str, Any]]:
        """获取指标历史"""
        key = f"{metric_name}_{plugin_id}" if plugin_id else metric_name
        
        if key not in self.metrics:
            return []
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        history = []
        
        for metric in self.metrics[key]:
            if metric.timestamp >= cutoff_time:
                history.append({
                    "timestamp": metric.timestamp.isoformat(),
                    "value": metric.value,
                    "plugin_id": metric.plugin_id
                })
        
        return history
    
    def get_metric_statistics(self, metric_name: str, plugin_id: Optional[str] = None, 
                             hours: int = 1) -> Dict[str, float]:
        """获取指标统计"""
        history = self.get_metric_history(metric_name, plugin_id, hours)
        
        if not history:
            return {}
        
        values = [h["value"] for h in history]
        
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "current": values[-1] if values else 0
        }
    
    def get_alerts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """获取告警历史"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        alerts = []
        for alert in self.alerts:
            if alert.timestamp >= cutoff_time:
                alerts.append({
                    "timestamp": alert.timestamp.isoformat(),
                    "severity": alert.severity,
                    "message": alert.message,
                    "metric_name": alert.metric_name,
                    "current_value": alert.current_value,
                    "threshold_value": alert.threshold_value,
                    "plugin_id": alert.plugin_id
                })
        
        return alerts
    
    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "monitoring_status": "active" if self.monitoring else "inactive",
            "plugin_count": len(self.plugins),
            "metrics_count": sum(len(queue) for queue in self.metrics.values()),
            "alerts_count": len(self.alerts),
            "performance_stats": self.performance_stats.copy(),
            "current_metrics": self.get_current_metrics(),
            "recent_alerts": self.get_alerts(hours=1)
        }
        
        # 添加关键指标摘要
        report["summary"] = {
            "cpu_usage": self.get_metric_statistics("cpu_usage"),
            "memory_usage": self.get_metric_statistics("memory_usage"),
            "framework_plugin_count": self.get_metric_statistics("framework_plugin_count"),
            "framework_active_plugins": self.get_metric_statistics("framework_active_plugins")
        }
        
        return report
    
    def export_metrics(self, format: str = "json") -> str:
        """导出指标数据"""
        if format.lower() == "json":
            return json.dumps(self.get_performance_report(), indent=2, default=str)
        elif format.lower() == "csv":
            # 简单的CSV导出
            lines = ["timestamp,metric_name,value,plugin_id"]
            
            for metric_key, metric_queue in self.metrics.items():
                for metric in metric_queue:
                    lines.append(f"{metric.timestamp.isoformat()},{metric.metric_name},{metric.value},{metric.plugin_id or ''}")
            
            return "\n".join(lines)
        else:
            raise ValueError(f"不支持的格式: {format}")


# 简单的告警处理器示例
class SimpleAlertHandler:
    """简单的告警处理器"""
    
    def __init__(self):
        self.logger = logging.getLogger("alert_handler")
    
    def handle_alert(self, alert: PerformanceAlert):
        """处理告警"""
        if alert.severity == "CRITICAL":
            self.logger.critical(f"严重告警: {alert.message}")
            # 可以发送邮件、短信等
        elif alert.severity == "WARNING":
            self.logger.warning(f"警告告警: {alert.message}")
            # 可以发送通知
        
        # 记录告警到文件
        self._log_alert_to_file(alert)
    
    def _log_alert_to_file(self, alert: PerformanceAlert):
        """记录告警到文件"""
        try:
            import os
            os.makedirs("logs", exist_ok=True)
            
            with open("logs/performance_alerts.log", "a") as f:
                f.write(f"{alert.timestamp.isoformat()} - {alert.severity} - {alert.message}\n")
        except Exception as e:
            self.logger.error(f"记录告警失败: {e}")


# 使用示例
async def monitor_example():
    """监控示例"""
    from mercari_agent.plugins.examples.basic_plugin import BasicExamplePlugin
    
    # 创建监控器
    monitor = PerformanceMonitor(collection_interval=2.0, retention_hours=1)
    
    # 添加告警处理器
    alert_handler = SimpleAlertHandler()
    monitor.add_alert_callback(alert_handler.handle_alert)
    
    # 设置阈值
    monitor.set_threshold("cpu_usage", warning=50.0, critical=80.0)
    monitor.set_threshold("memory_usage", warning=70.0, critical=90.0)
    
    # 创建并添加插件
    plugin = BasicExamplePlugin()
    await plugin.initialize({"enabled": True})
    await plugin.start()
    
    monitor.add_plugin(plugin)
    
    # 开始监控
    await monitor.start_monitoring()
    
    try:
        # 运行一段时间
        print("监控运行中...")
        await asyncio.sleep(30)
        
        # 获取报告
        report = monitor.get_performance_report()
        print("\n=== 性能报告 ===")
        print(json.dumps(report, indent=2, default=str))
        
        # 获取指标统计
        cpu_stats = monitor.get_metric_statistics("cpu_usage")
        print(f"\nCPU统计: {cpu_stats}")
        
        memory_stats = monitor.get_metric_statistics("memory_usage")
        print(f"内存统计: {memory_stats}")
        
    finally:
        # 停止监控
        await monitor.stop_monitoring()
        await plugin.stop()
        await plugin.cleanup()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(monitor_example())