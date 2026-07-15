"""
工具注册和管理系统 - 重构版本

提供动态工具注册、发现和调用管理功能。

Author: Kaidoki Team (Refactored)
"""

import asyncio
from typing import Dict, List, Optional, Type, Any, Callable
from collections import defaultdict
from datetime import datetime
import inspect
from functools import wraps

from .base_tool import BaseTool, ToolResult, ToolStatus, ToolError
from ...shared.utils.logger_utils import get_logger

logger = get_logger(__name__)


class ToolRegistry:
    """工具注册表 - 重构版本"""
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._categories: Dict[str, List[str]] = defaultdict(list)
        self._middleware: List[Callable] = []
        self._hooks: Dict[str, List[Callable]] = defaultdict(list)
        
    def register(self, tool: BaseTool, category: str = "general") -> None:
        """注册工具"""
        if tool.name in self._tools:
            logger.warning(f"Tool {tool.name} already registered, replacing...")
        
        self._tools[tool.name] = tool
        self._categories[category].append(tool.name)
        
        logger.info(f"Registered tool: {tool.name} in category: {category}")
    
    def register_tool(self, tool: BaseTool, category: str = "general") -> None:
        """注册工具（别名方法）"""
        self.register(tool, category)
    
    def register_decorator(self, name: str, description: str, 
                          schema: Dict[str, Any], category: str = "general"):
        """装饰器方式注册工具"""
        def decorator(func):
            # 创建动态工具类
            class DynamicTool(BaseTool):
                def __init__(self):
                    super().__init__(name, description)
                    self._schema = schema
                    self._func = func
                
                @property
                def schema(self) -> Dict[str, Any]:
                    return self._schema
                
                async def execute(self, **kwargs) -> ToolResult:
                    try:
                        # 检查函数是否为异步
                        if asyncio.iscoroutinefunction(self._func):
                            result = await self._func(**kwargs)
                        else:
                            result = self._func(**kwargs)
                        
                        return ToolResult(
                            status=ToolStatus.SUCCESS,
                            data=result
                        )
                    except Exception as e:
                        return ToolResult(
                            status=ToolStatus.ERROR,
                            error=str(e)
                        )
            
            # 注册工具
            tool = DynamicTool()
            self.register(tool, category)
            
            return func
        return decorator
    
    def unregister(self, tool_name: str) -> bool:
        """取消注册工具"""
        if tool_name not in self._tools:
            logger.warning(f"Tool {tool_name} not found")
            return False
        
        del self._tools[tool_name]
        
        # 从分类中移除
        for category, tools in self._categories.items():
            if tool_name in tools:
                tools.remove(tool_name)
                break
        
        logger.info(f"Unregistered tool: {tool_name}")
        return True
    
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """获取工具实例"""
        return self._tools.get(tool_name)
    
    def get_tools_by_category(self, category: str) -> List[BaseTool]:
        """根据分类获取工具列表"""
        tool_names = self._categories.get(category, [])
        return [self._tools[name] for name in tool_names if name in self._tools]
    
    def list_tools(self) -> List[str]:
        """列出所有工具名称"""
        return list(self._tools.keys())
    
    def list_categories(self) -> List[str]:
        """列出所有分类"""
        return list(self._categories.keys())
    
    def search_tools(self, query: str) -> List[BaseTool]:
        """搜索工具"""
        query_lower = query.lower()
        results = []
        
        for tool in self._tools.values():
            if (query_lower in tool.name.lower() or 
                query_lower in tool.description.lower()):
                results.append(tool)
        
        return results
    
    async def call_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """调用工具"""
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"Tool {tool_name} not found"
            )
        
        # 执行前置钩子
        await self._execute_hooks("before_call", tool_name, kwargs)
        
        # 应用中间件
        result = await self._apply_middleware(tool, **kwargs)
        
        # 执行后置钩子
        await self._execute_hooks("after_call", tool_name, result)
        
        return result
    
    def add_middleware(self, middleware: Callable) -> None:
        """添加中间件"""
        self._middleware.append(middleware)
    
    def add_hook(self, event: str, hook: Callable) -> None:
        """添加钩子函数"""
        self._hooks[event].append(hook)
    
    async def _apply_middleware(self, tool: BaseTool, **kwargs) -> ToolResult:
        """应用中间件"""
        async def _call():
            return await tool.call(**kwargs)
        
        # 从后往前应用中间件
        for middleware in reversed(self._middleware):
            if asyncio.iscoroutinefunction(middleware):
                _call = await middleware(_call)
            else:
                _call = middleware(_call)
        
        return await _call()
    
    async def _execute_hooks(self, event: str, tool_name: str, data: Any) -> None:
        """执行钩子函数"""
        hooks = self._hooks.get(event, [])
        for hook in hooks:
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook(tool_name, data)
                else:
                    hook(tool_name, data)
            except Exception as e:
                logger.error(f"Hook execution failed: {e}")
    
    def get_openai_functions(self, category: str = None) -> List[Dict[str, Any]]:
        """获取OpenAI函数格式的工具定义"""
        tools = (self.get_tools_by_category(category) if category 
                else self._tools.values())
        return [tool.to_openai_function() for tool in tools]
    
    def get_anthropic_tools(self, category: str = None) -> List[Dict[str, Any]]:
        """获取Anthropic工具格式的工具定义"""
        tools = (self.get_tools_by_category(category) if category 
                else self._tools.values())
        return [tool.to_anthropic_tool() for tool in tools]
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """获取注册表统计信息"""
        stats = {
            "total_tools": len(self._tools),
            "categories": dict(self._categories),
            "tool_stats": []
        }
        
        for tool in self._tools.values():
            stats["tool_stats"].append(tool.get_stats())
        
        return stats
    
    def export_tools(self, format: str = "json") -> Any:
        """导出工具定义"""
        if format == "json":
            return {
                "tools": [tool.to_openai_function() for tool in self._tools.values()],
                "categories": dict(self._categories),
                "exported_at": datetime.now().isoformat()
            }
        elif format == "openai":
            return self.get_openai_functions()
        elif format == "anthropic":
            return self.get_anthropic_tools()
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def clear(self) -> None:
        """清空注册表"""
        self._tools.clear()
        self._categories.clear()
        logger.info("Registry cleared")
    
    def __len__(self) -> int:
        return len(self._tools)
    
    def __contains__(self, tool_name: str) -> bool:
        return tool_name in self._tools
    
    def __iter__(self):
        return iter(self._tools.values())


# 全局工具注册表实例
registry = ToolRegistry()


def tool(name: str, description: str, schema: Dict[str, Any], 
         category: str = "general"):
    """工具注册装饰器"""
    return registry.register_decorator(name, description, schema, category)


def middleware(func: Callable) -> Callable:
    """中间件装饰器"""
    registry.add_middleware(func)
    return func


def hook(event: str):
    """钩子装饰器"""
    def decorator(func: Callable) -> Callable:
        registry.add_hook(event, func)
        return func
    return decorator