"""
工具调用协调器

该模块负责协调和管理所有工具的调用，包括：
- 工具注册和初始化
- 工具调用流程管理
- 工具间依赖关系处理
- 错误处理和降级机制
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from dataclasses import dataclass

from .tools.tool_registry import ToolRegistry
from .tools.base_tool import BaseTool, ToolResult, ToolStatus
from .tools.search_tools import SearchTools
from .tools.analysis_tools import AnalysisTools
from .tools.formatting_tools import FormattingTools
from ..services.llm_service import LLMService
from ..services.scraper_service import ScraperService
from ..services.analysis_service import AnalysisService
from ..core.output_formatter import OutputFormatter
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ToolExecutionContext:
    """工具执行上下文"""
    user_query: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    preferences: Dict[str, Any] = None
    execution_history: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.preferences is None:
            self.preferences = {}
        if self.execution_history is None:
            self.execution_history = []


@dataclass
class ToolExecutionResult:
    """工具执行结果"""
    success: bool
    results: Dict[str, ToolResult]
    execution_time: float
    tools_used: List[str]
    errors: List[str]
    warnings: List[str]
    context: ToolExecutionContext
    
    def get_final_result(self) -> Any:
        """获取最终结果"""
        if not self.success:
            return None
        
        # 返回最后一个成功执行的工具结果
        for tool_name in reversed(self.tools_used):
            if tool_name in self.results and self.results[tool_name].is_success():
                return self.results[tool_name].data
        
        return None


class ToolOrchestrator:
    """
    工具调用协调器
    
    负责管理所有工具的注册、调用和协调。
    """
    
    def __init__(self, 
                 llm_service: LLMService,
                 scraper_service: ScraperService,
                 analysis_service: AnalysisService,
                 output_formatter: OutputFormatter):
        """
        初始化工具协调器
        
        Args:
            llm_service: LLM服务
            scraper_service: 爬虫服务
            analysis_service: 分析服务
            output_formatter: 输出格式化器
        """
        self.llm_service = llm_service
        self.scraper_service = scraper_service
        self.analysis_service = analysis_service
        self.output_formatter = output_formatter
        
        # 初始化工具注册表
        self.tool_registry = ToolRegistry()
        
        # 工具执行统计
        self.execution_stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "average_execution_time": 0.0,
            "most_used_tools": [],
            "error_patterns": []
        }
        
        # 初始化工具
        self._initialize_tools()
        
        logger.info("ToolOrchestrator initialized with all tools registered")
    
    def _initialize_tools(self):
        """初始化所有工具"""
        try:
            # 注册搜索工具
            search_tools = SearchTools(self.scraper_service, self.llm_service)
            for tool in search_tools.get_tools():
                self.tool_registry.register(tool, "search")
            
            # 注册分析工具
            analysis_tools = AnalysisTools(self.analysis_service, self.llm_service)
            for tool in analysis_tools.get_tools():
                self.tool_registry.register(tool, "analysis")
            
            # 注册格式化工具
            formatting_tools = FormattingTools(self.llm_service, self.output_formatter)
            for tool in formatting_tools.get_tools():
                self.tool_registry.register(tool, "formatting")
            
            # 设置LLM服务的工具注册表
            self.llm_service.tool_registry = self.tool_registry
            
            logger.info(f"Initialized {len(self.tool_registry)} tools across 3 categories")
            
        except Exception as e:
            logger.error(f"Tool initialization failed: {e}")
            raise
    
    async def execute_query(self, context: ToolExecutionContext) -> ToolExecutionResult:
        """
        执行查询，自动选择和调用合适的工具
        
        Args:
            context: 工具执行上下文
            
        Returns:
            ToolExecutionResult: 执行结果
        """
        start_time = datetime.now()
        results = {}
        tools_used = []
        errors = []
        warnings = []
        
        try:
            # 1. 分析查询意图，确定需要的工具
            required_tools = await self._analyze_query_intent(context.user_query)
            
            # 2. 按优先级执行工具
            for tool_info in required_tools:
                tool_name = tool_info["tool_name"]
                tool_params = tool_info.get("parameters", {})
                
                # 🔧 修复：智能参数映射和占位符替换
                processed_params = self._fix_tool_parameters(tool_name, tool_params, context, results)
                
                logger.info(f"🔍 执行工具: {tool_name}")
                logger.info(f"📝 原始参数: {tool_params}")
                logger.info(f"✅ 处理后参数: {processed_params}")
                
                try:
                    # 执行工具
                    tool_result = await self.tool_registry.call_tool(tool_name, **processed_params)
                    results[tool_name] = tool_result
                    tools_used.append(tool_name)
                    
                    # 检查是否需要继续
                    if tool_result.is_success():
                        logger.info(f"✅ Tool {tool_name} executed successfully")
                    else:
                        errors.append(f"Tool {tool_name} failed: {tool_result.error}")
                        logger.error(f"❌ Tool {tool_name} failed: {tool_result.error}")
                        
                except Exception as e:
                    error_msg = f"Tool {tool_name} execution failed: {str(e)}"
                    errors.append(error_msg)
                    logger.error(f"❌ {error_msg}")
            
            # 3. 计算执行时间
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # 4. 更新统计信息
            self._update_execution_stats(tools_used, execution_time, len(errors) == 0)
            
            # 5. 构建结果
            success = len(errors) == 0 and len(results) > 0
            
            return ToolExecutionResult(
                success=success,
                results=results,
                execution_time=execution_time,
                tools_used=tools_used,
                errors=errors,
                warnings=warnings,
                context=context
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            error_msg = f"Query execution failed: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
            
            return ToolExecutionResult(
                success=False,
                results=results,
                execution_time=execution_time,
                tools_used=tools_used,
                errors=errors,
                warnings=warnings,
                context=context
            )
    
    async def _analyze_query_intent(self, user_query: str) -> List[Dict[str, Any]]:
        """
        分析查询意图，确定需要使用的工具
        
        Args:
            user_query: 用户查询
            
        Returns:
            List[Dict[str, Any]]: 需要使用的工具列表
        """
        logger.info(f"🔍 开始分析查询意图: {user_query}")
        
        try:
            # 使用LLM分析查询意图 - 修复占位符问题
            analysis_prompt = f"""
            分析以下用户查询，确定需要使用的工具和参数。
            
            用户查询: "{user_query}"
            
            可用工具:
            - search_products: 搜索Mercari商品，参数: query(搜索关键词), price_min, price_max, condition, category
            - analyze_query: 分析查询意图，参数: query(查询内容)
            - suggest_category: 建议商品类别，参数: query(查询内容)
            - analyze_product: 分析单个商品，参数: product_id, product_url, product_data
            - compare_products: 比较多个商品，参数: products(商品列表)
            - analyze_price: 分析价格，参数: price_data
            - generate_recommendations: 生成推荐，参数: search_results, user_preferences
            - generate_summary: 格式化商品摘要，参数: products
            - format_comparison_table: 格式化比较表，参数: products
            - format_recommendation_report: 格式化推荐报告，参数: recommendations
            
            ⚠️ 重要：请使用实际的参数值，不要使用占位符！
            
            对于用户查询 "{user_query}"，请返回JSON格式的工具调用计划：
            {{
                "tools": [
                    {{
                        "tool_name": "analyze_query",
                        "priority": 1,
                        "parameters": {{
                            "query": "{user_query}"
                        }},
                        "reason": "首先分析用户查询意图"
                    }},
                    {{
                        "tool_name": "search_products",
                        "priority": 2,
                        "parameters": {{
                            "query": "{user_query}"
                        }},
                        "reason": "搜索相关商品"
                    }}
                ]
            }}
            
            请确保所有parameters中的值都是实际的参数值，不要使用"用户查询的内容"等占位符。
            """
            
            response = await self.llm_service.generate_response(
                prompt=analysis_prompt,
                max_tokens=600,
                temperature=0.3,
                response_format="json"
            )
            
            logger.info(f"🔍 LLM 响应内容: {response.content}")
            
            import json
            analysis_result = json.loads(response.content)
            
            # 按优先级排序
            tools = analysis_result.get("tools", [])
            tools.sort(key=lambda x: x.get("priority", 99))
            
            logger.info(f"🔍 分析结果工具链: {tools}")
            
            return tools
            
        except Exception as e:
            logger.error(f"Query intent analysis failed: {e}")
            logger.error(f"🔍 使用默认工具链")
            # 返回默认工具链
            default_tools = [
                {
                    "tool_name": "analyze_query",
                    "priority": 1,
                    "parameters": {"query": user_query},
                    "reason": "Default query analysis"
                },
                {
                    "tool_name": "search_products",
                    "priority": 2,
                    "parameters": {"query": user_query},
                    "reason": "Default product search"
                }
            ]
            logger.info(f"🔍 默认工具链: {default_tools}")
            return default_tools
    
    async def execute_tool_chain(self, tool_chain: List[Dict[str, Any]], context: ToolExecutionContext) -> ToolExecutionResult:
        """
        执行工具链
        
        Args:
            tool_chain: 工具链定义
            context: 执行上下文
            
        Returns:
            ToolExecutionResult: 执行结果
        """
        start_time = datetime.now()
        results = {}
        tools_used = []
        errors = []
        warnings = []
        
        try:
            # 按顺序执行工具链
            for tool_info in tool_chain:
                tool_name = tool_info["tool_name"]
                tool_params = tool_info.get("parameters", {})
                
                # 处理参数中的引用（从前面的工具结果中获取）
                processed_params = self._process_tool_parameters(tool_params, results)
                
                try:
                    # 执行工具
                    tool_result = await self.tool_registry.call_tool(tool_name, **processed_params)
                    results[tool_name] = tool_result
                    tools_used.append(tool_name)
                    
                    if not tool_result.is_success():
                        errors.append(f"Tool {tool_name} failed: {tool_result.error}")
                        
                except Exception as e:
                    error_msg = f"Tool {tool_name} execution failed: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            success = len(errors) == 0 and len(results) > 0
            
            self._update_execution_stats(tools_used, execution_time, success)
            
            return ToolExecutionResult(
                success=success,
                results=results,
                execution_time=execution_time,
                tools_used=tools_used,
                errors=errors,
                warnings=warnings,
                context=context
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            error_msg = f"Tool chain execution failed: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
            
            return ToolExecutionResult(
                success=False,
                results=results,
                execution_time=execution_time,
                tools_used=tools_used,
                errors=errors,
                warnings=warnings,
                context=context
            )
    
    def _fix_tool_parameters(self, tool_name: str, params: Dict[str, Any],
                            context: ToolExecutionContext, previous_results: Dict[str, ToolResult]) -> Dict[str, Any]:
        """
        修复工具参数，处理占位符和参数映射
        
        Args:
            tool_name: 工具名称
            params: 原始参数
            context: 执行上下文
            previous_results: 前面的工具执行结果
            
        Returns:
            Dict[str, Any]: 修复后的参数
        """
        logger.info(f"🔧 修复工具参数: {tool_name}")
        
        # 1. 复制原始参数
        fixed_params = params.copy()
        
        # 2. 处理占位符和常见的参数映射问题
        placeholder_mappings = {
            "用户查询的内容": context.user_query,
            "用户查询": context.user_query,
            "搜索查询": context.user_query,
            "查询内容": context.user_query,
            "用户偏好": context.preferences,
            "用户喜好": context.preferences,
        }
        
        # 3. 替换占位符
        for key, value in fixed_params.items():
            if isinstance(value, str):
                # 检查是否是占位符
                if value in placeholder_mappings:
                    fixed_params[key] = placeholder_mappings[value]
                    logger.info(f"🔧 替换占位符 {key}: '{value}' -> '{fixed_params[key]}'")
                # 检查是否是引用
                elif value.startswith("$"):
                    fixed_params[key] = self._resolve_parameter_reference(value, previous_results)
                    logger.info(f"🔧 解析引用 {key}: '{value}' -> '{fixed_params[key]}'")
        
        # 4. 工具特定的参数修复
        fixed_params = self._apply_tool_specific_fixes(tool_name, fixed_params, context, previous_results)
        
        # 5. 验证必需参数
        fixed_params = self._ensure_required_parameters(tool_name, fixed_params, context, previous_results)
        
        return fixed_params
    
    def _resolve_parameter_reference(self, reference: str, previous_results: Dict[str, ToolResult]) -> Any:
        """
        解析参数引用
        
        Args:
            reference: 引用字符串，格式为 $tool_name.field_path
            previous_results: 前面的工具执行结果
            
        Returns:
            Any: 解析后的值
        """
        if not reference.startswith("$"):
            return reference
        
        ref_parts = reference[1:].split(".")
        if len(ref_parts) < 2:
            return None
        
        tool_name = ref_parts[0]
        field_path = ref_parts[1:]
        
        if tool_name not in previous_results:
            return None
        
        tool_result = previous_results[tool_name]
        if not tool_result.is_success():
            return None
        
        # 从结果中提取字段
        data = tool_result.data
        
        # 处理 "data" 字段特殊情况 - 如果第一个字段是 "data"，直接使用 tool_result.data
        if field_path[0] == "data":
            field_path = field_path[1:]  # 跳过 "data" 字段
        
        for field in field_path:
            if isinstance(data, dict) and field in data:
                data = data[field]
            elif isinstance(data, list) and field.isdigit():
                # 处理数组索引
                idx = int(field)
                if 0 <= idx < len(data):
                    data = data[idx]
                else:
                    return None
            else:
                return None
        
        return data
    
    def _apply_tool_specific_fixes(self, tool_name: str, params: Dict[str, Any],
                                 context: ToolExecutionContext, previous_results: Dict[str, ToolResult]) -> Dict[str, Any]:
        """
        应用工具特定的参数修复
        
        Args:
            tool_name: 工具名称
            params: 参数
            context: 执行上下文
            previous_results: 前面的工具执行结果
            
        Returns:
            Dict[str, Any]: 修复后的参数
        """
        fixed_params = params.copy()
        
        if tool_name == "analyze_query":
            # 增强的查询参数验证
            query_value = fixed_params.get("query", "")
            if not query_value or (isinstance(query_value, str) and not query_value.strip()):
                fallback_query = self._get_fallback_query(context, previous_results)
                fixed_params["query"] = fallback_query
                logger.info(f"🔧 为 analyze_query 添加/修复 query 参数: '{fallback_query}'")
            else:
                # 确保查询参数不为空字符串
                if isinstance(query_value, str):
                    fixed_params["query"] = query_value.strip()
                    logger.info(f"🔧 为 analyze_query 清理 query 参数: '{query_value.strip()}'")
        
        elif tool_name == "search_products":
            # 增强的查询参数验证
            query_value = fixed_params.get("query", "")
            if not query_value or (isinstance(query_value, str) and not query_value.strip()):
                fallback_query = self._get_fallback_query(context, previous_results)
                fixed_params["query"] = fallback_query
                logger.info(f"🔧 为 search_products 添加/修复 query 参数: '{fallback_query}'")
            else:
                # 确保查询参数不为空字符串
                if isinstance(query_value, str):
                    fixed_params["query"] = query_value.strip()
                    logger.info(f"🔧 为 search_products 清理 query 参数: '{query_value.strip()}'")
        
        elif tool_name == "generate_recommendations":
            # 确保search_results参数存在
            if "search_results" not in fixed_params or not fixed_params["search_results"]:
                # 尝试从前面的搜索结果中获取
                search_result = previous_results.get("search_products")
                if search_result and search_result.is_success():
                    fixed_params["search_results"] = search_result.data
                    logger.info(f"🔧 为 generate_recommendations 添加 search_results 参数")
            
            # 确保user_preferences参数存在
            if "user_preferences" not in fixed_params or not fixed_params["user_preferences"]:
                fixed_params["user_preferences"] = context.preferences
                logger.info(f"🔧 为 generate_recommendations 添加 user_preferences 参数")
        
        elif tool_name == "analyze_product":
            # 处理商品分析的参数
            if "product_data" not in fixed_params and "product_id" not in fixed_params and "product_url" not in fixed_params:
                # 如果没有任何产品相关参数，尝试从搜索结果中获取第一个产品
                search_result = previous_results.get("search_products")
                if search_result and search_result.is_success():
                    products = search_result.data
                    if isinstance(products, list) and len(products) > 0:
                        fixed_params["product_data"] = products[0]
                        logger.info(f"🔧 为 analyze_product 添加 product_data 参数")
        
        return fixed_params
    
    def _ensure_required_parameters(self, tool_name: str, params: Dict[str, Any],
                                  context: ToolExecutionContext, previous_results: Dict[str, ToolResult]) -> Dict[str, Any]:
        """
        确保必需参数存在
        
        Args:
            tool_name: 工具名称
            params: 参数
            context: 执行上下文
            previous_results: 前面的工具执行结果
            
        Returns:
            Dict[str, Any]: 确保必需参数后的参数
        """
        # 获取工具实例
        tool = self.tool_registry.get_tool(tool_name)
        if not tool:
            logger.warning(f"⚠️ 工具 {tool_name} 不存在")
            return params
        
        # 获取工具schema
        schema = tool.schema
        required_params = schema.get("parameters", {}).get("required", [])
        
        final_params = params.copy()
        
        # 检查必需参数
        for required_param in required_params:
            param_value = final_params.get(required_param)
            needs_fix = (param_value is None or
                        (isinstance(param_value, str) and not param_value.strip()))
            
            if required_param not in final_params or needs_fix:
                logger.warning(f"⚠️ 工具 {tool_name} 缺少或为空的必需参数: {required_param} = {param_value}")
                
                # 尝试提供默认值
                if required_param == "query":
                    # 增强的查询参数验证
                    fallback_query = self._get_fallback_query(context, previous_results)
                    final_params[required_param] = fallback_query
                    logger.info(f"🔧 为 {tool_name} 添加/修复 query 参数: '{fallback_query}'")
                elif required_param == "user_preferences":
                    final_params[required_param] = context.preferences or {}
                    logger.info(f"🔧 为 {tool_name} 添加默认 user_preferences 参数")
                elif required_param == "search_results":
                    # 尝试从前面的搜索结果中获取
                    search_result = previous_results.get("search_products")
                    if search_result and search_result.is_success():
                        final_params[required_param] = search_result.data
                        logger.info(f"🔧 为 {tool_name} 添加 search_results 参数")
                    else:
                        final_params[required_param] = []
                        logger.warning(f"⚠️ 为 {tool_name} 设置空 search_results 参数")
        
        return final_params
    
    def _get_fallback_query(self, context: ToolExecutionContext, previous_results: Dict[str, ToolResult]) -> str:
        """
        获取回退查询参数
        
        Args:
            context: 执行上下文
            previous_results: 前面的工具执行结果
            
        Returns:
            str: 回退查询字符串
        """
        # 1. 优先使用用户查询
        if context.user_query and context.user_query.strip():
            return context.user_query.strip()
        
        # 2. 尝试从查询解析结果中获取refined_query
        for tool_result in previous_results.values():
            if tool_result.is_success() and tool_result.data:
                if isinstance(tool_result.data, dict):
                    refined_query = tool_result.data.get("refined_query")
                    if refined_query and refined_query.strip():
                        logger.info(f"🔧 从工具结果中获取 refined_query: '{refined_query}'")
                        return refined_query.strip()
                    
                    # 也检查是否有query字段
                    query_field = tool_result.data.get("query")
                    if query_field and isinstance(query_field, dict):
                        normalized_query = query_field.get("normalized_query")
                        if normalized_query and normalized_query.strip():
                            logger.info(f"🔧 从工具结果中获取 normalized_query: '{normalized_query}'")
                            return normalized_query.strip()
        
        # 3. 如果都没有，使用默认查询
        fallback = "商品検索"
        logger.warning(f"⚠️ 使用默认回退查询: '{fallback}'")
        return fallback

    def _process_tool_parameters(self, params: Dict[str, Any], previous_results: Dict[str, ToolResult]) -> Dict[str, Any]:
        """
        处理工具参数，解析来自前面工具结果的引用
        
        Args:
            params: 原始参数
            previous_results: 前面的工具执行结果
            
        Returns:
            Dict[str, Any]: 处理后的参数
        """
        processed_params = {}
        
        for key, value in params.items():
            if isinstance(value, str) and value.startswith("$"):
                # 这是一个引用，需要从前面的结果中获取
                processed_params[key] = self._resolve_parameter_reference(value, previous_results)
            else:
                processed_params[key] = value
        
        return processed_params
    
    def _update_execution_stats(self, tools_used: List[str], execution_time: float, success: bool):
        """
        更新执行统计信息
        
        Args:
            tools_used: 使用的工具列表
            execution_time: 执行时间
            success: 是否成功
        """
        self.execution_stats["total_executions"] += 1
        
        if success:
            self.execution_stats["successful_executions"] += 1
        else:
            self.execution_stats["failed_executions"] += 1
        
        # 更新平均执行时间
        total_time = (self.execution_stats["average_execution_time"] * 
                     (self.execution_stats["total_executions"] - 1) + execution_time)
        self.execution_stats["average_execution_time"] = total_time / self.execution_stats["total_executions"]
        
        # 更新最常用工具
        # 这里可以添加更复杂的统计逻辑
    
    async def execute_tool(self, tool_name: str, **kwargs) -> 'ToolResult':
        """
        执行单个工具
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数
            
        Returns:
            ToolResult: 工具执行结果
        """
        try:
            logger.info(f"执行工具: {tool_name}")
            result = await self.tool_registry.call_tool(tool_name, **kwargs)
            
            # 更新统计信息
            self.execution_stats["total_executions"] += 1
            if result.is_success():
                self.execution_stats["successful_executions"] += 1
            else:
                self.execution_stats["failed_executions"] += 1
                
            return result
            
        except Exception as e:
            logger.error(f"工具执行失败: {tool_name} - {e}")
            self.execution_stats["total_executions"] += 1
            self.execution_stats["failed_executions"] += 1
            
            from .tools.base_tool import ToolResult, ToolStatus
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"工具执行失败: {str(e)}"
            )
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        获取可用工具列表
        
        Returns:
            List[Dict[str, Any]]: 工具列表
        """
        tools = []
        for tool in self.tool_registry:
            tools.append({
                "name": tool.name,
                "description": tool.description,
                "schema": tool.schema,
                "stats": tool.get_stats()
            })
        return tools
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """
        获取执行统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        return {
            **self.execution_stats,
            "registry_stats": self.tool_registry.get_registry_stats()
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        执行健康检查
        
        Returns:
            Dict[str, Any]: 健康检查结果
        """
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {},
            "tools": {},
            "issues": []
        }
        
        try:
            # 检查LLM服务
            llm_stats = self.llm_service.get_performance_metrics()
            health_status["services"]["llm"] = {
                "status": "healthy",
                "metrics": llm_stats
            }
        except Exception as e:
            health_status["services"]["llm"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["issues"].append(f"LLM service issue: {e}")
        
        # 检查工具注册表
        try:
            registry_stats = self.tool_registry.get_registry_stats()
            health_status["tools"] = {
                "total_tools": registry_stats["total_tools"],
                "status": "healthy" if registry_stats["total_tools"] > 0 else "warning"
            }
        except Exception as e:
            health_status["tools"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["issues"].append(f"Tool registry issue: {e}")
        
        # 确定总体状态
        if health_status["issues"]:
            health_status["status"] = "degraded" if len(health_status["issues"]) < 3 else "unhealthy"
        
        return health_status