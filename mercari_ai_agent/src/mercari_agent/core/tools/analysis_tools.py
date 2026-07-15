"""
分析相关工具

该模块包含与产品分析、比较和推荐相关的工具实现。
"""

from typing import Dict, Any, List, Optional, TYPE_CHECKING
import logging
from datetime import datetime
import json

from .base_tool import BaseTool, ToolResult, ToolStatus
from ...models.product import ProductData
from ...models.recommendation import RecommendationResult
from ...services.analysis_service import AnalysisService
from ...analyzers.product_analyzer import ProductAnalyzer
from ...analyzers.scoring_engine import ScoringEngine
from ...utils.logger import get_logger

if TYPE_CHECKING:
    from ...services.llm_service import LLMService

logger = get_logger(__name__)


class ProductAnalysisTool(BaseTool):
    """产品分析工具"""
    
    def __init__(self, analysis_service: AnalysisService, llm_service: 'LLMService'):
        super().__init__(
            name="analyze_product",
            description="分析单个产品的详细信息，包括价格分析、状态评估、性价比等"
        )
        self.analysis_service = analysis_service
        self.llm_service = llm_service
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "产品ID"
                    },
                    "product_url": {
                        "type": "string",
                        "description": "产品URL"
                    },
                    "analysis_type": {
                        "type": "string",
                        "description": "分析类型",
                        "enum": ["basic", "detailed", "price_analysis", "condition_assessment"],
                        "default": "basic"
                    },
                    "include_similar": {
                        "type": "boolean",
                        "description": "是否包含相似产品比较",
                        "default": false
                    }
                },
                "required": ["product_id"]
            }
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        try:
            product_id = kwargs["product_id"]
            analysis_type = kwargs.get("analysis_type", "basic")
            include_similar = kwargs.get("include_similar", False)
            
            # 执行产品分析
            analysis_result = await self.analysis_service.analyze_product(
                product_id=product_id,
                analysis_type=analysis_type,
                include_similar=include_similar
            )
            
            # 生成分析报告
            analysis_report = {
                "product_id": product_id,
                "analysis_type": analysis_type,
                "score": analysis_result.get("score", 0),
                "insights": analysis_result.get("insights", []),
                "recommendations": analysis_result.get("recommendations", []),
                "price_analysis": analysis_result.get("price_analysis", {}),
                "condition_assessment": analysis_result.get("condition_assessment", {}),
                "similar_products": analysis_result.get("similar_products", []) if include_similar else []
            }
            
            return ToolResult(
                status=ToolStatus.SUCCESS,
                data=analysis_report,
                metadata={
                    "analysis_time": datetime.now().isoformat(),
                    "analysis_type": analysis_type,
                    "include_similar": include_similar
                }
            )
            
        except Exception as e:
            logger.error(f"Product analysis failed: {e}")
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"产品分析失败: {str(e)}"
            )


class ProductComparisonTool(BaseTool):
    """产品比较工具"""
    
    def __init__(self, analysis_service: AnalysisService, llm_service: 'LLMService'):
        super().__init__(
            name="compare_products",
            description="比较多个产品的价格、状态、性价比等特征"
        )
        self.analysis_service = analysis_service
        self.llm_service = llm_service
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要比较的产品ID列表",
                        "minItems": 2,
                        "maxItems": 10
                    },
                    "comparison_criteria": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["price", "condition", "seller_rating", "shipping_cost", "value_score"]
                        },
                        "description": "比较标准",
                        "default": ["price", "condition", "value_score"]
                    },
                    "generate_summary": {
                        "type": "boolean",
                        "description": "是否生成比较摘要",
                        "default": True
                    }
                },
                "required": ["product_ids"]
            }
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        try:
            product_ids = kwargs["product_ids"]
            criteria = kwargs.get("comparison_criteria", ["price", "condition", "value_score"])
            generate_summary = kwargs.get("generate_summary", True)
            
            # 执行产品比较
            comparison_result = await self.analysis_service.compare_products(
                product_ids=product_ids,
                criteria=criteria
            )
            
            # 生成比较报告
            comparison_report = {
                "products": comparison_result.get("products", []),
                "comparison_matrix": comparison_result.get("comparison_matrix", {}),
                "rankings": comparison_result.get("rankings", {}),
                "insights": comparison_result.get("insights", [])
            }
            
            # 生成自然语言摘要
            if generate_summary:
                summary_prompt = f"""
                基于以下产品比较数据，生成一份简洁的比较摘要：
                
                比较数据: {json.dumps(comparison_report, ensure_ascii=False, indent=2)}
                
                请提供：
                1. 最佳选择推荐
                2. 各产品的主要优缺点
                3. 购买建议
                
                以日语返回摘要。
                """
                
                summary = await self.llm_service.generate_response(summary_prompt)
                comparison_report["summary"] = summary
            
            return ToolResult(
                status=ToolStatus.SUCCESS,
                data=comparison_report,
                metadata={
                    "comparison_time": datetime.now().isoformat(),
                    "product_count": len(product_ids),
                    "criteria": criteria
                }
            )
            
        except Exception as e:
            logger.error(f"Product comparison failed: {e}")
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"产品比较失败: {str(e)}"
            )


class PriceAnalysisTool(BaseTool):
    """价格分析工具"""
    
    def __init__(self, analysis_service: AnalysisService, llm_service: 'LLMService'):
        super().__init__(
            name="analyze_price",
            description="分析产品价格趋势、市场价格和性价比"
        )
        self.analysis_service = analysis_service
        self.llm_service = llm_service
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "产品ID"
                    },
                    "category": {
                        "type": "string",
                        "description": "产品类别（用于市场价格比较）"
                    },
                    "analysis_depth": {
                        "type": "string",
                        "description": "分析深度",
                        "enum": ["basic", "market_comparison", "trend_analysis"],
                        "default": "basic"
                    },
                    "include_recommendations": {
                        "type": "boolean",
                        "description": "是否包含购买建议",
                        "default": True
                    }
                },
                "required": ["product_id"]
            }
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        try:
            product_id = kwargs["product_id"]
            category = kwargs.get("category")
            analysis_depth = kwargs.get("analysis_depth", "basic")
            include_recommendations = kwargs.get("include_recommendations", True)
            
            # 执行价格分析
            price_analysis = await self.analysis_service.analyze_price(
                product_id=product_id,
                category=category,
                analysis_depth=analysis_depth
            )
            
            # 构建分析报告
            analysis_report = {
                "product_id": product_id,
                "current_price": price_analysis.get("current_price", 0),
                "price_assessment": price_analysis.get("assessment", ""),
                "market_comparison": price_analysis.get("market_comparison", {}),
                "value_score": price_analysis.get("value_score", 0),
                "price_factors": price_analysis.get("factors", [])
            }
            
            # 生成购买建议
            if include_recommendations:
                recommendation_prompt = f"""
                基于以下价格分析，提供购买建议：
                
                价格分析: {json.dumps(analysis_report, ensure_ascii=False, indent=2)}
                
                请提供：
                1. 是否推荐购买
                2. 价格是否合理
                3. 最佳购买时机建议
                4. 注意事项
                
                以日语返回建议。
                """
                
                recommendations = await self.llm_service.generate_response(recommendation_prompt)
                analysis_report["recommendations"] = recommendations
            
            return ToolResult(
                status=ToolStatus.SUCCESS,
                data=analysis_report,
                metadata={
                    "analysis_time": datetime.now().isoformat(),
                    "analysis_depth": analysis_depth,
                    "category": category
                }
            )
            
        except Exception as e:
            logger.error(f"Price analysis failed: {e}")
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"价格分析失败: {str(e)}"
            )


class RecommendationTool(BaseTool):
    """推荐工具"""
    
    def __init__(self, analysis_service: AnalysisService, llm_service: 'LLMService'):
        super().__init__(
            name="generate_recommendations",
            description="基于用户偏好和历史数据生成产品推荐"
        )
        self.analysis_service = analysis_service
        self.llm_service = llm_service
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_preferences": {
                        "type": "object",
                        "description": "用户偏好设置",
                        "properties": {
                            "budget_max": {"type": "number", "description": "最大预算"},
                            "budget_min": {"type": "number", "description": "最小预算"},
                            "preferred_categories": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "偏好类别"
                            },
                            "condition_preference": {
                                "type": "string",
                                "description": "状态偏好",
                                "enum": ["new", "like_new", "good", "fair", "any"]
                            }
                        }
                    },
                    "search_context": {
                        "type": "string",
                        "description": "搜索上下文"
                    },
                    "recommendation_count": {
                        "type": "integer",
                        "description": "推荐数量",
                        "minimum": 1,
                        "maximum": 20,
                        "default": 5
                    },
                    "personalization_level": {
                        "type": "string",
                        "description": "个性化程度",
                        "enum": ["basic", "moderate", "high"],
                        "default": "moderate"
                    }
                },
                "required": ["user_preferences"]
            }
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        try:
            user_preferences = kwargs["user_preferences"]
            search_context = kwargs.get("search_context", "")
            recommendation_count = kwargs.get("recommendation_count", 5)
            personalization_level = kwargs.get("personalization_level", "moderate")
            
            # 生成推荐
            recommendations = await self.analysis_service.generate_recommendations(
                user_preferences=user_preferences,
                context=search_context,
                count=recommendation_count,
                personalization_level=personalization_level
            )
            
            # 生成推荐解释
            explanation_prompt = f"""
            为以下推荐结果生成简洁的解释：
            
            用户偏好: {json.dumps(user_preferences, ensure_ascii=False, indent=2)}
            推荐结果: {json.dumps(recommendations, ensure_ascii=False, indent=2)}
            
            请解释：
            1. 为什么推荐这些产品
            2. 每个推荐的主要优势
            3. 如何满足用户需求
            
            以日语返回解释。
            """
            
            explanation = await self.llm_service.generate_response(explanation_prompt)
            
            return ToolResult(
                status=ToolStatus.SUCCESS,
                data={
                    "recommendations": recommendations,
                    "explanation": explanation,
                    "user_preferences": user_preferences,
                    "recommendation_count": len(recommendations)
                },
                metadata={
                    "recommendation_time": datetime.now().isoformat(),
                    "personalization_level": personalization_level,
                    "search_context": search_context
                }
            )
            
        except Exception as e:
            logger.error(f"Recommendation generation failed: {e}")
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"推荐生成失败: {str(e)}"
            )


class AnalysisTools:
    """分析工具集合"""
    
    def __init__(self, analysis_service: AnalysisService, llm_service: 'LLMService'):
        self.product_analysis = ProductAnalysisTool(analysis_service, llm_service)
        self.product_comparison = ProductComparisonTool(analysis_service, llm_service)
        self.price_analysis = PriceAnalysisTool(analysis_service, llm_service)
        self.recommendation = RecommendationTool(analysis_service, llm_service)
    
    def get_tools(self) -> List[BaseTool]:
        """获取所有分析工具"""
        return [
            self.product_analysis,
            self.product_comparison,
            self.price_analysis,
            self.recommendation
        ]