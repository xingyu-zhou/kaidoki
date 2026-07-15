"""
数据模型单元测试

测试各种数据模型的功能，包括产品、查询、推荐等模型。

Author: Mercari AI Agent Team
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from mercari_agent.models import (
    ProductData, 
    SellerInfo, 
    ProductImages,
    ParsedQuery,
    SearchQuery,
    QueryIntent,
    QueryComplexity,
    PriceRange,
    Recommendation,
    RecommendationReason,
    RecommendationResult,
    RecommendationStrategy,
    RecommendationConfidence,
    create_product_from_dict,
    create_empty_result
)


class TestProductData:
    """产品数据模型测试"""
    
    @pytest.mark.unit
    def test_create_product_basic(self):
        """测试基本产品创建"""
        product = ProductData(
            product_id="test123",
            title="Test Product",
            price=1000.0,
            currency="JPY",
            condition="新品、未使用",
            category="テスト",
            url="https://example.com/test123"
        )
        
        assert product.product_id == "test123"
        assert product.title == "Test Product"
        assert product.price == 1000.0
        assert product.currency == "JPY"
        assert product.condition == "新品、未使用"
        assert product.category == "テスト"
        assert product.url == "https://example.com/test123"
    
    @pytest.mark.unit
    def test_product_validation(self):
        """测试产品数据验证"""
        # 无效的产品ID
        with pytest.raises(ValueError, match="产品ID不能为空"):
            ProductData(
                product_id="",
                title="Test",
                price=1000.0,
                currency="JPY"
            )
        
        # 无效的价格
        with pytest.raises(ValueError, match="价格必须大于0"):
            ProductData(
                product_id="test123",
                title="Test",
                price=-100.0,
                currency="JPY"
            )
        
        # 无效的URL
        with pytest.raises(ValueError, match="URL格式不正确"):
            ProductData(
                product_id="test123",
                title="Test",
                price=1000.0,
                currency="JPY",
                url="invalid-url"
            )
    
    @pytest.mark.unit
    def test_product_to_dict(self):
        """测试产品转换为字典"""
        product = ProductData(
            product_id="test123",
            title="Test Product",
            price=1000.0,
            currency="JPY",
            condition="新品、未使用",
            category="テスト",
            url="https://example.com/test123"
        )
        
        data = product.to_dict()
        
        assert data["product_id"] == "test123"
        assert data["title"] == "Test Product"
        assert data["price"] == 1000.0
        assert data["currency"] == "JPY"
        assert data["condition"] == "新品、未使用"
        assert data["category"] == "テスト"
        assert data["url"] == "https://example.com/test123"
    
    @pytest.mark.unit
    def test_product_from_dict(self):
        """测试从字典创建产品"""
        data = {
            "product_id": "test123",
            "title": "Test Product",
            "price": 1000.0,
            "currency": "JPY",
            "condition": "新品、未使用",
            "category": "テスト",
            "url": "https://example.com/test123"
        }
        
        product = ProductData.from_dict(data)
        
        assert product.product_id == "test123"
        assert product.title == "Test Product"
        assert product.price == 1000.0
        assert product.currency == "JPY"
        assert product.condition == "新品、未使用"
        assert product.category == "テスト"
        assert product.url == "https://example.com/test123"
    
    @pytest.mark.unit
    def test_product_price_info(self):
        """测试产品价格信息"""
        product = ProductData(
            product_id="test123",
            title="Test Product",
            price=1000.0,
            original_price=1500.0,
            currency="JPY"
        )
        
        assert product.get_discount_amount() == 500.0
        assert product.get_discount_percentage() == 33.3
        assert product.is_on_sale() == True
        assert product.get_formatted_price() == "¥1,000"
    
    @pytest.mark.unit
    def test_product_condition_score(self):
        """测试产品状态评分"""
        # 新品
        product_new = ProductData(
            product_id="test1",
            title="New Product",
            price=1000.0,
            condition="新品、未使用"
        )
        assert product_new.get_condition_score() == 10
        
        # 中古
        product_used = ProductData(
            product_id="test2",
            title="Used Product",
            price=800.0,
            condition="やや傷や汚れあり"
        )
        assert product_used.get_condition_score() == 6
    
    @pytest.mark.unit
    def test_product_with_seller_info(self):
        """测试包含卖家信息的产品"""
        seller = SellerInfo(
            seller_id="seller123",
            seller_name="Test Seller",
            seller_rating=4.5,
            seller_reviews=100
        )
        
        product = ProductData(
            product_id="test123",
            title="Test Product",
            price=1000.0,
            currency="JPY",
            seller_info=seller
        )
        
        assert product.seller_info.seller_id == "seller123"
        assert product.seller_info.seller_name == "Test Seller"
        assert product.seller_info.seller_rating == 4.5
        assert product.get_seller_trust_score() == 4.5


class TestSellerInfo:
    """卖家信息模型测试"""
    
    @pytest.mark.unit
    def test_create_seller_info(self):
        """测试创建卖家信息"""
        seller = SellerInfo(
            seller_id="seller123",
            seller_name="Test Seller",
            seller_rating=4.5,
            seller_reviews=100,
            seller_location="東京都"
        )
        
        assert seller.seller_id == "seller123"
        assert seller.seller_name == "Test Seller"
        assert seller.seller_rating == 4.5
        assert seller.seller_reviews == 100
        assert seller.seller_location == "東京都"
    
    @pytest.mark.unit
    def test_seller_validation(self):
        """测试卖家信息验证"""
        # 无效的评分
        with pytest.raises(ValueError, match="评分必须在0-5之间"):
            SellerInfo(
                seller_id="seller123",
                seller_name="Test Seller",
                seller_rating=6.0,
                seller_reviews=100
            )
        
        # 无效的评论数
        with pytest.raises(ValueError, match="评论数不能为负"):
            SellerInfo(
                seller_id="seller123",
                seller_name="Test Seller",
                seller_rating=4.5,
                seller_reviews=-10
            )
    
    @pytest.mark.unit
    def test_seller_trust_level(self):
        """测试卖家信任级别"""
        # 高信任度
        seller_high = SellerInfo(
            seller_id="seller1",
            seller_name="High Trust Seller",
            seller_rating=4.8,
            seller_reviews=500,
            seller_badges=["verified", "top_seller"]
        )
        assert seller_high.get_trust_level() == "高"
        
        # 中等信任度
        seller_medium = SellerInfo(
            seller_id="seller2",
            seller_name="Medium Trust Seller",
            seller_rating=4.0,
            seller_reviews=50
        )
        assert seller_medium.get_trust_level() == "中"
        
        # 低信任度
        seller_low = SellerInfo(
            seller_id="seller3",
            seller_name="Low Trust Seller",
            seller_rating=3.0,
            seller_reviews=5
        )
        assert seller_low.get_trust_level() == "低"


class TestParsedQuery:
    """解析查询模型测试"""
    
    @pytest.mark.unit
    def test_create_parsed_query(self):
        """测试创建解析查询"""
        query = ParsedQuery(
            original_query="iPhone ケース",
            intent=QueryIntent.SEARCH,
            keywords=["iPhone", "ケース"],
            category="スマホアクセサリー",
            language="ja"
        )
        
        assert query.original_query == "iPhone ケース"
        assert query.intent == QueryIntent.SEARCH
        assert query.keywords == ["iPhone", "ケース"]
        assert query.category == "スマホアクセサリー"
        assert query.language == "ja"
    
    @pytest.mark.unit
    def test_query_with_price_range(self):
        """测试包含价格范围的查询"""
        price_range = PriceRange(min_price=1000, max_price=5000)
        
        query = ParsedQuery(
            original_query="1000円から5000円のiPhoneケース",
            intent=QueryIntent.SEARCH,
            keywords=["iPhone", "ケース"],
            price_range=price_range,
            language="ja"
        )
        
        assert query.price_range.min_price == 1000
        assert query.price_range.max_price == 5000
        assert query.has_price_constraint() == True
    
    @pytest.mark.unit
    def test_query_complexity_assessment(self):
        """测试查询复杂度评估"""
        # 简单查询
        simple_query = ParsedQuery(
            original_query="iPhone",
            intent=QueryIntent.SEARCH,
            keywords=["iPhone"],
            complexity=QueryComplexity.SIMPLE
        )
        assert simple_query.is_simple() == True
        
        # 复杂查询
        complex_query = ParsedQuery(
            original_query="3000円以下 新品 iPhone ケース 透明",
            intent=QueryIntent.SEARCH,
            keywords=["iPhone", "ケース", "透明"],
            complexity=QueryComplexity.COMPLEX,
            price_range=PriceRange(max_price=3000),
            condition="新品"
        )
        assert complex_query.is_complex() == True
        assert complex_query.has_multiple_constraints() == True
    
    @pytest.mark.unit
    def test_query_to_search_params(self):
        """测试查询转换为搜索参数"""
        query = ParsedQuery(
            original_query="iPhone ケース",
            intent=QueryIntent.SEARCH,
            keywords=["iPhone", "ケース"],
            category="スマホアクセサリー",
            price_range=PriceRange(max_price=3000),
            condition="新品"
        )
        
        params = query.to_search_params()
        
        assert params["keyword"] == "iPhone ケース"
        assert params["category"] == "スマホアクセサリー"
        assert params["price_max"] == 3000
        assert params["condition"] == "新品"


class TestRecommendation:
    """推荐模型测试"""
    
    @pytest.fixture
    def sample_product(self):
        """样本产品"""
        return ProductData(
            product_id="test123",
            title="Test Product",
            price=1000.0,
            currency="JPY",
            condition="新品、未使用",
            category="テスト",
            url="https://example.com/test123"
        )
    
    @pytest.fixture
    def sample_reason(self):
        """样本推荐理由"""
        return RecommendationReason(
            type="price_advantage",
            description="価格が安い",
            importance=0.8
        )
    
    @pytest.mark.unit
    def test_create_recommendation(self, sample_product, sample_reason):
        """测试创建推荐"""
        recommendation = Recommendation(
            product=sample_product,
            rank=1,
            score=8.5,
            confidence=0.9,
            reasons=[sample_reason]
        )
        
        assert recommendation.product.product_id == "test123"
        assert recommendation.rank == 1
        assert recommendation.score == 8.5
        assert recommendation.confidence == 0.9
        assert len(recommendation.reasons) == 1
        assert recommendation.reasons[0].type == "price_advantage"
    
    @pytest.mark.unit
    def test_recommendation_validation(self, sample_product):
        """测试推荐验证"""
        # 无效的排名
        with pytest.raises(ValueError, match="排名必须大于0"):
            Recommendation(
                product=sample_product,
                rank=0,
                score=8.5,
                confidence=0.9
            )
        
        # 无效的评分
        with pytest.raises(ValueError, match="评分必须在0-10之间"):
            Recommendation(
                product=sample_product,
                rank=1,
                score=11.0,
                confidence=0.9
            )
        
        # 无效的置信度
        with pytest.raises(ValueError, match="置信度必须在0-1之间"):
            Recommendation(
                product=sample_product,
                rank=1,
                score=8.5,
                confidence=1.5
            )
    
    @pytest.mark.unit
    def test_recommendation_confidence_level(self, sample_product):
        """测试推荐置信度级别"""
        # 高置信度
        high_confidence = Recommendation(
            product=sample_product,
            rank=1,
            score=8.5,
            confidence=0.95
        )
        assert high_confidence.get_confidence_level() == RecommendationConfidence.VERY_HIGH
        
        # 中等置信度
        medium_confidence = Recommendation(
            product=sample_product,
            rank=1,
            score=8.5,
            confidence=0.65
        )
        assert medium_confidence.get_confidence_level() == RecommendationConfidence.MEDIUM
        
        # 低置信度
        low_confidence = Recommendation(
            product=sample_product,
            rank=1,
            score=8.5,
            confidence=0.4
        )
        assert low_confidence.get_confidence_level() == RecommendationConfidence.LOW
    
    @pytest.mark.unit
    def test_recommendation_purchase_advice(self, sample_product):
        """测试购买建议"""
        # 强烈推荐
        strong_recommendation = Recommendation(
            product=sample_product,
            rank=1,
            score=9.0,
            confidence=0.9
        )
        assert strong_recommendation.get_purchase_recommendation() == "强烈推荐购买"
        
        # 推荐
        normal_recommendation = Recommendation(
            product=sample_product,
            rank=1,
            score=7.0,
            confidence=0.7
        )
        assert normal_recommendation.get_purchase_recommendation() == "推荐购买"
        
        # 不推荐
        poor_recommendation = Recommendation(
            product=sample_product,
            rank=1,
            score=3.0,
            confidence=0.3
        )
        assert poor_recommendation.get_purchase_recommendation() == "不推荐购买"


class TestRecommendationResult:
    """推荐结果模型测试"""
    
    @pytest.fixture
    def sample_recommendations(self):
        """样本推荐列表"""
        product = ProductData(
            product_id="test123",
            title="Test Product",
            price=1000.0,
            currency="JPY"
        )
        
        return [
            Recommendation(
                product=product,
                rank=1,
                score=9.0,
                confidence=0.9
            ),
            Recommendation(
                product=product,
                rank=2,
                score=8.0,
                confidence=0.8
            ),
            Recommendation(
                product=product,
                rank=3,
                score=7.0,
                confidence=0.7
            )
        ]
    
    @pytest.mark.unit
    def test_create_recommendation_result(self, sample_recommendations):
        """测试创建推荐结果"""
        result = RecommendationResult(
            recommendations=sample_recommendations,
            total_analyzed=48,
            processing_time=2.5,
            strategy_used=RecommendationStrategy.BALANCED
        )
        
        assert len(result.recommendations) == 3
        assert result.total_analyzed == 48
        assert result.processing_time == 2.5
        assert result.strategy_used == RecommendationStrategy.BALANCED
    
    @pytest.mark.unit
    def test_recommendation_result_statistics(self, sample_recommendations):
        """测试推荐结果统计"""
        result = RecommendationResult(
            recommendations=sample_recommendations,
            total_analyzed=48
        )
        
        assert result.average_score == 8.0  # (9.0 + 8.0 + 7.0) / 3
        assert result.get_average_confidence() == 0.8  # (0.9 + 0.8 + 0.7) / 3
        assert len(result.get_high_confidence_recommendations()) == 2  # 置信度 >= 0.8
        assert len(result.get_recommended_products()) == 2  # 评分 >= 6.0 且置信度 >= 0.6
    
    @pytest.mark.unit
    def test_empty_recommendation_result(self):
        """测试空推荐结果"""
        result = create_empty_result()
        
        assert len(result.recommendations) == 0
        assert result.total_analyzed == 0
        assert result.processing_time == 0.0
        assert result.average_score == 0.0
        assert result.get_average_confidence() == 0.0
    
    @pytest.mark.unit
    def test_recommendation_result_filtering(self, sample_recommendations):
        """测试推荐结果过滤"""
        result = RecommendationResult(recommendations=sample_recommendations)
        
        # 按评分过滤
        high_score = result.filter_by_score(8.5)
        assert len(high_score) == 1
        assert high_score[0].score == 9.0
        
        # 按置信度过滤
        high_confidence = result.filter_by_confidence(0.85)
        assert len(high_confidence) == 1
        assert high_confidence[0].confidence == 0.9
        
        # 按价格范围过滤
        price_filtered = result.filter_by_price_range(500, 1500)
        assert len(price_filtered) == 3  # 所有产品价格都是1000
    
    @pytest.mark.unit
    def test_recommendation_result_sorting(self, sample_recommendations):
        """测试推荐结果排序"""
        result = RecommendationResult(recommendations=sample_recommendations)
        
        # 按评分排序
        result.sort_by_score(reverse=False)  # 升序
        assert result.recommendations[0].score == 7.0
        assert result.recommendations[2].score == 9.0
        
        # 按置信度排序
        result.sort_by_confidence(reverse=True)  # 降序
        assert result.recommendations[0].confidence == 0.9
        assert result.recommendations[2].confidence == 0.7
    
    @pytest.mark.unit
    def test_recommendation_result_summary(self, sample_recommendations):
        """测试推荐结果摘要"""
        result = RecommendationResult(
            recommendations=sample_recommendations,
            total_analyzed=48,
            processing_time=2.5,
            strategy_used=RecommendationStrategy.BALANCED
        )
        
        summary = result.get_summary()
        
        assert summary["total_recommendations"] == 3
        assert summary["average_score"] == 8.0
        assert summary["average_confidence"] == 0.8
        assert summary["strategy_used"] == "balanced"
        assert summary["processing_time"] == 2.5
    
    @pytest.mark.unit
    def test_recommendation_result_serialization(self, sample_recommendations):
        """测试推荐结果序列化"""
        result = RecommendationResult(
            recommendations=sample_recommendations,
            total_analyzed=48,
            processing_time=2.5
        )
        
        # 转换为字典
        data = result.to_dict()
        assert "recommendations" in data
        assert "total_analyzed" in data
        assert "processing_time" in data
        
        # 转换为JSON
        json_str = result.to_json()
        assert isinstance(json_str, str)
        assert "recommendations" in json_str
        
        # 从JSON恢复
        restored = RecommendationResult.from_json(json_str)
        assert len(restored.recommendations) == 3
        assert restored.total_analyzed == 48
        assert restored.processing_time == 2.5