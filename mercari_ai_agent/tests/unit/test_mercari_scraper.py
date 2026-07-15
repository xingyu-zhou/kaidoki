"""
Mercari爬虫测试

该模块包含Mercari爬虫的单元测试。
测试商品搜索、详情页爬取、反爬虫处理等功能。

Author: Mercari AI Agent Team
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import aiohttp
from bs4 import BeautifulSoup

from mercari_agent.scrapers.mercari_scraper import (
    MercariScraper, MercariScrapingResult, SearchFilters, SearchSortOrder,
    create_mercari_scraper, quick_search, get_product_detail
)
from mercari_agent.scrapers.base_scraper import ScrapingStrategy
from mercari_agent.models.product import ProductData


class TestSearchFilters:
    """搜索过滤器测试"""
    
    def test_search_filters_init(self):
        """测试搜索过滤器初始化"""
        filters = SearchFilters(keywords="iPhone")
        
        assert filters.keywords == "iPhone"
        assert filters.category_id is None
        assert filters.price_min is None
        assert filters.price_max is None
        assert filters.sort_order == SearchSortOrder.RELEVANCE
        assert filters.page == 1
        assert filters.limit == 60
    
    def test_search_filters_to_params(self):
        """测试转换为URL参数"""
        filters = SearchFilters(
            keywords="iPhone",
            category_id=1,
            price_min=1000,
            price_max=50000,
            sort_order=SearchSortOrder.PRICE_LOW,
            page=2,
            limit=40
        )
        
        params = filters.to_params()
        
        assert params["keyword"] == "iPhone"
        assert params["category_id"] == 1
        assert params["price_min"] == 1000
        assert params["price_max"] == 50000
        assert params["sort"] == "price_low"
        assert params["page"] == 2
        assert params["limit"] == 40


class TestMercariScrapingResult:
    """Mercari爬虫结果测试"""
    
    def test_mercari_scraping_result_init(self):
        """测试Mercari爬虫结果初始化"""
        product = ProductData(
            title="Test Product",
            price=1000,
            url="https://jp.mercari.com/item/test123",
            source="mercari"
        )
        
        result = MercariScrapingResult(
            products=[product],
            success=True,
            page_number=1,
            has_next_page=True,
            total_results=100,
            search_query="test"
        )
        
        assert len(result.products) == 1
        assert result.success is True
        assert result.page_number == 1
        assert result.has_next_page is True
        assert result.total_results == 100
        assert result.search_query == "test"


class TestMercariScraper:
    """Mercari爬虫测试"""
    
    def test_mercari_scraper_init(self):
        """测试Mercari爬虫初始化"""
        scraper = MercariScraper(strategy=ScrapingStrategy.REQUESTS)
        
        assert scraper.config.strategy == ScrapingStrategy.REQUESTS
        assert scraper.base_url == "https://jp.mercari.com"
        assert scraper.search_url == "https://jp.mercari.com/search"
        assert scraper.session_manager is not None
        assert scraper.anti_bot_handler is not None
        assert scraper.data_parser is not None
        assert scraper.total_requests == 0
        assert scraper.successful_requests == 0
        assert scraper.failed_requests == 0
    
    @pytest.mark.asyncio
    async def test_mercari_scraper_initialize(self):
        """测试爬虫初始化"""
        scraper = MercariScraper()
        
        with patch.object(scraper.session_manager, 'initialize') as mock_init:
            await scraper.initialize()
            mock_init.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_mercari_scraper_scrape_page_success(self):
        """测试成功爬取页面"""
        scraper = MercariScraper()
        
        # 模拟HTML内容
        html_content = """
        <html>
            <body>
                <div data-testid="search-item">
                    <h3 data-testid="product-name">iPhone 12</h3>
                    <span data-testid="product-price">¥50,000</span>
                    <a data-testid="product-link" href="/item/test123">Link</a>
                    <img data-testid="product-image" src="https://example.com/image.jpg">
                </div>
            </body>
        </html>
        """
        
        # 模拟响应
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=html_content)
        
        # 模拟组件
        with patch.object(scraper.session_manager, 'make_request', return_value=mock_response), \
             patch.object(scraper.anti_bot_handler, 'detect_bot_protection') as mock_detect, \
             patch.object(scraper.data_parser, 'parse_page') as mock_parse:
            
            # 配置模拟
            mock_detect.return_value.is_detected = False
            
            product = ProductData(
                title="iPhone 12",
                price=50000,
                url="https://jp.mercari.com/item/test123",
                source="mercari"
            )
            
            mock_parse_result = MagicMock()
            mock_parse_result.products = [product]
            mock_parse_result.current_page = 1
            mock_parse_result.has_next_page = False
            mock_parse_result.total_count = 1
            mock_parse_result.errors = []
            mock_parse_result.metadata = {}
            
            mock_parse.return_value = mock_parse_result
            
            with patch.object(scraper.validation_tool, 'validate_product_data', return_value=(True, [])), \
                 patch.object(scraper.data_parser, 'clean_product_data', return_value=product):
                
                result = await scraper.scrape_page("https://jp.mercari.com/search?keyword=iPhone")
                
                assert result.success is True
                assert len(result.products) == 1
                assert result.products[0].title == "iPhone 12"
                assert scraper.total_requests == 1
                assert scraper.successful_requests == 1
    
    @pytest.mark.asyncio
    async def test_mercari_scraper_scrape_page_with_antibot(self):
        """测试带反爬虫检测的页面爬取"""
        scraper = MercariScraper()
        
        # 模拟响应
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="<html>Bot detected</html>")
        
        with patch.object(scraper.session_manager, 'make_request', return_value=mock_response), \
             patch.object(scraper.anti_bot_handler, 'detect_bot_protection') as mock_detect, \
             patch.object(scraper.session_manager, 'get_session') as mock_get_session, \
             patch.object(scraper.anti_bot_handler, 'handle_block') as mock_handle:
            
            # 配置反爬虫检测
            mock_detect.return_value.is_detected = True
            mock_detect.return_value.detection_type = "captcha"
            
            # 模拟会话
            mock_session_info = MagicMock()
            mock_session_info.session = AsyncMock()
            mock_get_session.return_value = mock_session_info
            
            # 模拟反爬虫处理
            mock_handle.return_value = "<html>Success</html>"
            
            with patch.object(scraper.data_parser, 'parse_page') as mock_parse:
                mock_parse_result = MagicMock()
                mock_parse_result.products = []
                mock_parse_result.errors = []
                mock_parse_result.metadata = {}
                mock_parse.return_value = mock_parse_result
                
                result = await scraper.scrape_page("https://jp.mercari.com/search")
                
                # 验证反爬虫处理被调用
                mock_handle.assert_called_once()
                assert scraper.blocked_requests == 1
    
    @pytest.mark.asyncio
    async def test_mercari_scraper_scrape_page_error(self):
        """测试页面爬取错误"""
        scraper = MercariScraper()
        
        with patch.object(scraper.session_manager, 'make_request', side_effect=Exception("Network error")):
            result = await scraper.scrape_page("https://jp.mercari.com/search")
            
            assert result.success is False
            assert "Network error" in result.error_message
            assert scraper.failed_requests == 1
    
    @pytest.mark.asyncio
    async def test_mercari_scraper_search_products(self):
        """测试搜索商品"""
        scraper = MercariScraper()
        
        # 模拟搜索结果
        product1 = ProductData(title="iPhone 12", price=50000, url="https://jp.mercari.com/item/1", source="mercari")
        product2 = ProductData(title="iPhone 13", price=60000, url="https://jp.mercari.com/item/2", source="mercari")
        
        result1 = MercariScrapingResult(products=[product1], success=True, has_next_page=True)
        result2 = MercariScrapingResult(products=[product2], success=True, has_next_page=False)
        
        with patch.object(scraper, 'scrape_page', side_effect=[result1, result2]), \
             patch.object(scraper, '_delay_between_requests'):
            
            filters = SearchFilters(keywords="iPhone")
            products = await scraper.search_products(filters, max_pages=2)
            
            assert len(products) == 2
            assert products[0].title == "iPhone 12"
            assert products[1].title == "iPhone 13"
    
    @pytest.mark.asyncio
    async def test_mercari_scraper_search_products_error(self):
        """测试搜索商品错误"""
        scraper = MercariScraper()
        
        # 模拟失败的搜索结果
        result = MercariScrapingResult(products=[], success=False, error_message="Search failed")
        
        with patch.object(scraper, 'scrape_page', return_value=result):
            filters = SearchFilters(keywords="iPhone")
            products = await scraper.search_products(filters)
            
            assert len(products) == 0
    
    @pytest.mark.asyncio
    async def test_mercari_scraper_scrape_product_detail(self):
        """测试爬取商品详情"""
        scraper = MercariScraper()
        
        # 模拟详情页面数据
        product = ProductData(
            title="iPhone 12 Pro",
            price=80000,
            url="https://jp.mercari.com/item/test123",
            description="Like new iPhone 12 Pro",
            condition="未使用に近い",
            source="mercari"
        )
        
        result = MercariScrapingResult(products=[product], success=True)
        
        with patch.object(scraper.url_tool, 'is_mercari_url', return_value=True), \
             patch.object(scraper, 'scrape_page', return_value=result), \
             patch.object(scraper, '_enrich_product_detail', return_value=product):
            
            detailed_product = await scraper.scrape_product_detail(
                "https://jp.mercari.com/item/test123"
            )
            
            assert detailed_product is not None
            assert detailed_product.title == "iPhone 12 Pro"
            assert detailed_product.description == "Like new iPhone 12 Pro"
    
    @pytest.mark.asyncio
    async def test_mercari_scraper_scrape_product_detail_invalid_url(self):
        """测试爬取商品详情 - 无效URL"""
        scraper = MercariScraper()
        
        with patch.object(scraper.url_tool, 'is_mercari_url', return_value=False):
            result = await scraper.scrape_product_detail("https://invalid.com/item/123")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_mercari_scraper_scrape_category(self):
        """测试爬取分类商品"""
        scraper = MercariScraper()
        
        product = ProductData(title="Category Product", price=1000, url="https://jp.mercari.com/item/cat1", source="mercari")
        
        with patch.object(scraper, 'search_products', return_value=[product]):
            products = await scraper.scrape_category(category_id=1)
            
            assert len(products) == 1
            assert products[0].title == "Category Product"
    
    @pytest.mark.asyncio
    async def test_mercari_scraper_scrape_seller_products(self):
        """测试爬取卖家商品"""
        scraper = MercariScraper()
        
        product = ProductData(title="Seller Product", price=2000, url="https://jp.mercari.com/item/seller1", source="mercari")
        result = MercariScrapingResult(products=[product], success=True)
        
        with patch.object(scraper, 'scrape_page', return_value=result):
            products = await scraper.scrape_seller_products(seller_id="12345")
            
            assert len(products) == 1
            assert products[0].title == "Seller Product"
    
    @pytest.mark.asyncio
    async def test_mercari_scraper_batch_scrape_products(self):
        """测试批量爬取商品"""
        scraper = MercariScraper()
        
        product1 = ProductData(title="Product 1", price=1000, url="https://jp.mercari.com/item/1", source="mercari")
        product2 = ProductData(title="Product 2", price=2000, url="https://jp.mercari.com/item/2", source="mercari")
        
        urls = [
            "https://jp.mercari.com/item/1",
            "https://jp.mercari.com/item/2"
        ]
        
        with patch.object(scraper, 'scrape_product_detail', side_effect=[product1, product2]), \
             patch('asyncio.sleep'):
            
            products = await scraper.batch_scrape_products(urls, batch_size=2)
            
            assert len(products) == 2
            assert products[0].title == "Product 1"
            assert products[1].title == "Product 2"
    
    @pytest.mark.asyncio
    async def test_mercari_scraper_batch_scrape_products_with_errors(self):
        """测试批量爬取商品 - 带错误"""
        scraper = MercariScraper()
        
        product1 = ProductData(title="Product 1", price=1000, url="https://jp.mercari.com/item/1", source="mercari")
        
        urls = [
            "https://jp.mercari.com/item/1",
            "https://jp.mercari.com/item/2"
        ]
        
        with patch.object(scraper, 'scrape_product_detail', side_effect=[product1, Exception("Error")]), \
             patch('asyncio.sleep'):
            
            products = await scraper.batch_scrape_products(urls, batch_size=2)
            
            assert len(products) == 1
            assert products[0].title == "Product 1"
    
    def test_mercari_scraper_build_search_url(self):
        """测试构建搜索URL"""
        scraper = MercariScraper()
        
        filters = SearchFilters(
            keywords="iPhone",
            category_id=1,
            price_min=1000,
            price_max=50000
        )
        
        url = scraper._build_search_url(filters)
        
        assert "jp.mercari.com/search" in url
        assert "keyword=iPhone" in url
        assert "category_id=1" in url
        assert "price_min=1000" in url
        assert "price_max=50000" in url
    
    @pytest.mark.asyncio
    async def test_mercari_scraper_enrich_product_detail(self):
        """测试丰富商品详情"""
        scraper = MercariScraper()
        
        product = ProductData(
            title="iPhone 12",
            price=50000,
            url="https://jp.mercari.com/item/test123",
            images=["https://example.com/image1.jpg", "https://example.com/image2.jpg"],
            condition="新品・未使用",
            source="mercari"
        )
        
        with patch.object(scraper.image_tool, 'filter_valid_images', return_value=product.images), \
             patch.object(scraper.image_tool, 'sort_images_by_quality', return_value=product.images), \
             patch.object(scraper.time_tool, 'parse_japanese_date', return_value=None):
            
            enriched = await scraper._enrich_product_detail(product)
            
            assert enriched.title == "iPhone 12"
            assert "high_quality" in enriched.tags
            assert "new_condition" in enriched.tags
    
    @pytest.mark.asyncio
    async def test_mercari_scraper_health_check(self):
        """测试健康检查"""
        scraper = MercariScraper()
        
        # 设置一些统计数据
        scraper.total_requests = 100
        scraper.successful_requests = 90
        scraper.failed_requests = 5
        scraper.blocked_requests = 3
        scraper.products_scraped = 50
        
        with patch.object(scraper.session_manager, 'health_check', return_value={"status": "healthy"}), \
             patch.object(scraper.anti_bot_handler, 'get_stats', return_value={"detection_count": 10}), \
             patch.object(scraper.data_parser, 'get_parser_stats', return_value={"parsed_pages": 20}):
            
            health = await scraper.health_check()
            
            assert health["scraper_status"] == "healthy"
            assert health["total_requests"] == 100
            assert health["successful_requests"] == 90
            assert health["success_rate"] == 90.0
            assert health["products_scraped"] == 50
    
    @pytest.mark.asyncio
    async def test_mercari_scraper_get_popular_searches(self):
        """测试获取热门搜索"""
        scraper = MercariScraper()
        
        result = MercariScrapingResult(products=[], success=True)
        
        with patch.object(scraper, 'scrape_page', return_value=result):
            popular_searches = await scraper.get_popular_searches()
            
            assert isinstance(popular_searches, list)
            assert len(popular_searches) > 0
            assert "iPhone" in popular_searches
    
    @pytest.mark.asyncio
    async def test_mercari_scraper_get_trending_categories(self):
        """测试获取热门分类"""
        scraper = MercariScraper()
        
        with patch.object(scraper, 'search_products', return_value=[ProductData(title="Test", source="mercari")]):
            categories = await scraper.get_trending_categories()
            
            assert isinstance(categories, list)
            assert len(categories) > 0
            
            # 验证返回的分类结构
            if categories:
                category = categories[0]
                assert "name" in category
                assert "id" in category
                assert "product_count" in category
                assert "url" in category
    
    @pytest.mark.asyncio
    async def test_mercari_scraper_close(self):
        """测试关闭爬虫"""
        scraper = MercariScraper()
        
        with patch.object(scraper.session_manager, 'close_all') as mock_close_all, \
             patch.object(scraper, '__del__', create=True):
            
            await scraper.close()
            mock_close_all.assert_called_once()
    
    def test_mercari_scraper_get_scraper_stats(self):
        """测试获取爬虫统计信息"""
        scraper = MercariScraper()
        
        # 设置统计数据
        scraper.total_requests = 100
        scraper.successful_requests = 95
        scraper.products_scraped = 50
        
        with patch.object(scraper.session_manager, 'get_stats', return_value={"sessions": 5}), \
             patch.object(scraper.anti_bot_handler, 'get_stats', return_value={"detections": 10}), \
             patch.object(scraper.data_parser, 'get_parser_stats', return_value={"parsed": 20}):
            
            stats = scraper.get_scraper_stats()
            
            assert stats["scraper_info"]["strategy"] == "requests"
            assert stats["scraper_info"]["base_url"] == "https://jp.mercari.com"
            assert stats["performance"]["total_requests"] == 100
            assert stats["performance"]["successful_requests"] == 95
            assert stats["performance"]["success_rate"] == 95.0
            assert stats["performance"]["products_scraped"] == 50


class TestConvenienceFunctions:
    """便捷函数测试"""
    
    @pytest.mark.asyncio
    async def test_create_mercari_scraper(self):
        """测试创建Mercari爬虫"""
        with patch.object(MercariScraper, 'initialize') as mock_init:
            scraper = await create_mercari_scraper(strategy=ScrapingStrategy.REQUESTS)
            
            assert isinstance(scraper, MercariScraper)
            mock_init.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_quick_search(self):
        """测试快速搜索"""
        product = ProductData(title="Quick Product", price=1000, url="https://jp.mercari.com/item/quick", source="mercari")
        
        with patch('mercari_agent.scrapers.mercari_scraper.create_mercari_scraper') as mock_create:
            mock_scraper = AsyncMock()
            mock_scraper.search_products.return_value = [product]
            mock_scraper.close = AsyncMock()
            mock_create.return_value = mock_scraper
            
            results = await quick_search("iPhone", max_pages=1)
            
            assert len(results) == 1
            assert results[0].title == "Quick Product"
            mock_scraper.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_product_detail(self):
        """测试获取商品详情"""
        product = ProductData(
            title="Detail Product",
            price=5000,
            url="https://jp.mercari.com/item/detail",
            description="Detailed description",
            source="mercari"
        )
        
        with patch('mercari_agent.scrapers.mercari_scraper.create_mercari_scraper') as mock_create:
            mock_scraper = AsyncMock()
            mock_scraper.scrape_product_detail.return_value = product
            mock_scraper.close = AsyncMock()
            mock_create.return_value = mock_scraper
            
            result = await get_product_detail("https://jp.mercari.com/item/detail")
            
            assert result is not None
            assert result.title == "Detail Product"
            assert result.description == "Detailed description"
            mock_scraper.close.assert_called_once()


@pytest.fixture
def sample_html():
    """示例HTML内容"""
    return """
    <html>
        <body>
            <div data-testid="search-item">
                <h3 data-testid="product-name">iPhone 12</h3>
                <span data-testid="product-price">¥50,000</span>
                <a data-testid="product-link" href="/item/test123">Link</a>
                <img data-testid="product-image" src="https://example.com/image.jpg">
                <span data-testid="product-condition">新品・未使用</span>
                <span data-testid="seller-name">TestSeller</span>
            </div>
        </body>
    </html>
    """


@pytest.fixture
def sample_product():
    """示例产品数据"""
    return ProductData(
        title="iPhone 12",
        price=50000,
        url="https://jp.mercari.com/item/test123",
        condition="新品・未使用",
        seller_name="TestSeller",
        images=["https://example.com/image.jpg"],
        source="mercari"
    )