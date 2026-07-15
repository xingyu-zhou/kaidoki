#!/usr/bin/env python3
"""
测试纯API策略的Mercari爬虫实现

测试流程：
1. 访问普通搜索页面获取Session Cookie和CSRF Token
2. 使用Cookie和CSRF Token调用API进行搜索
"""

import asyncio
import sys
import logging
from pathlib import Path

# 添加项目路径
sys.path.append('/Users/xingyu.zhou/ai_assistant/tech_blog/merukari/mercari_ai_agent_refactored/src')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_pure_api_scraper():
    """测试纯API策略爬虫"""
    from mercari_agent.infrastructure.scraping.scraper_service import ScraperService, ScrapingContext
    from mercari_agent.domain.entities.query import QueryEntity
    from mercari_agent.shared.config.app_config import AppConfig
    
    # 创建配置
    config = AppConfig()
    
    # 创建爬虫服务
    scraper_service = ScraperService(config)
    
    try:
        # 初始化服务
        print("🔧 初始化爬虫服务...")
        await scraper_service.initialize()
        
        # 显示服务信息
        service_info = scraper_service.get_service_info()
        print(f"📊 服务信息:")
        print(f"  策略: {service_info['available_strategies']}")
        print(f"  搜索API: {service_info['endpoints']['search_api']}")
        print(f"  Session初始化: {service_info['endpoints']['session_init']}")
        print(f"  认证支持: {service_info['authentication']}")
        
        # 健康检查
        print("\n🏥 健康检查...")
        health = await scraper_service.health_check()
        print(f"状态: {health['status']}")
        if health['status'] == 'healthy':
            print(f"Session已初始化: {health.get('session_initialized', 'unknown')}")
            print(f"CSRF Token: {health.get('has_csrf_token', 'unknown')}")
            print(f"Cookie数量: {health.get('cookies_count', 'unknown')}")
        
        # 创建查询
        query = QueryEntity(
            original_query="iPhone 14",
            keywords=["iPhone", "14"],
            price_min=30000,
            price_max=80000
        )
        
        # 创建爬虫上下文
        context = ScrapingContext(
            query=query,
            max_pages=2,
            max_products=10
        )
        
        print(f"\n🔍 开始API搜索...")
        print(f"查询: {query.original_query}")
        print(f"价格范围: ¥{query.price_min:,} - ¥{query.price_max:,}")
        
        # 执行搜索
        result = await scraper_service.scrape(context)
        
        print(f"\n✅ 搜索完成!")
        print(f"找到产品数量: {result.total_found}")
        print(f"使用策略: {result.strategy_used.value}")
        print(f"处理时间: {result.processing_time:.2f}秒")
        print(f"爬取页面: {result.pages_scraped}")
        
        # 显示产品信息
        if result.products:
            print(f"\n📦 产品列表:")
            for i, product in enumerate(result.products, 1):
                print(f"{i}. {product.title}")
                print(f"   价格: ¥{product.price:,}")
                print(f"   状态: {product.condition}")
                print(f"   品牌: {product.brand}")
                print(f"   URL: {product.url}")
                print()
        else:
            print("❌ 未找到任何产品")
        
        # 显示爬虫统计信息
        stats = scraper_service.scraper.get_stats()
        print("📊 爬虫统计:")
        print(f"策略: {stats['strategy']}")
        print(f"总请求: {stats['total_requests']}")
        print(f"成功请求: {stats['successful_requests']}")
        print(f"成功率: {stats['success_rate']}")
        print(f"Session初始化: {stats['session_initialized']}")
        print(f"CSRF Token: {stats['has_csrf_token']}")
        print(f"Cookie数量: {stats['session_cookies_count']}")
        
        # 测试不同的查询
        print(f"\n🔍 测试第二个查询...")
        query2 = QueryEntity(
            original_query="MacBook",
            keywords=["MacBook"],
            price_min=50000,
            price_max=200000
        )
        
        context2 = ScrapingContext(
            query=query2,
            max_pages=1,
            max_products=5
        )
        
        result2 = await scraper_service.scrape(context2)
        print(f"第二次搜索结果: {result2.total_found} 个产品")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # 关闭服务
        await scraper_service.close()
        print("\n🔚 服务已关闭")

if __name__ == "__main__":
    print("🚀 开始测试纯API策略爬虫...")
    asyncio.run(test_pure_api_scraper())
    print("\n✅ 测试完成!")
