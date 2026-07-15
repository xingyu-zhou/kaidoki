#!/usr/bin/env python3
"""
测试 AnalysisService.generate_recommendations 方法

该脚本验证新实现的 generate_recommendations 方法是否能正常工作。
"""

import asyncio
import sys
import os
from datetime import datetime
from typing import List, Dict, Any

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mercari_agent.services.analysis_service import AnalysisService
from mercari_agent.models.product import ProductData
from mercari_agent.models.query import ParsedQuery


def create_test_products() -> List[ProductData]:
    """创建测试产品数据"""
    products = [
        ProductData(
            title="iPhone 13 Pro 128GB シルバー",
            price=85000,
            url="https://jp.mercari.com/item/1",
            description="iPhone 13 Pro 128GB シルバー 美品 付属品完備。傷なし、動作良好。",
            condition="未使用に近い",
            category="家電・スマホ・カメラ",
            brand="Apple",
            seller_name="tech_seller",
            seller_rating=4.8,
            images=["img1.jpg", "img2.jpg", "img3.jpg"],
            like_count=25,
            view_count=150,
            scraped_at=datetime.now()
        ),
        ProductData(
            title="iPhone 12 64GB ブラック",
            price=65000,
            url="https://jp.mercari.com/item/2",
            description="iPhone 12 64GB ブラック 普通の中古品。動作問題なし。",
            condition="やや傷や汚れあり",
            category="家電・スマホ・カメラ",
            brand="Apple",
            seller_name="mobile_store",
            seller_rating=4.2,
            images=["img4.jpg", "img5.jpg"],
            like_count=12,
            view_count=80,
            scraped_at=datetime.now()
        ),
        ProductData(
            title="Samsung Galaxy S21 128GB",
            price=55000,
            url="https://jp.mercari.com/item/3",
            description="Samsung Galaxy S21 128GB 状態良好。箱なし。",
            condition="目立った傷や汚れなし",
            category="家電・スマホ・カメラ",
            brand="Samsung",
            seller_name="android_fan",
            seller_rating=4.5,
            images=["img6.jpg"],
            like_count=8,
            view_count=45,
            scraped_at=datetime.now()
        ),
        ProductData(
            title="古いAndroid端末",
            price=15000,
            url="https://jp.mercari.com/item/4",
            description="古いAndroid端末。動作不安定。",
            condition="全体的に状態が悪い",
            category="家電・スマホ・カメラ",
            brand="Unknown",
            seller_name="budget_seller",
            seller_rating=3.5,
            images=[],
            like_count=2,
            view_count=15,
            scraped_at=datetime.now()
        ),
        ProductData(
            title="iPad Pro 11インチ 256GB",
            price=95000,
            url="https://jp.mercari.com/item/5",
            description="iPad Pro 11インチ 256GB 新品未使用。Apple Pencil付属。",
            condition="新品・未使用",
            category="家電・スマホ・カメラ",
            brand="Apple",
            seller_name="premium_seller",
            seller_rating=4.9,
            images=["img7.jpg", "img8.jpg", "img9.jpg", "img10.jpg"],
            like_count=45,
            view_count=200,
            scraped_at=datetime.now()
        )
    ]
    return products


def create_test_user_preferences() -> Dict[str, Any]:
    """创建测试用户偏好"""
    return {
        "price_weight": 0.4,        # 价格权重
        "quality_weight": 0.3,      # 质量权重
        "seller_weight": 0.2,       # 卖家权重
        "condition_weight": 0.1,    # 状态权重
        "popularity_weight": 0.05,  # 热度权重
        "max_price": 80000,         # 最大价格
        "min_price": 30000,         # 最小价格
        "preferred_conditions": ["新品・未使用", "未使用に近い"],  # 偏好状态
        "preferred_categories": ["家電・スマホ・カメラ"],         # 偏好类别
        "risk_tolerance": 0.3       # 风险容忍度
    }


async def test_generate_recommendations():
    """测试 generate_recommendations 方法"""
    print("=" * 60)
    print("测试 AnalysisService.generate_recommendations 方法")
    print("=" * 60)
    
    try:
        # 1. 创建 AnalysisService 实例
        print("\n1. 初始化 AnalysisService...")
        analysis_service = AnalysisService()
        print("✓ AnalysisService 初始化成功")
        
        # 2. 创建测试数据
        print("\n2. 创建测试数据...")
        test_products = create_test_products()
        user_preferences = create_test_user_preferences()
        
        print(f"✓ 创建了 {len(test_products)} 个测试产品")
        print(f"✓ 创建了用户偏好设置")
        
        # 3. 调用 generate_recommendations 方法
        print("\n3. 调用 generate_recommendations 方法...")
        recommendations = await analysis_service.generate_recommendations(
            user_preferences=user_preferences,
            search_results=test_products,
            max_results=5
        )
        
        print(f"✓ 成功生成 {len(recommendations)} 个推荐")
        
        # 4. 验证结果
        print("\n4. 验证推荐结果...")
        
        if not recommendations:
            print("✗ 推荐结果为空")
            return False
        
        # 验证每个推荐的结构
        required_fields = [
            "rank", "product_id", "title", "price", "final_score",
            "recommendation_reason", "pros", "cons", "match_score"
        ]
        
        for i, rec in enumerate(recommendations):
            print(f"\n推荐 {i+1}:")
            print(f"  标题: {rec.get('title', 'N/A')}")
            print(f"  价格: ¥{rec.get('price', 0):,}")
            print(f"  综合评分: {rec.get('final_score', 0):.2f}")
            print(f"  匹配度: {rec.get('match_score', 0):.2f}")
            print(f"  推荐理由: {rec.get('recommendation_reason', 'N/A')}")
            print(f"  优点: {', '.join(rec.get('pros', []))}")
            print(f"  缺点: {', '.join(rec.get('cons', []))}")
            
            # 验证必需字段
            missing_fields = [field for field in required_fields if field not in rec]
            if missing_fields:
                print(f"✗ 推荐 {i+1} 缺少字段: {missing_fields}")
                return False
        
        print("\n✓ 所有推荐都包含必需字段")
        
        # 5. 验证排序
        print("\n5. 验证推荐排序...")
        scores = [rec["final_score"] for rec in recommendations]
        is_sorted = all(scores[i] >= scores[i+1] for i in range(len(scores)-1))
        
        if is_sorted:
            print("✓ 推荐按评分正确排序")
        else:
            print("✗ 推荐排序不正确")
            return False
        
        # 6. 测试空结果情况
        print("\n6. 测试空搜索结果...")
        empty_recommendations = await analysis_service.generate_recommendations(
            user_preferences=user_preferences,
            search_results=[],
            max_results=5
        )
        
        if len(empty_recommendations) == 0:
            print("✓ 空搜索结果正确处理")
        else:
            print("✗ 空搜索结果处理失败")
            return False
        
        # 7. 测试空偏好情况
        print("\n7. 测试空用户偏好...")
        default_recommendations = await analysis_service.generate_recommendations(
            user_preferences={},
            search_results=test_products[:2],
            max_results=2
        )
        
        if len(default_recommendations) == 2:
            print("✓ 空用户偏好使用默认设置")
        else:
            print("✗ 空用户偏好处理失败")
            return False
        
        print("\n" + "=" * 60)
        print("✓ 所有测试通过！generate_recommendations 方法工作正常")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    print("开始测试 AnalysisService.generate_recommendations 方法...")
    
    success = await test_generate_recommendations()
    
    if success:
        print("\n🎉 测试完成：方法实现正确！")
        sys.exit(0)
    else:
        print("\n❌ 测试失败：需要修复问题")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())