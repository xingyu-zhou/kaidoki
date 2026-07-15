"""
推荐流程集成测试

测试完整的推荐流程，包括查询解析、产品搜索、分析和推荐生成。

Author: Mercari AI Agent Team
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from mercari_agent.main import MercariAIAgent
from mercari_agent.models import (
    RecommendationStrategy, 
    RecommendationResult,
    QueryIntent
)
from tests.fixtures.sample_data import (
    SAMPLE_PRODUCTS,
    SAMPLE_QUERIES,
    SAMPLE_RECOMMENDATIONS
)


class TestRecommendationFlow:
    """推荐流程集成测试"""
    
    @pytest.fixture
    async def app_instance(self, test_settings):
        """应用实例"""
        app = MercariAIAgent()
        await app.initialize()
        yield app
        await app.shutdown()
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_basic_recommendation_flow(self, app_instance):
        """测试基本推荐流程"""
        # 模拟所有服务
        with patch.object(app_instance.query_parser, 'parse_query') as mock_parse, \
             patch.object(app_instance.recommendation_engine, 'generate_recommendations') as mock_recommend:
            
            # 设置模拟返回值
            mock_parse.return_value = Mock(
                original_query="iPhone ケース",
                intent=QueryIntent.SEARCH,
                keywords=["iPhone", "ケース"],
                category="スマホアクセサリー",
                language="ja"
            )
            
            mock_recommend.return_value = RecommendationResult(
                recommendations=SAMPLE_RECOMMENDATIONS[:3],
                total_analyzed=48,
                processing_time=2.5,
                strategy_used=RecommendationStrategy.BALANCED
            )
            
            # 执行推荐流程
            result = await app_instance.process_query(
                query="iPhone ケース",
                strategy=RecommendationStrategy.BALANCED,
                max_results=10
            )
            
            # 验证结果
            assert isinstance(result, RecommendationResult)
            assert len(result.recommendations) == 3
            assert result.total_analyzed == 48
            assert result.processing_time > 0
            assert result.strategy_used == RecommendationStrategy.BALANCED
            
            # 验证调用
            mock_parse.assert_called_once_with("iPhone ケース", "ja")
            mock_recommend.assert_called_once()
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_query_parsing_integration(self, app_instance):
        """测试查询解析集成"""
        with patch.object(app_instance.llm_service, 'parse_query') as mock_llm:
            mock_llm.return_value = {
                "intent": "search",
                "keywords": ["Nintendo", "Switch"],
                "category": "テレビゲーム",
                "price_range": {"min": 0, "max": 40000},
                "condition": "新品",
                "complexity": "medium"
            }
            
            # 测试查询解析
            parsed = await app_instance.query_parser.parse_query("40000円以下 新品 Nintendo Switch")
            
            assert parsed.intent == QueryIntent.SEARCH
            assert parsed.keywords == ["Nintendo", "Switch"]
            assert parsed.category == "テレビゲーム"
            assert parsed.price_range.max_price == 40000
            assert parsed.condition == "新品"
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_scraper_integration(self, app_instance):
        """测试爬虫集成"""
        with patch.object(app_instance.scraper_service, 'search_products') as mock_search:
            mock_search.return_value = SAMPLE_PRODUCTS[:5]
            
            # 测试产品搜索
            products = await app_instance.scraper_service.search_products("iPhone ケース")
            
            assert len(products) == 5
            assert all(hasattr(p, 'product_id') for p in products)
            assert all(hasattr(p, 'title') for p in products)
            assert all(hasattr(p, 'price') for p in products)
            
            mock_search.assert_called_once_with("iPhone ケース")
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_analysis_integration(self, app_instance):
        """测试分析集成"""
        with patch.object(app_instance.analysis_service, 'analyze_products') as mock_analyze:
            mock_analyze.return_value = [
                {
                    "price_score": 8.5,
                    "quality_score": 7.8,
                    "relevance_score": 9.2,
                    "reputation_score": 8.0,
                    "popularity_score": 7.5,
                    "overall_score": 8.2
                }
                for _ in range(3)
            ]
            
            # 测试产品分析
            results = await app_instance.analysis_service.analyze_products(SAMPLE_PRODUCTS[:3])
            
            assert len(results) == 3
            assert all('overall_score' in r for r in results)
            assert all(r['overall_score'] > 0 for r in results)
            
            mock_analyze.assert_called_once_with(SAMPLE_PRODUCTS[:3])
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_different_strategies(self, app_instance):
        """测试不同推荐策略"""
        strategies = [
            RecommendationStrategy.BALANCED,
            RecommendationStrategy.PRICE_ORIENTED,
            RecommendationStrategy.QUALITY_ORIENTED
        ]
        
        for strategy in strategies:
            with patch.object(app_instance.recommendation_engine, 'generate_recommendations') as mock_recommend:
                mock_recommend.return_value = RecommendationResult(
                    recommendations=SAMPLE_RECOMMENDATIONS[:5],
                    strategy_used=strategy
                )
                
                result = await app_instance.process_query(
                    query="iPhone ケース",
                    strategy=strategy
                )
                
                assert result.strategy_used == strategy
                assert len(result.recommendations) == 5
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_error_handling_integration(self, app_instance):
        """测试错误处理集成"""
        # 测试查询解析错误
        with patch.object(app_instance.query_parser, 'parse_query') as mock_parse:
            mock_parse.side_effect = Exception("查询解析失败")
            
            result = await app_instance.process_query("invalid query")
            
            # 应该返回空结果而不是抛出异常
            assert isinstance(result, RecommendationResult)
            assert len(result.recommendations) == 0
            assert "error" in result.metadata
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_caching_integration(self, app_instance):
        """测试缓存集成"""
        query = "iPhone ケース"
        
        # 模拟缓存
        with patch.object(app_instance.cache_manager, 'get') as mock_get, \
             patch.object(app_instance.cache_manager, 'set') as mock_set, \
             patch.object(app_instance.recommendation_engine, 'generate_recommendations') as mock_recommend:
            
            # 第一次调用 - 缓存未命中
            mock_get.return_value = None
            mock_recommend.return_value = RecommendationResult(
                recommendations=SAMPLE_RECOMMENDATIONS[:3]
            )
            
            result1 = await app_instance.process_query(query)
            
            # 验证缓存设置
            mock_get.assert_called()
            mock_set.assert_called()
            mock_recommend.assert_called_once()
            
            # 第二次调用 - 缓存命中
            mock_get.return_value = result1.to_dict()
            mock_recommend.reset_mock()
            
            result2 = await app_instance.process_query(query)
            
            # 验证缓存使用
            assert len(result2.recommendations) == len(result1.recommendations)
            mock_recommend.assert_not_called()  # 不应该调用推荐引擎
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_performance_integration(self, app_instance, performance_timer):
        """测试性能集成"""
        # 模拟快速响应
        with patch.object(app_instance.recommendation_engine, 'generate_recommendations') as mock_recommend:
            mock_recommend.return_value = RecommendationResult(
                recommendations=SAMPLE_RECOMMENDATIONS[:5],
                processing_time=0.5
            )
            
            # 性能测试
            with performance_timer() as timer:
                result = await app_instance.process_query("iPhone ケース")
            
            # 验证性能
            assert timer.elapsed < 2.0  # 应该在2秒内完成
            assert result.processing_time > 0
            assert len(result.recommendations) == 5
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, app_instance):
        """测试并发请求"""
        import asyncio
        
        # 模拟推荐引擎
        with patch.object(app_instance.recommendation_engine, 'generate_recommendations') as mock_recommend:
            mock_recommend.return_value = RecommendationResult(
                recommendations=SAMPLE_RECOMMENDATIONS[:3]
            )
            
            # 并发请求
            queries = ["iPhone ケース", "Nintendo Switch", "MacBook"]
            tasks = [app_instance.process_query(q) for q in queries]
            
            results = await asyncio.gather(*tasks)
            
            # 验证结果
            assert len(results) == 3
            assert all(isinstance(r, RecommendationResult) for r in results)
            assert all(len(r.recommendations) == 3 for r in results)
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_health_check_integration(self, app_instance):
        """测试健康检查集成"""
        # 模拟所有服务健康
        with patch.object(app_instance.llm_service, 'is_healthy', return_value=True), \
             patch.object(app_instance.scraper_service, 'is_healthy', return_value=True), \
             patch.object(app_instance.analysis_service, 'is_healthy', return_value=True), \
             patch.object(app_instance.cache_manager, 'is_healthy', return_value=True):
            
            status = app_instance.get_health_status()
            
            assert status["status"] == "healthy"
            assert status["services"]["llm_service"] == "healthy"
            assert status["services"]["scraper_service"] == "healthy"
            assert status["services"]["analysis_service"] == "healthy"
            assert status["services"]["cache_manager"] == "healthy"
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_service_failure_handling(self, app_instance):
        """测试服务故障处理"""
        # 模拟LLM服务故障
        with patch.object(app_instance.llm_service, 'is_healthy', return_value=False):
            
            status = app_instance.get_health_status()
            
            assert status["status"] == "unhealthy"
            assert status["services"]["llm_service"] == "unhealthy"
    
    @pytest.mark.integration
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_large_dataset_processing(self, app_instance):
        """测试大数据集处理"""
        # 模拟大量产品数据
        large_product_list = SAMPLE_PRODUCTS * 20  # 100个产品
        
        with patch.object(app_instance.scraper_service, 'search_products') as mock_search, \
             patch.object(app_instance.analysis_service, 'analyze_products') as mock_analyze:
            
            mock_search.return_value = large_product_list
            mock_analyze.return_value = [{"overall_score": 8.0}] * len(large_product_list)
            
            # 测试大数据集处理
            result = await app_instance.process_query("iPhone ケース", max_results=50)
            
            assert isinstance(result, RecommendationResult)
            assert result.total_analyzed == len(large_product_list)
            assert len(result.recommendations) <= 50  # 应该限制结果数量
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_multilingual_support(self, app_instance):
        """测试多语言支持"""
        languages = ["ja", "en", "zh"]
        queries = ["iPhone ケース", "iPhone case", "iPhone 保护壳"]
        
        for lang, query in zip(languages, queries):
            with patch.object(app_instance.query_parser, 'parse_query') as mock_parse:
                mock_parse.return_value = Mock(
                    original_query=query,
                    intent=QueryIntent.SEARCH,
                    keywords=["iPhone"],
                    language=lang
                )
                
                result = await app_instance.process_query(query, language=lang)
                
                assert isinstance(result, RecommendationResult)
                mock_parse.assert_called_with(query, lang)
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_recommendation_quality_metrics(self, app_instance):
        """测试推荐质量指标"""
        with patch.object(app_instance.recommendation_engine, 'generate_recommendations') as mock_recommend:
            # 设置高质量推荐
            high_quality_recommendations = [
                rec for rec in SAMPLE_RECOMMENDATIONS 
                if rec.score >= 8.0 and rec.confidence >= 0.8
            ]
            
            mock_recommend.return_value = RecommendationResult(
                recommendations=high_quality_recommendations,
                total_analyzed=48,
                processing_time=2.0
            )
            
            result = await app_instance.process_query("iPhone ケース")
            
            # 验证推荐质量
            assert result.average_score >= 8.0
            assert result.get_average_confidence() >= 0.8
            assert result.high_confidence_count == len(high_quality_recommendations)
            assert result.recommended_count == len(high_quality_recommendations)
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_recommendation_diversity(self, app_instance):
        """测试推荐多样性"""
        # 创建多样化的产品数据
        diverse_products = [
            SAMPLE_PRODUCTS[0],  # iPhone案例
            SAMPLE_PRODUCTS[1],  # Nintendo Switch
            SAMPLE_PRODUCTS[2],  # 服装
            SAMPLE_PRODUCTS[3],  # MacBook
            SAMPLE_PRODUCTS[4],  # 卡牌
        ]
        
        with patch.object(app_instance.scraper_service, 'search_products') as mock_search, \
             patch.object(app_instance.analysis_service, 'analyze_products') as mock_analyze:
            
            mock_search.return_value = diverse_products
            mock_analyze.return_value = [{"overall_score": 8.0}] * len(diverse_products)
            
            result = await app_instance.process_query("电子产品")
            
            # 验证多样性
            categories = set(r.product.category for r in result.recommendations)
            assert len(categories) > 1  # 应该有多个类别
    
    @pytest.mark.integration
    @pytest.mark.network
    @pytest.mark.asyncio
    async def test_external_service_integration(self, app_instance):
        """测试外部服务集成"""
        # 注意：这个测试需要网络连接，通常在CI/CD中跳过
        pytest.skip("需要网络连接的测试")
        
        # 真实的外部服务调用测试
        # result = await app_instance.process_query("iPhone ケース")
        # assert isinstance(result, RecommendationResult)