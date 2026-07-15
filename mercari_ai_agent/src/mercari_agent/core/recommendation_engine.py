"""
推荐引擎模块

该模块负责基于多维度分析结果生成智能推荐。
使用机器学习算法和启发式规则进行产品排名和推荐。

主要功能：
- 多维度产品评分
- 智能排名算法
- 个性化推荐
- 透明化推理过程

Author: Mercari AI Agent Team
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import math

from ..models.product import Product, ProductData
from ..models.recommendation import Recommendation, RecommendationResult, RecommendationReason
from ..models.query import ParsedQuery
from ..analyzers.scoring_engine import ScoringEngine
from ..analyzers.ranking_system import RankingSystem
from ..utils.logger import get_logger
from ..config.settings import settings

logger = get_logger(__name__)


class RecommendationStrategy(Enum):
    """推荐策略枚举"""
    PRICE_ORIENTED = "price_oriented"      # 价格导向
    QUALITY_ORIENTED = "quality_oriented"  # 质量导向
    BALANCED = "balanced"                  # 平衡策略
    TRENDING = "trending"                  # 趋势导向


@dataclass
class RecommendationContext:
    """推荐上下文"""
    query: ParsedQuery
    strategy: RecommendationStrategy
    user_preferences: Optional[Dict[str, Any]] = None
    market_context: Optional[Dict[str, Any]] = None


class RecommendationEngine:
    """
    推荐引擎类
    
    负责基于分析结果生成智能推荐，支持多种推荐策略。
    提供透明化的推理过程和可解释的推荐结果。
    """
    
    def __init__(self, scoring_engine: ScoringEngine, ranking_system: RankingSystem):
        """
        初始化推荐引擎
        
        Args:
            scoring_engine: 评分引擎实例
            ranking_system: 排名系统实例
        """
        self.scoring_engine = scoring_engine
        self.ranking_system = ranking_system
        self.strategy_weights = self._load_strategy_weights()
        self.recommendation_rules = self._load_recommendation_rules()
        
        logger.info("RecommendationEngine initialized")
    
    async def recommend(
        self,
        products: List[ProductData],
        context: RecommendationContext,
        max_results: int = 10
    ) -> RecommendationResult:
        """
        生成推荐结果
        
        Args:
            products: 产品数据列表
            context: 推荐上下文
            max_results: 最大结果数量
            
        Returns:
            RecommendationResult: 推荐结果
            
        Raises:
            ValueError: 产品列表为空
            RecommendationError: 推荐过程失败
        """
        if not products:
            raise ValueError("产品列表不能为空")
        
        start_time = datetime.now()
        
        try:
            # 1. 产品评分
            scored_products = await self._score_products(products, context)
            logger.debug(f"产品评分完成: {len(scored_products)} 个产品")
            
            # 2. 应用推荐策略
            strategy_scores = await self._apply_strategy(scored_products, context)
            logger.debug(f"策略应用完成: {context.strategy.value}")
            
            # 3. 产品排名
            ranked_products = await self._rank_products(strategy_scores, context)
            logger.debug(f"产品排名完成")
            
            # 4. 生成推荐
            recommendations = await self._generate_recommendations(
                ranked_products[:max_results],
                context
            )
            
            # 5. 构建结果
            result = RecommendationResult(
                recommendations=recommendations,
                total_analyzed=len(products),
                strategy_used=context.strategy,
                processing_time=(datetime.now() - start_time).total_seconds(),
                metadata={
                    "query_keywords": context.query.keywords,
                    "strategy_weights": self.strategy_weights.get(context.strategy.value, {}),
                    "ranking_factors": self._get_ranking_factors(context)
                }
            )
            
            logger.info(f"推荐生成完成: {len(recommendations)} 个推荐")
            return result
            
        except Exception as e:
            logger.error(f"推荐生成失败: {e}")
            raise
    
    async def _score_products(
        self,
        products: List[ProductData],
        context: RecommendationContext
    ) -> List[Tuple[ProductData, Dict[str, float]]]:
        """
        为产品评分
        
        Args:
            products: 产品数据列表
            context: 推荐上下文
            
        Returns:
            List[Tuple[ProductData, Dict[str, float]]]: 评分结果列表
        """
        scored_products = []
        
        for product in products:
            scores = await self.scoring_engine.score_product(product, context.query)
            scored_products.append((product, scores))
        
        return scored_products
    
    async def _apply_strategy(
        self,
        scored_products: List[Tuple[ProductData, Dict[str, float]]],
        context: RecommendationContext
    ) -> List[Tuple[ProductData, Dict[str, float], float]]:
        """
        应用推荐策略
        
        Args:
            scored_products: 评分产品列表
            context: 推荐上下文
            
        Returns:
            List[Tuple[ProductData, Dict[str, float], float]]: 策略评分结果
        """
        strategy_weights = self.strategy_weights.get(context.strategy.value, {})
        strategy_scores = []
        
        for product, scores in scored_products:
            # 计算策略加权分数
            weighted_score = 0.0
            for factor, score in scores.items():
                weight = strategy_weights.get(factor, 1.0)
                weighted_score += score * weight
            
            # 应用策略特定调整
            adjusted_score = self._apply_strategy_adjustments(
                weighted_score, product, context
            )
            
            strategy_scores.append((product, scores, adjusted_score))
        
        return strategy_scores
    
    def _apply_strategy_adjustments(
        self,
        base_score: float,
        product: ProductData,
        context: RecommendationContext
    ) -> float:
        """
        应用策略特定调整
        
        Args:
            base_score: 基础分数
            product: 产品数据
            context: 推荐上下文
            
        Returns:
            float: 调整后的分数
        """
        adjusted_score = base_score
        
        if context.strategy == RecommendationStrategy.PRICE_ORIENTED:
            # 价格导向：低价产品获得加分
            if product.price and context.query.price_max:
                price_ratio = product.price / context.query.price_max
                if price_ratio < 0.7:  # 低于预期价格30%
                    adjusted_score *= 1.2
        
        elif context.strategy == RecommendationStrategy.QUALITY_ORIENTED:
            # 质量导向：高质量产品获得加分
            if product.condition and "新品" in product.condition:
                adjusted_score *= 1.3
            elif product.seller_rating and product.seller_rating > 4.5:
                adjusted_score *= 1.2
        
        elif context.strategy == RecommendationStrategy.TRENDING:
            # 趋势导向：热门产品获得加分
            if product.view_count and product.view_count > 1000:
                adjusted_score *= 1.1
            if product.like_count and product.like_count > 50:
                adjusted_score *= 1.1
        
        return adjusted_score
    
    async def _rank_products(
        self,
        strategy_scores: List[Tuple[ProductData, Dict[str, float], float]],
        context: RecommendationContext
    ) -> List[Tuple[ProductData, Dict[str, float], float]]:
        """
        产品排名
        
        Args:
            strategy_scores: 策略评分结果
            context: 推荐上下文
            
        Returns:
            List[Tuple[ProductData, Dict[str, float], float]]: 排名结果
        """
        return await self.ranking_system.rank(strategy_scores, context)
    
    async def _generate_recommendations(
        self,
        ranked_products: List[Tuple[ProductData, Dict[str, float], float]],
        context: RecommendationContext
    ) -> List[Recommendation]:
        """
        生成推荐结果
        
        Args:
            ranked_products: 排名产品列表
            context: 推荐上下文
            
        Returns:
            List[Recommendation]: 推荐列表
        """
        recommendations = []
        
        for i, (product, scores, final_score) in enumerate(ranked_products):
            # 生成推荐理由
            reasons = await self._generate_recommendation_reasons(
                product, scores, context
            )
            
            # 计算置信度
            confidence = self._calculate_confidence(product, scores, final_score)
            
            # 生成购买建议
            purchase_advice = await self._generate_purchase_advice(
                product, scores, context
            )
            
            recommendation = Recommendation(
                product=product,
                rank=i + 1,
                score=final_score,
                confidence=confidence,
                reasons=reasons,
                purchase_advice=purchase_advice,
                metadata={
                    "detailed_scores": scores,
                    "strategy": context.strategy.value,
                    "processing_timestamp": datetime.now().isoformat()
                }
            )
            
            recommendations.append(recommendation)
        
        return recommendations
    
    async def _generate_recommendation_reasons(
        self,
        product: ProductData,
        scores: Dict[str, float],
        context: RecommendationContext
    ) -> List[RecommendationReason]:
        """
        生成推荐理由
        
        Args:
            product: 产品数据
            scores: 评分结果
            context: 推荐上下文
            
        Returns:
            List[RecommendationReason]: 推荐理由列表
        """
        reasons = []
        
        # 价格优势
        if scores.get("price_score", 0) > 0.8:
            reasons.append(RecommendationReason(
                type="price_advantage",
                description=f"价格优势明显：¥{product.price:,}，性价比高",
                importance=0.9
            ))
        
        # 质量优势
        if scores.get("quality_score", 0) > 0.8:
            reasons.append(RecommendationReason(
                type="quality_advantage",
                description=f"商品状态良好：{product.condition}",
                importance=0.8
            ))
        
        # 卖家信誉
        if product.seller_rating and product.seller_rating > 4.5:
            reasons.append(RecommendationReason(
                type="seller_reputation",
                description=f"卖家信誉度高：{product.seller_rating}★",
                importance=0.7
            ))
        
        # 匹配度
        if scores.get("relevance_score", 0) > 0.9:
            reasons.append(RecommendationReason(
                type="high_relevance",
                description="与搜索需求高度匹配",
                importance=0.9
            ))
        
        return reasons
    
    def _calculate_confidence(
        self,
        product: ProductData,
        scores: Dict[str, float],
        final_score: float
    ) -> float:
        """
        计算推荐置信度
        
        Args:
            product: 产品数据
            scores: 评分结果
            final_score: 最终分数
            
        Returns:
            float: 置信度（0-1）
        """
        # 基础置信度基于最终分数
        base_confidence = min(final_score, 1.0)
        
        # 根据数据完整性调整
        completeness_factor = 1.0
        if not product.description:
            completeness_factor -= 0.1
        if not product.images:
            completeness_factor -= 0.1
        if not product.seller_rating:
            completeness_factor -= 0.05
        
        # 根据评分一致性调整
        score_variance = self._calculate_score_variance(scores)
        consistency_factor = max(0.7, 1.0 - score_variance)
        
        confidence = base_confidence * completeness_factor * consistency_factor
        return max(0.1, min(1.0, confidence))
    
    def _calculate_score_variance(self, scores: Dict[str, float]) -> float:
        """
        计算评分方差
        
        Args:
            scores: 评分结果
            
        Returns:
            float: 方差值
        """
        if not scores:
            return 0.0
        
        values = list(scores.values())
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        
        return math.sqrt(variance)
    
    async def _generate_purchase_advice(
        self,
        product: ProductData,
        scores: Dict[str, float],
        context: RecommendationContext
    ) -> str:
        """
        生成购买建议
        
        Args:
            product: 产品数据
            scores: 评分结果
            context: 推荐上下文
            
        Returns:
            str: 购买建议
        """
        advice_parts = []
        
        # 价格建议
        if scores.get("price_score", 0) > 0.8:
            advice_parts.append("价格合理，建议购买")
        elif scores.get("price_score", 0) < 0.5:
            advice_parts.append("价格偏高，建议谨慎考虑")
        
        # 质量建议
        if product.condition and "新品" in product.condition:
            advice_parts.append("商品为新品，质量有保障")
        elif product.condition and "中古" in product.condition:
            advice_parts.append("二手商品，请仔细查看商品描述")
        
        # 卖家建议
        if product.seller_rating and product.seller_rating > 4.5:
            advice_parts.append("卖家信誉良好，交易相对安全")
        elif product.seller_rating and product.seller_rating < 3.5:
            advice_parts.append("卖家评分较低，建议谨慎购买")
        
        return "；".join(advice_parts) if advice_parts else "请根据个人需求决定"
    
    def _load_strategy_weights(self) -> Dict[str, Dict[str, float]]:
        """
        加载策略权重配置
        
        Returns:
            Dict[str, Dict[str, float]]: 策略权重字典
        """
        return {
            "price_oriented": {
                "price_score": 1.5,
                "quality_score": 1.0,
                "relevance_score": 1.2,
                "seller_score": 0.8,
                "popularity_score": 0.6
            },
            "quality_oriented": {
                "price_score": 0.8,
                "quality_score": 1.5,
                "relevance_score": 1.2,
                "seller_score": 1.3,
                "popularity_score": 0.7
            },
            "balanced": {
                "price_score": 1.0,
                "quality_score": 1.0,
                "relevance_score": 1.0,
                "seller_score": 1.0,
                "popularity_score": 1.0
            },
            "trending": {
                "price_score": 0.9,
                "quality_score": 0.8,
                "relevance_score": 1.0,
                "seller_score": 0.9,
                "popularity_score": 1.5
            }
        }
    
    def _load_recommendation_rules(self) -> Dict[str, Any]:
        """
        加载推荐规则
        
        Returns:
            Dict[str, Any]: 推荐规则字典
        """
        return {
            "min_confidence": 0.3,
            "max_price_deviation": 0.5,
            "quality_threshold": 0.6,
            "seller_rating_threshold": 3.0
        }
    
    def _get_ranking_factors(self, context: RecommendationContext) -> List[str]:
        """
        获取排名因素
        
        Args:
            context: 推荐上下文
            
        Returns:
            List[str]: 排名因素列表
        """
        base_factors = ["price", "quality", "relevance", "seller_rating"]
        
        if context.strategy == RecommendationStrategy.TRENDING:
            base_factors.extend(["popularity", "view_count"])
        elif context.strategy == RecommendationStrategy.PRICE_ORIENTED:
            base_factors.extend(["price_competitiveness"])
        elif context.strategy == RecommendationStrategy.QUALITY_ORIENTED:
            base_factors.extend(["condition_score", "description_quality"])
        
        return base_factors