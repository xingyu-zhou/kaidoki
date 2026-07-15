"""
爬虫服务模块

该模块提供Mercari平台的数据爬取功能。
实现了智能反爬虫机制、请求节流和数据提取。

主要功能：
- 多种爬虫策略（requests、Selenium、Playwright）
- 智能反爬虫检测和处理
- 请求节流和会话管理
- 数据提取和清洗
- 错误处理和重试机制

Author: Mercari AI Agent Team
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import json
import random
import time

from ..models.product import ProductData
from ..models.query import ParsedQuery
from ..scrapers.mercari_scraper import MercariScraper
from ..scrapers.anti_bot_handler import AntiBotHandler
from ..utils.cache_manager import CacheManager
from ..utils.logger import get_logger
from ..config.settings import settings

logger = get_logger(__name__)


class ScrapingStrategy(Enum):
    """爬虫策略枚举"""
    REQUESTS = "requests"          # 基于requests的快速爬虫
    SELENIUM = "selenium"          # 基于Selenium的浏览器爬虫
    PLAYWRIGHT = "playwright"     # 基于Playwright的现代爬虫
    HYBRID = "hybrid"             # 混合策略


@dataclass
class ScrapingResult:
    """爬虫结果"""
    products: List[ProductData]
    total_found: int
    pages_scraped: int
    strategy_used: ScrapingStrategy
    processing_time: float
    cache_hit_ratio: float
    metadata: Dict[str, Any]


@dataclass
class ScrapingContext:
    """爬虫上下文"""
    query: ParsedQuery
    max_pages: int = 5
    max_products: int = 50
    strategy: ScrapingStrategy = ScrapingStrategy.REQUESTS
    use_cache: bool = True
    bypass_rate_limit: bool = False


class ScraperService:
    """
    爬虫服务类
    
    负责从Mercari平台爬取产品数据。
    提供多种爬虫策略和智能反爬虫机制。
    """
    
    def __init__(self, config=None):
        """初始化爬虫服务"""
        self.config = config or getattr(settings, 'scraper', None)
        self.scrapers = {}
        self.anti_bot_handler = AntiBotHandler()
        self.cache_manager = CacheManager()
        self.request_stats = {}
        self.last_request_time = {}
        
        # 初始化各种爬虫
        self._initialize_scrapers()
        
        logger.info("ScraperService initialized")
    
    async def initialize(self):
        """异步初始化爬虫服务"""
        try:
            # 初始化所有爬虫
            for strategy, scraper in self.scrapers.items():
                if hasattr(scraper, 'initialize'):
                    await scraper.initialize()
            
            logger.info("ScraperService initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing ScraperService: {e}")
            raise
    
    async def close(self):
        """关闭爬虫服务，清理资源"""
        try:
            # 关闭所有爬虫
            for scraper in self.scrapers.values():
                if hasattr(scraper, 'close'):
                    await scraper.close()
            
            # 清理缓存管理器
            if hasattr(self.cache_manager, 'close'):
                await self.cache_manager.close()
            
            logger.info("ScraperService closed successfully")
        except Exception as e:
            logger.error(f"Error closing ScraperService: {e}")
    
    def _initialize_scrapers(self):
        """初始化爬虫实例"""
        self.scrapers[ScrapingStrategy.REQUESTS] = MercariScraper(
            strategy=ScrapingStrategy.REQUESTS,
            anti_bot_handler=self.anti_bot_handler
        )
        
        if getattr(settings, 'ENABLE_SELENIUM', False):
            self.scrapers[ScrapingStrategy.SELENIUM] = MercariScraper(
                strategy=ScrapingStrategy.SELENIUM,
                anti_bot_handler=self.anti_bot_handler
            )
        
        if getattr(settings, 'ENABLE_PLAYWRIGHT', False):
            self.scrapers[ScrapingStrategy.PLAYWRIGHT] = MercariScraper(
                strategy=ScrapingStrategy.PLAYWRIGHT,
                anti_bot_handler=self.anti_bot_handler
            )
    
    async def scrape(self, context: ScrapingContext) -> ScrapingResult:
        """
        执行爬虫任务
        
        Args:
            context: 爬虫上下文
            
        Returns:
            ScrapingResult: 爬虫结果
            
        Raises:
            ScrapingError: 爬虫失败时抛出
        """
        start_time = time.time()
        
        try:
            # 1. 缓存检查
            if context.use_cache:
                cached_result = await self._check_cache(context)
                if cached_result:
                    logger.info("从缓存获取爬虫结果")
                    return cached_result
            
            # 2. 选择爬虫策略
            strategy = await self._select_strategy(context)
            scraper = self.scrapers.get(strategy)
            
            if not scraper:
                strategy_name = strategy.value if hasattr(strategy, 'value') else str(strategy)
                raise ScrapingError(f"爬虫策略 {strategy_name} 不可用")
            
            # 3. 请求节流
            if not context.bypass_rate_limit:
                await self._throttle_requests(strategy)
            
            # 4. 执行爬虫
            products = await self._scrape_with_strategy(scraper, context)
            
            # 5. 数据后处理
            processed_products = await self._post_process_products(products, context)
            
            # 6. 构建结果
            processing_time = time.time() - start_time
            result = ScrapingResult(
                products=processed_products,
                total_found=len(processed_products),
                pages_scraped=min(context.max_pages, (len(processed_products) + 19) // 20),
                strategy_used=strategy,
                processing_time=processing_time,
                cache_hit_ratio=0.0,  # 无缓存命中
                metadata={
                    "query": context.query.original_query,
                    "scraper_stats": self.request_stats.get(strategy, {}),
                    "anti_bot_actions": self.anti_bot_handler.get_stats()
                }
            )
            
            # 7. 缓存结果
            if context.use_cache:
                await self._cache_result(context, result)
            
            # 8. 更新统计
            self._update_request_stats(strategy, result)
            
            logger.info(f"爬虫完成: {len(processed_products)} 个产品，耗时 {processing_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"爬虫失败: {e}")
            raise ScrapingError(f"爬虫执行失败: {e}")
    
    async def _check_cache(self, context: ScrapingContext) -> Optional[ScrapingResult]:
        """
        检查缓存
        
        Args:
            context: 爬虫上下文
            
        Returns:
            Optional[ScrapingResult]: 缓存结果
        """
        cache_key = self._generate_cache_key(context)
        cached_data = await self.cache_manager.get(cache_key)
        
        if cached_data:
            try:
                return ScrapingResult(**cached_data)
            except Exception as e:
                logger.warning(f"缓存数据格式错误: {e}")
                await self.cache_manager.delete(cache_key)
        
        return None
    
    async def _select_strategy(self, context: ScrapingContext) -> ScrapingStrategy:
        """
        选择爬虫策略
        
        Args:
            context: 爬虫上下文
            
        Returns:
            ScrapingStrategy: 选择的策略
        """
        if context.strategy != ScrapingStrategy.HYBRID:
            return context.strategy
        
        # 混合策略：根据历史成功率选择
        success_rates = {}
        for strategy in self.scrapers.keys():
            stats = self.request_stats.get(strategy, {})
            success_rate = stats.get("success_rate", 0.5)
            success_rates[strategy] = success_rate
        
        # 选择成功率最高的策略
        best_strategy = max(success_rates, key=success_rates.get)
        strategy_name = best_strategy.value if hasattr(best_strategy, 'value') else str(best_strategy)
        logger.debug(f"混合策略选择: {strategy_name}")
        
        return best_strategy
    
    async def _throttle_requests(self, strategy: ScrapingStrategy):
        """
        请求节流
        
        Args:
            strategy: 爬虫策略
        """
        last_time = self.last_request_time.get(strategy, 0)
        strategy_key = strategy.value if hasattr(strategy, 'value') else str(strategy)
        min_interval = settings.REQUEST_INTERVALS.get(strategy_key, 1.0)
        
        elapsed = time.time() - last_time
        if elapsed < min_interval:
            wait_time = min_interval - elapsed
            await asyncio.sleep(wait_time)
        
        self.last_request_time[strategy] = time.time()
    
    async def _scrape_with_strategy(
        self,
        scraper: MercariScraper,
        context: ScrapingContext
    ) -> List[ProductData]:
        """
        使用指定策略爬取
        
        Args:
            scraper: 爬虫实例
            context: 爬虫上下文
            
        Returns:
            List[ProductData]: 产品数据列表
        """
        products = []
        pages_scraped = 0
        
        for page in range(1, context.max_pages + 1):
            try:
                # 构建搜索URL
                search_url = self._build_search_url(context.query, page)
                
                # 爬取页面
                page_products = await scraper.scrape_page(search_url)
                
                if not page_products:
                    logger.warning(f"第 {page} 页没有获取到数据")
                    break
                
                products.extend(page_products)
                pages_scraped += 1
                
                # 检查是否达到最大产品数
                if len(products) >= context.max_products:
                    products = products[:context.max_products]
                    break
                
                # 页面间随机延迟
                await asyncio.sleep(random.uniform(0.5, 2.0))
                
            except Exception as e:
                logger.error(f"爬取第 {page} 页失败: {e}")
                break
        
        logger.info(f"爬取完成: {pages_scraped} 页，{len(products)} 个产品")
        return products
    
    def _build_search_url(self, query: ParsedQuery, page: int = 1) -> str:
        """
        构建搜索URL
        
        Args:
            query: 解析后的查询
            page: 页码
            
        Returns:
            str: 搜索URL
        """
        base_url = "https://jp.mercari.com/search"
        params = []
        
        # 关键词
        if query.keywords:
            if isinstance(query.keywords, list):
                keyword = " ".join(str(k) for k in query.keywords if k and k != "用户查询的关键词")
            else:
                keyword = str(query.keywords) if query.keywords != "用户查询的关键词" else ""
            
            if keyword:
                params.append(f"keyword={keyword}")
        
        # 类别
        if query.category:
            category_id = self._get_category_id(query.category)
            if category_id:
                params.append(f"category_id={category_id}")
        
        # 价格范围
        if query.price_min:
            params.append(f"price_min={int(query.price_min)}")
        if query.price_max:
            params.append(f"price_max={int(query.price_max)}")
        
        # 商品状态
        if query.condition:
            condition_id = self._get_condition_id(query.condition)
            if condition_id:
                params.append(f"item_condition_id={condition_id}")
        
        # 排序
        params.append("sort=created_time&order=desc")
        
        # 页码
        if page > 1:
            params.append(f"page={page}")
        
        # 构建完整URL
        if params:
            url = f"{base_url}?{'&'.join(params)}"
        else:
            url = base_url
        
        return url
    
    def _get_category_id(self, category: str) -> Optional[int]:
        """
        获取类别ID
        
        Args:
            category: 类别名称
            
        Returns:
            Optional[int]: 类别ID
        """
        category_mapping = {
            "ファッション": 1,
            "家電・スマホ・カメラ": 2,
            "本・音楽・ゲーム": 3,
            "コスメ・香水・美容": 4,
            "スポーツ・レジャー": 5,
            "ハンドメイド": 6,
            "食品": 7,
            "その他": 8
        }
        
        return category_mapping.get(category)
    
    def _get_condition_id(self, condition: str) -> Optional[int]:
        """
        获取商品状态ID
        
        Args:
            condition: 商品状态
            
        Returns:
            Optional[int]: 状态ID
        """
        condition_mapping = {
            "新品・未使用": 1,
            "未使用に近い": 2,
            "目立った傷や汚れなし": 3,
            "やや傷や汚れあり": 4,
            "傷や汚れあり": 5,
            "全体的に状態が悪い": 6
        }
        
        return condition_mapping.get(condition)
    
    async def _post_process_products(
        self,
        products: List[ProductData],
        context: ScrapingContext
    ) -> List[ProductData]:
        """
        产品数据后处理
        
        Args:
            products: 原始产品数据
            context: 爬虫上下文
            
        Returns:
            List[ProductData]: 处理后的产品数据
        """
        processed_products = []
        
        for product in products:
            try:
                # 数据验证
                if not self._validate_product_data(product):
                    continue
                
                # 价格规范化
                if product.price:
                    product.price = float(product.price)
                
                # 图片URL处理
                if product.images:
                    product.images = [self._normalize_image_url(img) for img in product.images]
                
                # 添加元数据
                product.scraped_at = datetime.now()
                product.scraper_version = "1.0.0"
                
                processed_products.append(product)
                
            except Exception as e:
                logger.warning(f"产品数据处理失败: {e}")
                continue
        
        return processed_products
    
    def _validate_product_data(self, product: ProductData) -> bool:
        """
        验证产品数据
        
        Args:
            product: 产品数据
            
        Returns:
            bool: 是否有效
        """
        # 必需字段检查
        if not product.title or not product.url:
            return False
        
        # 价格检查
        if product.price is not None and product.price <= 0:
            return False
        
        # URL格式检查
        if not product.url.startswith("https://jp.mercari.com/"):
            return False
        
        return True
    
    def _normalize_image_url(self, image_url: str) -> str:
        """
        规范化图片URL
        
        Args:
            image_url: 原始图片URL
            
        Returns:
            str: 规范化后的URL
        """
        if not image_url.startswith("http"):
            return f"https://static.mercdn.net/item/detail/orig/{image_url}"
        
        return image_url
    
    def _generate_cache_key(self, context: ScrapingContext) -> str:
        """
        生成缓存键
        
        Args:
            context: 爬虫上下文
            
        Returns:
            str: 缓存键
        """
        key_parts = [
            context.query.normalized_query,
            str(context.max_pages),
            str(context.max_products),
            context.strategy.value if hasattr(context.strategy, 'value') else str(context.strategy)
        ]
        
        if context.query.category:
            key_parts.append(context.query.category)
        
        if context.query.price_min:
            key_parts.append(str(context.query.price_min))
        
        if context.query.price_max:
            key_parts.append(str(context.query.price_max))
        
        return "scraper:" + ":".join(key_parts)
    
    async def _cache_result(self, context: ScrapingContext, result: ScrapingResult):
        """
        缓存结果
        
        Args:
            context: 爬虫上下文
            result: 爬虫结果
        """
        cache_key = self._generate_cache_key(context)
        cache_data = {
            "products": [product.__dict__ for product in result.products],
            "total_found": result.total_found,
            "pages_scraped": result.pages_scraped,
            "strategy_used": result.strategy_used.value if hasattr(result.strategy_used, 'value') else str(result.strategy_used),
            "processing_time": result.processing_time,
            "cache_hit_ratio": result.cache_hit_ratio,
            "metadata": result.metadata
        }
        
        # 缓存1小时
        await self.cache_manager.set(cache_key, cache_data, ttl=3600)
    
    def _update_request_stats(self, strategy: ScrapingStrategy, result: ScrapingResult):
        """
        更新请求统计
        
        Args:
            strategy: 爬虫策略
            result: 爬虫结果
        """
        if strategy not in self.request_stats:
            self.request_stats[strategy] = {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "total_products": 0,
                "total_time": 0.0,
                "success_rate": 0.0,
                "avg_response_time": 0.0,
                "last_used": None
            }
        
        stats = self.request_stats[strategy]
        stats["total_requests"] += 1
        stats["successful_requests"] += 1
        stats["total_products"] += result.total_found
        stats["total_time"] += result.processing_time
        stats["success_rate"] = stats["successful_requests"] / stats["total_requests"]
        stats["avg_response_time"] = stats["total_time"] / stats["total_requests"]
        stats["last_used"] = datetime.now()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取爬虫统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        return {
            "request_stats": self.request_stats,
            "anti_bot_stats": self.anti_bot_handler.get_stats(),
            "cache_stats": self.cache_manager.get_stats(),
            "available_strategies": list(self.scrapers.keys())
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查
        
        Returns:
            Dict[str, Any]: 健康状态
        """
        health_status = {
            "service": "healthy",
            "scrapers": {},
            "anti_bot_handler": "healthy",
            "cache_manager": "healthy"
        }
        
        # 检查各个爬虫
        for strategy, scraper in self.scrapers.items():
            try:
                await scraper.health_check()
                strategy_key = strategy.value if hasattr(strategy, 'value') else str(strategy)
                health_status["scrapers"][strategy_key] = "healthy"
            except Exception as e:
                strategy_key = strategy.value if hasattr(strategy, 'value') else str(strategy)
                health_status["scrapers"][strategy_key] = f"unhealthy: {e}"
                health_status["service"] = "degraded"
        
        return health_status


class ScrapingError(Exception):
    """爬虫异常"""
    pass