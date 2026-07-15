"""
会话管理器测试

该模块包含会话管理器的单元测试。
测试会话池管理、代理轮换、请求频率控制等功能。

Author: Mercari AI Agent Team
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import aiohttp

from mercari_agent.scrapers.session_manager import (
    SessionManager, SessionInfo, ProxyInfo, SessionStatus, RateLimiter
)
from mercari_agent.config.settings import settings


class TestRateLimiter:
    """请求频率限制器测试"""
    
    def test_rate_limiter_init(self):
        """测试频率限制器初始化"""
        limiter = RateLimiter(max_requests=10, time_window=60)
        assert limiter.max_requests == 10
        assert limiter.time_window == 60
        assert limiter.min_interval == 6.0
        assert len(limiter.requests) == 0
    
    @pytest.mark.asyncio
    async def test_rate_limiter_acquire(self):
        """测试获取请求许可"""
        limiter = RateLimiter(max_requests=2, time_window=60)
        
        # 第一次请求应该成功
        assert await limiter.acquire() is True
        
        # 第二次请求应该成功
        assert await limiter.acquire() is True
        
        # 第三次请求应该失败
        assert await limiter.acquire() is False
    
    @pytest.mark.asyncio
    async def test_rate_limiter_wait_for_slot(self):
        """测试等待时间槽"""
        limiter = RateLimiter(max_requests=1, time_window=1)
        
        # 消耗一个时间槽
        await limiter.acquire()
        
        # 应该需要等待
        wait_time = await limiter.wait_for_slot()
        assert wait_time > 0
        assert wait_time <= 1.0


class TestProxyInfo:
    """代理信息测试"""
    
    def test_proxy_info_init(self):
        """测试代理信息初始化"""
        proxy = ProxyInfo(url="http://proxy.example.com:8080")
        assert proxy.url == "http://proxy.example.com:8080"
        assert proxy.status == SessionStatus.ACTIVE
        assert proxy.success_count == 0
        assert proxy.error_count == 0
    
    def test_proxy_info_success_rate(self):
        """测试成功率计算"""
        proxy = ProxyInfo(url="http://proxy.example.com:8080")
        
        # 无请求时成功率为0
        assert proxy.success_rate == 0
        
        # 添加一些统计
        proxy.success_count = 7
        proxy.error_count = 3
        assert proxy.success_rate == 70.0
    
    def test_proxy_info_is_available(self):
        """测试代理可用性"""
        proxy = ProxyInfo(url="http://proxy.example.com:8080")
        
        # 正常状态应该可用
        assert proxy.is_available is True
        
        # 禁用状态应该不可用
        proxy.status = SessionStatus.DISABLED
        assert proxy.is_available is False
        
        # 冷却状态但时间未到应该不可用
        proxy.status = SessionStatus.COOLING_DOWN
        proxy.cooldown_until = datetime.now() + timedelta(minutes=1)
        assert proxy.is_available is False
        
        # 冷却时间已过应该可用
        proxy.cooldown_until = datetime.now() - timedelta(minutes=1)
        assert proxy.is_available is True


class TestSessionInfo:
    """会话信息测试"""
    
    def test_session_info_init(self):
        """测试会话信息初始化"""
        mock_session = MagicMock()
        session_info = SessionInfo(
            session_id="test_session",
            session=mock_session
        )
        
        assert session_info.session_id == "test_session"
        assert session_info.session == mock_session
        assert session_info.status == SessionStatus.ACTIVE
        assert session_info.request_count == 0
        assert session_info.success_count == 0
        assert session_info.error_count == 0
    
    def test_session_info_success_rate(self):
        """测试成功率计算"""
        mock_session = MagicMock()
        session_info = SessionInfo(
            session_id="test_session",
            session=mock_session
        )
        
        # 无请求时成功率为0
        assert session_info.success_rate == 0
        
        # 添加一些统计
        session_info.success_count = 8
        session_info.error_count = 2
        assert session_info.success_rate == 80.0
    
    def test_session_info_is_available(self):
        """测试会话可用性"""
        mock_session = MagicMock()
        session_info = SessionInfo(
            session_id="test_session",
            session=mock_session
        )
        
        # 正常状态应该可用
        assert session_info.is_available is True
        
        # 禁用状态应该不可用
        session_info.status = SessionStatus.DISABLED
        assert session_info.is_available is False


class TestSessionManager:
    """会话管理器测试"""
    
    def test_session_manager_init(self):
        """测试会话管理器初始化"""
        manager = SessionManager(max_sessions=3, max_requests_per_minute=60)
        
        assert manager.max_sessions == 3
        assert manager.rate_limiter.max_requests == 60
        assert len(manager.sessions) == 0
        assert len(manager.proxies) == 0
        assert manager.total_requests == 0
    
    @pytest.mark.asyncio
    async def test_session_manager_initialize(self):
        """测试会话管理器初始化"""
        manager = SessionManager(max_sessions=2)
        
        with patch.object(manager, '_load_proxies') as mock_load_proxies, \
             patch.object(manager, '_create_session_pool') as mock_create_pool, \
             patch.object(manager, '_load_cookies') as mock_load_cookies:
            
            await manager.initialize()
            
            mock_load_proxies.assert_called_once()
            mock_create_pool.assert_called_once()
            mock_load_cookies.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_session_manager_create_session_pool(self):
        """测试创建会话池"""
        manager = SessionManager(max_sessions=2)
        
        with patch('aiohttp.ClientSession') as mock_client_session:
            mock_session = AsyncMock()
            mock_client_session.return_value = mock_session
            
            await manager._create_session_pool()
            
            assert len(manager.sessions) == 2
            assert mock_client_session.call_count == 2
    
    @pytest.mark.asyncio
    async def test_session_manager_get_session(self):
        """测试获取会话"""
        manager = SessionManager(max_sessions=2)
        
        # 创建模拟会话
        mock_session1 = MagicMock()
        mock_session2 = MagicMock()
        
        session_info1 = SessionInfo(session_id="session1", session=mock_session1)
        session_info2 = SessionInfo(session_id="session2", session=mock_session2)
        
        manager.sessions = {
            "session1": session_info1,
            "session2": session_info2
        }
        
        # 获取会话
        session = await manager.get_session()
        assert session in [session_info1, session_info2]
        assert session.last_used is not None
    
    @pytest.mark.asyncio
    async def test_session_manager_get_session_prefer_proxy(self):
        """测试优先获取代理会话"""
        manager = SessionManager(max_sessions=2)
        
        # 创建带代理的会话
        proxy = ProxyInfo(url="http://proxy.example.com:8080")
        mock_session1 = MagicMock()
        mock_session2 = MagicMock()
        
        session_info1 = SessionInfo(session_id="session1", session=mock_session1, proxy=proxy)
        session_info2 = SessionInfo(session_id="session2", session=mock_session2)
        
        manager.sessions = {
            "session1": session_info1,
            "session2": session_info2
        }
        
        # 优先获取代理会话
        session = await manager.get_session(prefer_proxy=True)
        assert session == session_info1
    
    @pytest.mark.asyncio
    async def test_session_manager_make_request(self):
        """测试发送请求"""
        manager = SessionManager(max_sessions=1)
        
        # 创建模拟会话
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="test content")
        
        session_info = SessionInfo(session_id="session1", session=mock_session)
        manager.sessions = {"session1": session_info}
        
        # 模拟请求
        with patch.object(manager, 'get_session', return_value=session_info), \
             patch.object(manager.rate_limiter, 'acquire', return_value=True):
            
            # 配置session.request为返回async context manager
            async_context = AsyncMock()
            async_context.__aenter__.return_value = mock_response
            async_context.__aexit__.return_value = None
            mock_session.request.return_value = async_context
            
            response = await manager.make_request("https://example.com")
            
            assert response == mock_response
            assert manager.total_requests == 1
            assert manager.successful_requests == 1
            assert session_info.request_count == 1
            assert session_info.success_count == 1
    
    @pytest.mark.asyncio
    async def test_session_manager_make_request_rate_limited(self):
        """测试请求频率限制"""
        manager = SessionManager(max_sessions=1)
        
        with patch.object(manager.rate_limiter, 'acquire', return_value=False), \
             patch.object(manager.rate_limiter, 'wait_for_slot', return_value=1.0), \
             patch('asyncio.sleep') as mock_sleep:
            
            # 第二次acquire返回True
            manager.rate_limiter.acquire = AsyncMock(side_effect=[False, True])
            
            # 创建模拟会话和响应
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            
            session_info = SessionInfo(session_id="session1", session=mock_session)
            manager.sessions = {"session1": session_info}
            
            with patch.object(manager, 'get_session', return_value=session_info):
                # 配置session.request为返回async context manager
                async_context = AsyncMock()
                async_context.__aenter__.return_value = mock_response
                async_context.__aexit__.return_value = None
                mock_session.request.return_value = async_context
                
                response = await manager.make_request("https://example.com")
                
                # 验证等待了正确的时间
                mock_sleep.assert_called_once_with(1.0)
                assert response == mock_response
    
    @pytest.mark.asyncio
    async def test_session_manager_make_request_error(self):
        """测试请求错误处理"""
        manager = SessionManager(max_sessions=1)
        
        # 创建模拟会话
        mock_session = AsyncMock()
        session_info = SessionInfo(session_id="session1", session=mock_session)
        manager.sessions = {"session1": session_info}
        
        with patch.object(manager, 'get_session', return_value=session_info), \
             patch.object(manager.rate_limiter, 'acquire', return_value=True):
            
            # 模拟请求异常
            mock_session.request.side_effect = aiohttp.ClientError("Connection failed")
            
            with pytest.raises(Exception) as exc_info:
                await manager.make_request("https://example.com")
            
            assert "请求失败" in str(exc_info.value)
            assert manager.failed_requests == 1
            assert session_info.error_count == 1
    
    @pytest.mark.asyncio
    async def test_session_manager_health_check(self):
        """测试健康检查"""
        manager = SessionManager(max_sessions=2)
        
        # 创建模拟会话
        session_info1 = SessionInfo(session_id="session1", session=AsyncMock())
        session_info2 = SessionInfo(session_id="session2", session=AsyncMock())
        session_info2.status = SessionStatus.BLOCKED
        
        manager.sessions = {
            "session1": session_info1,
            "session2": session_info2
        }
        
        # 添加模拟代理
        proxy = ProxyInfo(url="http://proxy.example.com:8080")
        manager.proxies = [proxy]
        
        # 设置一些统计
        manager.total_requests = 100
        manager.successful_requests = 90
        
        health = await manager.health_check()
        
        assert health["total_sessions"] == 2
        assert health["active_sessions"] == 1
        assert health["blocked_sessions"] == 1
        assert health["available_proxies"] == 1
        assert health["total_requests"] == 100
        assert health["successful_requests"] == 90
        assert health["success_rate"] == 90.0
    
    @pytest.mark.asyncio
    async def test_session_manager_rotate_sessions(self):
        """测试会话轮换"""
        manager = SessionManager(max_sessions=2)
        
        # 创建一个表现不佳的会话
        mock_session1 = AsyncMock()
        mock_session2 = AsyncMock()
        
        session_info1 = SessionInfo(session_id="session1", session=mock_session1)
        session_info1.status = SessionStatus.BLOCKED
        
        session_info2 = SessionInfo(session_id="session2", session=mock_session2)
        session_info2.error_count = 15  # 超过阈值
        
        manager.sessions = {
            "session1": session_info1,
            "session2": session_info2
        }
        
        with patch.object(manager, '_create_session_pool') as mock_create_pool:
            await manager.rotate_sessions()
            
            # 验证坏会话被关闭
            mock_session1.close.assert_called_once()
            mock_session2.close.assert_called_once()
            
            # 验证会话被移除
            assert len(manager.sessions) == 0
            
            # 验证创建了新的会话池
            mock_create_pool.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_session_manager_close_all(self):
        """测试关闭所有会话"""
        manager = SessionManager(max_sessions=2)
        
        # 创建模拟会话
        mock_session1 = AsyncMock()
        mock_session2 = AsyncMock()
        
        session_info1 = SessionInfo(session_id="session1", session=mock_session1)
        session_info2 = SessionInfo(session_id="session2", session=mock_session2)
        
        manager.sessions = {
            "session1": session_info1,
            "session2": session_info2
        }
        
        with patch.object(manager, '_save_cookies') as mock_save_cookies:
            await manager.close_all()
            
            # 验证所有会话被关闭
            mock_session1.close.assert_called_once()
            mock_session2.close.assert_called_once()
            
            # 验证会话被清空
            assert len(manager.sessions) == 0
            
            # 验证保存了Cookie
            mock_save_cookies.assert_called_once()
    
    def test_session_manager_get_stats(self):
        """测试获取统计信息"""
        manager = SessionManager(max_sessions=2)
        
        # 创建模拟会话
        session_info1 = SessionInfo(session_id="session1", session=MagicMock())
        session_info2 = SessionInfo(session_id="session2", session=MagicMock())
        session_info2.status = SessionStatus.BLOCKED
        
        manager.sessions = {
            "session1": session_info1,
            "session2": session_info2
        }
        
        # 添加模拟代理
        proxy = ProxyInfo(url="http://proxy.example.com:8080")
        proxy.response_time = 0.5
        manager.proxies = [proxy]
        
        # 设置统计
        manager.total_requests = 50
        manager.successful_requests = 45
        
        stats = manager.get_stats()
        
        assert stats["sessions"]["total"] == 2
        assert stats["sessions"]["active"] == 1
        assert stats["sessions"]["blocked"] == 1
        assert stats["proxies"]["total"] == 1
        assert stats["proxies"]["available"] == 1
        assert stats["proxies"]["average_response_time"] == 0.5
        assert stats["requests"]["total"] == 50
        assert stats["requests"]["successful"] == 45
        assert stats["requests"]["success_rate"] == 90.0


@pytest.fixture
def mock_settings():
    """模拟设置"""
    with patch.object(settings, 'DATA_DIR', '/tmp/test_data'), \
         patch.object(settings, 'PROXY_LIST', []):
        yield settings