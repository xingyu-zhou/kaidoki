"""
LLM服务单元测试

该文件包含LLM服务各个组件的单元测试。

测试覆盖：
- LLMService核心功能
- 多提供商支持
- 成本跟踪
- 缓存机制
- 限流机制
- 错误处理和重试

Author: Mercari AI Agent Team
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, Any, List

# 导入被测试的模块
import sys
sys.path.insert(0, 'mercari_ai_agent/src')

from mercari_agent.services.llm_service import (
    LLMService, 
    CostTracker, 
    RateLimiter,
    LLMResponse,
    LLMProvider,
    LLMError,
    TokenUsage
)
from mercari_agent.config.settings import LLMConfig, CostTrackingConfig

# 导入测试工具
from tests.utils import (
    MockLLMResponse,
    create_test_config,
    async_test
)


class TestLLMResponse:
    """LLM响应测试"""
    
    def test_llm_response_creation(self):
        """测试LLM响应创建"""
        response = LLMResponse(
            content="这是一个测试响应",
            model="gpt-4",
            provider="openai",
            cost=0.01,
            tokens=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        )
        
        assert response.content == "这是一个测试响应"
        assert response.model == "gpt-4"
        assert response.provider == "openai"
        assert response.cost == 0.01
        assert response.tokens.total_tokens == 30
        assert isinstance(response.timestamp, datetime)
    
    def test_llm_response_to_dict(self):
        """测试LLM响应转字典"""
        response = LLMResponse(
            content="测试内容",
            model="gpt-4",
            provider="openai",
            cost=0.01,
            tokens=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        )
        
        response_dict = response.to_dict()
        
        assert response_dict["content"] == "测试内容"
        assert response_dict["model"] == "gpt-4"
        assert response_dict["provider"] == "openai"
        assert response_dict["cost"] == 0.01
        assert response_dict["tokens"]["total_tokens"] == 30
        assert "timestamp" in response_dict


class TestCostTracker:
    """成本跟踪器测试"""
    
    def setup_method(self):
        """测试设置"""
        config = CostTrackingConfig()
        self.cost_tracker = CostTracker(config)
    
    def test_cost_tracking_initialization(self):
        """测试成本跟踪器初始化"""
        assert self.cost_tracker.total_cost == 0.0
        assert self.cost_tracker.request_count == 0
        assert len(self.cost_tracker.cost_history) == 0
    
    def test_add_cost(self):
        """测试添加成本"""
        self.cost_tracker.add_cost(0.05, "gpt-4", "openai")
        
        assert self.cost_tracker.total_cost == 0.05
        assert self.cost_tracker.request_count == 1
        assert len(self.cost_tracker.cost_history) == 1
        
        # 添加更多成本
        self.cost_tracker.add_cost(0.03, "gpt-3.5-turbo", "openai")
        
        assert self.cost_tracker.total_cost == 0.08
        assert self.cost_tracker.request_count == 2
    
    def test_get_cost_summary(self):
        """测试获取成本摘要"""
        self.cost_tracker.add_cost(0.05, "gpt-4", "openai")
        self.cost_tracker.add_cost(0.03, "gpt-3.5-turbo", "openai")
        
        summary = self.cost_tracker.get_cost_summary()
        
        assert summary["total_cost"] == 0.08
        assert summary["request_count"] == 2
        assert summary["average_cost"] == 0.04
        assert "by_model" in summary
        assert "by_provider" in summary
    
    def test_cost_by_model(self):
        """测试按模型统计成本"""
        self.cost_tracker.add_cost(0.05, "gpt-4", "openai")
        self.cost_tracker.add_cost(0.03, "gpt-4", "openai")
        self.cost_tracker.add_cost(0.02, "gpt-3.5-turbo", "openai")
        
        by_model = self.cost_tracker.get_cost_by_model()
        
        assert by_model["gpt-4"] == 0.08
        assert by_model["gpt-3.5-turbo"] == 0.02
    
    def test_cost_by_provider(self):
        """测试按提供商统计成本"""
        self.cost_tracker.add_cost(0.05, "gpt-4", "openai")
        self.cost_tracker.add_cost(0.03, "claude-3", "anthropic")
        
        by_provider = self.cost_tracker.get_cost_by_provider()
        
        assert by_provider["openai"] == 0.05
        assert by_provider["anthropic"] == 0.03
    
    def test_cost_limit_check(self):
        """测试成本限制检查"""
        # 设置较低的成本限制
        config = CostTrackingConfig(daily_cost_limit=0.1)
        tracker = CostTracker(config)
        
        # 添加成本但不超过限制
        tracker.add_cost(0.05, "gpt-4", "openai")
        assert not tracker.is_cost_limit_exceeded()
        
        # 添加成本超过限制
        tracker.add_cost(0.06, "gpt-4", "openai")
        assert tracker.is_cost_limit_exceeded()
    
    def test_cost_reset(self):
        """测试成本重置"""
        self.cost_tracker.add_cost(0.05, "gpt-4", "openai")
        
        self.cost_tracker.reset_daily_cost()
        
        assert self.cost_tracker.total_cost == 0.0
        assert self.cost_tracker.request_count == 0
        assert len(self.cost_tracker.cost_history) == 0


class TestRateLimiter:
    """限流器测试"""
    
    def setup_method(self):
        """测试设置"""
        self.rate_limiter = RateLimiter(max_requests=5, window_seconds=60)
    
    @async_test
    async def test_rate_limit_acquisition(self):
        """测试限流获取"""
        # 连续获取5个请求
        for i in range(5):
            can_proceed = await self.rate_limiter.acquire()
            assert can_proceed is True
        
        # 第6个请求应该被限制
        can_proceed = await self.rate_limiter.acquire()
        assert can_proceed is False
    
    @async_test
    async def test_rate_limit_reset(self):
        """测试限流重置"""
        # 用完所有请求
        for i in range(5):
            await self.rate_limiter.acquire()
        
        # 重置限流器
        self.rate_limiter.reset()
        
        # 现在应该可以再次获取
        can_proceed = await self.rate_limiter.acquire()
        assert can_proceed is True
    
    def test_rate_limit_status(self):
        """测试限流状态"""
        status = self.rate_limiter.get_status()
        
        assert status["max_requests"] == 5
        assert status["window_seconds"] == 60
        assert status["current_requests"] == 0
        assert status["remaining_requests"] == 5


class TestLLMService:
    """LLM服务测试"""
    
    def setup_method(self):
        """测试设置"""
        self.config = LLMConfig(
            openai_api_key="test_key",
            default_provider="openai",
            enable_caching=True,
            enable_cost_tracking=True
        )
        self.llm_service = LLMService(self.config)
    
    def test_llm_service_initialization(self):
        """测试LLM服务初始化"""
        assert self.llm_service.config == self.config
        assert self.llm_service.default_provider == "openai"
        assert self.llm_service.cost_tracker is not None
        assert self.llm_service.rate_limiter is not None
    
    def test_provider_availability(self):
        """测试提供商可用性"""
        # OpenAI应该可用（有API密钥）
        assert self.llm_service.is_provider_available("openai") is True
        
        # Anthropic应该不可用（没有API密钥）
        assert self.llm_service.is_provider_available("anthropic") is False
    
    def test_get_available_providers(self):
        """测试获取可用提供商"""
        providers = self.llm_service.get_available_providers()
        
        assert "openai" in providers
        assert "anthropic" not in providers  # 没有API密钥
    
    @async_test
    async def test_openai_provider_call(self):
        """测试OpenAI提供商调用"""
        with patch('openai.AsyncOpenAI') as mock_openai:
            # 设置Mock响应
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content="测试响应"))]
            mock_response.usage = Mock(
                prompt_tokens=10,
                completion_tokens=20,
                total_tokens=30
            )
            mock_response.model = "gpt-4"
            
            mock_client.chat.completions.create.return_value = mock_response
            
            # 调用服务
            response = await self.llm_service._call_openai(
                "测试提示词",
                model="gpt-4",
                temperature=0.7
            )
            
            assert response.content == "测试响应"
            assert response.model == "gpt-4"
            assert response.provider == "openai"
            assert response.tokens.total_tokens == 30
    
    @async_test
    async def test_anthropic_provider_call(self):
        """测试Anthropic提供商调用"""
        with patch('anthropic.AsyncAnthropic') as mock_anthropic:
            # 设置Mock响应
            mock_client = AsyncMock()
            mock_anthropic.return_value = mock_client
            
            mock_response = Mock()
            mock_response.content = [Mock(text="测试响应")]
            mock_response.usage = Mock(
                input_tokens=10,
                output_tokens=20
            )
            mock_response.model = "claude-3-sonnet"
            
            mock_client.messages.create.return_value = mock_response
            
            # 调用服务
            response = await self.llm_service._call_anthropic(
                "测试提示词",
                model="claude-3-sonnet",
                temperature=0.7
            )
            
            assert response.content == "测试响应"
            assert response.model == "claude-3-sonnet"
            assert response.provider == "anthropic"
            assert response.tokens.total_tokens == 30
    
    @async_test
    async def test_generate_response(self):
        """测试生成响应"""
        with patch.object(self.llm_service, '_call_openai') as mock_call:
            # 设置Mock响应
            mock_response = LLMResponse(
                content="测试响应",
                model="gpt-4",
                provider="openai",
                cost=0.01,
                tokens=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
            )
            mock_call.return_value = mock_response
            
            # 调用生成响应
            response = await self.llm_service.generate_response(
                "测试提示词",
                model="gpt-4",
                temperature=0.7
            )
            
            assert response.content == "测试响应"
            assert response.model == "gpt-4"
            assert response.provider == "openai"
    
    @async_test
    async def test_provider_fallback(self):
        """测试提供商回退"""
        # 设置配置支持回退
        self.config.enable_fallback = True
        self.config.fallback_order = ["openai", "anthropic"]
        self.config.anthropic_api_key = "test_key"  # 添加Anthropic密钥
        
        with patch.object(self.llm_service, '_call_openai') as mock_openai, \
             patch.object(self.llm_service, '_call_anthropic') as mock_anthropic:
            
            # 设置OpenAI调用失败
            mock_openai.side_effect = Exception("OpenAI调用失败")
            
            # 设置Anthropic调用成功
            mock_anthropic.return_value = LLMResponse(
                content="Anthropic响应",
                model="claude-3-sonnet",
                provider="anthropic",
                cost=0.01,
                tokens=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
            )
            
            # 调用服务
            response = await self.llm_service.generate_response("测试提示词")
            
            assert response.content == "Anthropic响应"
            assert response.provider == "anthropic"
    
    @async_test
    async def test_caching_mechanism(self):
        """测试缓存机制"""
        with patch.object(self.llm_service, '_call_openai') as mock_call:
            # 设置Mock响应
            mock_response = LLMResponse(
                content="缓存测试响应",
                model="gpt-4",
                provider="openai",
                cost=0.01,
                tokens=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
            )
            mock_call.return_value = mock_response
            
            # 第一次调用
            response1 = await self.llm_service.generate_response("测试提示词")
            
            # 第二次调用相同提示词
            response2 = await self.llm_service.generate_response("测试提示词")
            
            # 验证只调用了一次实际的LLM
            assert mock_call.call_count == 1
            assert response1.content == response2.content
    
    @async_test
    async def test_cost_tracking_integration(self):
        """测试成本跟踪集成"""
        with patch.object(self.llm_service, '_call_openai') as mock_call:
            # 设置Mock响应
            mock_response = LLMResponse(
                content="测试响应",
                model="gpt-4",
                provider="openai",
                cost=0.05,
                tokens=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
            )
            mock_call.return_value = mock_response
            
            # 调用服务
            await self.llm_service.generate_response("测试提示词")
            
            # 验证成本被跟踪
            assert self.llm_service.cost_tracker.total_cost == 0.05
            assert self.llm_service.cost_tracker.request_count == 1
    
    @async_test
    async def test_rate_limiting_integration(self):
        """测试限流集成"""
        # 设置严格的限流
        self.llm_service.rate_limiter = RateLimiter(max_requests=1, window_seconds=60)
        
        with patch.object(self.llm_service, '_call_openai') as mock_call:
            # 设置Mock响应
            mock_response = LLMResponse(
                content="测试响应",
                model="gpt-4",
                provider="openai",
                cost=0.01,
                tokens=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
            )
            mock_call.return_value = mock_response
            
            # 第一次调用应该成功
            response1 = await self.llm_service.generate_response("测试提示词1")
            assert response1.content == "测试响应"
            
            # 第二次调用应该被限制
            with pytest.raises(LLMError, match="请求过于频繁"):
                await self.llm_service.generate_response("测试提示词2")
    
    @async_test
    async def test_error_handling(self):
        """测试错误处理"""
        with patch.object(self.llm_service, '_call_openai') as mock_call:
            # 设置Mock抛出异常
            mock_call.side_effect = Exception("网络错误")
            
            # 调用服务应该抛出LLMError
            with pytest.raises(LLMError, match="网络错误"):
                await self.llm_service.generate_response("测试提示词")
    
    @async_test
    async def test_retry_mechanism(self):
        """测试重试机制"""
        with patch.object(self.llm_service, '_call_openai') as mock_call:
            # 设置前两次调用失败，第三次成功
            mock_call.side_effect = [
                Exception("临时错误"),
                Exception("临时错误"),
                LLMResponse(
                    content="重试成功",
                    model="gpt-4",
                    provider="openai",
                    cost=0.01,
                    tokens=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
                )
            ]
            
            # 调用服务
            response = await self.llm_service.generate_response("测试提示词")
            
            assert response.content == "重试成功"
            assert mock_call.call_count == 3
    
    def test_get_cost_summary(self):
        """测试获取成本摘要"""
        # 添加一些成本数据
        self.llm_service.cost_tracker.add_cost(0.05, "gpt-4", "openai")
        self.llm_service.cost_tracker.add_cost(0.03, "gpt-3.5-turbo", "openai")
        
        summary = self.llm_service.get_cost_summary()
        
        assert summary["total_cost"] == 0.08
        assert summary["request_count"] == 2
        assert summary["average_cost"] == 0.04
    
    def test_get_rate_limit_status(self):
        """测试获取限流状态"""
        status = self.llm_service.get_rate_limit_status()
        
        assert "max_requests" in status
        assert "current_requests" in status
        assert "remaining_requests" in status
    
    @async_test
    async def test_stream_response(self):
        """测试流式响应"""
        with patch.object(self.llm_service, '_stream_openai') as mock_stream:
            # 设置Mock流式响应
            async def mock_stream_generator():
                for chunk in ["测试", "流式", "响应"]:
                    yield chunk
            
            mock_stream.return_value = mock_stream_generator()
            
            # 调用流式响应
            chunks = []
            async for chunk in self.llm_service.stream_response("测试提示词"):
                chunks.append(chunk)
            
            assert chunks == ["测试", "流式", "响应"]


class TestLLMIntegration:
    """LLM集成测试"""
    
    def setup_method(self):
        """测试设置"""
        self.config = LLMConfig(
            openai_api_key="test_key",
            anthropic_api_key="test_key",
            default_provider="openai",
            enable_fallback=True,
            fallback_order=["openai", "anthropic"]
        )
        self.llm_service = LLMService(self.config)
    
    @async_test
    async def test_multi_provider_workflow(self):
        """测试多提供商工作流"""
        with patch.object(self.llm_service, '_call_openai') as mock_openai, \
             patch.object(self.llm_service, '_call_anthropic') as mock_anthropic:
            
            # 设置OpenAI响应
            mock_openai.return_value = LLMResponse(
                content="OpenAI响应",
                model="gpt-4",
                provider="openai",
                cost=0.01,
                tokens=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
            )
            
            # 设置Anthropic响应
            mock_anthropic.return_value = LLMResponse(
                content="Anthropic响应",
                model="claude-3-sonnet",
                provider="anthropic",
                cost=0.02,
                tokens=TokenUsage(prompt_tokens=15, completion_tokens=25, total_tokens=40)
            )
            
            # 使用OpenAI
            response1 = await self.llm_service.generate_response(
                "测试提示词",
                provider="openai"
            )
            
            # 使用Anthropic
            response2 = await self.llm_service.generate_response(
                "测试提示词",
                provider="anthropic"
            )
            
            assert response1.provider == "openai"
            assert response2.provider == "anthropic"
            assert self.llm_service.cost_tracker.total_cost == 0.03


if __name__ == "__main__":
    pytest.main([__file__, "-v"])