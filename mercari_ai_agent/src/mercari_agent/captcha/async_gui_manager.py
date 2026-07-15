"""
异步GUI管理器模块

该模块提供异步GUI管理功能，解决GUI线程同步死锁问题。
通过专用的GUI线程管理器，实现GUI与主进程的安全通信。

主要功能：
- 专用GUI线程管理器
- 异步GUI架构支持
- 跨平台GUI权限检查
- 线程安全的GUI操作
- 优雅的资源清理
- 错误恢复机制

技术特点：
- 使用 threading.Event 进行线程同步
- 实现 Queue 用于线程间通信
- 支持超时保护和降级方案
- 提供完整的错误处理机制

Author: Mercari AI Agent Team
"""

import asyncio
import threading
import queue
import logging
import time
import os
import sys
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from abc import ABC, abstractmethod
import signal
import platform

from .captcha_types import (
    CaptchaType, CaptchaChallenge, CaptchaSolution, UIResult,
    CaptchaStatus, CAPTCHA_SOLVING_CONFIG
)
from ..utils.logger import get_logger

logger = get_logger(__name__)


class GUIState(Enum):
    """GUI状态枚举"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    CLOSING = "closing"
    CLOSED = "closed"
    ERROR = "error"


class GUIEnvironment(Enum):
    """GUI环境枚举"""
    DESKTOP = "desktop"
    HEADLESS = "headless"
    DOCKER = "docker"
    SSH = "ssh"
    UNKNOWN = "unknown"


@dataclass
class GUIConfig:
    """GUI配置"""
    timeout: float = 600.0  # 10分钟超时
    enable_fallback: bool = True
    auto_close_timeout: float = 30.0  # 30秒自动关闭
    max_retry_attempts: int = 3
    thread_join_timeout: float = 10.0  # 线程join超时
    enable_debug_mode: bool = False
    fallback_to_console: bool = True
    gui_check_timeout: float = 5.0  # GUI环境检查超时
    
    # 跨平台配置
    platform_specific: Dict[str, Any] = field(default_factory=lambda: {
        'windows': {
            'use_threading_timer': True,
            'close_method': 'destroy'
        },
        'linux': {
            'check_display': True,
            'use_xvfb_fallback': True,
            'close_method': 'quit'
        },
        'darwin': {
            'check_aqua': True,
            'close_method': 'quit'
        }
    })


@dataclass
class GUIMessage:
    """GUI消息"""
    message_type: str
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    message_id: str = field(default_factory=lambda: str(int(time.time() * 1000000)))
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'message_type': self.message_type,
            'payload': self.payload,
            'timestamp': self.timestamp.isoformat(),
            'message_id': self.message_id
        }


class GUIEnvironmentDetector:
    """GUI环境检测器"""
    
    @staticmethod
    def detect_environment() -> GUIEnvironment:
        """检测GUI环境"""
        try:
            # 检查是否在Docker环境
            if os.path.exists('/.dockerenv'):
                return GUIEnvironment.DOCKER
            
            # 检查是否通过SSH连接
            if 'SSH_CLIENT' in os.environ or 'SSH_CONNECTION' in os.environ:
                return GUIEnvironment.SSH
            
            # 检查显示环境
            if platform.system() == 'Linux':
                if not os.environ.get('DISPLAY'):
                    return GUIEnvironment.HEADLESS
            elif platform.system() == 'Windows':
                # Windows桌面环境检查
                pass
            elif platform.system() == 'Darwin':
                # macOS桌面环境检查
                pass
            
            return GUIEnvironment.DESKTOP
            
        except Exception as e:
            logger.warning(f"Failed to detect GUI environment: {e}")
            return GUIEnvironment.UNKNOWN
    
    @staticmethod
    def is_gui_available() -> bool:
        """检查GUI是否可用"""
        try:
            environment = GUIEnvironmentDetector.detect_environment()
            
            if environment in [GUIEnvironment.DOCKER, GUIEnvironment.HEADLESS]:
                return False
            
            # 尝试导入GUI库
            try:
                import tkinter as tk
                # 尝试创建测试窗口
                test_root = tk.Tk()
                test_root.withdraw()
                test_root.destroy()
                return True
            except Exception as e:
                logger.debug(f"GUI availability test failed: {e}")
                return False
                
        except Exception as e:
            logger.warning(f"GUI availability check failed: {e}")
            return False


class ThreadSafeGUIManager:
    """线程安全的GUI管理器"""
    
    def __init__(self, config: GUIConfig):
        self.config = config
        self.gui_thread: Optional[threading.Thread] = None
        self.gui_state = GUIState.IDLE
        self.state_lock = threading.Lock()
        
        # 线程间通信
        self.command_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.shutdown_event = threading.Event()
        
        # GUI组件
        self.root = None
        self.current_window = None
        
        # 错误处理
        self.last_error: Optional[Exception] = None
        self.error_count = 0
        
        logger.info("ThreadSafeGUIManager initialized")
    
    def start_gui_thread(self) -> bool:
        """启动GUI线程"""
        with self.state_lock:
            if self.gui_state != GUIState.IDLE:
                logger.warning(f"GUI thread already started or in invalid state: {self.gui_state}")
                return False
            
            self.gui_state = GUIState.INITIALIZING
        
        try:
            # 检查GUI环境
            if not GUIEnvironmentDetector.is_gui_available():
                logger.error("GUI environment is not available")
                self._set_state(GUIState.ERROR)
                return False
            
            # 创建GUI线程
            self.gui_thread = threading.Thread(
                target=self._gui_thread_main,
                name="CaptchaGUI",
                daemon=False  # 不使用daemon线程
            )
            
            self.gui_thread.start()
            
            # 等待GUI线程初始化完成
            init_timeout = self.config.gui_check_timeout
            start_time = time.time()
            
            while self.gui_state == GUIState.INITIALIZING:
                if time.time() - start_time > init_timeout:
                    logger.error("GUI thread initialization timeout")
                    self._set_state(GUIState.ERROR)
                    return False
                time.sleep(0.1)
            
            if self.gui_state == GUIState.ACTIVE:
                logger.info("GUI thread started successfully")
                return True
            else:
                logger.error(f"GUI thread failed to start: {self.gui_state}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start GUI thread: {e}")
            self._set_state(GUIState.ERROR)
            self.last_error = e
            return False
    
    def _gui_thread_main(self):
        """GUI线程主函数"""
        try:
            logger.debug("GUI thread started")
            
            # 导入GUI库
            import tkinter as tk
            from tkinter import ttk
            
            # 创建根窗口
            self.root = tk.Tk()
            self.root.withdraw()  # 隐藏主窗口
            
            # 配置根窗口
            self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)
            
            # 设置为活动状态
            self._set_state(GUIState.ACTIVE)
            
            # 主循环
            self._gui_main_loop()
            
        except Exception as e:
            logger.error(f"GUI thread error: {e}")
            self.last_error = e
            self._set_state(GUIState.ERROR)
        finally:
            self._cleanup_gui()
            self._set_state(GUIState.CLOSED)
            logger.debug("GUI thread ended")
    
    def _gui_main_loop(self):
        """GUI主循环"""
        while not self.shutdown_event.is_set():
            try:
                # 处理GUI事件
                self.root.update_idletasks()
                self.root.update()
                
                # 处理命令队列
                try:
                    command = self.command_queue.get(timeout=0.1)
                    self._handle_command(command)
                except queue.Empty:
                    pass
                
                # 短暂休眠
                time.sleep(0.01)
                
            except Exception as e:
                logger.error(f"GUI main loop error: {e}")
                self.error_count += 1
                if self.error_count > 10:
                    logger.error("Too many GUI errors, shutting down")
                    break
                time.sleep(0.1)
    
    def _handle_command(self, command: GUIMessage):
        """处理命令"""
        try:
            if command.message_type == 'show_captcha':
                result = self._show_captcha_window(command.payload)
                self.result_queue.put(GUIMessage('captcha_result', {'result': result}))
            
            elif command.message_type == 'close_window':
                self._close_current_window()
                self.result_queue.put(GUIMessage('window_closed', {}))
            
            elif command.message_type == 'shutdown':
                self.shutdown_event.set()
                self.result_queue.put(GUIMessage('shutdown_complete', {}))
            
            else:
                logger.warning(f"Unknown command type: {command.message_type}")
                
        except Exception as e:
            logger.error(f"Error handling command {command.message_type}: {e}")
            self.result_queue.put(GUIMessage('error', {'error': str(e)}))
    
    def _show_captcha_window(self, payload: Dict[str, Any]) -> UIResult:
        """显示验证码窗口"""
        try:
            challenge = payload.get('challenge')
            config = payload.get('config', {})
            
            # 创建验证码窗口
            if challenge.captcha_type == CaptchaType.IMAGE_TEXT:
                from .ui_manager import ImageCaptchaWindow
                window = ImageCaptchaWindow(
                    challenge=challenge,
                    config=config,
                    result_callback=None  # 不使用回调，直接返回结果
                )
            else:
                # 其他类型的验证码窗口
                logger.warning(f"Unsupported captcha type: {challenge.captcha_type}")
                return UIResult(success=False, error_message="Unsupported captcha type")
            
            # 显示窗口并等待结果
            self.current_window = window
            window.show()
            
            # 等待用户操作
            result = self._wait_for_user_input(window)
            
            return result
            
        except Exception as e:
            logger.error(f"Error showing captcha window: {e}")
            return UIResult(success=False, error_message=str(e))
    
    def _wait_for_user_input(self, window) -> UIResult:
        """等待用户输入"""
        # 这里需要实现等待用户输入的逻辑
        # 由于GUI窗口运行在同一线程，需要特殊处理
        start_time = time.time()
        timeout = self.config.timeout
        
        while time.time() - start_time < timeout:
            if self.shutdown_event.is_set():
                return UIResult(success=False, cancelled=True)
            
            # 处理GUI事件
            self.root.update_idletasks()
            self.root.update()
            
            # 检查窗口是否完成
            if hasattr(window, 'result') and window.result is not None:
                return window.result
            
            time.sleep(0.1)
        
        # 超时
        return UIResult(success=False, cancelled=True, solving_time=timeout)
    
    def _close_current_window(self):
        """关闭当前窗口"""
        if self.current_window:
            try:
                if hasattr(self.current_window, 'window') and self.current_window.window:
                    self.current_window.window.destroy()
                self.current_window = None
            except Exception as e:
                logger.error(f"Error closing window: {e}")
    
    def _on_window_close(self):
        """窗口关闭事件"""
        self.shutdown_event.set()
    
    def _cleanup_gui(self):
        """清理GUI资源"""
        try:
            if self.current_window:
                self._close_current_window()
            
            if self.root:
                self.root.quit()
                self.root.destroy()
                self.root = None
                
        except Exception as e:
            logger.error(f"Error cleaning up GUI: {e}")
    
    def _set_state(self, new_state: GUIState):
        """设置状态"""
        with self.state_lock:
            old_state = self.gui_state
            self.gui_state = new_state
            if old_state != new_state:
                logger.debug(f"GUI state changed: {old_state} -> {new_state}")
    
    def send_command(self, command: GUIMessage) -> Optional[GUIMessage]:
        """发送命令"""
        try:
            self.command_queue.put(command, timeout=1.0)
            
            # 等待结果
            result = self.result_queue.get(timeout=self.config.timeout)
            return result
            
        except queue.Empty:
            logger.error("Command timeout")
            return None
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            return None
    
    def stop_gui_thread(self):
        """停止GUI线程"""
        logger.info("Stopping GUI thread")
        
        with self.state_lock:
            if self.gui_state in [GUIState.CLOSED, GUIState.ERROR]:
                return
            
            self._set_state(GUIState.CLOSING)
        
        try:
            # 发送关闭命令
            self.shutdown_event.set()
            
            if self.gui_thread and self.gui_thread.is_alive():
                self.gui_thread.join(timeout=self.config.thread_join_timeout)
                
                if self.gui_thread.is_alive():
                    logger.warning("GUI thread did not terminate gracefully")
                    # 强制终止（不推荐，但作为最后手段）
                    if hasattr(self.gui_thread, '_stop'):
                        self.gui_thread._stop()
            
            self.gui_thread = None
            self._set_state(GUIState.CLOSED)
            
        except Exception as e:
            logger.error(f"Error stopping GUI thread: {e}")
            self._set_state(GUIState.ERROR)
    
    def is_active(self) -> bool:
        """检查是否活动"""
        with self.state_lock:
            return self.gui_state == GUIState.ACTIVE
    
    def get_state(self) -> GUIState:
        """获取状态"""
        with self.state_lock:
            return self.gui_state


class AsyncGUIManager:
    """异步GUI管理器"""
    
    def __init__(self, config: Optional[GUIConfig] = None):
        self.config = config or GUIConfig()
        self.gui_manager: Optional[ThreadSafeGUIManager] = None
        self.is_initialized = False
        self.environment = GUIEnvironmentDetector.detect_environment()
        
        logger.info(f"AsyncGUIManager initialized for environment: {self.environment}")
    
    async def initialize(self) -> bool:
        """初始化异步GUI管理器"""
        if self.is_initialized:
            return True
        
        try:
            # 检查GUI环境
            if not GUIEnvironmentDetector.is_gui_available():
                logger.warning("GUI not available, initialization skipped")
                return False
            
            # 创建GUI管理器
            self.gui_manager = ThreadSafeGUIManager(self.config)
            
            # 启动GUI线程
            success = await asyncio.get_event_loop().run_in_executor(
                None, self.gui_manager.start_gui_thread
            )
            
            if success:
                self.is_initialized = True
                logger.info("AsyncGUIManager initialized successfully")
                return True
            else:
                logger.error("Failed to initialize AsyncGUIManager")
                return False
                
        except Exception as e:
            logger.error(f"AsyncGUIManager initialization error: {e}")
            return False
    
    async def show_captcha(self, challenge: CaptchaChallenge, config: Dict[str, Any] = None) -> UIResult:
        """显示验证码"""
        if not self.is_initialized or not self.gui_manager:
            # 降级到控制台模式
            if self.config.fallback_to_console:
                return await self._console_fallback(challenge)
            else:
                return UIResult(success=False, error_message="GUI not initialized")
        
        try:
            # 创建命令
            command = GUIMessage('show_captcha', {
                'challenge': challenge,
                'config': config or {}
            })
            
            # 发送命令并等待结果
            result_message = await asyncio.get_event_loop().run_in_executor(
                None, self.gui_manager.send_command, command
            )
            
            if result_message and result_message.message_type == 'captcha_result':
                return result_message.payload.get('result')
            else:
                return UIResult(success=False, error_message="No result received")
                
        except Exception as e:
            logger.error(f"Error showing captcha: {e}")
            return UIResult(success=False, error_message=str(e))
    
    async def _console_fallback(self, challenge: CaptchaChallenge) -> UIResult:
        """控制台降级方案"""
        logger.info("Using console fallback for captcha")
        
        try:
            print(f"\n=== 验证码识别 ===")
            print(f"类型: {challenge.captcha_type}")
            print(f"说明: {challenge.description}")
            
            if challenge.image_url:
                print(f"图片地址: {challenge.image_url}")
            
            # 等待用户输入
            user_input = input("请输入验证码: ").strip()
            
            if user_input:
                return UIResult(
                    success=True,
                    text_input=user_input,
                    solving_time=0.0
                )
            else:
                return UIResult(success=False, cancelled=True)
                
        except KeyboardInterrupt:
            return UIResult(success=False, cancelled=True)
        except Exception as e:
            logger.error(f"Console fallback error: {e}")
            return UIResult(success=False, error_message=str(e))
    
    async def close(self):
        """关闭异步GUI管理器"""
        if self.gui_manager:
            await asyncio.get_event_loop().run_in_executor(
                None, self.gui_manager.stop_gui_thread
            )
            self.gui_manager = None
        
        self.is_initialized = False
        logger.info("AsyncGUIManager closed")
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态信息"""
        return {
            'is_initialized': self.is_initialized,
            'environment': self.environment.value,
            'gui_available': GUIEnvironmentDetector.is_gui_available(),
            'gui_state': self.gui_manager.get_state().value if self.gui_manager else None,
            'config': {
                'timeout': self.config.timeout,
                'enable_fallback': self.config.enable_fallback,
                'fallback_to_console': self.config.fallback_to_console
            }
        }