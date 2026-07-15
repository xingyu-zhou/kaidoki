#!/usr/bin/env python3
"""
测试Session+API策略的Mercari爬虫实现

测试流程：
1. 访问普通搜索页面获取Session Cookie
2. 提取CSRF Token
3. 使用Cookie和CSRF Token调用API
"""

import asyncio
import sys
import logging
from pathlib import Path

# 添加项目路径
sys.path.append('/Users/xingyu.zhou/ai_assistant/tech_blog/merukari/mercari_ai_agent_refactored/src')

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_session_api_scraper():
    """测试Session+API策略爬虫"""
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
        
        # 显示初始状态
        service_info = scraper_service.get_service_info()
        print(f"📊 服务信息:")
        print(f"  可用策略: {service_info['available_strategies']}")
        print(f"  API端点: {service_info['endpoints']['search_api']}")
        print(f"  网页端点: {service_info['endpoints']['search_web']}")
        
        # 健康检查（会触发Session初始化）
        print("\n🏥 健康检查...")
        health = await scraper_service.health_check()
        print(f"状态: {health['status']}")
        if health['status'] == 'healthy':
            print(f"Session初始化: {health.get('session_initialized', 'unknown')}")
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
        
        print(f"\n🔍 开始搜索产品...")
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
            for i, product in enumerate(result.products[:5], 1):
                print(f"{i}. {product.title}")
                print(f"   价格: ¥{product.price:,}")
                print(f"   状态: {product.condition}")
                print(f"   URL: {product.url}")
                print()
        else:
            print("❌ 未找到任何产品")
        
        # 显示统计信息
        stats = scraper_service.scraper.get_stats()
        print("📊 爬虫统计信息:")
        print(f"策略: {stats['strategy']}")
        print(f"总请求: {stats['total_requests']}")
        print(f"成功请求: {stats['successful_requests']}")
        print(f"成功率: {stats['success_rate']}")
        print(f"Session状态: {stats['session_initialized']}")
        print(f"CSRF Token: {stats['has_csrf_token']}")
        print(f"Cookie数量: {stats['session_cookies_count']}")
        
        # 测试单个产品详情（如果有产品的话）
        if result.products:
            print(f"\n🔍 测试产品详情获取...")
            first_product = result.products[0]
            detail = await scraper_service.get_product_detail(first_product.url)
            if detail:
                print(f"✅ 成功获取产品详情: {detail.title}")
            else:
                print("❌ 获取产品详情失败")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # 关闭服务
        await scraper_service.close()
        print("\n🔚 服务已关闭")

async def test_session_initialization():
    """单独测试Session初始化"""
    from mercari_agent.infrastructure.scraping.scraper_service import MercariScraper
    from mercari_agent.shared.config.app_config import AppConfig
    
    print("\n🧪 测试Session初始化...")
    
    config = AppConfig()
    scraper = MercariScraper(config)
    
    try:
        await scraper.initialize()
        
        print("🔧 初始化Session...")
        await scraper._initialize_session()
        
        print(f"✅ Session初始化完成")
        print(f"Session Cookies: {list(scraper.session_cookies.keys())}")
        print(f"CSRF Token: {'已获取' if scraper.csrf_token else '未获取'}")
        
        if scraper.csrf_token:
            print(f"CSRF Token预览: {scraper.csrf_token[:20]}...")
        
        for name, value in scraper.session_cookies.items():
            print(f"Cookie {name}: {value[:20]}...")
        
    except Exception as e:
        print(f"❌ Session初始化失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await scraper.close()

if __name__ == "__main__":
    print("🚀 开始测试Session+API策略爬虫...")
    
    # 先测试Session初始化
    asyncio.run(test_session_initialization())
    
    # 再测试完整的爬虫流程
    asyncio.run(test_session_api_scraper())
    
    print("\n✅ 测试完成!")
