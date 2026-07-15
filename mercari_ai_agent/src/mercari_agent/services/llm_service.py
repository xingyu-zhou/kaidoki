"""
LLM服务模块

该模块提供统一的LLM服务接口，支持多种LLM提供商。
实现了自动故障转移、负载均衡和统一的API接口。

支持的LLM提供商：
- OpenAI GPT系列
- Anthropic Claude系列
- 其他兼容OpenAI API的模型

主要功能：
- 多LLM提供商支持
- 自动故障转移
- 统一的响应格式
- 流式响应支持
- 工具调用支持

Author: Mercari AI Agent Team
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union, AsyncIterator, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import json
import time
import hashlib
import weakref
from collections import defaultdict

from ..utils.logger import get_logger
from ..utils.cache_manager import CacheManager
from ..config.settings import load_settings
from ..core.tools.tool_registry import ToolRegistry
from ..core.tools.base_tool import BaseTool, ToolResult

logger = get_logger(__name__)


class LLMProvider(Enum):
    """LLM提供商枚举"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"
    GOOGLE = "google"
    
    def __str__(self):
        """字符串表示"""
        return self.value
    
    def __json__(self):
        """JSON序列化支持"""
        return self.value
    
    @classmethod
    def from_string(cls, value: str):
        """从字符串创建枚举"""
        for provider in cls:
            if provider.value == value:
                return provider
        raise ValueError(f"Unknown LLM provider: {value}")


@dataclass
class LLMResponse:
    """LLM响应结果"""
    content: str
    provider: LLMProvider
    model: str
    usage: Dict[str, Any]
    latency: float
    metadata: Optional[Dict[str, Any]] = None
    cost: Optional[float] = None
    cached: bool = False
    tool_calls: Optional[List[Dict[str, Any]]] = None


@dataclass
class LLMStreamResponse:
    """LLM流式响应结果"""
    content: str
    finished: bool
    provider: LLMProvider
    model: str
    metadata: Optional[Dict[str, Any]] = None
    cost: Optional[float] = None


@dataclass
class CostTracker:
    """成本跟踪器"""
    total_cost: float = 0.0
    provider_costs: Dict[LLMProvider, float] = field(default_factory=dict)
    model_costs: Dict[str, float] = field(default_factory=dict)
    daily_costs: Dict[str, float] = field(default_factory=dict)
    monthly_costs: Dict[str, float] = field(default_factory=dict)
    request_count: int = 0
    token_count: int = 0
    
    def add_cost(self, provider: LLMProvider, model: str, cost: float, tokens: int):
        """添加成本记录"""
        self.total_cost += cost
        self.provider_costs[provider] = self.provider_costs.get(provider, 0) + cost
        self.model_costs[model] = self.model_costs.get(model, 0) + cost
        self.request_count += 1
        self.token_count += tokens
        
        # 按日期记录
        today = datetime.now().strftime("%Y-%m-%d")
        month = datetime.now().strftime("%Y-%m")
        
        self.daily_costs[today] = self.daily_costs.get(today, 0) + cost
        self.monthly_costs[month] = self.monthly_costs.get(month, 0) + cost


@dataclass
class RateLimiter:
    """速率限制器"""
    requests_per_minute: int
    tokens_per_minute: int
    requests_count: int = 0
    tokens_count: int = 0
    window_start: datetime = field(default_factory=datetime.now)
    
    async def wait_if_needed(self, estimated_tokens: int = 0):
        """如果需要则等待"""
        now = datetime.now()
        
        # 重置窗口
        if (now - self.window_start).total_seconds() >= 60:
            self.requests_count = 0
            self.tokens_count = 0
            self.window_start = now
        
        # 检查是否需要等待
        if (self.requests_count >= self.requests_per_minute or
            self.tokens_count + estimated_tokens > self.tokens_per_minute):
            
            wait_time = 60 - (now - self.window_start).total_seconds()
            if wait_time > 0:
                await asyncio.sleep(wait_time)
                self.requests_count = 0
                self.tokens_count = 0
                self.window_start = datetime.now()
        
        self.requests_count += 1
        self.tokens_count += estimated_tokens


@dataclass
class LLMConfig:
    """LLM配置"""
    provider: LLMProvider
    model: str
    api_key: str
    base_url: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    max_retries: int = 3
    timeout: int = 30
    enable_caching: bool = True
    enable_cost_tracking: bool = True
    rate_limit_rpm: int = 60
    rate_limit_tpm: int = 40000


class LLMServiceError(Exception):
    """LLM服务异常"""
    def __init__(self, message: str, provider: Optional[LLMProvider] = None,
                 error_code: Optional[str] = None, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.provider = provider
        self.error_code = error_code
        self.original_error = original_error
        self.timestamp = datetime.now()


class LLMProviderError(LLMServiceError):
    """LLM提供商异常"""
    pass


class LLMRateLimitError(LLMServiceError):
    """LLM速率限制异常"""
    pass


class LLMQuotaExceededError(LLMServiceError):
    """LLM配额超出异常"""
    pass


class LLMAuthenticationError(LLMServiceError):
    """LLM认证异常"""
    pass


class LLMTimeoutError(LLMServiceError):
    """LLM超时异常"""
    pass


class LLMService:
    """
    LLM服务类
    
    提供统一的LLM服务接口，支持多种LLM提供商。
    包含自动故障转移、负载均衡、工具调用、缓存和成本跟踪功能。
    """
    
    def __init__(self, llm_config, tool_registry: Optional[ToolRegistry] = None):
        """初始化LLM服务"""
        self.config = llm_config
        self.providers = {}
        self.current_provider = None
        self.failover_sequence = []
        self.rate_limiters = {}
        self.usage_stats = {}
        
        # 新增功能组件
        self.tool_registry = tool_registry or ToolRegistry()
        self.cache_manager = CacheManager()
        self.cost_tracker = CostTracker()
        
        # 定价映射 (每千tokens的成本，单位：USD) - 更新到最新模型
        self.pricing_map = {
            # 新的 GPT-o3 和 GPT-o4-mini 模型定价
            "gpt-o3": {"input": 0.02, "output": 0.04},
            "gpt-o4-mini": {"input": 0.001, "output": 0.0015},
            # 保持向后兼容
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-4-turbo-preview": {"input": 0.01, "output": 0.03},
            "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
            # Claude 模型
            "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
            "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
            "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
            "claude-3.5-sonnet-20241022": {"input": 0.003, "output": 0.015}
        }
        
        # 初始化各种LLM提供商
        self._initialize_providers()
        
        logger.info("LLMService initialized with enhanced features")
    
    def _initialize_providers(self):
        """初始化LLM提供商"""
        # OpenAI
        if self.config.openai_api_key:
            try:
                import openai
                self.providers[LLMProvider.OPENAI] = self._create_openai_provider()
                if not self.current_provider:
                    self.current_provider = LLMProvider.OPENAI
                logger.info("OpenAI provider initialized")
            except ImportError:
                logger.warning("OpenAI library not installed")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI provider: {e}")
        
        # Anthropic Claude
        if self.config.anthropic_api_key:
            try:
                import anthropic
                self.providers[LLMProvider.ANTHROPIC] = self._create_anthropic_provider()
                if not self.current_provider:
                    self.current_provider = LLMProvider.ANTHROPIC
                logger.info("Anthropic provider initialized")
            except ImportError:
                logger.warning("Anthropic library not installed")
            except Exception as e:
                logger.error(f"Failed to initialize Anthropic provider: {e}")
        
        # Azure OpenAI
        if self.config.azure_api_key and self.config.azure_endpoint:
            try:
                import openai
                self.providers[LLMProvider.AZURE_OPENAI] = self._create_azure_provider()
                if not self.current_provider:
                    self.current_provider = LLMProvider.AZURE_OPENAI
                logger.info("Azure OpenAI provider initialized")
            except ImportError:
                logger.warning("OpenAI library not installed")
            except Exception as e:
                logger.error(f"Failed to initialize Azure OpenAI provider: {e}")
    
    def _create_openai_client(self):
        """创建OpenAI客户端"""
        import openai
        return openai.OpenAI(
            api_key=self.config.openai_api_key,
            base_url=self.config.openai_base_url,
            timeout=self.config.openai_timeout
        )
    
    def _create_openai_provider(self):
        """创建OpenAI提供商包装器"""
        from dataclasses import dataclass
        
        @dataclass
        class LLMConfig:
            api_key: str
            base_url: str = None
            model: str = "gpt-3.5-turbo"
        
        llm_config = LLMConfig(
            api_key=self.config.openai_api_key,
            base_url=self.config.openai_base_url,
            model=self.config.openai_model or "gpt-3.5-turbo"
        )
        return OpenAILLM(llm_config)
    
    def _create_anthropic_client(self):
        """创建Anthropic客户端"""
        import anthropic
        return anthropic.Anthropic(
            api_key=self.config.anthropic_api_key,
            timeout=self.config.anthropic_timeout
        )
    
    def _create_anthropic_provider(self):
        """创建Anthropic提供商包装器"""
        from dataclasses import dataclass
        
        @dataclass
        class LLMConfig:
            api_key: str
            model: str = "claude-3-haiku-20240307"
            timeout: int = 30
        
        llm_config = LLMConfig(
            api_key=self.config.anthropic_api_key,
            model=self.config.anthropic_model or "claude-3-haiku-20240307",
            timeout=self.config.anthropic_timeout or 30
        )
        return AnthropicLLM(llm_config)
    
    def _create_azure_client(self):
        """创建Azure OpenAI客户端"""
        import openai
        return openai.AzureOpenAI(
            api_key=self.config.azure_api_key,
            azure_endpoint=self.config.azure_endpoint,
            api_version=self.config.azure_api_version,
            timeout=self.config.openai_timeout
        )
    
    def _create_azure_provider(self):
        """创建Azure OpenAI提供商包装器"""
        from dataclasses import dataclass
        
        @dataclass
        class LLMConfig:
            api_key: str
            base_url: str = None
            model: str = "gpt-3.5-turbo"
            endpoint: str = None
            api_version: str = None
        
        llm_config = LLMConfig(
            api_key=self.config.azure_api_key,
            endpoint=self.config.azure_endpoint,
            api_version=self.config.azure_api_version,
            model=self.config.azure_model or "gpt-3.5-turbo"
        )
        return AzureOpenAILLM(llm_config)
    
    def get_available_providers(self) -> List[str]:
        """获取可用的LLM提供商"""
        return list(self.providers.keys())
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """获取成本摘要"""
        return self.cost_tracker.to_dict()
        
        # 设置故障转移序列
        self.failover_sequence = list(self.providers.keys())
        
        if not self.providers:
            raise LLMServiceError("未配置任何LLM提供商")
    
    async def generate_response(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        stop: Optional[List[str]] = None,
        response_format: Optional[str] = None,
        enable_cache: bool = True,
        **kwargs
    ) -> LLMResponse:
        """
        生成响应
        
        Args:
            prompt: 输入提示
            max_tokens: 最大token数
            temperature: 温度参数
            top_p: Top-p参数
            stop: 停止词列表
            response_format: 响应格式（json/text）
            enable_cache: 是否启用缓存
            **kwargs: 其他参数
            
        Returns:
            LLMResponse: 响应结果
            
        Raises:
            LLMServiceError: 所有提供商都失败时抛出
        """
        # 生成缓存键
        cache_key = None
        if enable_cache:
            cache_key = self._generate_cache_key(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                stop=stop,
                response_format=response_format,
                **kwargs
            )
            
            # 检查缓存
            cached_response = await self.cache_manager.get(cache_key)
            if cached_response:
                logger.info("从缓存返回响应")
                cached_response.cached = True
                return cached_response
        
        last_error = None
        
        for provider in self._get_provider_sequence():
            try:
                # 速率限制检查
                await self._check_rate_limit(provider)
                
                # 获取LLM实例
                llm = self.providers[provider]
                
                # 调用LLM
                start_time = time.time()
                response = await llm.generate_response(
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    stop=stop,
                    response_format=response_format,
                    **kwargs
                )
                latency = time.time() - start_time
                
                # 计算成本
                cost = self._calculate_cost(provider, response["model"], response.get("usage", {}))
                
                # 构建响应
                llm_response = LLMResponse(
                    content=response["content"],
                    provider=provider,
                    model=response["model"],
                    usage=response.get("usage", {}),
                    latency=latency,
                    metadata=response.get("metadata", {}),
                    cost=cost,
                    cached=False,
                    tool_calls=response.get("tool_calls", [])
                )
                
                # 更新使用统计和成本跟踪
                self._update_usage_stats(provider, llm_response)
                self._update_cost_tracking(provider, llm_response)
                
                # 缓存响应
                if enable_cache and cache_key:
                    await self.cache_manager.set(cache_key, llm_response, ttl=3600)
                
                logger.info(f"LLM响应生成成功: {provider.value}, 耗时: {latency:.2f}s, 成本: ${cost:.6f}")
                return llm_response
                
            except Exception as e:
                handled_error = self._handle_provider_error(e, provider)
                logger.warning(f"LLM提供商 {provider.value} 调用失败: {handled_error}")
                last_error = handled_error
                
                # 如果是认证错误，跳过重试
                if isinstance(handled_error, LLMAuthenticationError):
                    continue
                    
                # 如果是速率限制错误，等待后重试
                if isinstance(handled_error, LLMRateLimitError):
                    await asyncio.sleep(60)  # 等待1分钟后重试
                    
                continue
        
        # 所有提供商都失败
        raise LLMServiceError(f"所有LLM提供商都失败，最后一个错误: {last_error}")
    
    def _handle_provider_error(self, error: Exception, provider: LLMProvider) -> LLMServiceError:
        """处理提供商错误，转换为具体的错误类型"""
        error_message = str(error)
        error_lower = error_message.lower()
        
        # 速率限制错误
        if any(keyword in error_lower for keyword in ['rate limit', 'quota exceeded', 'too many requests']):
            return LLMRateLimitError(f"速率限制: {error_message}", provider, "RATE_LIMIT", error)
        
        # 认证错误
        if any(keyword in error_lower for keyword in ['authentication', 'unauthorized', 'invalid api key', 'api key']):
            return LLMAuthenticationError(f"认证失败: {error_message}", provider, "AUTH_ERROR", error)
        
        # 配额超出错误
        if any(keyword in error_lower for keyword in ['quota', 'billing', 'payment']):
            return LLMQuotaExceededError(f"配额超出: {error_message}", provider, "QUOTA_EXCEEDED", error)
        
        # 超时错误
        if any(keyword in error_lower for keyword in ['timeout', 'timed out', 'time out']):
            return LLMTimeoutError(f"请求超时: {error_message}", provider, "TIMEOUT", error)
        
        # 通用提供商错误
        return LLMProviderError(f"提供商错误: {error_message}", provider, "PROVIDER_ERROR", error)
    
    async def stream_response(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> AsyncIterator[LLMStreamResponse]:
        """
        流式生成响应
        
        Args:
            prompt: 输入提示
            max_tokens: 最大token数
            temperature: 温度参数
            **kwargs: 其他参数
            
        Yields:
            LLMStreamResponse: 流式响应块
            
        Raises:
            LLMServiceError: 所有提供商都失败时抛出
        """
        last_error = None
        
        for provider in self._get_provider_sequence():
            try:
                # 速率限制检查
                await self._check_rate_limit(provider)
                
                # 获取LLM实例
                llm = self.providers[provider]
                
                # 检查是否支持流式
                if not hasattr(llm, 'stream_response'):
                    continue
                
                # 流式调用
                async for chunk in llm.stream_response(
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs
                ):
                    yield LLMStreamResponse(
                        content=chunk["content"],
                        finished=chunk["finished"],
                        provider=provider,
                        model=chunk["model"],
                        metadata=chunk.get("metadata", {})
                    )
                
                logger.info(f"LLM流式响应完成: {provider.value}")
                return
                
            except Exception as e:
                handled_error = self._handle_provider_error(e, provider)
                logger.warning(f"LLM提供商 {provider.value} 流式调用失败: {handled_error}")
                last_error = handled_error
                continue
        
        raise LLMServiceError(f"所有LLM提供商都失败，最后一个错误: {last_error}")
    
    async def generate_with_tools(
        self,
        prompt: str,
        tools: Optional[List[str]] = None,
        max_iterations: int = 5,
        **kwargs
    ) -> LLMResponse:
        """Generate response with tools"""
        if not self.tool_registry:
            return await self.generate_response(prompt, **kwargs)
        
        # 获取工具定义
        if tools is None:
            tool_definitions = self.tool_registry.get_openai_functions()
        else:
            tool_definitions = []
            for tool_name in tools:
                tool = self.tool_registry.get_tool(tool_name)
                if tool:
                    tool_definitions.append(tool.to_openai_function())
        
        current_prompt = prompt
        iteration = 0
        
        while iteration < max_iterations:
            # 使用工具调用
            response = await self.function_call(
                prompt=current_prompt,
                functions=tool_definitions,
                **kwargs
            )
            
            # 如果没有工具调用，直接返回
            if not response.get("function_name"):
                return LLMResponse(
                    content=response["content"],
                    provider=self.current_provider,
                    model="",
                    usage={},
                    latency=0,
                    tool_calls=[]
                )
            
            # 执行工具调用
            tool_name = response["function_name"]
            tool_args = response["arguments"]
            
            try:
                tool_result = await self.tool_registry.call_tool(tool_name, **tool_args)
                
                # 构建下一轮提示
                result_data = tool_result.data if tool_result.is_success() else tool_result.error
                current_prompt = f"原始请求: {prompt}\n\n工具调用结果:\n工具: {tool_name}\n参数: {tool_args}\n结果: {result_data}\n\n请基于这些信息提供最终回答。"
                
                iteration += 1
                
                # 如果工具执行成功且获得最终结果，可以结束
                if tool_result.is_success() and iteration >= max_iterations - 1:
                    break
                    
            except Exception as e:
                logger.error(f"工具调用失败: {e}")
                current_prompt = f"原始请求: {prompt}\n\n工具调用失败:\n工具: {tool_name}\n参数: {tool_args}\n错误: {str(e)}\n\n请基于可用信息提供回答。"
                break
        
        # 生成最终响应
        return await self.generate_response(current_prompt, **kwargs)
    
    async def chat_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[str]] = None,
        **kwargs
    ) -> LLMResponse:
        """Multi-turn conversation with tool calls"""
        # 构建完整的对话提示
        conversation = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in messages
        ])
        
        return await self.generate_with_tools(
            prompt=conversation,
            tools=tools,
            **kwargs
        )
    
    def _generate_cache_key(self, prompt: str, max_tokens=None, temperature=None,
                           top_p=None, stop=None, response_format=None, **kwargs) -> str:
        """Generate cache key"""
        cache_data = {
            "prompt": prompt,
            "provider": self.current_provider.value if self.current_provider else "unknown",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stop": stop,
            "response_format": response_format,
            **kwargs
        }
        
        cache_string = json.dumps(cache_data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(cache_string.encode()).hexdigest()
    
    def _calculate_cost(self, provider: LLMProvider, model: str, usage: Dict[str, Any]) -> float:
        """Calculate cost"""
        if not usage or model not in self.pricing_map:
            return 0.0
        
        pricing = self.pricing_map[model]
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        
        return input_cost + output_cost
    
    def _update_cost_tracking(self, provider: LLMProvider, response: LLMResponse):
        """Update cost tracking"""
        if response.cost and response.cost > 0:
            self.cost_tracker.add_cost(
                provider=provider,
                model=response.model,
                cost=response.cost,
                tokens=response.usage.get("total_tokens", 0)
            )
    
    async def _check_rate_limit(self, provider: LLMProvider):
        """Check rate limit"""
        if provider in self.rate_limiters:
            await self.rate_limiters[provider].wait_if_needed()
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost summary"""
        return {
            "total_cost": self.cost_tracker.total_cost,
            "provider_costs": {k.value: v for k, v in self.cost_tracker.provider_costs.items()},
            "model_costs": self.cost_tracker.model_costs.copy(),
            "daily_costs": self.cost_tracker.daily_costs.copy(),
            "monthly_costs": self.cost_tracker.monthly_costs.copy(),
            "request_count": self.cost_tracker.request_count,
            "token_count": self.cost_tracker.token_count,
            "average_cost_per_request": (
                self.cost_tracker.total_cost / self.cost_tracker.request_count
                if self.cost_tracker.request_count > 0 else 0
            )
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        metrics = {
            "providers": {},
            "cache_stats": self.cache_manager.get_stats() if hasattr(self.cache_manager, 'get_stats') else {},
            "cost_summary": self.get_cost_summary()
        }
        
        for provider, stats in self.usage_stats.items():
            avg_latency = stats["total_latency"] / stats["total_requests"] if stats["total_requests"] > 0 else 0
            metrics["providers"][provider.value] = {
                "total_requests": stats["total_requests"],
                "total_tokens": stats["total_tokens"],
                "average_latency": avg_latency,
                "error_count": stats["error_count"],
                "last_used": stats["last_used"].isoformat() if stats["last_used"] else None
            }
        
        return metrics
    
    def register_tool(self, tool: BaseTool, category: str = "general"):
        """Register tool"""
        self.tool_registry.register(tool, category)
        logger.info(f"Tool registered: {tool.name}")
    
    def register_tools(self, tools: List[BaseTool], category: str = "general"):
        """Register multiple tools"""
        for tool in tools:
            self.register_tool(tool, category)
    
    async def optimize_provider_selection(self):
        """Optimize provider selection strategy"""
        provider_scores = {}
        
        for provider in self.providers.keys():
            cost = self.cost_tracker.provider_costs.get(provider, 0)
            stats = self.usage_stats.get(provider, {})
            
            avg_latency = (stats.get("total_latency", 0) / stats.get("total_requests", 1))
            error_rate = stats.get("error_count", 0) / stats.get("total_requests", 1)
            
            score = avg_latency * 0.3 + cost * 0.4 + error_rate * 0.3
            provider_scores[provider] = score
        
        self.failover_sequence = sorted(provider_scores.keys(), key=lambda x: provider_scores[x])
        
        if self.failover_sequence:
            self.current_provider = self.failover_sequence[0]
        
        logger.info(f"Provider selection optimized: {[p.value for p in self.failover_sequence]}")
    
    async def function_call(
        self,
        prompt: str,
        functions: List[Dict[str, Any]],
        function_call: Union[str, Dict[str, str]] = "auto",
        **kwargs
    ) -> Dict[str, Any]:
        """
        工具调用
        
        Args:
            prompt: 输入提示
            functions: 函数定义列表
            function_call: 函数调用模式
            **kwargs: 其他参数
            
        Returns:
            Dict[str, Any]: 函数调用结果
            
        Raises:
            LLMServiceError: 所有提供商都失败时抛出
        """
        last_error = None
        
        for provider in self._get_provider_sequence():
            try:
                # 速率限制检查
                await self._check_rate_limit(provider)
                
                # 获取LLM实例
                llm = self.providers[provider]
                
                # 检查是否支持函数调用
                if not hasattr(llm, 'function_call'):
                    continue
                
                # 函数调用
                result = await llm.function_call(
                    prompt=prompt,
                    functions=functions,
                    function_call=function_call,
                    **kwargs
                )
                
                logger.info(f"LLM函数调用成功: {provider.value}")
                return result
                
            except Exception as e:
                logger.warning(f"LLM提供商 {provider.value} 函数调用失败: {e}")
                last_error = e
                continue
        
        raise LLMServiceError(f"所有LLM提供商都失败，最后一个错误: {last_error}")
    
    def _get_provider_sequence(self) -> List[LLMProvider]:
        """
        获取提供商使用序列
        
        Returns:
            List[LLMProvider]: 提供商序列
        """
        if self.current_provider and self.current_provider in self.providers:
            # 当前提供商优先
            sequence = [self.current_provider]
            sequence.extend([p for p in self.failover_sequence if p != self.current_provider])
            return sequence
        else:
            return self.failover_sequence
    
    def _update_usage_stats(self, provider: LLMProvider, response: LLMResponse):
        """
        更新使用统计
        
        Args:
            provider: 提供商
            response: 响应结果
        """
        if provider not in self.usage_stats:
            self.usage_stats[provider] = {
                "total_requests": 0,
                "total_tokens": 0,
                "total_latency": 0.0,
                "error_count": 0,
                "last_used": None
            }
        
        stats = self.usage_stats[provider]
        stats["total_requests"] += 1
        stats["total_tokens"] += response.usage.get("total_tokens", 0)
        stats["total_latency"] += response.latency
        stats["last_used"] = datetime.now()
    
    def get_usage_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        获取使用统计
        
        Returns:
            Dict[str, Dict[str, Any]]: 使用统计
        """
        return self.usage_stats.copy()
    
    def switch_provider(self, provider: LLMProvider):
        """
        切换提供商
        
        Args:
            provider: 新的提供商
            
        Raises:
            ValueError: 提供商不存在
        """
        if provider not in self.providers:
            raise ValueError(f"提供商 {provider.value} 不存在")
        
        old_provider = self.current_provider
        self.current_provider = provider
        
        logger.info(f"LLM提供商切换: {old_provider.value} -> {provider.value}")
    
    async def close(self):
        """关闭LLM服务，清理所有资源"""
        close_errors = []
        
        # 关闭所有提供商的HTTP客户端
        for provider_name, provider in self.providers.items():
            try:
                if hasattr(provider, 'close'):
                    await provider.close()
                elif hasattr(provider, 'client') and hasattr(provider.client, 'close'):
                    await provider.client.close()
                logger.debug(f"LLM提供商 {provider_name} 已关闭")
            except Exception as e:
                logger.error(f"关闭LLM提供商 {provider_name} 时出错: {e}")
                close_errors.append(f"Provider {provider_name}: {e}")
        
        # 关闭缓存管理器
        try:
            if hasattr(self.cache_manager, 'close'):
                await self.cache_manager.close()
        except Exception as e:
            logger.error(f"关闭缓存管理器时出错: {e}")
            close_errors.append(f"Cache manager: {e}")
        
        # 清理引用
        self.providers.clear()
        self.current_provider = None
        
        if close_errors:
            logger.warning(f"LLM服务关闭时遇到错误: {close_errors}")
        else:
            logger.info("LLM服务已完全关闭")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
        return False


class BaseLLM:
    """基础LLM类"""
    
    def __init__(self, model: str):
        self.model = model
    
    async def generate_response(self, **kwargs) -> Dict[str, Any]:
        """生成响应 - 需要子类实现"""
        raise NotImplementedError
    
    async def stream_response(self, **kwargs) -> AsyncIterator[Dict[str, Any]]:
        """流式响应 - 需要子类实现"""
        raise NotImplementedError
    
    async def function_call(self, **kwargs) -> Dict[str, Any]:
        """函数调用 - 需要子类实现"""
    
    async def close(self):
        """关闭LLM客户端 - 子类可以重写"""
        pass
        raise NotImplementedError


class OpenAILLM(BaseLLM):
    """OpenAI LLM实现"""
    
    def __init__(self, config: LLMConfig):
        super().__init__(config.model)
        self.config = config
        self.api_key = config.api_key
        self.base_url = config.base_url
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """初始化OpenAI客户端"""
        try:
            import openai
            self.client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        except ImportError:
            raise LLMServiceError("OpenAI库未安装，请运行: pip install openai")
    
    async def generate_response(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        stop: Optional[List[str]] = None,
        response_format: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """生成响应"""
        messages = [{"role": "user", "content": prompt}]
        
        request_params = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stop": stop,
            **kwargs
        }
        
        # 处理响应格式
        if response_format == "json":
            request_params["response_format"] = {"type": "json_object"}
        
        # 移除None值
        request_params = {k: v for k, v in request_params.items() if v is not None}
        
        response = await self.client.chat.completions.create(**request_params)
        
        return {
            "content": response.choices[0].message.content,
            "model": response.model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            },
            "metadata": {
                "finish_reason": response.choices[0].finish_reason,
                "response_id": response.id
            }
        }
    
    async def function_call(
        self,
        prompt: str,
        functions: List[Dict[str, Any]],
        function_call: Union[str, Dict[str, str]] = "auto",
        **kwargs
    ) -> Dict[str, Any]:
        """函数调用"""
        messages = [{"role": "user", "content": prompt}]
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            functions=functions,
            function_call=function_call,
            **kwargs
        )
        
        message = response.choices[0].message
        if message.function_call:
            return {
                "function_name": message.function_call.name,
                "arguments": json.loads(message.function_call.arguments),
                "content": message.content
            }
        else:
            return {
                "function_name": None,
                "arguments": None,
                "content": message.content
            }


class AnthropicLLM(BaseLLM):
    """Anthropic Claude LLM实现"""
    
    def __init__(self, config: LLMConfig):
        super().__init__(config.model)
        self.config = config
        self.api_key = config.api_key
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """初始化Anthropic客户端"""
        try:
            import anthropic
            self.client = anthropic.AsyncAnthropic(api_key=self.api_key)
        except ImportError:
            raise LLMServiceError("Anthropic库未安装，请运行: pip install anthropic")
    
    async def generate_response(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        stop: Optional[List[str]] = None,
        response_format: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """生成响应"""
        request_params = {
            "model": self.model,
            "max_tokens": max_tokens or 1000,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "top_p": top_p,
            "stop_sequences": stop,
            **kwargs
        }
        
        # 移除None值
        request_params = {k: v for k, v in request_params.items() if v is not None}
        
        response = await self.client.messages.create(**request_params)
        
        return {
            "content": response.content[0].text,
            "model": response.model,
            "usage": {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
            },
            "metadata": {
                "response_id": response.id,
                "stop_reason": response.stop_reason
            }
        }
    
    async def function_call(
        self,
        prompt: str,
        functions: List[Dict[str, Any]],
        function_call: Union[str, Dict[str, str]] = "auto",
        **kwargs
    ) -> Dict[str, Any]:
        """函数调用（通过工具实现）"""
        tools = []
        for func in functions:
            tools.append({
                "name": func["name"],
                "description": func["description"],
                "input_schema": func["parameters"]
            })
        
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
            tools=tools,
            **kwargs
        )
        
        # 处理工具调用
        if response.content and len(response.content) > 1:
            for content in response.content:
                if content.type == "tool_use":
                    return {
                        "function_name": content.name,
                        "arguments": content.input,
                        "content": None
                    }
        
        return {
            "function_name": None,
            "arguments": None,
            "content": response.content[0].text if response.content else None
        }


class AzureOpenAILLM(BaseLLM):
    """Azure OpenAI LLM实现"""
    
    def __init__(self, config: LLMConfig):
        super().__init__(config.model)
        self.config = config
        self.api_key = config.api_key
        self.endpoint = config.base_url
        self.deployment = config.model
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """初始化Azure OpenAI客户端"""
        try:
            import openai
            self.client = openai.AsyncAzureOpenAI(
                api_key=self.api_key,
                api_version="2023-12-01-preview",
                azure_endpoint=self.endpoint
            )
        except ImportError:
            raise LLMServiceError("OpenAI库未安装，请运行: pip install openai")
    
    async def generate_response(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """生成响应"""
        messages = [{"role": "user", "content": prompt}]
        
        response = await self.client.chat.completions.create(
            model=self.deployment,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )
        
        return {
            "content": response.choices[0].message.content,
            "model": response.model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            },
            "metadata": {
                "finish_reason": response.choices[0].finish_reason,
                "response_id": response.id
            }
        }