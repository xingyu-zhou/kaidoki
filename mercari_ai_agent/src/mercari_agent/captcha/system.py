"""
验证码人机交互系统集成模块

该模块提供系统的主要集成类，负责：
- 所有组件的初始化和配置
- 系统启动和关闭
- 组件间的协调
- 与现有爬虫系统的集成
- 系统监控和健康检查
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from pathlib import Path

from .captcha_types import CaptchaType, CAPTCHA_DETECTION_CONFIG, CAPTCHA_SOLVING_CONFIG
from .captcha_detector import CaptchaDetector
from .captcha_solver import CaptchaSolver
from .ui_manager import CaptchaUIManager
from .task_queue import TaskQueue, ScrapingTask, TaskStatus
from .workflow import CaptchaWorkflow, WorkflowManager, RecoveryManager
from .analytics import CaptchaAnalytics
from ..utils.logger import get_logger
from ..scrapers.anti_bot_handler import AntiBotHandler, BotDetectionType
from ..scrapers.session_manager import SessionManager

logger = get_logger(__name__)


class CaptchaInteractionSystem:
    """验证码人机交互系统主控制器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化验证码交互系统
        
        Args:
            config: 系统配置
        """
        self.config = config
        self.is_running = False
        self.start_time: Optional[datetime] = None
        
        # 核心组件
        self.captcha_detector: Optional[CaptchaDetector] = None
        self.ui_manager: Optional[CaptchaUIManager] = None
        self.captcha_solver: Optional[CaptchaSolver] = None
        self.task_queue: Optional[TaskQueue] = None
        self.workflow: Optional[CaptchaWorkflow] = None
        self.analytics: Optional[CaptchaAnalytics] = None
        
        # 管理组件
        self.workflow_manager: Optional[WorkflowManager] = None
        self.recovery_manager: Optional[RecoveryManager] = None
        
        # 集成组件
        self.session_manager: Optional[SessionManager] = None
        self.anti_bot_handler: Optional[AntiBotHandler] = None
        
        # 监控任务
        self.monitoring_tasks: List[asyncio.Task] = []
        
        # 系统统计
        self.system_stats = {
            'total_requests': 0,
            'captcha_requests': 0,
            'successful_captcha_solves': 0,
            'failed_captcha_solves': 0,
            'system_uptime': 0.0
        }
        
        logger.info("CaptchaInteractionSystem initialized")
    
    async def initialize(self):
        """初始化系统组件"""
        try:
            logger.info("Initializing CaptchaInteractionSystem...")
            
            # 1. 初始化分析器
            analytics_config = self.config.get("analytics", {})
            self.analytics = CaptchaAnalytics(analytics_config)
            
            # 2. 初始化检测器
            detector_config = self.config.get("detector", CAPTCHA_DETECTION_CONFIG)
            self.captcha_detector = CaptchaDetector(detector_config)
            
            # 3. 初始化UI管理器
            ui_config = self.config.get("ui", CAPTCHA_SOLVING_CONFIG)
            self.ui_manager = CaptchaUIManager(ui_config)
            
            # 4. 初始化解决器
            self.captcha_solver = CaptchaSolver(self.ui_manager, ui_config)
            
            # 5. 初始化任务队列
            queue_config = self.config.get("task_queue", {})
            max_size = queue_config.get("max_size", 1000)
            persistence_file = queue_config.get("persistence_file", "data/captcha_tasks.json")
            self.task_queue = TaskQueue(max_size, persistence_file)
            
            # 6. 初始化工作流
            self.workflow = CaptchaWorkflow(
                self.task_queue,
                self.captcha_detector,
                self.captcha_solver,
                self.analytics
            )
            
            # 7. 初始化管理器
            self.workflow_manager = WorkflowManager(self.workflow)
            self.recovery_manager = RecoveryManager(self.task_queue, self.workflow)
            
            # 8. 集成现有系统
            await self._integrate_with_existing_system()
            
            logger.info("CaptchaInteractionSystem initialized successfully")
            
        except Exception as e:
            logger.error(f"System initialization failed: {e}")
            raise
    
    async def start(self):
        """启动系统"""
        if self.is_running:
            logger.warning("System is already running")
            return
        
        try:
            # 启动工作流管理器
            await self.workflow_manager.start()
            
            # 启动监控任务
            self._start_monitoring_tasks()
            
            # 记录启动时间
            self.start_time = datetime.now()
            self.is_running = True
            
            logger.info("CaptchaInteractionSystem started successfully")
            
        except Exception as e:
            logger.error(f"System start failed: {e}")
            raise
    
    async def stop(self):
        """停止系统"""
        if not self.is_running:
            logger.warning("System is not running")
            return
        
        try:
            # 停止监控任务
            await self._stop_monitoring_tasks()
            
            # 停止工作流管理器
            if self.workflow_manager:
                await self.workflow_manager.stop()
            
            # 关闭分析器
            if self.analytics:
                await self.analytics.close()
            
            # 关闭UI管理器
            if self.ui_manager:
                await self.ui_manager.close()
            
            # 关闭任务队列
            if self.task_queue:
                await self.task_queue.close()
            
            self.is_running = False
            
            logger.info("CaptchaInteractionSystem stopped successfully")
            
        except Exception as e:
            logger.error(f"System stop failed: {e}")
            raise
    
    async def _integrate_with_existing_system(self):
        """与现有系统集成"""
        try:
            # 集成会话管理器
            session_config = self.config.get("session_manager", {})
            max_sessions = session_config.get("max_sessions", 5)
            max_requests_per_minute = session_config.get("max_requests_per_minute", 30)
            
            self.session_manager = SessionManager(max_sessions, max_requests_per_minute)
            await self.session_manager.initialize()
            
            # 集成反爬虫处理器
            self.anti_bot_handler = AntiBotHandler()
            
            # 替换现有的反爬虫处理逻辑
            await self._enhance_anti_bot_handler()
            
            logger.info("Integration with existing system completed")
            
        except Exception as e:
            logger.error(f"System integration failed: {e}")
            raise
    
    async def _enhance_anti_bot_handler(self):
        """增强反爬虫处理器"""
        # 保存原始的处理方法
        original_handle_block = self.anti_bot_handler.handle_block
        
        async def enhanced_handle_block(session, url, detection_result):
            """增强的反爬虫处理"""
            try:
                # 如果检测到验证码，使用新的处理流程
                if detection_result.detection_type == BotDetectionType.CAPTCHA:
                    logger.info(f"CAPTCHA detected by anti-bot handler for URL: {url}")
                    
                    # 创建任务
                    task = ScrapingTask(
                        task_id=f"captcha_{int(time.time() * 1000)}",
                        url=url,
                        task_type="captcha_handling",
                        status=TaskStatus.PENDING
                    )
                    
                    # 添加任务到队列
                    await self.task_queue.add_task(task)
                    
                    # 处理验证码工作流
                    success = await self.workflow.process_captcha_workflow(
                        task, detection_result.details.get("content", ""), None, session
                    )
                    
                    if success:
                        logger.info(f"CAPTCHA successfully handled for task: {task.task_id}")
                        return task.result
                    else:
                        raise Exception(f"CAPTCHA handling failed for task: {task.task_id}")
                else:
                    # 使用原始处理器
                    return await original_handle_block(session, url, detection_result)
                    
            except Exception as e:
                logger.error(f"Enhanced anti-bot handling failed: {e}")
                # 回退到原始处理器
                return await original_handle_block(session, url, detection_result)
        
        # 替换处理方法
        self.anti_bot_handler.handle_block = enhanced_handle_block
        
        logger.info("Anti-bot handler enhanced with CAPTCHA integration")
    
    def _start_monitoring_tasks(self):
        """启动监控任务"""
        # 系统健康检查任务
        self.monitoring_tasks.append(
            asyncio.create_task(self._system_health_monitor())
        )
        
        # 统计更新任务
        self.monitoring_tasks.append(
            asyncio.create_task(self._stats_update_monitor())
        )
        
        # 任务清理任务
        self.monitoring_tasks.append(
            asyncio.create_task(self._task_cleanup_monitor())
        )
        
        logger.info("Monitoring tasks started")
    
    async def _stop_monitoring_tasks(self):
        """停止监控任务"""
        for task in self.monitoring_tasks:
            task.cancel()
        
        # 等待任务完成
        await asyncio.gather(*self.monitoring_tasks, return_exceptions=True)
        
        self.monitoring_tasks.clear()
        logger.info("Monitoring tasks stopped")
    
    async def _system_health_monitor(self):
        """系统健康监控"""
        while self.is_running:
            try:
                # 检查系统健康状态
                health_status = await self.check_system_health()
                
                if not health_status.get("healthy", False):
                    logger.warning(f"System health check failed: {health_status}")
                    
                    # 可以在这里实现自动修复逻辑
                    await self._handle_system_issues(health_status)
                
                await asyncio.sleep(60)  # 每分钟检查一次
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"System health monitor error: {e}")
                await asyncio.sleep(30)
    
    async def _stats_update_monitor(self):
        """统计更新监控"""
        while self.is_running:
            try:
                # 更新系统统计
                await self._update_system_stats()
                
                await asyncio.sleep(300)  # 每5分钟更新一次
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Stats update monitor error: {e}")
                await asyncio.sleep(60)
    
    async def _task_cleanup_monitor(self):
        """任务清理监控"""
        while self.is_running:
            try:
                # 清理过期任务
                if self.task_queue:
                    await self.task_queue.cleanup_expired_tasks()
                
                await asyncio.sleep(1800)  # 每30分钟清理一次
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Task cleanup monitor error: {e}")
                await asyncio.sleep(300)
    
    async def check_system_health(self) -> Dict[str, Any]:
        """检查系统健康状态"""
        health_status = {
            "healthy": True,
            "components": {},
            "issues": [],
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            # 检查任务队列
            if self.task_queue:
                queue_stats = self.task_queue.get_stats()
                queue_utilization = int(queue_stats.get("queue_utilization", "0%").rstrip("%"))
                
                health_status["components"]["task_queue"] = {
                    "status": "healthy" if queue_utilization < 90 else "warning",
                    "utilization": f"{queue_utilization}%",
                    "running_tasks": queue_stats.get("running_tasks", 0)
                }
                
                if queue_utilization >= 90:
                    health_status["issues"].append("Task queue utilization high")
            
            # 检查工作流
            if self.workflow_manager:
                workflow_stats = self.workflow_manager.get_manager_stats()
                active_workflows = workflow_stats.get("active_workflows", 0)
                
                health_status["components"]["workflow"] = {
                    "status": "healthy" if active_workflows < 50 else "warning",
                    "active_workflows": active_workflows,
                    "is_running": workflow_stats.get("is_running", False)
                }
                
                if active_workflows >= 50:
                    health_status["issues"].append("Too many active workflows")
            
            # 检查分析器
            if self.analytics:
                analytics_metrics = await self.analytics.get_real_time_metrics()
                buffer_size = analytics_metrics.get("buffer_size", 0)
                
                health_status["components"]["analytics"] = {
                    "status": "healthy" if buffer_size < 1000 else "warning",
                    "buffer_size": buffer_size,
                    "recent_events": analytics_metrics.get("recent_events", 0)
                }
                
                if buffer_size >= 1000:
                    health_status["issues"].append("Analytics buffer size high")
            
            # 检查会话管理器
            if self.session_manager:
                session_health = await self.session_manager.health_check()
                
                health_status["components"]["session_manager"] = {
                    "status": "healthy" if session_health.get("healthy", False) else "error",
                    "details": session_health
                }
                
                if not session_health.get("healthy", False):
                    health_status["issues"].append("Session manager unhealthy")
            
            # 更新整体健康状态
            health_status["healthy"] = len(health_status["issues"]) == 0
            
            return health_status
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            health_status["healthy"] = False
            health_status["issues"].append(f"Health check error: {str(e)}")
            return health_status
    
    async def _handle_system_issues(self, health_status: Dict[str, Any]):
        """处理系统问题"""
        issues = health_status.get("issues", [])
        
        for issue in issues:
            logger.warning(f"Handling system issue: {issue}")
            
            if "Task queue utilization high" in issue:
                # 可以实现队列优化逻辑
                await self._optimize_task_queue()
            
            elif "Too many active workflows" in issue:
                # 可以实现工作流优化逻辑
                await self._optimize_workflows()
            
            elif "Analytics buffer size high" in issue:
                # 可以实现分析器优化逻辑
                await self._optimize_analytics()
            
            elif "Session manager unhealthy" in issue:
                # 可以实现会话管理器修复逻辑
                await self._repair_session_manager()
    
    async def _optimize_task_queue(self):
        """优化任务队列"""
        logger.info("Optimizing task queue...")
        
        # 可以实现队列优化策略
        # 比如：清理无效任务、调整队列大小等
        
        if self.task_queue:
            await self.task_queue.cleanup_expired_tasks()
    
    async def _optimize_workflows(self):
        """优化工作流"""
        logger.info("Optimizing workflows...")
        
        # 可以实现工作流优化策略
        # 比如：取消超时的工作流、调整并发数等
        
        if self.workflow_manager:
            await self.workflow_manager._check_timeout_workflows()
    
    async def _optimize_analytics(self):
        """优化分析器"""
        logger.info("Optimizing analytics...")
        
        # 可以实现分析器优化策略
        # 比如：强制持久化、清理缓存等
        
        if self.analytics:
            await self.analytics._persist_events()
    
    async def _repair_session_manager(self):
        """修复会话管理器"""
        logger.info("Repairing session manager...")
        
        # 可以实现会话管理器修复策略
        # 比如：重新初始化会话、清理无效会话等
        
        if self.session_manager:
            await self.session_manager.rotate_sessions()
    
    async def _update_system_stats(self):
        """更新系统统计"""
        if self.start_time:
            self.system_stats['system_uptime'] = (
                datetime.now() - self.start_time
            ).total_seconds()
        
        # 更新来自各组件的统计
        if self.analytics:
            analytics_report = await self.analytics.get_analytics_report()
            basic_stats = analytics_report.get("basic_stats", {})
            
            self.system_stats['captcha_requests'] = basic_stats.get("total_captcha", 0)
            self.system_stats['successful_captcha_solves'] = basic_stats.get("solved_captcha", 0)
            self.system_stats['failed_captcha_solves'] = basic_stats.get("failed_captcha", 0)
    
    async def process_request(self, url: str, content: str, response: Any = None) -> bool:
        """
        处理单个请求
        
        Args:
            url: 请求URL
            content: 响应内容
            response: 响应对象
            
        Returns:
            bool: 是否成功处理
        """
        self.system_stats['total_requests'] += 1
        
        try:
            # 检测验证码
            detection_result = await self.captcha_detector.detect_captcha(content, response, url)
            
            if detection_result.detected:
                logger.info(f"CAPTCHA detected for URL: {url}")
                
                # 创建任务
                task = ScrapingTask(
                    task_id=f"request_{int(time.time() * 1000)}",
                    url=url,
                    task_type="request_processing",
                    status=TaskStatus.PENDING
                )
                
                # 添加任务到队列
                await self.task_queue.add_task(task)
                
                # 处理验证码工作流
                return await self.workflow.process_captcha_workflow(
                    task, content, response, None
                )
            else:
                # 没有验证码，直接返回成功
                return True
                
        except Exception as e:
            logger.error(f"Request processing failed: {e}")
            return False
    
    async def recover_failed_tasks(self) -> Dict[str, int]:
        """
        恢复失败的任务
        
        Returns:
            Dict[str, int]: 恢复统计
        """
        if self.recovery_manager:
            return await self.recovery_manager.recover_all_recoverable_tasks()
        return {"total_attempts": 0, "successful_recoveries": 0, "failed_recoveries": 0}
    
    async def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        status = {
            "system_running": self.is_running,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "system_stats": self.system_stats.copy(),
            "config": self.config,
            "components": {}
        }
        
        # 添加组件状态
        if self.task_queue:
            status["components"]["task_queue"] = self.task_queue.get_stats()
        
        if self.workflow_manager:
            status["components"]["workflow"] = self.workflow_manager.get_manager_stats()
        
        if self.analytics:
            status["components"]["analytics"] = await self.analytics.get_real_time_metrics()
        
        if self.captcha_detector:
            status["components"]["detector"] = self.captcha_detector.get_detection_stats()
        
        if self.captcha_solver:
            status["components"]["solver"] = self.captcha_solver.get_solver_stats()
        
        return status
    
    async def generate_report(self, 
                            output_file: str = "captcha_system_report.json",
                            time_range: str = "24h") -> bool:
        """
        生成系统报告
        
        Args:
            output_file: 输出文件路径
            time_range: 时间范围
            
        Returns:
            bool: 是否成功生成
        """
        try:
            # 获取系统状态
            system_status = await self.get_system_status()
            
            # 获取分析报告
            analytics_report = {}
            if self.analytics:
                analytics_report = await self.analytics.get_analytics_report(
                    time_range, include_details=True
                )
            
            # 获取健康状态
            health_status = await self.check_system_health()
            
            # 组合报告
            report = {
                "report_info": {
                    "generated_at": datetime.now().isoformat(),
                    "time_range": time_range,
                    "system_version": "1.0.0"
                },
                "system_status": system_status,
                "analytics_report": analytics_report,
                "health_status": health_status
            }
            
            # 保存报告
            if self.analytics:
                return await self.analytics.export_data(output_file, "json", time_range)
            else:
                import json
                report_path = Path(output_file)
                report_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(report_path, 'w', encoding='utf-8') as f:
                    json.dump(report, f, ensure_ascii=False, indent=2)
                
                return True
                
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            return False


# 系统配置模板
DEFAULT_SYSTEM_CONFIG = {
    "detector": {
        "confidence_threshold": 0.7,
        "detection_timeout": 10.0,
        "max_detection_attempts": 3,
        "enable_ml_detection": True,
        "enable_dom_detection": True,
        "enable_image_analysis": True
    },
    "ui": {
        "framework": "tkinter",
        "theme": "light",
        "timeout": 300,
        "auto_refresh": True
    },
    "captcha_solver": {
        "max_solving_time": 300,
        "max_retry_attempts": 3,
        "auto_refresh_enabled": True,
        "input_validation": True,
        "save_user_history": True
    },
    "task_queue": {
        "max_size": 1000,
        "persistence_file": "data/captcha_tasks.json"
    },
    "workflow": {
        "max_retries": 3,
        "retry_delay": 5.0,
        "timeout": 300.0,
        "enable_auto_retry": True,
        "enable_timeout_handling": True,
        "enable_analytics": True
    },
    "analytics": {
        "enable_persistence": True,
        "events_file": "data/captcha_events.json",
        "stats_file": "data/captcha_stats.json"
    },
    "session_manager": {
        "max_sessions": 5,
        "max_requests_per_minute": 30
    }
}


async def create_captcha_system(config: Dict[str, Any] = None) -> CaptchaInteractionSystem:
    """
    创建验证码交互系统
    
    Args:
        config: 系统配置
        
    Returns:
        CaptchaInteractionSystem: 系统实例
    """
    if config is None:
        config = DEFAULT_SYSTEM_CONFIG.copy()
    
    system = CaptchaInteractionSystem(config)
    await system.initialize()
    
    return system