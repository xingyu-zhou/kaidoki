"""
搜索相关工具

该模块包含与产品搜索相关的工具实现。
"""

from typing import Dict, Any, List, Optional, TYPE_CHECKING
import logging
from datetime import datetime

from .base_tool import BaseTool, ToolResult, ToolStatus
from ...models.product import ProductData
from ...models.query import SearchQuery, QueryType, QueryIntent
from ...services.scraper_service import ScraperService
from ...utils.japanese_processor import JapaneseProcessor
from ...utils.logger import get_logger
from ...utils.json_encoder import safe_enum_value

if TYPE_CHECKING:
    from ...services.llm_service import LLMService

logger = get_logger(__name__)


class SearchMercariTool(BaseTool):
    """Mercari产品搜索工具"""
    
    def __init__(self, scraper_service: ScraperService):
        super().__init__(
            name="search_products",
            description="在Mercari平台搜索产品，支持关键词、价格范围、状态等多种搜索条件"
        )
        self.scraper_service = scraper_service
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词"
                    },
                    "price_min": {
                        "type": "number",
                        "description": "最低价格（日元）",
                        "minimum": 0
                    },
                    "price_max": {
                        "type": "number",
                        "description": "最高价格（日元）",
                        "minimum": 0
                    },
                    "category": {
                        "type": "string",
                        "description": "商品类别"
                    },
                    "condition": {
                        "type": "string",
                        "description": "商品状态",
                        "enum": ["新品・未使用", "未使用に近い", "目立った傷や汚れなし", 
                                "やや傷や汚れあり", "傷や汚れあり", "全体的に状態が悪い"]
                    },
                    "brand": {
                        "type": "string",
                        "description": "品牌名称"
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "排序方式",
                        "enum": ["created_time", "price", "num_comments"]
                    },
                    "sort_order": {
                        "type": "string",
                        "description": "排序顺序",
                        "enum": ["asc", "desc"],
                        "default": "desc"
                    },
                    "page": {
                        "type": "integer",
                        "description": "页码",
                        "minimum": 1,
                        "default": 1
                    },
                    "page_size": {
                        "type": "integer",
                        "description": "每页结果数",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 20
                    }
                },
                "required": ["query"]
            }
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        try:
            # 导入必要的模块
            from ...models.query import ParsedQuery
            from ...services.scraper_service import ScrapingContext, ScrapingStrategy
            
            # 验证查询参数
            query = kwargs.get("query", "").strip()
            logger.info(f"🔍 SearchMercariTool 接收到查询参数: {kwargs}")
            logger.info(f"📝 处理后的查询字符串: '{query}'")
            
            if not query:
                logger.error(f"❌ 搜索查询为空！原始参数: {kwargs}")
                logger.error(f"❌ 查询参数详情: query='{kwargs.get('query')}', 类型={type(kwargs.get('query'))}")
                return ToolResult(
                    status=ToolStatus.ERROR,
                    error="搜索查询不能为空",
                    metadata={
                        "original_params": kwargs,
                        "processed_query": query,
                        "error_type": "empty_query"
                    }
                )
            
            # 构建解析查询
            parsed_query = ParsedQuery(
                original_query=query,
                normalized_query=query,
                keywords=[query] if query else [],
                category=kwargs.get("category"),
                price_min=kwargs.get("price_min"),
                price_max=kwargs.get("price_max"),
                condition=kwargs.get("condition"),
                brand=kwargs.get("brand"),
                sort_preference=kwargs.get("sort_by")
            )
            
            logger.info(f"🔍 构建的解析查询: original='{parsed_query.original_query}', normalized='{parsed_query.normalized_query}'")
            logger.info(f"📋 查询关键词: {parsed_query.keywords}")
            logger.info(f"🏷️ 查询分类: {parsed_query.category}")
            logger.info(f"💰 价格范围: {parsed_query.price_min} - {parsed_query.price_max}")
            
            # 构建爬虫上下文
            context = ScrapingContext(
                query=parsed_query,
                max_pages=kwargs.get("max_pages", 3),
                max_products=kwargs.get("page_size", 20),
                strategy=ScrapingStrategy.REQUESTS,
                use_cache=True
            )
            
            logger.info(f"🌐 开始执行搜索 - 最大页数: {context.max_pages}, 最大产品数: {context.max_products}")
            
            # 执行搜索
            result = await self.scraper_service.scrape(context)
            
            logger.info(f"✅ 搜索完成 - 找到产品数: {result.total_found}, 爬取页数: {result.pages_scraped}")
            logger.info(f"⏱️ 搜索耗时: {result.processing_time:.2f}秒")
            
            # 处理结果
            products_data = []
            for product in result.products:
                products_data.append({
                    "id": product.id,
                    "title": product.title,
                    "price": product.price,
                    "condition": safe_enum_value(product.condition),
                    "url": product.url,
                    "image_url": product.images[0].url if product.images else None,
                    "seller_name": product.seller_name,
                    "created_at": product.created_at.isoformat() if product.created_at else None
                })
            
            return ToolResult(
                status=ToolStatus.SUCCESS,
                data={
                    "products": products_data,
                    "total_found": result.total_found,
                    "pages_scraped": result.pages_scraped,
                    "strategy_used": safe_enum_value(result.strategy_used),
                    "processing_time": result.processing_time,
                    "has_more": len(result.products) >= context.max_products
                },
                metadata={
                    "query": kwargs["query"],
                    "search_time": datetime.now().isoformat(),
                    "scraping_metadata": result.metadata
                }
            )
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"搜索失败: {str(e)}"
            )


class QueryAnalyzerTool(BaseTool):
    """查询分析工具"""
    
    def __init__(self, llm_service: 'LLMService'):
        super().__init__(
            name="analyze_query",
            description="分析用户查询意图，提取搜索参数和意图分类"
        )
        self.llm_service = llm_service
        self.japanese_processor = JapaneseProcessor()
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "用户的原始查询文本"
                    },
                    "context": {
                        "type": "string",
                        "description": "查询上下文（可选）"
                    }
                },
                "required": ["query"]
            }
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        try:
            query = kwargs["query"]
            context = kwargs.get("context", "")
            
            # 预处理日语文本
            processed_query = self.japanese_processor.preprocess_text(query)
            
            # 构建分析提示
            analysis_prompt = f"""
            分析以下日语购物查询，提取结构化信息：
            
            查询: {processed_query}
            上下文: {context}
            
            请提取以下信息：
            1. 查询意图 (搜索/比较/推荐/过滤/排序/分析/问题)
            2. 关键词
            3. 价格范围
            4. 商品类别
            5. 品牌
            6. 商品状态
            7. 排序偏好
            8. 其他过滤条件
            
            返回JSON格式结果。
            """
            
            # 使用LLM分析查询
            analysis_result = await self.llm_service.generate_response(
                analysis_prompt,
                response_format="json"
            )
            
            return ToolResult(
                status=ToolStatus.SUCCESS,
                data=analysis_result,
                metadata={
                    "original_query": query,
                    "processed_query": processed_query,
                    "analysis_time": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Query analysis failed: {e}")
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"查询分析失败: {str(e)}"
            )


class CategorySuggestTool(BaseTool):
    """类别建议工具"""
    
    def __init__(self, llm_service: 'LLMService'):
        super().__init__(
            name="suggest_category",
            description="根据查询内容建议相关的商品类别"
        )
        self.llm_service = llm_service
        self.category_mapping = self._load_category_mapping()
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "用户查询或关键词"
                    },
                    "max_suggestions": {
                        "type": "integer",
                        "description": "最大建议数量",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        try:
            query = kwargs["query"]
            max_suggestions = kwargs.get("max_suggestions", 5)
            
            # 构建类别建议提示
            suggestion_prompt = f"""
            基于以下查询，建议最相关的Mercari商品类别：
            
            查询: {query}
            
            可用类别: {list(self.category_mapping.keys())}
            
            请返回前{max_suggestions}个最相关的类别，按相关度排序。
            返回JSON格式: {{"categories": ["类别1", "类别2", ...], "confidence": [0.9, 0.8, ...]}}
            """
            
            # 使用LLM生成建议
            suggestion_result = await self.llm_service.generate_response(
                suggestion_prompt,
                response_format="json"
            )
            
            return ToolResult(
                status=ToolStatus.SUCCESS,
                data=suggestion_result,
                metadata={
                    "query": query,
                    "max_suggestions": max_suggestions,
                    "suggestion_time": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Category suggestion failed: {e}")
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"类别建议失败: {str(e)}"
            )
    
    def _load_category_mapping(self) -> Dict[str, str]:
        """加载类别映射"""
        return {
            "レディース": "women",
            "メンズ": "men", 
            "ベビー・キッズ": "baby_kids",
            "インテリア・住まい・小物": "interior",
            "本・音楽・ゲーム": "books_music_games",
            "おもちゃ・ホビー・グッズ": "toys_hobbies",
            "コスメ・香水・美容": "cosmetics",
            "家電・スマホ・カメラ": "electronics",
            "スポーツ・レジャー": "sports",
            "ハンドメイド": "handmade",
            "チケット": "tickets",
            "自動車・オートバイ": "automotive",
            "その他": "others"
        }


class SearchTools:
    """搜索工具集合"""
    
    def __init__(self, scraper_service: ScraperService, llm_service: 'LLMService'):
        self.search_tool = SearchMercariTool(scraper_service)
        self.query_analyzer = QueryAnalyzerTool(llm_service)
        self.category_suggest = CategorySuggestTool(llm_service)
    
    def get_tools(self) -> List[BaseTool]:
        """获取所有搜索工具"""
        return [
            self.search_tool,
            self.query_analyzer,
            self.category_suggest
        ]