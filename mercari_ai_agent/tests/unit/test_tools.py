"""
工具系统单元测试

该文件包含工具系统各个组件的单元测试。

测试覆盖：
- BaseTool抽象类
- ToolRegistry工具注册表
- 具体工具实现
- 工具中间件
- 工具执行结果

Author: Mercari AI Agent Team
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from typing import Dict, Any, List

# 导入被测试的模块
import sys
sys.path.insert(0, 'mercari_ai_agent/src')

from mercari_agent.core.tools.base_tool import BaseTool, ToolResult, ToolStatus
from mercari_agent.core.tools.tool_registry import ToolRegistry, ToolMiddleware
from mercari_agent.core.tools.search_tools import ProductSearchTool, MarketAnalysisTool
from mercari_agent.core.tools.analysis_tools import ProductAnalysisTool, PriceAnalysisTool
from mercari_agent.core.tools.formatting_tools import ResultsFormatterTool, ReportGeneratorTool

# 导入测试工具
from tests.utils import (
    create_test_products, 
    create_test_queries,
    MockToolResult,
    async_test,
    create_test_config
)


class TestTool(BaseTool):
    """测试用工具"""
    
    def __init__(self, should_succeed: bool = True):
        super().__init__()
        self.should_succeed = should_succeed
        self.execution_count = 0
    
    @property
    def name(self) -> str:
        return "test_tool"
    
    @property
    def description(self) -> str:
        return "用于测试的工具"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "test_param": {
                "type": "string",
                "description": "测试参数",
                "required": True
            }
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        self.execution_count += 1
        
        if not self.should_succeed:
            return ToolResult(
                success=False,
                data=None,
                error="测试失败",
                status=ToolStatus.FAILED,
                execution_time=0.1
            )
        
        return ToolResult(
            success=True,
            data={"result": f"执行成功，参数: {kwargs}"},
            status=ToolStatus.SUCCESS,
            execution_time=0.1
        )


class TestToolMiddleware(ToolMiddleware):
    """测试中间件"""
    
    def __init__(self):
        self.before_count = 0
        self.after_count = 0
    
    async def before_execute(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        self.before_count += 1
        return kwargs
    
    async def after_execute(self, tool_name: str, result: ToolResult, **kwargs) -> ToolResult:
        self.after_count += 1
        return result


class TestBaseTool:
    """BaseTool基类测试"""
    
    def test_tool_result_creation(self):
        """测试工具结果创建"""
        # 测试成功结果
        result = ToolResult(
            success=True,
            data={"test": "data"},
            status=ToolStatus.SUCCESS,
            execution_time=0.5
        )
        
        assert result.success is True
        assert result.data == {"test": "data"}
        assert result.status == ToolStatus.SUCCESS
        assert result.execution_time == 0.5
        assert result.error is None
        assert isinstance(result.timestamp, datetime)
    
    def test_tool_result_failure(self):
        """测试工具失败结果"""
        result = ToolResult(
            success=False,
            data=None,
            error="测试错误",
            status=ToolStatus.FAILED,
            execution_time=0.1
        )
        
        assert result.success is False
        assert result.data is None
        assert result.error == "测试错误"
        assert result.status == ToolStatus.FAILED
    
    def test_tool_result_to_dict(self):
        """测试工具结果转字典"""
        result = ToolResult(
            success=True,
            data={"test": "data"},
            status=ToolStatus.SUCCESS,
            execution_time=0.5
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["success"] is True
        assert result_dict["data"] == {"test": "data"}
        assert result_dict["status"] == "SUCCESS"
        assert result_dict["execution_time"] == 0.5
        assert "timestamp" in result_dict
    
    @async_test
    async def test_tool_execution(self):
        """测试工具执行"""
        tool = TestTool(should_succeed=True)
        
        result = await tool.execute(test_param="test_value")
        
        assert result.success is True
        assert result.data["result"] == "执行成功，参数: {'test_param': 'test_value'}"
        assert result.status == ToolStatus.SUCCESS
        assert tool.execution_count == 1
    
    @async_test
    async def test_tool_execution_failure(self):
        """测试工具执行失败"""
        tool = TestTool(should_succeed=False)
        
        result = await tool.execute(test_param="test_value")
        
        assert result.success is False
        assert result.error == "测试失败"
        assert result.status == ToolStatus.FAILED
        assert tool.execution_count == 1
    
    def test_tool_properties(self):
        """测试工具属性"""
        tool = TestTool()
        
        assert tool.name == "test_tool"
        assert tool.description == "用于测试的工具"
        assert "test_param" in tool.parameters
        assert tool.parameters["test_param"]["type"] == "string"
        assert tool.parameters["test_param"]["required"] is True


class TestToolRegistry:
    """工具注册表测试"""
    
    def setup_method(self):
        """测试设置"""
        self.registry = ToolRegistry()
    
    def test_tool_registration(self):
        """测试工具注册"""
        tool = TestTool()
        
        self.registry.register_tool(tool)
        
        assert "test_tool" in self.registry.tools
        assert self.registry.tools["test_tool"] == tool
    
    def test_tool_registration_duplicate(self):
        """测试重复工具注册"""
        tool1 = TestTool()
        tool2 = TestTool()
        
        self.registry.register_tool(tool1)
        
        with pytest.raises(ValueError, match="工具.*已存在"):
            self.registry.register_tool(tool2)
    
    def test_tool_registration_with_override(self):
        """测试工具注册覆盖"""
        tool1 = TestTool()
        tool2 = TestTool()
        
        self.registry.register_tool(tool1)
        self.registry.register_tool(tool2, override=True)
        
        assert self.registry.tools["test_tool"] == tool2
    
    def test_get_tool(self):
        """测试获取工具"""
        tool = TestTool()
        self.registry.register_tool(tool)
        
        retrieved_tool = self.registry.get_tool("test_tool")
        
        assert retrieved_tool == tool
    
    def test_get_tool_not_found(self):
        """测试获取不存在的工具"""
        with pytest.raises(KeyError, match="工具.*未找到"):
            self.registry.get_tool("non_existent_tool")
    
    def test_list_tools(self):
        """测试列出工具"""
        tool1 = TestTool()
        tool2 = TestTool()
        tool2.name = "test_tool_2"
        
        self.registry.register_tool(tool1)
        self.registry.register_tool(tool2)
        
        tools = self.registry.list_tools()
        
        assert len(tools) == 2
        assert "test_tool" in tools
        assert "test_tool_2" in tools
    
    def test_middleware_registration(self):
        """测试中间件注册"""
        middleware = TestToolMiddleware()
        
        self.registry.add_middleware(middleware)
        
        assert middleware in self.registry.middlewares
    
    @async_test
    async def test_tool_execution_with_middleware(self):
        """测试带中间件的工具执行"""
        tool = TestTool()
        middleware = TestToolMiddleware()
        
        self.registry.register_tool(tool)
        self.registry.add_middleware(middleware)
        
        result = await self.registry.execute_tool("test_tool", test_param="test_value")
        
        assert result.success is True
        assert middleware.before_count == 1
        assert middleware.after_count == 1
    
    @async_test
    async def test_tool_execution_not_found(self):
        """测试执行不存在的工具"""
        with pytest.raises(KeyError, match="工具.*未找到"):
            await self.registry.execute_tool("non_existent_tool")
    
    def test_tool_discovery(self):
        """测试工具发现"""
        # 模拟工具发现
        with patch('importlib.import_module') as mock_import:
            mock_module = Mock()
            mock_module.ProductSearchTool = TestTool
            mock_import.return_value = mock_module
            
            self.registry.discover_tools(["test_module"])
            
            assert "test_tool" in self.registry.tools


class TestProductSearchTool:
    """商品搜索工具测试"""
    
    def setup_method(self):
        """测试设置"""
        self.scraper_service = AsyncMock()
        self.tool = ProductSearchTool(self.scraper_service)
    
    def test_tool_properties(self):
        """测试工具属性"""
        assert self.tool.name == "search_products"
        assert "搜索Mercari商品" in self.tool.description
        assert "query" in self.tool.parameters
        assert self.tool.parameters["query"]["required"] is True
    
    @async_test
    async def test_search_execution(self):
        """测试搜索执行"""
        # 设置Mock返回值
        test_products = create_test_products(5)
        self.scraper_service.search_products.return_value = {
            "products": [p.__dict__ for p in test_products],
            "total": 100,
            "page": 1
        }
        
        result = await self.tool.execute(
            query="iPhone",
            category="家電",
            max_price=50000
        )
        
        assert result.success is True
        assert len(result.data["products"]) == 5
        assert result.data["total"] == 100
        assert result.status == ToolStatus.SUCCESS
        
        # 验证调用参数
        self.scraper_service.search_products.assert_called_once_with(
            query="iPhone",
            category="家電",
            max_price=50000
        )
    
    @async_test
    async def test_search_execution_failure(self):
        """测试搜索执行失败"""
        # 设置Mock抛出异常
        self.scraper_service.search_products.side_effect = Exception("搜索失败")
        
        result = await self.tool.execute(query="iPhone")
        
        assert result.success is False
        assert "搜索失败" in result.error
        assert result.status == ToolStatus.FAILED


class TestProductAnalysisTool:
    """商品分析工具测试"""
    
    def setup_method(self):
        """测试设置"""
        self.analysis_service = AsyncMock()
        self.tool = ProductAnalysisTool(self.analysis_service)
    
    def test_tool_properties(self):
        """测试工具属性"""
        assert self.tool.name == "analyze_product"
        assert "分析商品信息" in self.tool.description
        assert "product_data" in self.tool.parameters
    
    @async_test
    async def test_analysis_execution(self):
        """测试分析执行"""
        # 设置Mock返回值
        test_product = create_test_products(1)[0]
        self.analysis_service.analyze_product.return_value = {
            "score": 85,
            "recommendation": "推荐购买",
            "reasons": ["价格合理", "品质良好"]
        }
        
        result = await self.tool.execute(product_data=test_product.__dict__)
        
        assert result.success is True
        assert result.data["score"] == 85
        assert result.data["recommendation"] == "推荐购买"
        assert len(result.data["reasons"]) == 2
        assert result.status == ToolStatus.SUCCESS


class TestResultsFormatterTool:
    """结果格式化工具测试"""
    
    def setup_method(self):
        """测试设置"""
        self.tool = ResultsFormatterTool()
    
    def test_tool_properties(self):
        """测试工具属性"""
        assert self.tool.name == "format_results"
        assert "格式化搜索结果" in self.tool.description
        assert "results" in self.tool.parameters
        assert "format_type" in self.tool.parameters
    
    @async_test
    async def test_format_execution(self):
        """测试格式化执行"""
        test_products = create_test_products(3)
        results = [p.__dict__ for p in test_products]
        
        result = await self.tool.execute(
            results=results,
            format_type="table"
        )
        
        assert result.success is True
        assert "formatted_results" in result.data
        assert result.data["format_type"] == "table"
        assert result.status == ToolStatus.SUCCESS
    
    @async_test
    async def test_format_execution_json(self):
        """测试JSON格式化执行"""
        test_products = create_test_products(2)
        results = [p.__dict__ for p in test_products]
        
        result = await self.tool.execute(
            results=results,
            format_type="json"
        )
        
        assert result.success is True
        assert "formatted_results" in result.data
        assert result.data["format_type"] == "json"
        
        # 验证JSON格式
        import json
        json_results = json.loads(result.data["formatted_results"])
        assert len(json_results) == 2
    
    @async_test
    async def test_format_execution_invalid_format(self):
        """测试无效格式化类型"""
        result = await self.tool.execute(
            results=[],
            format_type="invalid_format"
        )
        
        assert result.success is False
        assert "不支持的格式类型" in result.error
        assert result.status == ToolStatus.FAILED


class TestToolIntegration:
    """工具集成测试"""
    
    def setup_method(self):
        """测试设置"""
        self.registry = ToolRegistry()
        self.scraper_service = AsyncMock()
        self.analysis_service = AsyncMock()
        
        # 注册工具
        self.registry.register_tool(ProductSearchTool(self.scraper_service))
        self.registry.register_tool(ProductAnalysisTool(self.analysis_service))
        self.registry.register_tool(ResultsFormatterTool())
    
    @async_test
    async def test_tool_workflow(self):
        """测试工具工作流"""
        # 设置Mock数据
        test_products = create_test_products(3)
        self.scraper_service.search_products.return_value = {
            "products": [p.__dict__ for p in test_products],
            "total": 50,
            "page": 1
        }
        
        self.analysis_service.analyze_product.return_value = {
            "score": 80,
            "recommendation": "推荐"
        }
        
        # 执行搜索
        search_result = await self.registry.execute_tool(
            "search_products",
            query="iPhone"
        )
        
        assert search_result.success is True
        products = search_result.data["products"]
        
        # 分析第一个产品
        analysis_result = await self.registry.execute_tool(
            "analyze_product",
            product_data=products[0]
        )
        
        assert analysis_result.success is True
        assert analysis_result.data["score"] == 80
        
        # 格式化结果
        format_result = await self.registry.execute_tool(
            "format_results",
            results=products,
            format_type="table"
        )
        
        assert format_result.success is True
        assert "formatted_results" in format_result.data
    
    @async_test
    async def test_tool_error_handling(self):
        """测试工具错误处理"""
        # 设置搜索失败
        self.scraper_service.search_products.side_effect = Exception("网络错误")
        
        result = await self.registry.execute_tool("search_products", query="test")
        
        assert result.success is False
        assert "网络错误" in result.error
        assert result.status == ToolStatus.FAILED
    
    def test_tool_performance_metrics(self):
        """测试工具性能指标"""
        # 这里可以添加性能测试
        # 例如测试工具执行时间、内存使用等
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])