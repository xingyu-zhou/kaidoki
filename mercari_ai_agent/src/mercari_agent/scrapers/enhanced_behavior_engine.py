"""
增强行为引擎 - 简化但有效的反检测优化

基于现有behavior_simulation_engine.py的分析，提供核心的行为模式改进：
1. 改进鼠标轨迹生成 - 更自然的贝塞尔曲线
2. 智能延迟策略 - 基于页面内容的动态等待
3. 自然交互行为 - 真实的滚动和悬停模式
4. Mercari网站专门优化

重点：简单、实用、有效
"""

import asyncio
import logging
import random
import time
import math
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import deque

from .behavior_simulation_engine import (
    BehaviorSimulationEngine, BehaviorType, MouseActionType, 
    MouseAction, DelayPattern, BehaviorConfig
)
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SimpleUserProfile:
    """简化的用户画像"""
    mouse_speed: float = 400.0        # 鼠标移动速度
    click_precision: float = 0.92     # 点击精度
    typing_speed: float = 65.0        # 打字速度(WPM)
    patience_level: float = 0.8       # 耐心程度
    jitter_level: float = 1.5         # 抖动程度


class EnhancedMouseTrajectory:
    """增强的鼠标轨迹生成器"""
    
    def __init__(self, profile: SimpleUserProfile):
        self.profile = profile
        self.current_pos = (0, 0)
    
    def generate_natural_path(self, start_x: int, start_y: int, 
                            end_x: int, end_y: int) -> List[Tuple[int, int]]:
        """生成自然的鼠标移动路径"""
        distance = math.sqrt((end_x - start_x)**2 + (end_y - start_y)**2)
        
        if distance < 5:
            return [(end_x, end_y)]
        
        # 计算路径点数
        num_points = max(8, int(distance / 10))
        points = []
        
        # 生成控制点用于贝塞尔曲线
        mid_x = (start_x + end_x) / 2
        mid_y = (start_y + end_y) / 2
        
        # 添加自然弯曲
        curve_offset = random.uniform(-30, 30)
        if distance > 50:
            control_x = mid_x + curve_offset
            control_y = mid_y + curve_offset * random.uniform(-0.5, 0.5)
        else:
            control_x = mid_x
            control_y = mid_y
        
        # 生成贝塞尔曲线路径
        for i in range(num_points + 1):
            t = i / num_points
            
            # 三次贝塞尔曲线
            x = (1-t)**2 * start_x + 2*(1-t)*t * control_x + t**2 * end_x
            y = (1-t)**2 * start_y + 2*(1-t)*t * control_y + t**2 * end_y
            
            # 添加微小抖动
            jitter_x = random.gauss(0, self.profile.jitter_level)
            jitter_y = random.gauss(0, self.profile.jitter_level)
            
            x += jitter_x
            y += jitter_y
            
            points.append((int(x), int(y)))
        
        # 随机添加过冲修正（10%概率）
        if random.random() < 0.1 and distance > 20:
            overshoot_x = end_x + random.randint(-8, 8)
            overshoot_y = end_y + random.randint(-8, 8)
            points.append((overshoot_x, overshoot_y))
            points.append((end_x + random.randint(-2, 2), end_y + random.randint(-2, 2)))
        
        self.current_pos = (end_x, end_y)
        return points


class SmartDelayCalculator:
    """智能延迟计算器"""
    
    def __init__(self, profile: SimpleUserProfile):
        self.profile = profile
        self.page_complexity = 0.5  # 默认页面复杂度
        self.fatigue_factor = 1.0   # 疲劳因子
        self.last_action_time = time.time()
    
    def calculate_delay(self, action_type: str, context: Dict[str, Any] = None) -> float:
        """计算智能延迟"""
        context = context or {}
        
        # 基础延迟映射
        base_delays = {
            'page_dwell': 3.0,
            'click_interval': 1.5,
            'scroll_pause': 0.8,
            'typing_interval': 0.12,
            'mouse_move': 0.05,
            'hover_explore': 1.2,
            'read_content': 2.0,
            'decision_making': 2.5
        }
        
        base_delay = base_delays.get(action_type, 1.0)
        
        # 页面复杂度调整
        complexity_factor = 1.0 + (self.page_complexity - 0.5) * 0.8
        
        # 耐心程度调整
        patience_factor = 2.0 - self.profile.patience_level
        
        # 疲劳调整
        fatigue_adjustment = self.fatigue_factor
        
        # 时间间隔调整（防止过于规律）
        time_since_last = time.time() - self.last_action_time
        if time_since_last < 0.5:
            interval_factor = 1.3  # 连续操作时增加延迟
        else:
            interval_factor = 1.0
        
        # 最终延迟计算
        final_delay = (base_delay * 
                      complexity_factor * 
                      patience_factor * 
                      fatigue_adjustment * 
                      interval_factor)
        
        # 添加自然随机性 (±20%)
        final_delay *= random.uniform(0.8, 1.2)
        
        # 确保最小延迟
        final_delay = max(0.1, final_delay)
        
        self.last_action_time = time.time()
        return final_delay
    
    def update_page_complexity(self, url: str, element_count: int = 50):
        """更新页面复杂度"""
        # 简单的复杂度评估
        if 'search' in url:
            self.page_complexity = 0.3  # 搜索页面相对简单
        elif 'item' in url or 'product' in url:
            self.page_complexity = 0.7  # 商品页面较复杂
        else:
            self.page_complexity = min(1.0, element_count / 100)


class NaturalScrollSimulator:
    """自然滚动模拟器"""
    
    def __init__(self, profile: SimpleUserProfile):
        self.profile = profile
        self.scroll_momentum = 0.0  # 滚动惯性
    
    def generate_scroll_sequence(self, total_distance: int, 
                               scroll_type: str = 'reading') -> List[Dict[str, Any]]:
        """生成自然的滚动序列"""
        
        if total_distance <= 0:
            return []
        
        scroll_events = []
        remaining_distance = abs(total_distance)
        direction = 1 if total_distance > 0 else -1
        
        # 滚动模式参数
        scroll_patterns = {
            'reading': {'chunk_size': (80, 120), 'pause_prob': 0.4},
            'browsing': {'chunk_size': (150, 300), 'pause_prob': 0.2},
            'searching': {'chunk_size': (200, 400), 'pause_prob': 0.1}
        }
        
        pattern = scroll_patterns.get(scroll_type, scroll_patterns['reading'])
        
        while remaining_distance > 10:
            # 计算本次滚动距离
            chunk_min, chunk_max = pattern['chunk_size']
            scroll_distance = min(remaining_distance, 
                                random.randint(chunk_min, chunk_max))
            
            scroll_events.append({
                'type': 'scroll',
                'distance': scroll_distance * direction,
                'duration': random.uniform(0.1, 0.3)
            })
            
            remaining_distance -= scroll_distance
            
            # 随机添加停顿
            if random.random() < pattern['pause_prob']:
                pause_duration = random.uniform(0.5, 2.0)
                scroll_events.append({
                    'type': 'pause',
                    'duration': pause_duration
                })
            
            # 偶尔反向滚动（重新查看）
            if random.random() < 0.05:
                back_distance = random.randint(20, 60)
                scroll_events.append({
                    'type': 'scroll',
                    'distance': -back_distance * direction,
                    'duration': random.uniform(0.2, 0.4)
                })
        
        return scroll_events


class MercariSpecificOptimizer:
    """Mercari网站专门优化器"""
    
    def __init__(self):
        self.mercari_patterns = {
            'search_page': {
                'scan_time': (2.0, 4.0),        # 搜索结果扫描时间
                'scroll_pattern': 'browsing',    # 浏览式滚动
                'click_hesitation': 0.8          # 点击前犹豫时间
            },
            'item_page': {
                'view_time': (5.0, 12.0),       # 商品查看时间
                'image_focus_time': (1.5, 3.0), # 图片查看时间
                'price_check_time': (1.0, 2.0)  # 价格检查时间
            },
            'category_page': {
                'browse_time': (3.0, 8.0),      # 分类浏览时间
                'scroll_pattern': 'searching'    # 搜索式滚动
            }
        }
    
    def get_page_behavior(self, url: str) -> Dict[str, Any]:
        """根据页面URL获取行为模式"""
        if '/search' in url:
            return self.mercari_patterns['search_page']
        elif '/item/' in url:
            return self.mercari_patterns['item_page']
        elif '/category/' in url:
            return self.mercari_patterns['category_page']
        else:
            return {'scan_time': (1.0, 3.0), 'scroll_pattern': 'reading'}
    
    def calculate_mercari_delay(self, page_type: str, action_type: str) -> float:
        """计算Mercari特定的延迟"""
        base_delays = {
            'search_page': {
                'item_click': 2.0,
                'filter_click': 1.5,
                'scroll': 0.8
            },
            'item_page': {
                'image_view': 2.5,
                'description_read': 4.0,
                'price_check': 1.5
            }
        }
        
        page_delays = base_delays.get(page_type, {})
        return page_delays.get(action_type, 1.0) * random.uniform(0.8, 1.2)


class EnhancedBehaviorEngine:
    """增强行为引擎主类"""
    
    def __init__(self, user_profile: SimpleUserProfile = None):
        self.profile = user_profile or SimpleUserProfile()
        self.mouse_trajectory = EnhancedMouseTrajectory(self.profile)
        self.delay_calculator = SmartDelayCalculator(self.profile)
        self.scroll_simulator = NaturalScrollSimulator(self.profile)
        self.mercari_optimizer = MercariSpecificOptimizer()
        
        # 集成原有的行为引擎
        self.base_engine = BehaviorSimulationEngine()
        
        logger.info("增强行为引擎初始化完成")
    
    async def enhanced_page_interaction(self, url: str, 
                                      interaction_type: str = 'browse') -> Dict[str, Any]:
        """增强的页面交互模拟"""
        
        # 更新页面复杂度
        self.delay_calculator.update_page_complexity(url)
        
        # 获取Mercari特定行为模式
        mercari_behavior = self.mercari_optimizer.get_page_behavior(url)
        
        # 开始行为会话
        session = self.base_engine.start_behavior_session(
            BehaviorType.NORMAL_BROWSING if interaction_type == 'browse' 
            else BehaviorType.SEARCH_BEHAVIOR
        )
        
        interactions = []
        
        # 页面加载等待
        load_delay = self.delay_calculator.calculate_delay('page_dwell')
        await asyncio.sleep(load_delay)
        
        # 模拟页面扫描
        scan_time = random.uniform(*mercari_behavior.get('scan_time', (1.0, 3.0)))
        await asyncio.sleep(scan_time)
        
        # 生成交互序列
        if interaction_type == 'browse':
            interactions = await self._simulate_enhanced_browsing(mercari_behavior)
        elif interaction_type == 'search':
            interactions = await self._simulate_enhanced_search(mercari_behavior)
        
        self.base_engine.end_behavior_session()
        
        return {
            'url': url,
            'interaction_type': interaction_type,
            'interactions': interactions,
            'total_time': sum(i.get('duration', 0) for i in interactions)
        }
    
    async def _simulate_enhanced_browsing(self, behavior_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """模拟增强的浏览行为"""
        interactions = []
        
        # 自然滚动
        scroll_events = self.scroll_simulator.generate_scroll_sequence(
            random.randint(500, 1500), 
            behavior_config.get('scroll_pattern', 'browsing')
        )
        
        for event in scroll_events:
            if event['type'] == 'scroll':
                interactions.append({
                    'type': 'scroll',
                    'distance': event['distance'],
                    'timestamp': datetime.now()
                })
                
                await asyncio.sleep(event.get('duration', 0.2))
                
            elif event['type'] == 'pause':
                interactions.append({
                    'type': 'pause',
                    'duration': event['duration'],
                    'timestamp': datetime.now()
                })
                
                await asyncio.sleep(event['duration'])
        
        # 随机点击或悬停
        if random.random() < 0.7:
            # 模拟商品点击
            hesitation_time = behavior_config.get('click_hesitation', 0.5)
            await asyncio.sleep(hesitation_time)
            
            # 生成自然鼠标轨迹
            mouse_path = self.mouse_trajectory.generate_natural_path(
                random.randint(100, 400), random.randint(200, 400),
                random.randint(200, 600), random.randint(300, 500)
            )
            
            interactions.append({
                'type': 'mouse_movement',
                'path': mouse_path,
                'timestamp': datetime.now()
            })
        
        return interactions
    
    async def _simulate_enhanced_search(self, behavior_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """模拟增强的搜索行为"""
        interactions = []
        
        # 搜索输入模拟
        typing_delay = self.delay_calculator.calculate_delay('typing_interval')
        search_text = "メルカリ 商品検索"
        
        for char in search_text:
            interactions.append({
                'type': 'typing',
                'character': char,
                'timestamp': datetime.now()
            })
            
            await asyncio.sleep(typing_delay * random.uniform(0.8, 1.2))
        
        # 搜索结果等待
        search_delay = self.delay_calculator.calculate_delay('decision_making')
        await asyncio.sleep(search_delay)
        
        # 结果浏览
        browse_interactions = await self._simulate_enhanced_browsing(behavior_config)
        interactions.extend(browse_interactions)
        
        return interactions
    
    def generate_enhanced_mouse_movement(self, start_x: int, start_y: int,
                                       end_x: int, end_y: int) -> List[MouseAction]:
        """生成增强的鼠标移动动作"""
        path = self.mouse_trajectory.generate_natural_path(start_x, start_y, end_x, end_y)
        
        actions = []
        base_time = time.time()
        
        for i, (x, y) in enumerate(path):
            # 计算移动时间间隔
            interval = self.delay_calculator.calculate_delay('mouse_move')
            timestamp = datetime.fromtimestamp(base_time + i * interval)
            
            action = MouseAction(
                action_type=MouseActionType.MOVE,
                x=x,
                y=y,
                timestamp=timestamp,
                velocity=random.uniform(100, 400),
                acceleration=random.uniform(-50, 50)
            )
            
            actions.append(action)
        
        return actions


# 便捷函数
def create_enhanced_behavior_engine(speed_factor: float = 1.0) -> EnhancedBehaviorEngine:
    """创建增强行为引擎"""
    profile = SimpleUserProfile(
        mouse_speed=400.0 * speed_factor,
        click_precision=0.92,
        typing_speed=65.0 * speed_factor,
        patience_level=0.8,
        jitter_level=1.5 / speed_factor
    )
    
    return EnhancedBehaviorEngine(profile)


def create_mercari_optimized_engine() -> EnhancedBehaviorEngine:
    """创建Mercari优化的行为引擎"""
    profile = SimpleUserProfile(
        mouse_speed=350.0,     # 稍慢的鼠标速度
        click_precision=0.90,  # 普通精度
        typing_speed=55.0,     # 日文输入较慢
        patience_level=0.9,    # 购物时较有耐心
        jitter_level=2.0       # 适中的抖动
    )
    
    return EnhancedBehaviorEngine(profile)


# 集成函数
def integrate_with_session_manager(session_manager, behavior_engine: EnhancedBehaviorEngine):
    """与会话管理器集成"""
    
    original_request = session_manager.request
    
    async def enhanced_request(*args, **kwargs):
        """增强的请求方法"""
        # 在请求前添加智能延迟
        delay = behavior_engine.delay_calculator.calculate_delay('click_interval')
        await asyncio.sleep(delay)
        
        # 执行原始请求
        response = await original_request(*args, **kwargs)
        
        # 请求后的行为模拟
        if hasattr(session_manager, 'current_url'):
            await behavior_engine.enhanced_page_interaction(
                session_manager.current_url, 'browse'
            )
        
        return response
    
    session_manager.request = enhanced_request
    return session_manager


if __name__ == "__main__":
    async def test_enhanced_behavior():
        """测试增强行为引擎"""
        engine = create_mercari_optimized_engine()
        
        # 测试页面交互
        result = await engine.enhanced_page_interaction(
            "https://mercari.com/search?q=test",
            "search"
        )
        
        print(f"交互结果: {len(result['interactions'])} 个交互")
        print(f"总时间: {result['total_time']:.2f} 秒")
    
    asyncio.run(test_enhanced_behavior())