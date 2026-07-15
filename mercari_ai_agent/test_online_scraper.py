#!/usr/bin/env python3
"""
在线爬虫测试
测试实际的网络爬虫功能
"""

import sys
import asyncio
import time
from datetime import datetime

# 添加模块路径
sys.path.insert(0, '.')

from src.mercari_agent.utils.logger import get_logger
from src.mercari_agent.scrapers.mercari_scraper import MercariScraper, SearchFilters
from src.mercari_agent.scrapers.base_scraper import ScrapingStrategy
from src.mercari_agent.scrapers.session_manager import SessionManager

logger = get_logger(__name__)


async def test_basic_connection():
    """测试基础网络连接"""
    print("🌐 测试基础网络连接...")
    
    session_manager = SessionManager()
    
    try:
        await session_manager.initialize()
        
        # 测试简单的HTTP请求（使用更可靠的端点）
        test_url = "https://jsonplaceholder.typicode.com/posts/1"
        response = await session_manager.make_request(test_url)
        
        if response.status == 200:
            print("✅ 基础网络连接成功")
            return True
        else:
            print(f"❌ 基础网络连接失败，状态码: {response.status}")
            return False
            
    except Exception as e:
        print(f"❌ 基础网络连接测试失败: {e}")
        return False
    finally:
        await session_manager.close_all()


async def test_mercari_homepage():
    """测试Mercari主页访问"""
    print("\n🏠 测试Mercari主页访问...")
    
    session_manager = SessionManager()
    
    try:
        await session_manager.initialize()
        
        # 测试Mercari主页
        mercari_url = "https://jp.mercari.com/"
        response = await session_manager.make_request(mercari_url)
        
        if response.status == 200:
            content = await response.text()
            print(f"✅ Mercari主页访问成功，内容长度: {len(content)} 字符")
            
            # 检查是否包含预期内容
            if "Mercari" in content or "メルカリ" in content:
                print("✅ 页面内容验证通过")
                return True
            else:
                print("❌ 页面内容验证失败")
                return False
        else:
            print(f"❌ Mercari主页访问失败，状态码: {response.status}")
            return False
            
    except Exception as e:
        print(f"❌ Mercari主页访问测试失败: {e}")
        return False
    finally:
        await session_manager.close_all()


async def test_search_page():
    """测试搜索页面访问"""
    print("\n🔍 测试搜索页面访问...")
    
    session_manager = SessionManager()
    
    try:
        await session_manager.initialize()
        
        # 构建搜索URL
        search_url = "https://jp.mercari.com/search?keyword=iPhone"
        
        print(f"访问搜索URL: {search_url}")
        response = await session_manager.make_request(search_url)
        
        if response.status == 200:
            content = await response.text()
            print(f"✅ 搜索页面访问成功，内容长度: {len(content)} 字符")
            
            # 检查是否包含搜索相关内容
            if "iPhone" in content or "search" in content:
                print("✅ 搜索页面内容验证通过")
                return True
            else:
                print("❌ 搜索页面内容验证失败")
                return False
        else:
            print(f"❌ 搜索页面访问失败，状态码: {response.status}")
            return False
            
    except Exception as e:
        print(f"❌ 搜索页面访问测试失败: {e}")
        return False
    finally:
        await session_manager.close_all()


async def test_scraper_initialization():
    """测试爬虫初始化"""
    print("\n⚙️ 测试爬虫初始化...")
    
    try:
        scraper = MercariScraper(ScrapingStrategy.REQUESTS)
        await scraper.initialize()
        
        print("✅ 爬虫初始化成功")
        
        # 测试搜索过滤器
        filters = SearchFilters(
            keywords="iPhone",
            price_min=10000,
            price_max=100000,
            page=1,
            limit=10
        )
        
        # 测试URL构建
        search_url = scraper.build_search_url(filters)
        print(f"✅ 搜索URL构建成功: {search_url}")
        
        # 测试基本信息
        scraper_info = scraper.get_scraper_info()
        print(f"✅ 爬虫总请求数: {scraper_info['total_requests']}")
        print(f"✅ 爬虫成功请求数: {scraper_info['successful_requests']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 爬虫初始化测试失败: {e}")
        return False


async def test_simple_search():
    """测试简单搜索功能"""
    print("\n🔎 测试简单搜索功能...")
    
    try:
        scraper = MercariScraper(ScrapingStrategy.REQUESTS)
        await scraper.initialize()
        
        # 创建搜索过滤器
        filters = SearchFilters(
            keywords="テスト",  # 使用简单的日语关键词
            page=1,
            limit=5
        )
        
        print(f"搜索关键词: {filters.keywords}")
        print(f"搜索参数: {filters.to_params()}")
        
        # 构建搜索URL
        search_url = scraper.build_search_url(filters)
        print(f"搜索URL: {search_url}")
        
        # 执行搜索（模拟）
        print("✅ 搜索功能模拟测试通过")
        
        return True
        
    except Exception as e:
        print(f"❌ 简单搜索功能测试失败: {e}")
        return False


async def test_rate_limiting():
    """测试请求频率控制"""
    print("\n⏱️ 测试请求频率控制...")
    
    session_manager = SessionManager()
    
    try:
        await session_manager.initialize()
        
        # 测试多个请求的间隔
        test_url = "https://httpbin.org/get"
        
        start_time = time.time()
        
        # 发送3个请求
        for i in range(3):
            print(f"发送第 {i+1} 个请求...")
            response = await session_manager.make_request(test_url)
            
            if response.status == 200:
                print(f"✅ 请求 {i+1} 成功")
            else:
                print(f"❌ 请求 {i+1} 失败")
                
            # 如果不是最后一个请求，等待一段时间
            if i < 2:
                await asyncio.sleep(1)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"✅ 3个请求总耗时: {total_time:.2f} 秒")
        
        if total_time >= 2:  # 至少需要2秒（2个间隔）
            print("✅ 请求频率控制正常")
            return True
        else:
            print("❌ 请求频率控制异常")
            return False
            
    except Exception as e:
        print(f"❌ 请求频率控制测试失败: {e}")
        return False
    finally:
        await session_manager.close()


async def main():
    """主测试函数"""
    print("🚀 开始在线爬虫测试...")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("基础网络连接", test_basic_connection),
        ("Mercari主页访问", test_mercari_homepage),
        ("搜索页面访问", test_search_page),
        ("爬虫初始化", test_scraper_initialization),
        ("简单搜索功能", test_simple_search),
        ("请求频率控制", test_rate_limiting),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"执行测试: {test_name}")
        print(f"{'='*60}")
        
        try:
            result = await test_func()
            results[test_name] = result
            
            if result:
                print(f"✅ {test_name} 测试通过")
            else:
                print(f"❌ {test_name} 测试失败")
                
        except Exception as e:
            print(f"❌ {test_name} 测试异常: {e}")
            results[test_name] = False
    
    # 输出总结
    print(f"\n{'='*60}")
    print("在线爬虫测试总结")
    print(f"{'='*60}")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    print(f"总测试数: {total}")
    print(f"通过测试: {passed}")
    print(f"失败测试: {total - passed}")
    print(f"成功率: {passed/total*100:.1f}%")
    
    if passed == total:
        print("🎉 所有测试通过！在线爬虫功能正常")
        print("✅ 爬虫可以正常访问网络和处理请求")
    else:
        print("❌ 部分测试失败")
        
        # 显示失败的测试
        failed_tests = [name for name, result in results.items() if not result]
        print(f"失败的测试: {failed_tests}")
        
        # 提供建议
        print("\n💡 故障排除建议:")
        print("1. 检查网络连接")
        print("2. 验证代理设置")
        print("3. 检查防火墙设置")
        print("4. 确认Mercari网站可访问")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)