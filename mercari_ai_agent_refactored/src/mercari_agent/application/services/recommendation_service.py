"""
推荐服务 - 最简版本
"""

import asyncio
import json
import re
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
    reasoning: Optional[str] = None


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
        reasoning: Optional[str] = None

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
                
                # 调用LLM服务 —— 启用结构化 JSON 输出，避免围栏/散文导致解析失败
                logger.info(f"使用LLM服务进行智能推荐，分析 {len(product_list)} 个商品")
                llm_response = await self.llm_service.generate_response(
                    llm_prompt, response_format="json"
                )
                logger.info(f"LLM推荐响应: {llm_response.content[:200]}...")

                # 解析LLM响应（防御性提取，容忍 ```json 围栏与前后散文）
                recommendation_data = self._extract_json(llm_response.content)
                if recommendation_data is not None:
                    recommended_indices = recommendation_data.get('recommended_indices', [])
                    # 只保留合法的整数索引，避免脏数据破坏后续逻辑
                    valid_indices = [
                        idx for idx in recommended_indices
                        if isinstance(idx, int) and 0 <= idx < len(products)
                    ]

                    # 按LLM推荐的顺序排列产品
                    llm_recommendations = [products[idx] for idx in valid_indices]

                    # 如果LLM推荐的产品不够，补充剩余产品
                    seen_indices = set(valid_indices)
                    remaining_products = [
                        p for i, p in enumerate(products) if i not in seen_indices
                    ]
                    llm_recommendations.extend(remaining_products)

                    recommendations = llm_recommendations[:limit]
                    strategy_used = recommendation_data.get('strategy_applied', strategy)
                    reasoning = recommendation_data.get('reasoning')

                    logger.info(f"LLM智能推荐成功，返回 {len(recommendations)} 个推荐")

                else:
                    logger.warning("LLM推荐响应解析失败，使用备用逻辑")
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
            total_analyzed=len(products),
            reasoning=reasoning
        )
    
    async def _fallback_recommend(
        self,
        products: List[ProductEntity],
        query: QueryEntity,
        limit: int,
        strategy: str
    ) -> List[ProductEntity]:
        """备用推荐逻辑

        先按价格范围过滤，再把命中关键词的商品排在前面、未命中的追加在后，
        避免关键词不相关的商品被无差别混入结果靠前的位置。
        """
        keywords = [k.lower() for k in (query.keywords or []) if k]

        # 基于价格过滤，并按关键词是否命中分成两组
        matched: List[ProductEntity] = []
        unmatched: List[ProductEntity] = []
        for product in products:
            # 价格过滤
            if query.price_min and product.price and product.price < query.price_min:
                continue
            if query.price_max and product.price and product.price > query.price_max:
                continue

            # 关键词匹配：命中优先，未命中保留但排在后面
            if keywords:
                title_lower = (product.title or "").lower()
                if any(keyword in title_lower for keyword in keywords):
                    matched.append(product)
                else:
                    logger.debug(f"产品 '{product.title}' 没有关键词匹配，追加到结果末尾")
                    unmatched.append(product)
            else:
                matched.append(product)

        # 组内按价格升序排序，命中组整体排在未命中组前面
        matched.sort(key=lambda p: p.price or 0)
        unmatched.sort(key=lambda p: p.price or 0)

        return (matched + unmatched)[:limit]

    def _extract_json(self, content: str) -> Optional[dict]:
        """从 LLM 响应文本中稳健地提取 JSON 对象。

        依次尝试：
        1. 剥掉 ```json / ``` 代码围栏后直接解析；
        2. 用正则抓取最外层的 ``{ ... }`` 再解析（容忍前后散文）。

        任何一步成功即返回对应的 dict，全部失败返回 None。
        """
        if not content:
            return None

        text = content.strip()

        # 1. 剥掉代码围栏（```json ... ``` 或 ``` ... ```）
        if text.startswith("```"):
            fence = re.match(r"^```[a-zA-Z0-9_-]*\s*\n?", text)
            if fence:
                text = text[fence.end():]
            if text.rstrip().endswith("```"):
                text = text.rstrip()[:-3]
            text = text.strip()

        # 候选串：优先整段，其次正则抓取的最外层花括号对象
        candidates = [text]
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            candidates.append(brace_match.group(0))

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(parsed, dict):
                return parsed

        return None