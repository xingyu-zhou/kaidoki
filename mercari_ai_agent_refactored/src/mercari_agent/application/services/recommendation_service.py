"""
推荐服务 - 最简版本
"""

import asyncio
import time
from typing import List, Optional
from dataclasses import dataclass

from ...domain.entities.product import ProductEntity
from ...domain.entities.query import QueryEntity
from ...shared.utils.logger_utils import get_logger

logger = get_logger(__name__)


@dataclass
class RecommendationResult:
    """推荐结果"""
    recommendations: List[ProductEntity]
    strategy_used: str
    processing_time: float
    total_analyzed: int


class RecommendationService:
    """推荐服务 - 集成LLM智能推荐"""
    
    def __init__(self, config, llm_service=None):
        self.config = config
        self.llm_service = llm_service
    
    async def recommend(
        self,
        products: List[ProductEntity],
        query: QueryEntity,
        limit: int = 10,
        strategy: str = "balanced"
    ) -> RecommendationResult:
        """生成推荐 - 集成LLM智能推荐"""
        start_time = time.time()
        
        # 🔧 关键修复：使用LLM进行智能推荐分析
        try:
            if self.llm_service and products:
                # 构建产品数据供LLM分析
                product_list = []
                for i, product in enumerate(products[:20]):  # 限制数量避免token超限
                    product_info = {
                        "index": i,
                        "title": product.title,
                        "price": product.price,
                        "condition": product.condition,
                        "seller_name": product.seller_name
                    }
                    product_list.append(product_info)
                
                # 构建LLM提示词进行智能推荐
                llm_prompt = f"""
作为智能购物助手，请基于用户查询分析以下商品并进行推荐排序：

用户查询: {query.original_query}
查询意图: {query.intent.value if query.intent else 'SEARCH'}
价格范围: {query.price_min or 0} - {query.price_max or '无限制'} 日元
推荐策略: {strategy}

商品列表:
{product_list}

请返回JSON格式的推荐结果，包含：
- recommended_indices: 推荐商品的索引列表（按优先级排序）
- reasoning: 推荐理由
- strategy_applied: 实际应用的策略

考虑因素：
1. 价格匹配度
2. 关键词相关性
3. 商品状态（新品vs中古）
4. 卖家信誉
5. 性价比

示例格式: {{"recommended_indices": [0, 2, 1], "reasoning": "基于价格和相关性排序", "strategy_applied": "balanced"}}
"""
                
                # 调用LLM服务
                logger.info(f"使用LLM服务进行智能推荐，分析 {len(product_list)} 个商品")
                llm_response = await self.llm_service.generate_response(llm_prompt)
                logger.info(f"LLM推荐响应: {llm_response.content[:200]}...")
                
                # 解析LLM响应
                import json
                try:
                    recommendation_data = json.loads(llm_response.content)
                    recommended_indices = recommendation_data.get('recommended_indices', [])
                    
                    # 按LLM推荐的顺序排列产品
                    llm_recommendations = []
                    for idx in recommended_indices:
                        if 0 <= idx < len(products):
                            llm_recommendations.append(products[idx])
                    
                    # 如果LLM推荐的产品不够，补充剩余产品
                    remaining_products = [p for i, p in enumerate(products) if i not in recommended_indices]
                    llm_recommendations.extend(remaining_products)
                    
                    recommendations = llm_recommendations[:limit]
                    strategy_used = recommendation_data.get('strategy_applied', strategy)
                    
                    logger.info(f"LLM智能推荐成功，返回 {len(recommendations)} 个推荐")
                    
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning(f"LLM推荐响应解析失败，使用备用逻辑: {e}")
                    recommendations = await self._fallback_recommend(products, query, limit, strategy)
                    strategy_used = strategy
            
            else:
                logger.info("LLM服务不可用或无商品数据，使用备用推荐逻辑")
                recommendations = await self._fallback_recommend(products, query, limit, strategy)
                strategy_used = strategy
        
        except Exception as e:
            logger.error(f"LLM推荐服务调用失败，使用备用逻辑: {e}")
            recommendations = await self._fallback_recommend(products, query, limit, strategy)
            strategy_used = strategy
        
        processing_time = time.time() - start_time
        
        return RecommendationResult(
            recommendations=recommendations,
            strategy_used=strategy_used,
            processing_time=processing_time,
            total_analyzed=len(products)
        )
    
    async def _fallback_recommend(
        self,
        products: List[ProductEntity],
        query: QueryEntity,
        limit: int,
        strategy: str
    ) -> List[ProductEntity]:
        """备用推荐逻辑"""
        # 基于价格过滤
        filtered_products = []
        for product in products:
            # 价格过滤
            if query.price_min and product.price and product.price < query.price_min:
                continue
            if query.price_max and product.price and product.price > query.price_max:
                continue
            
            # 关键词匹配
            if query.keywords:
                title_lower = product.title.lower()
                keyword_match = any(keyword.lower() in title_lower for keyword in query.keywords)
                if not keyword_match:
                    logger.debug(f"产品 '{product.title}' 没有关键词匹配，但通过价格过滤，仍然包含")
                filtered_products.append(product)
            else:
                filtered_products.append(product)
        
        # 简单排序：按价格升序
        filtered_products.sort(key=lambda p: p.price or 0)
        
        return filtered_products[:limit]