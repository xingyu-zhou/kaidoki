"""
Mercari专用爬虫模块 (增强版)

该模块实现了专门针对Mercari平台的高级爬虫功能。
集成了会话管理、数据解析、反爬虫处理、CAPTCHA工作流等组件。

主要功能：
- 高级商品搜索和详情爬虫
- 动态JavaScript内容加载处理
- 多种搜索参数和过滤条件支持
- 完整的商品列表和详情页面数据提取
- 智能会话管理和请求分发
- 反爬虫检测和绕过
- 集成CAPTCHA工作流处理
- 数据质量验证和清洗

技术特点：
- 多级爬虫策略（requests -> Selenium -> Playwright）
- 智能请求频率控制
- 会话池管理和轮换
- 代理支持和IP管理
- 完整的CAPTCHA处理流程
- 数据解析和验证
- 错误恢复和重试机制

Author: Mercari AI Agent Team
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import re
import json
from urllib.parse import urljoin, urlparse, urlencode
import random
import time
import aiohttp

from .base_scraper import BaseScraper, ScrapingStrategy, ScrapingConfig, ScrapingResult
from .anti_bot_handler import AntiBotHandler, BotDetectionResult
from .session_manager import SessionManager
from .data_parser import MercariDataParser, ParsingContext, PageType
from .scraper_utils import (
    HTMLSelectorTool, JapaneseTextTool, PriceNumberTool,
    URLTool, DataValidationTool, ImageTool, TimeTool,
    generate_request_id, retry_on_failure
)
from ..models.product import ProductData
from ..utils.logger import get_logger
from ..config.settings import settings

logger = get_logger(__name__)

# 导入CAPTCHA相关组件
from ..captcha.workflow import CaptchaWorkflow, WorkflowConfig
from ..captcha.captcha_detector import CaptchaDetector
from ..captcha.captcha_solver import CaptchaSolver
from ..captcha.ui_manager import CaptchaUIManager
from ..captcha.task_queue import TaskQueue, ScrapingTask, TaskStatus, TaskPriority
from ..captcha.captcha_types import CaptchaType
from ..captcha.unified_captcha_detector import UnifiedCaptchaDetector, get_unified_detector

# 导入反Bot检测增强组件
try:
    from .tls_fingerprint_manager import TLSFingerprintManager, TLSConfig, BrowserType
    from .browser_fingerprint_manager import BrowserFingerprintManager, FingerprintConfig
    from .enhanced_session_manager import EnhancedSessionManager
    from .behavior_simulation_engine import BehaviorSimulationEngine
    ENHANCED_COMPONENTS_AVAILABLE = True
    logger.info("Enhanced components successfully imported")
except ImportError as e:
    logger.warning(f"Enhanced components not available: {e}")
    ENHANCED_COMPONENTS_AVAILABLE = False
    # 创建回退类型定义
    class BrowserType:
        CHROME = "chrome"


class SearchSortOrder(Enum):
    """搜索排序枚举"""
    RELEVANCE = "relevance"
    PRICE_LOW = "price_low"
    PRICE_HIGH = "price_high"
    NEWEST = "newest"
    OLDEST = "oldest"
    POPULARITY = "popularity"


class PriceRange(Enum):
    """价格范围枚举"""
    UNDER_1000 = (0, 1000)
    RANGE_1000_3000 = (1000, 3000)
    RANGE_3000_5000 = (3000, 5000)
    RANGE_5000_10000 = (5000, 10000)
    OVER_10000 = (10000, None)


@dataclass
class SearchFilters:
    """搜索过滤条件"""
    keywords: str
    category_id: Optional[int] = None
    brand_id: Optional[int] = None
    price_min: Optional[int] = None
    price_max: Optional[int] = None
    condition: Optional[str] = None
    size: Optional[str] = None
    color: Optional[str] = None
    shipping_payer: Optional[str] = None  # 送料负担
    sort_order: SearchSortOrder = SearchSortOrder.RELEVANCE
    page: int = 1
    limit: int = 60
    
    def to_params(self) -> Dict[str, Any]:
        """转换为URL参数"""
        # 安全处理sort_order，支持字符串和枚举
        if isinstance(self.sort_order, str):
            sort_value = self.sort_order
        else:
            sort_value = self.sort_order.value if hasattr(self.sort_order, 'value') else str(self.sort_order)
        
        params = {
            'keyword': self.keywords,
            'page': self.page,
            'limit': self.limit,
            'sort': sort_value
        }
        
        if self.category_id:
            params['category_id'] = self.category_id
        if self.brand_id:
            params['brand_id'] = self.brand_id
        if self.price_min is not None:
            params['price_min'] = self.price_min
        if self.price_max is not None:
            params['price_max'] = self.price_max
        if self.condition:
            params['item_condition_id'] = self.condition
        if self.size:
            params['size_id'] = self.size
        if self.color:
            params['color_id'] = self.color
        if self.shipping_payer:
            params['shipping_payer_id'] = self.shipping_payer
        
        return params


@dataclass
class MercariScrapingResult(ScrapingResult):
    """Mercari爬虫结果"""
    page_number: int = 1
    has_next_page: bool = False
    total_results: Optional[int] = None
    search_query: Optional[str] = None
    filters_applied: Optional[Dict[str, Any]] = None
    parsing_errors: List[str] = field(default_factory=list)
    session_info: Optional[Dict[str, Any]] = None
    
    def __iter__(self):
        """使结果对象可迭代，迭代产品列表"""
        return iter(self.products)
    
    def __len__(self):
        """返回产品数量"""
        return len(self.products)
    
    def __getitem__(self, index):
        """支持索引访问"""
        return self.products[index]


class MercariScraper(BaseScraper):
    """
    Mercari专用爬虫类 (增强版)
    
    专门针对Mercari平台设计的高级爬虫实现。
    集成了会话管理、数据解析、反爬虫处理等功能。
    """
    
    def __init__(self, strategy: ScrapingStrategy = ScrapingStrategy.REQUESTS,
                 anti_bot_handler: Optional[AntiBotHandler] = None):
        """
        初始化Mercari爬虫
        
        Args:
            strategy: 爬虫策略
            anti_bot_handler: 反爬虫处理器（可选）
        """
        config = ScrapingConfig(
            strategy=strategy,
            max_retries=3,
            timeout=30,
            delay_range=(2, 5),
            use_proxy=getattr(settings, 'USE_PROXY', False),
            proxy_rotation=getattr(settings, 'PROXY_ROTATION', False),
            user_agent_rotation=True
        )
        
        super().__init__(config)
        
        # 初始化反Bot检测增强组件（如果可用）
        if ENHANCED_COMPONENTS_AVAILABLE:
            try:
                self.tls_fingerprint_manager = TLSFingerprintManager(TLSConfig(
                    enable_fingerprint_rotation=True,
                    enable_ja3_spoofing=True,
                    enable_ja4_spoofing=True,
                    enable_http2=True
                ))
                self.browser_fingerprint_manager = BrowserFingerprintManager(FingerprintConfig(
                    enable_user_agent_rotation=True,
                    enable_webgl_spoofing=True,
                    enable_canvas_spoofing=True,
                    enable_header_randomization=True,
                    remove_automation_traces=True
                ))
                self.behavior_simulation_engine = BehaviorSimulationEngine()
                
                # 初始化增强会话管理器
                self.session_manager = EnhancedSessionManager(
                    max_sessions=5,
                    max_requests_per_minute=getattr(settings, 'MAX_REQUESTS_PER_MINUTE', 30)
                )
                logger.info("Enhanced anti-bot components initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize enhanced components: {e}")
                # 回退到基础会话管理器
                self.session_manager = SessionManager(
                    max_sessions=5,
                    max_requests_per_minute=getattr(settings, 'MAX_REQUESTS_PER_MINUTE', 30)
                )
                logger.info("Fallback to basic session manager")
        else:
            # 使用基础会话管理器
            self.session_manager = SessionManager(
                max_sessions=5,
                max_requests_per_minute=getattr(settings, 'MAX_REQUESTS_PER_MINUTE', 30)
            )
            logger.info("Using basic session manager")
        
        # 初始化反爬虫处理器
        self.anti_bot_handler = anti_bot_handler or AntiBotHandler()
        self.data_parser = MercariDataParser()
        
        # 初始化CAPTCHA工作流组件
        self.task_queue = TaskQueue()
        self.captcha_detector = CaptchaDetector()
        self.unified_detector = get_unified_detector()  # 使用统一检测器
        self.captcha_ui_manager = CaptchaUIManager()
        self.captcha_solver = CaptchaSolver(self.captcha_ui_manager)
        
        # 初始化CAPTCHA工作流
        workflow_config = WorkflowConfig(
            max_retries=3,
            timeout=300.0,
            enable_auto_retry=True,
            enable_user_notifications=True,
            enable_detailed_logging=True
        )
        self.captcha_workflow = CaptchaWorkflow(
            task_queue=self.task_queue,
            captcha_detector=self.captcha_detector,
            captcha_solver=self.captcha_solver,
            config=workflow_config
        )
        
        # 初始化工具
        self.html_tool = HTMLSelectorTool()
        self.japanese_tool = JapaneseTextTool()
        self.price_tool = PriceNumberTool()
        self.url_tool = URLTool()
        self.validation_tool = DataValidationTool()
        self.image_tool = ImageTool()
        self.time_tool = TimeTool()
        
        # Mercari特定配置
        self.base_url = "https://jp.mercari.com"
        self.search_url = "https://jp.mercari.com/search"
        self.api_base_url = "https://api.mercari.jp"
        
        # 支持的搜索参数
        self.supported_categories = self._load_category_mapping()
        self.supported_conditions = self._load_condition_mapping()
        
        # 统计信息
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.blocked_requests = 0
        self.products_scraped = 0
        self.captcha_encountered = 0
        self.captcha_solved = 0
        
        # 智能重试配置
        self.max_total_retries = 3
        self.retry_delays = [2, 4, 8]  # 指数退避
    
    def _get_enhanced_request_params(self) -> Dict[str, Any]:
        """获取增强的请求参数"""
        params = {}
        
        # 基础请求头
        if hasattr(self, 'browser_fingerprint_manager'):
            try:
                fingerprint = self.browser_fingerprint_manager.generate_fingerprint()
                params['headers'] = fingerprint.get('headers', {})
            except Exception as e:
                logger.warning(f"获取浏览器指纹失败: {e}")
        
        # 如果没有增强组件，使用基础头
        if 'headers' not in params:
            params['headers'] = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1'
            }
        
        return params
    
    async def _post_captcha_retry_strategy(self, session_info, url: str, last_response) -> Optional[str]:
        """CAPTCHA解决后的智能重试策略"""
        # 检查 session_info 是否为 None
        if session_info is None:
            logger.error("Session info is None in _post_captcha_retry_strategy")
            return None
            
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # 逐步增加延迟
                delay = 2 ** attempt
                logger.info(f"CAPTCHA解决后重试策略，尝试 {attempt + 1}/{max_retries}，延迟 {delay}s")
                await asyncio.sleep(delay)
                
                # 尝试不同的请求策略
                if attempt == 0:
                    # 第一次：使用原始会话，刷新请求头
                    fresh_headers = self._get_enhanced_request_params()['headers']
                    response = await session_info.session.get(
                        url,
                        headers=fresh_headers,
                        timeout=aiohttp.ClientTimeout(total=self.config.timeout)
                    )
                elif attempt == 1:
                    # 第二次：模拟浏览器行为
                    if hasattr(self, 'behavior_simulation_engine'):
                        try:
                            delay_info = self.behavior_simulation_engine.simulate_human_delay()
                            await asyncio.sleep(delay_info['delay'])
                        except Exception as e:
                            logger.warning(f"行为模拟失败: {e}")
                    
                    headers = self._get_enhanced_request_params()['headers']
                    headers['Cache-Control'] = 'no-cache'
                    response = await session_info.session.get(
                        url,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=self.config.timeout)
                    )
                else:
                    # 第三次：使用不同的用户代理
                    headers = self._get_enhanced_request_params()['headers']
                    headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    response = await session_info.session.get(
                        url,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=self.config.timeout)
                    )
                
                content = await response.text()
                
                # 检查是否仍被阻止
                detection = self.anti_bot_handler.detect_bot_protection(content, response)
                
                if not detection.is_detected:
                    logger.info(f"CAPTCHA解决后重试成功，尝试次数: {attempt + 1}")
                    return content
                elif detection.confidence < 0.7:
                    logger.info(f"CAPTCHA解决后重试可能成功，置信度较低: {detection.confidence}")
                    return content
                else:
                    logger.warning(f"CAPTCHA解决后重试失败，尝试次数: {attempt + 1}，置信度: {detection.confidence}")
                    
            except Exception as e:
                logger.error(f"CAPTCHA解决后重试异常，尝试次数: {attempt + 1}，错误: {e}")
                if attempt == max_retries - 1:
                    break
                continue
        
        logger.error("CAPTCHA解决后多次重试仍失败")
        return None
        self.enable_fallback_mode = True
        
        strategy_name = strategy.value if hasattr(strategy, 'value') else str(strategy)
        logger.info(f"Enhanced MercariScraper initialized with strategy: {strategy_name}")
        logger.info("CAPTCHA工作流已集成到爬虫核心流程中")
        logger.info(f"智能重试机制已启用，最大重试次数: {self.max_total_retries}")
    
    async def initialize(self):
        """初始化爬虫"""
        await self.session_manager.initialize()
        logger.info("MercariScraper initialized successfully")
    
    async def scrape_page(self, url: str, **kwargs) -> MercariScrapingResult:
        """
        爬取单个页面 (增强版 - 移除外部重试逻辑，统一使用内部重试协调器)
        
        Args:
            url: 目标URL
            **kwargs: 额外参数
            
        Returns:
            MercariScrapingResult: 爬取结果
        """
        start_time = time.time()
        request_id = generate_request_id()
        
        # 🔧 关键修改：移除外部重试逻辑，直接执行单次尝试
        # 重试逻辑现在完全由内部的CAPTCHA工作流和重试协调器管理
        try:
            result = await self._scrape_page_attempt(url, request_id, start_time, **kwargs)
            return result
        except Exception as e:
            logger.error(f"Scrape page attempt failed: {e}")
            return MercariScrapingResult(
                products=[],
                success=False,
                error_message=f"Scrape attempt failed: {str(e)}",
                response_time=time.time() - start_time,
                metadata={"request_id": request_id}
            )
    
    async def _scrape_page_attempt(self, url: str, request_id: str, start_time: float, **kwargs) -> MercariScrapingResult:
        """
        单次页面爬取尝试
        
        Args:
            url: 目标URL
            request_id: 请求ID
            start_time: 开始时间
            **kwargs: 额外参数
            
        Returns:
            MercariScrapingResult: 爬取结果
        """
        try:
            self.total_requests += 1
            
            # 创建解析上下文
            context = ParsingContext(
                page_type=PageType.UNKNOWN,
                base_url=self.base_url,
                current_url=url,
                user_agent=kwargs.get('user_agent'),
                timestamp=datetime.now()
            )
            
            # 发送请求
            response = await self.session_manager.make_request(
                url=url,
                method="GET",
                timeout=self.config.timeout,
                max_retries=self.config.max_retries,
                prefer_proxy=kwargs.get('prefer_proxy', False)
            )
            
            # 读取响应内容
            content = await response.text()
            
            # 🔧 修复：使用统一检测器进行检测
            unified_result = await self.unified_detector.detect_unified(content, response, url)
            
            # 记录统一检测结果
            self.unified_detector.log_detection_result(unified_result, request_id)
            
            if unified_result.is_detected:
                logger.warning(f"Bot protection detected: {unified_result.detection_type}")
                self.blocked_requests += 1
                
                # 检查是否为CAPTCHA类型 - 使用统一结果
                if unified_result.is_captcha:
                    logger.info(f"CAPTCHA检测到，类型: {unified_result.captcha_type.value if unified_result.captcha_type else 'unknown'}，启动CAPTCHA工作流处理")
                    self.captcha_encountered += 1
                    
                    # 创建爬虫任务
                    scraping_task = ScrapingTask(
                        task_id=request_id,
                        url=url,
                        task_type="page_scraping",
                        status=TaskStatus.CAPTCHA_REQUIRED,
                        priority=TaskPriority.HIGH,
                        params=kwargs,
                        context=context.__dict__ if hasattr(context, '__dict__') else {}
                    )
                    
                    # 启动CAPTCHA工作流
                    try:
                        session_info = await self.session_manager.get_session()
                        
                        # 检查会话是否有效
                        if session_info is None:
                            logger.error("Failed to get valid session for CAPTCHA processing")
                            return MercariScrapingResult(
                                products=[],
                                success=False,
                                error_message="无法获取有效会话处理CAPTCHA",
                                response_time=time.time() - start_time
                            )
                        
                        captcha_success = await self.captcha_workflow.process_captcha_workflow(
                            task=scraping_task,
                            response_content=content,
                            response=response,
                            session=session_info.session
                        )
                        
                        if captcha_success:
                            logger.info("CAPTCHA成功解决，继续爬取数据")
                            self.captcha_solved += 1
                            
                            # 🔧 修复：确保使用CAPTCHA解决后的会话状态
                            # 等待服务器端状态更新
                            await asyncio.sleep(2)
                            
                            # 使用相同的会话信息重新请求，确保会话状态连续性
                            try:
                                # 再次检查 session_info 是否有效
                                if session_info is None:
                                    logger.error("Session info is None during CAPTCHA retry")
                                    return MercariScrapingResult(
                                        products=[],
                                        success=False,
                                        error_message="CAPTCHA解决后会话无效",
                                        response_time=time.time() - start_time
                                    )
                                
                                # 获取增强的请求参数
                                enhanced_params = self._get_enhanced_request_params()
                                
                                # 使用原始会话直接请求，避免会话管理器的重新分配
                                retry_response = await session_info.session.get(
                                    url=url,
                                    timeout=aiohttp.ClientTimeout(total=self.config.timeout),
                                    **enhanced_params
                                )
                                content = await retry_response.text()
                                
                                # 🔧 修复：使用统一检测器进行重检测
                                retry_detection = await self.unified_detector.detect_unified(
                                    content, retry_response, url
                                )
                                
                                # 记录重检测结果
                                self.unified_detector.log_detection_result(retry_detection, f"{request_id}_retry")
                                
                                # 仅在高置信度时认为仍被阻止
                                if retry_detection.is_detected and retry_detection.confidence > 0.8:
                                    logger.warning(f"CAPTCHA解决后仍检测到高置信度反爬虫保护 (置信度: {retry_detection.confidence})")
                                    
                                    # 🔧 修复：实施额外的绕过策略
                                    content = await self._post_captcha_retry_strategy(
                                        session_info, url, retry_response
                                    )
                                    
                                    # 最终验证
                                    if content is None:
                                        logger.error("CAPTCHA解决后多次重试仍失败")
                                        return MercariScrapingResult(
                                            products=[],
                                            success=False,
                                            error_message="CAPTCHA解决后多次重试仍失败",
                                            response_time=time.time() - start_time
                                        )
                                else:
                                    logger.info("CAPTCHA解决后成功获取数据")
                                    
                            except Exception as e:
                                logger.error(f"CAPTCHA解决后重新请求失败: {e}")
                                return MercariScrapingResult(
                                    products=[],
                                    success=False,
                                    error_message=f"CAPTCHA解决后重新请求失败: {str(e)}",
                                    response_time=time.time() - start_time
                                )
                        else:
                            logger.error("CAPTCHA处理失败")
                            return MercariScrapingResult(
                                products=[],
                                success=False,
                                error_message="CAPTCHA处理失败",
                                response_time=time.time() - start_time
                            )
                    except Exception as e:
                        logger.error(f"CAPTCHA工作流处理异常: {e}")
                        return MercariScrapingResult(
                            products=[],
                            success=False,
                            error_message=f"CAPTCHA工作流处理异常: {str(e)}",
                            response_time=time.time() - start_time
                        )
                else:
                    # 非CAPTCHA类型的反爬虫，使用原有处理方式
                    try:
                        session_info = await self.session_manager.get_session()
                        
                        # 检查会话是否有效
                        if session_info is None:
                            logger.error("Failed to get valid session for anti-bot handling")
                            return MercariScrapingResult(
                                products=[],
                                success=False,
                                error_message="无法获取有效会话处理反爬虫保护",
                                response_time=time.time() - start_time
                            )
                        
                        # 转换为旧格式用于兼容性
                        bot_detection_result = unified_result.to_bot_detection_result()
                        content = await self.anti_bot_handler.handle_block(
                            session_info.session, url, bot_detection_result
                        )
                    except Exception as e:
                        logger.error(f"Failed to handle bot protection: {e}")
                        return MercariScrapingResult(
                            products=[],
                            success=False,
                            error_message=f"Bot protection handling failed: {str(e)}",
                            response_time=time.time() - start_time
                        )
            
            # 解析页面数据
            parsing_result = self.data_parser.parse_page(content, context)
            
            # 验证和清洗数据
            validated_products = []
            for product in parsing_result.products:
                is_valid, errors = self.validation_tool.validate_product_data(product.to_dict())
                if is_valid:
                    cleaned_product = self.data_parser.clean_product_data(product)
                    validated_products.append(cleaned_product)
                else:
                    parsing_result.errors.extend(errors)
            
            # 更新统计
            self.successful_requests += 1
            self.products_scraped += len(validated_products)
            
            # 创建结果
            result = MercariScrapingResult(
                products=validated_products,
                success=True,
                response_time=time.time() - start_time,
                status_code=response.status,
                page_number=parsing_result.current_page,
                has_next_page=parsing_result.has_next_page,
                total_results=parsing_result.total_count,
                search_query=kwargs.get('search_query'),
                filters_applied=kwargs.get('filters'),
                parsing_errors=parsing_result.errors,
                metadata={
                    "request_id": request_id,
                    "parsing_metadata": parsing_result.metadata,
                    "detection_result": {
                        "unified_result": unified_result.__dict__,
                        "detection_method": unified_result.detection_method,
                        "confidence": unified_result.confidence
                    }
                }
            )
            
            logger.info(f"Successfully scraped {len(validated_products)} products from {url}")
            return result
            
        except Exception as e:
            self.failed_requests += 1
            logger.error(f"Failed to scrape page {url}: {e}")
            
            return MercariScrapingResult(
                products=[],
                success=False,
                error_message=str(e),
                response_time=time.time() - start_time,
                metadata={"request_id": request_id}
            )
    
    async def search_products(self, filters: SearchFilters, **kwargs) -> List[ProductData]:
        """
        搜索商品
        
        Args:
            filters: 搜索过滤条件
            **kwargs: 额外参数
            
        Returns:
            List[ProductData]: 商品数据列表
        """
        all_products = []
        current_page = filters.page
        max_pages = kwargs.get('max_pages', 10)
        
        try:
            while current_page <= max_pages:
                # 构建搜索URL
                search_url = self._build_search_url(filters)
                
                # 爬取页面
                result = await self.scrape_page(
                    url=search_url,
                    search_query=filters.keywords,
                    filters=filters.to_params(),
                    **kwargs
                )
                
                if not result.success:
                    logger.warning(f"Failed to scrape page {current_page}: {result.error_message}")
                    break
                
                # 添加产品
                all_products.extend(result.products)
                
                # 检查是否有下一页
                if not result.has_next_page:
                    break
                
                # 更新页码
                current_page += 1
                filters.page = current_page
                
                # 请求间延迟
                await self._delay_between_requests()
            
            logger.info(f"Search completed: {len(all_products)} products found")
            return all_products
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return all_products
    
    async def scrape_product_detail(self, product_url: str, **kwargs) -> Optional[ProductData]:
        """
        爬取商品详情
        
        Args:
            product_url: 商品URL
            **kwargs: 额外参数
            
        Returns:
            Optional[ProductData]: 详细商品数据
        """
        try:
            # 验证URL
            if not self.url_tool.is_mercari_url(product_url):
                logger.warning(f"Invalid Mercari URL: {product_url}")
                return None
            
            # 爬取详情页
            result = await self.scrape_page(product_url, **kwargs)
            
            if result.success and result.products:
                # 返回第一个产品（详情页只有一个产品）
                product = result.products[0]
                
                # 额外的详情页特定处理
                product = await self._enrich_product_detail(product)
                
                return product
            else:
                logger.warning(f"Failed to scrape product detail: {result.error_message}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to scrape product detail {product_url}: {e}")
            return None
    
    async def scrape_category(self, category_id: int, **kwargs) -> List[ProductData]:
        """
        爬取分类商品
        
        Args:
            category_id: 分类ID
            **kwargs: 额外参数
            
        Returns:
            List[ProductData]: 商品数据列表
        """
        filters = SearchFilters(
            keywords="",
            category_id=category_id,
            **kwargs
        )
        
        return await self.search_products(filters, **kwargs)
    
    async def scrape_seller_products(self, seller_id: str, **kwargs) -> List[ProductData]:
        """
        爬取卖家商品
        
        Args:
            seller_id: 卖家ID
            **kwargs: 额外参数
            
        Returns:
            List[ProductData]: 商品数据列表
        """
        seller_url = f"{self.base_url}/u/{seller_id}"
        
        try:
            result = await self.scrape_page(seller_url, **kwargs)
            
            if result.success:
                return result.products
            else:
                logger.warning(f"Failed to scrape seller products: {result.error_message}")
                return []
                
        except Exception as e:
            logger.error(f"Failed to scrape seller {seller_id} products: {e}")
            return []
    
    async def batch_scrape_products(self, product_urls: List[str], **kwargs) -> List[ProductData]:
        """
        批量爬取商品
        
        Args:
            product_urls: 商品URL列表
            **kwargs: 额外参数
            
        Returns:
            List[ProductData]: 商品数据列表
        """
        products = []
        batch_size = kwargs.get('batch_size', 5)
        
        try:
            # 分批处理
            for i in range(0, len(product_urls), batch_size):
                batch_urls = product_urls[i:i + batch_size]
                
                # 并发爬取
                tasks = [
                    self.scrape_product_detail(url, **kwargs)
                    for url in batch_urls
                ]
                
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 处理结果
                for result in batch_results:
                    if isinstance(result, ProductData):
                        products.append(result)
                    elif isinstance(result, Exception):
                        logger.warning(f"Batch scraping error: {result}")
                
                # 批次间延迟
                if i + batch_size < len(product_urls):
                    await asyncio.sleep(random.uniform(1, 3))
            
            logger.info(f"Batch scraping completed: {len(products)} products")
            return products
            
        except Exception as e:
            logger.error(f"Batch scraping failed: {e}")
            return products
    
    def build_search_url(self, filters: SearchFilters) -> str:
        """
        构建搜索URL的公共接口
        
        Args:
            filters: 搜索过滤条件
            
        Returns:
            str: 搜索URL
        """
        return self._build_search_url(filters)
    
    def get_scraper_info(self) -> Dict[str, Any]:
        """
        获取爬虫状态信息的公共接口
        
        Returns:
            Dict[str, Any]: 爬虫状态信息
        """
        return {
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'blocked_requests': self.blocked_requests,
            'products_scraped': self.products_scraped,
            'captcha_encountered': self.captcha_encountered,
            'captcha_solved': self.captcha_solved,
            'base_url': self.base_url,
            'search_url': self.search_url,
            'strategy': self.config.strategy.value if hasattr(self.config.strategy, 'value') else str(self.config.strategy)
        }
    
    def _build_search_url(self, filters: SearchFilters) -> str:
        """
        构建搜索URL
        
        Args:
            filters: 搜索过滤条件
            
        Returns:
            str: 搜索URL
        """
        params = filters.to_params()
        return f"{self.search_url}?{urlencode(params)}"
    
    async def _enrich_product_detail(self, product: ProductData) -> ProductData:
        """
        丰富商品详情数据
        
        Args:
            product: 原始商品数据
            
        Returns:
            ProductData: 丰富后的商品数据
        """
        try:
            # 处理图片
            if product.images:
                product.images = self.image_tool.filter_valid_images(product.images)
                product.images = self.image_tool.sort_images_by_quality(product.images)
            
            # 处理时间
            if product.created_at:
                product.created_at = self.time_tool.parse_japanese_date(str(product.created_at))
            
            # 添加额外分析标签
            if product.is_high_quality():
                product.add_tag("high_quality")
            
            if product.price and product.price < 1000:
                product.add_tag("budget_friendly")
            
            if product.condition and "新品" in product.condition:
                product.add_tag("new_condition")
            
            return product
            
        except Exception as e:
            logger.warning(f"Failed to enrich product detail: {e}")
            return product
    
    async def _delay_between_requests(self):
        """请求间延迟"""
        delay = random.uniform(*self.config.delay_range)
        await asyncio.sleep(delay)
    
    def _load_category_mapping(self) -> Dict[str, int]:
        """加载分类映射"""
        return {
            "レディース": 1,
            "メンズ": 2,
            "ベビー・キッズ": 3,
            "インテリア・住まい・小物": 4,
            "本・音楽・ゲーム": 5,
            "おもちゃ・ホビー・グッズ": 6,
            "コスメ・香水・美容": 7,
            "家電・スマホ・カメラ": 8,
            "スポーツ・レジャー": 9,
            "ハンドメイド": 10,
            "チケット": 11,
            "自動車・オートバイ": 12,
            "その他": 13
        }
    
    def _load_condition_mapping(self) -> Dict[str, int]:
        """加载状态映射"""
        return {
            "新品・未使用": 1,
            "未使用に近い": 2,
            "目立った傷や汚れなし": 3,
            "やや傷や汚れあり": 4,
            "傷や汚れあり": 5,
            "全体的に状態が悪い": 6
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查
        
        Returns:
            Dict[str, Any]: 健康状态
        """
        session_health = await self.session_manager.health_check()
        
        return {
            "scraper_status": "healthy",
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "blocked_requests": self.blocked_requests,
            "products_scraped": self.products_scraped,
            "success_rate": (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0,
            "session_manager": session_health,
            "anti_bot_handler": self.anti_bot_handler.get_stats(),
            "data_parser": self.data_parser.get_parser_stats()
        }
    
    async def get_popular_searches(self) -> List[str]:
        """
        获取热门搜索
        
        Returns:
            List[str]: 热门搜索关键词
        """
        try:
            # 从Mercari首页获取热门搜索
            result = await self.scrape_page(self.base_url)
            
            if result.success:
                # 这里需要解析热门搜索，简化实现
                return [
                    "iPhone", "ナイキ", "アディダス", "シャネル", "ルイヴィトン",
                    "任天堂", "ポケモン", "アニメ", "本", "化粧品"
                ]
            else:
                return []
                
        except Exception as e:
            logger.error(f"Failed to get popular searches: {e}")
            return []
    
    async def get_trending_categories(self) -> List[Dict[str, Any]]:
        """
        获取热门分类
        
        Returns:
            List[Dict[str, Any]]: 热门分类信息
        """
        try:
            categories = []
            
            for category_name, category_id in self.supported_categories.items():
                # 获取分类商品数量（简化实现）
                filters = SearchFilters(
                    keywords="",
                    category_id=category_id,
                    limit=1  # 只获取1个结果用于统计
                )
                
                result = await self.search_products(filters, max_pages=1)
                
                categories.append({
                    "name": category_name,
                    "id": category_id,
                    "product_count": len(result),
                    "url": f"{self.base_url}/category/{category_id}"
                })
            
            # 按商品数量排序
            categories.sort(key=lambda x: x["product_count"], reverse=True)
            
            return categories[:10]  # 返回前10个
            
        except Exception as e:
            logger.error(f"Failed to get trending categories: {e}")
            return []
    
    async def extract_product_data(self, content: str, url: str) -> List[ProductData]:
        """
        从页面内容提取产品数据
        
        Args:
            content: 页面内容
            url: 页面URL
            
        Returns:
            List[ProductData]: 产品数据列表
        """
        try:
            # 创建解析上下文
            context = ParsingContext(
                page_type=PageType.UNKNOWN,
                base_url=self.base_url,
                current_url=url,
                user_agent=None,
                timestamp=datetime.now()
            )
            
            # 使用数据解析器解析页面
            parsing_result = self.data_parser.parse_page(content, context)
            
            # 验证和清洗数据
            validated_products = []
            for product in parsing_result.products:
                is_valid, errors = self.validation_tool.validate_product_data(product.to_dict())
                if is_valid:
                    cleaned_product = self.data_parser.clean_product_data(product)
                    validated_products.append(cleaned_product)
                else:
                    logger.warning(f"Invalid product data: {errors}")
            
            return validated_products
            
        except Exception as e:
            logger.error(f"Failed to extract product data from {url}: {e}")
            return []
    
    async def close(self):
        """关闭爬虫"""
        close_errors = []
        
        # 关闭会话管理器
        try:
            if hasattr(self.session_manager, 'close_all'):
                await self.session_manager.close_all()
            elif hasattr(self.session_manager, 'close'):
                await self.session_manager.close()
        except Exception as e:
            logger.error(f"关闭会话管理器时出错: {e}")
            close_errors.append(f"Session manager: {e}")
        
        # 关闭CAPTCHA工作流
        try:
            if hasattr(self.captcha_workflow, 'close'):
                await self.captcha_workflow.close()
        except Exception as e:
            logger.error(f"关闭CAPTCHA工作流时出错: {e}")
            close_errors.append(f"CAPTCHA workflow: {e}")
        
        # 关闭任务队列
        try:
            if hasattr(self.task_queue, 'close'):
                await self.task_queue.close()
        except Exception as e:
            logger.error(f"关闭任务队列时出错: {e}")
            close_errors.append(f"Task queue: {e}")
        
        # 关闭CAPTCHA UI管理器
        try:
            if hasattr(self.captcha_ui_manager, 'close'):
                await self.captcha_ui_manager.close()
        except Exception as e:
            logger.error(f"关闭CAPTCHA UI管理器时出错: {e}")
            close_errors.append(f"CAPTCHA UI manager: {e}")
        
        # 关闭基类会话
        try:
            await super().close()
        except Exception as e:
            logger.error(f"关闭基类会话时出错: {e}")
            close_errors.append(f"Base scraper: {e}")
        
        if close_errors:
            logger.warning(f"MercariScraper关闭时遇到错误: {close_errors}")
        else:
            logger.info("Enhanced MercariScraper已完全关闭")
    
    def get_scraper_stats(self) -> Dict[str, Any]:
        """
        获取爬虫统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        return {
            "scraper_info": {
                "strategy": self.config.strategy.value if hasattr(self.config.strategy, 'value') else str(self.config.strategy),
                "base_url": self.base_url,
                "supported_categories": len(self.supported_categories),
                "supported_conditions": len(self.supported_conditions)
            },
            "performance": {
                "total_requests": self.total_requests,
                "successful_requests": self.successful_requests,
                "failed_requests": self.failed_requests,
                "blocked_requests": self.blocked_requests,
                "products_scraped": self.products_scraped,
                "success_rate": (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0
            },
            "components": {
                "session_manager": self.session_manager.get_stats(),
                "anti_bot_handler": self.anti_bot_handler.get_stats(),
                "data_parser": self.data_parser.get_parser_stats()
            }
        }


# 便捷函数
async def create_mercari_scraper(strategy: ScrapingStrategy = ScrapingStrategy.REQUESTS) -> MercariScraper:
    """
    创建并初始化Mercari爬虫
    
    Args:
        strategy: 爬虫策略
        
    Returns:
        MercariScraper: 初始化后的爬虫实例
    """
    scraper = MercariScraper(strategy)
    await scraper.initialize()
    return scraper


async def quick_search(keywords: str, max_pages: int = 3) -> List[ProductData]:
    """
    快速搜索
    
    Args:
        keywords: 搜索关键词
        max_pages: 最大页数
        
    Returns:
        List[ProductData]: 搜索结果
    """
    scraper = await create_mercari_scraper()
    
    try:
        filters = SearchFilters(keywords=keywords)
        results = await scraper.search_products(filters, max_pages=max_pages)
        return results
    finally:
        await scraper.close()


async def get_product_detail(product_url: str) -> Optional[ProductData]:
    """
    获取商品详情
    
    Args:
        product_url: 商品URL
        
    Returns:
        Optional[ProductData]: 商品详情
    """
    scraper = await create_mercari_scraper()
    
    try:
        return await scraper.scrape_product_detail(product_url)
    finally:
        await scraper.close()