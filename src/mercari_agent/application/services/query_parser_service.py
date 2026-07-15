"""
查询解析服务 - 最简版本
"""

import asyncio
import time
from typing import List, Optional
from dataclasses import dataclass

from ...domain.entities.query import QueryEntity, QueryIntent, QueryComplexity
from ...shared.utils.logger_utils import get_logger

logger = get_logger(__name__)


@dataclass
class QueryParseResult:
    """查询解析结果"""
    query: QueryEntity
    confidence: float
    complexity: QueryComplexity
    processing_time: float


class QueryParserService:
    """查询解析服务 - 最简实现"""
    
    def __init__(self, config, llm_service):
        self.config = config
        self.llm_service = llm_service
    
    async def parse(self, query_text: str) -> QueryParseResult:
        """解析查询 - 集成LLM服务"""
        start_time = time.time()
        
        # 🔧 关键修复：集成LLM服务进行智能解析
        try:
            # 构建LLM提示词进行查询解析
            llm_prompt = f"""请分析以下购物查询，提取结构化信息，返回 JSON。
查询: {query_text}

字段：
- keywords: 用于在 Mercari 搜索的**简洁产品关键词**数组（产品名/型号/品牌/规格），通常 2~5 个词。
  **只放产品词**：不要放价格/预算/成色，也不要放 "探して/おすすめ/安い/コスパ/以内" 这类意图或修饰词，
  更不要放助词或整句片段。日文或通用名皆可。
- category: 产品类别（可空）
- brand: 品牌（可空）
- price_min / price_max: 价格（日元，整数或 null）
- intent: SEARCH / PURCHASE / COMPARE
- condition: 成色（可空）

示例1 查询: "iPhone 15 Pro Max 1TB 10万円以下"
示例1 响应: {{"keywords": ["iPhone", "15", "Pro", "Max", "1TB"], "category": "スマートフォン", "brand": "Apple", "price_min": null, "price_max": 100000, "intent": "SEARCH", "condition": null}}
示例2 查询: "AirPods Pro を1万円以内で探して、コスパのいいもの"
示例2 响应: {{"keywords": ["AirPods", "Pro"], "category": null, "brand": "Apple", "price_min": null, "price_max": 10000, "intent": "SEARCH", "condition": null}}
"""
            
            # 调用LLM服务进行智能解析
            logger.info(f"使用LLM服务解析查询: {query_text}")
            llm_response = await self.llm_service.generate_response(llm_prompt, response_format="json")
            logger.info(f"LLM解析响应: {llm_response.content[:200]}...")

            # 解析LLM响应（JSON 模式；仍防御性剥掉可能的 ```json 围栏）
            import json
            try:
                content = (llm_response.content or "").strip()
                if content.startswith("```"):
                    parts = content.split("```")
                    if len(parts) > 1:
                        content = parts[1]
                    if content.lstrip().lower().startswith("json"):
                        content = content.lstrip()[4:]
                parsed_data = json.loads(content)
                keywords = parsed_data.get('keywords', [])
                category = parsed_data.get('category')
                brand = parsed_data.get('brand')
                price_min = parsed_data.get('price_min')
                price_max = parsed_data.get('price_max')
                intent_str = parsed_data.get('intent', 'SEARCH')
                condition = parsed_data.get('condition')
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"LLM响应解析失败，使用备用解析: {e}")
                # 回退到基础解析逻辑
                keywords, price_min, price_max, category, brand, condition = await self._fallback_parse(query_text)
                intent_str = 'SEARCH'
        
        except Exception as e:
            logger.error(f"LLM服务调用失败，使用备用解析: {e}")
            # 回退到基础解析逻辑
            keywords, price_min, price_max, category, brand, condition = await self._fallback_parse(query_text)
            intent_str = 'SEARCH'
        
        # 转换intent字符串为枚举
        try:
            intent = QueryIntent[intent_str.upper()]
        except (KeyError, AttributeError):
            intent = QueryIntent.SEARCH
        
        # 清洗关键词：去掉误混入的价格/成色/意图短语与整句片段，只留简洁产品词
        cleaned_kw = self._clean_keywords(keywords)
        keywords = cleaned_kw or keywords

        # 创建查询实体
        query_entity = QueryEntity(
            original_query=query_text,
            normalized_query=query_text.lower(),
            keywords=keywords or [],
            intent=intent,
            category=category,
            brand=brand,
            price_min=price_min,
            price_max=price_max,
            condition=condition,
            complexity=QueryComplexity.MEDIUM if len(query_text.split()) > 3 else QueryComplexity.SIMPLE
        )
        
        processing_time = time.time() - start_time
        
        return QueryParseResult(
            query=query_entity,
            confidence=0.9,  # 使用LLM后提高置信度
            complexity=query_entity.complexity,
            processing_time=processing_time
        )
    
    async def _fallback_parse(self, query_text: str) -> tuple:
        """备用解析逻辑（原有的基础解析）"""
        # 改进的关键词提取 - 过滤价格条件词
        keywords = []
        for word in query_text.split():
            word = word.strip()
            if word and not self._is_price_condition(word):
                keywords.append(word)
        
        # 修复的日语价格提取逻辑
        price_min = None
        price_max = None
        
        # 处理价格范围 "X万円からY万円"
        import re
        range_pattern = r'(\d+)万?円?から(\d+)万?円?'
        range_match = re.search(range_pattern, query_text)
        if range_match:
            min_num = int(range_match.group(1))
            max_num = int(range_match.group(2))
            
            # 检查是否包含"万"单位
            min_text = range_match.group(0)[:len(range_match.group(1))+2]
            max_text = range_match.group(0)[len(range_match.group(1))+2:]
            
            price_min = min_num * 10000 if "万" in min_text else min_num
            price_max = max_num * 10000 if "万" in max_text else max_num
        else:
            # 处理单个价格条件
            for word in query_text.split():
                if "円" in word or "¥" in word:
                    try:
                        # 处理万単位
                        man_pattern = r'(\d+)万円?'
                        man_match = re.search(man_pattern, word)
                        if man_match:
                            base_num = int(man_match.group(1))
                            price_num = base_num * 10000
                        else:
                            # 处理普通数字
                            price_num = int(''.join(filter(str.isdigit, word)))
                        
                        # 检查条件词
                        if "以下" in query_text or "未満" in query_text:
                            if "以下" in word or "未満" in word:
                                price_max = price_num
                        elif "以上" in query_text:
                            if "以上" in word:
                                price_min = price_num
                        else:
                            # 如果没有明确条件，设为最大价格
                            if not price_max:
                                price_max = price_num
                    except Exception as e:
                        # 解析失败时忽略
                        pass
        
        # 基础类别和品牌推测
        category = None
        brand = None
        condition = None
        
        if any(word in query_text.lower() for word in ['iphone', 'アイフォン']):
            category = "スマートフォン"
            brand = "Apple"
        elif any(word in query_text.lower() for word in ['android', 'galaxy', 'pixel']):
            category = "スマートフォン"
        
        if "新品" in query_text:
            condition = "新品"
        elif "中古" in query_text:
            condition = "中古"
        
        return keywords, price_min, price_max, category, brand, condition

    def _clean_keywords(self, keywords) -> list:
        """过滤误混入关键词的价格/成色/意图短语与整句片段，只留简洁产品词。

        安全网：无论 LLM 是否遵守提示词，都保证送去搜索的是干净关键词。
        """
        cleaned = []
        for kw in keywords or []:
            if not isinstance(kw, str):
                continue
            w = kw.strip()
            if not w or self._is_price_condition(w):
                continue
            # 整句片段特征：含读点/助词/价格字，或过长（正常产品关键词都很短）
            if any(ch in w for ch in ("、", "。", "，", "を", "円")) or len(w) > 14:
                continue
            cleaned.append(w)
        return cleaned

    def _is_price_condition(self, word: str) -> bool:
        """判断是否为价格条件词"""
        price_patterns = [
            r'\d+万?円?以下',
            r'\d+万?円?以上',
            r'\d+万?円?未満',
            r'\d+万?円?まで',
            r'\d+万?円?から'
        ]
        
        import re
        for pattern in price_patterns:
            if re.search(pattern, word):
                return True
        return False