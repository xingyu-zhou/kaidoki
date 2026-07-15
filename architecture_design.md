# 🕸️ 网络爬虫系统CAPTCHA人机交互架构设计

## 📋 项目概述

设计一个具备人机交互界面的网络爬虫系统架构，在现有智能请求频率控制基础上，集成CAPTCHA检测与处理模块。当系统遇到验证码时，自动暂停爬取进程并弹出可视化界面窗口，支持多种验证码类型的手动识别和处理。

## 🎯 核心需求

### 功能需求
- ✅ CAPTCHA检测与处理模块
- ✅ 人机交互可视化界面
- ✅ 多种验证码类型支持（图片、滑块、点击）
- ✅ 爬虫任务队列状态管理
- ✅ 无缝恢复机制
- ✅ 验证成功率统计
- ✅ 自动超时重试机制

### 非功能需求
- 🔄 高可用性和容错性
- ⚡ 低延迟响应
- 📊 实时监控和统计
- 🔒 安全性和隐私保护

## 🏗️ 系统架构设计

### 1. 核心模块架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    CAPTCHA人机交互系统                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │  CAPTCHA检测     │  │  人机交互界面    │  │  任务队列管理    │  │
│  │  & 处理模块      │  │     系统        │  │     系统        │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │  统计分析       │  │  恢复机制       │  │  配置管理       │  │
│  │    模块         │  │    模块         │  │    模块         │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                    现有爬虫系统基础                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │  AntiBotHandler │  │  SessionManager │  │  MercariScraper │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2. 详细模块设计

## 🔍 CAPTCHA检测与处理模块

### 2.1 模块架构

```python
# 验证码类型枚举
class CaptchaType(Enum):
    IMAGE_TEXT = "image_text"         # 图片文字验证码
    SLIDE_PUZZLE = "slide_puzzle"     # 滑块验证码
    CLICK_SEQUENCE = "click_sequence"  # 点击序列验证码
    RECAPTCHA_V2 = "recaptcha_v2"     # Google reCAPTCHA v2
    RECAPTCHA_V3 = "recaptcha_v3"     # Google reCAPTCHA v3
    HCAPTCHA = "hcaptcha"             # hCaptcha
    FUNCAPTCHA = "funcaptcha"         # FunCaptcha
    GEETEST = "geetest"               # 极验验证码
    CUSTOM = "custom"                 # 自定义验证码
```

### 2.2 核心类设计

```python
@dataclass
class CaptchaChallenge:
    """验证码挑战数据"""
    challenge_id: str
    captcha_type: CaptchaType
    image_url: Optional[str] = None
    image_data: Optional[bytes] = None
    challenge_params: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    
    # 验证码特定参数
    slide_track: Optional[List[Tuple[int, int]]] = None  # 滑块轨迹
    click_points: Optional[List[Tuple[int, int]]] = None  # 点击坐标
    text_answer: Optional[str] = None                    # 文字答案

@dataclass
class CaptchaSolution:
    """验证码解决方案"""
    challenge_id: str
    solution_type: CaptchaType
    solution_data: Dict[str, Any]
    confidence: float
    solving_time: float
    solved_at: datetime = field(default_factory=datetime.now)
    
    # 解决方案数据
    text_result: Optional[str] = None
    coordinates: Optional[List[Tuple[int, int]]] = None
    slide_distance: Optional[int] = None
    token: Optional[str] = None

class CaptchaDetector:
    """验证码检测器"""
    
    def __init__(self):
        self.detection_patterns = self._load_detection_patterns()
        self.ml_model = self._load_ml_model()
    
    async def detect_captcha(self, content: str, response: aiohttp.ClientResponse) -> Optional[CaptchaChallenge]:
        """检测验证码"""
        # 1. 基于规则的检测
        rule_result = self._rule_based_detection(content)
        
        # 2. 基于机器学习的检测
        ml_result = self._ml_based_detection(content)
        
        # 3. 基于DOM结构的检测
        dom_result = self._dom_based_detection(content)
        
        # 4. 融合检测结果
        return self._fuse_detection_results([rule_result, ml_result, dom_result])
    
    def _rule_based_detection(self, content: str) -> Optional[CaptchaChallenge]:
        """基于规则的检测"""
        patterns = {
            CaptchaType.IMAGE_TEXT: [
                r'<img[^>]*captcha[^>]*>',
                r'verification.*image',
                r'验证码.*图片'
            ],
            CaptchaType.SLIDE_PUZZLE: [
                r'slide.*verify',
                r'滑动.*验证',
                r'拖动.*滑块'
            ],
            CaptchaType.RECAPTCHA_V2: [
                r'g-recaptcha',
                r'recaptcha.*v2'
            ]
        }
        
        for captcha_type, type_patterns in patterns.items():
            for pattern in type_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    return self._create_challenge(captcha_type, content)
        
        return None

class CaptchaSolver:
    """验证码解决器"""
    
    def __init__(self, ui_manager: 'CaptchaUIManager'):
        self.ui_manager = ui_manager
        self.solver_strategies = {
            CaptchaType.IMAGE_TEXT: self._solve_image_text,
            CaptchaType.SLIDE_PUZZLE: self._solve_slide_puzzle,
            CaptchaType.CLICK_SEQUENCE: self._solve_click_sequence,
            CaptchaType.RECAPTCHA_V2: self._solve_recaptcha_v2,
            CaptchaType.GEETEST: self._solve_geetest,
        }
    
    async def solve_captcha(self, challenge: CaptchaChallenge) -> CaptchaSolution:
        """解决验证码"""
        solver_func = self.solver_strategies.get(challenge.captcha_type)
        if not solver_func:
            raise ValueError(f"不支持的验证码类型: {challenge.captcha_type}")
        
        return await solver_func(challenge)
    
    async def _solve_image_text(self, challenge: CaptchaChallenge) -> CaptchaSolution:
        """解决图片文字验证码"""
        # 1. 显示验证码界面
        ui_result = await self.ui_manager.show_image_captcha(challenge)
        
        # 2. 创建解决方案
        return CaptchaSolution(
            challenge_id=challenge.challenge_id,
            solution_type=CaptchaType.IMAGE_TEXT,
            solution_data={"text": ui_result.text_input},
            confidence=ui_result.confidence,
            solving_time=ui_result.solving_time,
            text_result=ui_result.text_input
        )
    
    async def _solve_slide_puzzle(self, challenge: CaptchaChallenge) -> CaptchaSolution:
        """解决滑块验证码"""
        ui_result = await self.ui_manager.show_slide_captcha(challenge)
        
        return CaptchaSolution(
            challenge_id=challenge.challenge_id,
            solution_type=CaptchaType.SLIDE_PUZZLE,
            solution_data={"slide_distance": ui_result.slide_distance},
            confidence=ui_result.confidence,
            solving_time=ui_result.solving_time,
            slide_distance=ui_result.slide_distance
        )
```

## 🖥️ 人机交互界面系统

### 3.1 界面架构

```python
class CaptchaUIManager:
    """验证码UI管理器"""
    
    def __init__(self):
        self.ui_framework = self._detect_ui_framework()
        self.window_manager = WindowManager()
        self.input_validators = InputValidators()
        
    async def show_image_captcha(self, challenge: CaptchaChallenge) -> UIResult:
        """显示图片验证码界面"""
        window = await self.window_manager.create_window(
            title="验证码识别",
            width=500,
            height=400,
            resizable=False
        )
        
        # 创建界面组件
        components = {
            'image_display': ImageDisplay(challenge.image_url),
            'text_input': TextInput(placeholder="请输入验证码"),
            'refresh_button': Button("刷新验证码", self._refresh_captcha),
            'submit_button': Button("提交", self._submit_solution),
            'history_dropdown': HistoryDropdown(self._get_input_history()),
            'timer_display': TimerDisplay(timeout=300)  # 5分钟超时
        }
        
        layout = self._create_layout(components)
        window.set_content(layout)
        
        # 显示窗口并等待结果
        result = await window.show_and_wait()
        return result
    
    async def show_slide_captcha(self, challenge: CaptchaChallenge) -> UIResult:
        """显示滑块验证码界面"""
        window = await self.window_manager.create_window(
            title="滑块验证",
            width=400,
            height=300
        )
        
        components = {
            'slide_puzzle': SlidePuzzle(challenge.image_url),
            'instruction_label': Label("请拖动滑块完成验证"),
            'reset_button': Button("重置", self._reset_slide),
            'submit_button': Button("提交", self._submit_slide)
        }
        
        layout = self._create_layout(components)
        window.set_content(layout)
        
        result = await window.show_and_wait()
        return result
    
    async def show_click_captcha(self, challenge: CaptchaChallenge) -> UIResult:
        """显示点击验证码界面"""
        window = await self.window_manager.create_window(
            title="点击验证",
            width=600,
            height=500
        )
        
        components = {
            'click_image': ClickableImage(challenge.image_url),
            'instruction_label': Label("请按顺序点击指定区域"),
            'click_points_display': ClickPointsDisplay(),
            'undo_button': Button("撤销", self._undo_click),
            'clear_button': Button("清空", self._clear_clicks),
            'submit_button': Button("提交", self._submit_clicks)
        }
        
        layout = self._create_layout(components)
        window.set_content(layout)
        
        result = await window.show_and_wait()
        return result

class UIComponent:
    """UI组件基类"""
    
    def __init__(self, name: str):
        self.name = name
        self.value = None
        self.validators = []
        self.event_handlers = {}
    
    def set_validator(self, validator: Callable[[Any], bool]):
        """设置验证器"""
        self.validators.append(validator)
    
    def validate(self) -> bool:
        """验证输入"""
        return all(validator(self.value) for validator in self.validators)
    
    def on_event(self, event: str, handler: Callable):
        """事件处理器"""
        self.event_handlers[event] = handler

class ImageDisplay(UIComponent):
    """图片显示组件"""
    
    def __init__(self, image_url: str):
        super().__init__("image_display")
        self.image_url = image_url
        self.image_data = None
        self.refresh_count = 0
    
    async def load_image(self):
        """加载图片"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.image_url) as response:
                    self.image_data = await response.read()
            return True
        except Exception as e:
            logger.error(f"加载图片失败: {e}")
            return False
    
    async def refresh(self):
        """刷新图片"""
        self.refresh_count += 1
        return await self.load_image()

class TextInput(UIComponent):
    """文本输入组件"""
    
    def __init__(self, placeholder: str = ""):
        super().__init__("text_input")
        self.placeholder = placeholder
        self.max_length = 20
        self.input_history = []
    
    def set_value(self, value: str):
        """设置值"""
        self.value = value.strip()
        if self.value and self.value not in self.input_history:
            self.input_history.append(self.value)
    
    def get_suggestions(self) -> List[str]:
        """获取输入建议"""
        if not self.value:
            return self.input_history[-5:]  # 最近5次输入
        
        return [h for h in self.input_history if h.startswith(self.value)]

class SlidePuzzle(UIComponent):
    """滑块拼图组件"""
    
    def __init__(self, image_url: str):
        super().__init__("slide_puzzle")
        self.image_url = image_url
        self.slide_distance = 0
        self.slide_track = []
        self.is_sliding = False
    
    def start_slide(self, x: int, y: int):
        """开始滑动"""
        self.is_sliding = True
        self.slide_track = [(x, y)]
    
    def update_slide(self, x: int, y: int):
        """更新滑动位置"""
        if self.is_sliding:
            self.slide_track.append((x, y))
            self.slide_distance = x - self.slide_track[0][0]
    
    def end_slide(self):
        """结束滑动"""
        self.is_sliding = False
        self.value = {
            "distance": self.slide_distance,
            "track": self.slide_track
        }
```

## 📋 任务队列状态管理系统

### 4.1 任务队列设计

```python
class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"             # 待处理
    RUNNING = "running"             # 运行中
    PAUSED = "paused"               # 暂停
    CAPTCHA_REQUIRED = "captcha_required"  # 需要验证码
    WAITING_USER = "waiting_user"   # 等待用户
    COMPLETED = "completed"         # 已完成
    FAILED = "failed"               # 失败
    CANCELLED = "cancelled"         # 已取消
    TIMEOUT = "timeout"             # 超时

@dataclass
class ScrapingTask:
    """爬虫任务"""
    task_id: str
    url: str
    task_type: str
    status: TaskStatus
    priority: int = 0
    retry_count: int = 0
    max_retries: int = 3
    
    # 时间信息
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # 任务数据
    params: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[str] = None
    
    # CAPTCHA相关
    captcha_challenge: Optional[CaptchaChallenge] = None
    captcha_solution: Optional[CaptchaSolution] = None
    
    # 统计信息
    processing_time: float = 0.0
    captcha_count: int = 0
    success_rate: float = 0.0

class TaskQueue:
    """任务队列管理器"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.tasks: Dict[str, ScrapingTask] = {}
        self.priority_queue = asyncio.PriorityQueue()
        self.running_tasks: Dict[str, ScrapingTask] = {}
        self.paused_tasks: Dict[str, ScrapingTask] = {}
        self.completed_tasks: Dict[str, ScrapingTask] = {}
        self.lock = asyncio.Lock()
        
        # 统计信息
        self.total_tasks = 0
        self.completed_tasks_count = 0
        self.failed_tasks_count = 0
        self.captcha_tasks_count = 0
    
    async def add_task(self, task: ScrapingTask) -> bool:
        """添加任务"""
        async with self.lock:
            if len(self.tasks) >= self.max_size:
                return False
            
            self.tasks[task.task_id] = task
            await self.priority_queue.put((-task.priority, task.task_id))
            self.total_tasks += 1
            
            logger.info(f"任务已添加: {task.task_id}")
            return True
    
    async def get_next_task(self) -> Optional[ScrapingTask]:
        """获取下一个任务"""
        try:
            priority, task_id = await self.priority_queue.get()
            
            async with self.lock:
                if task_id in self.tasks:
                    task = self.tasks[task_id]
                    task.status = TaskStatus.RUNNING
                    task.started_at = datetime.now()
                    self.running_tasks[task_id] = task
                    return task
                
        except asyncio.QueueEmpty:
            return None
    
    async def pause_task(self, task_id: str, reason: str = ""):
        """暂停任务"""
        async with self.lock:
            if task_id in self.running_tasks:
                task = self.running_tasks[task_id]
                task.status = TaskStatus.PAUSED
                task.paused_at = datetime.now()
                
                # 移动到暂停队列
                del self.running_tasks[task_id]
                self.paused_tasks[task_id] = task
                
                logger.info(f"任务已暂停: {task_id}, 原因: {reason}")
    
    async def resume_task(self, task_id: str):
        """恢复任务"""
        async with self.lock:
            if task_id in self.paused_tasks:
                task = self.paused_tasks[task_id]
                task.status = TaskStatus.RUNNING
                task.paused_at = None
                
                # 移动到运行队列
                del self.paused_tasks[task_id]
                self.running_tasks[task_id] = task
                
                logger.info(f"任务已恢复: {task_id}")
    
    async def complete_task(self, task_id: str, result: Any = None):
        """完成任务"""
        async with self.lock:
            if task_id in self.running_tasks:
                task = self.running_tasks[task_id]
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now()
                task.result = result
                task.processing_time = (task.completed_at - task.started_at).total_seconds()
                
                # 移动到完成队列
                del self.running_tasks[task_id]
                self.completed_tasks[task_id] = task
                self.completed_tasks_count += 1
                
                logger.info(f"任务已完成: {task_id}")
    
    async def handle_captcha_task(self, task_id: str, challenge: CaptchaChallenge):
        """处理验证码任务"""
        async with self.lock:
            if task_id in self.running_tasks:
                task = self.running_tasks[task_id]
                task.status = TaskStatus.CAPTCHA_REQUIRED
                task.captcha_challenge = challenge
                task.captcha_count += 1
                self.captcha_tasks_count += 1
                
                logger.info(f"任务需要验证码: {task_id}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_tasks": self.total_tasks,
            "running_tasks": len(self.running_tasks),
            "paused_tasks": len(self.paused_tasks),
            "completed_tasks": self.completed_tasks_count,
            "failed_tasks": self.failed_tasks_count,
            "captcha_tasks": self.captcha_tasks_count,
            "queue_size": self.priority_queue.qsize()
        }

class TaskManager:
    """任务管理器"""
    
    def __init__(self, captcha_detector: CaptchaDetector, 
                 captcha_solver: CaptchaSolver):
        self.task_queue = TaskQueue()
        self.captcha_detector = captcha_detector
        self.captcha_solver = captcha_solver
        self.worker_pool = []
        self.max_workers = 5
        self.running = False
    
    async def start(self):
        """启动任务管理器"""
        self.running = True
        
        # 创建工作线程池
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.worker_pool.append(worker)
        
        logger.info("任务管理器已启动")
    
    async def stop(self):
        """停止任务管理器"""
        self.running = False
        
        # 等待工作线程完成
        for worker in self.worker_pool:
            worker.cancel()
        
        await asyncio.gather(*self.worker_pool, return_exceptions=True)
        logger.info("任务管理器已停止")
    
    async def _worker(self, worker_id: str):
        """工作线程"""
        while self.running:
            try:
                task = await self.task_queue.get_next_task()
                if not task:
                    await asyncio.sleep(1)
                    continue
                
                logger.info(f"工作线程 {worker_id} 开始处理任务: {task.task_id}")
                
                # 执行任务
                await self._process_task(task)
                
            except Exception as e:
                logger.error(f"工作线程 {worker_id} 错误: {e}")
                await asyncio.sleep(1)
    
    async def _process_task(self, task: ScrapingTask):
        """处理任务"""
        try:
            # 模拟爬虫处理
            result = await self._scrape_url(task.url)
            
            # 检查是否需要验证码
            if self._needs_captcha(result):
                challenge = await self.captcha_detector.detect_captcha(result, None)
                if challenge:
                    await self._handle_captcha(task, challenge)
                    return
            
            # 完成任务
            await self.task_queue.complete_task(task.task_id, result)
            
        except Exception as e:
            logger.error(f"任务处理失败: {task.task_id}, 错误: {e}")
            await self.task_queue.fail_task(task.task_id, str(e))
    
    async def _handle_captcha(self, task: ScrapingTask, challenge: CaptchaChallenge):
        """处理验证码"""
        # 1. 暂停任务
        await self.task_queue.pause_task(task.task_id, "需要验证码")
        
        # 2. 标记为需要验证码
        await self.task_queue.handle_captcha_task(task.task_id, challenge)
        
        # 3. 解决验证码
        try:
            solution = await self.captcha_solver.solve_captcha(challenge)
            task.captcha_solution = solution
            
            # 4. 恢复任务
            await self.task_queue.resume_task(task.task_id)
            
        except Exception as e:
            logger.error(f"验证码处理失败: {e}")
            await self.task_queue.fail_task(task.task_id, f"验证码处理失败: {e}")
```

## 📊 统计数据收集和分析模块

### 5.1 统计数据设计

```python
@dataclass
class CaptchaStats:
    """验证码统计数据"""
    total_captcha_count: int = 0
    solved_captcha_count: int = 0
    failed_captcha_count: int = 0
    timeout_captcha_count: int = 0
    
    # 按类型统计
    type_stats: Dict[CaptchaType, Dict[str, int]] = field(default_factory=dict)
    
    # 时间统计
    average_solve_time: float = 0.0
    total_solve_time: float = 0.0
    
    # 成功率统计
    success_rate: float = 0.0
    
    # 用户行为统计
    refresh_count: int = 0
    retry_count: int = 0
    
    @property
    def success_rate_percentage(self) -> float:
        """成功率百分比"""
        if self.total_captcha_count == 0:
            return 0.0
        return (self.solved_captcha_count / self.total_captcha_count) * 100

class CaptchaAnalytics:
    """验证码分析器"""
    
    def __init__(self):
        self.stats = CaptchaStats()
        self.session_stats = {}
        self.historical_data = []
        self.lock = asyncio.Lock()
    
    async def record_captcha_event(self, event_type: str, captcha_type: CaptchaType, 
                                 metadata: Dict[str, Any] = None):
        """记录验证码事件"""
        async with self.lock:
            if event_type == "detected":
                self.stats.total_captcha_count += 1
                self._update_type_stats(captcha_type, "detected")
            
            elif event_type == "solved":
                self.stats.solved_captcha_count += 1
                self._update_type_stats(captcha_type, "solved")
                
                # 记录解决时间
                if metadata and "solve_time" in metadata:
                    solve_time = metadata["solve_time"]
                    self.stats.total_solve_time += solve_time
                    self.stats.average_solve_time = (
                        self.stats.total_solve_time / self.stats.solved_captcha_count
                    )
            
            elif event_type == "failed":
                self.stats.failed_captcha_count += 1
                self._update_type_stats(captcha_type, "failed")
            
            elif event_type == "timeout":
                self.stats.timeout_captcha_count += 1
                self._update_type_stats(captcha_type, "timeout")
            
            elif event_type == "refresh":
                self.stats.refresh_count += 1
            
            elif event_type == "retry":
                self.stats.retry_count += 1
            
            # 更新成功率
            self._update_success_rate()
    
    def _update_type_stats(self, captcha_type: CaptchaType, event: str):
        """更新类型统计"""
        if captcha_type not in self.stats.type_stats:
            self.stats.type_stats[captcha_type] = {
                "detected": 0,
                "solved": 0,
                "failed": 0,
                "timeout": 0
            }
        
        self.stats.type_stats[captcha_type][event] += 1
    
    def _update_success_rate(self):
        """更新成功率"""
        if self.stats.total_captcha_count > 0:
            self.stats.success_rate = (
                self.stats.solved_captcha_count / self.stats.total_captcha_count
            )
    
    def get_analytics_report(self) -> Dict[str, Any]:
        """获取分析报告"""
        return {
            "overall_stats": {
                "total_captcha": self.stats.total_captcha_count,
                "solved_captcha": self.stats.solved_captcha_count,
                "failed_captcha": self.stats.failed_captcha_count,
                "timeout_captcha": self.stats.timeout_captcha_count,
                "success_rate": f"{self.stats.success_rate_percentage:.2f}%",
                "average_solve_time": f"{self.stats.average_solve_time:.2f}s"
            },
            "type_breakdown": {
                captcha_type.value: {
                    "detected": stats.get("detected", 0),
                    "solved": stats.get("solved", 0),
                    "success_rate": f"{(stats.get('solved', 0) / max(stats.get('detected', 1), 1)) * 100:.2f}%"
                }
                for captcha_type, stats in self.stats.type_stats.items()
            },
            "user_behavior": {
                "refresh_count": self.stats.refresh_count,
                "retry_count": self.stats.retry_count,
                "average_refreshes_per_captcha": (
                    self.stats.refresh_count / max(self.stats.total_captcha_count, 1)
                )
            }
        }
```

## 🔄 验证码处理流程和恢复机制

### 6.1 处理流程设计

```python
class CaptchaWorkflow:
    """验证码处理工作流"""
    
    def __init__(self, task_manager: TaskManager, 
                 captcha_detector: CaptchaDetector,
                 captcha_solver: CaptchaSolver,
                 analytics: CaptchaAnalytics):
        self.task_manager = task_manager
        self.captcha_detector = captcha_detector
        self.captcha_solver = captcha_solver
        self.analytics = analytics
        self.retry_config = {
            "max_retries": 3,
            "retry_delay": 5.0,
            "timeout": 300  # 5分钟
        }
    
    async def process_captcha_workflow(self, task: ScrapingTask, 
                                     response_content: str,
                                     response: aiohttp.ClientResponse) -> bool:
        """处理验证码工作流"""
        try:
            # 1. 检测验证码
            challenge = await self.captcha_detector.detect_captcha(response_content, response)
            if not challenge:
                return True  # 没有验证码，继续处理
            
            # 2. 记录检测事件
            await self.analytics.record_captcha_event("detected", challenge.captcha_type)
            
            # 3. 暂停任务
            await self.task_manager.task_queue.pause_task(task.task_id, "检测到验证码")
            
            # 4. 设置超时
            timeout_task = asyncio.create_task(self._timeout_handler(task, challenge))
            
            # 5. 解决验证码
            solution = await self._solve_with_retry(challenge)
            
            # 6. 取消超时任务
            timeout_task.cancel()
            
            if solution:
                # 7. 应用解决方案
                success = await self._apply_solution(task, solution)
                
                if success:
                    # 8. 恢复任务
                    await self.task_manager.task_queue.resume_task(task.task_id)
                    await self.analytics.record_captcha_event("solved", challenge.captcha_type, {
                        "solve_time": solution.solving_time
                    })
                    return True
                else:
                    await self.analytics.record_captcha_event("failed", challenge.captcha_type)
                    return False
            else:
                await self.analytics.record_captcha_event("failed", challenge.captcha_type)
                return False
                
        except asyncio.TimeoutError:
            await self.analytics.record_captcha_event("timeout", challenge.captcha_type)
            return False
        except Exception as e:
            logger.error(f"验证码处理工作流错误: {e}")
            return False
    
    async def _solve_with_retry(self, challenge: CaptchaChallenge) -> Optional[CaptchaSolution]:
        """带重试的验证码解决"""
        for attempt in range(self.retry_config["max_retries"]):
            try:
                if attempt > 0:
                    await asyncio.sleep(self.retry_config["retry_delay"])
                    await self.analytics.record_captcha_event("retry", challenge.captcha_type)
                
                solution = await self.captcha_solver.solve_captcha(challenge)
                return solution
                
            except Exception as e:
                logger.warning(f"验证码解决失败 (尝试 {attempt + 1}): {e}")
                if attempt == self.retry_config["max_retries"] - 1:
                    raise
        
        return None
    
    async def _timeout_handler(self, task: ScrapingTask, challenge: CaptchaChallenge):
        """超时处理器"""
        await asyncio.sleep(self.retry_config["timeout"])
        
        # 超时后标记任务失败
        await self.task_manager.task_queue.fail_task(
            task.task_id, 
            f"验证码处理超时: {challenge.captcha_type}"
        )
        
        await self.analytics.record_captcha_event("timeout", challenge.captcha_type)
    
    async def _apply_solution(self, task: ScrapingTask, solution: CaptchaSolution) -> bool:
        """应用解决方案"""
        try:
            # 根据验证码类型应用不同的解决方案
            if solution.solution_type == CaptchaType.IMAGE_TEXT:
                return await self._apply_text_solution(task, solution)
            elif solution.solution_type == CaptchaType.SLIDE_PUZZLE:
                return await self._apply_slide_solution(task, solution)
            elif solution.solution_type == CaptchaType.CLICK_SEQUENCE:
                return await self._apply_click_solution(task, solution)
            else:
                logger.warning(f"未知的验证码类型: {solution.solution_type}")
                return False
                
        except Exception as e:
            logger.error(f"应用解决方案失败: {e}")
            return False
    
    async def _apply_text_solution(self, task: ScrapingTask, solution: CaptchaSolution) -> bool:
        """应用文字验证码解决方案"""
        # 实现文字验证码提交逻辑
        pass
    
    async def _apply_slide_solution(self, task: ScrapingTask, solution: CaptchaSolution) -> bool:
        """应用滑块验证码解决方案"""
        # 实现滑块验证码提交逻辑
        pass
    
    async def _apply_click_solution(self, task: ScrapingTask, solution: CaptchaSolution) -> bool:
        """应用点击验证码解决方案"""
        # 实现点击验证码提交逻辑
        pass
```

## 🎮 系统集成和配置

### 7.1 主控制器设计

```python
class CaptchaInteractionSystem:
    """验证码人机交互系统主控制器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # 初始化核心组件
        self.captcha_detector = CaptchaDetector()
        self.ui_manager = CaptchaUIManager()
        self.captcha_solver = CaptchaSolver(self.ui_manager)
        self.analytics = CaptchaAnalytics()
        self.task_manager = TaskManager(self.captcha_detector, self.captcha_solver)
        self.workflow = CaptchaWorkflow(
            self.task_manager, self.captcha_detector, 
            self.captcha_solver, self.analytics
        )
        
        # 集成现有组件
        self.session_manager = SessionManager()
        self.anti_bot_handler = AntiBotHandler()
        
        # 系统状态
        self.is_running = False
        self.stats = {}
    
    async def start(self):
        """启动系统"""
        try:
            # 1. 初始化组件
            await self.session_manager.initialize()
            await self.task_manager.start()
            
            # 2. 集成现有系统
            self._integrate_with_existing_system()
            
            # 3. 启动监控
            asyncio.create_task(self._monitoring_loop())
            
            self.is_running = True
            logger.info("验证码人机交互系统已启动")
            
        except Exception as e:
            logger.error(f"系统启动失败: {e}")
            raise
    
    async def stop(self):
        """停止系统"""
        try:
            self.is_running = False
            await self.task_manager.stop()
            await self.session_manager.close_all()
            
            logger.info("验证码人机交互系统已停止")
            
        except Exception as e:
            logger.error(f"系统停止失败: {e}")
    
    def _integrate_with_existing_system(self):
        """与现有系统集成"""
        # 替换现有的反爬虫处理器
        original_handle_block = self.anti_bot_handler.handle_block
        
        async def enhanced_handle_block(session, url, detection_result):
            """增强的反爬虫处理"""
            if detection_result.detection_type == BotDetectionType.CAPTCHA:
                # 使用新的验证码处理流程
                task = ScrapingTask(
                    task_id=f"captcha_{int(time.time())}",
                    url=url,
                    task_type="captcha_handling",
                    status=TaskStatus.CAPTCHA_REQUIRED
                )
                
                # 添加到任务队列
                await self.task_manager.task_queue.add_task(task)
                
                # 等待处理完成
                while task.status in [TaskStatus.CAPTCHA_REQUIRED, TaskStatus.WAITING_USER]:
                    await asyncio.sleep(1)
                
                if task.status == TaskStatus.COMPLETED:
                    return task.result
                else:
                    raise Exception(f"验证码处理失败: {task.error}")
            else:
                # 使用原始处理器
                return await original_handle_block(session, url, detection_result)
        
        self.anti_bot_handler.handle_block = enhanced_handle_block
    
    async def _monitoring_loop(self):
        """监控循环"""
        while self.is_running:
            try:
                # 更新统计信息
                self.stats = {
                    "task_queue": self.task_manager.task_queue.get_stats(),
                    "captcha_analytics": self.analytics.get_analytics_report(),
                    "session_manager": self.session_manager.get_stats()
                }
                
                # 检查异常情况
                await self._check_system_health()
                
                await asyncio.sleep(10)  # 10秒检查一次
                
            except Exception as e:
                logger.error(f"监控循环错误: {e}")
                await asyncio.sleep(10)
    
    async def _check_system_health(self):
        """检查系统健康状态"""
        # 检查任务队列是否过载
        queue_stats = self.task_manager.task_queue.get_stats()
        if queue_stats["running_tasks"] > 10:
            logger.warning("任务队列过载，考虑增加工作线程")
        
        # 检查验证码成功率
        analytics = self.analytics.get_analytics_report()
        success_rate = float(analytics["overall_stats"]["success_rate"].rstrip('%'))
        if success_rate < 70:
            logger.warning(f"验证码成功率较低: {success_rate}%")
        
        # 检查会话健康状态
        session_health = await self.session_manager.health_check()
        if not session_health.get("healthy", False):
            logger.warning("会话管理器健康状态异常")
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            "system_running": self.is_running,
            "stats": self.stats,
            "config": self.config
        }

# 配置示例
CAPTCHA_SYSTEM_CONFIG = {
    "ui": {
        "framework": "tkinter",  # tkinter, qt, web
        "theme": "light",
        "timeout": 300,
        "auto_refresh": True
    },
    "captcha": {
        "supported_types": [
            "image_text",
            "slide_puzzle", 
            "click_sequence",
            "recaptcha_v2"
        ],
        "detection_threshold": 0.8,
        "retry_count": 3,
        "timeout": 300
    },
    "task_queue": {
        "max_size": 1000,
        "max_workers": 5,
        "priority_enabled": True
    },
    "analytics": {
        "enable_detailed_logging": True,
        "retention_days": 30,
        "export_format": "json"
    }
}
```

## 🚀 部署和使用

### 8.1 快速开始

```python
# 使用示例
async def main():
    # 1. 创建系统配置
    config = CAPTCHA_SYSTEM_CONFIG.copy()
    
    # 2. 初始化系统
    captcha_system = CaptchaInteractionSystem(config)
    
    # 3. 启动系统
    await captcha_system.start()
    
    # 4. 添加爬虫任务
    task = ScrapingTask(
        task_id="test_task_001",
        url="https://jp.mercari.com/search?keyword=iPhone",
        task_type="search",
        status=TaskStatus.PENDING
    )
    
    await captcha_system.task_manager.task_queue.add_task(task)
    
    # 5. 监控系统状态
    while True:
        status = captcha_system.get_system_status()
        print(f"系统状态: {status}")
        await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())
```

### 8.2 与现有系统集成

```python
# 在现有的MercariScraper中集成
class EnhancedMercariScraper(MercariScraper):
    """增强版Mercari爬虫"""
    
    def __init__(self, captcha_system: CaptchaInteractionSystem):
        super().__init__()
        self.captcha_system = captcha_system
    
    async def scrape_page(self, url: str, **kwargs) -> MercariScrapingResult:
        """重写爬取页面方法"""
        # 创建任务
        task = ScrapingTask(
            task_id=f"scrape_{int(time.time())}",
            url=url,
            task_type="scrape_page",
            status=TaskStatus.PENDING,
            params=kwargs
        )
        
        # 添加到队列
        await self.captcha_system.task_manager.task_queue.add_task(task)
        
        # 等待完成
        while task.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            await asyncio.sleep(0.5)
        
        if task.status == TaskStatus.COMPLETED:
            return task.result
        else:
            raise Exception(f"任务失败: {task.error}")
```

## 📝 总结

该架构设计提供了一个完整的验证码人机交互系统，具有以下特点：

### ✅ 核心功能
1. **智能CAPTCHA检测** - 多层次检测算法
2. **直观用户界面** - 支持多种验证码类型
3. **任务队列管理** - 完善的状态跟踪
4. **无缝恢复机制** - 自动暂停和恢复
5. **统计分析系统** - 详细的性能监控

### 🎯 技术优势
- 模块化设计，易于扩展
- 异步处理，高性能
- 完善的错误处理
- 详细的日志记录
- 灵活的配置系统

### 🔧 可扩展性
- 支持新的验证码类型
- 可更换UI框架
- 可集成现有系统
- 支持分布式部署

该系统可以显著提高爬虫在遇到验证码时的处理效率，通过人机交互确保验证码的准确识别和处理。