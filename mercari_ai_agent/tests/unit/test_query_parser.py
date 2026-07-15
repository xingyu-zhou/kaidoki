"""
查询解析器单元测试

测试 QueryParser 类的各种功能，包括查询解析、意图分类、关键词提取等。

Author: Mercari AI Agent Team
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from mercari_agent.core.query_parser import QueryParser
from mercari_agent.models import ParsedQuery, QueryIntent, QueryComplexity
from mercari_agent.services.llm_service import LLMService


class TestQueryParser:
    """查询解析器测试类"""
    
    @pytest.fixture
    def mock_llm_service(self):
        """模拟LLM服务"""
        mock_service = Mock(spec=LLMService)
        mock_service.is_healthy.return_value = True
        return mock_service
    
    @pytest.fixture
    def query_parser(self, mock_llm_service):
        """查询解析器实例"""
        return QueryParser(mock_llm_service)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_parse_simple_query(self, query_parser, mock_llm_service):
        """测试简单查询解析"""
        # 设置模拟响应
        mock_llm_service.parse_query = AsyncMock(return_value={
            "intent": "search",
            "keywords": ["iPhone", "ケース"],
            "category": "スマホアクセサリー",
            "price_range": None,
            "condition": None,
            "brand": None,
            "complexity": "simple"
        })
        
        # 执行测试
        result = await query_parser.parse_query("iPhone ケース")
        
        # 验证结果
        assert isinstance(result, ParsedQuery)
        assert result.original_query == "iPhone ケース"
        assert result.intent == QueryIntent.SEARCH
        assert result.keywords == ["iPhone", "ケース"]
        assert result.category == "スマホアクセサリー"
        assert result.complexity == QueryComplexity.SIMPLE
        assert result.language == "ja"
        
        # 验证LLM服务被调用
        mock_llm_service.parse_query.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_parse_complex_query_with_price(self, query_parser, mock_llm_service):
        """测试包含价格的复杂查询解析"""
        # 设置模拟响应
        mock_llm_service.parse_query = AsyncMock(return_value={
            "intent": "search",
            "keywords": ["iPhone", "ケース"],
            "category": "スマホアクセサリー",
            "price_range": {"min": 0, "max": 3000},
            "condition": "新品",
            "brand": None,
            "complexity": "complex"
        })
        
        # 执行测试
        result = await query_parser.parse_query("3000円以下 新品 iPhone ケース")
        
        # 验证结果
        assert result.intent == QueryIntent.SEARCH
        assert result.keywords == ["iPhone", "ケース"]
        assert result.price_range is not None
        assert result.price_range.min_price == 0
        assert result.price_range.max_price == 3000
        assert result.condition == "新品"
        assert result.complexity == QueryComplexity.COMPLEX
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_parse_comparison_query(self, query_parser, mock_llm_service):
        """测试比较查询解析"""
        # 设置模拟响应
        mock_llm_service.parse_query = AsyncMock(return_value={
            "intent": "compare",
            "keywords": ["iPhone", "Samsung", "Galaxy"],
            "category": "スマートフォン",
            "price_range": None,
            "condition": None,
            "brand": None,
            "complexity": "complex"
        })
        
        # 执行测试
        result = await query_parser.parse_query("iPhone と Samsung Galaxy を比較")
        
        # 验证结果
        assert result.intent == QueryIntent.COMPARE
        assert "iPhone" in result.keywords
        assert "Samsung" in result.keywords
        assert "Galaxy" in result.keywords
        assert result.complexity == QueryComplexity.COMPLEX
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_parse_recommendation_query(self, query_parser, mock_llm_service):
        """测试推荐查询解析"""
        # 设置模拟响应
        mock_llm_service.parse_query = AsyncMock(return_value={
            "intent": "recommend",
            "keywords": ["ゲーミング", "ヘッドセット"],
            "category": "オーディオ機器",
            "price_range": {"min": 5000, "max": 15000},
            "condition": None,
            "brand": None,
            "complexity": "medium"
        })
        
        # 执行测试
        result = await query_parser.parse_query("5000円から15000円のゲーミングヘッドセットを推薦して")
        
        # 验证结果
        assert result.intent == QueryIntent.RECOMMEND
        assert result.keywords == ["ゲーミング", "ヘッドセット"]
        assert result.price_range.min_price == 5000
        assert result.price_range.max_price == 15000
        assert result.complexity == QueryComplexity.MEDIUM
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_parse_english_query(self, query_parser, mock_llm_service):
        """测试英语查询解析"""
        # 设置模拟响应
        mock_llm_service.parse_query = AsyncMock(return_value={
            "intent": "search",
            "keywords": ["iPhone", "case", "clear"],
            "category": "phone_accessories",
            "price_range": None,
            "condition": None,
            "brand": "Apple",
            "complexity": "simple"
        })
        
        # 执行测试
        result = await query_parser.parse_query("iPhone clear case", language="en")
        
        # 验证结果
        assert result.language == "en"
        assert result.keywords == ["iPhone", "case", "clear"]
        assert result.brand == "Apple"
        assert result.complexity == QueryComplexity.SIMPLE
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_parse_query_with_brand(self, query_parser, mock_llm_service):
        """测试包含品牌的查询解析"""
        # 设置模拟响应
        mock_llm_service.parse_query = AsyncMock(return_value={
            "intent": "search",
            "keywords": ["腕時計", "自動巻き"],
            "category": "腕時計",
            "price_range": None,
            "condition": None,
            "brand": "Seiko",
            "complexity": "medium"
        })
        
        # 执行测试
        result = await query_parser.parse_query("Seiko 自動巻き腕時計")
        
        # 验证结果
        assert result.brand == "Seiko"
        assert result.keywords == ["腕時計", "自動巻き"]
        assert result.complexity == QueryComplexity.MEDIUM
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_parse_empty_query(self, query_parser, mock_llm_service):
        """测试空查询处理"""
        with pytest.raises(ValueError, match="查询不能为空"):
            await query_parser.parse_query("")
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_parse_query_llm_error(self, query_parser, mock_llm_service):
        """测试LLM服务错误处理"""
        # 设置LLM服务抛出异常
        mock_llm_service.parse_query = AsyncMock(side_effect=Exception("LLM服务错误"))
        
        # 测试应该抛出异常
        with pytest.raises(Exception):
            await query_parser.parse_query("iPhone ケース")
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_parse_query_fallback(self, query_parser, mock_llm_service):
        """测试查询解析回退机制"""
        # 设置LLM服务返回不完整的响应
        mock_llm_service.parse_query = AsyncMock(return_value={
            "intent": "search",
            "keywords": ["iPhone"],
            # 缺少其他字段
        })
        
        # 执行测试
        result = await query_parser.parse_query("iPhone")
        
        # 验证回退值
        assert result.intent == QueryIntent.SEARCH
        assert result.keywords == ["iPhone"]
        assert result.category is None
        assert result.price_range is None
        assert result.complexity == QueryComplexity.SIMPLE  # 默认值
    
    @pytest.mark.unit
    def test_extract_keywords_japanese(self, query_parser):
        """测试日语关键词提取"""
        keywords = query_parser.extract_keywords("iPhone ケース 透明 新品")
        
        assert "iPhone" in keywords
        assert "ケース" in keywords
        assert "透明" in keywords
        assert "新品" in keywords
    
    @pytest.mark.unit
    def test_extract_keywords_english(self, query_parser):
        """测试英语关键词提取"""
        keywords = query_parser.extract_keywords("iPhone case clear new")
        
        assert "iPhone" in keywords
        assert "case" in keywords
        assert "clear" in keywords
        assert "new" in keywords
    
    @pytest.mark.unit
    def test_extract_price_range(self, query_parser):
        """测试价格范围提取"""
        # 测试单个价格
        price_range = query_parser.extract_price_range("3000円以下")
        assert price_range is not None
        assert price_range["max"] == 3000
        
        # 测试价格范围
        price_range = query_parser.extract_price_range("5000円から15000円")
        assert price_range is not None
        assert price_range["min"] == 5000
        assert price_range["max"] == 15000
        
        # 测试无价格
        price_range = query_parser.extract_price_range("iPhone ケース")
        assert price_range is None
    
    @pytest.mark.unit
    def test_classify_intent(self, query_parser):
        """测试意图分类"""
        # 搜索意图
        intent = query_parser.classify_intent("iPhone ケース")
        assert intent == QueryIntent.SEARCH
        
        # 比较意图
        intent = query_parser.classify_intent("iPhone と Samsung を比較")
        assert intent == QueryIntent.COMPARE
        
        # 推荐意图
        intent = query_parser.classify_intent("おすすめのスマートフォンを教えて")
        assert intent == QueryIntent.RECOMMEND
    
    @pytest.mark.unit
    def test_assess_complexity(self, query_parser):
        """测试复杂度评估"""
        # 简单查询
        complexity = query_parser.assess_complexity("iPhone")
        assert complexity == QueryComplexity.SIMPLE
        
        # 中等复杂度查询
        complexity = query_parser.assess_complexity("iPhone ケース 透明")
        assert complexity == QueryComplexity.MEDIUM
        
        # 复杂查询
        complexity = query_parser.assess_complexity("3000円以下 新品 iPhone ケース 透明 らくらくメルカリ便")
        assert complexity == QueryComplexity.COMPLEX
    
    @pytest.mark.unit
    def test_detect_language(self, query_parser):
        """测试语言检测"""
        # 日语
        language = query_parser.detect_language("iPhone ケース")
        assert language == "ja"
        
        # 英语
        language = query_parser.detect_language("iPhone case")
        assert language == "en"
        
        # 中文
        language = query_parser.detect_language("iPhone 保护壳")
        assert language == "zh"
    
    @pytest.mark.unit
    def test_normalize_query(self, query_parser):
        """测试查询标准化"""
        # 测试空格处理
        normalized = query_parser.normalize_query("  iPhone   ケース  ")
        assert normalized == "iPhone ケース"
        
        # 测试全角半角转换
        normalized = query_parser.normalize_query("ｉＰｈｏｎｅ　ケース")
        assert normalized == "iPhone ケース"
        
        # 测试大小写处理
        normalized = query_parser.normalize_query("iphone case")
        assert normalized == "iPhone case"
    
    @pytest.mark.unit
    def test_validate_query(self, query_parser):
        """测试查询验证"""
        # 有效查询
        assert query_parser.validate_query("iPhone ケース") == True
        
        # 空查询
        assert query_parser.validate_query("") == False
        assert query_parser.validate_query("   ") == False
        
        # 过长查询
        long_query = "a" * 1000
        assert query_parser.validate_query(long_query) == False
        
        # 包含特殊字符
        assert query_parser.validate_query("iPhone<script>alert('xss')</script>") == False
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_parse_query_caching(self, query_parser, mock_llm_service):
        """测试查询解析缓存"""
        # 设置模拟响应
        mock_response = {
            "intent": "search",
            "keywords": ["iPhone", "ケース"],
            "category": "スマホアクセサリー",
            "complexity": "simple"
        }
        mock_llm_service.parse_query = AsyncMock(return_value=mock_response)
        
        # 第一次调用
        result1 = await query_parser.parse_query("iPhone ケース")
        
        # 第二次调用相同查询
        result2 = await query_parser.parse_query("iPhone ケース")
        
        # 验证结果相同
        assert result1.original_query == result2.original_query
        assert result1.keywords == result2.keywords
        
        # 验证LLM服务只被调用一次（由于缓存）
        assert mock_llm_service.parse_query.call_count == 1
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_parse_query_performance(self, query_parser, mock_llm_service, performance_timer):
        """测试查询解析性能"""
        # 设置模拟响应
        mock_llm_service.parse_query = AsyncMock(return_value={
            "intent": "search",
            "keywords": ["iPhone"],
            "complexity": "simple"
        })
        
        # 性能测试
        with performance_timer() as timer:
            await query_parser.parse_query("iPhone")
        
        # 验证性能（应该在1秒内完成）
        assert timer.elapsed < 1.0
    
    @pytest.mark.unit
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_parse_query_stress(self, query_parser, mock_llm_service):
        """测试查询解析压力测试"""
        # 设置模拟响应
        mock_llm_service.parse_query = AsyncMock(return_value={
            "intent": "search",
            "keywords": ["test"],
            "complexity": "simple"
        })
        
        # 并发测试
        import asyncio
        tasks = []
        for i in range(100):
            task = query_parser.parse_query(f"test query {i}")
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        # 验证所有结果都成功
        assert len(results) == 100
        for result in results:
            assert isinstance(result, ParsedQuery)
            assert result.intent == QueryIntent.SEARCH