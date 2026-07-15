"""
行为模拟优化引擎

该模块提供全面的人类行为模拟功能，用于绕过基于行为分析的反爬虫检测。
通过模拟真实用户的浏览、点击、滚动等行为模式，大幅提高反检测能力。

主要功能：
- 自然延迟模式生成
- 鼠标/键盘行为模拟
- 基于响应模式的自适应时间调整
- 人类行为模式学习与重现
- 请求频率智能控制
- 页面浏览行为模拟
- 反检测优化策略

技术特点：
- 基于真实用户行为数据的模拟
- 自适应行为调整算法
- 多维度行为特征融合
- 智能反检测策略

Author: Mercari AI Agent Team
"""

import asyncio
import logging
import random
import time
import math
from typing import Dict, List, Optional, Any, Tuple, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import numpy as np
from collections import deque, defaultdict
import json

from ..utils.logger import get_logger
from ..config.settings import settings

logger = get_logger(__name__)


class BehaviorType(Enum):
    """行为类型枚举"""
    NORMAL_BROWSING = "normal_browsing"
    SEARCH_BEHAVIOR = "search_behavior"
    SHOPPING_BEHAVIOR = "shopping_behavior"
    READING_BEHAVIOR = "reading_behavior"
    INTERACTION_BEHAVIOR = "interaction_behavior"
    IDLE_BEHAVIOR = "idle_behavior"


class MouseActionType(Enum):
    """鼠标动作类型"""
    MOVE = "move"
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    SCROLL = "scroll"
    HOVER = "hover"
    DRAG = "drag"


class KeyboardActionType(Enum):
    """键盘动作类型"""
    TYPE = "type"
    KEY_PRESS = "key_press"
    KEY_COMBINATION = "key_combination"
    BACKSPACE = "backspace"
    DELETE = "delete"
    ENTER = "enter"
    TAB = "tab"


@dataclass
class DelayPattern:
    """延迟模式数据结构"""
    min_delay: float
    max_delay: float
    mean_delay: float
    std_deviation: float
    distribution_type: str = "gaussian"
    
    def generate_delay(self) -> float:
        """生成符合模式的延迟"""
        if self.distribution_type == "gaussian":
            delay = np.random.normal(self.mean_delay, self.std_deviation)
        elif self.distribution_type == "exponential":
            delay = np.random.exponential(self.mean_delay)
        elif self.distribution_type == "uniform":
            delay = np.random.uniform(self.min_delay, self.max_delay)
        elif self.distribution_type == "beta":
            alpha, beta = 2.0, 3.0
            delay = np.random.beta(alpha, beta) * (self.max_delay - self.min_delay) + self.min_delay
        else:
            delay = np.random.uniform(self.min_delay, self.max_delay)
        
        return max(self.min_delay, min(self.max_delay, delay))


@dataclass
class MouseAction:
    """鼠标动作数据结构"""
    action_type: MouseActionType
    x: int
    y: int
    timestamp: datetime
    duration: float = 0.0
    velocity: float = 0.0
    acceleration: float = 0.0
    pressure: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'action_type': self.action_type.value,
            'x': self.x,
            'y': self.y,
            'timestamp': self.timestamp.isoformat(),
            'duration': self.duration,
            'velocity': self.velocity,
            'acceleration': self.acceleration,
            'pressure': self.pressure
        }


@dataclass
class KeyboardAction:
    """键盘动作数据结构"""
    action_type: KeyboardActionType
    key: str
    timestamp: datetime
    duration: float = 0.0
    typing_speed: float = 0.0
    rhythm_pattern: List[float] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'action_type': self.action_type.value,
            'key': self.key,
            'timestamp': self.timestamp.isoformat(),
            'duration': self.duration,
            'typing_speed': self.typing_speed,
            'rhythm_pattern': self.rhythm_pattern
        }


@dataclass
class BehaviorSession:
    """行为会话数据结构"""
    session_id: str
    behavior_type: BehaviorType
    start_time: datetime
    end_time: Optional[datetime] = None
    mouse_actions: List[MouseAction] = field(default_factory=list)
    keyboard_actions: List[KeyboardAction] = field(default_factory=list)
    page_views: List[str] = field(default_factory=list)
    scroll_patterns: List[Dict[str, Any]] = field(default_factory=list)
    interaction_intervals: List[float] = field(default_factory=list)
    
    def get_duration(self) -> float:
        """获取会话持续时间"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.now() - self.start_time).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'session_id': self.session_id,
            'behavior_type': self.behavior_type.value,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'mouse_actions': [action.to_dict() for action in self.mouse_actions],
            'keyboard_actions': [action.to_dict() for action in self.keyboard_actions],
            'page_views': self.page_views,
            'scroll_patterns': self.scroll_patterns,
            'interaction_intervals': self.interaction_intervals
        }


@dataclass
class BehaviorConfig:
    """行为配置"""
    enable_mouse_simulation: bool = True
    enable_keyboard_simulation: bool = True
    enable_scroll_simulation: bool = True
    enable_adaptive_timing: bool = True
    enable_behavior_learning: bool = True
    
    # 延迟配置
    base_delay_range: Tuple[float, float] = (0.1, 2.0)
    typing_speed_range: Tuple[float, float] = (40.0, 120.0)  # WPM
    mouse_move_speed_range: Tuple[float, float] = (100.0, 800.0)  # pixels/second
    scroll_speed_range: Tuple[float, float] = (200.0, 1000.0)  # pixels/second
    
    # 行为模式配置
    behavior_patterns: Dict[BehaviorType, Dict[str, Any]] = field(default_factory=lambda: {
        BehaviorType.NORMAL_BROWSING: {
            'page_dwell_time': DelayPattern(3.0, 60.0, 15.0, 8.0, 'gaussian'),
            'click_interval': DelayPattern(0.5, 5.0, 2.0, 1.0, 'exponential'),
            'scroll_frequency': 0.7,
            'mouse_movement_frequency': 0.8
        },
        BehaviorType.SEARCH_BEHAVIOR: {
            'page_dwell_time': DelayPattern(1.0, 30.0, 8.0, 5.0, 'exponential'),
            'click_interval': DelayPattern(0.3, 3.0, 1.5, 0.8, 'gaussian'),
            'scroll_frequency': 0.9,
            'mouse_movement_frequency': 0.6
        },
        BehaviorType.SHOPPING_BEHAVIOR: {
            'page_dwell_time': DelayPattern(5.0, 120.0, 30.0, 15.0, 'gaussian'),
            'click_interval': DelayPattern(1.0, 8.0, 3.0, 2.0, 'beta'),
            'scroll_frequency': 0.8,
            'mouse_movement_frequency': 0.9
        },
        BehaviorType.READING_BEHAVIOR: {
            'page_dwell_time': DelayPattern(10.0, 300.0, 60.0, 30.0, 'gaussian'),
            'click_interval': DelayPattern(2.0, 15.0, 5.0, 3.0, 'exponential'),
            'scroll_frequency': 0.95,
            'mouse_movement_frequency': 0.4
        },
        BehaviorType.INTERACTION_BEHAVIOR: {
            'page_dwell_time': DelayPattern(2.0, 45.0, 12.0, 6.0, 'beta'),
            'click_interval': DelayPattern(0.2, 2.0, 1.0, 0.5, 'gaussian'),
            'scroll_frequency': 0.5,
            'mouse_movement_frequency': 0.95
        },
        BehaviorType.IDLE_BEHAVIOR: {
            'page_dwell_time': DelayPattern(30.0, 600.0, 120.0, 60.0, 'exponential'),
            'click_interval': DelayPattern(10.0, 60.0, 30.0, 15.0, 'gaussian'),
            'scroll_frequency': 0.1,
            'mouse_movement_frequency': 0.2
        }
    })
    
    # 自适应配置
    adaptive_learning_rate: float = 0.1
    behavior_memory_size: int = 1000
    performance_threshold: float = 0.8
    
    # 反检测配置
    randomization_factor: float = 0.2
    humanization_level: float = 0.8
    detection_avoidance_level: float = 0.9


class HumanBehaviorPatterns:
    """人类行为模式库"""
    
    def __init__(self):
        self.typing_patterns = self._load_typing_patterns()
        self.mouse_patterns = self._load_mouse_patterns()
        self.scroll_patterns = self._load_scroll_patterns()
        self.interaction_patterns = self._load_interaction_patterns()
        
        logger.info("人类行为模式库初始化完成")
    
    def _load_typing_patterns(self) -> Dict[str, Any]:
        """加载打字模式"""
        return {
            'normal_typing': {
                'avg_wpm': 65,
                'std_wpm': 15,
                'key_intervals': {
                    'common_bigrams': {
                        'th': 0.08, 'he': 0.09, 'in': 0.10, 'er': 0.11, 're': 0.12,
                        'an': 0.09, 'nd': 0.13, 'on': 0.08, 'en': 0.10, 'at': 0.07
                    },
                    'difficult_combinations': {
                        'qu': 0.18, 'wr': 0.22, 'xz': 0.35, 'qw': 0.25, 'zx': 0.30
                    }
                },
                'rhythm_patterns': [0.12, 0.08, 0.15, 0.09, 0.11, 0.13, 0.10, 0.14],
                'pause_probability': 0.15,
                'backspace_probability': 0.05,
                'mistake_correction_delay': (0.5, 1.5)
            },
            'fast_typing': {
                'avg_wpm': 85,
                'std_wpm': 12,
                'key_intervals': {
                    'common_bigrams': {
                        'th': 0.06, 'he': 0.07, 'in': 0.08, 'er': 0.09, 're': 0.10,
                        'an': 0.07, 'nd': 0.11, 'on': 0.06, 'en': 0.08, 'at': 0.05
                    },
                    'difficult_combinations': {
                        'qu': 0.15, 'wr': 0.18, 'xz': 0.28, 'qw': 0.20, 'zx': 0.25
                    }
                },
                'rhythm_patterns': [0.08, 0.06, 0.10, 0.07, 0.09, 0.11, 0.08, 0.12],
                'pause_probability': 0.08,
                'backspace_probability': 0.08,
                'mistake_correction_delay': (0.3, 1.0)
            },
            'slow_typing': {
                'avg_wpm': 35,
                'std_wpm': 8,
                'key_intervals': {
                    'common_bigrams': {
                        'th': 0.15, 'he': 0.16, 'in': 0.18, 'er': 0.19, 're': 0.20,
                        'an': 0.16, 'nd': 0.22, 'on': 0.15, 'en': 0.17, 'at': 0.14
                    },
                    'difficult_combinations': {
                        'qu': 0.35, 'wr': 0.40, 'xz': 0.60, 'qw': 0.45, 'zx': 0.55
                    }
                },
                'rhythm_patterns': [0.20, 0.15, 0.25, 0.18, 0.22, 0.28, 0.17, 0.24],
                'pause_probability': 0.25,
                'backspace_probability': 0.03,
                'mistake_correction_delay': (1.0, 3.0)
            }
        }
    
    def _load_mouse_patterns(self) -> Dict[str, Any]:
        """加载鼠标模式"""
        return {
            'precise_movements': {
                'velocity_profile': 'smooth',
                'acceleration_factor': 0.8,
                'jitter_amplitude': 1.0,
                'overshoot_probability': 0.05,
                'correction_probability': 0.95
            },
            'casual_movements': {
                'velocity_profile': 'variable',
                'acceleration_factor': 1.2,
                'jitter_amplitude': 2.5,
                'overshoot_probability': 0.15,
                'correction_probability': 0.80
            },
            'gaming_movements': {
                'velocity_profile': 'fast',
                'acceleration_factor': 1.8,
                'jitter_amplitude': 0.5,
                'overshoot_probability': 0.02,
                'correction_probability': 0.98
            },
            'elderly_movements': {
                'velocity_profile': 'slow',
                'acceleration_factor': 0.4,
                'jitter_amplitude': 4.0,
                'overshoot_probability': 0.25,
                'correction_probability': 0.70
            }
        }
    
    def _load_scroll_patterns(self) -> Dict[str, Any]:
        """加载滚动模式"""
        return {
            'reading_scroll': {
                'scroll_amount': (80, 120),
                'scroll_interval': (0.5, 2.0),
                'acceleration_curve': 'linear',
                'pause_probability': 0.3,
                'reverse_probability': 0.05
            },
            'browsing_scroll': {
                'scroll_amount': (150, 300),
                'scroll_interval': (0.2, 1.0),
                'acceleration_curve': 'exponential',
                'pause_probability': 0.15,
                'reverse_probability': 0.10
            },
            'searching_scroll': {
                'scroll_amount': (200, 500),
                'scroll_interval': (0.1, 0.5),
                'acceleration_curve': 'variable',
                'pause_probability': 0.05,
                'reverse_probability': 0.20
            }
        }
    
    def _load_interaction_patterns(self) -> Dict[str, Any]:
        """加载交互模式"""
        return {
            'click_patterns': {
                'single_click': {
                    'duration': (0.05, 0.15),
                    'pressure_curve': 'normal',
                    'precision': 0.95
                },
                'double_click': {
                    'interval': (0.1, 0.3),
                    'consistency': 0.90,
                    'precision': 0.92
                },
                'hesitation_click': {
                    'pre_hover_duration': (0.5, 2.0),
                    'click_delay': (0.2, 0.8),
                    'precision': 0.85
                }
            },
            'hover_patterns': {
                'exploration_hover': {
                    'duration': (0.3, 1.5),
                    'movement_amplitude': 5.0,
                    'frequency': 0.8
                },
                'decision_hover': {
                    'duration': (1.0, 3.0),
                    'movement_amplitude': 2.0,
                    'frequency': 0.6
                },
                'accidental_hover': {
                    'duration': (0.1, 0.5),
                    'movement_amplitude': 10.0,
                    'frequency': 0.3
                }
            }
        }


class DelayEngine:
    """延迟引擎"""
    
    def __init__(self, config: BehaviorConfig):
        self.config = config
        self.historical_delays = deque(maxlen=config.behavior_memory_size)
        self.success_rates = defaultdict(float)
        self.current_behavior = BehaviorType.NORMAL_BROWSING
        
        logger.info("延迟引擎初始化完成")
    
    def generate_delay(self, 
                      action_type: str, 
                      context: Dict[str, Any] = None) -> float:
        """生成智能延迟"""
        context = context or {}
        
        # 获取基础延迟模式
        base_pattern = self._get_base_delay_pattern(action_type)
        
        # 生成基础延迟
        base_delay = base_pattern.generate_delay()
        
        # 应用自适应调整
        if self.config.enable_adaptive_timing:
            adaptive_factor = self._calculate_adaptive_factor(action_type, context)
            base_delay *= adaptive_factor
        
        # 应用随机化
        randomization = np.random.normal(1.0, self.config.randomization_factor)
        final_delay = base_delay * max(0.1, randomization)
        
        # 记录延迟历史
        self.historical_delays.append({
            'action_type': action_type,
            'delay': final_delay,
            'timestamp': datetime.now(),
            'context': context
        })
        
        return final_delay
    
    def _get_base_delay_pattern(self, action_type: str) -> DelayPattern:
        """获取基础延迟模式"""
        behavior_config = self.config.behavior_patterns.get(self.current_behavior)
        
        if action_type == 'page_dwell':
            return behavior_config['page_dwell_time']
        elif action_type == 'click_interval':
            return behavior_config['click_interval']
        elif action_type == 'typing':
            return DelayPattern(0.05, 0.5, 0.12, 0.08, 'gaussian')
        elif action_type == 'mouse_move':
            return DelayPattern(0.01, 0.3, 0.08, 0.05, 'exponential')
        elif action_type == 'scroll':
            return DelayPattern(0.1, 1.0, 0.3, 0.2, 'beta')
        else:
            return DelayPattern(0.1, 2.0, 0.5, 0.3, 'gaussian')
    
    def _calculate_adaptive_factor(self, action_type: str, context: Dict[str, Any]) -> float:
        """计算自适应因子"""
        base_factor = 1.0
        
        # 基于成功率调整
        success_rate = self.success_rates.get(action_type, 0.5)
        if success_rate < self.config.performance_threshold:
            base_factor *= (1.0 + (self.config.performance_threshold - success_rate))
        
        # 基于时间段调整
        current_hour = datetime.now().hour
        if 9 <= current_hour <= 17:  # 工作时间
            base_factor *= 0.8
        elif 22 <= current_hour or current_hour <= 6:  # 深夜
            base_factor *= 1.3
        
        # 基于系统负载调整
        system_load = context.get('system_load', 0.5)
        base_factor *= (1.0 + system_load * 0.2)
        
        # 基于网络延迟调整
        network_delay = context.get('network_delay', 0.1)
        base_factor *= (1.0 + network_delay * 0.5)
        
        return base_factor
    
    def update_success_rate(self, action_type: str, success: bool):
        """更新成功率"""
        current_rate = self.success_rates.get(action_type, 0.5)
        learning_rate = self.config.adaptive_learning_rate
        
        if success:
            self.success_rates[action_type] = current_rate + learning_rate * (1.0 - current_rate)
        else:
            self.success_rates[action_type] = current_rate * (1.0 - learning_rate)
    
    def set_behavior_context(self, behavior_type: BehaviorType):
        """设置行为上下文"""
        self.current_behavior = behavior_type
        logger.debug(f"行为上下文切换到: {behavior_type.value}")


class MouseSimulator:
    """鼠标模拟器"""
    
    def __init__(self, config: BehaviorConfig, patterns: HumanBehaviorPatterns):
        self.config = config
        self.patterns = patterns
        self.current_position = (0, 0)
        self.movement_history = deque(maxlen=100)
        
        logger.info("鼠标模拟器初始化完成")
    
    def generate_mouse_movement(self, 
                              target_x: int, 
                              target_y: int,
                              movement_style: str = 'casual_movements') -> List[MouseAction]:
        """生成鼠标移动轨迹"""
        start_x, start_y = self.current_position
        
        # 获取移动模式
        pattern = self.patterns.mouse_patterns.get(movement_style, 
                                                  self.patterns.mouse_patterns['casual_movements'])
        
        # 计算移动路径
        path_points = self._calculate_movement_path(start_x, start_y, target_x, target_y, pattern)
        
        # 生成移动动作序列
        actions = []
        for i, (x, y) in enumerate(path_points):
            # 计算时间戳
            timestamp = datetime.now() + timedelta(milliseconds=i * 10)
            
            # 计算速度和加速度
            velocity = self._calculate_velocity(i, path_points, pattern)
            acceleration = self._calculate_acceleration(i, path_points, pattern)
            
            action = MouseAction(
                action_type=MouseActionType.MOVE,
                x=x,
                y=y,
                timestamp=timestamp,
                velocity=velocity,
                acceleration=acceleration
            )
            actions.append(action)
        
        # 更新当前位置
        self.current_position = (target_x, target_y)
        
        # 记录移动历史
        self.movement_history.append({
            'start': (start_x, start_y),
            'end': (target_x, target_y),
            'style': movement_style,
            'timestamp': datetime.now()
        })
        
        return actions
    
    def _calculate_movement_path(self, start_x: int, start_y: int, 
                               target_x: int, target_y: int, 
                               pattern: Dict[str, Any]) -> List[Tuple[int, int]]:
        """计算移动路径"""
        distance = math.sqrt((target_x - start_x)**2 + (target_y - start_y)**2)
        
        if distance < 5:
            return [(target_x, target_y)]
        
        # 计算路径点数量
        num_points = max(5, int(distance / 10))
        
        # 生成基础路径
        path_points = []
        for i in range(num_points + 1):
            t = i / num_points
            
            # 使用贝塞尔曲线生成自然路径
            x = self._bezier_interpolation(start_x, target_x, t)
            y = self._bezier_interpolation(start_y, target_y, t)
            
            # 添加抖动
            jitter_x = np.random.normal(0, pattern['jitter_amplitude'])
            jitter_y = np.random.normal(0, pattern['jitter_amplitude'])
            
            x += jitter_x
            y += jitter_y
            
            path_points.append((int(x), int(y)))
        
        # 添加过冲和修正
        if random.random() < pattern['overshoot_probability']:
            path_points.extend(self._generate_overshoot_correction(target_x, target_y, pattern))
        
        return path_points
    
    def _bezier_interpolation(self, start: float, end: float, t: float) -> float:
        """贝塞尔曲线插值"""
        # 使用三次贝塞尔曲线
        control1 = start + (end - start) * 0.33
        control2 = start + (end - start) * 0.66
        
        return ((1-t)**3 * start + 
                3*(1-t)**2*t * control1 + 
                3*(1-t)*t**2 * control2 + 
                t**3 * end)
    
    def _generate_overshoot_correction(self, target_x: int, target_y: int, 
                                     pattern: Dict[str, Any]) -> List[Tuple[int, int]]:
        """生成过冲修正"""
        overshoot_distance = random.uniform(5, 15)
        angle = random.uniform(0, 2 * math.pi)
        
        overshoot_x = target_x + overshoot_distance * math.cos(angle)
        overshoot_y = target_y + overshoot_distance * math.sin(angle)
        
        correction_points = []
        for i in range(3):
            t = (i + 1) / 3
            x = overshoot_x + (target_x - overshoot_x) * t
            y = overshoot_y + (target_y - overshoot_y) * t
            correction_points.append((int(x), int(y)))
        
        return correction_points
    
    def _calculate_velocity(self, index: int, path_points: List[Tuple[int, int]], 
                          pattern: Dict[str, Any]) -> float:
        """计算移动速度"""
        if index == 0 or index >= len(path_points) - 1:
            return 0.0
        
        prev_point = path_points[index - 1]
        curr_point = path_points[index]
        
        distance = math.sqrt((curr_point[0] - prev_point[0])**2 + 
                           (curr_point[1] - prev_point[1])**2)
        
        # 基础速度（像素/10ms）
        base_velocity = distance
        
        # 根据模式调整
        velocity_factor = pattern['acceleration_factor']
        return base_velocity * velocity_factor
    
    def _calculate_acceleration(self, index: int, path_points: List[Tuple[int, int]], 
                              pattern: Dict[str, Any]) -> float:
        """计算加速度"""
        if index < 2 or index >= len(path_points) - 1:
            return 0.0
        
        prev_velocity = self._calculate_velocity(index - 1, path_points, pattern)
        curr_velocity = self._calculate_velocity(index, path_points, pattern)
        
        return curr_velocity - prev_velocity
    
    def generate_click_action(self, x: int, y: int, 
                            click_type: MouseActionType = MouseActionType.CLICK,
                            click_style: str = 'single_click') -> MouseAction:
        """生成点击动作"""
        pattern = self.patterns.interaction_patterns['click_patterns'].get(
            click_style, self.patterns.interaction_patterns['click_patterns']['single_click']
        )
        
        # 生成点击持续时间
        duration = np.random.uniform(*pattern['duration'])
        
        # 添加位置精度影响
        precision = pattern['precision']
        if random.random() > precision:
            x += random.randint(-3, 3)
            y += random.randint(-3, 3)
        
        return MouseAction(
            action_type=click_type,
            x=x,
            y=y,
            timestamp=datetime.now(),
            duration=duration,
            pressure=random.uniform(0.8, 1.2)
        )
    
    def generate_scroll_action(self, x: int, y: int, 
                             scroll_amount: int,
                             scroll_style: str = 'browsing_scroll') -> MouseAction:
        """生成滚动动作"""
        pattern = self.patterns.scroll_patterns.get(
            scroll_style, self.patterns.scroll_patterns['browsing_scroll']
        )
        
        # 调整滚动量
        amount_range = pattern['scroll_amount']
        actual_amount = random.randint(*amount_range)
        if scroll_amount < 0:
            actual_amount = -actual_amount
        
        return MouseAction(
            action_type=MouseActionType.SCROLL,
            x=x,
            y=y,
            timestamp=datetime.now(),
            velocity=actual_amount
        )


class KeyboardSimulator:
    """键盘模拟器"""
    
    def __init__(self, config: BehaviorConfig, patterns: HumanBehaviorPatterns):
        self.config = config
        self.patterns = patterns
        self.typing_history = deque(maxlen=100)
        self.current_typing_style = 'normal_typing'
        
        logger.info("键盘模拟器初始化完成")
    
    def generate_typing_sequence(self, text: str, 
                               typing_style: str = 'normal_typing') -> List[KeyboardAction]:
        """生成打字序列"""
        pattern = self.patterns.typing_patterns.get(typing_style, 
                                                   self.patterns.typing_patterns['normal_typing'])
        
        actions = []
        current_time = datetime.now()
        
        # 计算基础打字速度
        wpm = np.random.normal(pattern['avg_wpm'], pattern['std_wpm'])
        base_interval = 60.0 / (wpm * 5)  # 转换为秒/字符
        
        i = 0
        while i < len(text):
            char = text[i]
            
            # 计算字符间隔
            interval = self._calculate_char_interval(char, text, i, pattern, base_interval)
            
            current_time += timedelta(seconds=interval)
            
            # 生成打字动作
            action = KeyboardAction(
                action_type=KeyboardActionType.TYPE,
                key=char,
                timestamp=current_time,
                duration=random.uniform(0.05, 0.15),
                typing_speed=wpm
            )
            actions.append(action)
            
            # 处理错误和修正
            if random.random() < pattern['backspace_probability']:
                correction_actions = self._generate_mistake_correction(char, current_time, pattern)
                actions.extend(correction_actions)
                current_time = correction_actions[-1].timestamp
            
            # 处理停顿
            if random.random() < pattern['pause_probability']:
                pause_duration = random.uniform(0.5, 2.0)
                current_time += timedelta(seconds=pause_duration)
            
            i += 1
        
        # 记录打字历史
        self.typing_history.append({
            'text': text,
            'style': typing_style,
            'wpm': wpm,
            'timestamp': datetime.now()
        })
        
        return actions
    
    def _calculate_char_interval(self, char: str, text: str, index: int, 
                               pattern: Dict[str, Any], base_interval: float) -> float:
        """计算字符间隔"""
        interval = base_interval
        
        # 检查双字符组合
        if index > 0:
            bigram = text[index-1:index+1]
            if bigram in pattern['key_intervals']['common_bigrams']:
                interval *= pattern['key_intervals']['common_bigrams'][bigram]
            elif bigram in pattern['key_intervals']['difficult_combinations']:
                interval *= pattern['key_intervals']['difficult_combinations'][bigram]
        
        # 应用节奏模式
        rhythm_index = index % len(pattern['rhythm_patterns'])
        rhythm_factor = pattern['rhythm_patterns'][rhythm_index]
        interval *= rhythm_factor
        
        # 添加随机变化
        interval *= np.random.normal(1.0, 0.2)
        
        return max(0.02, interval)
    
    def _generate_mistake_correction(self, char: str, current_time: datetime, 
                                   pattern: Dict[str, Any]) -> List[KeyboardAction]:
        """生成错误修正序列"""
        actions = []
        
        # 打错字
        wrong_char = self._get_adjacent_key(char)
        actions.append(KeyboardAction(
            action_type=KeyboardActionType.TYPE,
            key=wrong_char,
            timestamp=current_time,
            duration=random.uniform(0.05, 0.15)
        ))
        
        # 发现错误的延迟
        delay = random.uniform(*pattern['mistake_correction_delay'])
        correction_time = current_time + timedelta(seconds=delay)
        
        # 退格
        actions.append(KeyboardAction(
            action_type=KeyboardActionType.BACKSPACE,
            key='Backspace',
            timestamp=correction_time,
            duration=random.uniform(0.05, 0.12)
        ))
        
        # 打正确字符
        actions.append(KeyboardAction(
            action_type=KeyboardActionType.TYPE,
            key=char,
            timestamp=correction_time + timedelta(seconds=0.1),
            duration=random.uniform(0.05, 0.15)
        ))
        
        return actions
    
    def _get_adjacent_key(self, char: str) -> str:
        """获取相邻按键"""
        # 简化的键盘布局映射
        keyboard_layout = {
            'q': ['w', 'a'], 'w': ['q', 'e', 's'], 'e': ['w', 'r', 'd'],
            'r': ['e', 't', 'f'], 't': ['r', 'y', 'g'], 'y': ['t', 'u', 'h'],
            'u': ['y', 'i', 'j'], 'i': ['u', 'o', 'k'], 'o': ['i', 'p', 'l'],
            'p': ['o', 'l'], 'a': ['q', 's', 'z'], 's': ['a', 'w', 'd', 'x'],
            'd': ['s', 'e', 'f', 'c'], 'f': ['d', 'r', 'g', 'v'], 'g': ['f', 't', 'h', 'b'],
            'h': ['g', 'y', 'j', 'n'], 'j': ['h', 'u', 'k', 'm'], 'k': ['j', 'i', 'l'],
            'l': ['k', 'o', 'p'], 'z': ['a', 'x'], 'x': ['z', 's', 'c'],
            'c': ['x', 'd', 'v'], 'v': ['c', 'f', 'b'], 'b': ['v', 'g', 'n'],
            'n': ['b', 'h', 'm'], 'm': ['n', 'j']
        }
        
        adjacent_keys = keyboard_layout.get(char.lower(), [char])
        return random.choice(adjacent_keys) if adjacent_keys else char


class BehaviorSimulationEngine:
    """行为模拟引擎主类"""
    
    def __init__(self, config: Optional[BehaviorConfig] = None):
        self.config = config or BehaviorConfig()
        self.patterns = HumanBehaviorPatterns()
        self.delay_engine = DelayEngine(self.config)
        self.mouse_simulator = MouseSimulator(self.config, self.patterns)
        self.keyboard_simulator = KeyboardSimulator(self.config, self.patterns)
        
        self.current_session: Optional[BehaviorSession] = None
        self.session_history: List[BehaviorSession] = []
        self.performance_metrics = defaultdict(list)
        
        logger.info("行为模拟引擎初始化完成")
    
    def start_behavior_session(self, behavior_type: BehaviorType, 
                             session_id: str = None) -> BehaviorSession:
        """开始行为会话"""
        if session_id is None:
            session_id = f"session_{int(time.time())}_{random.randint(1000, 9999)}"
        
        self.current_session = BehaviorSession(
            session_id=session_id,
            behavior_type=behavior_type,
            start_time=datetime.now()
        )
        
        # 设置行为上下文
        self.delay_engine.set_behavior_context(behavior_type)
        
        logger.info(f"开始行为会话: {session_id} ({behavior_type.value})")
        return self.current_session
    
    def end_behavior_session(self):
        """结束行为会话"""
        if self.current_session:
            self.current_session.end_time = datetime.now()
            self.session_history.append(self.current_session)
            
            logger.info(f"结束行为会话: {self.current_session.session_id}, "
                       f"持续时间: {self.current_session.get_duration():.2f}秒")
            
            self.current_session = None
    
    async def simulate_page_interaction(self, page_url: str, 
                                      interaction_type: str = 'browse') -> Dict[str, Any]:
        """模拟页面交互"""
        if not self.current_session:
            self.start_behavior_session(BehaviorType.NORMAL_BROWSING)
        
        # 记录页面访问
        self.current_session.page_views.append(page_url)
        
        # 生成页面停留时间
        dwell_delay = self.delay_engine.generate_delay('page_dwell', {
            'page_url': page_url,
            'interaction_type': interaction_type
        })
        
        # 模拟页面交互行为
        interactions = []
        
        if interaction_type == 'browse':
            interactions = await self._simulate_browsing_behavior(dwell_delay)
        elif interaction_type == 'search':
            interactions = await self._simulate_search_behavior(dwell_delay)
        elif interaction_type == 'shop':
            interactions = await self._simulate_shopping_behavior(dwell_delay)
        elif interaction_type == 'read':
            interactions = await self._simulate_reading_behavior(dwell_delay)
        
        # 记录交互间隔
        if interactions:
            intervals = []
            for i in range(1, len(interactions)):
                prev_time = interactions[i-1].get('timestamp', datetime.now())
                curr_time = interactions[i].get('timestamp', datetime.now())
                interval = (curr_time - prev_time).total_seconds()
                intervals.append(interval)
            
            self.current_session.interaction_intervals.extend(intervals)
        
        return {
            'page_url': page_url,
            'dwell_time': dwell_delay,
            'interactions': interactions,
            'interaction_count': len(interactions)
        }
    
    async def _simulate_browsing_behavior(self, dwell_time: float) -> List[Dict[str, Any]]:
        """模拟浏览行为"""
        interactions = []
        elapsed_time = 0.0
        
        while elapsed_time < dwell_time:
            # 随机选择交互类型
            interaction_types = ['scroll', 'mouse_move', 'click', 'hover']
            probabilities = [0.4, 0.3, 0.2, 0.1]
            interaction_type = np.random.choice(interaction_types, p=probabilities)
            
            if interaction_type == 'scroll':
                # 模拟滚动
                scroll_action = self.mouse_simulator.generate_scroll_action(
                    random.randint(100, 800), random.randint(100, 600),
                    random.randint(100, 500)
                )
                interactions.append({
                    'type': 'scroll',
                    'action': scroll_action,
                    'timestamp': datetime.now()
                })
                
                # 滚动后的停顿
                pause_delay = self.delay_engine.generate_delay('scroll')
                await asyncio.sleep(pause_delay)
                elapsed_time += pause_delay
            
            elif interaction_type == 'mouse_move':
                # 模拟鼠标移动
                target_x = random.randint(50, 950)
                target_y = random.randint(50, 650)
                
                move_actions = self.mouse_simulator.generate_mouse_movement(
                    target_x, target_y, 'casual_movements'
                )
                
                interactions.append({
                    'type': 'mouse_move',
                    'actions': move_actions,
                    'timestamp': datetime.now()
                })
                
                # 移动后的停顿
                pause_delay = self.delay_engine.generate_delay('mouse_move')
                await asyncio.sleep(pause_delay)
                elapsed_time += pause_delay
            
            elif interaction_type == 'click':
                # 模拟点击
                click_x = random.randint(100, 800)
                click_y = random.randint(100, 600)
                
                click_action = self.mouse_simulator.generate_click_action(
                    click_x, click_y, MouseActionType.CLICK
                )
                
                interactions.append({
                    'type': 'click',
                    'action': click_action,
                    'timestamp': datetime.now()
                })
                
                # 点击后的停顿
                pause_delay = self.delay_engine.generate_delay('click_interval')
                await asyncio.sleep(pause_delay)
                elapsed_time += pause_delay
            
            elif interaction_type == 'hover':
                # 模拟悬停
                hover_x = random.randint(100, 800)
                hover_y = random.randint(100, 600)
                
                hover_action = MouseAction(
                    action_type=MouseActionType.HOVER,
                    x=hover_x,
                    y=hover_y,
                    timestamp=datetime.now(),
                    duration=random.uniform(0.5, 2.0)
                )
                
                interactions.append({
                    'type': 'hover',
                    'action': hover_action,
                    'timestamp': datetime.now()
                })
                
                # 悬停持续时间
                pause_delay = hover_action.duration
                await asyncio.sleep(pause_delay)
                elapsed_time += pause_delay
            
            # 随机添加空闲时间
            if random.random() < 0.2:
                idle_delay = random.uniform(0.5, 3.0)
                await asyncio.sleep(idle_delay)
                elapsed_time += idle_delay
        
        return interactions
    
    async def _simulate_search_behavior(self, dwell_time: float) -> List[Dict[str, Any]]:
        """模拟搜索行为"""
        interactions = []
        elapsed_time = 0.0
        
        # 模拟搜索输入
        search_query = "mercari search query"
        typing_actions = self.keyboard_simulator.generate_typing_sequence(
            search_query, 'normal_typing'
        )
        
        interactions.append({
            'type': 'typing',
            'actions': typing_actions,
            'text': search_query,
            'timestamp': datetime.now()
        })
        
        # 计算打字时间
        typing_duration = sum(action.duration for action in typing_actions)
        await asyncio.sleep(typing_duration)
        elapsed_time += typing_duration
        
        # 模拟搜索结果浏览
        remaining_time = dwell_time - elapsed_time
        if remaining_time > 0:
            browse_interactions = await self._simulate_browsing_behavior(remaining_time)
            interactions.extend(browse_interactions)
        
        return interactions
    
    async def _simulate_shopping_behavior(self, dwell_time: float) -> List[Dict[str, Any]]:
        """模拟购物行为"""
        interactions = []
        elapsed_time = 0.0
        
        # 购物行为模式：更多的点击和详细查看
        while elapsed_time < dwell_time:
            interaction_types = ['click', 'scroll', 'hover', 'zoom']
            probabilities = [0.4, 0.3, 0.2, 0.1]
            interaction_type = np.random.choice(interaction_types, p=probabilities)
            
            if interaction_type == 'click':
                # 模拟产品点击
                click_action = self.mouse_simulator.generate_click_action(
                    random.randint(200, 700), random.randint(200, 500),
                    MouseActionType.CLICK, 'hesitation_click'
                )
                
                interactions.append({
                    'type': 'product_click',
                    'action': click_action,
                    'timestamp': datetime.now()
                })
                
                # 点击后的详细查看时间
                pause_delay = self.delay_engine.generate_delay('click_interval', {
                    'behavior_type': 'shopping'
                })
                await asyncio.sleep(pause_delay)
                elapsed_time += pause_delay
            
            elif interaction_type == 'scroll':
                # 模拟产品列表滚动
                scroll_action = self.mouse_simulator.generate_scroll_action(
                    random.randint(100, 800), random.randint(100, 600),
                    random.randint(150, 400), 'searching_scroll'
                )
                
                interactions.append({
                    'type': 'product_scroll',
                    'action': scroll_action,
                    'timestamp': datetime.now()
                })
                
                pause_delay = self.delay_engine.generate_delay('scroll')
                await asyncio.sleep(pause_delay)
                elapsed_time += pause_delay
            
            elif interaction_type == 'hover':
                # 模拟产品悬停查看
                hover_action = MouseAction(
                    action_type=MouseActionType.HOVER,
                    x=random.randint(150, 750),
                    y=random.randint(150, 550),
                    timestamp=datetime.now(),
                    duration=random.uniform(1.0, 3.0)
                )
                
                interactions.append({
                    'type': 'product_hover',
                    'action': hover_action,
                    'timestamp': datetime.now()
                })
                
                await asyncio.sleep(hover_action.duration)
                elapsed_time += hover_action.duration
            
            # 购物行为中的较长停顿
            if random.random() < 0.3:
                thinking_delay = random.uniform(2.0, 8.0)
                await asyncio.sleep(thinking_delay)
                elapsed_time += thinking_delay
        
        return interactions
    
    async def _simulate_reading_behavior(self, dwell_time: float) -> List[Dict[str, Any]]:
        """模拟阅读行为"""
        interactions = []
        elapsed_time = 0.0
        
        # 阅读行为模式：主要是滚动，偶尔点击
        while elapsed_time < dwell_time:
            interaction_types = ['scroll', 'pause', 'highlight', 'back_scroll']
            probabilities = [0.6, 0.2, 0.1, 0.1]
            interaction_type = np.random.choice(interaction_types, p=probabilities)
            
            if interaction_type == 'scroll':
                # 模拟阅读滚动
                scroll_action = self.mouse_simulator.generate_scroll_action(
                    random.randint(100, 800), random.randint(100, 600),
                    random.randint(80, 150), 'reading_scroll'
                )
                
                interactions.append({
                    'type': 'reading_scroll',
                    'action': scroll_action,
                    'timestamp': datetime.now()
                })
                
                # 阅读停顿
                reading_pause = random.uniform(1.0, 4.0)
                await asyncio.sleep(reading_pause)
                elapsed_time += reading_pause
            
            elif interaction_type == 'pause':
                # 模拟阅读停顿
                pause_duration = random.uniform(3.0, 10.0)
                interactions.append({
                    'type': 'reading_pause',
                    'duration': pause_duration,
                    'timestamp': datetime.now()
                })
                
                await asyncio.sleep(pause_duration)
                elapsed_time += pause_duration
            
            elif interaction_type == 'highlight':
                # 模拟文本选择/高亮
                start_action = self.mouse_simulator.generate_click_action(
                    random.randint(100, 700), random.randint(200, 500),
                    MouseActionType.CLICK
                )
                
                end_action = self.mouse_simulator.generate_click_action(
                    start_action.x + random.randint(50, 200),
                    start_action.y + random.randint(-20, 20),
                    MouseActionType.CLICK
                )
                
                interactions.append({
                    'type': 'text_highlight',
                    'start_action': start_action,
                    'end_action': end_action,
                    'timestamp': datetime.now()
                })
                
                highlight_delay = random.uniform(0.5, 2.0)
                await asyncio.sleep(highlight_delay)
                elapsed_time += highlight_delay
            
            elif interaction_type == 'back_scroll':
                # 模拟向上滚动（重新阅读）
                back_scroll_action = self.mouse_simulator.generate_scroll_action(
                    random.randint(100, 800), random.randint(100, 600),
                    -random.randint(50, 150), 'reading_scroll'
                )
                
                interactions.append({
                    'type': 'back_scroll',
                    'action': back_scroll_action,
                    'timestamp': datetime.now()
                })
                
                pause_delay = random.uniform(1.0, 3.0)
                await asyncio.sleep(pause_delay)
                elapsed_time += pause_delay
        
        return interactions
    
    def update_performance_metrics(self, action_type: str, success: bool, 
                                 response_time: float = None):
        """更新性能指标"""
        self.performance_metrics[action_type].append({
            'success': success,
            'response_time': response_time,
            'timestamp': datetime.now()
        })
        
        # 更新延迟引擎的成功率
        self.delay_engine.update_success_rate(action_type, success)
        
        # 清理旧数据
        cutoff_time = datetime.now() - timedelta(hours=1)
        for metrics in self.performance_metrics.values():
            while metrics and metrics[0]['timestamp'] < cutoff_time:
                metrics.pop(0)
    
    def get_behavior_statistics(self) -> Dict[str, Any]:
        """获取行为统计信息"""
        stats = {
            'total_sessions': len(self.session_history),
            'current_session': self.current_session.session_id if self.current_session else None,
            'behavior_distribution': defaultdict(int),
            'average_session_duration': 0.0,
            'total_interactions': 0,
            'performance_metrics': {}
        }
        
        # 计算行为分布和平均持续时间
        total_duration = 0.0
        for session in self.session_history:
            stats['behavior_distribution'][session.behavior_type.value] += 1
            duration = session.get_duration()
            total_duration += duration
            stats['total_interactions'] += len(session.mouse_actions) + len(session.keyboard_actions)
        
        if self.session_history:
            stats['average_session_duration'] = total_duration / len(self.session_history)
        
        # 计算性能指标
        for action_type, metrics in self.performance_metrics.items():
            if metrics:
                success_rate = sum(1 for m in metrics if m['success']) / len(metrics)
                avg_response_time = sum(m['response_time'] for m in metrics if m['response_time']) / len(metrics)
                
                stats['performance_metrics'][action_type] = {
                    'success_rate': success_rate,
                    'average_response_time': avg_response_time,
                    'total_actions': len(metrics)
                }
        
        return stats
    
    def export_session_data(self, session_id: str = None) -> str:
        """导出会话数据"""
        if session_id:
            session = next((s for s in self.session_history if s.session_id == session_id), None)
            if session:
                return json.dumps(session.to_dict(), indent=2, ensure_ascii=False)
            else:
                return json.dumps({"error": "Session not found"}, indent=2)
        else:
            # 导出所有会话
            all_sessions = [session.to_dict() for session in self.session_history]
            return json.dumps(all_sessions, indent=2, ensure_ascii=False)
    
    def optimize_behavior_parameters(self):
        """优化行为参数"""
        # 基于性能指标调整行为参数
        for action_type, metrics in self.performance_metrics.items():
            if metrics:
                recent_metrics = [m for m in metrics if 
                                (datetime.now() - m['timestamp']).total_seconds() < 3600]
                
                if recent_metrics:
                    success_rate = sum(1 for m in recent_metrics if m['success']) / len(recent_metrics)
                    
                    if success_rate < self.config.performance_threshold:
                        # 性能不佳，调整参数
                        if action_type in ['click_interval', 'page_dwell']:
                            # 增加延迟
                            pattern = self.delay_engine._get_base_delay_pattern(action_type)
                            pattern.mean_delay *= 1.2
                            pattern.std_deviation *= 1.1
                            
                            logger.info(f"调整 {action_type} 延迟参数: mean={pattern.mean_delay:.2f}")
                        
                        elif action_type == 'mouse_move':
                            # 降低移动速度
                            speed_range = list(self.config.mouse_move_speed_range)
                            speed_range[0] *= 0.8
                            speed_range[1] *= 0.8
                            self.config.mouse_move_speed_range = tuple(speed_range)
                            
                            logger.info(f"调整鼠标移动速度: {self.config.mouse_move_speed_range}")
                    
                    elif success_rate > 0.95:
                        # 性能过好，可能看起来太机械，增加一些随机性
                        self.config.randomization_factor = min(0.5, self.config.randomization_factor * 1.1)
                        logger.info(f"增加随机化因子: {self.config.randomization_factor:.2f}")


# 工厂函数
def create_behavior_simulation_engine(config: Optional[BehaviorConfig] = None) -> BehaviorSimulationEngine:
    """创建行为模拟引擎实例"""
    return BehaviorSimulationEngine(config)


# 便捷函数
def create_browsing_engine() -> BehaviorSimulationEngine:
    """创建浏览行为引擎"""
    config = BehaviorConfig()
    config.behavior_patterns[BehaviorType.NORMAL_BROWSING]['scroll_frequency'] = 0.8
    config.behavior_patterns[BehaviorType.NORMAL_BROWSING]['mouse_movement_frequency'] = 0.9
    return BehaviorSimulationEngine(config)


def create_shopping_engine() -> BehaviorSimulationEngine:
    """创建购物行为引擎"""
    config = BehaviorConfig()
    config.behavior_patterns[BehaviorType.SHOPPING_BEHAVIOR]['click_interval'].mean_delay = 4.0
    config.behavior_patterns[BehaviorType.SHOPPING_BEHAVIOR]['page_dwell_time'].mean_delay = 40.0
    return BehaviorSimulationEngine(config)


if __name__ == "__main__":
    # 测试代码
    async def test_behavior_simulation():
        """测试行为模拟引擎"""
        engine = create_behavior_simulation_engine()
        
        # 测试浏览行为
        session = engine.start_behavior_session(BehaviorType.NORMAL_BROWSING)
        
        # 模拟页面交互
        result = await engine.simulate_page_interaction(
            "https://mercari.com/search?query=test",
            "browse"
        )
        
        print(f"页面交互结果: {result['interaction_count']} 个交互")
        print(f"停留时间: {result['dwell_time']:.2f} 秒")
        
        # 测试搜索行为
        engine.delay_engine.set_behavior_context(BehaviorType.SEARCH_BEHAVIOR)
        search_result = await engine.simulate_page_interaction(
            "https://mercari.com/search",
            "search"
        )
        
        print(f"搜索交互结果: {search_result['interaction_count']} 个交互")
        
        # 结束会话
        engine.end_behavior_session()
        
        # 获取统计信息
        stats = engine.get_behavior_statistics()
        print(f"行为统计: {stats}")
        
        # 导出会话数据
        session_data = engine.export_session_data()
        print(f"会话数据长度: {len(session_data)} 字符")
    
    # 运行测试
    asyncio.run(test_behavior_simulation())