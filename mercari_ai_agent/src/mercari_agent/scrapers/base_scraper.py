"""
基础爬虫类模块

该模块提供爬虫的基础抽象类和通用功能。
定义了爬虫的标准接口和基本实现。

主要功能：
- 抽象爬虫接口定义
- 通用爬虫功能实现
- 错误处理和重试机制
- 会话管理
- 数据提取框架

Author: Mercari AI Agent Team
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import aiohttp
import random
import time

from ..models.product import ProductData
from ..utils.logger import get_logger
from ..config.settings import settings

logger = get_logger(__name__)


class ScrapingStrategy(Enum):
    """爬虫策略枚举"""
    REQUESTS = "requests"          # 基于requests的快速爬虫
    SELENIUM = "selenium"          # 基于Selenium的浏览器爬虫
    PLAYWRIGHT = "playwright"     # 基于Playwright的现代爬虫


@dataclass
class ScrapingConfig:
    """爬虫配置"""
    strategy: ScrapingStrategy
    max_retries: int = 3
    timeout: int = 30
    delay_range: tuple = (1, 3)
    use_proxy: bool = False
    proxy_rotation: bool = False
    user_agent_rotation: bool = True
    headers: Optional[Dict[str, str]] = None


@dataclass
class ScrapingResult:
    """爬虫结果"""
    products: List[ProductData]
    success: bool
    error_message: Optional[str] = None
    response_time: float = 0.0
    status_code: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseScraper(ABC):
    """
    基础爬虫抽象类
    
    定义了爬虫的标准接口和基本功能。
    所有具体的爬虫实现都应该继承此类。
    """
    
    def __init__(self, config: ScrapingConfig):
        """
        初始化基础爬虫
        
        Args:
            config: 爬虫配置
        """
        self.config = config
        self.session = None
        self.user_agents = self._load_user_agents()
        self.proxies = self._load_proxies() if config.use_proxy else []
        self.current_proxy_index = 0
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
        
        strategy_name = config.strategy.value if hasattr(config.strategy, 'value') else str(config.strategy)
        logger.info(f"BaseScraper initialized with strategy: {strategy_name}")
    
    @abstractmethod
    async def scrape_page(self, url: str, **kwargs) -> ScrapingResult:
        """
        爬取单个页面
        
        Args:
            url: 目标URL
            **kwargs: 额外参数
            
        Returns:
            ScrapingResult: 爬取结果
        """
        pass
    
    @abstractmethod
    async def extract_product_data(self, content: str, url: str) -> List[ProductData]:
        """
        从页面内容提取产品数据
        
        Args:
            content: 页面内容
            url: 页面URL
            
        Returns:
            List[ProductData]: 产品数据列表
        """
        pass
    
    async def scrape_multiple_pages(self, urls: List[str], **kwargs) -> List[ScrapingResult]:
        """
        批量爬取多个页面
        
        Args:
            urls: URL列表
            **kwargs: 额外参数
            
        Returns:
            List[ScrapingResult]: 爬取结果列表
        """
        results = []
        
        # 并发爬取
        semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_REQUESTS)
        
        async def scrape_with_semaphore(url: str):
            async with semaphore:
                return await self.scrape_page(url, **kwargs)
        
        tasks = [scrape_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"爬取URL {urls[i]} 失败: {result}")
                processed_results.append(ScrapingResult(
                    products=[],
                    success=False,
                    error_message=str(result)
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _make_request(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """
        发送HTTP请求
        
        Args:
            url: 请求URL
            **kwargs: 额外参数
            
        Returns:
            aiohttp.ClientResponse: 响应对象
            
        Raises:
            ScrapingError: 请求失败时抛出
        """
        if not self.session:
            await self._create_session()
        
        headers = self._get_headers()
        proxy = self._get_proxy() if self.config.use_proxy else None
        
        try:
            self.request_count += 1
            
            async with self.session.get(
                url,
                headers=headers,
                proxy=proxy,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
                **kwargs
            ) as response:
                
                # 检查响应状态
                if response.status != 200:
                    raise ScrapingError(f"HTTP {response.status}: {response.reason}")
                
                self.success_count += 1
                logger.debug(f"请求成功: {url} (状态: {response.status})")
                
                return response
                
        except Exception as e:
            self.error_count += 1
            logger.error(f"请求失败: {url} - {e}")
            raise ScrapingError(f"请求失败: {e}")
    
    async def _create_session(self):
        """创建HTTP会话"""
        connector = aiohttp.TCPConnector(
            limit=settings.MAX_CONCURRENT_REQUESTS,
            limit_per_host=settings.MAX_REQUESTS_PER_HOST,
            ttl_dns_cache=300,
            use_dns_cache=True,
            ssl=False  # 禁用SSL验证以解决连接问题
        )
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=self.config.timeout)
        )
        
        logger.debug("HTTP会话创建成功")
    
    def _get_headers(self) -> Dict[str, str]:
        """
        获取请求头
        
        Returns:
            Dict[str, str]: 请求头字典
        """
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        }
        
        # 用户代理轮换
        if self.config.user_agent_rotation:
            headers["User-Agent"] = self._get_random_user_agent()
        else:
            headers["User-Agent"] = settings.DEFAULT_USER_AGENT
        
        # 合并自定义头部
        if self.config.headers:
            headers.update(self.config.headers)
        
        return headers
    
    def _get_proxy(self) -> Optional[str]:
        """
        获取代理
        
        Returns:
            Optional[str]: 代理URL
        """
        if not self.proxies:
            return None
        
        if self.config.proxy_rotation:
            proxy = self.proxies[self.current_proxy_index]
            self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
            return proxy
        else:
            return self.proxies[0]
    
    def _get_random_user_agent(self) -> str:
        """
        获取随机用户代理
        
        Returns:
            str: 用户代理字符串
        """
        return random.choice(self.user_agents)
    
    def _load_user_agents(self) -> List[str]:
        """
        加载用户代理列表
        
        Returns:
            List[str]: 用户代理列表
        """
        return [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/91.0.864.59",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15"
        ]
    
    def _load_proxies(self) -> List[str]:
        """
        加载代理列表
        
        Returns:
            List[str]: 代理列表
        """
        # 从配置或文件加载代理
        proxies = []
        
        if hasattr(settings, 'PROXY_LIST') and settings.PROXY_LIST:
            proxies = settings.PROXY_LIST
        
        return proxies
    
    async def _delay_between_requests(self):
        """请求间延迟"""
        delay = random.uniform(*self.config.delay_range)
        await asyncio.sleep(delay)
    
    async def _retry_request(self, url: str, max_retries: int = None, **kwargs):
        """
        重试请求
        
        Args:
            url: 请求URL
            max_retries: 最大重试次数
            **kwargs: 额外参数
            
        Returns:
            aiohttp.ClientResponse: 响应对象
            
        Raises:
            ScrapingError: 所有重试都失败时抛出
        """
        max_retries = max_retries or self.config.max_retries
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    # 指数退避
                    delay = min(60, 2 ** attempt)
                    await asyncio.sleep(delay)
                    logger.info(f"重试请求 {url} (第{attempt}次)")
                
                response = await self._make_request(url, **kwargs)
                return response
                
            except Exception as e:
                last_error = e
                logger.warning(f"请求失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                
                if attempt < max_retries:
                    continue
                else:
                    break
        
        raise ScrapingError(f"重试{max_retries}次后仍然失败: {last_error}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取爬虫统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        success_rate = (self.success_count / self.request_count * 100) if self.request_count > 0 else 0
        
        strategy_name = self.config.strategy.value if hasattr(self.config.strategy, 'value') else str(self.config.strategy)
        return {
            "strategy": strategy_name,
            "total_requests": self.request_count,
            "successful_requests": self.success_count,
            "failed_requests": self.error_count,
            "success_rate": success_rate,
            "current_proxy_index": self.current_proxy_index,
            "available_proxies": len(self.proxies),
            "available_user_agents": len(self.user_agents)
        }
    
    async def health_check(self) -> bool:
        """
        健康检查
        
        Returns:
            bool: 健康状态
        """
        try:
            # 尝试发送一个简单的请求
            test_url = "https://httpbin.org/get"
            response = await self._make_request(test_url)
            return response.status == 200
        except Exception:
            return False
    
    async def close(self):
        """关闭爬虫会话"""
        if self.session:
            try:
                if not self.session.closed:
                    await self.session.close()
                    logger.debug("爬虫会话关闭成功")
                else:
                    logger.debug("爬虫会话已经关闭")
            except Exception as e:
                logger.error(f"关闭爬虫会话时出错: {e}")
            finally:
                self.session = None
                logger.info("爬虫会话已关闭")


class ScrapingError(Exception):
    """爬虫异常"""
    pass


class RequestThrottler:
    """请求节流器"""
    
    def __init__(self, max_requests_per_second: float = 1.0):
        """
        初始化请求节流器
        
        Args:
            max_requests_per_second: 每秒最大请求数
        """
        self.max_requests_per_second = max_requests_per_second
        self.min_interval = 1.0 / max_requests_per_second
        self.last_request_time = 0.0
        self.lock = asyncio.Lock()
    
    async def wait(self):
        """等待合适的请求时机"""
        async with self.lock:
            current_time = time.time()
            elapsed = current_time - self.last_request_time
            
            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                await asyncio.sleep(wait_time)
            
            self.last_request_time = time.time()


class SessionManager:
    """会话管理器"""
    
    def __init__(self, max_sessions: int = 10):
        """
        初始化会话管理器
        
        Args:
            max_sessions: 最大会话数
        """
        self.max_sessions = max_sessions
        self.sessions = []
        self.current_session_index = 0
        self.lock = asyncio.Lock()
    
    async def get_session(self) -> aiohttp.ClientSession:
        """
        获取会话
        
        Returns:
            aiohttp.ClientSession: 会话对象
        """
        async with self.lock:
            if not self.sessions:
                await self._create_sessions()
            
            session = self.sessions[self.current_session_index]
            self.current_session_index = (self.current_session_index + 1) % len(self.sessions)
            
            return session
    
    async def _create_sessions(self):
        """创建会话池"""
        created_sessions = []
        try:
            for _ in range(self.max_sessions):
                connector = aiohttp.TCPConnector(
                    limit=100,
                    limit_per_host=30,
                    ttl_dns_cache=300,
                    use_dns_cache=True,
                    ssl=False  # 禁用SSL验证以解决连接问题
                )
                
                session = aiohttp.ClientSession(
                    connector=connector,
                    timeout=aiohttp.ClientTimeout(total=30)
                )
                
                created_sessions.append(session)
            
            # 只有在所有session都创建成功后才添加到self.sessions
            self.sessions.extend(created_sessions)
            
        except Exception as e:
            # 如果创建失败，关闭已创建的session
            for session in created_sessions:
                if not session.closed:
                    await session.close()
            raise e
    
    async def close_all(self):
        """关闭所有会话"""
        close_errors = []
        
        # 并行关闭所有会话
        async def safe_close_session(session):
            try:
                if not session.closed:
                    await session.close()
            except Exception as e:
                logger.error(f"关闭会话时出错: {e}")
                close_errors.append(str(e))
        
        # 使用 asyncio.gather 并行关闭所有会话
        if self.sessions:
            await asyncio.gather(
                *[safe_close_session(session) for session in self.sessions],
                return_exceptions=True
            )
        
        self.sessions.clear()
        
        if close_errors:
            logger.warning(f"关闭会话时遇到错误: {close_errors}")
        else:
            logger.info("所有会话已关闭")