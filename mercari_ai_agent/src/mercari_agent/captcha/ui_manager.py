"""
验证码用户界面管理器

该模块提供验证码人机交互界面的管理功能，包括：
- 多种UI框架支持（tkinter、Qt、Web）
- 不同验证码类型的专门界面
- 用户输入验证和历史记录
- 界面超时和自动刷新
- 详细操作指导和帮助系统
- 进度指示器和实时反馈
- 优化的用户体验
- 异步GUI管理和线程安全
"""

import asyncio
import logging
import time
import json
import re
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from pathlib import Path
import threading

from .captcha_types import (
    CaptchaType, CaptchaChallenge, CaptchaSolution, UIResult,
    CaptchaStatus, CAPTCHA_SOLVING_CONFIG
)
from .async_gui_manager import AsyncGUIManager, GUIConfig
from ..utils.logger import get_logger

logger = get_logger(__name__)

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
    from PIL import Image, ImageTk
    import io
    import requests
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False
    logger.warning("Tkinter not available, UI functionality will be limited")


class UIFramework(ABC):
    """UI框架抽象基类"""
    
    @abstractmethod
    async def show_image_captcha(self, challenge: CaptchaChallenge) -> UIResult:
        """显示图片验证码界面"""
        pass
    
    @abstractmethod
    async def show_slide_captcha(self, challenge: CaptchaChallenge) -> UIResult:
        """显示滑块验证码界面"""
        pass
    
    @abstractmethod
    async def show_click_captcha(self, challenge: CaptchaChallenge) -> UIResult:
        """显示点击验证码界面"""
        pass
    
    @abstractmethod
    async def close(self):
        """关闭UI框架"""
        pass


class TkinterUI(UIFramework):
    """基于Tkinter的UI实现（已修复线程同步死锁问题）"""
    
    def __init__(self, config: Dict[str, Any]):
        if not TKINTER_AVAILABLE:
            raise ImportError("Tkinter is not available")
        
        self.config = config
        self.input_history = []
        self.load_input_history()
        
        # 创建AsyncGUIManager
        gui_config = GUIConfig(
            timeout=config.get("timeout", 600),
            enable_fallback=config.get("enable_fallback", True),
            fallback_to_console=config.get("fallback_to_console", True)
        )
        self.async_gui_manager = AsyncGUIManager(gui_config)
        
        logger.info("TkinterUI initialized with AsyncGUIManager")
    
    async def show_image_captcha(self, challenge: CaptchaChallenge) -> UIResult:
        """显示图片验证码界面（修复版）"""
        try:
            # 初始化异步GUI管理器
            if not self.async_gui_manager.is_initialized:
                success = await self.async_gui_manager.initialize()
                if not success:
                    logger.warning("Failed to initialize GUI, using fallback")
                    return await self._console_fallback(challenge)
            
            # 使用异步GUI管理器显示验证码
            result = await self.async_gui_manager.show_captcha(challenge, self.config)
            
            # 保存输入历史
            if result.text_input and result.text_input not in self.input_history:
                self.input_history.append(result.text_input)
                self.save_input_history()
            
            return result
            
        except Exception as e:
            logger.error(f"Error in show_image_captcha: {e}")
            return UIResult(
                success=False,
                error_message=str(e),
                solving_time=0.0
            )
    
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
                # 保存到历史记录
                if user_input not in self.input_history:
                    self.input_history.append(user_input)
                    self.save_input_history()
                
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
    
    async def show_slide_captcha(self, challenge: CaptchaChallenge) -> UIResult:
        """显示滑块验证码界面（修复版）"""
        try:
            # 初始化异步GUI管理器
            if not self.async_gui_manager.is_initialized:
                success = await self.async_gui_manager.initialize()
                if not success:
                    logger.warning("Failed to initialize GUI for slide captcha")
                    return UIResult(success=False, error_message="GUI initialization failed")
            
            # 使用异步GUI管理器显示验证码
            result = await self.async_gui_manager.show_captcha(challenge, self.config)
            return result
            
        except Exception as e:
            logger.error(f"Error in show_slide_captcha: {e}")
            return UIResult(
                success=False,
                error_message=str(e),
                solving_time=0.0
            )
    
    async def show_click_captcha(self, challenge: CaptchaChallenge) -> UIResult:
        """显示点击验证码界面（修复版）"""
        try:
            # 初始化异步GUI管理器
            if not self.async_gui_manager.is_initialized:
                success = await self.async_gui_manager.initialize()
                if not success:
                    logger.warning("Failed to initialize GUI for click captcha")
                    return UIResult(success=False, error_message="GUI initialization failed")
            
            # 使用异步GUI管理器显示验证码
            result = await self.async_gui_manager.show_captcha(challenge, self.config)
            return result
            
        except Exception as e:
            logger.error(f"Error in show_click_captcha: {e}")
            return UIResult(
                success=False,
                error_message=str(e),
                solving_time=0.0
            )
    
    async def close(self):
        """关闭UI框架（修复版）"""
        try:
            if self.async_gui_manager:
                await self.async_gui_manager.close()
            logger.info("TkinterUI closed successfully")
        except Exception as e:
            logger.error(f"Error closing TkinterUI: {e}")
    
    def load_input_history(self):
        """加载输入历史"""
        try:
            history_file = Path("data/captcha_input_history.json")
            if history_file.exists():
                with open(history_file, 'r', encoding='utf-8') as f:
                    self.input_history = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load input history: {e}")
            self.input_history = []
    
    def save_input_history(self):
        """保存输入历史"""
        try:
            history_file = Path("data/captcha_input_history.json")
            history_file.parent.mkdir(exist_ok=True)
            
            # 保持历史记录在合理范围内
            if len(self.input_history) > 100:
                self.input_history = self.input_history[-50:]
            
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(self.input_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save input history: {e}")


class ImageCaptchaWindow:
    """图片验证码窗口"""
    
    def __init__(self, challenge: CaptchaChallenge, config: Dict[str, Any], 
                 result_callback: Callable[[UIResult], None],
                 input_history: List[str] = None):
        self.challenge = challenge
        self.config = config
        self.result_callback = result_callback
        self.input_history = input_history or []
        
        self.window = None
        self.image_label = None
        self.text_var = None
        self.entry = None
        self.history_var = None
        self.refresh_count = 0
        self.start_time = time.time()
        self.timer_label = None
        self.remaining_time = config.get("timeout", 600)
        self.progress_bar = None
        self.help_window = None
        self.validation_label = None
        
        self.setup_window()
    
    def setup_window(self):
        """设置窗口"""
        self.window = tk.Toplevel()
        self.window.title("验证码识别 - 增强版")
        self.window.geometry("650x550")
        self.window.resizable(True, True)
        self.window.minsize(600, 500)
        
        # 居中显示
        self.window.transient()
        self.window.grab_set()
        
        # 设置关闭事件
        self.window.protocol("WM_DELETE_WINDOW", self.on_cancel)
        
        # 创建界面元素
        self.create_widgets()
        
        # 加载图片
        self.load_image()
        
        # 启动定时器
        self.start_timer()
    
    def create_widgets(self):
        """创建窗口组件"""
        # 主框架
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置主框架权重
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        
        # 创建操作指导面板
        self.create_instruction_panel(main_frame)
        
        # 图片显示区域
        image_frame = ttk.LabelFrame(main_frame, text="验证码图片", padding="5")
        image_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        image_container = ttk.Frame(image_frame)
        image_container.grid(row=0, column=0, sticky=(tk.W, tk.E))
        image_container.columnconfigure(0, weight=1)
        
        self.image_label = ttk.Label(image_container, text="加载中...")
        self.image_label.grid(row=0, column=0, padx=5, pady=5)
        
        # 刷新按钮
        refresh_btn = ttk.Button(image_container, text="刷新验证码", command=self.refresh_image)
        refresh_btn.grid(row=0, column=1, padx=5, pady=5)
        
        # 输入区域
        input_frame = ttk.LabelFrame(main_frame, text="输入验证码", padding="5")
        input_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        input_frame.columnconfigure(1, weight=1)
        
        # 历史记录下拉框
        if self.input_history:
            ttk.Label(input_frame, text="历史记录:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
            self.history_var = tk.StringVar()
            history_combo = ttk.Combobox(input_frame, textvariable=self.history_var,
                                       values=self.input_history[-10:], state="readonly")
            history_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=(0, 5))
            history_combo.bind('<<ComboboxSelected>>', self.on_history_selected)
        
        # 文本输入框
        ttk.Label(input_frame, text="验证码:").grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        self.text_var = tk.StringVar()
        self.entry = ttk.Entry(input_frame, textvariable=self.text_var, font=('Arial', 12))
        self.entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(0, 5))
        self.entry.focus_set()
        
        # 绑定事件
        self.entry.bind('<Return>', lambda e: self.on_submit())
        self.entry.bind('<KeyRelease>', self.on_text_changed)
        
        # 输入验证标签
        self.validation_label = ttk.Label(input_frame, text="", foreground="red")
        self.validation_label.grid(row=2, column=1, sticky=tk.W, pady=(0, 5))
        
        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(button_frame, text="提交", command=self.on_submit).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(button_frame, text="取消", command=self.on_cancel).grid(row=0, column=1, padx=(5, 0))
        ttk.Button(button_frame, text="帮助", command=self.show_help).grid(row=0, column=2, padx=(5, 0))
        
        # 状态区域
        status_frame = ttk.LabelFrame(main_frame, text="状态信息", padding="5")
        status_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E))
        status_frame.columnconfigure(0, weight=1)
        
        # 倒计时和进度条
        timer_frame = ttk.Frame(status_frame)
        timer_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        timer_frame.columnconfigure(1, weight=1)
        
        self.timer_label = ttk.Label(timer_frame, text="", font=('Arial', 10, 'bold'))
        self.timer_label.grid(row=0, column=0, sticky=tk.W)
        
        self.progress_bar = ttk.Progressbar(timer_frame, mode='determinate')
        self.progress_bar.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0))
        
        # 统计信息
        stats_label = ttk.Label(status_frame, text=f"刷新次数: {self.refresh_count}")
        stats_label.grid(row=1, column=0, sticky=tk.W)
    def create_instruction_panel(self, parent):
        """创建操作指导面板"""
        instruction_frame = ttk.LabelFrame(parent, text="操作指导", padding="5")
        instruction_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 创建指导文本
        instructions = [
            "1. 仔细观察验证码图片，识别其中的文字或数字",
            "2. 如果图片不清晰，点击'刷新验证码'按钮获取新的验证码",
            "3. 在输入框中输入识别到的验证码内容",
            "4. 注意区分大小写字母和数字（如0和O，1和I）",
            "5. 输入完成后点击'提交'按钮或按回车键",
            "6. 如遇困难，点击'帮助'按钮查看详细说明"
        ]
        
        for i, instruction in enumerate(instructions):
            label = ttk.Label(instruction_frame, text=instruction, font=('Arial', 9))
            label.grid(row=i, column=0, sticky=tk.W, pady=1)
    
    def on_text_changed(self, event):
        """输入文本变化时的实时验证"""
        text = self.text_var.get()
        validation_msg = self.validate_input(text)
        
        if validation_msg:
            self.validation_label.config(text=validation_msg, foreground="red")
        else:
            self.validation_label.config(text="✓ 输入格式正确", foreground="green")
    
    def validate_input(self, text):
        """验证输入文本"""
        if not text:
            return ""
        
        # 基本验证规则
        if len(text) < 3:
            return "验证码长度通常为3-8位"
        
        if len(text) > 8:
            return "验证码长度不应超过8位"
        
        # 检查是否包含特殊字符
        if not re.match(r'^[a-zA-Z0-9]+$', text):
            return "验证码通常只包含字母和数字"
        
        return ""
    
    def show_help(self):
        """显示帮助窗口"""
        if self.help_window and self.help_window.winfo_exists():
            self.help_window.lift()
            return
        
        self.help_window = tk.Toplevel(self.window)
        self.help_window.title("验证码识别帮助")
        self.help_window.geometry("500x400")
        self.help_window.resizable(False, False)
        
        # 创建帮助内容
        help_frame = ttk.Frame(self.help_window, padding="10")
        help_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 帮助标题
        title_label = ttk.Label(help_frame, text="验证码识别帮助", font=('Arial', 14, 'bold'))
        title_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        
        # 创建滚动文本框
        text_frame = ttk.Frame(help_frame)
        text_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        help_text = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set, 
                           font=('Arial', 10), height=20, width=60)
        help_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar.config(command=help_text.yview)
        
        # 帮助内容
        help_content = """
验证码识别类型识别指南：

1. 数字验证码
   - 通常包含4-6位数字
   - 注意区分数字0和字母O
   - 注意区分数字1和字母I/l

2. 字母验证码
   - 通常包含4-6位字母
   - 注意大小写区分
   - 常见混淆：O/0, I/1/l, S/5, Z/2

3. 混合验证码
   - 包含数字和字母的组合
   - 按顺序输入所有字符
   - 保持大小写一致

常见问题解答：

Q: 验证码图片看不清怎么办？
A: 点击"刷新验证码"按钮获取新的图片。

Q: 输入验证码后提示错误怎么办？
A: 检查大小写是否正确，确认是否混淆了相似字符。

Q: 验证码输入超时怎么办？
A: 系统会自动刷新，重新开始输入即可。

Q: 如何提高识别准确率？
A: 仔细观察字符特征，必要时可以放大浏览器窗口。

输入技巧：
- 逐字符对比，确保准确性
- 使用历史记录功能快速输入
- 注意验证码的时效性

如果持续遇到问题，请联系技术支持。
        """
        
        help_text.insert(tk.END, help_content)
        help_text.config(state=tk.DISABLED)
        
        # 关闭按钮
        close_btn = ttk.Button(help_frame, text="关闭", 
                              command=self.help_window.destroy)
        close_btn.grid(row=2, column=0, pady=(10, 0))
        
        # 配置权重
        help_frame.columnconfigure(0, weight=1)
        help_frame.rowconfigure(1, weight=1)
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        self.help_window.columnconfigure(0, weight=1)
        self.help_window.rowconfigure(0, weight=1)
    
    
    def load_image(self):
        """加载验证码图片"""
        try:
            if self.challenge.image_url:
                # 从URL加载图片
                response = requests.get(self.challenge.image_url, timeout=10)
                if response.status_code == 200:
                    image_data = response.content
                    self.display_image(image_data)
                else:
                    self.image_label.config(text=f"图片加载失败: {response.status_code}")
            elif self.challenge.image_data:
                # 从数据加载图片
                self.display_image(self.challenge.image_data)
            else:
                self.image_label.config(text="无图片数据")
        except Exception as e:
            logger.error(f"Failed to load captcha image: {e}")
            self.image_label.config(text=f"图片加载错误: {str(e)}")
    
    def display_image(self, image_data: bytes):
        """显示图片"""
        try:
            # 使用PIL处理图片
            image = Image.open(io.BytesIO(image_data))
            
            # 调整图片大小
            max_width, max_height = 300, 150
            image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            # 转换为Tkinter格式
            photo = ImageTk.PhotoImage(image)
            
            # 显示图片
            self.image_label.config(image=photo, text="")
            self.image_label.image = photo  # 保持引用
            
        except Exception as e:
            logger.error(f"Failed to display image: {e}")
            self.image_label.config(text=f"图片显示错误: {str(e)}")
    
    def refresh_image(self):
        """刷新验证码图片"""
        self.refresh_count += 1
        self.image_label.config(text="刷新中...")
        
        # 模拟刷新 - 实际应用中应该请求新的验证码
        self.window.after(1000, self.load_image)
    
    def start_timer(self):
        """启动倒计时"""
        self.update_timer()
    
    def update_timer(self):
        """更新倒计时"""
        if self.remaining_time > 0:
            minutes = self.remaining_time // 60
            seconds = self.remaining_time % 60
            
            # 更新倒计时显示
            time_text = f"剩余时间: {minutes:02d}:{seconds:02d}"
            
            # 根据剩余时间设置颜色警告
            if self.remaining_time <= 30:
                self.timer_label.config(text=time_text, foreground="red")
            elif self.remaining_time <= 60:
                self.timer_label.config(text=time_text, foreground="orange")
            else:
                self.timer_label.config(text=time_text, foreground="black")
            
            # 更新进度条
            total_time = self.config.get("timeout", 600)
            progress = ((total_time - self.remaining_time) / total_time) * 100
            self.progress_bar['value'] = progress
            
            # 时间警告提示
            if self.remaining_time == 60:
                messagebox.showwarning("时间警告", "剩余时间不足1分钟，请尽快完成验证！")
            elif self.remaining_time == 30:
                messagebox.showwarning("时间警告", "剩余时间不足30秒，请立即完成验证！")
            
            self.remaining_time -= 1
            self.window.after(1000, self.update_timer)
        else:
            self.on_timeout()
    
    def on_timeout(self):
        """超时处理"""
        messagebox.showerror("验证超时",
                           "验证码输入时间已超过10分钟，请重新获取验证码。\n\n"
                           "提示：您可以点击'刷新验证码'获取新的验证码。")
        self.on_cancel()
    
    def on_history_selected(self, event):
        """历史记录选择事件"""
        selected = self.history_var.get()
        if selected:
            self.text_var.set(selected)
    
    def on_submit(self):
        """提交按钮事件"""
        text_input = self.text_var.get().strip()
        
        # 基本验证
        if not text_input:
            messagebox.showwarning("输入错误", "请输入验证码内容")
            self.entry.focus_set()
            return
        
        # 格式验证
        validation_msg = self.validate_input(text_input)
        if validation_msg:
            result = messagebox.askyesno("输入验证",
                                       f"输入可能有误：{validation_msg}\n\n确定要提交吗？")
            if not result:
                self.entry.focus_set()
                return
        
        solving_time = time.time() - self.start_time
        
        result = UIResult(
            success=True,
            text_input=text_input,
            confidence=0.9,  # 用户输入的置信度
            solving_time=solving_time,
            refresh_count=self.refresh_count,
            input_history=self.input_history
        )
        
        self.result_callback(result)
        self.window.destroy()
    
    def on_cancel(self):
        """取消按钮事件"""
        solving_time = time.time() - self.start_time
        
        result = UIResult(
            success=False,
            cancelled=True,
            solving_time=solving_time,
            refresh_count=self.refresh_count
        )
        
        self.result_callback(result)
        self.window.destroy()
    
    def show(self):
        """显示窗口"""
        self.window.deiconify()


class SlideCaptchaWindow:
    """滑块验证码窗口"""
    
    def __init__(self, challenge: CaptchaChallenge, config: Dict[str, Any],
                 result_callback: Callable[[UIResult], None]):
        self.challenge = challenge
        self.config = config
        self.result_callback = result_callback
        
        self.window = None
        self.canvas = None
        self.slider = None
        self.slide_distance = 0
        self.slide_track = []
        self.is_sliding = False
        self.start_time = time.time()
        
        # 倒计时相关
        self.remaining_time = config.get("timeout", 600)
        self.timer_label = None
        self.progress_bar = None
        self.help_window = None
        
        self.setup_window()
    
    def setup_window(self):
        """设置窗口"""
        self.window = tk.Toplevel()
        self.window.title("滑块验证 - 增强版")
        self.window.geometry("550x450")
        self.window.resizable(True, True)
        self.window.minsize(500, 400)
        
        self.window.transient()
        self.window.grab_set()
        self.window.protocol("WM_DELETE_WINDOW", self.on_cancel)
        
        self.create_widgets()
        self.start_timer()
    
    def create_widgets(self):
        """创建窗口组件"""
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置主框架权重
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        
        # 创建操作指导面板
        self.create_slide_instruction_panel(main_frame)
        
        # 滑块区域
        slider_frame = ttk.LabelFrame(main_frame, text="滑块验证", padding="10")
        slider_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        slider_frame.columnconfigure(0, weight=1)
        
        # 说明文本
        instruction_label = ttk.Label(slider_frame, text="请拖动滑块完成验证",
                                    font=('Arial', 12, 'bold'))
        instruction_label.grid(row=0, column=0, pady=(0, 15))
        
        # 创建滑块画布
        canvas_frame = ttk.Frame(slider_frame)
        canvas_frame.grid(row=1, column=0, pady=(0, 15))
        
        self.canvas = tk.Canvas(canvas_frame, width=400, height=60, bg='lightgray',
                               relief='sunken', bd=2)
        self.canvas.grid(row=0, column=0)
        
        # 绘制滑块轨道
        self.canvas.create_rectangle(15, 25, 385, 35, fill='white', outline='gray', width=2)
        
        # 绘制目标位置提示
        self.canvas.create_text(200, 20, text="拖动到此处", font=('Arial', 8), fill='gray')
        
        # 创建滑块
        self.slider = self.canvas.create_rectangle(15, 20, 35, 40, fill='blue', outline='darkblue', width=2)
        
        # 绑定鼠标事件
        self.canvas.bind("<Button-1>", self.start_slide)
        self.canvas.bind("<B1-Motion>", self.on_slide)
        self.canvas.bind("<ButtonRelease-1>", self.end_slide)
        
        # 滑动状态显示
        status_frame = ttk.Frame(slider_frame)
        status_frame.grid(row=2, column=0, pady=(0, 10))
        
        self.slide_status_label = ttk.Label(status_frame, text="请拖动滑块", font=('Arial', 10))
        self.slide_status_label.grid(row=0, column=0)
        
        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, pady=(0, 10))
        
        ttk.Button(button_frame, text="重置", command=self.reset_slide).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(button_frame, text="提交", command=self.on_submit).grid(row=0, column=1, padx=(5, 0))
        ttk.Button(button_frame, text="取消", command=self.on_cancel).grid(row=0, column=2, padx=(5, 0))
        ttk.Button(button_frame, text="帮助", command=self.show_slide_help).grid(row=0, column=3, padx=(5, 0))
        
        # 状态区域
        status_frame = ttk.LabelFrame(main_frame, text="状态信息", padding="5")
        status_frame.grid(row=3, column=0, sticky=(tk.W, tk.E))
        status_frame.columnconfigure(0, weight=1)
        
        # 倒计时和进度条
        timer_frame = ttk.Frame(status_frame)
        timer_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        timer_frame.columnconfigure(1, weight=1)
        
        self.timer_label = ttk.Label(timer_frame, text="", font=('Arial', 10, 'bold'))
        self.timer_label.grid(row=0, column=0, sticky=tk.W)
        
    def create_slide_instruction_panel(self, parent):
        """创建滑块操作指导面板"""
        instruction_frame = ttk.LabelFrame(parent, text="操作指导", padding="5")
        instruction_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 创建指导文本
        instructions = [
            "1. 点击滑块并按住鼠标左键",
            "2. 拖动滑块到轨道右侧的目标位置",
            "3. 松开鼠标完成滑动验证",
            "4. 滑动距离需要达到最小要求",
            "5. 如需重新滑动，点击'重置'按钮",
            "6. 如遇困难，点击'帮助'按钮查看详细说明"
        ]
        
        for i, instruction in enumerate(instructions):
            label = ttk.Label(instruction_frame, text=instruction, font=('Arial', 9))
            label.grid(row=i, column=0, sticky=tk.W, pady=1)
    
    def start_timer(self):
        """启动倒计时"""
        self.update_timer()
    
    def update_timer(self):
        """更新倒计时"""
        if self.remaining_time > 0:
            minutes = self.remaining_time // 60
            seconds = self.remaining_time % 60
            
            # 更新倒计时显示
            time_text = f"剩余时间: {minutes:02d}:{seconds:02d}"
            
            # 根据剩余时间设置颜色警告
            if self.remaining_time <= 30:
                self.timer_label.config(text=time_text, foreground="red")
            elif self.remaining_time <= 60:
                self.timer_label.config(text=time_text, foreground="orange")
            else:
                self.timer_label.config(text=time_text, foreground="black")
            
            # 更新进度条
            total_time = self.config.get("timeout", 600)
            progress = ((total_time - self.remaining_time) / total_time) * 100
            self.progress_bar['value'] = progress
            
            # 时间警告提示
            if self.remaining_time == 60:
                messagebox.showwarning("时间警告", "剩余时间不足1分钟，请尽快完成验证！")
            elif self.remaining_time == 30:
                messagebox.showwarning("时间警告", "剩余时间不足30秒，请立即完成验证！")
            
            self.remaining_time -= 1
            self.window.after(1000, self.update_timer)
        else:
            self.on_timeout()
    
    def on_timeout(self):
        """超时处理"""
        messagebox.showerror("验证超时", 
                           "滑块验证时间已超过10分钟，请重新开始验证。")
        self.on_cancel()
    
    def show_slide_help(self):
        """显示滑块验证帮助窗口"""
        if self.help_window and self.help_window.winfo_exists():
            self.help_window.lift()
            return
        
        self.help_window = tk.Toplevel(self.window)
        self.help_window.title("滑块验证帮助")
        self.help_window.geometry("450x350")
        self.help_window.resizable(False, False)
        
        # 创建帮助内容
        help_frame = ttk.Frame(self.help_window, padding="10")
        help_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 帮助标题
        title_label = ttk.Label(help_frame, text="滑块验证帮助", font=('Arial', 14, 'bold'))
        title_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        
        # 创建滚动文本框
        text_frame = ttk.Frame(help_frame)
        text_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        help_text = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set, 
                           font=('Arial', 10), height=15, width=50)
        help_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar.config(command=help_text.yview)
        
        # 帮助内容
        help_content = """
滑块验证操作指南：

1. 基本操作步骤：
   - 将鼠标移动到蓝色滑块上
   - 按住鼠标左键不放
   - 拖动滑块向右滑动
   - 到达目标位置后松开鼠标

2. 验证成功条件：
   - 滑动距离需要达到最小要求（通常10像素以上）
   - 滑动轨迹应该相对平滑
   - 在规定时间内完成操作

3. 常见问题解决：
   - 如果滑块不响应，请确保鼠标在滑块区域内点击
   - 如果滑动不顺畅，可以尝试重置后重新滑动
   - 如果验证失败，请检查滑动距离是否足够

4. 操作技巧：
   - 保持鼠标按钮按住状态直到完成滑动
   - 滑动速度适中，不要过快或过慢
   - 滑动轨迹尽量保持水平

5. 注意事项：
   - 验证有时间限制，请及时完成
   - 如果多次失败，可能需要刷新页面重新开始
   - 确保网络连接稳定

如果持续遇到问题，请联系技术支持。
        """
        
        help_text.insert(tk.END, help_content)
        help_text.config(state=tk.DISABLED)
        
        # 关闭按钮
        close_btn = ttk.Button(help_frame, text="关闭", 
                              command=self.help_window.destroy)
        close_btn.grid(row=2, column=0, pady=(10, 0))
        
        # 配置权重
        help_frame.columnconfigure(0, weight=1)
        help_frame.rowconfigure(1, weight=1)
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        self.help_window.columnconfigure(0, weight=1)
        self.help_window.rowconfigure(0, weight=1)
    
        self.progress_bar = ttk.Progressbar(timer_frame, mode='determinate')
        self.progress_bar.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0))
        
        # 滑动距离显示
        self.distance_label = ttk.Label(status_frame, text="滑动距离: 0 px")
        self.distance_label.grid(row=1, column=0, sticky=tk.W)
    
    def start_slide(self, event):
        """开始滑动"""
        self.is_sliding = True
        self.slide_track = [(event.x, event.y)]
        self.slide_status_label.config(text="正在滑动...", foreground="blue")
        logger.debug("Started sliding")
    
    def on_slide(self, event):
        """滑动过程"""
        if self.is_sliding:
            # 计算滑动距离
            start_x = self.slide_track[0][0] if self.slide_track else 0
            self.slide_distance = event.x - start_x
            
            # 限制滑动范围
            if self.slide_distance < 0:
                self.slide_distance = 0
            elif self.slide_distance > 350:
                self.slide_distance = 350
            
            # 更新滑块位置
            self.canvas.coords(self.slider, 15 + self.slide_distance, 20,
                             35 + self.slide_distance, 40)
            
            # 实时更新距离显示
            self.distance_label.config(text=f"滑动距离: {self.slide_distance} px")
            
            # 根据滑动距离提供反馈
            if self.slide_distance < 10:
                self.slide_status_label.config(text="继续滑动...", foreground="orange")
            elif self.slide_distance >= 100:
                self.slide_status_label.config(text="滑动距离充足", foreground="green")
            else:
                self.slide_status_label.config(text="滑动中...", foreground="blue")
            
            # 记录轨迹
            self.slide_track.append((event.x, event.y))
    
    def end_slide(self, event):
        """结束滑动"""
        self.is_sliding = False
        
        # 根据滑动距离提供反馈
        if self.slide_distance < 10:
            self.slide_status_label.config(text="滑动距离不足，请重新滑动", foreground="red")
        elif self.slide_distance >= 100:
            self.slide_status_label.config(text="滑动完成！可以提交验证", foreground="green")
        else:
            self.slide_status_label.config(text="滑动距离可能不足", foreground="orange")
        
        logger.debug(f"Ended sliding, distance: {self.slide_distance}")
    
    def reset_slide(self):
        """重置滑块"""
        self.slide_distance = 0
        self.slide_track = []
        self.canvas.coords(self.slider, 15, 20, 35, 40)
        
        # 重置状态显示
        self.slide_status_label.config(text="请拖动滑块", foreground="black")
        self.distance_label.config(text="滑动距离: 0 px")
    
    def on_submit(self):
        """提交按钮事件"""
        if self.slide_distance < 10:
            messagebox.showwarning("验证失败",
                                 "滑动距离不足，请拖动滑块到足够的距离。\n\n"
                                 "提示：滑动距离需要至少10像素。")
            return
        
        # 验证成功提示
        if self.slide_distance >= 100:
            messagebox.showinfo("验证成功", "滑块验证完成！")
        
        solving_time = time.time() - self.start_time
        
        result = UIResult(
            success=True,
            slide_distance=self.slide_distance,
            confidence=0.8,
            solving_time=solving_time
        )
        
        self.result_callback(result)
        self.window.destroy()
    
    def on_cancel(self):
        """取消按钮事件"""
        solving_time = time.time() - self.start_time
        
        result = UIResult(
            success=False,
            cancelled=True,
            solving_time=solving_time
        )
        
        self.result_callback(result)
        self.window.destroy()
    
    def show(self):
        """显示窗口"""
        self.window.deiconify()


class ClickCaptchaWindow:
    """点击验证码窗口"""
    
    def __init__(self, challenge: CaptchaChallenge, config: Dict[str, Any],
                 result_callback: Callable[[UIResult], None]):
        self.challenge = challenge
        self.config = config
        self.result_callback = result_callback
        
        self.window = None
        self.canvas = None
        self.click_points = []
        self.start_time = time.time()
        
        # 倒计时相关
        self.remaining_time = config.get("timeout", 600)
        self.timer_label = None
        self.progress_bar = None
        self.help_window = None
        
        # 状态标签
        self.click_status_label = None
        self.points_label = None
        
        self.setup_window()
    
    def setup_window(self):
        """设置窗口"""
        self.window = tk.Toplevel()
        self.window.title("点击验证 - 增强版")
        self.window.geometry("700x600")
        self.window.resizable(True, True)
        self.window.minsize(650, 550)
        
        self.window.transient()
        self.window.grab_set()
        self.window.protocol("WM_DELETE_WINDOW", self.on_cancel)
        
        self.create_widgets()
        self.start_timer()
    
    def create_widgets(self):
        """创建窗口组件"""
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置主框架权重
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        
        # 创建操作指导面板
        self.create_click_instruction_panel(main_frame)
        
        # 点击区域
        click_frame = ttk.LabelFrame(main_frame, text="点击验证区域", padding="10")
        click_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        click_frame.columnconfigure(0, weight=1)
        
        # 说明文本
        instruction = self.challenge.instruction or "请按顺序点击指定区域"
        instruction_label = ttk.Label(click_frame, text=instruction,
                                    font=('Arial', 12, 'bold'))
        instruction_label.grid(row=0, column=0, pady=(0, 10))
        
        # 点击画布
        canvas_frame = ttk.Frame(click_frame)
        canvas_frame.grid(row=1, column=0, pady=(0, 10))
        
        self.canvas = tk.Canvas(canvas_frame, width=600, height=350, bg='lightblue',
                               relief='sunken', bd=2)
        self.canvas.grid(row=0, column=0)
        
        # 点击状态显示
        self.click_status_label = ttk.Label(click_frame, text="等待点击...",
                                          font=('Arial', 10))
        self.click_status_label.grid(row=2, column=0, pady=(0, 10))
        
        # 绑定点击事件
        self.canvas.bind("<Button-1>", self.on_click)
        
        # 点击点显示区域
        points_frame = ttk.LabelFrame(main_frame, text="点击点", padding="5")
        points_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.points_label = ttk.Label(points_frame, text="点击点: 无")
        self.points_label.grid(row=0, column=0, sticky=tk.W)
        
        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, pady=(0, 10))
        
        ttk.Button(button_frame, text="撤销", command=self.undo_click).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(button_frame, text="清空", command=self.clear_clicks).grid(row=0, column=1, padx=(5, 0))
        ttk.Button(button_frame, text="提交", command=self.on_submit).grid(row=0, column=2, padx=(5, 0))
        ttk.Button(button_frame, text="取消", command=self.on_cancel).grid(row=0, column=3, padx=(5, 0))
        ttk.Button(button_frame, text="帮助", command=self.show_click_help).grid(row=0, column=4, padx=(5, 0))
        
        # 状态区域
        status_frame = ttk.LabelFrame(main_frame, text="状态信息", padding="5")
        status_frame.grid(row=4, column=0, sticky=(tk.W, tk.E))
        status_frame.columnconfigure(0, weight=1)
        
        # 倒计时和进度条
        timer_frame = ttk.Frame(status_frame)
        timer_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        timer_frame.columnconfigure(1, weight=1)
        
    def create_click_instruction_panel(self, parent):
        """创建点击操作指导面板"""
        instruction_frame = ttk.LabelFrame(parent, text="操作指导", padding="5")
        instruction_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 创建指导文本
        instructions = [
            "1. 根据验证码要求，按顺序点击指定的图像区域",
            "2. 每次点击都会在画布上显示一个红色圆点和序号",
            "3. 点击错误可以使用'撤销'按钮撤销最后一次点击",
            "4. 点击'清空'按钮可以清除所有点击记录",
            "5. 完成所有点击后，点击'提交'按钮提交验证",
            "6. 如遇困难，点击'帮助'按钮查看详细说明"
        ]
        
        for i, instruction in enumerate(instructions):
            label = ttk.Label(instruction_frame, text=instruction, font=('Arial', 9))
            label.grid(row=i, column=0, sticky=tk.W, pady=1)
    
    def start_timer(self):
        """启动倒计时"""
        self.update_timer()
    
    def update_timer(self):
        """更新倒计时"""
        if self.remaining_time > 0:
            minutes = self.remaining_time // 60
            seconds = self.remaining_time % 60
            
            # 更新倒计时显示
            time_text = f"剩余时间: {minutes:02d}:{seconds:02d}"
            
            # 根据剩余时间设置颜色警告
            if self.remaining_time <= 30:
                self.timer_label.config(text=time_text, foreground="red")
            elif self.remaining_time <= 60:
                self.timer_label.config(text=time_text, foreground="orange")
            else:
                self.timer_label.config(text=time_text, foreground="black")
            
            # 更新进度条
            total_time = self.config.get("timeout", 600)
            progress = ((total_time - self.remaining_time) / total_time) * 100
            self.progress_bar['value'] = progress
            
            # 时间警告提示
            if self.remaining_time == 60:
                messagebox.showwarning("时间警告", "剩余时间不足1分钟，请尽快完成验证！")
            elif self.remaining_time == 30:
                messagebox.showwarning("时间警告", "剩余时间不足30秒，请立即完成验证！")
            
            self.remaining_time -= 1
            self.window.after(1000, self.update_timer)
        else:
            self.on_timeout()
    
    def on_timeout(self):
        """超时处理"""
        messagebox.showerror("验证超时", 
                           "点击验证时间已超过10分钟，请重新开始验证。")
        self.on_cancel()
    
    def show_click_help(self):
        """显示点击验证帮助窗口"""
        if self.help_window and self.help_window.winfo_exists():
            self.help_window.lift()
            return
        
        self.help_window = tk.Toplevel(self.window)
        self.help_window.title("点击验证帮助")
        self.help_window.geometry("500x400")
        self.help_window.resizable(False, False)
        
        # 创建帮助内容
        help_frame = ttk.Frame(self.help_window, padding="10")
        help_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 帮助标题
        title_label = ttk.Label(help_frame, text="点击验证帮助", font=('Arial', 14, 'bold'))
        title_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        
        # 创建滚动文本框
        text_frame = ttk.Frame(help_frame)
        text_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        help_text = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set, 
                           font=('Arial', 10), height=18, width=55)
        help_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar.config(command=help_text.yview)
        
        # 帮助内容
        help_content = """
点击验证操作指南：

1. 基本操作步骤：
   - 仔细阅读验证码指示要求
   - 识别需要点击的图像区域
   - 按照要求的顺序依次点击
   - 每次点击后会显示红色圆点和序号

2. 验证要求：
   - 必须按照指定顺序点击
   - 点击位置应该准确
   - 通常需要点击3-5个位置
   - 在规定时间内完成所有点击

3. 常见验证类型：
   - 按顺序点击文字：按照从左到右、从上到下的顺序
   - 点击相同物体：识别并点击所有相同的物体
   - 点击特定位置：根据指示点击特定的图像区域

4. 操作技巧：
   - 仔细观察验证码图像
   - 确认点击顺序后再开始操作
   - 点击位置要准确，尽量点击目标中心
   - 如果点击错误，及时使用撤销功能

5. 注意事项：
   - 点击过快可能被识别为机器行为
   - 确保每次点击都有视觉反馈
   - 验证有时间限制，请合理安排时间
   - 如果多次失败，可能需要刷新页面

6. 错误处理：
   - 点击错误：使用'撤销'按钮撤销最后一次点击
   - 全部重新开始：使用'清空'按钮清除所有点击
   - 超时：系统会自动提示，请重新开始验证

如果持续遇到问题，请联系技术支持。
        """
        
        help_text.insert(tk.END, help_content)
        help_text.config(state=tk.DISABLED)
        
        # 关闭按钮
        close_btn = ttk.Button(help_frame, text="关闭", 
                              command=self.help_window.destroy)
        close_btn.grid(row=2, column=0, pady=(10, 0))
        
        # 配置权重
        help_frame.columnconfigure(0, weight=1)
        help_frame.rowconfigure(1, weight=1)
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        self.help_window.columnconfigure(0, weight=1)
        self.help_window.rowconfigure(0, weight=1)
    
        self.timer_label = ttk.Label(timer_frame, text="", font=('Arial', 10, 'bold'))
        self.timer_label.grid(row=0, column=0, sticky=tk.W)
        
        self.progress_bar = ttk.Progressbar(timer_frame, mode='determinate')
        self.progress_bar.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0))
        
        # 点击统计
        self.click_count_label = ttk.Label(status_frame, text="点击次数: 0")
        self.click_count_label.grid(row=1, column=0, sticky=tk.W)
        ttk.Button(button_frame, text="提交", command=self.on_submit).grid(row=0, column=2, padx=(5, 0))
        ttk.Button(button_frame, text="取消", command=self.on_cancel).grid(row=0, column=3, padx=(5, 0))
    
    def on_click(self, event):
        """点击事件"""
        x, y = event.x, event.y
        self.click_points.append((x, y))
        
        # 在画布上绘制点击点
        point_id = self.canvas.create_oval(x-8, y-8, x+8, y+8,
                                         fill='red', outline='darkred', width=2)
        
        # 显示点击序号
        text_id = self.canvas.create_text(x, y-20, text=str(len(self.click_points)),
                                        fill='white', font=('Arial', 12, 'bold'))
        
        # 更新点击点显示
        self.update_points_display()
        
        # 实时状态反馈
        click_count = len(self.click_points)
        if click_count == 1:
            self.click_status_label.config(text="第一次点击完成，继续点击...", foreground="blue")
        elif click_count < 5:
            self.click_status_label.config(text=f"已点击{click_count}次，继续点击...", foreground="blue")
        else:
            self.click_status_label.config(text="点击次数充足，可以提交验证", foreground="green")
        
        logger.debug(f"Clicked at ({x}, {y})")
    
    def update_points_display(self):
        """更新点击点显示"""
        if self.click_points:
            points_str = ", ".join([f"({x},{y})" for x, y in self.click_points])
            self.points_label.config(text=f"点击点: {points_str}")
        else:
            self.points_label.config(text="点击点: 无")
        
        # 更新点击统计
        self.click_count_label.config(text=f"点击次数: {len(self.click_points)}")
    
    def undo_click(self):
        """撤销最后一次点击"""
        if self.click_points:
            self.click_points.pop()
            self.canvas.delete("all")  # 清空画布
            
            # 重新绘制所有点击点
            for i, (x, y) in enumerate(self.click_points):
                self.canvas.create_oval(x-8, y-8, x+8, y+8,
                                      fill='red', outline='darkred', width=2)
                self.canvas.create_text(x, y-20, text=str(i+1),
                                      fill='white', font=('Arial', 12, 'bold'))
            
            self.update_points_display()
            
            # 更新状态反馈
            if not self.click_points:
                self.click_status_label.config(text="所有点击已撤销，请重新点击", foreground="orange")
            else:
                self.click_status_label.config(text="已撤销最后一次点击", foreground="orange")
        else:
            messagebox.showinfo("提示", "没有可撤销的点击")
    
    def clear_clicks(self):
        """清空所有点击点"""
        if self.click_points:
            self.click_points = []
            self.canvas.delete("all")
            self.update_points_display()
            self.click_status_label.config(text="已清空所有点击，请重新开始", foreground="orange")
        else:
            messagebox.showinfo("提示", "没有点击记录需要清空")
    
    def on_submit(self):
        """提交按钮事件"""
        if not self.click_points:
            messagebox.showwarning("验证失败",
                                 "请至少点击一个位置完成验证。\n\n"
                                 "提示：根据验证码要求点击相应的图像区域。")
            return
        
        # 验证点击数量
        if len(self.click_points) < 2:
            result = messagebox.askyesno("验证确认",
                                       f"您只点击了{len(self.click_points)}个位置，这可能不够。\n\n"
                                       "确定要提交验证吗？")
            if not result:
                return
        
        # 验证成功提示
        if len(self.click_points) >= 3:
            messagebox.showinfo("验证成功", "点击验证完成！")
        
        solving_time = time.time() - self.start_time
        
        result = UIResult(
            success=True,
            click_points=self.click_points,
            confidence=0.8,
            solving_time=solving_time
        )
        
        self.result_callback(result)
        self.window.destroy()
    
    def on_cancel(self):
        """取消按钮事件"""
        solving_time = time.time() - self.start_time
        
        result = UIResult(
            success=False,
            cancelled=True,
            solving_time=solving_time
        )
        
        self.result_callback(result)
        self.window.destroy()
    
    def show(self):
        """显示窗口"""
        self.window.deiconify()


class CaptchaUIManager:
    """验证码UI管理器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化UI管理器
        
        Args:
            config: UI配置
        """
        self.config = config or CAPTCHA_SOLVING_CONFIG
        self.ui_framework = self._detect_ui_framework()
        
        logger.info(f"CaptchaUIManager initialized with framework: {type(self.ui_framework).__name__}")
    
    def _detect_ui_framework(self) -> UIFramework:
        """检测并初始化UI框架"""
        framework_name = self.config.get("ui", {}).get("framework", "tkinter")
        
        if framework_name == "tkinter" and TKINTER_AVAILABLE:
            return TkinterUI(self.config)
        else:
            # 如果没有可用的UI框架，返回模拟实现
            logger.warning("No UI framework available, using mock implementation")
            return MockUIFramework()
    
    async def show_captcha_ui(self, challenge: CaptchaChallenge) -> UIResult:
        """
        显示验证码UI
        
        Args:
            challenge: 验证码挑战
            
        Returns:
            UIResult: 用户输入结果
        """
        try:
            if challenge.captcha_type == CaptchaType.IMAGE_TEXT:
                return await self.ui_framework.show_image_captcha(challenge)
            elif challenge.captcha_type == CaptchaType.SLIDE_PUZZLE:
                return await self.ui_framework.show_slide_captcha(challenge)
            elif challenge.captcha_type == CaptchaType.CLICK_SEQUENCE:
                return await self.ui_framework.show_click_captcha(challenge)
            else:
                logger.warning(f"Unsupported captcha type: {challenge.captcha_type}")
                return UIResult(
                    success=False,
                    cancelled=True,
                    solving_time=0.0
                )
        except Exception as e:
            logger.error(f"UI display failed: {e}")
            return UIResult(
                success=False,
                cancelled=True,
                solving_time=0.0
            )
    
    async def close(self):
        """关闭UI管理器"""
        if self.ui_framework:
            await self.ui_framework.close()


class MockUIFramework(UIFramework):
    """模拟UI框架（用于测试）"""
    
    async def show_image_captcha(self, challenge: CaptchaChallenge) -> UIResult:
        """模拟图片验证码界面"""
        logger.info(f"Mock image captcha for challenge: {challenge.challenge_id}")
        
        # 模拟用户输入
        await asyncio.sleep(2)
        
        return UIResult(
            success=True,
            text_input="mock_text",
            confidence=0.8,
            solving_time=2.0
        )
    
    async def show_slide_captcha(self, challenge: CaptchaChallenge) -> UIResult:
        """模拟滑块验证码界面"""
        logger.info(f"Mock slide captcha for challenge: {challenge.challenge_id}")
        
        await asyncio.sleep(1.5)
        
        return UIResult(
            success=True,
            slide_distance=150,
            confidence=0.8,
            solving_time=1.5
        )
    
    async def show_click_captcha(self, challenge: CaptchaChallenge) -> UIResult:
        """模拟点击验证码界面"""
        logger.info(f"Mock click captcha for challenge: {challenge.challenge_id}")
        
        await asyncio.sleep(3)
        
        return UIResult(
            success=True,
            click_points=[(100, 100), (200, 150), (300, 200)],
            confidence=0.8,
            solving_time=3.0
        )
    
    async def close(self):
        """关闭模拟框架"""
        logger.info("Mock UI framework closed")