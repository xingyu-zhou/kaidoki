"""
验证码统计分析模块

该模块提供验证码相关的统计数据收集和分析功能，包括：
- 验证码成功率统计
- 用户行为分析
- 性能指标监控
- 趋势分析
- 报告生成
"""

import asyncio
import logging
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
import statistics
from collections import defaultdict, deque

from .captcha_types import CaptchaType, CaptchaStatus
from ..utils.logger import get_logger

logger = get_logger(__name__)


class EventType(Enum):
    """事件类型枚举"""
    DETECTED = "detected"
    SOLVED = "solved"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    REFRESH = "refresh"
    RETRY = "retry"
    USER_INPUT = "user_input"


@dataclass
class CaptchaEvent:
    """验证码事件"""
    event_id: str
    event_type: EventType
    captcha_type: CaptchaType
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 性能数据
    processing_time: Optional[float] = None
    response_time: Optional[float] = None
    
    # 用户数据
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "captcha_type": self.captcha_type.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "processing_time": self.processing_time,
            "response_time": self.response_time,
            "user_id": self.user_id,
            "session_id": self.session_id
        }


@dataclass
class CaptchaStats:
    """验证码统计数据"""
    total_captcha_count: int = 0
    solved_captcha_count: int = 0
    failed_captcha_count: int = 0
    timeout_captcha_count: int = 0
    cancelled_captcha_count: int = 0
    
    # 按类型统计
    type_stats: Dict[CaptchaType, Dict[str, int]] = field(default_factory=dict)
    
    # 时间统计
    total_solve_time: float = 0.0
    solve_times: List[float] = field(default_factory=list)
    
    # 用户行为统计
    refresh_count: int = 0
    retry_count: int = 0
    user_input_count: int = 0
    
    # 会话统计
    session_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_captcha_count == 0:
            return 0.0
        return (self.solved_captcha_count / self.total_captcha_count) * 100
    
    @property
    def average_solve_time(self) -> float:
        """平均解决时间"""
        if not self.solve_times:
            return 0.0
        return statistics.mean(self.solve_times)
    
    @property
    def median_solve_time(self) -> float:
        """中位数解决时间"""
        if not self.solve_times:
            return 0.0
        return statistics.median(self.solve_times)
    
    def update_type_stats(self, captcha_type: CaptchaType, event_type: str):
        """更新类型统计"""
        if captcha_type not in self.type_stats:
            self.type_stats[captcha_type] = {
                "detected": 0,
                "solved": 0,
                "failed": 0,
                "timeout": 0,
                "cancelled": 0
            }
        
        if event_type in self.type_stats[captcha_type]:
            self.type_stats[captcha_type][event_type] += 1


class CaptchaAnalytics:
    """验证码分析器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化验证码分析器
        
        Args:
            config: 配置参数
        """
        self.config = config or {}
        self.stats = CaptchaStats()
        self.events: deque = deque(maxlen=10000)  # 保持最近10000个事件
        self.event_buffer: List[CaptchaEvent] = []
        self.lock = asyncio.Lock()
        
        # 时间窗口统计
        self.time_windows = {
            "1h": deque(maxlen=3600),    # 1小时
            "6h": deque(maxlen=21600),   # 6小时
            "24h": deque(maxlen=86400),  # 24小时
        }
        
        # 实时统计
        self.real_time_stats = {
            "current_hour": {"solved": 0, "failed": 0, "total": 0},
            "current_day": {"solved": 0, "failed": 0, "total": 0},
            "last_hour": {"solved": 0, "failed": 0, "total": 0}
        }
        
        # 趋势数据
        self.trend_data = {
            "hourly": defaultdict(lambda: {"solved": 0, "failed": 0, "total": 0}),
            "daily": defaultdict(lambda: {"solved": 0, "failed": 0, "total": 0})
        }
        
        # 性能指标
        self.performance_metrics = {
            "response_times": deque(maxlen=1000),
            "processing_times": deque(maxlen=1000),
            "detection_times": deque(maxlen=1000)
        }
        
        # 用户行为模式
        self.user_patterns = defaultdict(lambda: {
            "total_attempts": 0,
            "successful_attempts": 0,
            "average_solve_time": 0.0,
            "preferred_types": defaultdict(int),
            "error_patterns": defaultdict(int)
        })
        
        # 启动后台任务
        self.background_tasks = []
        self._start_background_tasks()
        
        logger.info("CaptchaAnalytics initialized")
    
    def _start_background_tasks(self):
        """启动后台任务"""
        # 定期统计更新任务
        self.background_tasks.append(
            asyncio.create_task(self._periodic_stats_update())
        )
        
        # 数据持久化任务
        if self.config.get("enable_persistence", True):
            self.background_tasks.append(
                asyncio.create_task(self._periodic_data_persistence())
            )
    
    async def record_captcha_event(self, 
                                 event_type: str, 
                                 captcha_type: CaptchaType,
                                 metadata: Dict[str, Any] = None,
                                 user_id: Optional[str] = None,
                                 session_id: Optional[str] = None) -> str:
        """
        记录验证码事件
        
        Args:
            event_type: 事件类型
            captcha_type: 验证码类型
            metadata: 元数据
            user_id: 用户ID
            session_id: 会话ID
            
        Returns:
            str: 事件ID
        """
        try:
            event_type_enum = EventType(event_type)
        except ValueError:
            logger.warning(f"Unknown event type: {event_type}")
            return ""
        
        # 创建事件
        event = CaptchaEvent(
            event_id=f"{int(time.time() * 1000000)}_{event_type}_{captcha_type.value}",
            event_type=event_type_enum,
            captcha_type=captcha_type,
            timestamp=datetime.now(),
            metadata=metadata or {},
            user_id=user_id,
            session_id=session_id
        )
        
        # 提取性能数据
        if metadata:
            event.processing_time = metadata.get("processing_time")
            event.response_time = metadata.get("response_time")
        
        async with self.lock:
            # 添加到事件队列
            self.events.append(event)
            self.event_buffer.append(event)
            
            # 更新统计
            await self._update_stats(event)
            
            # 更新时间窗口统计
            self._update_time_window_stats(event)
            
            # 更新用户行为模式
            if user_id:
                self._update_user_patterns(event, user_id)
            
            # 更新性能指标
            self._update_performance_metrics(event)
        
        logger.debug(f"Recorded captcha event: {event.event_id}")
        return event.event_id
    
    async def _update_stats(self, event: CaptchaEvent):
        """更新统计数据"""
        if event.event_type == EventType.DETECTED:
            self.stats.total_captcha_count += 1
            self.stats.update_type_stats(event.captcha_type, "detected")
            
        elif event.event_type == EventType.SOLVED:
            self.stats.solved_captcha_count += 1
            self.stats.update_type_stats(event.captcha_type, "solved")
            
            # 记录解决时间
            if event.processing_time:
                self.stats.total_solve_time += event.processing_time
                self.stats.solve_times.append(event.processing_time)
                
        elif event.event_type == EventType.FAILED:
            self.stats.failed_captcha_count += 1
            self.stats.update_type_stats(event.captcha_type, "failed")
            
        elif event.event_type == EventType.TIMEOUT:
            self.stats.timeout_captcha_count += 1
            self.stats.update_type_stats(event.captcha_type, "timeout")
            
        elif event.event_type == EventType.CANCELLED:
            self.stats.cancelled_captcha_count += 1
            self.stats.update_type_stats(event.captcha_type, "cancelled")
            
        elif event.event_type == EventType.REFRESH:
            self.stats.refresh_count += 1
            
        elif event.event_type == EventType.RETRY:
            self.stats.retry_count += 1
            
        elif event.event_type == EventType.USER_INPUT:
            self.stats.user_input_count += 1
        
        # 更新会话统计
        if event.session_id:
            if event.session_id not in self.stats.session_stats:
                self.stats.session_stats[event.session_id] = {
                    "total": 0, "solved": 0, "failed": 0
                }
            
            session_stats = self.stats.session_stats[event.session_id]
            session_stats["total"] += 1
            
            if event.event_type == EventType.SOLVED:
                session_stats["solved"] += 1
            elif event.event_type == EventType.FAILED:
                session_stats["failed"] += 1
    
    def _update_time_window_stats(self, event: CaptchaEvent):
        """更新时间窗口统计"""
        timestamp = event.timestamp
        
        # 更新实时统计
        current_hour = timestamp.replace(minute=0, second=0, microsecond=0)
        current_day = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        
        if event.event_type == EventType.DETECTED:
            self.real_time_stats["current_hour"]["total"] += 1
            self.real_time_stats["current_day"]["total"] += 1
        elif event.event_type == EventType.SOLVED:
            self.real_time_stats["current_hour"]["solved"] += 1
            self.real_time_stats["current_day"]["solved"] += 1
        elif event.event_type == EventType.FAILED:
            self.real_time_stats["current_hour"]["failed"] += 1
            self.real_time_stats["current_day"]["failed"] += 1
        
        # 更新趋势数据
        hour_key = current_hour.strftime("%Y%m%d%H")
        day_key = current_day.strftime("%Y%m%d")
        
        if event.event_type == EventType.DETECTED:
            self.trend_data["hourly"][hour_key]["total"] += 1
            self.trend_data["daily"][day_key]["total"] += 1
        elif event.event_type == EventType.SOLVED:
            self.trend_data["hourly"][hour_key]["solved"] += 1
            self.trend_data["daily"][day_key]["solved"] += 1
        elif event.event_type == EventType.FAILED:
            self.trend_data["hourly"][hour_key]["failed"] += 1
            self.trend_data["daily"][day_key]["failed"] += 1
    
    def _update_user_patterns(self, event: CaptchaEvent, user_id: str):
        """更新用户行为模式"""
        user_pattern = self.user_patterns[user_id]
        
        if event.event_type == EventType.DETECTED:
            user_pattern["total_attempts"] += 1
            user_pattern["preferred_types"][event.captcha_type] += 1
        elif event.event_type == EventType.SOLVED:
            user_pattern["successful_attempts"] += 1
            
            # 更新平均解决时间
            if event.processing_time:
                current_avg = user_pattern["average_solve_time"]
                total_successful = user_pattern["successful_attempts"]
                
                if total_successful == 1:
                    user_pattern["average_solve_time"] = event.processing_time
                else:
                    user_pattern["average_solve_time"] = (
                        (current_avg * (total_successful - 1) + event.processing_time) / 
                        total_successful
                    )
        elif event.event_type == EventType.FAILED:
            error_type = event.metadata.get("error_type", "unknown")
            user_pattern["error_patterns"][error_type] += 1
    
    def _update_performance_metrics(self, event: CaptchaEvent):
        """更新性能指标"""
        if event.response_time:
            self.performance_metrics["response_times"].append(event.response_time)
        
        if event.processing_time:
            self.performance_metrics["processing_times"].append(event.processing_time)
        
        detection_time = event.metadata.get("detection_time")
        if detection_time:
            self.performance_metrics["detection_times"].append(detection_time)
    
    async def get_analytics_report(self, 
                                 time_range: str = "24h",
                                 include_details: bool = False) -> Dict[str, Any]:
        """
        获取分析报告
        
        Args:
            time_range: 时间范围 ("1h", "6h", "24h", "all")
            include_details: 是否包含详细信息
            
        Returns:
            Dict[str, Any]: 分析报告
        """
        async with self.lock:
            # 基础统计
            basic_stats = {
                "total_captcha": self.stats.total_captcha_count,
                "solved_captcha": self.stats.solved_captcha_count,
                "failed_captcha": self.stats.failed_captcha_count,
                "timeout_captcha": self.stats.timeout_captcha_count,
                "cancelled_captcha": self.stats.cancelled_captcha_count,
                "success_rate": f"{self.stats.success_rate:.2f}%",
                "average_solve_time": f"{self.stats.average_solve_time:.2f}s",
                "median_solve_time": f"{self.stats.median_solve_time:.2f}s"
            }
            
            # 按类型统计
            type_breakdown = {}
            for captcha_type, stats in self.stats.type_stats.items():
                total = stats.get("detected", 0)
                solved = stats.get("solved", 0)
                success_rate = (solved / total * 100) if total > 0 else 0
                
                type_breakdown[captcha_type.value] = {
                    "total": total,
                    "solved": solved,
                    "failed": stats.get("failed", 0),
                    "timeout": stats.get("timeout", 0),
                    "success_rate": f"{success_rate:.2f}%"
                }
            
            # 用户行为统计
            user_behavior = {
                "refresh_count": self.stats.refresh_count,
                "retry_count": self.stats.retry_count,
                "user_input_count": self.stats.user_input_count,
                "average_refreshes_per_captcha": (
                    self.stats.refresh_count / max(self.stats.total_captcha_count, 1)
                ),
                "average_retries_per_captcha": (
                    self.stats.retry_count / max(self.stats.total_captcha_count, 1)
                )
            }
            
            # 性能指标
            performance = {}
            if self.performance_metrics["response_times"]:
                response_times = list(self.performance_metrics["response_times"])
                performance["response_time"] = {
                    "average": f"{statistics.mean(response_times):.3f}s",
                    "median": f"{statistics.median(response_times):.3f}s",
                    "min": f"{min(response_times):.3f}s",
                    "max": f"{max(response_times):.3f}s"
                }
            
            if self.performance_metrics["processing_times"]:
                processing_times = list(self.performance_metrics["processing_times"])
                performance["processing_time"] = {
                    "average": f"{statistics.mean(processing_times):.3f}s",
                    "median": f"{statistics.median(processing_times):.3f}s",
                    "min": f"{min(processing_times):.3f}s",
                    "max": f"{max(processing_times):.3f}s"
                }
            
            # 实时统计
            real_time = {
                "current_hour": self.real_time_stats["current_hour"],
                "current_day": self.real_time_stats["current_day"]
            }
            
            report = {
                "basic_stats": basic_stats,
                "type_breakdown": type_breakdown,
                "user_behavior": user_behavior,
                "performance": performance,
                "real_time": real_time,
                "report_generated_at": datetime.now().isoformat()
            }
            
            # 包含详细信息
            if include_details:
                report["detailed_stats"] = await self._get_detailed_stats(time_range)
            
            return report
    
    async def _get_detailed_stats(self, time_range: str) -> Dict[str, Any]:
        """获取详细统计信息"""
        # 趋势分析
        trend_analysis = self._analyze_trends(time_range)
        
        # 用户模式分析
        user_analysis = self._analyze_user_patterns()
        
        # 错误模式分析
        error_analysis = self._analyze_error_patterns()
        
        return {
            "trend_analysis": trend_analysis,
            "user_analysis": user_analysis,
            "error_analysis": error_analysis
        }
    
    def _analyze_trends(self, time_range: str) -> Dict[str, Any]:
        """分析趋势"""
        if time_range == "1h":
            data = dict(list(self.trend_data["hourly"].items())[-1:])
        elif time_range == "6h":
            data = dict(list(self.trend_data["hourly"].items())[-6:])
        elif time_range == "24h":
            data = dict(list(self.trend_data["hourly"].items())[-24:])
        else:
            data = dict(self.trend_data["daily"])
        
        if not data:
            return {"trend": "no_data"}
        
        # 计算趋势
        success_rates = []
        for stats in data.values():
            total = stats["total"]
            if total > 0:
                success_rates.append(stats["solved"] / total * 100)
        
        if len(success_rates) >= 2:
            if success_rates[-1] > success_rates[-2]:
                trend = "improving"
            elif success_rates[-1] < success_rates[-2]:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"
        
        return {
            "trend": trend,
            "data_points": len(data),
            "average_success_rate": statistics.mean(success_rates) if success_rates else 0
        }
    
    def _analyze_user_patterns(self) -> Dict[str, Any]:
        """分析用户模式"""
        if not self.user_patterns:
            return {"analysis": "no_user_data"}
        
        # 计算平均成功率
        success_rates = []
        solve_times = []
        
        for user_id, pattern in self.user_patterns.items():
            if pattern["total_attempts"] > 0:
                success_rate = pattern["successful_attempts"] / pattern["total_attempts"] * 100
                success_rates.append(success_rate)
                
                if pattern["average_solve_time"] > 0:
                    solve_times.append(pattern["average_solve_time"])
        
        analysis = {
            "total_users": len(self.user_patterns),
            "average_success_rate": statistics.mean(success_rates) if success_rates else 0,
            "average_solve_time": statistics.mean(solve_times) if solve_times else 0
        }
        
        # 找出最常见的验证码类型
        type_preferences = defaultdict(int)
        for pattern in self.user_patterns.values():
            for captcha_type, count in pattern["preferred_types"].items():
                type_preferences[captcha_type] += count
        
        if type_preferences:
            most_common_type = max(type_preferences, key=type_preferences.get)
            analysis["most_common_type"] = most_common_type.value
        
        return analysis
    
    def _analyze_error_patterns(self) -> Dict[str, Any]:
        """分析错误模式"""
        error_counts = defaultdict(int)
        
        for pattern in self.user_patterns.values():
            for error_type, count in pattern["error_patterns"].items():
                error_counts[error_type] += count
        
        if not error_counts:
            return {"analysis": "no_error_data"}
        
        # 找出最常见的错误
        most_common_error = max(error_counts, key=error_counts.get)
        total_errors = sum(error_counts.values())
        
        return {
            "total_errors": total_errors,
            "most_common_error": most_common_error,
            "error_distribution": dict(error_counts)
        }
    
    async def get_real_time_metrics(self) -> Dict[str, Any]:
        """获取实时指标"""
        async with self.lock:
            return {
                "current_hour": self.real_time_stats["current_hour"],
                "current_day": self.real_time_stats["current_day"],
                "recent_events": len(self.events),
                "buffer_size": len(self.event_buffer),
                "timestamp": datetime.now().isoformat()
            }
    
    async def export_data(self, 
                         file_path: str,
                         format: str = "json",
                         time_range: str = "24h") -> bool:
        """
        导出数据
        
        Args:
            file_path: 文件路径
            format: 导出格式 ("json", "csv")
            time_range: 时间范围
            
        Returns:
            bool: 是否成功导出
        """
        try:
            # 获取分析报告
            report = await self.get_analytics_report(time_range, include_details=True)
            
            # 导出数据
            export_path = Path(file_path)
            export_path.parent.mkdir(parents=True, exist_ok=True)
            
            if format.lower() == "json":
                with open(export_path, 'w', encoding='utf-8') as f:
                    json.dump(report, f, ensure_ascii=False, indent=2)
            elif format.lower() == "csv":
                # 简化的CSV导出
                import csv
                with open(export_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Metric", "Value"])
                    
                    for key, value in report["basic_stats"].items():
                        writer.writerow([key, value])
            
            logger.info(f"Analytics data exported to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export analytics data: {e}")
            return False
    
    async def _periodic_stats_update(self):
        """定期统计更新"""
        while True:
            try:
                await asyncio.sleep(300)  # 5分钟更新一次
                
                # 清理过期的趋势数据
                await self._cleanup_trend_data()
                
                # 更新实时统计
                await self._update_real_time_stats()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Periodic stats update error: {e}")
                await asyncio.sleep(60)
    
    async def _periodic_data_persistence(self):
        """定期数据持久化"""
        while True:
            try:
                await asyncio.sleep(1800)  # 30分钟持久化一次
                
                # 保存事件数据
                await self._persist_events()
                
                # 保存统计数据
                await self._persist_stats()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Periodic data persistence error: {e}")
                await asyncio.sleep(300)
    
    async def _cleanup_trend_data(self):
        """清理趋势数据"""
        async with self.lock:
            # 清理过期的小时数据（保留7天）
            cutoff_time = datetime.now() - timedelta(days=7)
            cutoff_hour = cutoff_time.strftime("%Y%m%d%H")
            
            expired_hours = [
                hour for hour in self.trend_data["hourly"].keys()
                if hour < cutoff_hour
            ]
            
            for hour in expired_hours:
                del self.trend_data["hourly"][hour]
            
            # 清理过期的天数据（保留30天）
            cutoff_day = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
            
            expired_days = [
                day for day in self.trend_data["daily"].keys()
                if day < cutoff_day
            ]
            
            for day in expired_days:
                del self.trend_data["daily"][day]
    
    async def _update_real_time_stats(self):
        """更新实时统计"""
        current_time = datetime.now()
        current_hour = current_time.replace(minute=0, second=0, microsecond=0)
        
        # 检查是否需要重置小时统计
        if hasattr(self, '_last_hour_reset'):
            if current_hour > self._last_hour_reset:
                self.real_time_stats["last_hour"] = self.real_time_stats["current_hour"].copy()
                self.real_time_stats["current_hour"] = {"solved": 0, "failed": 0, "total": 0}
                self._last_hour_reset = current_hour
        else:
            self._last_hour_reset = current_hour
    
    async def _persist_events(self):
        """持久化事件数据"""
        if not self.event_buffer:
            return
        
        try:
            # 保存事件缓冲区
            persistence_file = self.config.get("events_file", "data/captcha_events.json")
            persistence_path = Path(persistence_file)
            persistence_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 准备事件数据
            events_data = [event.to_dict() for event in self.event_buffer]
            
            # 读取现有数据
            existing_data = []
            if persistence_path.exists():
                with open(persistence_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            
            # 合并数据
            all_events = existing_data + events_data
            
            # 限制数据量（保留最近的50000个事件）
            if len(all_events) > 50000:
                all_events = all_events[-50000:]
            
            # 保存数据
            with open(persistence_path, 'w', encoding='utf-8') as f:
                json.dump(all_events, f, ensure_ascii=False, indent=2)
            
            # 清空缓冲区
            self.event_buffer.clear()
            
            logger.debug(f"Persisted {len(events_data)} events")
            
        except Exception as e:
            logger.error(f"Failed to persist events: {e}")
    
    async def _persist_stats(self):
        """持久化统计数据"""
        try:
            # 保存统计数据
            stats_file = self.config.get("stats_file", "data/captcha_stats.json")
            stats_path = Path(stats_file)
            stats_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 准备统计数据
            stats_data = {
                "stats": {
                    "total_captcha_count": self.stats.total_captcha_count,
                    "solved_captcha_count": self.stats.solved_captcha_count,
                    "failed_captcha_count": self.stats.failed_captcha_count,
                    "timeout_captcha_count": self.stats.timeout_captcha_count,
                    "cancelled_captcha_count": self.stats.cancelled_captcha_count,
                    "success_rate": self.stats.success_rate,
                    "average_solve_time": self.stats.average_solve_time,
                    "refresh_count": self.stats.refresh_count,
                    "retry_count": self.stats.retry_count,
                    "user_input_count": self.stats.user_input_count
                },
                "type_stats": {
                    captcha_type.value: stats 
                    for captcha_type, stats in self.stats.type_stats.items()
                },
                "trend_data": {
                    "hourly": dict(self.trend_data["hourly"]),
                    "daily": dict(self.trend_data["daily"])
                },
                "real_time_stats": self.real_time_stats,
                "timestamp": datetime.now().isoformat()
            }
            
            # 保存数据
            with open(stats_path, 'w', encoding='utf-8') as f:
                json.dump(stats_data, f, ensure_ascii=False, indent=2)
            
            logger.debug("Statistics data persisted")
            
        except Exception as e:
            logger.error(f"Failed to persist stats: {e}")
    
    async def close(self):
        """关闭分析器"""
        # 取消后台任务
        for task in self.background_tasks:
            task.cancel()
        
        # 等待任务完成
        await asyncio.gather(*self.background_tasks, return_exceptions=True)
        
        # 持久化数据
        if self.config.get("enable_persistence", True):
            await self._persist_events()
            await self._persist_stats()
        
        logger.info("CaptchaAnalytics closed")