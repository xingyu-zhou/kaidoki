"""
排名系统模块

该模块负责对产品进行智能排名。
基于评分结果和用户偏好进行排序优化。

主要功能：
- 智能排名算法
- 个性化排序
- 多维度权重调整
- 排名解释
- 动态优化

Author: Mercari AI Agent Team
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import random
import math

from ..models.product import ProductData
from ..models.query import ParsedQuery
from ..utils.logger import get_logger
from ..config.settings import settings

logger = get_logger(__name__)


class RankingStrategy(Enum):
    """排名策略枚举"""
    SCORE_BASED = "score_based"        # 基于评分
    POPULARITY_BASED = "popularity_based"  # 基于热度
    PRICE_BASED = "price_based"        # 基于价格
    QUALITY_BASED = "quality_based"    # 基于质量
    HYBRID = "hybrid"                  # 混合策略
    PERSONALIZED = "personalized"     # 个性化


@dataclass
class RankingResult:
    """排名结果"""
    ranked_products: List[Tuple[ProductData, float, Dict[str, Any]]]
    strategy_used: RankingStrategy
    total_products: int
    ranking_factors: List[str]
    processing_time: float
    metadata: Dict[str, Any]


class RankingSystem:
    """
    排名系统类
    
    负责对产品进行智能排名和排序。
    支持多种排名策略和个性化调整。
    """
    
    def __init__(self):
        """初始化排名系统"""
        self.ranking_strategies = self._initialize_strategies()
        self.ranking_weights = self._load_ranking_weights()
        self.personalization_factors = self._initialize_personalization()
        self.ranking_history = []
        
        logger.info("RankingSystem initialized")
    
    async def rank(
        self,
        scored_products: List[Tuple[ProductData, Dict[str, float], float]],
        context: Any,
        strategy: RankingStrategy = RankingStrategy.HYBRID
    ) -> List[Tuple[ProductData, Dict[str, float], float]]:
        """
        对产品进行排名
        
        Args:
            scored_products: 已评分的产品列表
            context: 排名上下文
            strategy: 排名策略
            
        Returns:
            List[Tuple[ProductData, Dict[str, float], float]]: 排名后的产品列表
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            # 1. 选择排名策略
            ranking_func = self.ranking_strategies.get(strategy)
            if not ranking_func:
                ranking_func = self.ranking_strategies[RankingStrategy.SCORE_BASED]
            
            # 2. 执行排名
            ranked_products = await ranking_func(scored_products, context)
            
            # 3. 应用个性化调整
            if hasattr(context, 'user_preferences') and context.user_preferences:
                ranked_products = await self._apply_personalization(
                    ranked_products, context.user_preferences
                )
            
            # 4. 应用多样性调整
            ranked_products = await self._apply_diversity(ranked_products)
            
            # 5. 记录排名历史
            processing_time = asyncio.get_event_loop().time() - start_time
            self._record_ranking_history(ranked_products, strategy, processing_time)
            
            logger.info(f"产品排名完成: {len(ranked_products)} 个产品，策略: {strategy.value}")
            return ranked_products
            
        except Exception as e:
            logger.error(f"产品排名失败: {e}")
            # 返回原始顺序
            return scored_products
    
    async def _score_based_ranking(
        self,
        scored_products: List[Tuple[ProductData, Dict[str, float], float]],
        context: Any
    ) -> List[Tuple[ProductData, Dict[str, float], float]]:
        """基于评分的排名"""
        # 按最终评分降序排列
        return sorted(scored_products, key=lambda x: x[2], reverse=True)
    
    async def _popularity_based_ranking(
        self,
        scored_products: List[Tuple[ProductData, Dict[str, float], float]],
        context: Any
    ) -> List[Tuple[ProductData, Dict[str, float], float]]:
        """基于热度的排名"""
        def popularity_score(item):
            product, scores, final_score = item
            popularity = 0.0
            
            # 点赞数
            if product.like_count:
                popularity += math.log(product.like_count + 1) * 0.3
            
            # 浏览数
            if product.view_count:
                popularity += math.log(product.view_count + 1) * 0.2
            
            # 结合最终评分
            popularity += final_score * 0.5
            
            return popularity
        
        return sorted(scored_products, key=popularity_score, reverse=True)
    
    async def _price_based_ranking(
        self,
        scored_products: List[Tuple[ProductData, Dict[str, float], float]],
        context: Any
    ) -> List[Tuple[ProductData, Dict[str, float], float]]:
        """基于价格的排名"""
        def price_score(item):
            product, scores, final_score = item
            price_factor = 0.0
            
            if product.price:
                # 价格越低，排名越高（在一定范围内）
                if product.price > 0:
                    price_factor = 1.0 / (1.0 + product.price / 10000)
                
                # 结合价格评分
                price_factor += scores.get("price_score", 0.5) * 0.3
            
            # 结合最终评分
            price_factor += final_score * 0.7
            
            return price_factor
        
        return sorted(scored_products, key=price_score, reverse=True)
    
    async def _quality_based_ranking(
        self,
        scored_products: List[Tuple[ProductData, Dict[str, float], float]],
        context: Any
    ) -> List[Tuple[ProductData, Dict[str, float], float]]:
        """基于质量的排名"""
        def quality_score(item):
            product, scores, final_score = item
            quality_factor = 0.0
            
            # 质量评分
            quality_factor += scores.get("quality_score", 0.5) * 0.4
            
            # 卖家评分
            quality_factor += scores.get("seller_score", 0.5) * 0.3
            
            # 结合最终评分
            quality_factor += final_score * 0.3
            
            return quality_factor
        
        return sorted(scored_products, key=quality_score, reverse=True)
    
    async def _hybrid_ranking(
        self,
        scored_products: List[Tuple[ProductData, Dict[str, float], float]],
        context: Any
    ) -> List[Tuple[ProductData, Dict[str, float], float]]:
        """混合排名策略"""
        def hybrid_score(item):
            product, scores, final_score = item
            
            # 基础评分权重
            hybrid_factor = final_score * 0.6
            
            # 价格因子
            if product.price:
                price_factor = scores.get("price_score", 0.5) * 0.15
                hybrid_factor += price_factor
            
            # 质量因子
            quality_factor = scores.get("quality_score", 0.5) * 0.15
            hybrid_factor += quality_factor
            
            # 热度因子
            if product.like_count or product.view_count:
                popularity_factor = 0.0
                if product.like_count:
                    popularity_factor += math.log(product.like_count + 1) * 0.05
                if product.view_count:
                    popularity_factor += math.log(product.view_count + 1) * 0.05
                hybrid_factor += popularity_factor
            
            return hybrid_factor
        
        return sorted(scored_products, key=hybrid_score, reverse=True)
    
    async def _personalized_ranking(
        self,
        scored_products: List[Tuple[ProductData, Dict[str, float], float]],
        context: Any
    ) -> List[Tuple[ProductData, Dict[str, float], float]]:
        """个性化排名"""
        # 如果没有个性化信息，回退到混合策略
        if not hasattr(context, 'user_preferences') or not context.user_preferences:
            return await self._hybrid_ranking(scored_products, context)
        
        preferences = context.user_preferences
        
        def personalized_score(item):
            product, scores, final_score = item
            
            # 基础评分
            personalized_factor = final_score * 0.5
            
            # 根据用户偏好调整
            if preferences.get("prefer_low_price", False):
                personalized_factor += scores.get("price_score", 0.5) * 0.2
            
            if preferences.get("prefer_high_quality", False):
                personalized_factor += scores.get("quality_score", 0.5) * 0.2
            
            if preferences.get("prefer_popular", False):
                personalized_factor += scores.get("popularity_score", 0.5) * 0.1
            
            # 品牌偏好
            if preferences.get("preferred_brands") and product.title:
                for brand in preferences["preferred_brands"]:
                    if brand.lower() in product.title.lower():
                        personalized_factor += 0.1
                        break
            
            # 类别偏好
            if preferences.get("preferred_categories") and product.category:
                if product.category in preferences["preferred_categories"]:
                    personalized_factor += 0.1
            
            return personalized_factor
        
        return sorted(scored_products, key=personalized_score, reverse=True)
    
    async def _apply_personalization(
        self,
        ranked_products: List[Tuple[ProductData, Dict[str, float], float]],
        user_preferences: Dict[str, Any]
    ) -> List[Tuple[ProductData, Dict[str, float], float]]:
        """应用个性化调整"""
        if not user_preferences:
            return ranked_products
        
        # 根据用户历史行为调整
        if user_preferences.get("recent_purchases"):
            ranked_products = await self._adjust_for_purchase_history(
                ranked_products, user_preferences["recent_purchases"]
            )
        
        # 根据用户搜索历史调整
        if user_preferences.get("search_history"):
            ranked_products = await self._adjust_for_search_history(
                ranked_products, user_preferences["search_history"]
            )
        
        return ranked_products
    
    async def _apply_diversity(
        self,
        ranked_products: List[Tuple[ProductData, Dict[str, float], float]]
    ) -> List[Tuple[ProductData, Dict[str, float], float]]:
        """应用多样性调整"""
        if len(ranked_products) <= 10:
            return ranked_products
        
        # 确保前10名中有不同类别的产品
        diverse_products = []
        seen_categories = set()
        remaining_products = []
        
        for item in ranked_products:
            product, scores, final_score = item
            category = product.category or "其他"
            
            if category not in seen_categories and len(diverse_products) < 10:
                diverse_products.append(item)
                seen_categories.add(category)
            else:
                remaining_products.append(item)
        
        # 填充剩余位置
        diverse_products.extend(remaining_products)
        
        return diverse_products
    
    async def _adjust_for_purchase_history(
        self,
        ranked_products: List[Tuple[ProductData, Dict[str, float], float]],
        purchase_history: List[Dict[str, Any]]
    ) -> List[Tuple[ProductData, Dict[str, float], float]]:
        """根据购买历史调整排名"""
        # 提取购买历史中的关键信息
        purchased_categories = set()
        purchased_brands = set()
        
        for purchase in purchase_history:
            if purchase.get("category"):
                purchased_categories.add(purchase["category"])
            if purchase.get("brand"):
                purchased_brands.add(purchase["brand"])
        
        # 调整排名
        adjusted_products = []
        for product, scores, final_score in ranked_products:
            adjustment = 0.0
            
            # 相同类别的产品获得加分
            if product.category in purchased_categories:
                adjustment += 0.1
            
            # 相同品牌的产品获得加分
            if product.title:
                for brand in purchased_brands:
                    if brand.lower() in product.title.lower():
                        adjustment += 0.05
                        break
            
            adjusted_score = final_score + adjustment
            adjusted_products.append((product, scores, adjusted_score))
        
        # 重新排序
        return sorted(adjusted_products, key=lambda x: x[2], reverse=True)
    
    async def _adjust_for_search_history(
        self,
        ranked_products: List[Tuple[ProductData, Dict[str, float], float]],
        search_history: List[str]
    ) -> List[Tuple[ProductData, Dict[str, float], float]]:
        """根据搜索历史调整排名"""
        # 提取搜索历史中的关键词
        search_keywords = set()
        for search in search_history:
            search_keywords.update(search.lower().split())
        
        # 调整排名
        adjusted_products = []
        for product, scores, final_score in ranked_products:
            adjustment = 0.0
            
            # 标题匹配搜索历史
            if product.title:
                title_lower = product.title.lower()
                matches = sum(1 for keyword in search_keywords if keyword in title_lower)
                adjustment += matches * 0.02
            
            adjusted_score = final_score + adjustment
            adjusted_products.append((product, scores, adjusted_score))
        
        # 重新排序
        return sorted(adjusted_products, key=lambda x: x[2], reverse=True)
    
    def _record_ranking_history(
        self,
        ranked_products: List[Tuple[ProductData, Dict[str, float], float]],
        strategy: RankingStrategy,
        processing_time: float
    ):
        """记录排名历史"""
        history_entry = {
            "timestamp": datetime.now().isoformat(),
            "strategy": strategy.value,
            "product_count": len(ranked_products),
            "processing_time": processing_time,
            "top_scores": [item[2] for item in ranked_products[:10]]
        }
        
        self.ranking_history.append(history_entry)
        
        # 限制历史记录数量
        if len(self.ranking_history) > 1000:
            self.ranking_history = self.ranking_history[-1000:]
    
    def _initialize_strategies(self) -> Dict[RankingStrategy, Any]:
        """初始化排名策略"""
        return {
            RankingStrategy.SCORE_BASED: self._score_based_ranking,
            RankingStrategy.POPULARITY_BASED: self._popularity_based_ranking,
            RankingStrategy.PRICE_BASED: self._price_based_ranking,
            RankingStrategy.QUALITY_BASED: self._quality_based_ranking,
            RankingStrategy.HYBRID: self._hybrid_ranking,
            RankingStrategy.PERSONALIZED: self._personalized_ranking
        }
    
    def _load_ranking_weights(self) -> Dict[str, float]:
        """加载排名权重"""
        return {
            "score_weight": 0.6,
            "price_weight": 0.15,
            "quality_weight": 0.15,
            "popularity_weight": 0.1
        }
    
    def _initialize_personalization(self) -> Dict[str, Any]:
        """初始化个性化因子"""
        return {
            "price_sensitivity": 0.2,
            "quality_preference": 0.3,
            "brand_loyalty": 0.1,
            "category_preference": 0.2,
            "popularity_influence": 0.1,
            "novelty_preference": 0.1
        }
    
    def update_ranking_weights(self, new_weights: Dict[str, float]):
        """更新排名权重"""
        self.ranking_weights.update(new_weights)
        logger.info(f"排名权重已更新: {new_weights}")
    
    def get_ranking_statistics(self) -> Dict[str, Any]:
        """获取排名统计"""
        if not self.ranking_history:
            return {"message": "无排名历史"}
        
        strategies_used = {}
        total_processing_time = 0.0
        
        for entry in self.ranking_history:
            strategy = entry["strategy"]
            strategies_used[strategy] = strategies_used.get(strategy, 0) + 1
            total_processing_time += entry["processing_time"]
        
        return {
            "total_rankings": len(self.ranking_history),
            "strategies_used": strategies_used,
            "average_processing_time": total_processing_time / len(self.ranking_history),
            "available_strategies": [strategy.value for strategy in RankingStrategy]
        }
    
    def optimize_ranking_parameters(self, feedback_data: List[Dict[str, Any]]):
        """基于反馈数据优化排名参数"""
        if not feedback_data:
            return
        
        # 分析反馈数据
        positive_feedback = [item for item in feedback_data if item.get("feedback") == "positive"]
        negative_feedback = [item for item in feedback_data if item.get("feedback") == "negative"]
        
        # 调整权重
        if len(positive_feedback) > len(negative_feedback):
            # 正面反馈较多，保持当前策略
            logger.info("正面反馈较多，保持当前排名策略")
        else:
            # 负面反馈较多，调整策略
            logger.info("负面反馈较多，调整排名策略")
            self._adjust_ranking_strategy(negative_feedback)
    
    def _adjust_ranking_strategy(self, negative_feedback: List[Dict[str, Any]]):
        """调整排名策略"""
        # 分析负面反馈的原因
        common_issues = {}
        for feedback in negative_feedback:
            issue = feedback.get("issue", "unknown")
            common_issues[issue] = common_issues.get(issue, 0) + 1
        
        # 根据常见问题调整权重
        if "price_too_high" in common_issues:
            self.ranking_weights["price_weight"] += 0.05
        
        if "quality_too_low" in common_issues:
            self.ranking_weights["quality_weight"] += 0.05
        
        # 确保权重总和不超过1
        total_weight = sum(self.ranking_weights.values())
        if total_weight > 1.0:
            for key in self.ranking_weights:
                self.ranking_weights[key] /= total_weight
    
    def get_ranking_explanation(
        self,
        product: ProductData,
        rank: int,
        scores: Dict[str, float],
        strategy: RankingStrategy
    ) -> str:
        """获取排名解释"""
        explanation_parts = []
        
        explanation_parts.append(f"排名第{rank}位")
        explanation_parts.append(f"使用{strategy.value}策略")
        
        # 根据策略添加具体解释
        if strategy == RankingStrategy.SCORE_BASED:
            explanation_parts.append(f"综合评分较高")
        elif strategy == RankingStrategy.PRICE_BASED:
            explanation_parts.append(f"价格优势明显")
        elif strategy == RankingStrategy.QUALITY_BASED:
            explanation_parts.append(f"质量评分较高")
        elif strategy == RankingStrategy.POPULARITY_BASED:
            explanation_parts.append(f"热度较高")
        elif strategy == RankingStrategy.HYBRID:
            explanation_parts.append(f"综合表现优秀")
        elif strategy == RankingStrategy.PERSONALIZED:
            explanation_parts.append(f"符合个人偏好")
        
        # 添加具体得分信息
        if scores.get("price_score", 0) > 0.8:
            explanation_parts.append("价格优势")
        if scores.get("quality_score", 0) > 0.8:
            explanation_parts.append("质量优秀")
        if scores.get("relevance_score", 0) > 0.8:
            explanation_parts.append("高度相关")
        
        return "，".join(explanation_parts)
    
    def get_info(self) -> Dict[str, Any]:
        """获取排名系统信息"""
        return {
            "version": "1.0.0",
            "available_strategies": [strategy.value for strategy in RankingStrategy],
            "current_weights": self.ranking_weights,
            "personalization_factors": self.personalization_factors,
            "ranking_history_size": len(self.ranking_history)
        }