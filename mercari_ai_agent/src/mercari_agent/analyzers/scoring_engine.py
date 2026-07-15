"""
评分引擎模块

该模块负责对产品进行综合评分。
基于多个维度的指标计算产品的综合得分。

主要功能：
- 多维度评分
- 权重配置
- 评分规则管理
- 动态调整
- 评分解释

Author: Mercari AI Agent Team
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import math

from ..models.product import ProductData
from ..models.query import ParsedQuery
from ..utils.logger import get_logger
from ..config.settings import settings

logger = get_logger(__name__)


class ScoreDimension(Enum):
    """评分维度枚举"""
    PRICE = "price"              # 价格
    QUALITY = "quality"          # 质量
    RELEVANCE = "relevance"      # 相关性
    SELLER = "seller"            # 卖家
    POPULARITY = "popularity"    # 热度
    RISK = "risk"               # 风险
    COMPLETENESS = "completeness"  # 完整性


@dataclass
class ScoreResult:
    """评分结果"""
    total_score: float
    dimension_scores: Dict[ScoreDimension, float]
    normalized_scores: Dict[ScoreDimension, float]
    weights: Dict[ScoreDimension, float]
    explanations: Dict[ScoreDimension, str]
    confidence: float
    metadata: Dict[str, Any]


class ScoringEngine:
    """
    评分引擎类
    
    负责对产品进行多维度评分。
    支持动态权重调整和评分规则配置。
    """
    
    def __init__(self):
        """初始化评分引擎"""
        self.default_weights = self._load_default_weights()
        self.scoring_rules = self._load_scoring_rules()
        self.normalization_params = self._load_normalization_params()
        self.scoring_history = []
        
        logger.info("ScoringEngine initialized")
    
    async def score_product(
        self,
        product: ProductData,
        query: Optional[ParsedQuery] = None,
        custom_weights: Optional[Dict[ScoreDimension, float]] = None
    ) -> ScoreResult:
        """
        对产品进行评分
        
        Args:
            product: 产品数据
            query: 查询上下文
            custom_weights: 自定义权重
            
        Returns:
            ScoreResult: 评分结果
        """
        try:
            # 1. 获取权重
            weights = custom_weights or self.default_weights
            
            # 2. 计算各维度得分
            dimension_scores = await self._calculate_dimension_scores(product, query)
            
            # 3. 归一化处理
            normalized_scores = await self._normalize_scores(dimension_scores)
            
            # 4. 计算总分
            total_score = await self._calculate_total_score(normalized_scores, weights)
            
            # 5. 生成解释
            explanations = await self._generate_explanations(product, dimension_scores, normalized_scores)
            
            # 6. 计算置信度
            confidence = await self._calculate_confidence(product, dimension_scores)
            
            # 7. 构建结果
            result = ScoreResult(
                total_score=total_score,
                dimension_scores=dimension_scores,
                normalized_scores=normalized_scores,
                weights=weights,
                explanations=explanations,
                confidence=confidence,
                metadata={
                    "product_id": product.url,
                    "query_keywords": query.keywords if query else [],
                    "scoring_timestamp": datetime.now().isoformat(),
                    "engine_version": "1.0.0"
                }
            )
            
            # 8. 记录历史
            self.scoring_history.append(result)
            
            logger.debug(f"产品评分完成: {total_score:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"产品评分失败: {e}")
            raise
    
    async def _calculate_dimension_scores(
        self,
        product: ProductData,
        query: Optional[ParsedQuery]
    ) -> Dict[ScoreDimension, float]:
        """计算各维度得分"""
        scores = {}
        
        # 价格得分
        scores[ScoreDimension.PRICE] = await self._calculate_price_score(product, query)
        
        # 质量得分
        scores[ScoreDimension.QUALITY] = await self._calculate_quality_score(product)
        
        # 相关性得分
        scores[ScoreDimension.RELEVANCE] = await self._calculate_relevance_score(product, query)
        
        # 卖家得分
        scores[ScoreDimension.SELLER] = await self._calculate_seller_score(product)
        
        # 热度得分
        scores[ScoreDimension.POPULARITY] = await self._calculate_popularity_score(product)
        
        # 风险得分
        scores[ScoreDimension.RISK] = await self._calculate_risk_score(product)
        
        # 完整性得分
        scores[ScoreDimension.COMPLETENESS] = await self._calculate_completeness_score(product)
        
        return scores
    
    async def _calculate_price_score(self, product: ProductData, query: Optional[ParsedQuery]) -> float:
        """计算价格得分"""
        if not product.price:
            return 0.5
        
        score = 0.5
        
        # 基础价格合理性
        if product.price > 0:
            score += 0.2
        
        # 价格范围匹配
        if query and query.price_min and query.price_max:
            if query.price_min <= product.price <= query.price_max:
                score += 0.3
            elif product.price < query.price_min:
                # 低于预期价格，给予奖励
                score += 0.4
            else:
                # 高于预期价格，给予惩罚
                score -= 0.2
        
        # 价格区间评估
        if product.price < 1000:
            score += 0.1  # 便宜商品奖励
        elif product.price > 50000:
            score -= 0.1  # 昂贵商品惩罚
        
        return max(0.0, min(1.0, score))
    
    async def _calculate_quality_score(self, product: ProductData) -> float:
        """计算质量得分"""
        score = 0.0
        
        # 状态评估
        if product.condition:
            condition_scores = {
                "新品・未使用": 1.0,
                "未使用に近い": 0.9,
                "目立った傷や汚れなし": 0.8,
                "やや傷や汚れあり": 0.6,
                "傷や汚れあり": 0.4,
                "全体的に状態が悪い": 0.2
            }
            score += condition_scores.get(product.condition, 0.5) * 0.4
        else:
            score += 0.2  # 无状态信息的默认分数
        
        # 描述质量
        if product.description:
            desc_length = len(product.description)
            if desc_length > 100:
                score += 0.2
            elif desc_length > 50:
                score += 0.1
        
        # 图片数量
        if product.images:
            image_count = len(product.images)
            if image_count >= 3:
                score += 0.2
            elif image_count >= 1:
                score += 0.1
        
        # 标题质量
        if product.title:
            title_length = len(product.title)
            if 20 <= title_length <= 100:
                score += 0.1
        
        return max(0.0, min(1.0, score))
    
    async def _calculate_relevance_score(self, product: ProductData, query: Optional[ParsedQuery]) -> float:
        """计算相关性得分"""
        if not query or not query.keywords:
            return 0.5
        
        score = 0.0
        
        # 标题匹配
        if product.title:
            title_lower = product.title.lower()
            keyword_matches = sum(1 for keyword in query.keywords if keyword.lower() in title_lower)
            score += (keyword_matches / len(query.keywords)) * 0.6
        
        # 描述匹配
        if product.description:
            desc_lower = product.description.lower()
            keyword_matches = sum(1 for keyword in query.keywords if keyword.lower() in desc_lower)
            score += (keyword_matches / len(query.keywords)) * 0.3
        
        # 类别匹配
        if product.category and query.category:
            if product.category == query.category:
                score += 0.1
        
        return max(0.0, min(1.0, score))
    
    async def _calculate_seller_score(self, product: ProductData) -> float:
        """计算卖家得分"""
        score = 0.5
        
        # 卖家评分
        if product.seller_rating:
            rating_normalized = product.seller_rating / 5.0
            score = rating_normalized * 0.8 + 0.2
        
        # 卖家名称
        if product.seller_name:
            name_length = len(product.seller_name)
            if 3 <= name_length <= 20:
                score += 0.1
        
        return max(0.0, min(1.0, score))
    
    async def _calculate_popularity_score(self, product: ProductData) -> float:
        """计算热度得分"""
        score = 0.5
        
        # 点赞数
        if product.like_count:
            # 使用对数函数防止得分过高
            like_score = min(0.3, math.log(product.like_count + 1) / 10)
            score += like_score
        
        # 浏览数
        if product.view_count:
            view_score = min(0.2, math.log(product.view_count + 1) / 15)
            score += view_score
        
        return max(0.0, min(1.0, score))
    
    async def _calculate_risk_score(self, product: ProductData) -> float:
        """计算风险得分（风险越低，得分越高）"""
        score = 1.0
        
        # 卖家风险
        if product.seller_rating:
            if product.seller_rating < 3.0:
                score -= 0.3
            elif product.seller_rating < 4.0:
                score -= 0.1
        else:
            score -= 0.1  # 无评分的风险
        
        # 价格风险
        if product.price:
            if product.price < 100:
                score -= 0.2  # 过低价格风险
            elif product.price > 100000:
                score -= 0.1  # 过高价格风险
        
        # 信息缺失风险
        if not product.description:
            score -= 0.1
        
        if not product.images:
            score -= 0.1
        
        return max(0.0, min(1.0, score))
    
    async def _calculate_completeness_score(self, product: ProductData) -> float:
        """计算完整性得分"""
        score = 0.0
        
        # 必需信息
        if product.title:
            score += 0.3
        
        if product.price:
            score += 0.2
        
        # 重要信息
        if product.description:
            score += 0.2
        
        if product.images:
            score += 0.1
        
        if product.condition:
            score += 0.1
        
        # 额外信息
        if product.seller_name:
            score += 0.05
        
        if product.seller_rating:
            score += 0.05
        
        return max(0.0, min(1.0, score))
    
    async def _normalize_scores(self, scores: Dict[ScoreDimension, float]) -> Dict[ScoreDimension, float]:
        """归一化得分"""
        normalized = {}
        
        for dimension, score in scores.items():
            # 应用归一化参数
            params = self.normalization_params.get(dimension, {"min": 0.0, "max": 1.0})
            
            # 线性归一化
            normalized_score = (score - params["min"]) / (params["max"] - params["min"])
            normalized[dimension] = max(0.0, min(1.0, normalized_score))
        
        return normalized
    
    async def _calculate_total_score(
        self,
        normalized_scores: Dict[ScoreDimension, float],
        weights: Dict[ScoreDimension, float]
    ) -> float:
        """计算总分"""
        total_score = 0.0
        total_weight = 0.0
        
        for dimension, score in normalized_scores.items():
            weight = weights.get(dimension, 0.0)
            total_score += score * weight
            total_weight += weight
        
        # 归一化到0-10分
        if total_weight > 0:
            return (total_score / total_weight) * 10.0
        else:
            return 5.0
    
    async def _generate_explanations(
        self,
        product: ProductData,
        dimension_scores: Dict[ScoreDimension, float],
        normalized_scores: Dict[ScoreDimension, float]
    ) -> Dict[ScoreDimension, str]:
        """生成得分解释"""
        explanations = {}
        
        for dimension, score in normalized_scores.items():
            if dimension == ScoreDimension.PRICE:
                explanations[dimension] = await self._explain_price_score(product, score)
            elif dimension == ScoreDimension.QUALITY:
                explanations[dimension] = await self._explain_quality_score(product, score)
            elif dimension == ScoreDimension.RELEVANCE:
                explanations[dimension] = await self._explain_relevance_score(product, score)
            elif dimension == ScoreDimension.SELLER:
                explanations[dimension] = await self._explain_seller_score(product, score)
            elif dimension == ScoreDimension.POPULARITY:
                explanations[dimension] = await self._explain_popularity_score(product, score)
            elif dimension == ScoreDimension.RISK:
                explanations[dimension] = await self._explain_risk_score(product, score)
            elif dimension == ScoreDimension.COMPLETENESS:
                explanations[dimension] = await self._explain_completeness_score(product, score)
        
        return explanations
    
    async def _explain_price_score(self, product: ProductData, score: float) -> str:
        """解释价格得分"""
        if not product.price:
            return "无价格信息"
        
        if score >= 0.8:
            return f"价格合理（¥{product.price:,}），性价比高"
        elif score >= 0.6:
            return f"价格适中（¥{product.price:,}），可接受"
        elif score >= 0.4:
            return f"价格偏高（¥{product.price:,}），需谨慎考虑"
        else:
            return f"价格过高（¥{product.price:,}），不建议购买"
    
    async def _explain_quality_score(self, product: ProductData, score: float) -> str:
        """解释质量得分"""
        if score >= 0.8:
            return f"质量优秀，状态：{product.condition or '未知'}"
        elif score >= 0.6:
            return f"质量良好，状态：{product.condition or '未知'}"
        elif score >= 0.4:
            return f"质量一般，状态：{product.condition or '未知'}"
        else:
            return f"质量较差，状态：{product.condition or '未知'}"
    
    async def _explain_relevance_score(self, product: ProductData, score: float) -> str:
        """解释相关性得分"""
        if score >= 0.8:
            return "与搜索需求高度匹配"
        elif score >= 0.6:
            return "与搜索需求较好匹配"
        elif score >= 0.4:
            return "与搜索需求部分匹配"
        else:
            return "与搜索需求匹配度较低"
    
    async def _explain_seller_score(self, product: ProductData, score: float) -> str:
        """解释卖家得分"""
        if not product.seller_rating:
            return "无卖家评分信息"
        
        if score >= 0.8:
            return f"卖家信誉优秀（{product.seller_rating}★）"
        elif score >= 0.6:
            return f"卖家信誉良好（{product.seller_rating}★）"
        elif score >= 0.4:
            return f"卖家信誉一般（{product.seller_rating}★）"
        else:
            return f"卖家信誉较差（{product.seller_rating}★）"
    
    async def _explain_popularity_score(self, product: ProductData, score: float) -> str:
        """解释热度得分"""
        if score >= 0.8:
            return "商品热度很高"
        elif score >= 0.6:
            return "商品热度较高"
        elif score >= 0.4:
            return "商品热度一般"
        else:
            return "商品热度较低"
    
    async def _explain_risk_score(self, product: ProductData, score: float) -> str:
        """解释风险得分"""
        if score >= 0.8:
            return "购买风险很低"
        elif score >= 0.6:
            return "购买风险较低"
        elif score >= 0.4:
            return "购买风险中等"
        else:
            return "购买风险较高"
    
    async def _explain_completeness_score(self, product: ProductData, score: float) -> str:
        """解释完整性得分"""
        if score >= 0.8:
            return "商品信息完整详细"
        elif score >= 0.6:
            return "商品信息较为完整"
        elif score >= 0.4:
            return "商品信息基本完整"
        else:
            return "商品信息不够完整"
    
    async def _calculate_confidence(
        self,
        product: ProductData,
        dimension_scores: Dict[ScoreDimension, float]
    ) -> float:
        """计算置信度"""
        confidence = 0.5
        
        # 基于信息完整性
        if product.description:
            confidence += 0.15
        
        if product.images:
            confidence += 0.1
        
        if product.seller_rating:
            confidence += 0.1
        
        if product.condition:
            confidence += 0.1
        
        # 基于得分一致性
        scores = list(dimension_scores.values())
        if scores:
            score_variance = sum((s - sum(scores)/len(scores))**2 for s in scores) / len(scores)
            if score_variance < 0.1:
                confidence += 0.05
        
        return max(0.0, min(1.0, confidence))
    
    def _load_default_weights(self) -> Dict[ScoreDimension, float]:
        """加载默认权重"""
        return {
            ScoreDimension.PRICE: 0.25,
            ScoreDimension.QUALITY: 0.20,
            ScoreDimension.RELEVANCE: 0.20,
            ScoreDimension.SELLER: 0.15,
            ScoreDimension.POPULARITY: 0.05,
            ScoreDimension.RISK: 0.10,
            ScoreDimension.COMPLETENESS: 0.05
        }
    
    def _load_scoring_rules(self) -> Dict[str, Any]:
        """加载评分规则"""
        return {
            "price_thresholds": {
                "very_cheap": 500,
                "cheap": 2000,
                "moderate": 10000,
                "expensive": 50000
            },
            "quality_conditions": {
                "excellent": ["新品・未使用", "未使用に近い"],
                "good": ["目立った傷や汚れなし"],
                "fair": ["やや傷や汚れあり"],
                "poor": ["傷や汚れあり", "全体的に状態が悪い"]
            },
            "seller_rating_thresholds": {
                "excellent": 4.5,
                "good": 4.0,
                "fair": 3.5,
                "poor": 3.0
            }
        }
    
    def _load_normalization_params(self) -> Dict[ScoreDimension, Dict[str, float]]:
        """加载归一化参数"""
        return {
            ScoreDimension.PRICE: {"min": 0.0, "max": 1.0},
            ScoreDimension.QUALITY: {"min": 0.0, "max": 1.0},
            ScoreDimension.RELEVANCE: {"min": 0.0, "max": 1.0},
            ScoreDimension.SELLER: {"min": 0.0, "max": 1.0},
            ScoreDimension.POPULARITY: {"min": 0.0, "max": 1.0},
            ScoreDimension.RISK: {"min": 0.0, "max": 1.0},
            ScoreDimension.COMPLETENESS: {"min": 0.0, "max": 1.0}
        }
    
    def update_weights(self, new_weights: Dict[ScoreDimension, float]):
        """更新权重"""
        # 验证权重总和
        total_weight = sum(new_weights.values())
        if abs(total_weight - 1.0) > 0.01:
            raise ValueError(f"权重总和必须为1.0，当前为{total_weight}")
        
        self.default_weights.update(new_weights)
        logger.info(f"评分权重已更新: {new_weights}")
    
    def get_score_statistics(self) -> Dict[str, Any]:
        """获取评分统计"""
        if not self.scoring_history:
            return {"message": "无评分历史"}
        
        total_scores = [result.total_score for result in self.scoring_history]
        
        return {
            "total_evaluations": len(self.scoring_history),
            "average_score": sum(total_scores) / len(total_scores),
            "score_range": {
                "min": min(total_scores),
                "max": max(total_scores)
            },
            "dimension_averages": self._calculate_dimension_averages()
        }
    
    def _calculate_dimension_averages(self) -> Dict[str, float]:
        """计算各维度平均分"""
        if not self.scoring_history:
            return {}
        
        dimension_sums = {}
        for result in self.scoring_history:
            for dimension, score in result.normalized_scores.items():
                if dimension not in dimension_sums:
                    dimension_sums[dimension] = []
                dimension_sums[dimension].append(score)
        
        return {
            dimension.value: sum(scores) / len(scores)
            for dimension, scores in dimension_sums.items()
        }
    
    def get_info(self) -> Dict[str, Any]:
        """获取引擎信息"""
        return {
            "version": "1.0.0",
            "dimensions": [dim.value for dim in ScoreDimension],
            "default_weights": {dim.value: weight for dim, weight in self.default_weights.items()},
            "scoring_history_size": len(self.scoring_history)
        }