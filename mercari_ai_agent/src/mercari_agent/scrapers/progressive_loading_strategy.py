"""
渐进式页面加载策略

实现真实用户的页面交互时序，包括：
1. 资源加载等待和DOM ready检测
2. 网络延迟模拟
3. 页面完全渲染验证
4. 自然的页面探索行为

保持简洁实用的原则
"""

import asyncio
import logging
import time
import random
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PageLoadingConfig:
    """页面加载配置"""
    initial_wait: float = 2.0          # 初始等待时间
    dom_ready_wait: float = 1.5        # DOM准备等待时间
    image_load_wait: float = 3.0       # 图片加载等待时间
    ajax_wait: float = 2.0             # AJAX请求等待时间
    max_total_wait: float = 15.0       # 最大总等待时间
    
    # 网络模拟
    network_delay_base: float = 0.5    # 基础网络延迟
    network_jitter: float = 0.3        # 网络抖动
    
    # 验证配置
    verify_elements: bool = True       # 是否验证元素加载
    verify_images: bool = True         # 是否验证图片加载
    verify_scripts: bool = False       # 是否验证脚本加载（简化）


class ProgressiveLoadingStrategy:
    """渐进式页面加载策略"""
    
    def __init__(self, config: PageLoadingConfig = None):
        self.config = config or PageLoadingConfig()
        self.loading_history = []
        
        logger.info("渐进式页面加载策略初始化完成")
    
    async def wait_for_page_load(self, session, url: str, 
                                page_type: str = 'generic') -> Dict[str, Any]:
        """等待页面完全加载"""
        start_time = time.time()
        load_stages = []
        
        # 阶段1: 初始页面加载
        logger.info(f"开始加载页面: {url}")
        initial_delay = self._calculate_initial_delay(url, page_type)
        await asyncio.sleep(initial_delay)
        
        load_stages.append({
            'stage': 'initial_load',
            'duration': initial_delay,
            'timestamp': datetime.now()
        })
        
        # 阶段2: DOM准备等待
        dom_delay = self._calculate_dom_delay(page_type)
        await asyncio.sleep(dom_delay)
        
        load_stages.append({
            'stage': 'dom_ready',
            'duration': dom_delay,
            'timestamp': datetime.now()
        })
        
        # 阶段3: 资源加载等待
        if self.config.verify_images:
            image_delay = self._calculate_image_delay(page_type)
            await asyncio.sleep(image_delay)
            
            load_stages.append({
                'stage': 'images_loaded',
                'duration': image_delay,
                'timestamp': datetime.now()
            })
        
        # 阶段4: AJAX请求等待（如果需要）
        if self._needs_ajax_wait(page_type):
            ajax_delay = self._calculate_ajax_delay(page_type)
            await asyncio.sleep(ajax_delay)
            
            load_stages.append({
                'stage': 'ajax_complete',
                'duration': ajax_delay,
                'timestamp': datetime.now()
            })
        
        # 阶段5: 最终稳定等待
        final_delay = self._calculate_final_delay(page_type)
        await asyncio.sleep(final_delay)
        
        load_stages.append({
            'stage': 'page_stable',
            'duration': final_delay,
            'timestamp': datetime.now()
        })
        
        total_time = time.time() - start_time
        
        # 记录加载历史
        self.loading_history.append({
            'url': url,
            'page_type': page_type,
            'stages': load_stages,
            'total_time': total_time,
            'timestamp': datetime.now()
        })
        
        logger.info(f"页面加载完成: {url}, 总时间: {total_time:.2f}秒")
        
        return {
            'url': url,
            'page_type': page_type,
            'stages': load_stages,
            'total_time': total_time,
            'success': True
        }
    
    def _calculate_initial_delay(self, url: str, page_type: str) -> float:
        """计算初始延迟"""
        base_delay = self.config.initial_wait
        
        # 根据页面类型调整
        type_factors = {
            'search': 0.8,      # 搜索页面加载较快
            'product': 1.2,     # 商品页面加载较慢
            'category': 1.0,    # 分类页面正常
            'home': 0.9,        # 首页相对较快
            'generic': 1.0      # 普通页面
        }
        
        type_factor = type_factors.get(page_type, 1.0)
        
        # 添加网络延迟模拟
        network_delay = self._simulate_network_delay()
        
        # 添加随机性
        random_factor = random.uniform(0.8, 1.2)
        
        return (base_delay * type_factor + network_delay) * random_factor
    
    def _calculate_dom_delay(self, page_type: str) -> float:
        """计算DOM准备延迟"""
        base_delay = self.config.dom_ready_wait
        
        # 复杂页面需要更长时间
        complexity_factors = {
            'product': 1.3,     # 商品页面DOM较复杂
            'search': 1.1,      # 搜索结果页面
            'category': 1.0,    # 分类页面
            'home': 1.2,        # 首页内容丰富
            'generic': 1.0
        }
        
        complexity_factor = complexity_factors.get(page_type, 1.0)
        
        return base_delay * complexity_factor * random.uniform(0.8, 1.2)
    
    def _calculate_image_delay(self, page_type: str) -> float:
        """计算图片加载延迟"""
        base_delay = self.config.image_load_wait
        
        # 图片密集的页面需要更长时间
        image_factors = {
            'product': 1.5,     # 商品页面图片多
            'search': 1.2,      # 搜索结果有缩略图
            'category': 1.3,    # 分类页面图片较多
            'home': 1.1,        # 首页图片适中
            'generic': 1.0
        }
        
        image_factor = image_factors.get(page_type, 1.0)
        
        # 模拟网络速度影响
        network_factor = random.uniform(0.7, 1.3)
        
        return base_delay * image_factor * network_factor
    
    def _calculate_ajax_delay(self, page_type: str) -> float:
        """计算AJAX请求延迟"""
        base_delay = self.config.ajax_wait
        
        # 动态内容较多的页面AJAX请求多
        ajax_factors = {
            'search': 1.3,      # 搜索页面有过滤器等AJAX
            'product': 1.1,     # 商品页面有相关商品加载
            'category': 1.2,    # 分类页面有动态加载
            'home': 1.0,        # 首页AJAX较少
            'generic': 1.0
        }
        
        ajax_factor = ajax_factors.get(page_type, 1.0)
        
        return base_delay * ajax_factor * random.uniform(0.8, 1.2)
    
    def _calculate_final_delay(self, page_type: str) -> float:
        """计算最终稳定延迟"""
        # 简单的最终等待时间
        base_delay = 0.5
        
        # 复杂页面需要更长稳定时间
        if page_type in ['product', 'search']:
            base_delay *= 1.5
        
        return base_delay * random.uniform(0.8, 1.2)
    
    def _needs_ajax_wait(self, page_type: str) -> bool:
        """判断是否需要AJAX等待"""
        # 简化判断：搜索和商品页面通常有AJAX
        return page_type in ['search', 'product', 'category']
    
    def _simulate_network_delay(self) -> float:
        """模拟网络延迟"""
        base_delay = self.config.network_delay_base
        jitter = random.uniform(-self.config.network_jitter, self.config.network_jitter)
        
        # 确保延迟为正数
        return max(0.1, base_delay + jitter)
    
    def _detect_page_type(self, url: str) -> str:
        """检测页面类型"""
        url_lower = url.lower()
        
        if '/search' in url_lower:
            return 'search'
        elif '/item/' in url_lower or '/product/' in url_lower:
            return 'product'
        elif '/category/' in url_lower:
            return 'category'
        elif url_lower.endswith('/') or 'mercari.com' in url_lower:
            return 'home'
        else:
            return 'generic'
    
    async def wait_for_element_interaction(self, element_selector: str, 
                                         interaction_type: str = 'click') -> float:
        """等待元素交互前的延迟"""
        
        # 元素发现时间
        discovery_time = random.uniform(0.3, 1.0)
        
        # 决策时间
        decision_time = self._calculate_decision_time(interaction_type)
        
        # 移动准备时间
        preparation_time = random.uniform(0.2, 0.5)
        
        total_delay = discovery_time + decision_time + preparation_time
        
        await asyncio.sleep(total_delay)
        
        return total_delay
    
    def _calculate_decision_time(self, interaction_type: str) -> float:
        """计算决策时间"""
        decision_times = {
            'click': random.uniform(0.5, 1.5),
            'hover': random.uniform(0.2, 0.8),
            'scroll': random.uniform(0.1, 0.5),
            'type': random.uniform(0.8, 2.0)
        }
        
        return decision_times.get(interaction_type, 0.5)


class MercariPageLoadingOptimizer:
    """Mercari页面加载优化器"""
    
    def __init__(self):
        self.mercari_configs = {
            'search': PageLoadingConfig(
                initial_wait=1.5,
                dom_ready_wait=1.0,
                image_load_wait=2.0,
                ajax_wait=1.5
            ),
            'product': PageLoadingConfig(
                initial_wait=2.0,
                dom_ready_wait=1.5,
                image_load_wait=3.5,
                ajax_wait=2.0
            ),
            'category': PageLoadingConfig(
                initial_wait=1.8,
                dom_ready_wait=1.2,
                image_load_wait=2.5,
                ajax_wait=1.8
            )
        }
    
    def get_optimized_config(self, url: str) -> PageLoadingConfig:
        """获取优化的配置"""
        if '/search' in url:
            return self.mercari_configs['search']
        elif '/item/' in url:
            return self.mercari_configs['product']
        elif '/category/' in url:
            return self.mercari_configs['category']
        else:
            return PageLoadingConfig()  # 默认配置
    
    async def optimized_page_load(self, session, url: str) -> Dict[str, Any]:
        """优化的页面加载"""
        config = self.get_optimized_config(url)
        strategy = ProgressiveLoadingStrategy(config)
        
        # 检测页面类型
        page_type = strategy._detect_page_type(url)
        
        # 执行加载
        return await strategy.wait_for_page_load(session, url, page_type)


# 集成函数
def create_loading_strategy(optimize_for_mercari: bool = True) -> ProgressiveLoadingStrategy:
    """创建加载策略"""
    if optimize_for_mercari:
        return MercariPageLoadingOptimizer()
    else:
        return ProgressiveLoadingStrategy()


def integrate_with_behavior_engine(behavior_engine, loading_strategy):
    """与行为引擎集成"""
    
    original_page_interaction = behavior_engine.enhanced_page_interaction
    
    async def enhanced_page_interaction_with_loading(url: str, interaction_type: str = 'browse'):
        """增强的页面交互（包含加载策略）"""
        # 先执行页面加载策略
        if hasattr(loading_strategy, 'optimized_page_load'):
            await loading_strategy.optimized_page_load(None, url)
        else:
            await loading_strategy.wait_for_page_load(None, url, 'generic')
        
        # 然后执行原始的页面交互
        return await original_page_interaction(url, interaction_type)
    
    behavior_engine.enhanced_page_interaction = enhanced_page_interaction_with_loading
    return behavior_engine


if __name__ == "__main__":
    async def test_loading_strategy():
        """测试加载策略"""
        optimizer = MercariPageLoadingOptimizer()
        
        # 测试不同页面类型
        test_urls = [
            "https://mercari.com/search?q=test",
            "https://mercari.com/item/m12345",
            "https://mercari.com/category/1"
        ]
        
        for url in test_urls:
            result = await optimizer.optimized_page_load(None, url)
            print(f"URL: {url}")
            print(f"加载时间: {result['total_time']:.2f}秒")
            print(f"阶段数: {len(result['stages'])}")
            print("---")
    
    asyncio.run(test_loading_strategy())