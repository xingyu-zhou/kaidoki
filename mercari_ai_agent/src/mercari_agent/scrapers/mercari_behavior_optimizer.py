"""
Mercari网站行为优化器

针对Mercari网站的特定行为模式和反检测策略：
1. Mercari特有的页面交互模式
2. 日本用户行为习惯模拟
3. 购物网站特定的浏览模式
4. CAPTCHA触发避免策略

专门针对jp.mercari.com的优化
"""

import asyncio
import logging
import random
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from .enhanced_behavior_engine import EnhancedBehaviorEngine, SimpleUserProfile
from .progressive_loading_strategy import MercariPageLoadingOptimizer
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MercariUserBehavior:
    """Mercari用户行为模式"""
    # 搜索行为
    search_patience: float = 0.85      # 搜索时的耐心程度
    filter_usage_rate: float = 0.6     # 过滤器使用率
    
    # 商品浏览行为
    image_view_duration: float = 3.0   # 图片查看时间
    description_read_rate: float = 0.8 # 描述阅读率
    price_comparison_time: float = 2.0 # 价格比较时间
    
    # 购物车行为
    add_to_cart_hesitation: float = 2.5  # 加购物车犹豫时间
    checkout_preparation: float = 5.0    # 结账准备时间
    
    # 日本用户特征
    politeness_factor: float = 1.2     # 礼貌因子（更慢更仔细）
    mobile_preference: float = 0.7     # 移动优先偏好


class MercariSpecificPatterns:
    """Mercari特定模式库"""
    
    @staticmethod
    def get_search_patterns() -> Dict[str, Any]:
        """获取搜索模式"""
        return {
            'keyword_input_delay': (0.3, 0.8),      # 关键词输入延迟
            'filter_click_delay': (1.0, 2.5),       # 过滤器点击延迟
            'result_scan_time': (2.0, 5.0),         # 结果扫描时间
            'item_hover_time': (0.8, 2.0),          # 商品悬停时间
            'pagination_delay': (1.5, 3.0)          # 翻页延迟
        }
    
    @staticmethod
    def get_product_patterns() -> Dict[str, Any]:
        """获取商品页面模式"""
        return {
            'image_carousel_time': (1.5, 4.0),      # 图片轮播查看时间
            'description_scroll_time': (3.0, 8.0),   # 描述滚动时间
            'seller_info_check': (1.0, 2.5),        # 卖家信息检查时间
            'similar_items_browse': (2.0, 6.0),     # 相似商品浏览时间
            'purchase_decision_time': (5.0, 15.0)   # 购买决策时间
        }
    
    @staticmethod
    def get_category_patterns() -> Dict[str, Any]:
        """获取分类页面模式"""
        return {
            'subcategory_explore': (1.0, 3.0),      # 子分类探索时间
            'sort_option_delay': (0.8, 2.0),        # 排序选项延迟
            'grid_view_scan': (2.0, 5.0),          # 网格视图扫描
            'infinite_scroll_pause': (1.5, 4.0)     # 无限滚动停顿
        }


class MercariBehaviorOptimizer:
    """Mercari行为优化器"""
    
    def __init__(self):
        # 创建日本用户画像
        self.user_profile = SimpleUserProfile(
            mouse_speed=320.0,        # 日本用户通常较慢
            click_precision=0.90,     # 较为精确
            typing_speed=45.0,        # 日文输入较慢
            patience_level=0.85,      # 日本用户较有耐心
            jitter_level=1.8          # 适中抖动
        )
        
        self.behavior_engine = EnhancedBehaviorEngine(self.user_profile)
        self.loading_optimizer = MercariPageLoadingOptimizer()
        self.user_behavior = MercariUserBehavior()
        
        # CAPTCHA避免策略
        self.request_count = 0
        self.last_request_time = time.time()
        self.suspicious_action_count = 0
        
        logger.info("Mercari行为优化器初始化完成")
    
    async def optimized_search_behavior(self, search_query: str, 
                                      url: str) -> Dict[str, Any]:
        """优化的搜索行为"""
        patterns = MercariSpecificPatterns.get_search_patterns()
        interactions = []
        
        # 1. 页面加载等待
        load_result = await self.loading_optimizer.optimized_page_load(None, url)
        interactions.append({
            'type': 'page_load',
            'duration': load_result['total_time'],
            'timestamp': datetime.now()
        })
        
        # 2. 搜索框定位和输入
        search_delay = random.uniform(*patterns['keyword_input_delay'])
        await asyncio.sleep(search_delay)
        
        # 模拟日文输入（更慢）
        for char in search_query:
            char_delay = self._calculate_japanese_input_delay(char)
            await asyncio.sleep(char_delay)
            
            interactions.append({
                'type': 'typing',
                'character': char,
                'delay': char_delay,
                'timestamp': datetime.now()
            })
        
        # 3. 搜索结果等待和扫描
        result_scan_time = random.uniform(*patterns['result_scan_time'])
        await asyncio.sleep(result_scan_time)
        
        interactions.append({
            'type': 'result_scan',
            'duration': result_scan_time,
            'timestamp': datetime.now()
        })
        
        # 4. 过滤器使用（根据使用率）
        if random.random() < self.user_behavior.filter_usage_rate:
            filter_delay = random.uniform(*patterns['filter_click_delay'])
            await asyncio.sleep(filter_delay)
            
            interactions.append({
                'type': 'filter_interaction',
                'duration': filter_delay,
                'timestamp': datetime.now()
            })
        
        # 5. 商品项目悬停浏览
        item_count = random.randint(3, 8)  # 浏览3-8个商品
        for i in range(item_count):
            hover_time = random.uniform(*patterns['item_hover_time'])
            await asyncio.sleep(hover_time)
            
            interactions.append({
                'type': 'item_hover',
                'item_index': i,
                'duration': hover_time,
                'timestamp': datetime.now()
            })
        
        return {
            'behavior_type': 'mercari_search',
            'search_query': search_query,
            'interactions': interactions,
            'total_time': sum(i.get('duration', 0) for i in interactions)
        }
    
    async def optimized_product_behavior(self, product_url: str) -> Dict[str, Any]:
        """优化的商品页面行为"""
        patterns = MercariSpecificPatterns.get_product_patterns()
        interactions = []
        
        # 1. 页面加载
        load_result = await self.loading_optimizer.optimized_page_load(None, product_url)
        interactions.append({
            'type': 'page_load',
            'duration': load_result['total_time'],
            'timestamp': datetime.now()
        })
        
        # 2. 图片查看行为
        image_time = random.uniform(*patterns['image_carousel_time'])
        image_time *= self.user_behavior.politeness_factor  # 日本用户更仔细
        await asyncio.sleep(image_time)
        
        interactions.append({
            'type': 'image_viewing',
            'duration': image_time,
            'timestamp': datetime.now()
        })
        
        # 3. 商品描述阅读
        if random.random() < self.user_behavior.description_read_rate:
            desc_time = random.uniform(*patterns['description_scroll_time'])
            await asyncio.sleep(desc_time)
            
            interactions.append({
                'type': 'description_reading',
                'duration': desc_time,
                'timestamp': datetime.now()
            })
        
        # 4. 卖家信息检查
        seller_check_time = random.uniform(*patterns['seller_info_check'])
        await asyncio.sleep(seller_check_time)
        
        interactions.append({
            'type': 'seller_info_check',
            'duration': seller_check_time,
            'timestamp': datetime.now()
        })
        
        # 5. 相似商品浏览
        if random.random() < 0.6:  # 60%的概率浏览相似商品
            similar_time = random.uniform(*patterns['similar_items_browse'])
            await asyncio.sleep(similar_time)
            
            interactions.append({
                'type': 'similar_items_browse',
                'duration': similar_time,
                'timestamp': datetime.now()
            })
        
        # 6. 购买决策时间
        decision_time = random.uniform(*patterns['purchase_decision_time'])
        decision_time *= self.user_behavior.politeness_factor
        await asyncio.sleep(decision_time)
        
        interactions.append({
            'type': 'purchase_decision',
            'duration': decision_time,
            'timestamp': datetime.now()
        })
        
        return {
            'behavior_type': 'mercari_product_view',
            'product_url': product_url,
            'interactions': interactions,
            'total_time': sum(i.get('duration', 0) for i in interactions)
        }
    
    def _calculate_japanese_input_delay(self, char: str) -> float:
        """计算日文输入延迟"""
        base_delay = 0.15  # 基础延迟
        
        # 日文字符需要更长时间
        if ord(char) > 127:  # 非ASCII字符（包括日文）
            base_delay *= 1.8
        
        # 添加输入法切换延迟
        if hasattr(self, '_last_char_type'):
            current_is_japanese = ord(char) > 127
            if current_is_japanese != self._last_char_type:
                base_delay += random.uniform(0.2, 0.5)  # 输入法切换延迟
        
        self._last_char_type = ord(char) > 127
        
        return base_delay * random.uniform(0.8, 1.2)
    
    async def anti_captcha_delay_strategy(self, action_type: str) -> float:
        """防CAPTCHA延迟策略"""
        self.request_count += 1
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        # 基础延迟
        base_delay = 2.0
        
        # 请求频率控制
        if time_since_last < 3.0:
            # 请求太频繁，增加延迟
            frequency_penalty = (3.0 - time_since_last) * 2
            base_delay += frequency_penalty
            self.suspicious_action_count += 1
        else:
            # 重置可疑行为计数
            self.suspicious_action_count = max(0, self.suspicious_action_count - 1)
        
        # 累积可疑行为惩罚
        if self.suspicious_action_count > 5:
            base_delay *= (1.0 + self.suspicious_action_count * 0.1)
        
        # 时间段调整
        hour = datetime.now().hour
        if 9 <= hour <= 17:  # 工作时间，降低延迟
            base_delay *= 0.8
        elif 22 <= hour or hour <= 6:  # 深夜，增加延迟
            base_delay *= 1.3
        
        # 添加随机性
        final_delay = base_delay * random.uniform(0.8, 1.2)
        
        self.last_request_time = current_time
        
        logger.debug(f"防CAPTCHA延迟: {final_delay:.2f}秒 (动作: {action_type})")
        
        await asyncio.sleep(final_delay)
        return final_delay
    
    def get_mercari_headers(self) -> Dict[str, str]:
        """获取Mercari专用请求头"""
        return {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        }
    
    def should_use_mobile_simulation(self) -> bool:
        """判断是否应该使用移动端模拟"""
        return random.random() < self.user_behavior.mobile_preference


def create_mercari_optimizer() -> MercariBehaviorOptimizer:
    """创建Mercari优化器"""
    return MercariBehaviorOptimizer()


# 快速集成函数
def integrate_mercari_optimizer(session_manager) -> MercariBehaviorOptimizer:
    """快速集成Mercari优化器到会话管理器"""
    optimizer = create_mercari_optimizer()
    
    # 保存原始方法
    original_request = getattr(session_manager, 'request', None)
    
    async def optimized_request(method: str, url: str, **kwargs):
        """优化的请求方法"""
        # 添加Mercari专用头部
        headers = kwargs.get('headers', {})
        headers.update(optimizer.get_mercari_headers())
        kwargs['headers'] = headers
        
        # 执行防CAPTCHA延迟
        await optimizer.anti_captcha_delay_strategy(method.lower())
        
        # 执行原始请求
        if original_request:
            return await original_request(method, url, **kwargs)
        else:
            # 如果没有原始方法，返回模拟响应
            logger.warning("没有找到原始request方法，返回模拟响应")
            return None
    
    # 替换请求方法
    if hasattr(session_manager, 'request'):
        session_manager.request = optimized_request
    
    # 添加Mercari特定方法
    session_manager.mercari_search = optimizer.optimized_search_behavior
    session_manager.mercari_product_view = optimizer.optimized_product_behavior
    
    return optimizer


if __name__ == "__main__":
    async def test_mercari_optimizer():
        """测试Mercari优化器"""
        optimizer = create_mercari_optimizer()
        
        # 测试搜索行为
        search_result = await optimizer.optimized_search_behavior(
            "iPhone ケース", 
            "https://jp.mercari.com/search?q=iPhone"
        )
        
        print(f"搜索行为测试:")
        print(f"总时间: {search_result['total_time']:.2f}秒")
        print(f"交互数: {len(search_result['interactions'])}")
        
        # 测试商品页面行为
        product_result = await optimizer.optimized_product_behavior(
            "https://jp.mercari.com/item/m12345"
        )
        
        print(f"\n商品页面行为测试:")
        print(f"总时间: {product_result['total_time']:.2f}秒")
        print(f"交互数: {len(product_result['interactions'])}")
    
    asyncio.run(test_mercari_optimizer())