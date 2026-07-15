"""
爬虫工具集测试

该模块包含爬虫工具集的单元测试。
测试HTML选择器、价格解析、文本处理、图片处理、URL工具、数据验证、时间解析等功能。

Author: Mercari AI Agent Team
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from PIL import Image

from mercari_agent.scrapers.scraper_utils import (
    HTMLSelectorTool, PriceParsingTool, TextProcessingTool,
    ImageProcessingTool, URLTool, DataValidationTool, TimeParsingTool
)
from mercari_agent.models.product import ProductData


class TestHTMLSelectorTool:
    """HTML选择器工具测试"""
    
    def test_html_selector_tool_init(self):
        """测试HTML选择器工具初始化"""
        tool = HTMLSelectorTool()
        
        assert tool.selectors is not None
        assert "search_items" in tool.selectors
        assert "product_name" in tool.selectors
        assert "product_price" in tool.selectors
    
    def test_find_element_by_selector(self):
        """测试通过选择器查找元素"""
        tool = HTMLSelectorTool()
        
        html = """
        <div data-testid="product-name">iPhone 12</div>
        <div class="price">¥50,000</div>
        <div id="description">Great phone</div>
        """
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # 测试data-testid选择器
        element = tool.find_element_by_selector(soup, "product_name")
        assert element is not None
        assert element.get_text() == "iPhone 12"
        
        # 测试自定义选择器
        element = tool.find_element_by_selector(soup, "custom", selector=".price")
        assert element is not None
        assert element.get_text() == "¥50,000"
    
    def test_find_elements_by_selector(self):
        """测试通过选择器查找多个元素"""
        tool = HTMLSelectorTool()
        
        html = """
        <div data-testid="search-item">Item 1</div>
        <div data-testid="search-item">Item 2</div>
        <div data-testid="search-item">Item 3</div>
        """
        
        soup = BeautifulSoup(html, 'html.parser')
        
        elements = tool.find_elements_by_selector(soup, "search_items")
        assert len(elements) == 3
        assert elements[0].get_text() == "Item 1"
        assert elements[1].get_text() == "Item 2"
        assert elements[2].get_text() == "Item 3"
    
    def test_extract_text_safe(self):
        """测试安全文本提取"""
        tool = HTMLSelectorTool()
        
        html = """
        <div>  Normal text  </div>
        <div><span>Nested</span> text</div>
        <div></div>
        """
        
        soup = BeautifulSoup(html, 'html.parser')
        elements = soup.find_all('div')
        
        # 正常文本
        text = tool.extract_text_safe(elements[0])
        assert text == "Normal text"
        
        # 嵌套文本
        text = tool.extract_text_safe(elements[1])
        assert text == "Nested text"
        
        # 空元素
        text = tool.extract_text_safe(elements[2])
        assert text == ""
        
        # None元素
        text = tool.extract_text_safe(None)
        assert text == ""
    
    def test_extract_attribute_safe(self):
        """测试安全属性提取"""
        tool = HTMLSelectorTool()
        
        html = """
        <a href="/item/123" data-id="456">Link</a>
        <img src="image.jpg" alt="Image">
        <div>No attributes</div>
        """
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # 提取href属性
        link = soup.find('a')
        href = tool.extract_attribute_safe(link, 'href')
        assert href == "/item/123"
        
        # 提取data属性
        data_id = tool.extract_attribute_safe(link, 'data-id')
        assert data_id == "456"
        
        # 提取不存在的属性
        title = tool.extract_attribute_safe(link, 'title')
        assert title == ""
        
        # None元素
        attr = tool.extract_attribute_safe(None, 'href')
        assert attr == ""
    
    def test_has_class(self):
        """测试类名检查"""
        tool = HTMLSelectorTool()
        
        html = """
        <div class="product sold">Item</div>
        <div class="product">Item</div>
        <div>Item</div>
        """
        
        soup = BeautifulSoup(html, 'html.parser')
        elements = soup.find_all('div')
        
        # 有目标类
        assert tool.has_class(elements[0], "product") is True
        assert tool.has_class(elements[0], "sold") is True
        assert tool.has_class(elements[0], "available") is False
        
        # 只有部分类
        assert tool.has_class(elements[1], "product") is True
        assert tool.has_class(elements[1], "sold") is False
        
        # 没有类
        assert tool.has_class(elements[2], "product") is False
        
        # None元素
        assert tool.has_class(None, "product") is False
    
    def test_get_selectors(self):
        """测试获取选择器"""
        tool = HTMLSelectorTool()
        
        selectors = tool.get_selectors()
        
        assert isinstance(selectors, dict)
        assert "search_items" in selectors
        assert "product_name" in selectors
        assert "product_price" in selectors
        assert "product_link" in selectors
    
    def test_add_custom_selector(self):
        """测试添加自定义选择器"""
        tool = HTMLSelectorTool()
        
        original_count = len(tool.selectors)
        
        tool.add_custom_selector("custom_element", "[data-custom]")
        
        assert len(tool.selectors) == original_count + 1
        assert tool.selectors["custom_element"] == "[data-custom]"


class TestPriceParsingTool:
    """价格解析工具测试"""
    
    def test_price_parsing_tool_init(self):
        """测试价格解析工具初始化"""
        tool = PriceParsingTool()
        
        assert tool.currency_symbols is not None
        assert "¥" in tool.currency_symbols
        assert "円" in tool.currency_symbols
    
    def test_parse_price_yen(self):
        """测试解析日元价格"""
        tool = PriceParsingTool()
        
        # 标准格式
        assert tool.parse_price("¥50,000") == 50000
        assert tool.parse_price("¥1,234") == 1234
        assert tool.parse_price("¥500") == 500
        
        # 不同格式
        assert tool.parse_price("50,000円") == 50000
        assert tool.parse_price("1000 yen") == 1000
        assert tool.parse_price("2,500 JPY") == 2500
        
        # 带空格
        assert tool.parse_price("¥ 10,000") == 10000
        assert tool.parse_price("5,000 円") == 5000
    
    def test_parse_price_invalid(self):
        """测试解析无效价格"""
        tool = PriceParsingTool()
        
        # 无效格式
        assert tool.parse_price("invalid") is None
        assert tool.parse_price("") is None
        assert tool.parse_price("   ") is None
        assert tool.parse_price("free") is None
        
        # 负数
        assert tool.parse_price("-¥1000") is None
        assert tool.parse_price("¥-500") is None
    
    def test_parse_price_range(self):
        """测试解析价格范围"""
        tool = PriceParsingTool()
        
        # 价格范围
        min_price, max_price = tool.parse_price_range("¥1,000 - ¥5,000")
        assert min_price == 1000
        assert max_price == 5000
        
        # 不同分隔符
        min_price, max_price = tool.parse_price_range("¥2,000〜¥8,000")
        assert min_price == 2000
        assert max_price == 8000
        
        # 单一价格
        min_price, max_price = tool.parse_price_range("¥3,000")
        assert min_price == 3000
        assert max_price == 3000
        
        # 无效范围
        result = tool.parse_price_range("invalid range")
        assert result == (None, None)
    
    def test_format_price(self):
        """测试格式化价格"""
        tool = PriceParsingTool()
        
        # 标准格式化
        assert tool.format_price(50000) == "¥50,000"
        assert tool.format_price(1234) == "¥1,234"
        assert tool.format_price(500) == "¥500"
        
        # 不同货币
        assert tool.format_price(1000, currency="円") == "1,000円"
        assert tool.format_price(2500, currency="JPY") == "2,500 JPY"
        
        # 无效价格
        assert tool.format_price(None) == "価格不明"
        assert tool.format_price(-1000) == "価格不明"
    
    def test_is_valid_price(self):
        """测试价格验证"""
        tool = PriceParsingTool()
        
        # 有效价格
        assert tool.is_valid_price(1000) is True
        assert tool.is_valid_price(50000) is True
        assert tool.is_valid_price(1) is True
        
        # 无效价格
        assert tool.is_valid_price(None) is False
        assert tool.is_valid_price(-1000) is False
        assert tool.is_valid_price(0) is False
        assert tool.is_valid_price("1000") is False
    
    def test_compare_prices(self):
        """测试价格比较"""
        tool = PriceParsingTool()
        
        # 正常比较
        assert tool.compare_prices(1000, 2000) == -1
        assert tool.compare_prices(2000, 1000) == 1
        assert tool.compare_prices(1000, 1000) == 0
        
        # 包含None
        assert tool.compare_prices(None, 1000) == -1
        assert tool.compare_prices(1000, None) == 1
        assert tool.compare_prices(None, None) == 0
    
    def test_calculate_price_difference(self):
        """测试计算价格差异"""
        tool = PriceParsingTool()
        
        # 绝对差异
        assert tool.calculate_price_difference(5000, 3000) == 2000
        assert tool.calculate_price_difference(3000, 5000) == 2000
        
        # 百分比差异
        assert tool.calculate_price_difference(5000, 4000, percentage=True) == 20.0
        assert tool.calculate_price_difference(4000, 5000, percentage=True) == 25.0
        
        # 包含None
        assert tool.calculate_price_difference(None, 1000) is None
        assert tool.calculate_price_difference(1000, None) is None


class TestTextProcessingTool:
    """文本处理工具测试"""
    
    def test_text_processing_tool_init(self):
        """测试文本处理工具初始化"""
        tool = TextProcessingTool()
        
        assert tool.stopwords is not None
        assert len(tool.stopwords) > 0
        assert tool.kanji_pattern is not None
        assert tool.hiragana_pattern is not None
        assert tool.katakana_pattern is not None
    
    def test_clean_text(self):
        """测试清洗文本"""
        tool = TextProcessingTool()
        
        # 基本清洗
        text = "  Hello World  \n\n  "
        cleaned = tool.clean_text(text)
        assert cleaned == "Hello World"
        
        # 多行文本
        text = "Line 1\n\nLine 2\n   Line 3   "
        cleaned = tool.clean_text(text)
        assert cleaned == "Line 1 Line 2 Line 3"
        
        # 特殊字符
        text = "Text\u3000with\u00A0special\u2028spaces"
        cleaned = tool.clean_text(text)
        assert cleaned == "Text with special spaces"
    
    def test_normalize_japanese_text(self):
        """测试日语文本规范化"""
        tool = TextProcessingTool()
        
        # 全角转半角
        text = "ＩＰｈｏｎｅ　１２"
        normalized = tool.normalize_japanese_text(text)
        assert normalized == "iPhone 12"
        
        # Unicode规范化
        text = "が"  # 组合字符
        normalized = tool.normalize_japanese_text(text)
        assert len(normalized) == 1
        
        # 混合文本
        text = "商品名：ＩＰｈｏｎｅ　１２　Ｐｒｏ"
        normalized = tool.normalize_japanese_text(text)
        assert "iPhone 12 Pro" in normalized
    
    def test_extract_keywords(self):
        """测试提取关键词"""
        tool = TextProcessingTool()
        
        # 英文文本
        text = "iPhone 12 Pro Max in excellent condition"
        keywords = tool.extract_keywords(text)
        assert "iPhone" in keywords
        assert "Pro" in keywords
        assert "Max" in keywords
        assert "excellent" in keywords
        assert "condition" in keywords
        
        # 日文文本
        text = "iPhone 12 Pro 新品未使用 美品"
        keywords = tool.extract_keywords(text)
        assert "iPhone" in keywords
        assert "Pro" in keywords
        assert "新品" in keywords
        assert "未使用" in keywords
        assert "美品" in keywords
    
    def test_detect_language(self):
        """测试语言检测"""
        tool = TextProcessingTool()
        
        # 日语
        assert tool.detect_language("こんにちは") == "ja"
        assert tool.detect_language("商品説明") == "ja"
        assert tool.detect_language("カテゴリー") == "ja"
        
        # 英语
        assert tool.detect_language("Hello World") == "en"
        assert tool.detect_language("Product Description") == "en"
        
        # 混合（应该检测为主要语言）
        assert tool.detect_language("iPhone 12 新品") == "ja"
        assert tool.detect_language("Brand new iPhone 12") == "en"
    
    def test_split_sentences(self):
        """测试分句"""
        tool = TextProcessingTool()
        
        # 英文分句
        text = "This is sentence 1. This is sentence 2! This is sentence 3?"
        sentences = tool.split_sentences(text)
        assert len(sentences) == 3
        assert sentences[0] == "This is sentence 1."
        assert sentences[1] == "This is sentence 2!"
        assert sentences[2] == "This is sentence 3?"
        
        # 日文分句
        text = "これは文章1です。これは文章2です！これは文章3ですか？"
        sentences = tool.split_sentences(text)
        assert len(sentences) == 3
    
    def test_remove_html_tags(self):
        """测试移除HTML标签"""
        tool = TextProcessingTool()
        
        # 简单标签
        text = "<p>Hello <b>World</b></p>"
        cleaned = tool.remove_html_tags(text)
        assert cleaned == "Hello World"
        
        # 复杂标签
        text = '<div class="test">Text with <a href="link">link</a> and <img src="image.jpg" alt="image"></div>'
        cleaned = tool.remove_html_tags(text)
        assert cleaned == "Text with link and "
        
        # 自闭合标签
        text = "Line 1<br/>Line 2<hr>Line 3"
        cleaned = tool.remove_html_tags(text)
        assert cleaned == "Line 1Line 2Line 3"
    
    def test_truncate_text(self):
        """测试截断文本"""
        tool = TextProcessingTool()
        
        # 正常截断
        text = "This is a long text that should be truncated"
        truncated = tool.truncate_text(text, max_length=20)
        assert len(truncated) <= 20
        assert truncated.endswith("...")
        
        # 按词截断
        text = "This is a long text that should be truncated"
        truncated = tool.truncate_text(text, max_length=20, by_words=True)
        assert len(truncated) <= 20
        assert not truncated.endswith("is a")  # 不应该在单词中间截断
        
        # 短文本
        text = "Short text"
        truncated = tool.truncate_text(text, max_length=20)
        assert truncated == "Short text"
    
    def test_contains_japanese(self):
        """测试检测日语"""
        tool = TextProcessingTool()
        
        # 包含日语
        assert tool.contains_japanese("こんにちは") is True
        assert tool.contains_japanese("商品説明") is True
        assert tool.contains_japanese("カテゴリー") is True
        assert tool.contains_japanese("iPhone 12 新品") is True
        
        # 不包含日语
        assert tool.contains_japanese("Hello World") is False
        assert tool.contains_japanese("Product Description") is False
        assert tool.contains_japanese("12345") is False
    
    def test_get_text_stats(self):
        """测试获取文本统计"""
        tool = TextProcessingTool()
        
        text = "This is a test text. It has multiple sentences!"
        stats = tool.get_text_stats(text)
        
        assert stats["char_count"] == len(text)
        assert stats["word_count"] == 9
        assert stats["sentence_count"] == 2
        assert stats["contains_japanese"] is False
        assert stats["detected_language"] == "en"


class TestImageProcessingTool:
    """图片处理工具测试"""
    
    def test_image_processing_tool_init(self):
        """测试图片处理工具初始化"""
        tool = ImageProcessingTool()
        
        assert tool.supported_formats is not None
        assert "jpg" in tool.supported_formats
        assert "png" in tool.supported_formats
        assert "jpeg" in tool.supported_formats
    
    def test_is_valid_image_url(self):
        """测试验证图片URL"""
        tool = ImageProcessingTool()
        
        # 有效URL
        assert tool.is_valid_image_url("https://example.com/image.jpg") is True
        assert tool.is_valid_image_url("https://example.com/image.png") is True
        assert tool.is_valid_image_url("https://example.com/image.jpeg") is True
        
        # 无效URL
        assert tool.is_valid_image_url("https://example.com/document.pdf") is False
        assert tool.is_valid_image_url("invalid-url") is False
        assert tool.is_valid_image_url("") is False
        assert tool.is_valid_image_url(None) is False
    
    def test_extract_image_urls(self):
        """测试提取图片URL"""
        tool = ImageProcessingTool()
        
        html = """
        <div>
            <img src="https://example.com/image1.jpg" alt="Image 1">
            <img src="https://example.com/image2.png" alt="Image 2">
            <img src="invalid-url" alt="Invalid">
            <img src="https://example.com/document.pdf" alt="Not image">
        </div>
        """
        
        soup = BeautifulSoup(html, 'html.parser')
        urls = tool.extract_image_urls(soup)
        
        assert len(urls) == 2
        assert "https://example.com/image1.jpg" in urls
        assert "https://example.com/image2.png" in urls
        assert "invalid-url" not in urls
        assert "https://example.com/document.pdf" not in urls
    
    def test_filter_valid_images(self):
        """测试过滤有效图片"""
        tool = ImageProcessingTool()
        
        urls = [
            "https://example.com/image1.jpg",
            "https://example.com/image2.png",
            "invalid-url",
            "https://example.com/document.pdf",
            "",
            None
        ]
        
        valid_urls = tool.filter_valid_images(urls)
        
        assert len(valid_urls) == 2
        assert "https://example.com/image1.jpg" in valid_urls
        assert "https://example.com/image2.png" in valid_urls
    
    def test_get_image_filename(self):
        """测试获取图片文件名"""
        tool = ImageProcessingTool()
        
        # 标准URL
        filename = tool.get_image_filename("https://example.com/path/image.jpg")
        assert filename == "image.jpg"
        
        # 带查询参数
        filename = tool.get_image_filename("https://example.com/image.png?size=large")
        assert filename == "image.png"
        
        # 无扩展名
        filename = tool.get_image_filename("https://example.com/image")
        assert filename == "image"
    
    def test_get_image_extension(self):
        """测试获取图片扩展名"""
        tool = ImageProcessingTool()
        
        # 标准URL
        ext = tool.get_image_extension("https://example.com/image.jpg")
        assert ext == "jpg"
        
        # 大写扩展名
        ext = tool.get_image_extension("https://example.com/image.PNG")
        assert ext == "png"
        
        # 无扩展名
        ext = tool.get_image_extension("https://example.com/image")
        assert ext == ""
    
    def test_sort_images_by_quality(self):
        """测试按质量排序图片"""
        tool = ImageProcessingTool()
        
        urls = [
            "https://example.com/thumb.jpg",
            "https://example.com/image_1200x800.jpg",
            "https://example.com/image_600x400.jpg",
            "https://example.com/image.jpg"
        ]
        
        sorted_urls = tool.sort_images_by_quality(urls)
        
        # 应该按质量降序排列
        assert sorted_urls[0] == "https://example.com/image_1200x800.jpg"
        assert sorted_urls[1] == "https://example.com/image_600x400.jpg"
        # 其他图片顺序可能不定
    
    @patch('requests.head')
    def test_check_image_accessibility(self, mock_head):
        """测试检查图片可访问性"""
        tool = ImageProcessingTool()
        
        # 模拟成功响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "image/jpeg"}
        mock_head.return_value = mock_response
        
        is_accessible = tool.check_image_accessibility("https://example.com/image.jpg")
        assert is_accessible is True
        
        # 模拟失败响应
        mock_response.status_code = 404
        is_accessible = tool.check_image_accessibility("https://example.com/missing.jpg")
        assert is_accessible is False
        
        # 模拟网络错误
        mock_head.side_effect = requests.RequestException("Network error")
        is_accessible = tool.check_image_accessibility("https://example.com/error.jpg")
        assert is_accessible is False
    
    def test_estimate_image_quality(self):
        """测试估计图片质量"""
        tool = ImageProcessingTool()
        
        # 高质量图片
        high_quality = tool.estimate_image_quality("https://example.com/image_1920x1080.jpg")
        assert high_quality > 0.8
        
        # 中等质量图片
        medium_quality = tool.estimate_image_quality("https://example.com/image_800x600.jpg")
        assert 0.5 <= medium_quality <= 0.8
        
        # 低质量图片
        low_quality = tool.estimate_image_quality("https://example.com/thumb_100x100.jpg")
        assert low_quality < 0.5
        
        # 无尺寸信息
        unknown_quality = tool.estimate_image_quality("https://example.com/image.jpg")
        assert unknown_quality == 0.5  # 默认中等质量


class TestURLTool:
    """URL工具测试"""
    
    def test_url_tool_init(self):
        """测试URL工具初始化"""
        tool = URLTool()
        
        assert tool.base_url == "https://jp.mercari.com"
        assert tool.search_url == "https://jp.mercari.com/search"
    
    def test_is_valid_url(self):
        """测试URL验证"""
        tool = URLTool()
        
        # 有效URL
        assert tool.is_valid_url("https://jp.mercari.com") is True
        assert tool.is_valid_url("https://jp.mercari.com/item/123") is True
        assert tool.is_valid_url("http://example.com") is True
        
        # 无效URL
        assert tool.is_valid_url("not-a-url") is False
        assert tool.is_valid_url("") is False
        assert tool.is_valid_url(None) is False
    
    def test_is_mercari_url(self):
        """测试Mercari URL验证"""
        tool = URLTool()
        
        # 有效Mercari URL
        assert tool.is_mercari_url("https://jp.mercari.com") is True
        assert tool.is_mercari_url("https://jp.mercari.com/item/123") is True
        assert tool.is_mercari_url("https://jp.mercari.com/search") is True
        
        # 无效Mercari URL
        assert tool.is_mercari_url("https://example.com") is False
        assert tool.is_mercari_url("https://mercari.com") is False  # 不是jp子域
        assert tool.is_mercari_url("not-a-url") is False
    
    def test_normalize_url(self):
        """测试URL规范化"""
        tool = URLTool()
        
        # 相对URL
        assert tool.normalize_url("/item/123") == "https://jp.mercari.com/item/123"
        assert tool.normalize_url("item/123") == "https://jp.mercari.com/item/123"
        
        # 绝对URL
        assert tool.normalize_url("https://jp.mercari.com/item/123") == "https://jp.mercari.com/item/123"
        
        # 带查询参数
        assert tool.normalize_url("/search?keyword=iPhone") == "https://jp.mercari.com/search?keyword=iPhone"
    
    def test_extract_product_id(self):
        """测试提取商品ID"""
        tool = URLTool()
        
        # 标准商品URL
        assert tool.extract_product_id("https://jp.mercari.com/item/m12345678") == "m12345678"
        assert tool.extract_product_id("https://jp.mercari.com/item/m87654321") == "m87654321"
        
        # 相对URL
        assert tool.extract_product_id("/item/m12345678") == "m12345678"
        
        # 无效URL
        assert tool.extract_product_id("https://jp.mercari.com/search") is None
        assert tool.extract_product_id("invalid-url") is None
    
    def test_build_search_url(self):
        """测试构建搜索URL"""
        tool = URLTool()
        
        # 基本搜索
        params = {"keyword": "iPhone"}
        url = tool.build_search_url(params)
        assert "jp.mercari.com/search" in url
        assert "keyword=iPhone" in url
        
        # 多参数搜索
        params = {
            "keyword": "iPhone",
            "category_id": "1",
            "price_min": "1000",
            "price_max": "50000"
        }
        url = tool.build_search_url(params)
        assert "keyword=iPhone" in url
        assert "category_id=1" in url
        assert "price_min=1000" in url
        assert "price_max=50000" in url
    
    def test_build_category_url(self):
        """测试构建分类URL"""
        tool = URLTool()
        
        # 基本分类
        url = tool.build_category_url(1)
        assert "jp.mercari.com/category/1" in url
        
        # 带参数的分类
        url = tool.build_category_url(1, {"sort": "price_low"})
        assert "jp.mercari.com/category/1" in url
        assert "sort=price_low" in url
    
    def test_build_seller_url(self):
        """测试构建卖家URL"""
        tool = URLTool()
        
        # 基本卖家
        url = tool.build_seller_url("seller123")
        assert "jp.mercari.com/seller/seller123" in url
        
        # 带参数的卖家
        url = tool.build_seller_url("seller123", {"page": "2"})
        assert "jp.mercari.com/seller/seller123" in url
        assert "page=2" in url
    
    def test_parse_url_components(self):
        """测试解析URL组件"""
        tool = URLTool()
        
        url = "https://jp.mercari.com/search?keyword=iPhone&category_id=1&page=2"
        components = tool.parse_url_components(url)
        
        assert components["scheme"] == "https"
        assert components["netloc"] == "jp.mercari.com"
        assert components["path"] == "/search"
        assert components["query"]["keyword"] == "iPhone"
        assert components["query"]["category_id"] == "1"
        assert components["query"]["page"] == "2"
    
    def test_get_domain(self):
        """测试获取域名"""
        tool = URLTool()
        
        assert tool.get_domain("https://jp.mercari.com/item/123") == "jp.mercari.com"
        assert tool.get_domain("https://example.com/path") == "example.com"
        assert tool.get_domain("invalid-url") is None


class TestDataValidationTool:
    """数据验证工具测试"""
    
    def test_data_validation_tool_init(self):
        """测试数据验证工具初始化"""
        tool = DataValidationTool()
        
        assert tool.validation_rules is not None
        assert "title" in tool.validation_rules
        assert "price" in tool.validation_rules
        assert "url" in tool.validation_rules
    
    def test_validate_product_data(self):
        """测试验证商品数据"""
        tool = DataValidationTool()
        
        # 有效数据
        valid_product = ProductData(
            title="iPhone 12",
            price=50000,
            url="https://jp.mercari.com/item/test123",
            source="mercari"
        )
        
        is_valid, errors = tool.validate_product_data(valid_product)
        assert is_valid is True
        assert len(errors) == 0
        
        # 无效数据
        invalid_product = ProductData(
            title="",  # 空标题
            price=-1000,  # 负价格
            url="invalid-url",  # 无效URL
            source="mercari"
        )
        
        is_valid, errors = tool.validate_product_data(invalid_product)
        assert is_valid is False
        assert len(errors) > 0
    
    def test_validate_title(self):
        """测试验证标题"""
        tool = DataValidationTool()
        
        # 有效标题
        assert tool.validate_title("iPhone 12") is True
        assert tool.validate_title("商品名") is True
        
        # 无效标题
        assert tool.validate_title("") is False
        assert tool.validate_title("   ") is False
        assert tool.validate_title(None) is False
        assert tool.validate_title("a" * 201) is False  # 太长
    
    def test_validate_price(self):
        """测试验证价格"""
        tool = DataValidationTool()
        
        # 有效价格
        assert tool.validate_price(1000) is True
        assert tool.validate_price(50000) is True
        assert tool.validate_price(1) is True
        
        # 无效价格
        assert tool.validate_price(None) is False
        assert tool.validate_price(-1000) is False
        assert tool.validate_price(0) is False
        assert tool.validate_price("1000") is False
        assert tool.validate_price(10000000) is False  # 太贵
    
    def test_validate_url(self):
        """测试验证URL"""
        tool = DataValidationTool()
        
        # 有效URL
        assert tool.validate_url("https://jp.mercari.com/item/123") is True
        assert tool.validate_url("https://example.com") is True
        
        # 无效URL
        assert tool.validate_url("") is False
        assert tool.validate_url("not-a-url") is False
        assert tool.validate_url(None) is False
    
    def test_validate_image_urls(self):
        """测试验证图片URL"""
        tool = DataValidationTool()
        
        # 有效图片URL
        valid_urls = [
            "https://example.com/image1.jpg",
            "https://example.com/image2.png"
        ]
        assert tool.validate_image_urls(valid_urls) is True
        
        # 包含无效URL
        invalid_urls = [
            "https://example.com/image1.jpg",
            "invalid-url",
            "https://example.com/document.pdf"
        ]
        assert tool.validate_image_urls(invalid_urls) is False
        
        # 空列表
        assert tool.validate_image_urls([]) is True
        assert tool.validate_image_urls(None) is True
    
    def test_calculate_data_quality_score(self):
        """测试计算数据质量分数"""
        tool = DataValidationTool()
        
        # 高质量数据
        high_quality_product = ProductData(
            title="iPhone 12 Pro Max 256GB",
            price=80000,
            url="https://jp.mercari.com/item/test123",
            description="Detailed description of the product",
            condition="新品・未使用",
            images=["https://example.com/image1.jpg", "https://example.com/image2.jpg"],
            seller_name="TrustedSeller",
            seller_rating=4.8,
            source="mercari"
        )
        
        score = tool.calculate_data_quality_score(high_quality_product)
        assert score >= 0.8
        
        # 低质量数据
        low_quality_product = ProductData(
            title="Item",
            price=1000,
            url="https://jp.mercari.com/item/test456",
            source="mercari"
        )
        
        score = tool.calculate_data_quality_score(low_quality_product)
        assert score < 0.5
    
    def test_get_validation_summary(self):
        """测试获取验证摘要"""
        tool = DataValidationTool()
        
        product = ProductData(
            title="iPhone 12",
            price=50000,
            url="https://jp.mercari.com/item/test123",
            source="mercari"
        )
        
        summary = tool.get_validation_summary(product)
        
        assert "is_valid" in summary
        assert "quality_score" in summary
        assert "errors" in summary
        assert "warnings" in summary
        assert "field_completeness" in summary


class TestTimeParsingTool:
    """时间解析工具测试"""
    
    def test_time_parsing_tool_init(self):
        """测试时间解析工具初始化"""
        tool = TimeParsingTool()
        
        assert tool.japanese_time_patterns is not None
        assert tool.time_keywords is not None
        assert "分前" in tool.time_keywords
        assert "時間前" in tool.time_keywords
    
    def test_parse_japanese_date(self):
        """测试解析日语日期"""
        tool = TimeParsingTool()
        
        # 相对时间
        assert tool.parse_japanese_date("5分前") is not None
        assert tool.parse_japanese_date("2時間前") is not None
        assert tool.parse_japanese_date("3日前") is not None
        
        # 绝对日期
        assert tool.parse_japanese_date("2024年1月15日") is not None
        assert tool.parse_japanese_date("2024/01/15") is not None
        assert tool.parse_japanese_date("01-15") is not None
        
        # 无效日期
        assert tool.parse_japanese_date("invalid date") is None
        assert tool.parse_japanese_date("") is None
    
    def test_parse_relative_time(self):
        """测试解析相对时间"""
        tool = TimeParsingTool()
        
        # 分钟前
        time_5min = tool.parse_relative_time("5分前")
        assert time_5min is not None
        assert (datetime.now() - time_5min).total_seconds() < 400  # 约6分钟内
        
        # 小时前
        time_2hour = tool.parse_relative_time("2時間前")
        assert time_2hour is not None
        assert (datetime.now() - time_2hour).total_seconds() < 7300  # 约2小时内
        
        # 天前
        time_3day = tool.parse_relative_time("3日前")
        assert time_3day is not None
        assert (datetime.now() - time_3day).days <= 3
    
    def test_parse_absolute_date(self):
        """测试解析绝对日期"""
        tool = TimeParsingTool()
        
        # 完整日期
        date = tool.parse_absolute_date("2024年1月15日")
        assert date is not None
        assert date.year == 2024
        assert date.month == 1
        assert date.day == 15
        
        # 数字格式
        date = tool.parse_absolute_date("2024/01/15")
        assert date is not None
        assert date.year == 2024
        assert date.month == 1
        assert date.day == 15
        
        # 月日格式
        date = tool.parse_absolute_date("01-15")
        assert date is not None
        assert date.month == 1
        assert date.day == 15
    
    def test_format_japanese_time(self):
        """测试格式化日语时间"""
        tool = TimeParsingTool()
        
        # 创建测试时间
        test_time = datetime(2024, 1, 15, 14, 30, 0)
        
        # 格式化
        formatted = tool.format_japanese_time(test_time)
        assert "2024年1月15日" in formatted
        
        # 相对时间格式
        formatted = tool.format_japanese_time(test_time, relative=True)
        assert "前" in formatted or "ago" in formatted
    
    def test_is_recent_time(self):
        """测试检查是否为最近时间"""
        tool = TimeParsingTool()
        
        # 最近时间
        recent_time = datetime.now()
        assert tool.is_recent_time(recent_time) is True
        
        # 1小时前
        one_hour_ago = datetime.now().replace(hour=datetime.now().hour - 1)
        assert tool.is_recent_time(one_hour_ago, hours=2) is True
        
        # 很久以前
        long_ago = datetime(2020, 1, 1)
        assert tool.is_recent_time(long_ago) is False
    
    def test_calculate_time_difference(self):
        """测试计算时间差"""
        tool = TimeParsingTool()
        
        # 创建时间差
        time1 = datetime(2024, 1, 15, 10, 0, 0)
        time2 = datetime(2024, 1, 15, 12, 30, 0)
        
        diff = tool.calculate_time_difference(time1, time2)
        assert diff["hours"] == 2
        assert diff["minutes"] == 30
        
        # 负时间差
        diff = tool.calculate_time_difference(time2, time1)
        assert diff["hours"] == -2
        assert diff["minutes"] == -30


@pytest.fixture
def sample_html():
    """示例HTML内容"""
    return """
    <html>
        <body>
            <div data-testid="search-item">
                <h3 data-testid="product-name">Sample Product</h3>
                <span data-testid="product-price">¥10,000</span>
                <a data-testid="product-link" href="/item/sample">Link</a>
                <img data-testid="product-image" src="https://example.com/sample.jpg">
            </div>
        </body>
    </html>
    """


@pytest.fixture
def sample_product():
    """示例产品数据"""
    return ProductData(
        title="Sample Product",
        price=10000,
        url="https://jp.mercari.com/item/sample",
        description="Sample description",
        condition="良い",
        images=["https://example.com/sample.jpg"],
        source="mercari"
    )