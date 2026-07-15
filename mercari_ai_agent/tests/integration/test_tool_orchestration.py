"""
工具调用架构集成测试

该文件测试工具调用架构与LLM服务的集成。

测试场景：
- 工具调用编排器与LLM服务集成
- 查询解析器与工具调用集成
- 端到端工作流测试
- 错误处理和恢复

Author: Mercari AI Agent Team
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from typing import Dict, Any, List

# 导入被测试的模块
import sys
sys.path.insert(0, 'mercari_ai_agent/src')

from mercari_agent.core.tool_orchestrator import (
    ToolOrchestrator,
    ToolExecutionContext,
    ToolExecutionResult,
    ToolExecutionPlan,
    ToolExecutionError
)
from mercari_agent.core.query_parser import QueryParser
from mercari_agent.core.tools.tool_registry import ToolRegistry
from mercari_agent.services.llm_service import LLMService, LLMResponse
from mercari_agent.config.settings import Settings

# 导入测试工具
from tests.utils import (
    create_test_products,
    create_test_queries,
    create_mock_llm_service,
    create_mock_tool_registry,
    create_mock_scraper_service,
    async_test,
    TestDataManager
)


class TestToolOrchestration:
    """工具调用编排测试"""
    
    def setup_method(self):
        """测试设置"""
        self.settings = Settings()
        self.llm_service = AsyncMock()
        self.tool_registry = Mock()
        self.orchestrator = ToolOrchestrator(
            llm_service=self.llm_service,
            tool_registry=self.tool_registry,
            settings=self.settings
        )
    
    @async_test
    async def test_simple_tool_execution(self):
        """测试简单工具执行"""
        # 设置Mock工具
        mock_tool_result = Mock()
        mock_tool_result.success = True
        mock_tool_result.data = {"products": create_test_products(3)}
        
        self.tool_registry.execute_tool.return_value = mock_tool_result
        
        # 创建执行上下文
        context = ToolExecutionContext(
            query="iPhone 14",
            user_id="test_user",
            session_id="test_session"
        )
        
        # 执行工具
        result = await self.orchestrator.execute_tool(
            tool_name="search_products",
            context=context,
            query="iPhone 14",
            category="家電"
        )
        
        assert result.success is True
        assert len(result.data["products"]) == 3
        assert result.execution_time > 0
    
    @async_test
    async def test_tool_execution_with_llm_enhancement(self):
        """测试带LLM增强的工具执行"""
        # 设置Mock LLM响应
        self.llm_service.generate_response.return_value = LLMResponse(
            content="根据用户查询，建议搜索iPhone 14 Pro相关产品",
            model="gpt-4",
            provider="openai",
            cost=0.01,
            tokens=Mock(total_tokens=30)
        )
        
        # 设置Mock工具结果
        mock_tool_result = Mock()
        mock_tool_result.success = True
        mock_tool_result.data = {"products": create_test_products(5)}
        
        self.tool_registry.execute_tool.return_value = mock_tool_result
        
        # 创建执行上下文
        context = ToolExecutionContext(
            query="找一个好的iPhone",
            user_id="test_user",
            session_id="test_session"
        )
        
        # 执行带LLM增强的工具
        result = await self.orchestrator.execute_tool_with_llm_enhancement(
            tool_name="search_products",
            context=context,
            original_query="找一个好的iPhone"
        )
        
        assert result.success is True
        assert len(result.data["products"]) == 5
        
        # 验证LLM被调用
        self.llm_service.generate_response.assert_called_once()
    
    @async_test
    async def test_multi_step_tool_execution(self):
        """测试多步骤工具执行"""
        # 设置搜索工具Mock
        search_result = Mock()
        search_result.success = True
        search_result.data = {"products": create_test_products(3)}
        
        # 设置分析工具Mock
        analysis_result = Mock()
        analysis_result.success = True
        analysis_result.data = {"score": 85, "recommendation": "推荐购买"}
        
        # 设置格式化工具Mock
        format_result = Mock()
        format_result.success = True
        format_result.data = {"formatted_results": "格式化的结果"}
        
        # 配置工具调用返回值
        self.tool_registry.execute_tool.side_effect = [
            search_result,
            analysis_result,
            format_result
        ]
        
        # 创建执行计划
        plan = ToolExecutionPlan(
            steps=[
                {"tool": "search_products", "params": {"query": "iPhone"}},
                {"tool": "analyze_product", "params": {"product_data": None}},
                {"tool": "format_results", "params": {"results": None}}
            ]
        )
        
        # 创建执行上下文
        context = ToolExecutionContext(
            query="iPhone 14",
            user_id="test_user",
            session_id="test_session"
        )
        
        # 执行计划
        result = await self.orchestrator.execute_plan(plan, context)
        
        assert result.success is True
        assert len(result.step_results) == 3
        assert all(step.success for step in result.step_results)
    
    @async_test
    async def test_tool_execution_error_handling(self):
        """测试工具执行错误处理"""
        # 设置工具执行失败
        self.tool_registry.execute_tool.side_effect = Exception("工具执行失败")
        
        # 创建执行上下文
        context = ToolExecutionContext(
            query="测试查询",
            user_id="test_user",
            session_id="test_session"
        )
        
        # 执行工具应该抛出异常
        with pytest.raises(ToolExecutionError, match="工具执行失败"):
            await self.orchestrator.execute_tool(
                tool_name="search_products",
                context=context,
                query="测试查询"
            )
    
    @async_test
    async def test_tool_execution_with_retry(self):
        """测试工具执行重试"""
        # 设置前两次失败，第三次成功
        failure_result = Mock()
        failure_result.success = False
        failure_result.error = "临时错误"
        
        success_result = Mock()
        success_result.success = True
        success_result.data = {"products": create_test_products(2)}
        
        self.tool_registry.execute_tool.side_effect = [
            failure_result,
            failure_result,
            success_result
        ]
        
        # 创建执行上下文
        context = ToolExecutionContext(
            query="测试查询",
            user_id="test_user",
            session_id="test_session"
        )
        
        # 执行工具（带重试）
        result = await self.orchestrator.execute_tool_with_retry(
            tool_name="search_products",
            context=context,
            max_retries=3,
            query="测试查询"
        )
        
        assert result.success is True
        assert len(result.data["products"]) == 2
        assert self.tool_registry.execute_tool.call_count == 3


class TestQueryParserIntegration:
    """查询解析器集成测试"""
    
    def setup_method(self):
        """测试设置"""
        self.llm_service = AsyncMock()
        self.query_parser = QueryParser(self.llm_service)
    
    @async_test
    async def test_query_parsing_with_llm(self):
        """测试带LLM的查询解析"""
        # 设置Mock LLM响应
        self.llm_service.generate_response.return_value = LLMResponse(
            content="""{
                "refined_query": "iPhone 14 Pro 256GB",
                "category": "家電",
                "price_range": {"min": 80000, "max": 150000},
                "intent": "purchase",
                "priority": "high"
            }""",
            model="gpt-4",
            provider="openai",
            cost=0.01,
            tokens=Mock(total_tokens=100)
        )
        
        # 解析查询
        result = await self.query_parser.parse_query("想买一个iPhone 14 Pro")
        
        assert result.refined_query == "iPhone 14 Pro 256GB"
        assert result.category == "家電"
        assert result.price_range["min"] == 80000
        assert result.intent == "purchase"
        
        # 验证LLM被调用
        self.llm_service.generate_response.assert_called_once()
    
    @async_test
    async def test_query_expansion(self):
        """测试查询扩展"""
        # 设置Mock LLM响应
        self.llm_service.generate_response.return_value = LLMResponse(
            content="""{
                "expanded_queries": [
                    "iPhone 14",
                    "iPhone 14 Pro",
                    "iPhone 14 Pro Max",
                    "アイフォン 14"
                ],
                "synonyms": ["iPhone", "アイフォン", "アイフォーン"],
                "related_terms": ["スマートフォン", "携帯電話", "モバイル"]
            }""",
            model="gpt-4",
            provider="openai",
            cost=0.01,
            tokens=Mock(total_tokens=150)
        )
        
        # 扩展查询
        result = await self.query_parser.expand_query_if_needed("iPhone")
        
        assert len(result.expanded_queries) == 4
        assert "iPhone 14" in result.expanded_queries
        assert "アイフォン 14" in result.expanded_queries
        assert len(result.synonyms) == 3
        assert len(result.related_terms) == 3
    
    @async_test
    async def test_category_suggestion(self):
        """测试类别建议"""
        # 设置Mock LLM响应
        self.llm_service.generate_response.return_value = LLMResponse(
            content="""{
                "suggested_category": "家電",
                "confidence": 0.95,
                "alternative_categories": ["スマートフォン", "通信機器"],
                "reasoning": "iPhone是智能手机，属于家电类别"
            }""",
            model="gpt-4",
            provider="openai",
            cost=0.01,
            tokens=Mock(total_tokens=80)
        )
        
        # 获取类别建议
        result = await self.query_parser.suggest_categories("iPhone 14")
        
        assert result.suggested_category == "家電"
        assert result.confidence == 0.95
        assert len(result.alternative_categories) == 2
        assert "スマートフォン" in result.alternative_categories


class TestEndToEndWorkflow:
    """端到端工作流测试"""
    
    def setup_method(self):
        """测试设置"""
        self.settings = Settings()
        self.llm_service = AsyncMock()
        self.tool_registry = Mock()
        self.scraper_service = AsyncMock()
        self.analysis_service = AsyncMock()
        
        # 创建组件
        self.query_parser = QueryParser(self.llm_service)
        self.orchestrator = ToolOrchestrator(
            llm_service=self.llm_service,
            tool_registry=self.tool_registry,
            settings=self.settings
        )
    
    @async_test
    async def test_complete_search_workflow(self):
        """测试完整搜索工作流"""
        # 1. 设置查询解析Mock
        self.llm_service.generate_response.side_effect = [
            # 查询解析响应
            LLMResponse(
                content="""{
                    "refined_query": "iPhone 14 Pro 256GB",
                    "category": "家電",
                    "price_range": {"min": 80000, "max": 150000},
                    "intent": "purchase"
                }""",
                model="gpt-4",
                provider="openai",
                cost=0.01,
                tokens=Mock(total_tokens=100)
            ),
            # 工具选择响应
            LLMResponse(
                content="""{
                    "selected_tools": ["search_products", "analyze_product", "format_results"],
                    "execution_order": ["search_products", "analyze_product", "format_results"]
                }""",
                model="gpt-4",
                provider="openai",
                cost=0.01,
                tokens=Mock(total_tokens=80)
            )
        ]
        
        # 2. 设置工具执行Mock
        test_products = create_test_products(5)
        
        search_result = Mock()
        search_result.success = True
        search_result.data = {"products": [p.__dict__ for p in test_products]}
        
        analysis_result = Mock()
        analysis_result.success = True
        analysis_result.data = {"score": 88, "recommendation": "强烈推荐"}
        
        format_result = Mock()
        format_result.success = True
        format_result.data = {"formatted_results": "格式化的产品列表"}
        
        self.tool_registry.execute_tool.side_effect = [
            search_result,
            analysis_result,
            format_result
        ]
        
        # 3. 执行完整工作流
        # 解析查询
        query_result = await self.query_parser.parse_query("想买iPhone 14 Pro")
        
        # 创建执行上下文
        context = ToolExecutionContext(
            query=query_result.refined_query,
            user_id="test_user",
            session_id="test_session",
            metadata={
                "category": query_result.category,
                "price_range": query_result.price_range,
                "intent": query_result.intent
            }
        )
        
        # 执行工具链
        search_result = await self.orchestrator.execute_tool(
            "search_products",
            context,
            query=query_result.refined_query,
            category=query_result.category
        )
        
        analysis_result = await self.orchestrator.execute_tool(
            "analyze_product",
            context,
            product_data=search_result.data["products"][0]
        )
        
        format_result = await self.orchestrator.execute_tool(
            "format_results",
            context,
            results=search_result.data["products"]
        )
        
        # 4. 验证结果
        assert search_result.success is True
        assert analysis_result.success is True
        assert format_result.success is True
        
        assert len(search_result.data["products"]) == 5
        assert analysis_result.data["score"] == 88
        assert format_result.data["formatted_results"] == "格式化的产品列表"
    
    @async_test
    async def test_error_recovery_workflow(self):
        """测试错误恢复工作流"""
        # 设置搜索工具失败
        search_failure = Mock()
        search_failure.success = False
        search_failure.error = "搜索服务不可用"
        
        # 设置备用搜索成功
        backup_search_result = Mock()
        backup_search_result.success = True
        backup_search_result.data = {"products": create_test_products(2)}
        
        self.tool_registry.execute_tool.side_effect = [
            search_failure,
            backup_search_result
        ]
        
        # 创建执行上下文
        context = ToolExecutionContext(
            query="iPhone 14",
            user_id="test_user",
            session_id="test_session"
        )
        
        # 执行带错误恢复的工具
        try:
            result = await self.orchestrator.execute_tool(
                "search_products",
                context,
                query="iPhone 14"
            )
            assert False, "应该抛出异常"
        except ToolExecutionError:
            # 执行备用策略
            result = await self.orchestrator.execute_tool(
                "backup_search",
                context,
                query="iPhone 14"
            )
            
            assert result.success is True
            assert len(result.data["products"]) == 2
    
    @async_test
    async def test_concurrent_tool_execution(self):
        """测试并发工具执行"""
        # 设置多个并发工具
        tool_results = []
        for i in range(3):
            result = Mock()
            result.success = True
            result.data = {"result": f"工具{i}的结果"}
            tool_results.append(result)
        
        self.tool_registry.execute_tool.side_effect = tool_results
        
        # 创建执行上下文
        context = ToolExecutionContext(
            query="并发测试",
            user_id="test_user",
            session_id="test_session"
        )
        
        # 并发执行工具
        tasks = []
        for i in range(3):
            task = self.orchestrator.execute_tool(
                f"tool_{i}",
                context,
                param=f"value_{i}"
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        # 验证所有工具都成功执行
        assert len(results) == 3
        assert all(result.success for result in results)
        
        for i, result in enumerate(results):
            assert result.data["result"] == f"工具{i}的结果"
    
    @async_test
    async def test_workflow_performance_metrics(self):
        """测试工作流性能指标"""
        # 设置工具执行时间
        search_result = Mock()
        search_result.success = True
        search_result.data = {"products": create_test_products(3)}
        search_result.execution_time = 0.5
        
        analysis_result = Mock()
        analysis_result.success = True
        analysis_result.data = {"score": 85}
        analysis_result.execution_time = 0.3
        
        self.tool_registry.execute_tool.side_effect = [
            search_result,
            analysis_result
        ]
        
        # 创建执行上下文
        context = ToolExecutionContext(
            query="性能测试",
            user_id="test_user",
            session_id="test_session"
        )
        
        # 记录开始时间
        start_time = datetime.now()
        
        # 执行工具
        search_result = await self.orchestrator.execute_tool(
            "search_products",
            context,
            query="性能测试"
        )
        
        analysis_result = await self.orchestrator.execute_tool(
            "analyze_product",
            context,
            product_data=search_result.data["products"][0]
        )
        
        # 记录结束时间
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        # 验证性能指标
        assert search_result.execution_time == 0.5
        assert analysis_result.execution_time == 0.3
        assert total_time < 2.0  # 总时间应该少于2秒


class TestSystemIntegration:
    """系统集成测试"""
    
    def setup_method(self):
        """测试设置"""
        self.test_data_manager = TestDataManager()
        self.settings = Settings()
        
        # 创建Mock服务
        self.llm_service = AsyncMock()
        self.scraper_service = AsyncMock()
        self.analysis_service = AsyncMock()
        
        # 创建真实的组件
        self.tool_registry = ToolRegistry()
        self.query_parser = QueryParser(self.llm_service)
        self.orchestrator = ToolOrchestrator(
            llm_service=self.llm_service,
            tool_registry=self.tool_registry,
            settings=self.settings
        )
    
    @async_test
    async def test_system_initialization(self):
        """测试系统初始化"""
        # 验证所有组件都正确初始化
        assert self.llm_service is not None
        assert self.tool_registry is not None
        assert self.query_parser is not None
        assert self.orchestrator is not None
        
        # 验证配置加载
        assert self.settings.app_name == "Mercari AI Agent"
        assert self.settings.llm.default_provider == "openai"
    
    @async_test
    async def test_configuration_integration(self):
        """测试配置集成"""
        # 验证LLM配置
        assert self.settings.llm.enable_caching is True
        assert self.settings.llm.enable_cost_tracking is True
        
        # 验证工具配置
        assert self.settings.tool.tool_timeout == 30
        assert self.settings.tool.max_tool_iterations == 5
        
        # 验证成本跟踪配置
        assert self.settings.cost_tracking.enable_cost_tracking is True
        assert self.settings.cost_tracking.daily_cost_limit == 50.0
    
    def test_data_flow_integration(self):
        """测试数据流集成"""
        # 创建测试数据
        test_products = create_test_products(10)
        test_queries = create_test_queries()
        
        # 验证数据结构
        assert len(test_products) == 10
        assert len(test_queries) == 4
        
        # 验证数据完整性
        for product in test_products:
            assert hasattr(product, 'id')
            assert hasattr(product, 'title')
            assert hasattr(product, 'price')
            assert hasattr(product, 'category')
        
        for query in test_queries:
            assert hasattr(query, 'query')
            assert hasattr(query, 'expected_results')
    
    def test_error_handling_integration(self):
        """测试错误处理集成"""
        # 测试配置验证
        errors = self.settings.validate()
        
        # 如果有错误，应该是可以处理的
        if errors:
            assert isinstance(errors, list)
            assert all(isinstance(error, str) for error in errors)
    
    def teardown_method(self):
        """测试清理"""
        # 清理测试数据
        self.test_data_manager.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])