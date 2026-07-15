"""
数据解析器测试

该模块包含Mercari数据解析器的单元测试。
测试HTML解析、数据提取、数据清洗等功能。

Author: Mercari AI Agent Team
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from bs4 import BeautifulSoup

from mercari_agent.scrapers.data_parser import (
    DataParser, ParsedData, PageType, ProductParseResult, 
    parse_mercari_page, clean_html_content, extract_product_info
)
from mercari_agent.models.product import ProductData


class TestParseResult:
    """解析结果测试"""
    
    def test_parsed_data_init(self):
        """测试解析数据初始化"""
        product = ProductData(
            title="Test Product",
            price=1000,
            url="https://jp.mercari.com/item/test",
            source="mercari"
        )
        
        parsed = ParsedData(
            products=[product],
            page_type=PageType.SEARCH,
            current_page=1,
            has_next_page=True,
            total_count=100
        )
        
        assert len(parsed.products) == 1
        assert parsed.page_type == PageType.SEARCH
        assert parsed.current_page == 1
        assert parsed.has_next_page is True
        assert parsed.total_count == 100
        assert parsed.success is True
        assert len(parsed.errors) == 0
    
    def test_product_parse_result_init(self):
        """测试商品解析结果初始化"""
        product = ProductData(
            title="Test Product",
            price=1000,
            url="https://jp.mercari.com/item/test",
            source="mercari"
        )
        
        result = ProductParseResult(
            product=product,
            success=True,
            confidence=0.95,
            extracted_fields=["title", "price", "url"]
        )
        
        assert result.product.title == "Test Product"
        assert result.success is True
        assert result.confidence == 0.95
        assert "title" in result.extracted_fields
        assert len(result.errors) == 0


class TestDataParser:
    """数据解析器测试"""
    
    def test_data_parser_init(self):
        """测试数据解析器初始化"""
        parser = DataParser()
        
        assert parser.html_tool is not None
        assert parser.price_tool is not None
        assert parser.text_tool is not None
        assert parser.image_tool is not None
        assert parser.time_tool is not None
        assert parser.validation_tool is not None
        
        assert parser.page_parsers[PageType.SEARCH] is not None
        assert parser.page_parsers[PageType.PRODUCT] is not None
    
    def test_parse_page_search(self):
        """测试解析搜索页面"""
        parser = DataParser()
        
        # 模拟搜索页面HTML
        html = """
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
                <div data-testid="search-item">
                    <h3 data-testid="product-name">iPhone 13</h3>
                    <span data-testid="product-price">¥60,000</span>
                    <a data-testid="product-link" href="/item/test456">Link</a>
                    <img data-testid="product-image" src="https://example.com/image2.jpg">
                </div>
                <div data-testid="pagination">
                    <button data-testid="next-page">次へ</button>
                </div>
            </body>
        </html>
        """
        
        with patch.object(parser, '_detect_page_type', return_value=PageType.SEARCH):
            result = parser.parse_page(html, "https://jp.mercari.com/search")
            
            assert result.success is True
            assert len(result.products) == 2
            assert result.page_type == PageType.SEARCH
            assert result.has_next_page is True
            
            # 检查第一个产品
            product1 = result.products[0]
            assert product1.title == "iPhone 12"
            assert product1.price == 50000
            assert product1.url == "https://jp.mercari.com/item/test123"
            assert product1.condition == "新品・未使用"
            assert product1.seller_name == "TestSeller"
    
    def test_parse_page_product_detail(self):
        """测试解析商品详情页面"""
        parser = DataParser()
        
        # 模拟商品详情页面HTML
        html = """
        <html>
            <body>
                <div data-testid="product-detail">
                    <h1 data-testid="product-name">iPhone 12 Pro Max</h1>
                    <div data-testid="product-price">¥80,000</div>
                    <div data-testid="product-description">
                        <p>iPhone 12 Pro Max in excellent condition.</p>
                        <p>Comes with original box and accessories.</p>
                    </div>
                    <div data-testid="product-images">
                        <img src="https://example.com/image1.jpg" alt="Product image 1">
                        <img src="https://example.com/image2.jpg" alt="Product image 2">
                    </div>
                    <div data-testid="product-condition">未使用に近い</div>
                    <div data-testid="seller-info">
                        <span data-testid="seller-name">ProSeller</span>
                        <span data-testid="seller-rating">4.8</span>
                    </div>
                    <div data-testid="product-specs">
                        <div>Brand: Apple</div>
                        <div>Model: iPhone 12 Pro Max</div>
                        <div>Color: Blue</div>
                        <div>Storage: 256GB</div>
                    </div>
                    <div data-testid="shipping-info">
                        <span data-testid="shipping-cost">¥300</span>
                        <span data-testid="shipping-method">らくらくメルカリ便</span>
                    </div>
                    <div data-testid="listing-date">2024-01-15</div>
                    <div data-testid="view-count">123 views</div>
                    <div data-testid="like-count">45 likes</div>
                </div>
            </body>
        </html>
        """
        
        with patch.object(parser, '_detect_page_type', return_value=PageType.PRODUCT):
            result = parser.parse_page(html, "https://jp.mercari.com/item/test123")
            
            assert result.success is True
            assert len(result.products) == 1
            assert result.page_type == PageType.PRODUCT
            
            product = result.products[0]
            assert product.title == "iPhone 12 Pro Max"
            assert product.price == 80000
            assert product.description is not None
            assert "iPhone 12 Pro Max in excellent condition" in product.description
            assert product.condition == "未使用に近い"
            assert product.seller_name == "ProSeller"
            assert product.seller_rating == 4.8
            assert len(product.images) == 2
            assert product.shipping_cost == 300
            assert product.shipping_method == "らくらくメルカリ便"
            assert product.brand == "Apple"
            assert product.model == "iPhone 12 Pro Max"
            assert product.color == "Blue"
            assert product.storage == "256GB"
            assert product.view_count == 123
            assert product.like_count == 45
    
    def test_parse_page_invalid_html(self):
        """测试解析无效HTML"""
        parser = DataParser()
        
        html = "<html><body>Invalid content</body></html>"
        
        result = parser.parse_page(html, "https://jp.mercari.com/search")
        
        assert result.success is False
        assert len(result.products) == 0
        assert len(result.errors) > 0
    
    def test_parse_page_empty_html(self):
        """测试解析空HTML"""
        parser = DataParser()
        
        html = ""
        
        result = parser.parse_page(html, "https://jp.mercari.com/search")
        
        assert result.success is False
        assert len(result.products) == 0
        assert "Empty HTML content" in result.errors[0]
    
    def test_parse_search_page(self):
        """测试解析搜索页面"""
        parser = DataParser()
        
        html = """
        <html>
            <body>
                <div data-testid="search-item">
                    <h3 data-testid="product-name">Test Product</h3>
                    <span data-testid="product-price">¥1,000</span>
                    <a data-testid="product-link" href="/item/test">Link</a>
                    <img data-testid="product-image" src="https://example.com/image.jpg">
                </div>
                <div data-testid="search-results-count">100件の商品</div>
                <div data-testid="pagination">
                    <span data-testid="current-page">1</span>
                    <button data-testid="next-page">次へ</button>
                </div>
            </body>
        </html>
        """
        
        soup = BeautifulSoup(html, 'html.parser')
        
        result = parser._parse_search_page(soup, "https://jp.mercari.com/search")
        
        assert result.success is True
        assert len(result.products) == 1
        assert result.current_page == 1
        assert result.has_next_page is True
        assert result.total_count == 100
        
        product = result.products[0]
        assert product.title == "Test Product"
        assert product.price == 1000
        assert product.url == "https://jp.mercari.com/item/test"
    
    def test_parse_product_page(self):
        """测试解析商品页面"""
        parser = DataParser()
        
        html = """
        <html>
            <body>
                <div data-testid="product-detail">
                    <h1 data-testid="product-name">Detail Product</h1>
                    <div data-testid="product-price">¥5,000</div>
                    <div data-testid="product-description">Product description</div>
                    <div data-testid="product-condition">良い</div>
                    <div data-testid="seller-info">
                        <span data-testid="seller-name">DetailSeller</span>
                    </div>
                </div>
            </body>
        </html>
        """
        
        soup = BeautifulSoup(html, 'html.parser')
        
        result = parser._parse_product_page(soup, "https://jp.mercari.com/item/test")
        
        assert result.success is True
        assert len(result.products) == 1
        
        product = result.products[0]
        assert product.title == "Detail Product"
        assert product.price == 5000
        assert product.description == "Product description"
        assert product.condition == "良い"
        assert product.seller_name == "DetailSeller"
    
    def test_parse_product_from_search_item(self):
        """测试从搜索项解析商品"""
        parser = DataParser()
        
        html = """
        <div data-testid="search-item">
            <h3 data-testid="product-name">Search Item</h3>
            <span data-testid="product-price">¥2,000</span>
            <a data-testid="product-link" href="/item/search">Link</a>
            <img data-testid="product-image" src="https://example.com/search.jpg">
            <span data-testid="product-condition">やや傷や汚れあり</span>
            <span data-testid="seller-name">SearchSeller</span>
            <span data-testid="shipping-cost">¥500</span>
            <span data-testid="like-count">10</span>
        </div>
        """
        
        soup = BeautifulSoup(html, 'html.parser')
        item = soup.find('div', {'data-testid': 'search-item'})
        
        result = parser._parse_product_from_search_item(item, "https://jp.mercari.com")
        
        assert result.success is True
        assert result.product.title == "Search Item"
        assert result.product.price == 2000
        assert result.product.url == "https://jp.mercari.com/item/search"
        assert result.product.condition == "やや傷や汚れあり"
        assert result.product.seller_name == "SearchSeller"
        assert result.product.shipping_cost == 500
        assert result.product.like_count == 10
    
    def test_parse_product_from_search_item_missing_data(self):
        """测试从搜索项解析商品 - 缺少数据"""
        parser = DataParser()
        
        html = """
        <div data-testid="search-item">
            <h3 data-testid="product-name">Incomplete Item</h3>
            <!-- 缺少价格和其他信息 -->
        </div>
        """
        
        soup = BeautifulSoup(html, 'html.parser')
        item = soup.find('div', {'data-testid': 'search-item'})
        
        result = parser._parse_product_from_search_item(item, "https://jp.mercari.com")
        
        assert result.success is True
        assert result.product.title == "Incomplete Item"
        assert result.product.price is None
        assert result.confidence < 0.5  # 低置信度
        assert len(result.errors) > 0
    
    def test_parse_product_from_detail_page(self):
        """测试从详情页解析商品"""
        parser = DataParser()
        
        html = """
        <div data-testid="product-detail">
            <h1 data-testid="product-name">Detail Page Product</h1>
            <div data-testid="product-price">¥10,000</div>
            <div data-testid="product-description">
                <p>This is a detailed description.</p>
                <p>Multiple paragraphs.</p>
            </div>
            <div data-testid="product-images">
                <img src="https://example.com/detail1.jpg" alt="Image 1">
                <img src="https://example.com/detail2.jpg" alt="Image 2">
                <img src="https://example.com/detail3.jpg" alt="Image 3">
            </div>
            <div data-testid="product-condition">目立った傷や汚れなし</div>
            <div data-testid="seller-info">
                <span data-testid="seller-name">DetailPageSeller</span>
                <span data-testid="seller-rating">4.5</span>
                <span data-testid="seller-reviews">100</span>
            </div>
            <div data-testid="product-specs">
                <div>Brand: TestBrand</div>
                <div>Model: TestModel</div>
                <div>Color: Red</div>
                <div>Size: Large</div>
            </div>
            <div data-testid="shipping-info">
                <span data-testid="shipping-cost">¥400</span>
                <span data-testid="shipping-method">ゆうゆうメルカリ便</span>
                <span data-testid="shipping-days">1-2日で発送</span>
            </div>
            <div data-testid="listing-date">2024-01-20</div>
            <div data-testid="view-count">456 views</div>
            <div data-testid="like-count">78 likes</div>
        </div>
        """
        
        soup = BeautifulSoup(html, 'html.parser')
        detail_div = soup.find('div', {'data-testid': 'product-detail'})
        
        result = parser._parse_product_from_detail_page(detail_div, "https://jp.mercari.com/item/detail")
        
        assert result.success is True
        assert result.product.title == "Detail Page Product"
        assert result.product.price == 10000
        assert "This is a detailed description" in result.product.description
        assert result.product.condition == "目立った傷や汚れなし"
        assert result.product.seller_name == "DetailPageSeller"
        assert result.product.seller_rating == 4.5
        assert result.product.seller_reviews == 100
        assert result.product.brand == "TestBrand"
        assert result.product.model == "TestModel"
        assert result.product.color == "Red"
        assert result.product.size == "Large"
        assert result.product.shipping_cost == 400
        assert result.product.shipping_method == "ゆうゆうメルカリ便"
        assert result.product.shipping_days == "1-2日で発送"
        assert result.product.view_count == 456
        assert result.product.like_count == 78
        assert len(result.product.images) == 3
        assert result.confidence > 0.8  # 高置信度
    
    def test_extract_pagination_info(self):
        """测试提取分页信息"""
        parser = DataParser()
        
        html = """
        <div data-testid="pagination">
            <span data-testid="current-page">2</span>
            <span data-testid="total-pages">10</span>
            <button data-testid="next-page">次へ</button>
            <button data-testid="prev-page">前へ</button>
        </div>
        """
        
        soup = BeautifulSoup(html, 'html.parser')
        pagination = soup.find('div', {'data-testid': 'pagination'})
        
        current_page, has_next, total_pages = parser._extract_pagination_info(pagination)
        
        assert current_page == 2
        assert has_next is True
        assert total_pages == 10
    
    def test_extract_pagination_info_no_next(self):
        """测试提取分页信息 - 没有下一页"""
        parser = DataParser()
        
        html = """
        <div data-testid="pagination">
            <span data-testid="current-page">10</span>
            <span data-testid="total-pages">10</span>
            <button data-testid="prev-page">前へ</button>
        </div>
        """
        
        soup = BeautifulSoup(html, 'html.parser')
        pagination = soup.find('div', {'data-testid': 'pagination'})
        
        current_page, has_next, total_pages = parser._extract_pagination_info(pagination)
        
        assert current_page == 10
        assert has_next is False
        assert total_pages == 10
    
    def test_extract_total_results(self):
        """测试提取总结果数"""
        parser = DataParser()
        
        html = """
        <div data-testid="search-results-count">1,234件の商品</div>
        """
        
        soup = BeautifulSoup(html, 'html.parser')
        
        total = parser._extract_total_results(soup)
        
        assert total == 1234
    
    def test_extract_total_results_no_results(self):
        """测试提取总结果数 - 没有结果"""
        parser = DataParser()
        
        html = """
        <div data-testid="search-results-count">該当する商品がありません</div>
        """
        
        soup = BeautifulSoup(html, 'html.parser')
        
        total = parser._extract_total_results(soup)
        
        assert total == 0
    
    def test_detect_page_type_search(self):
        """测试检测页面类型 - 搜索页"""
        parser = DataParser()
        
        html = """
        <html>
            <body>
                <div data-testid="search-item">Item 1</div>
                <div data-testid="search-item">Item 2</div>
                <div data-testid="pagination">Pagination</div>
            </body>
        </html>
        """
        
        soup = BeautifulSoup(html, 'html.parser')
        page_type = parser._detect_page_type(soup, "https://jp.mercari.com/search")
        
        assert page_type == PageType.SEARCH
    
    def test_detect_page_type_product(self):
        """测试检测页面类型 - 商品页"""
        parser = DataParser()
        
        html = """
        <html>
            <body>
                <div data-testid="product-detail">Product detail</div>
            </body>
        </html>
        """
        
        soup = BeautifulSoup(html, 'html.parser')
        page_type = parser._detect_page_type(soup, "https://jp.mercari.com/item/test123")
        
        assert page_type == PageType.PRODUCT
    
    def test_detect_page_type_unknown(self):
        """测试检测页面类型 - 未知页面"""
        parser = DataParser()
        
        html = """
        <html>
            <body>
                <div>Unknown content</div>
            </body>
        </html>
        """
        
        soup = BeautifulSoup(html, 'html.parser')
        page_type = parser._detect_page_type(soup, "https://jp.mercari.com/unknown")
        
        assert page_type == PageType.UNKNOWN
    
    def test_clean_product_data(self):
        """测试清洗商品数据"""
        parser = DataParser()
        
        product = ProductData(
            title="  iPhone 12  ",
            price=50000,
            url="https://jp.mercari.com/item/test",
            description="  Great condition phone.  \n\n  ",
            condition="新品・未使用",
            seller_name="  TestSeller  ",
            images=["https://example.com/image1.jpg", "", "https://example.com/image2.jpg"],
            tags=["smartphone", "", "apple", "smartphone"],  # 重复和空标签
            source="mercari"
        )
        
        cleaned = parser.clean_product_data(product)
        
        assert cleaned.title == "iPhone 12"
        assert cleaned.description == "Great condition phone."
        assert cleaned.seller_name == "TestSeller"
        assert len(cleaned.images) == 2
        assert "" not in cleaned.images
        assert len(cleaned.tags) == 2  # 去重后
        assert "smartphone" in cleaned.tags
        assert "apple" in cleaned.tags
    
    def test_validate_product_data(self):
        """测试验证商品数据"""
        parser = DataParser()
        
        # 有效商品
        valid_product = ProductData(
            title="iPhone 12",
            price=50000,
            url="https://jp.mercari.com/item/test",
            source="mercari"
        )
        
        is_valid, errors = parser.validate_product_data(valid_product)
        
        assert is_valid is True
        assert len(errors) == 0
        
        # 无效商品
        invalid_product = ProductData(
            title="",  # 空标题
            price=-1000,  # 负价格
            url="invalid-url",  # 无效URL
            source="mercari"
        )
        
        is_valid, errors = parser.validate_product_data(invalid_product)
        
        assert is_valid is False
        assert len(errors) > 0
        assert any("title" in error for error in errors)
        assert any("price" in error for error in errors)
        assert any("url" in error for error in errors)
    
    def test_get_parser_stats(self):
        """测试获取解析器统计"""
        parser = DataParser()
        
        # 模拟一些统计数据
        parser.pages_parsed = 100
        parser.products_extracted = 500
        parser.parse_errors = 5
        
        stats = parser.get_parser_stats()
        
        assert stats["pages_parsed"] == 100
        assert stats["products_extracted"] == 500
        assert stats["parse_errors"] == 5
        assert stats["success_rate"] == 95.0
        assert stats["average_products_per_page"] == 5.0


class TestConvenienceFunctions:
    """便捷函数测试"""
    
    def test_parse_mercari_page(self):
        """测试解析Mercari页面"""
        html = """
        <html>
            <body>
                <div data-testid="search-item">
                    <h3 data-testid="product-name">Function Test</h3>
                    <span data-testid="product-price">¥3,000</span>
                    <a data-testid="product-link" href="/item/func">Link</a>
                </div>
            </body>
        </html>
        """
        
        with patch('mercari_agent.scrapers.data_parser.DataParser') as mock_parser_class:
            mock_parser = MagicMock()
            mock_parser_class.return_value = mock_parser
            
            # 配置模拟返回
            mock_result = ParsedData(
                products=[ProductData(title="Function Test", price=3000, url="https://jp.mercari.com/item/func", source="mercari")],
                page_type=PageType.SEARCH,
                current_page=1,
                has_next_page=False,
                total_count=1
            )
            mock_parser.parse_page.return_value = mock_result
            
            result = parse_mercari_page(html, "https://jp.mercari.com/search")
            
            assert result.success is True
            assert len(result.products) == 1
            assert result.products[0].title == "Function Test"
    
    def test_clean_html_content(self):
        """测试清洗HTML内容"""
        html = """
        <html>
            <head>
                <title>Test</title>
                <script>alert('test');</script>
                <style>body { color: red; }</style>
            </head>
            <body>
                <div>Clean content</div>
                <script>malicious code</script>
            </body>
        </html>
        """
        
        cleaned = clean_html_content(html)
        
        assert "Clean content" in cleaned
        assert "alert('test')" not in cleaned
        assert "malicious code" not in cleaned
        assert "color: red" not in cleaned
    
    def test_extract_product_info(self):
        """测试提取商品信息"""
        html = """
        <div data-testid="search-item">
            <h3 data-testid="product-name">Extract Test</h3>
            <span data-testid="product-price">¥4,000</span>
            <a data-testid="product-link" href="/item/extract">Link</a>
        </div>
        """
        
        soup = BeautifulSoup(html, 'html.parser')
        item = soup.find('div', {'data-testid': 'search-item'})
        
        with patch('mercari_agent.scrapers.data_parser.DataParser') as mock_parser_class:
            mock_parser = MagicMock()
            mock_parser_class.return_value = mock_parser
            
            mock_result = ProductParseResult(
                product=ProductData(title="Extract Test", price=4000, url="https://jp.mercari.com/item/extract", source="mercari"),
                success=True,
                confidence=0.9,
                extracted_fields=["title", "price", "url"]
            )
            mock_parser._parse_product_from_search_item.return_value = mock_result
            
            result = extract_product_info(item, "https://jp.mercari.com")
            
            assert result.success is True
            assert result.product.title == "Extract Test"
            assert result.confidence == 0.9


@pytest.fixture
def sample_search_html():
    """示例搜索页面HTML"""
    return """
    <html>
        <body>
            <div data-testid="search-item">
                <h3 data-testid="product-name">Sample Product 1</h3>
                <span data-testid="product-price">¥1,000</span>
                <a data-testid="product-link" href="/item/sample1">Link</a>
                <img data-testid="product-image" src="https://example.com/sample1.jpg">
            </div>
            <div data-testid="search-item">
                <h3 data-testid="product-name">Sample Product 2</h3>
                <span data-testid="product-price">¥2,000</span>
                <a data-testid="product-link" href="/item/sample2">Link</a>
                <img data-testid="product-image" src="https://example.com/sample2.jpg">
            </div>
            <div data-testid="pagination">
                <span data-testid="current-page">1</span>
                <button data-testid="next-page">次へ</button>
            </div>
        </body>
    </html>
    """


@pytest.fixture
def sample_product_html():
    """示例商品详情页面HTML"""
    return """
    <html>
        <body>
            <div data-testid="product-detail">
                <h1 data-testid="product-name">Sample Detail Product</h1>
                <div data-testid="product-price">¥5,000</div>
                <div data-testid="product-description">Sample description</div>
                <div data-testid="product-condition">良い</div>
                <div data-testid="seller-info">
                    <span data-testid="seller-name">SampleSeller</span>
                    <span data-testid="seller-rating">4.5</span>
                </div>
                <div data-testid="product-images">
                    <img src="https://example.com/detail1.jpg" alt="Image 1">
                    <img src="https://example.com/detail2.jpg" alt="Image 2">
                </div>
            </div>
        </body>
    </html>
    """