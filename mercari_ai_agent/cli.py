#!/usr/bin/env python3
"""
Mercari AI Agent CLI工具
用于测试和调试推荐引擎功能
"""

import sys
import asyncio
import logging
from pathlib import Path
from typing import List, Optional

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from mercari_agent.core.recommendation_engine import (
    RecommendationEngine,
    RecommendationStrategy,
    RecommendationContext
)
from mercari_agent.models.product import ProductData
from mercari_agent.models.query import ParsedQuery, QueryIntent
from mercari_agent.analyzers.scoring_engine import ScoringEngine
from mercari_agent.analyzers.ranking_system import RankingSystem
from mercari_agent.utils.logger import setup_logging, get_logger

# 设置日志
setup_logging(level=logging.DEBUG)
logger = get_logger(__name__)

def create_test_products() -> List[ProductData]:
    """创建测试产品数据"""
    test_products = [
        ProductData(
            id="1",
            title="iPhone 15 Pro Max 1TB 自然钛",
            description="全新iPhone 15 Pro Max，1TB存储，自然钛色，原装配件齐全",
            price=89800,
            currency="JPY",
            condition="新品",
            category="スマートフォン",
            brand="Apple",
            seller_name="信用卖家A",
            seller_rating=4.8,
            images=["image1.jpg", "image2.jpg"],
            url="https://mercari.com/item/1",
            view_count=1200,
            like_count=80,
            availability=True
        ),
        ProductData(
            id="2", 
            title="iPhone 15 Pro Max 1TB シルバー",
            description="中古美品iPhone 15 Pro Max，1TB，银色，9成新",
            price=78000,
            currency="JPY",
            condition="中古",
            category="スマートフォン",
            brand="Apple",
            seller_name="信用卖家B",
            seller_rating=4.5,
            images=["image3.jpg"],
            url="https://mercari.com/item/2",
            view_count=800,
            like_count=45,
            availability=True
        ),
        ProductData(
            id="3",
            title="iPhone 14 Pro Max 1TB ゴールド",
            description="iPhone 14 Pro Max 金色 1TB 状态良好",
            price=68000,
            currency="JPY",
            condition="中古",
            category="スマートフォン", 
            brand="Apple",
            seller_name="信用卖家C",
            seller_rating=4.2,
            images=["image4.jpg"],
            url="https://mercari.com/item/3",
            view_count=500,
            like_count=20,
            availability=True
        )
    ]
    return test_products

def create_test_query(query_text: str) -> ParsedQuery:
    """创建测试查询对象"""
    return ParsedQuery(
        original_query=query_text,
        normalized_query=query_text.lower(),
        keywords=["iphone", "15", "pro", "max", "1tb"],
        intent=QueryIntent.PURCHASE,
        category="スマートフォン",
        brand="Apple",
        price_min=0,
        price_max=100000,
        condition=None
    )

async def test_recommendation_engine():
    """测试推荐引擎"""
    try:
        print("🔍 初始化推荐引擎组件...")
        
        # 初始化组件
        scoring_engine = ScoringEngine()
        ranking_system = RankingSystem()
        recommendation_engine = RecommendationEngine(scoring_engine, ranking_system)
        
        print("✅ 推荐引擎初始化完成")
        
        # 创建测试数据
        print("\n📦 创建测试产品数据...")
        products = create_test_products()
        print(f"✅ 创建了 {len(products)} 个测试产品")
        
        # 创建测试查询
        query_text = "iPhone 15 Pro Max 1TB 10万円以下"
        print(f"\n🔍 创建测试查询: {query_text}")
        parsed_query = create_test_query(query_text)
        print("✅ 查询创建完成")
        
        # 创建推荐上下文
        context = RecommendationContext(
            query=parsed_query,
            strategy=RecommendationStrategy.BALANCED
        )
        
        # 执行推荐
        print("\n🎯 开始生成推荐...")
        result = await recommendation_engine.recommend(products, context, max_results=5)
        
        # 显示结果
        print("\n" + "="*50)
        print("📊 推荐结果")
        print("="*50)
        
        if result.recommendations:
            print(f"✅ 找到 {len(result.recommendations)} 个推荐")
            print(f"📈 总分析产品数: {result.total_analyzed}")
            print(f"🛡️ 使用策略: {result.strategy_used.value}")
            print(f"⏱️ 处理时间: {result.processing_time:.3f}s")
            
            print("\n🏆 推荐列表:")
            for rec in result.recommendations:
                print(f"\n{rec.rank}. {rec.product.title}")
                print(f"   💰 价格: ¥{rec.product.price:,}")
                print(f"   ⭐ 评分: {rec.score:.2f}")
                print(f"   🔗 置信度: {rec.confidence:.2f}")
                if rec.reasons:
                    print(f"   💡 推荐理由: {', '.join([r.description for r in rec.reasons])}")
                if rec.purchase_advice:
                    print(f"   📝 购买建议: {rec.purchase_advice}")
        else:
            print("❌ 没有生成推荐结果")
            print("这可能是推荐引擎空结果问题的体现")
            
    except Exception as e:
        print(f"❌ 推荐引擎测试失败: {e}")
        logger.exception("推荐引擎测试异常")
        return False
    
    return len(result.recommendations) > 0 if 'result' in locals() else False

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Mercari AI Agent CLI工具")
    parser.add_argument("command", choices=["recommend", "parse", "test"], 
                       help="要执行的命令")
    parser.add_argument("query", nargs="?", default="iPhone 15 Pro Max 1TB 10万円以下",
                       help="查询字符串")
    
    args = parser.parse_args()
    
    if args.command == "recommend" or args.command == "test":
        print("🚀 启动推荐引擎测试...")
        success = asyncio.run(test_recommendation_engine())
        if success:
            print("\n✅ 推荐引擎测试成功")
        else:
            print("\n❌ 推荐引擎测试失败")
            sys.exit(1)
    
    elif args.command == "parse":
        print(f"📝 解析查询: {args.query}")
        # 这里可以添加查询解析测试
        print("查询解析功能待实现")

if __name__ == "__main__":
    main()