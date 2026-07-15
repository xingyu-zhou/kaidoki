"""
验证码人机交互系统模块

该模块提供完整的验证码处理解决方案，包括：
- 验证码检测和识别
- 人机交互界面
- 任务队列管理
- 处理流程控制
- 统计分析功能
"""

from .captcha_types import (
    CaptchaType,
    CaptchaStatus,
    CaptchaChallenge,
    CaptchaSolution,
    CaptchaDetectionResult,
    UIResult,
    CAPTCHA_PATTERNS,
    CAPTCHA_DETECTION_CONFIG,
    CAPTCHA_SOLVING_CONFIG
)

from .captcha_detector import CaptchaDetector
from .captcha_solver import CaptchaSolver, SolutionValidator, SolutionApplier
from .ui_manager import CaptchaUIManager, TkinterUI
from .task_queue import TaskQueue, ScrapingTask, TaskStatus, TaskPriority
from .workflow import CaptchaWorkflow, WorkflowManager, RecoveryManager
from .analytics import CaptchaAnalytics, CaptchaEvent, EventType
from .system import CaptchaInteractionSystem, create_captcha_system

__version__ = "1.0.0"
__author__ = "Mercari AI Agent Team"

__all__ = [
    # 核心类型
    "CaptchaType",
    "CaptchaStatus", 
    "CaptchaChallenge",
    "CaptchaSolution",
    "CaptchaDetectionResult",
    "UIResult",
    
    # 检测和解决
    "CaptchaDetector",
    "CaptchaSolver",
    "SolutionValidator",
    "SolutionApplier",
    
    # 用户界面
    "CaptchaUIManager",
    "TkinterUI",
    
    # 任务管理
    "TaskQueue",
    "ScrapingTask",
    "TaskStatus",
    "TaskPriority",
    
    # 工作流
    "CaptchaWorkflow",
    "WorkflowManager", 
    "RecoveryManager",
    
    # 分析
    "CaptchaAnalytics",
    "CaptchaEvent",
    "EventType",
    
    # 系统集成
    "CaptchaInteractionSystem",
    "create_captcha_system",
    
    # 配置
    "CAPTCHA_PATTERNS",
    "CAPTCHA_DETECTION_CONFIG",
    "CAPTCHA_SOLVING_CONFIG"
]