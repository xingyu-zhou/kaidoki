"""
工具基础类 - 重构版本

定义了所有工具都需要实现的基本接口和数据结构。

Author: Kaidoki Team (Refactored)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Type, Union
from enum import Enum
import json
import logging
from datetime import datetime

from ...shared.utils.logger_utils import get_logger

logger = get_logger(__name__)


class ToolStatus(Enum):
    """工具执行状态"""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class ToolResult:
    """工具执行结果"""
    status: ToolStatus
    data: Optional[Any] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def is_success(self) -> bool:
        """检查是否执行成功"""
        return self.status == ToolStatus.SUCCESS
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "status": self.status.value,
            "data": self.data,
            "error": self.error,
            "execution_time": self.execution_time,
            "metadata": self.metadata or {}
        }


class BaseTool(ABC):
    """工具基础类"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.created_at = datetime.now()
        self.call_count = 0
        self.total_execution_time = 0.0
        
    @property
    @abstractmethod
    def schema(self) -> Dict[str, Any]:
        """返回工具的JSON Schema定义"""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """执行工具逻辑"""
        pass
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """验证参数是否符合schema"""
        try:
            # 简单的参数验证
            schema = self.schema
            required_params = schema.get("parameters", {}).get("required", [])
            
            # 增强的调试信息
            logger.debug(f"🔍 Tool {self.name} parameter validation:")
            logger.debug(f"  Required params: {required_params}")
            logger.debug(f"  Provided params: {list(parameters.keys())}")
            logger.debug(f"  Provided values: {parameters}")
            
            for param in required_params:
                if param not in parameters:
                    logger.error(f"❌ Missing required parameter '{param}' for tool {self.name}")
                    logger.error(f"  Required: {required_params}")
                    logger.error(f"  Provided: {list(parameters.keys())}")
                    return False
                else:
                    logger.debug(f"  ✅ Found required parameter: {param} = {parameters[param]}")
            
            logger.debug(f"  ✅ All required parameters found for tool {self.name}")
            return True
        except Exception as e:
            logger.error(f"Parameter validation failed for tool {self.name}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    async def call(self, **kwargs) -> ToolResult:
        """调用工具的主要方法"""
        start_time = datetime.now()
        
        try:
            # 验证参数
            if not self.validate_parameters(kwargs):
                return ToolResult(
                    status=ToolStatus.ERROR,
                    error=f"Invalid parameters for tool {self.name}"
                )
            
            # 执行工具
            result = await self.execute(**kwargs)
            
            # 更新统计信息
            execution_time = (datetime.now() - start_time).total_seconds()
            result.execution_time = execution_time
            self.call_count += 1
            self.total_execution_time += execution_time
            
            logger.info(f"Tool {self.name} executed successfully in {execution_time:.2f}s")
            return result
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Tool {self.name} failed: {e}")
            return ToolResult(
                status=ToolStatus.ERROR,
                error=str(e),
                execution_time=execution_time
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取工具统计信息"""
        avg_execution_time = (
            self.total_execution_time / self.call_count 
            if self.call_count > 0 else 0.0
        )
        
        return {
            "name": self.name,
            "call_count": self.call_count,
            "total_execution_time": self.total_execution_time,
            "average_execution_time": avg_execution_time,
            "created_at": self.created_at.isoformat()
        }
    
    def to_openai_function(self) -> Dict[str, Any]:
        """转换为OpenAI函数调用格式"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.schema.get("parameters", {})
        }
    
    def to_anthropic_tool(self) -> Dict[str, Any]:
        """转换为Anthropic工具格式"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.schema.get("parameters", {})
        }
    
    def __str__(self) -> str:
        return f"Tool(name={self.name}, calls={self.call_count})"
    
    def __repr__(self) -> str:
        return self.__str__()


class ToolError(Exception):
    """工具执行错误"""
    
    def __init__(self, message: str, tool_name: str = None):
        super().__init__(message)
        self.tool_name = tool_name
        self.message = message
    
    def __str__(self) -> str:
        if self.tool_name:
            return f"Tool '{self.tool_name}' error: {self.message}"
        return f"Tool error: {self.message}"


class ToolTimeoutError(ToolError):
    """工具超时错误"""
    pass


class ToolValidationError(ToolError):
    """工具参数验证错误"""
    pass