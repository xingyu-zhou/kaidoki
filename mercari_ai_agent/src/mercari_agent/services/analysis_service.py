"""
分析服务模块

该模块提供产品分析和评分功能。
基于多维度指标对产品进行综合评估和排名。

主要功能：
- 多维度产品分析
- 智能评分算法
- 市场趋势分析
- 价格合理性评估
- 质量评估和风险分析

Author: Mercari AI Agent Team
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import statistics
import math

from ..models.product import ProductData
from ..models.query import ParsedQuery
from ..analyzers.product_analyzer import ProductAnalyzer
from ..analyzers.scoring_engine import ScoringEngine
from ..utils.price_normalizer import PriceNormalizer
from ..utils.logger import get_logger
from ..config.settings import settings

logger = get_logger(__name__)


class AnalysisType(Enum):
    """分析类型枚举"""
    BASIC = "basic"              # 基础分析
    COMPREHENSIVE = "comprehensive"  # 综合分析
    MARKET_TREND = "market_trend"   # 市场趋势分析
    PRICE_ANALYSIS = "price_analysis"  # 价格分析
    QUALITY_ASSESSMENT = "quality_assessment"  # 质量评估


@dataclass
class AnalysisResult:
    """分析结果"""
    products: List[ProductData]
    analysis_type: AnalysisType
    market_summary: Dict[str, Any]
    price_analysis: Dict[str, Any]
    quality_distribution: Dict[str, Any]
    recommendations: List[str]
    processing_time: float
    metadata: Dict[str, Any]


@dataclass
class AnalysisContext:
    """分析上下文"""
    query: ParsedQuery
    analysis_type: AnalysisType = AnalysisType.COMPREHENSIVE
    include_market_trend: bool = True
    include_price_analysis: bool = True
    include_quality_assessment: bool = True
    risk_tolerance: float = 0.5  # 风险容忍度 0-1


class AnalysisService:
    """
    分析服务类
    
    负责对产品数据进行多维度分析和评估。
    提供智能评分、市场分析和购买建议。
    """
    
    def __init__(self):
        """初始化分析服务"""
        self.product_analyzer = ProductAnalyzer()
        self.scoring_engine = ScoringEngine()
        self.price_normalizer = PriceNormalizer()
        self.analysis_cache = {}
        self.market_data = {}
        
        logger.info("AnalysisService initialized")
    
    async def analyze(
        self,
        products: List[ProductData],
        context: AnalysisContext
    ) -> AnalysisResult:
        """
        分析产品数据
        
        Args:
            products: 产品数据列表
            context: 分析上下文
            
        Returns:
            AnalysisResult: 分析结果
            
        Raises:
            AnalysisError: 分析失败时抛出
        """
        if not products:
            raise AnalysisError("产品列表为空")
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            # 1. 基础数据预处理
            processed_products = await self._preprocess_products(products, context)
            
            # 2. 执行不同类型的分析
            analysis_results = {}
            
            if context.analysis_type in [AnalysisType.BASIC, AnalysisType.COMPREHENSIVE]:
                analysis_results["basic"] = await self._basic_analysis(processed_products, context)
            
            if context.include_market_trend:
                analysis_results["market_trend"] = await self._market_trend_analysis(processed_products, context)
            
            if context.include_price_analysis:
                analysis_results["price_analysis"] = await self._price_analysis(processed_products, context)
            
            if context.include_quality_assessment:
                analysis_results["quality_assessment"] = await self._quality_assessment(processed_products, context)
            
            # 3. 综合评分
            scored_products = await self._score_products(processed_products, context, analysis_results)
            
            # 4. 生成市场摘要
            market_summary = await self._generate_market_summary(scored_products, context)
            
            # 5. 生成推荐建议
            recommendations = await self._generate_recommendations(scored_products, context, analysis_results)
            
            # 6. 构建结果
            processing_time = asyncio.get_event_loop().time() - start_time
            result = AnalysisResult(
                products=scored_products,
                analysis_type=context.analysis_type,
                market_summary=market_summary,
                price_analysis=analysis_results.get("price_analysis", {}),
                quality_distribution=analysis_results.get("quality_assessment", {}),
                recommendations=recommendations,
                processing_time=processing_time,
                metadata={
                    "query": context.query.original_query,
                    "analyzed_count": len(processed_products),
                    "analysis_components": list(analysis_results.keys()),
                    "risk_tolerance": context.risk_tolerance
                }
            )
            
            logger.info(f"产品分析完成: {len(processed_products)} 个产品，耗时 {processing_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"产品分析失败: {e}")
            raise AnalysisError(f"分析执行失败: {e}")
    
    async def _preprocess_products(
        self,
        products: List[ProductData],
        context: AnalysisContext
    ) -> List[ProductData]:
        """
        预处理产品数据
        
        Args:
            products: 原始产品数据
            context: 分析上下文
            
        Returns:
            List[ProductData]: 预处理后的产品数据
        """
        processed_products = []
        
        for product in products:
            try:
                # 价格规范化
                if product.price:
                    product.price = await self.price_normalizer.normalize(product.price)
                
                # 标题清洗
                if product.title:
                    product.title = await self._clean_title(product.title)
                
                # 描述处理
                if product.description:
                    product.description = await self._clean_description(product.description)
                
                # 添加分析元数据
                product.analysis_metadata = {
                    "processed_at": datetime.now().isoformat(),
                    "processor_version": "1.0.0"
                }
                
                processed_products.append(product)
                
            except Exception as e:
                logger.warning(f"产品预处理失败: {e}")
                continue
        
        return processed_products
    
    async def _basic_analysis(
        self,
        products: List[ProductData],
        context: AnalysisContext
    ) -> Dict[str, Any]:
        """
        基础分析
        
        Args:
            products: 产品数据列表
            context: 分析上下文
            
        Returns:
            Dict[str, Any]: 基础分析结果
        """
        prices = [p.price for p in products if p.price]
        
        if not prices:
            return {"error": "没有有效的价格数据"}
        
        return {
            "total_products": len(products),
            "price_stats": {
                "min": min(prices),
                "max": max(prices),
                "mean": statistics.mean(prices),
                "median": statistics.median(prices),
                "std_dev": statistics.stdev(prices) if len(prices) > 1 else 0
            },
            "condition_distribution": await self._analyze_condition_distribution(products),
            "seller_rating_stats": await self._analyze_seller_ratings(products),
            "availability_stats": await self._analyze_availability(products)
        }
    
    async def _market_trend_analysis(
        self,
        products: List[ProductData],
        context: AnalysisContext
    ) -> Dict[str, Any]:
        """
        市场趋势分析
        
        Args:
            products: 产品数据列表
            context: 分析上下文
            
        Returns:
            Dict[str, Any]: 市场趋势分析结果
        """
        # 分析价格趋势
        price_trend = await self._analyze_price_trend(products)
        
        # 分析受欢迎程度
        popularity_analysis = await self._analyze_popularity(products)
        
        # 分析供需关系
        supply_demand = await self._analyze_supply_demand(products, context)
        
        return {
            "price_trend": price_trend,
            "popularity_analysis": popularity_analysis,
            "supply_demand": supply_demand,
            "market_activity": await self._analyze_market_activity(products)
        }
    
    async def _price_analysis(
        self,
        products: List[ProductData],
        context: AnalysisContext
    ) -> Dict[str, Any]:
        """
        价格分析
        
        Args:
            products: 产品数据列表
            context: 分析上下文
            
        Returns:
            Dict[str, Any]: 价格分析结果
        """
        prices = [p.price for p in products if p.price]
        
        if not prices:
            return {"error": "没有有效的价格数据"}
        
        # 价格分布分析
        price_distribution = await self._analyze_price_distribution(prices)
        
        # 价格合理性评估
        price_reasonableness = await self._evaluate_price_reasonableness(products, context)
        
        # 性价比分析
        value_analysis = await self._analyze_value_proposition(products, context)
        
        return {
            "price_distribution": price_distribution,
            "price_reasonableness": price_reasonableness,
            "value_analysis": value_analysis,
            "price_recommendations": await self._generate_price_recommendations(products, context)
        }
    
    async def _quality_assessment(
        self,
        products: List[ProductData],
        context: AnalysisContext
    ) -> Dict[str, Any]:
        """
        质量评估
        
        Args:
            products: 产品数据列表
            context: 分析上下文
            
        Returns:
            Dict[str, Any]: 质量评估结果
        """
        # 状态分布
        condition_analysis = await self._analyze_condition_distribution(products)
        
        # 卖家信誉分析
        seller_analysis = await self._analyze_seller_quality(products)
        
        # 描述质量分析
        description_analysis = await self._analyze_description_quality(products)
        
        # 风险评估
        risk_assessment = await self._assess_purchase_risks(products, context)
        
        return {
            "condition_analysis": condition_analysis,
            "seller_analysis": seller_analysis,
            "description_analysis": description_analysis,
            "risk_assessment": risk_assessment,
            "quality_score_distribution": await self._calculate_quality_scores(products)
        }
    
    async def _score_products(
        self,
        products: List[ProductData],
        context: AnalysisContext,
        analysis_results: Dict[str, Any]
    ) -> List[ProductData]:
        """
        为产品评分
        
        Args:
            products: 产品数据列表
            context: 分析上下文
            analysis_results: 分析结果
            
        Returns:
            List[ProductData]: 评分后的产品数据
        """
        scored_products = []
        
        for product in products:
            try:
                # 使用评分引擎计算分数
                scores = await self.scoring_engine.score_product(product, context.query)
                
                # 基于分析结果调整分数
                adjusted_scores = await self._adjust_scores_based_on_analysis(
                    scores, product, analysis_results, context
                )
                
                # 计算最终分数
                final_score = await self._calculate_final_score(adjusted_scores, context)
                
                # 添加评分信息
                product.analysis_scores = adjusted_scores
                product.final_score = final_score
                product.score_breakdown = await self._generate_score_breakdown(adjusted_scores)
                
                scored_products.append(product)
                
            except Exception as e:
                logger.warning(f"产品评分失败: {e}")
                continue
        
        # 按分数排序
        scored_products.sort(key=lambda p: p.final_score, reverse=True)
        
        return scored_products
    
    async def _generate_market_summary(
        self,
        products: List[ProductData],
        context: AnalysisContext
    ) -> Dict[str, Any]:
        """
        生成市场摘要
        
        Args:
            products: 产品数据列表
            context: 分析上下文
            
        Returns:
            Dict[str, Any]: 市场摘要
        """
        prices = [p.price for p in products if p.price]
        
        if not prices:
            return {"error": "没有有效的价格数据"}
        
        return {
            "market_overview": {
                "total_listings": len(products),
                "price_range": {
                    "min": min(prices),
                    "max": max(prices),
                    "average": statistics.mean(prices)
                },
                "market_activity": "活跃" if len(products) > 20 else "一般"
            },
            "competitive_landscape": await self._analyze_competitive_landscape(products),
            "buying_opportunities": await self._identify_buying_opportunities(products, context),
            "market_insights": await self._generate_market_insights(products, context)
        }
    
    async def _generate_recommendations(
        self,
        products: List[ProductData],
        context: AnalysisContext,
        analysis_results: Dict[str, Any]
    ) -> List[str]:
        """
        生成推荐建议
        
        Args:
            products: 产品数据列表
            context: 分析上下文
            analysis_results: 分析结果
            
        Returns:
            List[str]: 推荐建议列表
        """
        recommendations = []
        
        # 基于价格分析的建议
        if "price_analysis" in analysis_results:
            price_recs = await self._generate_price_based_recommendations(
                products, analysis_results["price_analysis"]
            )
            recommendations.extend(price_recs)
        
        # 基于质量评估的建议
        if "quality_assessment" in analysis_results:
            quality_recs = await self._generate_quality_based_recommendations(
                products, analysis_results["quality_assessment"]
            )
            recommendations.extend(quality_recs)
        
        # 基于市场趋势的建议
        if "market_trend" in analysis_results:
            trend_recs = await self._generate_trend_based_recommendations(
                products, analysis_results["market_trend"]
            )
            recommendations.extend(trend_recs)
        
        # 基于风险评估的建议
        risk_recs = await self._generate_risk_based_recommendations(products, context)
        recommendations.extend(risk_recs)
        
        return recommendations[:10]  # 限制推荐数量
    
    # 辅助方法
    async def _clean_title(self, title: str) -> str:
        """清洗标题"""
        # 移除多余空格和特殊字符
        import re
        cleaned = re.sub(r'\s+', ' ', title.strip())
        return cleaned
    
    async def _clean_description(self, description: str) -> str:
        """清洗描述"""
        # 移除HTML标签和多余空格
        import re
        cleaned = re.sub(r'<[^>]+>', '', description)
        cleaned = re.sub(r'\s+', ' ', cleaned.strip())
        return cleaned
    
    async def _analyze_condition_distribution(self, products: List[ProductData]) -> Dict[str, Any]:
        """分析商品状态分布"""
        conditions = {}
        for product in products:
            condition = product.condition or "未知"
            conditions[condition] = conditions.get(condition, 0) + 1
        
        total = len(products)
        return {
            "distribution": conditions,
            "percentages": {k: v/total*100 for k, v in conditions.items()}
        }
    
    async def _analyze_seller_ratings(self, products: List[ProductData]) -> Dict[str, Any]:
        """分析卖家评分"""
        ratings = [p.seller_rating for p in products if p.seller_rating]
        
        if not ratings:
            return {"error": "没有卖家评分数据"}
        
        return {
            "average": statistics.mean(ratings),
            "median": statistics.median(ratings),
            "min": min(ratings),
            "max": max(ratings),
            "high_rating_percentage": len([r for r in ratings if r >= 4.5]) / len(ratings) * 100
        }
    
    async def _analyze_availability(self, products: List[ProductData]) -> Dict[str, Any]:
        """分析商品可用性"""
        total = len(products)
        sold_count = len([p for p in products if p.is_sold])
        
        return {
            "total_listings": total,
            "sold_count": sold_count,
            "available_count": total - sold_count,
            "sell_through_rate": sold_count / total * 100 if total > 0 else 0
        }
    
    async def _adjust_scores_based_on_analysis(
        self,
        scores: Dict[str, float],
        product: ProductData,
        analysis_results: Dict[str, Any],
        context: AnalysisContext
    ) -> Dict[str, float]:
        """基于分析结果调整分数"""
        adjusted_scores = scores.copy()
        
        # 基于市场趋势调整
        if "market_trend" in analysis_results:
            market_trend = analysis_results["market_trend"]
            if market_trend.get("price_trend", {}).get("direction") == "increasing":
                adjusted_scores["price_score"] *= 1.1
        
        # 基于质量评估调整
        if "quality_assessment" in analysis_results:
            quality_data = analysis_results["quality_assessment"]
            risk_level = quality_data.get("risk_assessment", {}).get("overall_risk", "medium")
            
            if risk_level == "low":
                adjusted_scores["quality_score"] *= 1.2
            elif risk_level == "high":
                adjusted_scores["quality_score"] *= 0.8
        
        return adjusted_scores
    
    async def _calculate_final_score(
        self,
        scores: Dict[str, float],
        context: AnalysisContext
    ) -> float:
        """计算最终分数"""
        weights = {
            "price_score": 0.3,
            "quality_score": 0.25,
            "relevance_score": 0.2,
            "seller_score": 0.15,
            "popularity_score": 0.1
        }
        
        final_score = 0.0
        for score_type, score_value in scores.items():
            weight = weights.get(score_type, 0.1)
            final_score += score_value * weight
        
        return min(10.0, max(0.0, final_score))
    
    async def _generate_score_breakdown(self, scores: Dict[str, float]) -> Dict[str, str]:
        """生成分数breakdown"""
        breakdown = {}
        for score_type, score_value in scores.items():
            if score_value >= 8.0:
                breakdown[score_type] = "优秀"
            elif score_value >= 6.0:
                breakdown[score_type] = "良好"
            elif score_value >= 4.0:
                breakdown[score_type] = "一般"
            else:
                breakdown[score_type] = "较差"
        
        return breakdown
    
    def get_analysis_stats(self) -> Dict[str, Any]:
        """获取分析统计信息"""
        return {
            "cache_size": len(self.analysis_cache),
            "market_data_size": len(self.market_data),
            "analyzer_info": {
                "product_analyzer": self.product_analyzer.get_info(),
                "scoring_engine": self.scoring_engine.get_info()
            }
        }

    async def generate_recommendations(
        self,
        user_preferences: Dict[str, Any],
        search_results: List[ProductData] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        生成商品推荐结果
        
        Args:
            user_preferences: 用户偏好设置
            search_results: 搜索结果产品列表
            **kwargs: 额外参数
            
        Returns:
            List[Dict[str, Any]]: 推荐结果列表
            
        Raises:
            AnalysisError: 推荐生成失败时抛出
        """
        try:
            start_time = asyncio.get_event_loop().time()
            
            # 1. 处理空搜索结果的情况
            if not search_results:
                logger.warning("搜索结果为空，无法生成推荐")
                return []
            
            # 2. 验证用户偏好
            if not user_preferences:
                logger.warning("用户偏好为空，使用默认设置")
                user_preferences = self._get_default_preferences()
            
            # 3. 创建分析上下文
            analysis_context = self._create_analysis_context_from_preferences(user_preferences)
            
            # 4. 对产品进行分析和评分
            analyzed_products = []
            for product in search_results:
                try:
                    # 使用ProductAnalyzer进行分析
                    analysis_result = await self.product_analyzer.analyze_product(
                        product,
                        analysis_context.query if hasattr(analysis_context, 'query') else None
                    )
                    
                    # 使用ScoringEngine进行评分
                    score_result = await self.scoring_engine.score_product(
                        product,
                        analysis_context.query if hasattr(analysis_context, 'query') else None
                    )
                    
                    # 基于用户偏好调整分数
                    adjusted_score = await self._adjust_score_by_preferences(
                        score_result, product, user_preferences
                    )
                    
                    # 添加分析信息到产品
                    product.analysis_scores = {
                        dim.value: score for dim, score in score_result.normalized_scores.items()
                    }
                    product.final_score = adjusted_score
                    product.analysis_metadata = {
                        "analysis_result": analysis_result,
                        "score_result": score_result,
                        "user_preferences_applied": True
                    }
                    
                    analyzed_products.append(product)
                    
                except Exception as e:
                    logger.warning(f"产品分析失败: {e}")
                    continue
            
            # 5. 按评分排序
            analyzed_products.sort(key=lambda p: p.final_score, reverse=True)
            
            # 6. 生成推荐结果
            recommendations = []
            for i, product in enumerate(analyzed_products[:kwargs.get('max_results', 10)]):
                recommendation = {
                    "rank": i + 1,
                    "product_id": product.url or f"product_{i}",
                    "title": product.title,
                    "price": product.price,
                    "url": product.url,
                    "condition": product.condition,
                    "seller_name": product.seller_name,
                    "seller_rating": product.seller_rating,
                    "final_score": product.final_score,
                    "score_breakdown": product.analysis_scores,
                    "recommendation_reason": await self._generate_recommendation_reason(
                        product, user_preferences
                    ),
                    "pros": await self._extract_product_pros(product),
                    "cons": await self._extract_product_cons(product),
                    "match_score": await self._calculate_preference_match_score(
                        product, user_preferences
                    )
                }
                recommendations.append(recommendation)
            
            # 7. 添加推荐统计信息
            processing_time = asyncio.get_event_loop().time() - start_time
            
            logger.info(f"生成推荐完成: {len(recommendations)} 个推荐，耗时 {processing_time:.2f}s")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"生成推荐失败: {e}")
            raise AnalysisError(f"推荐生成失败: {e}")
    
    def _get_default_preferences(self) -> Dict[str, Any]:
        """获取默认用户偏好"""
        return {
            "price_weight": 0.3,
            "quality_weight": 0.25,
            "seller_weight": 0.15,
            "condition_weight": 0.15,
            "popularity_weight": 0.1,
            "max_price": None,
            "min_price": None,
            "preferred_conditions": [],
            "preferred_categories": [],
            "risk_tolerance": 0.5
        }
    
    def _create_analysis_context_from_preferences(self, user_preferences: Dict[str, Any]) -> AnalysisContext:
        """从用户偏好创建分析上下文"""
        # 创建一个虚拟的ParsedQuery对象
        from ..models.query import ParsedQuery
        
        query = ParsedQuery(
            original_query="user_preferences",
            normalized_query="user_preferences",
            keywords=user_preferences.get("keywords", []),
            price_min=user_preferences.get("min_price"),
            price_max=user_preferences.get("max_price"),
            category=user_preferences.get("preferred_categories", [None])[0] if user_preferences.get("preferred_categories") else None,
            condition=user_preferences.get("preferred_conditions", [None])[0] if user_preferences.get("preferred_conditions") else None
        )
        
        return AnalysisContext(
            query=query,
            risk_tolerance=user_preferences.get("risk_tolerance", 0.5),
            analysis_type=AnalysisType.COMPREHENSIVE
        )
    
    async def _adjust_score_by_preferences(
        self,
        score_result,
        product: ProductData,
        user_preferences: Dict[str, Any]
    ) -> float:
        """基于用户偏好调整评分"""
        # 获取基础分数
        base_score = score_result.total_score
        
        # 应用用户偏好权重
        adjusted_score = 0.0
        total_weight = 0.0
        
        # 价格权重
        if "price_weight" in user_preferences:
            price_score = score_result.normalized_scores.get("price", 0.5)
            weight = user_preferences["price_weight"]
            adjusted_score += price_score * weight
            total_weight += weight
        
        # 质量权重
        if "quality_weight" in user_preferences:
            quality_score = score_result.normalized_scores.get("quality", 0.5)
            weight = user_preferences["quality_weight"]
            adjusted_score += quality_score * weight
            total_weight += weight
        
        # 卖家权重
        if "seller_weight" in user_preferences:
            seller_score = score_result.normalized_scores.get("seller", 0.5)
            weight = user_preferences["seller_weight"]
            adjusted_score += seller_score * weight
            total_weight += weight
        
        # 其他维度权重
        for dim_name, dim_obj in [
            ("condition_weight", "quality"),
            ("popularity_weight", "popularity")
        ]:
            if dim_name in user_preferences:
                dim_score = score_result.normalized_scores.get(dim_obj, 0.5)
                weight = user_preferences[dim_name]
                adjusted_score += dim_score * weight
                total_weight += weight
        
        # 归一化到0-10分
        if total_weight > 0:
            final_score = (adjusted_score / total_weight) * 10.0
        else:
            final_score = base_score
        
        # 应用价格偏好额外调整
        if user_preferences.get("max_price") and product.price:
            if product.price > user_preferences["max_price"]:
                final_score *= 0.8  # 超出预算的产品降分
        
        return max(0.0, min(10.0, final_score))
    
    async def _generate_recommendation_reason(
        self,
        product: ProductData,
        user_preferences: Dict[str, Any]
    ) -> str:
        """生成推荐理由"""
        reasons = []
        
        # 价格优势
        if product.price and user_preferences.get("max_price"):
            if product.price < user_preferences["max_price"] * 0.8:
                reasons.append("价格优惠")
        
        # 质量优势
        if product.condition and product.condition in ["新品・未使用", "未使用に近い"]:
            reasons.append("商品状态良好")
        
        # 卖家优势
        if product.seller_rating and product.seller_rating >= 4.5:
            reasons.append("卖家信誉优秀")
        
        # 完整性优势
        if product.description and len(product.description) > 100:
            reasons.append("商品描述详细")
        
        # 图片优势
        if product.images and len(product.images) >= 3:
            reasons.append("图片丰富")
        
        return "、".join(reasons) if reasons else "综合评分较高"
    
    async def _extract_product_pros(self, product: ProductData) -> List[str]:
        """提取产品优点"""
        pros = []
        
        if product.condition and product.condition in ["新品・未使用", "未使用に近い"]:
            pros.append("商品状态优秀")
        
        if product.seller_rating and product.seller_rating >= 4.5:
            pros.append("卖家信誉良好")
        
        if product.images and len(product.images) >= 3:
            pros.append("图片展示充分")
        
        if product.description and len(product.description) > 100:
            pros.append("描述详细完整")
        
        return pros
    
    async def _extract_product_cons(self, product: ProductData) -> List[str]:
        """提取产品缺点"""
        cons = []
        
        if product.condition and "傷" in product.condition:
            cons.append("商品有瑕疵")
        
        if product.seller_rating and product.seller_rating < 4.0:
            cons.append("卖家评分较低")
        
        if not product.images:
            cons.append("缺少商品图片")
        
        if not product.description or len(product.description) < 50:
            cons.append("商品描述不够详细")
        
        return cons
    
    async def _calculate_preference_match_score(
        self,
        product: ProductData,
        user_preferences: Dict[str, Any]
    ) -> float:
        """计算偏好匹配分数"""
        match_score = 0.0
        total_factors = 0
        
        # 价格匹配
        if product.price and user_preferences.get("max_price"):
            if product.price <= user_preferences["max_price"]:
                match_score += 1.0
            else:
                match_score += max(0.0, 1.0 - (product.price - user_preferences["max_price"]) / user_preferences["max_price"])
            total_factors += 1
        
        # 类别匹配
        if user_preferences.get("preferred_categories") and product.category:
            if product.category in user_preferences["preferred_categories"]:
                match_score += 1.0
            total_factors += 1
        
        # 状态匹配
        if user_preferences.get("preferred_conditions") and product.condition:
            if product.condition in user_preferences["preferred_conditions"]:
                match_score += 1.0
            total_factors += 1
        
        return match_score / total_factors if total_factors > 0 else 0.5


class AnalysisError(Exception):
    """分析异常"""
    pass


# 其他分析相关的辅助函数可以在这里继续添加
async def _analyze_price_trend(products: List[ProductData]) -> Dict[str, Any]:
    """分析价格趋势"""
    # 实现价格趋势分析逻辑
    return {"direction": "stable", "confidence": 0.7}


async def _analyze_popularity(products: List[ProductData]) -> Dict[str, Any]:
    """分析受欢迎程度"""
    # 实现受欢迎程度分析逻辑
    return {"popularity_score": 0.6, "trending_items": []}


async def _analyze_supply_demand(products: List[ProductData], context: AnalysisContext) -> Dict[str, Any]:
    """分析供需关系"""
    # 实现供需分析逻辑
    return {"supply_level": "medium", "demand_level": "high"}