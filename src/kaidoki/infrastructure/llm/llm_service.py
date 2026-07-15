"""
LLM服务模块 - 重构版本

该模块提供统一的LLM服务接口，支持多种LLM提供商。
实现了自动故障转移、负载均衡和统一的API接口。

支持的LLM提供商：
- OpenAI GPT系列
- Anthropic Claude系列
- Azure OpenAI

主要功能：
- 多LLM提供商支持
- 自动故障转移
- 统一的响应格式
- 流式响应支持
- 工具调用支持
- 成本跟踪
- 缓存管理

Author: Kaidoki Team (Refactored)
"""

import asyncio
import logging
import time
import json
import hashlib
from typing import Dict, List, Optional, Any, Union, AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict

from ...shared.utils.logger_utils import get_logger
from ...shared.config import get_llm_config
from ..storage.cache_manager import CacheManager
from ...tools.framework.tool_registry import ToolRegistry
from ...tools.framework.base_tool import BaseTool, ToolResult

logger = get_logger(__name__)


class LLMProvider(Enum):
    """LLM提供商枚举"""
    BEDROCK = "bedrock"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"
    
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
    LLM服务类 - 重构版本
    
    提供统一的LLM服务接口，支持多种LLM提供商。
    包含自动故障转移、负载均衡、工具调用、缓存和成本跟踪功能。
    """
    
    def __init__(self, config=None, tool_registry: Optional[ToolRegistry] = None):
        """初始化LLM服务"""
        self.config = config or get_llm_config()
        self.providers = {}
        self.current_provider = None
        self.failover_sequence = []
        self.rate_limiters = {}
        self.usage_stats = {}
        
        # 功能组件
        self.tool_registry = tool_registry or ToolRegistry()
        self.cache_manager = CacheManager()
        self.cost_tracker = CostTracker()
        
        # 定价映射 (每千tokens的成本，单位：USD)
        self.pricing_map = {
            # OpenAI GPT-4o 系列
            "gpt-4o": {"input": 0.005, "output": 0.015},
            "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
            # 保持向后兼容
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-4-turbo-preview": {"input": 0.01, "output": 0.03},
            "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
            # Claude 模型
            "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
            "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
            "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
            "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
            # AWS Bedrock 上的 Claude（按 model_id 匹配；匹配不到则成本记 0）
            "us.anthropic.claude-sonnet-4-6": {"input": 0.003, "output": 0.015},
            "us.anthropic.claude-3-5-sonnet-20241022-v2:0": {"input": 0.003, "output": 0.015},
            "anthropic.claude-3-5-sonnet-20241022-v2:0": {"input": 0.003, "output": 0.015},
            # 规范化短名键（response.model 常返回短名；数值为按官方 tier 的近似值）
            "claude-sonnet-4-6": {"input": 0.003, "output": 0.015},
            "claude-sonnet-5": {"input": 0.003, "output": 0.015},
            "claude-haiku-4-5-20251001": {"input": 0.001, "output": 0.005},
            "claude-opus-4-7": {"input": 0.015, "output": 0.075}
        }
        
        # 初始化标记
        self._initialized = False
        
        logger.info("LLMService initialized with enhanced features")
    
    async def initialize(self):
        """异步初始化LLM服务"""
        if self._initialized:
            return
        
        try:
            # 初始化各种LLM提供商
            await self._initialize_providers()
            
            # 初始化缓存管理器
            await self.cache_manager.initialize()
            
            self._initialized = True
            logger.info("LLM服务初始化完成")
            
        except Exception as e:
            logger.error(f"LLM服务初始化失败: {e}")
            raise
    
    async def _initialize_providers(self):
        """初始化LLM提供商"""
        # AWS Bedrock (Claude) —— 主 provider，优先于 OpenAI 检查/初始化
        # 若无 AWS 凭证等原因失败，记录 error 并继续（可 fallback 到 OpenAI），不硬崩
        if self.config.has_bedrock_config():
            try:
                self.providers[LLMProvider.BEDROCK] = await self._create_bedrock_provider()
                if not self.current_provider:
                    self.current_provider = LLMProvider.BEDROCK
                logger.info("Bedrock (Claude) provider initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Bedrock provider: {e}")

        # OpenAI
        if self.config.has_openai_config():
            try:
                self.providers[LLMProvider.OPENAI] = await self._create_openai_provider()
                if not self.current_provider:
                    self.current_provider = LLMProvider.OPENAI
                logger.info("OpenAI provider initialized")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI provider: {e}")
        
        # Anthropic Claude
        if self.config.has_anthropic_config():
            try:
                self.providers[LLMProvider.ANTHROPIC] = await self._create_anthropic_provider()
                if not self.current_provider:
                    self.current_provider = LLMProvider.ANTHROPIC
                logger.info("Anthropic provider initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Anthropic provider: {e}")
        
        # Azure OpenAI
        if self.config.has_azure_config():
            try:
                self.providers[LLMProvider.AZURE_OPENAI] = await self._create_azure_provider()
                if not self.current_provider:
                    self.current_provider = LLMProvider.AZURE_OPENAI
                logger.info("Azure OpenAI provider initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Azure OpenAI provider: {e}")
        
        # 设置故障转移序列
        self.failover_sequence = list(self.providers.keys())
        
        if not self.providers:
            raise LLMServiceError("未配置任何LLM提供商")
    
    async def _create_bedrock_provider(self):
        """创建 AWS Bedrock (Claude) 提供商"""
        return BedrockClaudeLLM(self.config)

    async def _create_openai_provider(self):
        """创建OpenAI提供商"""
        return OpenAILLM(self.config)
    
    async def _create_anthropic_provider(self):
        """创建Anthropic提供商"""
        return AnthropicLLM(self.config)
    
    async def _create_azure_provider(self):
        """创建Azure OpenAI提供商"""
        return AzureOpenAILLM(self.config)
    
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
        # 确保服务已初始化
        if not self._initialized:
            await self.initialize()
        
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
                    max_tokens=max_tokens or self.config.llm.max_tokens,
                    temperature=temperature or self.config.llm.temperature,
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
    
    async def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        tool_choice: Union[str, Dict[str, Any]] = "auto",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """原生工具调用（native function calling）。

        路由到主 provider（当前为 OpenAI），使用现代 tools API 让模型自主决定
        调用哪些工具。返回 assistant 消息 dict：
        {"content": str|None, "tool_calls": [{"id","type","function":{"name","arguments"}}],
         "model": str, "usage": {...}, "metadata": {...}}

        Args:
            messages: 完整对话消息列表（含 system/user/assistant/tool 各角色）
            tools: 工具 schema 列表（可为裸 function schema 或已包裹的现代格式）
            tool_choice: "auto" / "none" / {"type":"function",...}
        """
        if not self._initialized:
            await self.initialize()

        provider = self.current_provider
        if provider is None or provider not in self.providers:
            raise LLMServiceError("没有可用的 LLM 提供商")

        llm = self.providers[provider]
        if not hasattr(llm, "chat_with_tools"):
            raise LLMServiceError(
                f"提供商 {provider.value} 不支持原生工具调用（chat_with_tools）"
            )

        start_time = time.time()
        result = await llm.chat_with_tools(
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )
        latency = time.time() - start_time

        # 成本 / 用量跟踪（复用现有逻辑）
        usage = result.get("usage", {})
        cost = self._calculate_cost(provider, result.get("model", ""), usage)
        if cost and cost > 0:
            self.cost_tracker.add_cost(
                provider=provider,
                model=result.get("model", ""),
                cost=cost,
                tokens=usage.get("total_tokens", 0),
            )
        logger.info(
            f"chat_with_tools 完成: {provider.value}, 耗时 {latency:.2f}s, "
            f"tool_calls={len(result.get('tool_calls') or [])}"
        )
        return result

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
        if not usage:
            return 0.0
        
        pricing = self.pricing_map.get(model) or self.pricing_map.get(self._normalize_model_key(model))
        if not pricing:
            return 0.0
        input_tokens = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
        output_tokens = usage.get("completion_tokens") or usage.get("output_tokens") or 0
        
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        
        return input_cost + output_cost

    @staticmethod
    def _normalize_model_key(model: str) -> str:
        """把 Bedrock 的 model / inference-profile ID 规范化成定价表键。

        例: 'us.anthropic.claude-sonnet-4-6' / 'claude-sonnet-4-6' -> 'claude-sonnet-4-6';
            'us.anthropic.claude-haiku-4-5-20251001-v1:0' -> 'claude-haiku-4-5-20251001'。
        """
        m = model or ""
        for prefix in ("us.", "eu.", "apac.", "global."):
            if m.startswith(prefix):
                m = m[len(prefix):]
                break
        if m.startswith("anthropic."):
            m = m[len("anthropic."):]
        if ":" in m:  # 去掉 ':0'
            m = m.split(":", 1)[0]
        if "-v" in m:  # 去掉结尾的 '-vN'
            head, _, tail = m.rpartition("-v")
            if tail.isdigit():
                m = head
        return m

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
    
    async def get_service_info(self) -> Dict[str, Any]:
        """获取服务信息"""
        return {
            "available_providers": [p.value for p in self.providers.keys()],
            "primary_provider": self.current_provider.value if self.current_provider else None,
            "status": "ready" if self._initialized else "initializing"
        }
    
    async def test_connection(self) -> Dict[str, Dict[str, Any]]:
        """测试连接"""
        results = {}
        
        for provider_name, llm in self.providers.items():
            try:
                start_time = time.time()
                # 简单的测试请求
                await llm.generate_response("Hello", max_tokens=5)
                latency = time.time() - start_time
                
                results[provider_name.value] = {
                    "status": "success",
                    "latency": latency
                }
            except Exception as e:
                results[provider_name.value] = {
                    "status": "error",
                    "error": str(e),
                    "latency": None
                }
        
        return results
    
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
        self._initialized = False
        
        if close_errors:
            logger.warning(f"LLM服务关闭时遇到错误: {close_errors}")
        else:
            logger.info("LLM服务已完全关闭")


class BaseLLM:
    """基础LLM类"""
    
    def __init__(self, config):
        self.config = config
    
    async def generate_response(self, **kwargs) -> Dict[str, Any]:
        """生成响应 - 需要子类实现"""
        raise NotImplementedError
    
    async def close(self):
        """关闭LLM客户端 - 子类可以重写"""
        pass


class OpenAILLM(BaseLLM):
    """OpenAI LLM实现"""
    
    def __init__(self, config):
        super().__init__(config)
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """初始化OpenAI客户端"""
        try:
            import openai
            self.client = openai.AsyncOpenAI(
                api_key=self.config.llm.openai_api_key,
                base_url=self.config.llm.openai_base_url,
                timeout=self.config.llm.timeout
            )
        except ImportError:
            raise LLMServiceError("OpenAI库未安装，请运行: uv sync --extra openai")
    
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
            "model": self.config.llm.openai_model,
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

    async def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Union[str, Dict[str, Any]] = "auto",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """原生工具调用（现代 tools API）。

        - 使用 `tools=[{"type":"function","function":{...}}]` 与 `tool_choice`，
          不使用已弃用的 `functions=` / `function_call=`。
        - 返回 assistant 消息的 `content` 与结构化的 `tool_calls`
          （每个含 id / type / function.name / function.arguments 原始 JSON 字符串）。
        """
        request_params: Dict[str, Any] = {
            "model": self.config.llm.openai_model,
            "messages": messages,
        }
        if tools:
            # 自动包裹成现代格式：允许调用方传入裸 function schema 或已包裹好的
            wrapped = []
            for t in tools:
                if isinstance(t, dict) and t.get("type") == "function" and "function" in t:
                    wrapped.append(t)
                else:
                    wrapped.append({"type": "function", "function": t})
            request_params["tools"] = wrapped
            request_params["tool_choice"] = tool_choice
        if max_tokens is not None:
            request_params["max_tokens"] = max_tokens
        if temperature is not None:
            request_params["temperature"] = temperature
        request_params.update(kwargs)

        response = await self.client.chat.completions.create(**request_params)
        msg = response.choices[0].message

        tool_calls: List[Dict[str, Any]] = []
        for tc in (msg.tool_calls or []):
            tool_calls.append({
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            })

        return {
            "content": msg.content,
            "tool_calls": tool_calls,
            "model": response.model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            "metadata": {
                "finish_reason": response.choices[0].finish_reason,
                "response_id": response.id,
            },
        }


class AnthropicLLM(BaseLLM):
    """Anthropic Claude LLM实现"""
    
    def __init__(self, config):
        super().__init__(config)
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """初始化Anthropic客户端"""
        try:
            import anthropic
            self.client = anthropic.AsyncAnthropic(
                api_key=self.config.llm.anthropic_api_key,
                timeout=self.config.llm.timeout
            )
        except ImportError:
            raise LLMServiceError("Anthropic库未安装，请运行: uv sync")
    
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
            "model": self.config.llm.anthropic_model,
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


class BedrockClaudeLLM(BaseLLM):
    """AWS Bedrock 上的 Claude LLM 实现（新增的主 provider）。

    使用 anthropic SDK 的 ``AsyncAnthropicBedrock`` 客户端，通过 boto3 的
    profile 解析 SSO 凭证注入。对外暴露与 OpenAI provider 一致的接口：

      - ``generate_response(...)`` —— 供 search 流程（query_parser / recommendation
        / output_formatter）使用；
      - ``chat_with_tools(...)`` —— 供 agent 循环使用，内部做 OpenAI<->Anthropic
        的 messages / tools / tool_choice / 响应格式适配，返回 **OpenAI 风格** 的
        assistant 消息。

    因此 ``AgentService`` / ``interfaces`` 无需任何改动即可切换到 Bedrock/Claude。
    """

    def __init__(self, config):
        super().__init__(config)
        # config 为 AppConfig，Bedrock 字段挂在 config.llm 上
        self.model_id = config.llm.bedrock_model_id
        self.region = config.llm.bedrock_region
        self.profile = config.llm.aws_profile
        self.client = None
        self._initialize_client()

    def _initialize_client(self):
        """用 boto3 profile 解析 SSO 凭证，初始化 AsyncAnthropicBedrock 客户端。

        凭证缺失（未 aws sso login）时抛出清晰错误；该异常会被
        ``LLMService._initialize_providers`` 的 try/except 接住，从而 fallback 到
        其它 provider，而不是让整个服务崩掉。
        """
        try:
            import boto3
            from anthropic import AsyncAnthropicBedrock
        except ImportError as e:
            raise LLMServiceError(
                f"缺少 Bedrock 依赖（需要 boto3 + anthropic）: {e}"
            )

        session = boto3.Session(profile_name=self.profile, region_name=self.region)
        creds = session.get_credentials()
        if creds is None:
            raise LLMServiceError(
                f"无 AWS 凭证，请先 aws sso login --profile {self.profile}"
            )
        frozen = creds.get_frozen_credentials()
        self.client = AsyncAnthropicBedrock(
            aws_access_key=frozen.access_key,
            aws_secret_key=frozen.secret_key,
            aws_session_token=frozen.token,
            aws_region=self.region,
        )

    # ------------------------------------------------------------------ #
    # 适配层（纯函数，便于离线单测）
    # ------------------------------------------------------------------ #
    @staticmethod
    def _translate_tools(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """OpenAI tools schema -> Anthropic tools schema。

        兼容裸 function schema（``{"name","description","parameters"}``）或已包裹的
        ``{"type":"function","function":{...}}``；``parameters`` -> ``input_schema``。
        """
        anthropic_tools: List[Dict[str, Any]] = []
        for t in tools or []:
            if isinstance(t, dict) and t.get("type") == "function" and "function" in t:
                fn = t["function"]
            else:
                fn = t
            anthropic_tools.append({
                "name": fn["name"],
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
            })
        return anthropic_tools

    @staticmethod
    def _translate_tool_choice(tool_choice: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """OpenAI tool_choice -> Anthropic tool_choice。不确定时当 auto。

        （``"none"`` 由调用方通过“不传 tools”处理，不会走到这里。）
        """
        if tool_choice == "auto":
            return {"type": "auto"}
        if isinstance(tool_choice, dict):
            # {"type":"function","function":{"name":...}} -> {"type":"tool","name":...}
            if tool_choice.get("type") == "function":
                name = (tool_choice.get("function") or {}).get("name")
                if name:
                    return {"type": "tool", "name": name}
            if tool_choice.get("type") in ("auto", "any", "tool"):
                return tool_choice
        return {"type": "auto"}

    @staticmethod
    def _translate_messages(messages: List[Dict[str, Any]]):
        """OpenAI 风格 messages -> (system_text, anthropic_messages)。

        - 所有 ``role=="system"`` 的 content 拼成一个 system 字符串单独返回；
        - ``role=="user"`` -> ``{"role":"user","content":content}``；
        - ``role=="assistant"``：
            * 有 tool_calls -> content 为 block 列表：
              ``([text block] if content else []) + [tool_use block ...]``；
            * 否则 -> ``{"role":"assistant","content":content}``；
        - ``role=="tool"`` -> ``tool_result`` block；**连续的 tool 结果合并进同一个**
          ``{"role":"user","content":[...]}``（Anthropic 要求 tool_result 紧跟
          tool_use 的 assistant，且在同一个 user turn 里）。
        """
        system_parts: List[str] = []
        result: List[Dict[str, Any]] = []
        pending_tool_results: List[Dict[str, Any]] = []

        def flush_tool_results():
            if pending_tool_results:
                result.append({"role": "user", "content": list(pending_tool_results)})
                pending_tool_results.clear()

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            if role == "tool":
                # 累积连续的 tool 结果，遇到非 tool 或结束时再 flush
                pending_tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": msg.get("tool_call_id"),
                    "content": content if content is not None else "",
                })
                continue

            # 非 tool 消息前，先把累积的 tool 结果 flush 成一个 user turn
            flush_tool_results()

            if role == "system":
                if content:
                    system_parts.append(content)
            elif role == "user":
                result.append({"role": "user", "content": content})
            elif role == "assistant":
                tool_calls = msg.get("tool_calls") or []
                if tool_calls:
                    blocks: List[Dict[str, Any]] = []
                    if content:
                        blocks.append({"type": "text", "text": content})
                    for tc in tool_calls:
                        fn = tc.get("function", {})
                        raw_args = fn.get("arguments") or "{}"
                        try:
                            parsed = json.loads(raw_args) if str(raw_args).strip() else {}
                        except (ValueError, TypeError):
                            parsed = {}
                        blocks.append({
                            "type": "tool_use",
                            "id": tc.get("id"),
                            "name": fn.get("name"),
                            "input": parsed,
                        })
                    result.append({"role": "assistant", "content": blocks})
                else:
                    result.append({"role": "assistant", "content": content})
            else:
                # 未知 role：尽力保留
                result.append({"role": role, "content": content})

        # 末尾 flush 掉遗留的 tool 结果
        flush_tool_results()

        system_text = "\n\n".join(system_parts) if system_parts else None
        return system_text, result

    # ------------------------------------------------------------------ #
    # 对外接口
    # ------------------------------------------------------------------ #
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
        """生成响应（供 search 流程使用）。"""
        request_params: Dict[str, Any] = {
            "model": self.model_id,
            "max_tokens": max_tokens or 1024,
            "temperature": temperature if temperature is not None else 0.3,
            "messages": [{"role": "user", "content": prompt}],
        }
        if response_format == "json":
            request_params["system"] = (
                "You must output only valid JSON. No prose, no markdown code fences."
            )
        if top_p is not None:
            request_params["top_p"] = top_p
        if stop:
            request_params["stop_sequences"] = stop

        resp = await self.client.messages.create(**request_params)

        content = "".join(
            block.text for block in resp.content
            if getattr(block, "type", None) == "text"
        )
        return {
            "content": content,
            "model": resp.model,
            "usage": {
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
                "total_tokens": resp.usage.input_tokens + resp.usage.output_tokens,
            },
            "metadata": {"stop_reason": resp.stop_reason},
            "tool_calls": [],
        }

    async def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Union[str, Dict[str, Any]] = "auto",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """原生工具调用（内部做 OpenAI<->Anthropic 适配）。

        返回 **OpenAI 风格** 的 assistant 消息 dict，AgentService 无需改动即可消费：
        ``{"content": str|None, "tool_calls": [...], "model", "usage", "metadata"}``。
        """
        system_text, translated = self._translate_messages(messages)

        request_params: Dict[str, Any] = {
            "model": self.model_id,
            "max_tokens": max_tokens or 1200,
            "temperature": temperature if temperature is not None else 0.3,
            "messages": translated,
        }
        if system_text:
            request_params["system"] = system_text

        # tool_choice == "none" -> 不传 tools（强制纯文本收尾）
        if tool_choice != "none":
            request_params["tools"] = self._translate_tools(tools or [])
            request_params["tool_choice"] = self._translate_tool_choice(tool_choice)

        resp = await self.client.messages.create(**request_params)

        content_parts: List[str] = []
        tool_calls: List[Dict[str, Any]] = []
        for block in resp.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                content_parts.append(block.text)
            elif btype == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "type": "function",
                    "function": {
                        "name": block.name,
                        # arguments 必须是可被 json.loads 的字符串（对齐 OpenAI 形状）
                        "arguments": json.dumps(block.input, ensure_ascii=False),
                    },
                })
        content = "".join(content_parts) if content_parts else None

        return {
            "content": content,
            "tool_calls": tool_calls,
            "model": resp.model,
            "usage": {
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
                "total_tokens": resp.usage.input_tokens + resp.usage.output_tokens,
            },
            "metadata": {"stop_reason": resp.stop_reason},
        }

    async def close(self):
        """防御性关闭客户端（有 close 才调）。"""
        try:
            if self.client is not None and hasattr(self.client, "close"):
                await self.client.close()
        except Exception as e:  # noqa: BLE001 —— 关闭失败不应影响主流程
            logger.debug(f"关闭 Bedrock 客户端时出错: {e}")


class AzureOpenAILLM(BaseLLM):
    """Azure OpenAI LLM实现"""
    
    def __init__(self, config):
        super().__init__(config)
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """初始化Azure OpenAI客户端"""
        try:
            import openai
            self.client = openai.AsyncAzureOpenAI(
                api_key=self.config.llm.azure_openai_api_key,
                api_version=self.config.llm.azure_openai_api_version,
                azure_endpoint=self.config.llm.azure_openai_endpoint,
                timeout=self.config.llm.timeout
            )
        except ImportError:
            raise LLMServiceError("OpenAI库未安装，请运行: uv sync --extra openai")
    
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
            model=self.config.llm.azure_openai_deployment,
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
