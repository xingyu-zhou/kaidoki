"""
爬虫系统集成测试

该模块包含完整爬虫系统的集成测试。
测试各个组件之间的协同工作和端到端的爬虫流程。

Author: Mercari AI Agent Team
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import aiohttp
from bs4 import BeautifulSoup

from mercari_agent.scrapers.mercari_scraper import MercariScraper, SearchFilters
from mercari_agent.scrapers.base_scraper import ScrapingStrategy
from mercari_agent.scrapers.session_manager import SessionManager
from mercari_agent.scrapers.data_parser import DataParser
from mercari_agent.scrapers.anti_bot_handler import AntiBotHandler
from mercari_agent.models.product import ProductData
from mercari_agent.config.settings import ScraperConfig


class TestScraperIntegration:
    """爬虫系统集成测试"""
    
    @pytest.mark.asyncio
    async def test_complete_scraping_workflow(self):
        """测试完整的爬虫工作流程"""
        # 创建爬虫实例
        scraper = MercariScraper(strategy=ScrapingStrategy.REQUESTS)
        
        # 模拟搜索页面HTML
        search_html = """
        <html>
            <body>
                <div data-testid="search-item">
                    <h3 data-testid="product-name">iPhone 12 Pro</h3>
                    <span data-testid="product-price">¥80,000</span>
                    <a data-testid="product-link" href="/item/test123">Link</a>
                    <img data-testid="product-image" src="https://example.com/image1.jpg">
                    <span data-testid="product-condition">新品・未使用</span>
                    <span data-testid="seller-name">TrustedSeller</span>
                </div>
                <div data-testid="search-item">
                    <h3 data-testid="product-name">iPhone 13</h3>
                    <span data-testid="product-price">¥90,000</span>
                    <a data-testid="product-link" href="/item/test456">Link</a>
                    <img data-testid="product-image" src="https://example.com/image2.jpg">
                    <span data-testid="product-condition">未使用に近い</span>
                    <span data-testid="seller-name">ReliableSeller</span>
                </div>
                <div data-testid="pagination">
                    <span data-testid="current-page">1</span>
                    <button data-testid="next-page">次へ</button>
                </div>
            </body>
        </html>
        """
        
        # 模拟商品详情页面HTML
        detail_html = """
        <html>
            <body>
                <div data-testid="product-detail">
                    <h1 data-testid="product-name">iPhone 12 Pro 256GB</h1>
                    <div data-testid="product-price">¥80,000</div>
                    <div data-testid="product-description">
                        <p>iPhone 12 Pro 256GB in excellent condition.</p>
                        <p>Comes with original box and accessories.</p>
                    </div>
                    <div data-testid="product-images">
                        <img src="https://example.com/detail1.jpg" alt="Front">
                        <img src="https://example.com/detail2.jpg" alt="Back">
                        <img src="https://example.com/detail3.jpg" alt="Box">
                    </div>
                    <div data-testid="product-condition">新品・未使用</div>
                    <div data-testid="seller-info">
                        <span data-testid="seller-name">TrustedSeller</span>
                        <span data-testid="seller-rating">4.9</span>
                        <span data-testid="seller-reviews">1500</span>
                    </div>
                    <div data-testid="shipping-info">
                        <span data-testid="shipping-cost">¥300</span>
                        <span data-testid="shipping-method">らくらくメルカリ便</span>
                    </div>
                    <div data-testid="listing-date">2024-01-20</div>
                    <div data-testid="view-count">856 views</div>
                    <div data-testid="like-count">127 likes</div>
                </div>
            </body>
        </html>
        """
        
        # 模拟HTTP响应
        mock_search_response = AsyncMock()
        mock_search_response.status = 200
        mock_search_response.text = AsyncMock(return_value=search_html)
        
        mock_detail_response = AsyncMock()
        mock_detail_response.status = 200
        mock_detail_response.text = AsyncMock(return_value=detail_html)
        
        # 模拟会话管理器
        with patch.object(scraper.session_manager, 'make_request') as mock_request, \
             patch.object(scraper.anti_bot_handler, 'detect_bot_protection') as mock_detect, \
             patch.object(scraper, '_delay_between_requests'):
            
            # 配置模拟
            mock_request.side_effect = [mock_search_response, mock_detail_response]
            
            mock_detect_result = MagicMock()
            mock_detect_result.is_detected = False
            mock_detect.return_value = mock_detect_result
            
            # 执行搜索
            filters = SearchFilters(keywords="iPhone", max_pages=1)
            products = await scraper.search_products(filters)
            
            # 验证搜索结果
            assert len(products) == 2
            assert products[0].title == "iPhone 12 Pro"
            assert products[0].price == 80000
            assert products[0].condition == "新品・未使用"
            assert products[1].title == "iPhone 13"
            assert products[1].price == 90000
            
            # 获取详细信息
            detailed_product = await scraper.scrape_product_detail(products[0].url)
            
            # 验证详细信息
            assert detailed_product is not None
            assert detailed_product.title == "iPhone 12 Pro 256GB"
            assert detailed_product.price == 80000
            assert "iPhone 12 Pro 256GB in excellent condition" in detailed_product.description
            assert len(detailed_product.images) == 3
            assert detailed_product.seller_rating == 4.9
            assert detailed_product.seller_reviews == 1500
            assert detailed_product.shipping_cost == 300
            assert detailed_product.view_count == 856
            assert detailed_product.like_count == 127
            
            # 验证统计信息
            assert scraper.total_requests == 2
            assert scraper.successful_requests == 2
            assert scraper.failed_requests == 0
            assert scraper.products_scraped == 3  # 2 from search + 1 from detail
    
    @pytest.mark.asyncio
    async def test_anti_bot_handling_integration(self):
        """测试反爬虫处理集成"""
        scraper = MercariScraper(strategy=ScrapingStrategy.REQUESTS)
        
        # 模拟被反爬虫系统阻止的响应
        blocked_html = """
        <html>
            <body>
                <div class="g-recaptcha" data-sitekey="test-site-key">
                    <div>Please complete the CAPTCHA</div>
                </div>
            </body>
        </html>
        """
        
        # 模拟绕过后的正常响应
        normal_html = """
        <html>
            <body>
                <div data-testid="search-item">
                    <h3 data-testid="product-name">Bypassed Product</h3>
                    <span data-testid="product-price">¥50,000</span>
                    <a data-testid="product-link" href="/item/bypassed">Link</a>
                </div>
            </body>
        </html>
        """
        
        # 模拟HTTP响应
        mock_blocked_response = AsyncMock()
        mock_blocked_response.status = 200
        mock_blocked_response.text = AsyncMock(return_value=blocked_html)
        
        mock_normal_response = AsyncMock()
        mock_normal_response.status = 200
        mock_normal_response.text = AsyncMock(return_value=normal_html)
        
        # 模拟会话和反爬虫处理
        with patch.object(scraper.session_manager, 'make_request', return_value=mock_blocked_response), \
             patch.object(scraper.session_manager, 'get_session') as mock_get_session, \
             patch.object(scraper.anti_bot_handler, 'handle_block', return_value=normal_html):
            
            # 模拟会话
            mock_session_info = MagicMock()
            mock_session_info.session = AsyncMock()
            mock_get_session.return_value = mock_session_info
            
            # 执行搜索
            filters = SearchFilters(keywords="iPhone")
            products = await scraper.search_products(filters)
            
            # 验证绕过成功
            assert len(products) == 1
            assert products[0].title == "Bypassed Product"
            assert products[0].price == 50000
            
            # 验证反爬虫处理被调用
            scraper.anti_bot_handler.handle_block.assert_called_once()
            assert scraper.blocked_requests == 1
    
    @pytest.mark.asyncio
    async def test_session_management_integration(self):
        """测试会话管理集成"""
        scraper = MercariScraper(strategy=ScrapingStrategy.REQUESTS)
        
        # 模拟多个请求
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="<html><body>Test</body></html>")
        
        with patch.object(scraper.session_manager, 'make_request', return_value=mock_response) as mock_request, \
             patch.object(scraper.session_manager, 'get_session') as mock_get_session, \
             patch.object(scraper.session_manager, 'close_session') as mock_close_session:
            
            # 模拟会话
            mock_session_info = MagicMock()
            mock_session_info.session = AsyncMock()
            mock_session_info.request_count = 0
            mock_get_session.return_value = mock_session_info
            
            # 执行多个请求
            urls = [
                "https://jp.mercari.com/item/1",
                "https://jp.mercari.com/item/2",
                "https://jp.mercari.com/item/3"
            ]
            
            for url in urls:
                await scraper.scrape_page(url)
            
            # 验证会话管理
            assert mock_request.call_count == 3
            assert mock_get_session.call_count == 3
            
            # 关闭爬虫
            await scraper.close()
            
            # 验证会话关闭
            scraper.session_manager.close_all.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_data_validation_integration(self):
        """测试数据验证集成"""
        scraper = MercariScraper(strategy=ScrapingStrategy.REQUESTS)
        
        # 模拟包含无效数据的HTML
        invalid_html = """
        <html>
            <body>
                <div data-testid="search-item">
                    <h3 data-testid="product-name"></h3>
                    <span data-testid="product-price">¥-1,000</span>
                    <a data-testid="product-link" href="invalid-url">Link</a>
                </div>
                <div data-testid="search-item">
                    <h3 data-testid="product-name">Valid Product</h3>
                    <span data-testid="product-price">¥50,000</span>
                    <a data-testid="product-link" href="/item/valid">Link</a>
                </div>
            </body>
        </html>
        """
        
        # 模拟HTTP响应
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=invalid_html)
        
        with patch.object(scraper.session_manager, 'make_request', return_value=mock_response), \
             patch.object(scraper.anti_bot_handler, 'detect_bot_protection') as mock_detect:
            
            # 配置模拟
            mock_detect_result = MagicMock()
            mock_detect_result.is_detected = False
            mock_detect.return_value = mock_detect_result
            
            # 执行搜索
            filters = SearchFilters(keywords="test")
            products = await scraper.search_products(filters)
            
            # 验证只返回有效产品
            assert len(products) == 1
            assert products[0].title == "Valid Product"
            assert products[0].price == 50000
            assert products[0].url == "https://jp.mercari.com/item/valid"
    
    @pytest.mark.asyncio
    async def test_batch_processing_integration(self):
        """测试批量处理集成"""
        scraper = MercariScraper(strategy=ScrapingStrategy.REQUESTS)
        
        # 模拟多个商品详情页面
        detail_templates = [
            ("Product 1", 10000),
            ("Product 2", 20000),
            ("Product 3", 30000),
            ("Product 4", 40000),
            ("Product 5", 50000)
        ]
        
        def create_detail_html(title, price):
            return f"""
            <html>
                <body>
                    <div data-testid="product-detail">
                        <h1 data-testid="product-name">{title}</h1>
                        <div data-testid="product-price">¥{price:,}</div>
                        <div data-testid="product-description">Description for {title}</div>
                    </div>
                </body>
            </html>
            """
        
        # 模拟HTTP响应
        mock_responses = []
        for title, price in detail_templates:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value=create_detail_html(title, price))
            mock_responses.append(mock_response)
        
        with patch.object(scraper.session_manager, 'make_request', side_effect=mock_responses), \
             patch.object(scraper.anti_bot_handler, 'detect_bot_protection') as mock_detect, \
             patch('asyncio.sleep'):  # 跳过延迟
            
            # 配置模拟
            mock_detect_result = MagicMock()
            mock_detect_result.is_detected = False
            mock_detect.return_value = mock_detect_result
            
            # 执行批量爬取
            urls = [f"https://jp.mercari.com/item/{i}" for i in range(1, 6)]
            products = await scraper.batch_scrape_products(urls, batch_size=2)
            
            # 验证批量处理结果
            assert len(products) == 5
            for i, product in enumerate(products):
                expected_title, expected_price = detail_templates[i]
                assert product.title == expected_title
                assert product.price == expected_price
                assert f"Description for {expected_title}" in product.description
    
    @pytest.mark.asyncio
    async def test_error_handling_integration(self):
        """测试错误处理集成"""
        scraper = MercariScraper(strategy=ScrapingStrategy.REQUESTS)
        
        # 模拟各种错误情况
        with patch.object(scraper.session_manager, 'make_request') as mock_request:
            
            # 网络错误
            mock_request.side_effect = aiohttp.ClientError("Network error")
            
            result = await scraper.scrape_page("https://jp.mercari.com/search")
            
            assert result.success is False
            assert "Network error" in result.error_message
            assert scraper.failed_requests == 1
            
            # 重置计数器
            scraper.failed_requests = 0
            
            # HTTP错误
            mock_response = AsyncMock()
            mock_response.status = 404
            mock_response.text = AsyncMock(return_value="Not Found")
            mock_request.side_effect = None
            mock_request.return_value = mock_response
            
            result = await scraper.scrape_page("https://jp.mercari.com/search")
            
            assert result.success is False
            assert "404" in result.error_message
            assert scraper.failed_requests == 1
    
    @pytest.mark.asyncio
    async def test_performance_monitoring_integration(self):
        """测试性能监控集成"""
        scraper = MercariScraper(strategy=ScrapingStrategy.REQUESTS)
        
        # 模拟响应
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="<html><body>Test</body></html>")
        
        with patch.object(scraper.session_manager, 'make_request', return_value=mock_response), \
             patch.object(scraper.anti_bot_handler, 'detect_bot_protection') as mock_detect:
            
            # 配置模拟
            mock_detect_result = MagicMock()
            mock_detect_result.is_detected = False
            mock_detect.return_value = mock_detect_result
            
            # 执行多个请求
            start_time = datetime.now()
            
            for i in range(10):
                await scraper.scrape_page(f"https://jp.mercari.com/item/{i}")
            
            end_time = datetime.now()
            
            # 验证性能统计
            assert scraper.total_requests == 10
            assert scraper.successful_requests == 10
            assert scraper.failed_requests == 0
            
            # 检查健康状态
            health = await scraper.health_check()
            assert health["scraper_status"] == "healthy"
            assert health["total_requests"] == 10
            assert health["success_rate"] == 100.0
            
            # 检查统计信息
            stats = scraper.get_scraper_stats()
            assert stats["performance"]["total_requests"] == 10
            assert stats["performance"]["success_rate"] == 100.0
    
    @pytest.mark.asyncio
    async def test_configuration_integration(self):
        """测试配置集成"""
        # 自定义配置
        config = ScraperConfig(
            max_concurrent_requests=5,
            request_timeout=15,
            retry_attempts=2,
            rate_limit_delay=0.5
        )
        
        scraper = MercariScraper(config=config)
        
        # 验证配置生效
        assert scraper.config.max_concurrent_requests == 5
        assert scraper.config.request_timeout == 15
        assert scraper.config.retry_attempts == 2
        assert scraper.config.rate_limit_delay == 0.5
        
        # 验证组件使用配置
        assert scraper.session_manager.config.max_concurrent_requests == 5
        assert scraper.session_manager.config.request_timeout == 15
    
    @pytest.mark.asyncio
    async def test_memory_management_integration(self):
        """测试内存管理集成"""
        scraper = MercariScraper(strategy=ScrapingStrategy.REQUESTS)
        
        # 模拟大量数据
        large_html = "<html><body>" + "x" * 1000000 + "</body></html>"  # 1MB HTML
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=large_html)
        
        with patch.object(scraper.session_manager, 'make_request', return_value=mock_response), \
             patch.object(scraper.anti_bot_handler, 'detect_bot_protection') as mock_detect:
            
            # 配置模拟
            mock_detect_result = MagicMock()
            mock_detect_result.is_detected = False
            mock_detect.return_value = mock_detect_result
            
            # 执行多个请求
            for i in range(10):
                result = await scraper.scrape_page(f"https://jp.mercari.com/item/{i}")
                assert result.success is True
            
            # 验证内存没有泄漏（通过成功完成所有请求来验证）
            assert scraper.total_requests == 10
            assert scraper.successful_requests == 10
    
    @pytest.mark.asyncio
    async def test_concurrent_scraping_integration(self):
        """测试并发爬取集成"""
        scraper = MercariScraper(strategy=ScrapingStrategy.REQUESTS)
        
        # 模拟不同的商品页面
        def create_product_html(product_id):
            return f"""
            <html>
                <body>
                    <div data-testid="product-detail">
                        <h1 data-testid="product-name">Product {product_id}</h1>
                        <div data-testid="product-price">¥{product_id * 1000}</div>
                        <div data-testid="product-description">Description {product_id}</div>
                    </div>
                </body>
            </html>
            """
        
        # 模拟HTTP响应
        async def mock_request(url, **kwargs):
            # 从URL提取产品ID
            product_id = url.split('/')[-1]
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value=create_product_html(product_id))
            return mock_response
        
        with patch.object(scraper.session_manager, 'make_request', side_effect=mock_request), \
             patch.object(scraper.anti_bot_handler, 'detect_bot_protection') as mock_detect, \
             patch('asyncio.sleep'):  # 跳过延迟
            
            # 配置模拟
            mock_detect_result = MagicMock()
            mock_detect_result.is_detected = False
            mock_detect.return_value = mock_detect_result
            
            # 并发爬取
            urls = [f"https://jp.mercari.com/item/{i}" for i in range(1, 21)]
            
            # 使用asyncio.gather进行并发处理
            tasks = []
            for url in urls:
                task = scraper.scrape_page(url)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 验证并发结果
            successful_results = [r for r in results if hasattr(r, 'success') and r.success]
            assert len(successful_results) == 20
            
            # 验证统计信息
            assert scraper.total_requests == 20
            assert scraper.successful_requests == 20
            assert scraper.failed_requests == 0


class TestEndToEndScenarios:
    """端到端测试场景"""
    
    @pytest.mark.asyncio
    async def test_real_world_search_scenario(self):
        """测试真实世界搜索场景"""
        scraper = MercariScraper(strategy=ScrapingStrategy.REQUESTS)
        
        # 模拟真实搜索场景的HTML
        search_html = """
        <html>
            <body>
                <div data-testid="search-results-count">1,234件の商品</div>
                <div data-testid="search-item">
                    <h3 data-testid="product-name">iPhone 12 Pro 128GB ゴールド</h3>
                    <span data-testid="product-price">¥78,000</span>
                    <a data-testid="product-link" href="/item/m12345678">Link</a>
                    <img data-testid="product-image" src="https://static.mercdn.net/item/detail/orig/photos/m12345678_1.jpg">
                    <span data-testid="product-condition">目立った傷や汚れなし</span>
                    <span data-testid="seller-name">良品堂</span>
                    <span data-testid="shipping-cost">¥300</span>
                    <span data-testid="like-count">23</span>
                </div>
                <div data-testid="search-item">
                    <h3 data-testid="product-name">iPhone 12 Pro 256GB シルバー</h3>
                    <span data-testid="product-price">¥85,000</span>
                    <a data-testid="product-link" href="/item/m87654321">Link</a>
                    <img data-testid="product-image" src="https://static.mercdn.net/item/detail/orig/photos/m87654321_1.jpg">
                    <span data-testid="product-condition">新品・未使用</span>
                    <span data-testid="seller-name">スマホショップ太郎</span>
                    <span data-testid="shipping-cost">¥500</span>
                    <span data-testid="like-count">45</span>
                </div>
                <div data-testid="pagination">
                    <span data-testid="current-page">1</span>
                    <span data-testid="total-pages">21</span>
                    <button data-testid="next-page">次へ</button>
                </div>
            </body>
        </html>
        """
        
        # 模拟HTTP响应
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=search_html)
        
        with patch.object(scraper.session_manager, 'make_request', return_value=mock_response), \
             patch.object(scraper.anti_bot_handler, 'detect_bot_protection') as mock_detect:
            
            # 配置模拟
            mock_detect_result = MagicMock()
            mock_detect_result.is_detected = False
            mock_detect.return_value = mock_detect_result
            
            # 执行搜索
            filters = SearchFilters(
                keywords="iPhone 12 Pro",
                price_min=50000,
                price_max=100000,
                condition="新品・未使用"
            )
            
            products = await scraper.search_products(filters, max_pages=1)
            
            # 验证结果
            assert len(products) == 2
            
            # 验证第一个产品
            product1 = products[0]
            assert product1.title == "iPhone 12 Pro 128GB ゴールド"
            assert product1.price == 78000
            assert product1.condition == "目立った傷や汚れなし"
            assert product1.seller_name == "良品堂"
            assert product1.shipping_cost == 300
            assert product1.like_count == 23
            
            # 验证第二个产品
            product2 = products[1]
            assert product2.title == "iPhone 12 Pro 256GB シルバー"
            assert product2.price == 85000
            assert product2.condition == "新品・未使用"
            assert product2.seller_name == "スマホショップ太郎"
            assert product2.shipping_cost == 500
            assert product2.like_count == 45
    
    @pytest.mark.asyncio
    async def test_complex_anti_bot_scenario(self):
        """测试复杂反爬虫场景"""
        scraper = MercariScraper(strategy=ScrapingStrategy.REQUESTS)
        
        # 模拟复杂的反爬虫检测场景
        scenarios = [
            # 第一次请求：Cloudflare检测
            """
            <html>
                <body>
                    <div class="cf-browser-verification">
                        <h1>Checking your browser before accessing...</h1>
                        <p>This process is automatic.</p>
                    </div>
                </body>
            </html>
            """,
            # 第二次请求：CAPTCHA
            """
            <html>
                <body>
                    <div class="g-recaptcha" data-sitekey="test">
                        <div>Please complete the CAPTCHA</div>
                    </div>
                </body>
            </html>
            """,
            # 第三次请求：成功
            """
            <html>
                <body>
                    <div data-testid="search-item">
                        <h3 data-testid="product-name">Successfully Bypassed</h3>
                        <span data-testid="product-price">¥100,000</span>
                        <a data-testid="product-link" href="/item/success">Link</a>
                    </div>
                </body>
            </html>
            """
        ]
        
        # 模拟HTTP响应序列
        mock_responses = []
        for html in scenarios:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value=html)
            mock_responses.append(mock_response)
        
        with patch.object(scraper.session_manager, 'make_request', side_effect=mock_responses), \
             patch.object(scraper.session_manager, 'get_session') as mock_get_session, \
             patch.object(scraper.anti_bot_handler, 'handle_block', side_effect=[scenarios[1], scenarios[2]]):
            
            # 模拟会话
            mock_session_info = MagicMock()
            mock_session_info.session = AsyncMock()
            mock_get_session.return_value = mock_session_info
            
            # 执行搜索
            filters = SearchFilters(keywords="test")
            products = await scraper.search_products(filters, max_pages=1)
            
            # 验证最终成功
            assert len(products) == 1
            assert products[0].title == "Successfully Bypassed"
            assert products[0].price == 100000
            
            # 验证反爬虫处理统计
            assert scraper.blocked_requests == 2  # Cloudflare + CAPTCHA
            assert scraper.anti_bot_handler.handle_block.call_count == 2
    
    @pytest.mark.asyncio
    async def test_large_scale_scraping_scenario(self):
        """测试大规模爬取场景"""
        scraper = MercariScraper(strategy=ScrapingStrategy.REQUESTS)
        
        # 模拟大规模搜索结果
        def create_search_page(page_num, items_per_page=60):
            items_html = []
            for i in range(items_per_page):
                item_id = (page_num - 1) * items_per_page + i + 1
                items_html.append(f"""
                <div data-testid="search-item">
                    <h3 data-testid="product-name">Product {item_id}</h3>
                    <span data-testid="product-price">¥{item_id * 1000}</span>
                    <a data-testid="product-link" href="/item/m{item_id:08d}">Link</a>
                    <img data-testid="product-image" src="https://example.com/image{item_id}.jpg">
                    <span data-testid="product-condition">良い</span>
                    <span data-testid="seller-name">Seller{item_id}</span>
                </div>
                """)
            
            has_next = page_num < 5  # 总共5页
            next_button = '<button data-testid="next-page">次へ</button>' if has_next else ''
            
            return f"""
            <html>
                <body>
                    <div data-testid="search-results-count">300件の商品</div>
                    {''.join(items_html)}
                    <div data-testid="pagination">
                        <span data-testid="current-page">{page_num}</span>
                        <span data-testid="total-pages">5</span>
                        {next_button}
                    </div>
                </body>
            </html>
            """
        
        # 模拟HTTP响应
        def mock_request(url, **kwargs):
            # 从URL参数提取页码
            if "page=" in url:
                page_num = int(url.split("page=")[1].split("&")[0])
            else:
                page_num = 1
            
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value=create_search_page(page_num))
            return mock_response
        
        with patch.object(scraper.session_manager, 'make_request', side_effect=mock_request), \
             patch.object(scraper.anti_bot_handler, 'detect_bot_protection') as mock_detect, \
             patch.object(scraper, '_delay_between_requests'):
            
            # 配置模拟
            mock_detect_result = MagicMock()
            mock_detect_result.is_detected = False
            mock_detect.return_value = mock_detect_result
            
            # 执行大规模搜索
            filters = SearchFilters(keywords="large test")
            products = await scraper.search_products(filters, max_pages=5)
            
            # 验证结果
            assert len(products) == 300  # 5页 × 60项/页
            
            # 验证产品数据
            for i, product in enumerate(products):
                expected_id = i + 1
                assert product.title == f"Product {expected_id}"
                assert product.price == expected_id * 1000
                assert product.seller_name == f"Seller{expected_id}"
            
            # 验证性能统计
            assert scraper.total_requests == 5
            assert scraper.successful_requests == 5
            assert scraper.products_scraped == 300


@pytest.fixture
def mock_session():
    """模拟会话"""
    session = AsyncMock()
    session.get = AsyncMock()
    session.post = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def sample_config():
    """示例配置"""
    return ScraperConfig(
        max_concurrent_requests=10,
        request_timeout=30,
        retry_attempts=3,
        rate_limit_delay=1.0,
        max_retries=3,
        backoff_factor=2.0
    )