"""
查询解析器模块

该模块负责解析用户的日语购物查询，提取结构化的搜索意图。
使用LLM进行自然语言理解，结合日语NLP技术。

主要功能：
- 日语文本预处理和规范化
- 使用LLM提取搜索意图
- 生成结构化的查询对象
- 处理复杂的日语表达和模糊查询

Author: Mercari AI Agent Team
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from ..models.query import ParsedQuery, SearchQuery, QueryIntent
from ..services.llm_service import LLMService
from ..prompts.query_prompts import QueryPrompts
from ..prompts.system_prompts import SystemPrompts
from ..utils.japanese_processor import JapaneseProcessor
from ..utils.logger import get_logger
from ..config.settings import settings

logger = get_logger(__name__)


class QueryComplexity(Enum):
    """查询复杂度枚举"""
    SIMPLE = "simple"      # 简单关键词查询
    MODERATE = "moderate"  # 包含条件的查询
    COMPLEX = "complex"    # 复杂多条件查询


@dataclass
class ParsedQueryResult:
    """查询解析结果"""
    query: ParsedQuery
    complexity: QueryComplexity
    confidence: float
    processing_time: float
    refined_query: str = ""
    category: str = ""
    intent: str = ""
    price_range: Optional[Dict[str, Any]] = None
    debug_info: Optional[Dict[str, Any]] = None


class QueryParser:
    """
    查询解析器类
    
    负责解析用户的日语购物查询，提取结构化信息。
    使用LLM进行自然语言理解，结合专业的日语处理技术。
    """
    
    def __init__(self, llm_service: LLMService):
        """
        初始化查询解析器
        
        Args:
            llm_service: LLM服务实例
        """
        self.llm_service = llm_service
        self.japanese_processor = JapaneseProcessor()
        self.category_mapping = self._load_category_mapping()
        self.condition_mapping = self._load_condition_mapping()
        
        logger.info("QueryParser initialized")
    
    async def parse(self, user_query: str) -> ParsedQueryResult:
        """
        解析用户查询
        
        Args:
            user_query: 用户输入的日语查询
            
        Returns:
            ParsedQueryResult: 解析结果
            
        Raises:
            ValueError: 查询为空或格式错误
            LLMServiceError: LLM服务调用失败
        """
        if not user_query or not user_query.strip():
            raise ValueError("用户查询不能为空")
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            # 1. 日语预处理
            processed_text = await self.japanese_processor.process(user_query)
            logger.debug(f"日语预处理完成: {processed_text.normalized}")
            
            # 2. 判断查询复杂度
            complexity = self._assess_complexity(processed_text)
            logger.debug(f"查询复杂度: {complexity.value}")
            
            # 3. 构建解析提示
            prompt = self._build_parsing_prompt(processed_text, complexity)
            
            # 4. 使用LLM进行意图提取
            llm_response = await self._extract_intent_with_llm(user_query, processed_text, complexity)
            
            # 5. 构建解析结果
            parsed_query = self._build_parsed_query(llm_response, processed_text)
            
            # 6. 验证和后处理
            validated_query = self._validate_and_enhance(parsed_query)
            
            processing_time = asyncio.get_event_loop().time() - start_time
            
            result = ParsedQueryResult(
                query=validated_query,
                complexity=complexity,
                confidence=llm_response.get("confidence", 0.8),
                processing_time=processing_time,
                refined_query=validated_query.normalized_query or user_query,  # 添加此行
                category=validated_query.category,
                intent=validated_query.intent.value if validated_query.intent else "search",
                price_range={"min": validated_query.price_min, "max": validated_query.price_max},
                debug_info={
                    "original_query": user_query,
                    "processed_text": processed_text.normalized,
                    "llm_response": llm_response
                } if settings.debug else None
            )
            
            logger.info(f"查询解析完成: {user_query[:50]}... -> {validated_query.keywords}")
            return result
            
        except Exception as e:
            logger.error(f"查询解析失败: {e}")
            raise
    
    def _assess_complexity(self, processed_text) -> QueryComplexity:
        """
        评估查询复杂度
        
        Args:
            processed_text: 预处理后的文本
            
        Returns:
            QueryComplexity: 复杂度枚举
        """
        text = processed_text.normalized
        tokens = processed_text.tokens
        
        # 简单启发式规则
        if len(tokens) <= 3:
            return QueryComplexity.SIMPLE
        elif len(tokens) <= 8 and not any(word in text for word in ['価格', '値段', '条件', '状態']):
            return QueryComplexity.MODERATE
        else:
            return QueryComplexity.COMPLEX
    
    def _build_parsing_prompt(self, processed_text, complexity: QueryComplexity) -> str:
        """
        构建LLM解析提示
        
        Args:
            processed_text: 预处理后的文本
            complexity: 查询复杂度
            
        Returns:
            str: 构建的提示文本
        """
        if complexity == QueryComplexity.COMPLEX:
            return QueryPrompts.get_query_analysis_prompt(
                query=processed_text.normalized,
                context=f"原始查询: {processed_text.original}\n分词结果: {processed_text.tokens}",
                complexity="complex"
            )
        else:
            return QueryPrompts.get_query_analysis_prompt(
                query=processed_text.normalized,
                complexity="simple"
            )
    
    async def _extract_intent_with_llm(self, user_query: str, processed_text, complexity: QueryComplexity) -> Dict[str, Any]:
        """
        使用LLM提取查询意图
        
        Args:
            user_query: 用户原始查询
            processed_text: 预处理后的文本
            complexity: 查询复杂度
            
        Returns:
            Dict[str, Any]: LLM返回的解析结果
        """
        try:
            # 首先进行意图分类
            intent_prompt = QueryPrompts.get_intent_classification_prompt(user_query)
            intent_response = await self.llm_service.generate_response(
                prompt=intent_prompt,
                max_tokens=300,
                temperature=0.2,
                response_format="json"
            )
            
            # 解析意图分类结果
            import json
            intent_result = json.loads(intent_response.content)
            
            # 根据复杂度选择解析策略
            if complexity == QueryComplexity.COMPLEX:
                analysis_prompt = QueryPrompts.get_query_analysis_prompt(
                    query=processed_text.normalized,
                    context=f"原始查询: {processed_text.original}\n分词结果: {processed_text.tokens}",
                    complexity="complex"
                )
            else:
                analysis_prompt = QueryPrompts.get_query_analysis_prompt(
                    query=processed_text.normalized,
                    complexity="simple"
                )
            
            # 进行详细查询分析
            analysis_response = await self.llm_service.generate_response(
                prompt=analysis_prompt,
                max_tokens=500,
                temperature=0.3,
                response_format="json"
            )
            
            # 解析分析结果
            analysis_result = json.loads(analysis_response.content)
            
            # 合并结果
            combined_result = {
                **analysis_result,
                "primary_intent": intent_result.get("primary_intent", "search"),
                "secondary_intents": intent_result.get("secondary_intents", []),
                "intent_confidence": intent_result.get("confidence", 0.8)
            }
            
            return combined_result
            
        except Exception as e:
            logger.error(f"LLM意图提取失败: {e}")
            # 返回默认结果
            return {
                "keywords": [processed_text.normalized],
                "category": None,
                "brand": None,
                "price_range": {"min": None, "max": None},
                "condition": None,
                "size": None,
                "color": None,
                "intent": "search",
                "primary_intent": "search",
                "secondary_intents": [],
                "confidence": 0.5,
                "intent_confidence": 0.5
            }
    
    def _build_parsed_query(self, llm_response: Dict[str, Any], processed_text) -> ParsedQuery:
        """
        构建解析后的查询对象
        
        Args:
            llm_response: LLM返回的解析结果
            processed_text: 预处理后的文本
            
        Returns:
            ParsedQuery: 解析后的查询对象
        """
        return ParsedQuery(
            original_query=processed_text.original,
            normalized_query=processed_text.normalized,
            keywords=llm_response.get("keywords", []),
            category=llm_response.get("category"),
            brand=llm_response.get("brand"),
            price_min=llm_response.get("price_range", {}).get("min"),
            price_max=llm_response.get("price_range", {}).get("max"),
            condition=llm_response.get("condition"),
            size=llm_response.get("size"),
            color=llm_response.get("color"),
            intent=QueryIntent(llm_response.get("intent", "search")),
            confidence=llm_response.get("confidence", 0.8)
        )
    
    async def validate_and_refine_query(self, parsed_query: ParsedQuery) -> ParsedQuery:
        """
        验证和改善查询参数
        
        Args:
            parsed_query: 已解析的查询
            
        Returns:
            ParsedQuery: 验证和改善后的查询
        """
        try:
            # 构建参数字典进行验证
            parameters = {
                "keywords": parsed_query.keywords,
                "category": parsed_query.category,
                "brand": parsed_query.brand,
                "price_range": {
                    "min": parsed_query.price_min,
                    "max": parsed_query.price_max
                },
                "condition": parsed_query.condition
            }
            
            # 使用提示词管理系统进行参数验证
            validation_prompt = QueryPrompts.get_parameter_validation_prompt(parameters)
            
            validation_response = await self.llm_service.generate_response(
                prompt=validation_prompt,
                max_tokens=400,
                temperature=0.2,
                response_format="json"
            )
            
            import json
            validation_result = json.loads(validation_response.content)
            
            # 应用验证结果的修正
            validated_params = validation_result.get("validated_parameters", {})
            
            # 更新解析查询
            if validated_params:
                if "keywords" in validated_params:
                    parsed_query.keywords = validated_params["keywords"]
                if "category" in validated_params:
                    parsed_query.category = validated_params["category"]
                if "brand" in validated_params:
                    parsed_query.brand = validated_params["brand"]
                if "price_range" in validated_params:
                    price_range = validated_params["price_range"]
                    parsed_query.price_min = price_range.get("min")
                    parsed_query.price_max = price_range.get("max")
                if "condition" in validated_params:
                    parsed_query.condition = validated_params["condition"]
            
            # 记录警告和建议
            warnings = validation_result.get("warnings", [])
            suggestions = validation_result.get("suggestions", [])
            
            if warnings:
                logger.warning(f"查询验证警告: {warnings}")
            if suggestions:
                logger.info(f"查询改善建议: {suggestions}")
            
            return parsed_query
            
        except Exception as e:
            logger.error(f"查询验证失败: {e}")
            return parsed_query
    
    async def expand_query_if_needed(self, parsed_query: ParsedQuery, search_results_count: int = 0) -> List[ParsedQuery]:
        """
        根据搜索结果数量扩展查询
        
        Args:
            parsed_query: 原始解析查询
            search_results_count: 搜索结果数量
            
        Returns:
            List[ParsedQuery]: 扩展后的查询列表
        """
        try:
            # 如果搜索结果足够多，不需要扩展
            if search_results_count > 10:
                return [parsed_query]
            
            # 使用查询扩展提示词
            expansion_prompt = QueryPrompts.get_query_expansion_prompt(
                original_query=parsed_query.original_query,
                search_results_count=search_results_count
            )
            
            expansion_response = await self.llm_service.generate_response(
                prompt=expansion_prompt,
                max_tokens=600,
                temperature=0.4,
                response_format="json"
            )
            
            import json
            expansion_result = json.loads(expansion_response.content)
            
            expanded_queries = [parsed_query]  # 包含原始查询
            
            # 处理扩展查询
            for expanded_query_data in expansion_result.get("expanded_queries", []):
                expanded_query_text = expanded_query_data.get("query", "")
                if expanded_query_text and expanded_query_text != parsed_query.original_query:
                    # 解析扩展查询
                    expanded_result = await self.parse(expanded_query_text)
                    expanded_queries.append(expanded_result.query)
            
            logger.info(f"查询扩展完成: 生成了 {len(expanded_queries)} 个变体")
            return expanded_queries
            
        except Exception as e:
            logger.error(f"查询扩展失败: {e}")
            return [parsed_query]
    
    async def suggest_categories(self, keywords: List[str]) -> List[Dict[str, Any]]:
        """
        基于关键词建议商品类别
        
        Args:
            keywords: 关键词列表
            
        Returns:
            List[Dict[str, Any]]: 类别建议列表
        """
        try:
            category_prompt = QueryPrompts.get_category_suggestion_prompt(keywords)
            
            category_response = await self.llm_service.generate_response(
                prompt=category_prompt,
                max_tokens=400,
                temperature=0.3,
                response_format="json"
            )
            
            import json
            category_result = json.loads(category_response.content)
            
            return category_result.get("recommended_categories", [])
            
        except Exception as e:
            logger.error(f"类别建议失败: {e}")
            return []
    
    async def parse_query(self, user_query: str) -> ParsedQueryResult:
        """
        解析用户查询的简化接口
        
        Args:
            user_query: 用户输入的查询
            
        Returns:
            ParsedQueryResult: 解析结果
        """
        return await self.parse(user_query)
    
    async def refine_query_with_feedback(self, original_query: str, search_results: List[Dict], user_feedback: str = None) -> ParsedQuery:
        """
        基于搜索结果和用户反馈改善查询
        
        Args:
            original_query: 原始查询
            search_results: 搜索结果
            user_feedback: 用户反馈
            
        Returns:
            ParsedQuery: 改善后的查询
        """
        try:
            refinement_prompt = QueryPrompts.get_query_refinement_prompt(
                original_query=original_query,
                search_results=search_results,
                user_feedback=user_feedback
            )
            
            refinement_response = await self.llm_service.generate_response(
                prompt=refinement_prompt,
                max_tokens=500,
                temperature=0.3,
                response_format="json"
            )
            
            import json
            refinement_result = json.loads(refinement_response.content)
            
            # 解析改善后的查询
            refined_query_text = refinement_result.get("refined_query", original_query)
            refined_result = await self.parse(refined_query_text)
            
            return refined_result.query
            
        except Exception as e:
            logger.error(f"查询改善失败: {e}")
            # 返回原始查询的解析结果
            original_result = await self.parse(original_query)
            return original_result.query
    
    async def process_japanese_text(self, text: str) -> Dict[str, Any]:
        """
        专门处理日语文本的规范化和同义词扩展
        
        Args:
            text: 日语文本
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            processing_prompt = QueryPrompts.get_japanese_processing_prompt(text)
            
            processing_response = await self.llm_service.generate_response(
                prompt=processing_prompt,
                max_tokens=400,
                temperature=0.2,
                response_format="json"
            )
            
            import json
            processing_result = json.loads(processing_response.content)
            
            return processing_result
            
        except Exception as e:
            logger.error(f"日语文本处理失败: {e}")
            return {
                "normalized_text": text,
                "synonyms": [],
                "expanded_terms": [],
                "alternative_readings": [],
                "search_keywords": [text]
            }
    
    def get_parsing_stats(self) -> Dict[str, Any]:
        """
        获取查询解析的统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        # 这里可以添加解析统计的逻辑
        # 目前返回基本信息
        return {
            "total_parsed": getattr(self, '_total_parsed', 0),
            "average_confidence": getattr(self, '_average_confidence', 0.0),
            "common_categories": getattr(self, '_common_categories', []),
            "common_intents": getattr(self, '_common_intents', [])
        }
    
    def _load_category_mapping(self) -> Dict[str, str]:
        """
        加载类别映射
        
        Returns:
            Dict[str, str]: 类别映射字典
        """
        return {
            "レディース": "ladies",
            "メンズ": "mens", 
            "ベビー・キッズ": "baby_kids",
            "インテリア・住まい・小物": "interior_home",
            "本・音楽・ゲーム": "books_music_games",
            "おもちゃ・ホビー・グッズ": "toys_hobbies",
            "コスメ・香水・美容": "cosmetics_beauty",
            "家電・スマホ・カメラ": "electronics",
            "スポーツ・レジャー": "sports_leisure",
            "ハンドメイド": "handmade",
            "チケット": "tickets",
            "自動車・オートバイ": "automotive",
            "その他": "others"
        }
    
    def _load_condition_mapping(self) -> Dict[str, str]:
        """
        加载商品状态映射
        
        Returns:
            Dict[str, str]: 状态映射字典
        """
        return {
            "新品・未使用": "new_unused",
            "未使用に近い": "like_new",
            "目立った傷や汚れなし": "good_condition",
            "やや傷や汚れあり": "some_wear",
            "傷や汚れあり": "worn_condition",
            "全体的に状態が悪い": "poor_condition"
        }
    
    def _validate_and_enhance(self, query: ParsedQuery) -> ParsedQuery:
        """
        验证和增强查询结果
        
        Args:
            query: 待验证的查询对象
            
        Returns:
            ParsedQuery: 验证后的查询对象
        """
        # 关键词验证和清理
        if query.keywords:
            query.keywords = [kw.strip() for kw in query.keywords if kw.strip()]
        
        # 类别标准化
        if query.category:
            query.category = self.category_mapping.get(query.category, query.category)
        
        # 条件标准化
        if query.condition:
            query.condition = self.condition_mapping.get(query.condition, query.condition)
        
        # 价格范围验证
        if query.price_min and query.price_max:
            if query.price_min > query.price_max:
                query.price_min, query.price_max = query.price_max, query.price_min
        
        return query
    
    def _load_category_mapping(self) -> Dict[str, str]:
        """
        加载类别映射表
        
        Returns:
            Dict[str, str]: 类别映射字典
        """
        return {
            "服": "ファッション",
            "服装": "ファッション",
            "衣服": "ファッション",
            "電子機器": "家電・スマホ・カメラ",
            "电子产品": "家電・スマホ・カメラ",
            "手机": "家電・スマホ・カメラ",
            "スマホ": "家電・スマホ・カメラ",
            "本": "本・音楽・ゲーム",
            "書籍": "本・音楽・ゲーム",
            "游戏": "本・音楽・ゲーム",
            "ゲーム": "本・音楽・ゲーム"
        }
    
    def _load_condition_mapping(self) -> Dict[str, str]:
        """
        加载条件映射表
        
        Returns:
            Dict[str, str]: 条件映射字典
        """
        return {
            "新品": "新品・未使用",
            "全新": "新品・未使用",
            "新しい": "新品・未使用",
            "中古": "やや傷や汚れあり",
            "二手": "やや傷や汚れあり",
            "使用过": "やや傷や汚れあり",
            "良好": "目立った傷や汚れなし",
            "状态良好": "目立った傷や汚れなし"
        }