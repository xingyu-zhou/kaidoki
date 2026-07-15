"""
增强会话管理器 - 修复版本

主要修复：
1. 添加安全的初始化逻辑
2. 增强错误处理和恢复机制
3. 改进会话池管理
4. 添加健康检查和监控
"""

import asyncio
import logging
import random
import time
import json
import hashlib
import uuid
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from http.cookies import SimpleCookie
import aiohttp
from aiohttp import ClientSession, ClientTimeout, TCPConnector, CookieJar
from aiohttp.client_exceptions import ClientError
from collections import defaultdict, deque
import ssl
import weakref

from .tls_fingerprint_manager import TLSFingerprintManager, BrowserType
from .browser_fingerprint_manager import BrowserFingerprintManager, BrowserFingerprint
from .behavior_simulation_engine import BehaviorSimulationEngine, BehaviorType
from .session_manager import SessionManager
from ..utils.logger import get_logger
from ..config.settings import settings

logger = get_logger(__name__)


class SessionState(Enum):
    """会话状态枚举"""
    INITIALIZING = "initializing"
    ACTIVE = "active"
    IDLE = "idle"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


class SessionType(Enum):
    """会话类型枚举"""
    BROWSING = "browsing"
    SCRAPING = "scraping"
    SEARCH = "search"
    AUTHENTICATION = "authentication"
    BACKGROUND = "background"
    TESTING = "testing"


@dataclass
class SessionConfig:
    """会话配置 - P0级修复：保守并发配置"""
    session_type: SessionType = SessionType.BROWSING
    max_concurrent_sessions: int = 2  # P0级修复：极度保守配置
    session_timeout: int = 1800  # 30分钟
    idle_timeout: int = 300  # 5分钟
    max_requests_per_session: int = 1000
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # 连接配置 - P0级修复：保守连接参数
    connection_timeout: float = 30.0
    read_timeout: float = 60.0
    total_timeout: float = 120.0
    max_connections: int = 5  # P0级修复：降低连接数
    max_connections_per_host: int = 2  # P0级修复：降低单主机连接数
    
    # 初始化配置
    max_init_retries: int = 5
    init_retry_delay: float = 2.0
    init_timeout: float = 30.0
    
    # 健康检查配置
    health_check_interval: int = 60
    health_check_timeout: float = 10.0
    
    # 请求间隔配置 - P0级修复：防止CAPTCHA
    request_delay_min: float = 8.0  # P0级修复：最小请求间隔8秒
    request_delay_max: float = 15.0  # P0级修复：最大请求间隔15秒


class SessionInitializationError(Exception):
    """会话初始化错误"""
    pass


class SessionPoolEmptyError(Exception):
    """会话池为空错误"""
    pass


class EnhancedSessionManager(SessionManager):
    """增强会话管理器主类 - 修复版本"""
    
    def __init__(self, config: Optional[SessionConfig] = None, **kwargs):
        # 初始化锁和状态
        self._initialization_lock = asyncio.Lock()
        self._initialization_status = "pending"
        self._initialization_error = None
        self._retry_count = 0
        self._fully_initialized = False
        
        # 会话池管理
        self._sessions: Dict[str, Any] = {}
        self._session_metrics: Dict[str, Any] = {}
        
        # 配置
        self.config = config or SessionConfig()
        
        # 健康检查
        self._health_check_task: Optional[asyncio.Task] = None
        
        # P0级修复：请求间隔控制
        self._last_request_time: float = 0.0
        self._request_lock = asyncio.Lock()
        
        # 调用父类初始化
        try:
            super().__init__()
        except Exception as e:
            logger.error(f"父类初始化失败: {e}")
            # 继续初始化，不让父类错误阻止修复
        
        logger.info("✅ 增强会话管理器初始化完成")
    
    async def initialize(self):
        """安全的异步初始化"""
        async with self._initialization_lock:
            if self._initialization_status == "completed":
                logger.info("会话管理器已完成初始化")
                return
            
            if self._initialization_status == "initializing":
                logger.info("会话管理器正在初始化中...")
                # 等待初始化完成
                while self._initialization_status == "initializing":
                    await asyncio.sleep(0.1)
                return
            
            try:
                logger.info("🔄 开始初始化会话管理器...")
                self._initialization_status = "initializing"
                
                # 初始化会话池
                await self._safe_initialize_session_pool()
                
                # 启动健康检查
                await self._start_health_check()
                
                self._initialization_status = "completed"
                self._fully_initialized = True
                logger.info("✅ 会话管理器初始化成功")
                
            except Exception as e:
                self._initialization_status = "failed"
                self._initialization_error = e
                logger.error(f"❌ 会话管理器初始化失败: {e}")
                raise SessionInitializationError(f"会话管理器初始化失败: {e}")
    
    async def _safe_initialize_session_pool(self):
        """安全初始化会话池"""
        retry_count = 0
        last_error = None
        
        while retry_count < self.config.max_init_retries:
            try:
                logger.info(f"尝试初始化会话池 (第{retry_count + 1}次)")
                
                # 清理旧的会话
                await self._cleanup_old_sessions()
                
                # 预创建最小数量的会话
                min_sessions = max(1, self.config.max_concurrent_sessions // 4)
                successful_sessions = 0
                
                for i in range(min_sessions):
                    try:
                        session_id = f"init_session_{i}_{int(time.time())}"
                        session = await self._create_single_session(session_id)
                        
                        if session:
                            self._sessions[session_id] = session
                            successful_sessions += 1
                            logger.info(f"成功预创建会话 {successful_sessions}/{min_sessions}")
                        
                    except Exception as e:
                        logger.warning(f"预创建会话失败: {e}")
                        # 继续尝试创建其他会话
                        continue
                
                # 验证会话池状态
                if successful_sessions == 0:
                    raise SessionPoolEmptyError("会话池为空，无法提供服务")
                
                logger.info(f"✅ 会话池初始化成功，已创建 {successful_sessions} 个会话")
                return
                
            except Exception as e:
                retry_count += 1
                last_error = e
                logger.error(f"会话池初始化失败 (第{retry_count}次): {e}")
                
                if retry_count < self.config.max_init_retries:
                    delay = self.config.init_retry_delay * (2 ** (retry_count - 1))  # 指数退避
                    logger.info(f"等待 {delay:.1f}s 后重试...")
                    await asyncio.sleep(delay)
                else:
                    break
        
        raise SessionInitializationError(f"会话池初始化最终失败: {last_error}")
    
    async def _create_single_session(self, session_id: str) -> Optional[Any]:
        """创建单个会话"""
        connector = None
        session = None
        
        try:
            # 创建TCP连接器 - P0级修复：修复SSL配置
            connector = TCPConnector(
                limit=5,  # 保守配置：降低并发连接数
                limit_per_host=2,  # 保守配置：降低单主机连接数
                ttl_dns_cache=300,
                use_dns_cache=True,
                keepalive_timeout=30,
                enable_cleanup_closed=True,
                ssl=False  # P0级修复：禁用SSL验证以解决连接问题
            )
            
            # 创建超时配置
            timeout = ClientTimeout(
                total=self.config.total_timeout,
                connect=self.config.connection_timeout,
                sock_read=self.config.read_timeout
            )
            
            # 创建会话
            session = ClientSession(
                connector=connector,
                timeout=timeout,
                cookie_jar=CookieJar(unsafe=True),
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'ja,ja-JP;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
            )
            
            # 简单的健康检查
            try:
                async with session.get('https://httpbin.org/get', timeout=ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        logger.debug(f"会话 {session_id} 健康检查通过")
                    else:
                        logger.warning(f"会话 {session_id} 健康检查失败: {response.status}")
            except Exception as e:
                logger.warning(f"会话 {session_id} 健康检查异常: {e}")
                # 不因为健康检查失败而丢弃会话
            
            return session
            
        except Exception as e:
            logger.error(f"创建会话失败: {e}")
            
            # 清理失败的资源
            if session is not None:
                try:
                    await session.close()
                except Exception:
                    pass
            
            if connector is not None:
                try:
                    await connector.close()
                except Exception:
                    pass
            
            return None
    
    async def get(self, session_id: str = None) -> Optional[Any]:
        """获取会话（简化接口）"""
        return await self.get_session_safe(session_id)
    
    async def get_session_safe(self, session_id: str = None) -> Optional[Any]:
        """安全获取会话"""
        # 确保初始化完成
        if not self._fully_initialized:
            await self.initialize()
        
        try:
            # 如果没有指定会话ID，随机选择一个
            if session_id is None:
                available_sessions = [sid for sid, session in self._sessions.items() if not session.closed]
                if available_sessions:
                    session_id = random.choice(available_sessions)
                else:
                    # 没有可用会话，尝试创建新会话
                    session_id = f"auto_session_{int(time.time())}"
            
            # 获取会话
            session = self._sessions.get(session_id)
            
            if session is None or session.closed:
                logger.warning(f"会话 {session_id} 不存在或已关闭，尝试创建新会话")
                # 尝试创建新会话
                session = await self._create_single_session(session_id)
                if session:
                    self._sessions[session_id] = session
                else:
                    # 创建失败，尝试从现有会话中获取
                    return await self._get_fallback_session()
            
            return session
            
        except Exception as e:
            logger.error(f"获取会话失败: {e}")
            # 尝试恢复机制
            try:
                return await self._emergency_session_recovery()
            except Exception as recovery_error:
                logger.error(f"会话恢复失败: {recovery_error}")
                raise SessionPoolEmptyError(f"会话管理器完全失效: {e}")
    
    async def _get_fallback_session(self) -> Optional[Any]:
        """获取备用会话"""
        # 尝试从现有会话中选择一个可用的
        for session_id, session in self._sessions.items():
            if not session.closed:
                logger.info(f"使用备用会话: {session_id}")
                return session
        
        # 没有可用会话，创建紧急会话
        emergency_session_id = f"emergency_{int(time.time())}"
        session = await self._create_single_session(emergency_session_id)
        if session:
            self._sessions[emergency_session_id] = session
            logger.info(f"创建紧急会话: {emergency_session_id}")
            return session
        
        return None
    
    async def _emergency_session_recovery(self) -> Any:
        """紧急会话恢复"""
        logger.warning("🚨 执行紧急会话恢复...")
        
        # 清理所有会话
        await self._cleanup_all_sessions()
        
        # 重置初始化状态
        self._fully_initialized = False
        self._initialization_status = "pending"
        
        # 重新初始化
        await self.initialize()
        
        # 获取一个会话
        session = await self._get_fallback_session()
        if session:
            logger.info("✅ 紧急会话恢复成功")
            return session
        else:
            raise SessionPoolEmptyError("紧急会话恢复失败")
    
    async def _cleanup_old_sessions(self):
        """清理旧会话"""
        logger.info("🧹 清理旧会话...")
        
        closed_sessions = []
        for session_id, session in self._sessions.items():
            if session.closed:
                closed_sessions.append(session_id)
        
        for session_id in closed_sessions:
            del self._sessions[session_id]
            logger.debug(f"清理已关闭会话: {session_id}")
        
        if closed_sessions:
            logger.info(f"清理了 {len(closed_sessions)} 个旧会话")
    
    async def _cleanup_all_sessions(self):
        """清理所有会话"""
        logger.info("🧹 清理所有会话...")
        
        cleanup_tasks = []
        for session_id, session in self._sessions.items():
            cleanup_tasks.append(self._cleanup_single_session(session_id, session))
        
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        self._sessions.clear()
        logger.info("所有会话已清理")
    
    async def _cleanup_single_session(self, session_id: str, session: Any):
        """清理单个会话"""
        try:
            if not session.closed:
                # 确保连接器也被关闭
                if hasattr(session, 'connector') and session.connector:
                    await session.connector.close()
                await session.close()
            logger.debug(f"关闭会话: {session_id}")
        except Exception as e:
            logger.warning(f"关闭会话失败: {session_id} - {e}")
    
    async def _start_health_check(self):
        """启动健康检查"""
        if self._health_check_task is None:
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            logger.info("启动健康检查任务")
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._perform_health_check()
            except asyncio.CancelledError:
                logger.info("健康检查任务被取消")
                break
            except Exception as e:
                logger.error(f"健康检查失败: {e}")
    
    async def _perform_health_check(self):
        """执行健康检查"""
        logger.debug("执行健康检查...")
        
        # 清理关闭的会话
        await self._cleanup_old_sessions()
        
        # 检查会话池状态
        active_sessions = len([s for s in self._sessions.values() if not s.closed])
        
        if active_sessions == 0:
            logger.warning("会话池为空，尝试创建新会话")
            try:
                session_id = f"health_check_{int(time.time())}"
                session = await self._create_single_session(session_id)
                if session:
                    self._sessions[session_id] = session
                    logger.info("健康检查创建新会话成功")
            except Exception as e:
                logger.error(f"健康检查创建会话失败: {e}")
        
        logger.debug(f"健康检查完成，活跃会话数: {active_sessions}")
    
    async def make_request(self, url: str, method: str = "GET", **kwargs) -> 'aiohttp.ClientResponse':
        """发送HTTP请求 - P0级修复：包含请求间隔和重试逻辑"""
        # P0级修复：请求间隔控制，防止CAPTCHA
        async with self._request_lock:
            current_time = time.time()
            time_since_last_request = current_time - self._last_request_time
            
            if time_since_last_request < self.config.request_delay_min:
                # 计算需要等待的时间，使用随机间隔
                delay_needed = random.uniform(
                    self.config.request_delay_min - time_since_last_request,
                    self.config.request_delay_max - time_since_last_request
                )
                if delay_needed > 0:
                    logger.debug(f"P0级防护：等待 {delay_needed:.2f}s 防止CAPTCHA触发")
                    await asyncio.sleep(delay_needed)
            
            self._last_request_time = time.time()
        
        # 提取自定义参数，防止传递给session.request()
        max_retries = kwargs.pop('max_retries', self.config.max_retries)
        retry_delay = kwargs.pop('retry_delay', self.config.retry_delay)
        prefer_proxy = kwargs.pop('prefer_proxy', False)  # 移除prefer_proxy参数
        
        # 定义aiohttp.ClientSession.request()支持的标准参数
        allowed_kwargs = {
            'params', 'data', 'json', 'cookies', 'headers', 'skip_auto_headers',
            'auth', 'allow_redirects', 'max_redirects', 'encoding', 'compress',
            'chunked', 'expect100', 'raise_for_status', 'read_until_eof', 'proxy',
            'proxy_auth', 'timeout', 'ssl', 'verify_ssl', 'fingerprint', 'ssl_context',
            'proxy_headers', 'trace_request_ctx', 'read_bufsize'
        }
        
        # 过滤掉不兼容的参数
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in allowed_kwargs}
        
        # 记录被过滤的参数
        filtered_params = set(kwargs.keys()) - set(filtered_kwargs.keys())
        if filtered_params:
            logger.debug(f"过滤不兼容参数: {filtered_params}")
        
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                session = await self.get_session_safe()
                if session is None:
                    raise SessionPoolEmptyError("无法获取可用会话")
                
                # 使用过滤后的参数发送请求
                # 修复: 不使用async with，避免自动关闭连接
                response = await session.request(method, url, **filtered_kwargs)
                
                # 如果是重试成功，记录日志
                if attempt > 0:
                    logger.info(f"请求重试成功 (第{attempt + 1}次尝试): {method} {url}")
                return response
                    
            except Exception as e:
                last_exception = e
                
                # 如果是最后一次尝试，或者是不可重试的错误，直接抛出
                if attempt == max_retries or self._is_non_retryable_error(e):
                    logger.error(f"请求最终失败: {method} {url} - {e}")
                    raise
                
                # 记录重试日志
                logger.warning(f"请求失败，将重试 (第{attempt + 1}次尝试): {method} {url} - {e}")
                
                # 等待后重试
                if retry_delay > 0:
                    await asyncio.sleep(retry_delay * (2 ** attempt))  # 指数退避
        
        # 这里不应该到达，但为了安全起见
        raise last_exception or Exception("请求失败")
    
    def _is_non_retryable_error(self, error: Exception) -> bool:
        """判断是否为不可重试的错误"""
        # 4xx错误通常不需要重试
        if hasattr(error, 'status') and 400 <= error.status < 500:
            return True
        
        # 特定的错误类型不需要重试
        non_retryable_errors = [
            'ClientPayloadError',
            'InvalidURL',
            'ClientConnectorCertificateError'
        ]
        
        return any(err in str(type(error)) for err in non_retryable_errors)
    
    async def close_all_sessions(self):
        """关闭所有会话"""
        logger.info("关闭所有会话...")
        
        # 取消健康检查任务
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        # 关闭所有会话
        await self._cleanup_all_sessions()
        
        # 重置状态
        self._fully_initialized = False
        self._initialization_status = "pending"
        
        logger.info("所有会话已关闭")
    
    def get_session_statistics(self) -> Dict[str, Any]:
        """获取会话统计信息"""
        active_sessions = len([s for s in self._sessions.values() if not s.closed])
        total_sessions = len(self._sessions)
        
        return {
            "initialization_status": self._initialization_status,
            "fully_initialized": self._fully_initialized,
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "closed_sessions": total_sessions - active_sessions,
            "session_list": list(self._sessions.keys()),
            "config": {
                "max_concurrent_sessions": self.config.max_concurrent_sessions,
                "session_timeout": self.config.session_timeout,
                "max_init_retries": self.config.max_init_retries
            }
        }
    
    @property
    def is_healthy(self) -> bool:
        """检查会话管理器是否健康"""
        return (
            self._fully_initialized and
            self._initialization_status == "completed" and
            len([s for s in self._sessions.values() if not s.closed]) > 0
        )
    
    # 异步上下文管理器支持
    async def __aenter__(self):
        """异步上下文管理器入口"""
        try:
            await self.initialize()
            return self
        except Exception as e:
            logger.error(f"进入异步上下文时出错: {e}")
            try:
                await self.close_all_sessions()
            except Exception:
                pass
            raise
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        try:
            await self.close_all_sessions()
        except Exception as e:
            logger.error(f"退出异步上下文时出错: {e}")
        
        if exc_type is not None:
            logger.error(f"异步上下文中发生异常: {exc_type.__name__}: {exc_val}")
        
        # 不抑制异常
        return False


# 便捷函数
def create_session_manager(config: Optional[SessionConfig] = None) -> EnhancedSessionManager:
    """创建会话管理器"""
    return EnhancedSessionManager(config)


def create_browsing_session_manager() -> EnhancedSessionManager:
    """创建浏览会话管理器"""
    config = SessionConfig(
        session_type=SessionType.BROWSING,
        max_concurrent_sessions=5,
        session_timeout=1800
    )
    return EnhancedSessionManager(config)


def create_scraping_session_manager() -> EnhancedSessionManager:
    """创建爬虫会话管理器"""
    config = SessionConfig(
        session_type=SessionType.SCRAPING,
        max_concurrent_sessions=10,
        session_timeout=3600
    )
    return EnhancedSessionManager(config)


# 测试函数
async def test_session_manager():
    """测试会话管理器"""
    logger.info("🧪 测试会话管理器...")
    
    try:
        async with create_session_manager() as manager:
            # 测试初始化
            logger.info("测试初始化...")
            assert manager.is_healthy, "会话管理器不健康"
            
            # 测试获取会话
            logger.info("测试获取会话...")
            session = await manager.get_session_safe()
            assert session is not None, "无法获取会话"
            
            # 测试统计信息
            logger.info("测试统计信息...")
            stats = manager.get_session_statistics()
            assert stats["active_sessions"] > 0, "没有活跃会话"
            
            logger.info("✅ 会话管理器测试通过")
            
    except Exception as e:
        logger.error(f"❌ 会话管理器测试失败: {e}")
        raise


if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_session_manager())
