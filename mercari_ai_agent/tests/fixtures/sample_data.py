"""
测试用样本数据

该模块包含用于测试的样本数据，包括产品数据、查询数据、推荐数据等。

Author: Mercari AI Agent Team
"""

from datetime import datetime, timedelta
from mercari_agent.models import (
    ProductData, 
    SellerInfo, 
    ProductImages,
    ParsedQuery,
    Recommendation,
    RecommendationReason,
    RecommendationStrategy,
    QueryIntent
)


# =============================================================================
# 样本产品数据
# =============================================================================

SAMPLE_SELLER_INFO = [
    SellerInfo(
        seller_id="user123",
        seller_name="優良出品者",
        seller_rating=4.8,
        seller_reviews=256,
        seller_badges=["verified", "fast_shipping"],
        seller_location="東京都",
        seller_since=datetime(2020, 1, 15)
    ),
    SellerInfo(
        seller_id="user456",
        seller_name="信頼できる販売者",
        seller_rating=4.9,
        seller_reviews=512,
        seller_badges=["verified", "top_seller"],
        seller_location="大阪府",
        seller_since=datetime(2019, 6, 10)
    ),
    SellerInfo(
        seller_id="user789",
        seller_name="新規出品者",
        seller_rating=4.2,
        seller_reviews=23,
        seller_badges=["new_seller"],
        seller_location="神奈川県",
        seller_since=datetime(2023, 8, 1)
    )
]


SAMPLE_PRODUCT_IMAGES = [
    ProductImages(
        main_image="https://static.mercdn.net/item/detail/1.jpg",
        thumbnail_images=[
            "https://static.mercdn.net/thumb/1_1.jpg",
            "https://static.mercdn.net/thumb/1_2.jpg"
        ],
        additional_images=[
            "https://static.mercdn.net/detail/1_1.jpg",
            "https://static.mercdn.net/detail/1_2.jpg",
            "https://static.mercdn.net/detail/1_3.jpg"
        ]
    ),
    ProductImages(
        main_image="https://static.mercdn.net/item/detail/2.jpg",
        thumbnail_images=[
            "https://static.mercdn.net/thumb/2_1.jpg"
        ],
        additional_images=[
            "https://static.mercdn.net/detail/2_1.jpg",
            "https://static.mercdn.net/detail/2_2.jpg"
        ]
    )
]


SAMPLE_PRODUCTS = [
    ProductData(
        product_id="m12345678901",
        title="iPhone 14 Pro ケース 透明 クリア",
        price=1280.0,
        original_price=1680.0,
        currency="JPY",
        condition="新品、未使用",
        category="スマホアクセサリー",
        subcategory="iPhone用ケース",
        brand="Apple",
        model="iPhone 14 Pro",
        color="透明",
        size="iPhone 14 Pro用",
        material="TPU",
        description="iPhone 14 Pro専用の透明ケースです。高品質なTPU素材を使用し、端末をしっかり保護します。",
        seller_info=SAMPLE_SELLER_INFO[0],
        images=SAMPLE_PRODUCT_IMAGES[0],
        url="https://jp.mercari.com/item/m12345678901",
        posted_date=datetime.now() - timedelta(days=2),
        updated_date=datetime.now() - timedelta(days=1),
        view_count=156,
        like_count=23,
        shipping_fee=0.0,
        shipping_method="らくらくメルカリ便",
        shipping_days="1-2日で発送",
        tags=["iPhone", "ケース", "透明", "新品"],
        is_sold=False,
        is_featured=False
    ),
    ProductData(
        product_id="m23456789012",
        title="Nintendo Switch 有機ELモデル ホワイト",
        price=32800.0,
        original_price=37980.0,
        currency="JPY",
        condition="未使用に近い",
        category="テレビゲーム",
        subcategory="Nintendo Switch",
        brand="Nintendo",
        model="Switch OLED",
        color="ホワイト",
        description="Nintendo Switch有機ELモデルです。購入後数回使用しましたが、ほぼ新品同様の状態です。",
        seller_info=SAMPLE_SELLER_INFO[1],
        images=SAMPLE_PRODUCT_IMAGES[1],
        url="https://jp.mercari.com/item/m23456789012",
        posted_date=datetime.now() - timedelta(days=1),
        updated_date=datetime.now() - timedelta(hours=12),
        view_count=428,
        like_count=67,
        shipping_fee=0.0,
        shipping_method="らくらくメルカリ便",
        shipping_days="1-2日で発送",
        tags=["Nintendo", "Switch", "有機EL", "ホワイト"],
        is_sold=False,
        is_featured=True
    ),
    ProductData(
        product_id="m34567890123",
        title="ユニクロ ヒートテック 長袖Tシャツ Lサイズ",
        price=590.0,
        original_price=990.0,
        currency="JPY",
        condition="目立った傷や汚れなし",
        category="メンズファッション",
        subcategory="トップス",
        brand="UNIQLO",
        color="ブラック",
        size="L",
        material="ポリエステル",
        description="ユニクロのヒートテック長袖Tシャツです。数回着用しましたが状態は良好です。",
        seller_info=SAMPLE_SELLER_INFO[2],
        url="https://jp.mercari.com/item/m34567890123",
        posted_date=datetime.now() - timedelta(days=3),
        updated_date=datetime.now() - timedelta(days=2),
        view_count=89,
        like_count=12,
        shipping_fee=210.0,
        shipping_method="普通郵便",
        shipping_days="2-3日で発送",
        tags=["ユニクロ", "ヒートテック", "長袖", "Lサイズ"],
        is_sold=False,
        is_featured=False
    ),
    ProductData(
        product_id="m45678901234",
        title="MacBook Air M2 13インチ シルバー 256GB",
        price=128000.0,
        original_price=164800.0,
        currency="JPY",
        condition="やや傷や汚れあり",
        category="PC・タブレット",
        subcategory="ノートPC",
        brand="Apple",
        model="MacBook Air M2",
        color="シルバー",
        size="13インチ",
        description="MacBook Air M2 13インチです。使用感はありますが、動作に問題はありません。",
        seller_info=SAMPLE_SELLER_INFO[0],
        url="https://jp.mercari.com/item/m45678901234",
        posted_date=datetime.now() - timedelta(days=5),
        updated_date=datetime.now() - timedelta(days=4),
        view_count=892,
        like_count=156,
        shipping_fee=0.0,
        shipping_method="らくらくメルカリ便",
        shipping_days="1-2日で発送",
        tags=["MacBook", "Air", "M2", "Apple"],
        is_sold=False,
        is_featured=True
    ),
    ProductData(
        product_id="m56789012345",
        title="ポケモンカード ピカチュウ プロモ",
        price=2500.0,
        currency="JPY",
        condition="新品、未使用",
        category="おもちゃ・ホビー・グッズ",
        subcategory="トレーディングカード",
        brand="ポケモン",
        description="ポケモンカードのピカチュウプロモカードです。未開封品です。",
        seller_info=SAMPLE_SELLER_INFO[1],
        url="https://jp.mercari.com/item/m56789012345",
        posted_date=datetime.now() - timedelta(hours=6),
        updated_date=datetime.now() - timedelta(hours=3),
        view_count=234,
        like_count=45,
        shipping_fee=180.0,
        shipping_method="普通郵便",
        shipping_days="1-2日で発送",
        tags=["ポケモン", "カード", "ピカチュウ", "プロモ"],
        is_sold=False,
        is_featured=False
    )
]


# =============================================================================
# 样本查询数据
# =============================================================================

SAMPLE_QUERIES = [
    "iPhone ケース",
    "Nintendo Switch",
    "MacBook Air",
    "ユニクロ ヒートテック",
    "ポケモンカード",
    "3000円以下 iPhone ケース",
    "新品 Nintendo Switch",
    "中古 MacBook 10万円以下",
    "レディース バッグ ブランド",
    "メンズ 腕時計 カシオ"
]


SAMPLE_PARSED_QUERIES = [
    ParsedQuery(
        original_query="iPhone ケース",
        intent=QueryIntent.SEARCH,
        keywords=["iPhone", "ケース"],
        category="スマホアクセサリー",
        language="ja",
        complexity="simple"
    ),
    ParsedQuery(
        original_query="3000円以下 iPhone ケース",
        intent=QueryIntent.SEARCH,
        keywords=["iPhone", "ケース"],
        category="スマホアクセサリー",
        price_range={"min": 0, "max": 3000},
        language="ja",
        complexity="medium"
    ),
    ParsedQuery(
        original_query="新品 Nintendo Switch",
        intent=QueryIntent.SEARCH,
        keywords=["Nintendo", "Switch"],
        category="テレビゲーム",
        condition="新品",
        language="ja",
        complexity="medium"
    )
]


# =============================================================================
# 样本推荐数据
# =============================================================================

SAMPLE_RECOMMENDATION_REASONS = [
    RecommendationReason(
        type="price_advantage",
        description="市場価格より24%安い",
        importance=0.9,
        evidence={"market_price": 1680, "current_price": 1280, "savings": 400}
    ),
    RecommendationReason(
        type="quality",
        description="商品状態が新品で、卖家评价も高い",
        importance=0.8,
        evidence={"condition": "新品、未使用", "seller_rating": 4.8}
    ),
    RecommendationReason(
        type="popularity",
        description="閲覧数が多く、人気商品",
        importance=0.7,
        evidence={"view_count": 156, "like_count": 23}
    ),
    RecommendationReason(
        type="shipping",
        description="送料無料でお得",
        importance=0.6,
        evidence={"shipping_fee": 0, "shipping_method": "らくらくメルカリ便"}
    )
]


SAMPLE_RECOMMENDATIONS = [
    Recommendation(
        product=SAMPLE_PRODUCTS[0],
        rank=1,
        score=9.2,
        confidence=0.89,
        reasons=SAMPLE_RECOMMENDATION_REASONS[:2],
        purchase_advice="強く推奨します。価格、品質ともに優秀です。",
        strategy=RecommendationStrategy.BALANCED
    ),
    Recommendation(
        product=SAMPLE_PRODUCTS[1],
        rank=2,
        score=8.8,
        confidence=0.85,
        reasons=SAMPLE_RECOMMENDATION_REASONS[1:3],
        purchase_advice="推奨します。人気商品で状態も良好です。",
        strategy=RecommendationStrategy.BALANCED
    ),
    Recommendation(
        product=SAMPLE_PRODUCTS[2],
        rank=3,
        score=7.5,
        confidence=0.72,
        reasons=SAMPLE_RECOMMENDATION_REASONS[2:4],
        purchase_advice="検討の価値があります。",
        strategy=RecommendationStrategy.PRICE_ORIENTED
    ),
    Recommendation(
        product=SAMPLE_PRODUCTS[3],
        rank=4,
        score=8.0,
        confidence=0.78,
        reasons=SAMPLE_RECOMMENDATION_REASONS[:3],
        purchase_advice="良い選択です。",
        strategy=RecommendationStrategy.QUALITY_ORIENTED
    ),
    Recommendation(
        product=SAMPLE_PRODUCTS[4],
        rank=5,
        score=7.8,
        confidence=0.75,
        reasons=SAMPLE_RECOMMENDATION_REASONS[1:3],
        purchase_advice="コレクターにおすすめです。",
        strategy=RecommendationStrategy.TRENDING
    )
]


# =============================================================================
# 样本分析数据
# =============================================================================

SAMPLE_ANALYSIS_RESULTS = [
    {
        "product_id": "m12345678901",
        "price_score": 9.2,
        "quality_score": 8.8,
        "relevance_score": 9.5,
        "reputation_score": 8.9,
        "popularity_score": 7.8,
        "overall_score": 8.84,
        "analysis_time": 1.2,
        "market_comparison": {
            "average_price": 1580,
            "min_price": 980,
            "max_price": 2280,
            "price_position": "below_average"
        }
    },
    {
        "product_id": "m23456789012",
        "price_score": 8.5,
        "quality_score": 9.1,
        "relevance_score": 9.0,
        "reputation_score": 9.2,
        "popularity_score": 8.8,
        "overall_score": 8.92,
        "analysis_time": 1.8,
        "market_comparison": {
            "average_price": 35000,
            "min_price": 30000,
            "max_price": 40000,
            "price_position": "below_average"
        }
    }
]


# =============================================================================
# 样本错误数据
# =============================================================================

SAMPLE_ERROR_RESPONSES = [
    {
        "error_code": "NETWORK_ERROR",
        "message": "ネットワークエラーが発生しました",
        "details": "Connection timeout after 30 seconds"
    },
    {
        "error_code": "PARSE_ERROR",
        "message": "クエリの解析に失敗しました",
        "details": "Invalid query format"
    },
    {
        "error_code": "API_ERROR",
        "message": "外部APIエラー",
        "details": "Rate limit exceeded"
    }
]


# =============================================================================
# 样本API响应数据
# =============================================================================

SAMPLE_API_RESPONSES = {
    "search_success": {
        "success": True,
        "message": "検索が完了しました",
        "data": {
            "recommendations": [r.to_dict() for r in SAMPLE_RECOMMENDATIONS],
            "total_analyzed": 48,
            "processing_time": 2.5
        }
    },
    "search_empty": {
        "success": True,
        "message": "検索結果が見つかりませんでした",
        "data": {
            "recommendations": [],
            "total_analyzed": 0,
            "processing_time": 0.8
        }
    },
    "search_error": {
        "success": False,
        "message": "検索中にエラーが発生しました",
        "error": "Internal server error",
        "processing_time": 0.0
    },
    "health_check": {
        "status": "healthy",
        "version": "1.0.0",
        "environment": "testing",
        "services": {
            "llm_service": "healthy",
            "scraper_service": "healthy",
            "analysis_service": "healthy",
            "cache_manager": "healthy"
        },
        "uptime": 3600.0
    }
}


# =============================================================================
# 样本配置数据
# =============================================================================

SAMPLE_CONFIG = {
    "app_name": "Mercari AI Agent Test",
    "environment": "testing",
    "debug": True,
    "llm": {
        "default_provider": "mock",
        "enable_fallback": False
    },
    "scraper": {
        "max_concurrent_requests": 5,
        "enable_cache": True
    },
    "cache": {
        "enable_memory_cache": True,
        "enable_disk_cache": False,
        "enable_redis_cache": False
    },
    "log": {
        "level": "DEBUG",
        "console_output": True
    }
}


# =============================================================================
# 工具函数
# =============================================================================

def get_sample_product_by_id(product_id: str) -> ProductData:
    """根据ID获取样本产品"""
    for product in SAMPLE_PRODUCTS:
        if product.product_id == product_id:
            return product
    return None


def get_sample_products_by_category(category: str) -> list:
    """根据类别获取样本产品"""
    return [p for p in SAMPLE_PRODUCTS if p.category == category]


def get_sample_products_by_price_range(min_price: float, max_price: float) -> list:
    """根据价格范围获取样本产品"""
    return [p for p in SAMPLE_PRODUCTS 
            if p.price and min_price <= p.price <= max_price]


def create_sample_product(**kwargs) -> ProductData:
    """创建样本产品"""
    base_product = SAMPLE_PRODUCTS[0]
    product_data = base_product.to_dict()
    product_data.update(kwargs)
    return ProductData.from_dict(product_data)


def create_sample_recommendation(**kwargs) -> Recommendation:
    """创建样本推荐"""
    base_recommendation = SAMPLE_RECOMMENDATIONS[0]
    recommendation_data = base_recommendation.to_dict()
    recommendation_data.update(kwargs)
    return Recommendation.from_dict(recommendation_data)