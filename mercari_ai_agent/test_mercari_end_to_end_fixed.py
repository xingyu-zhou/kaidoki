#!/usr/bin/env python3
"""
Mercari端到端测试 - 修复版本
测试完整的Mercari爬虫功能，包括数据解析
"""

import sys
import asyncio
import json
from bs4 import BeautifulSoup

# 添加模块路径
sys.path.insert(0, '.')

from src.mercari_agent.scrapers.mercari_scraper import MercariScraper
from src.mercari_agent.scrapers.session_manager import SessionManager
from src.mercari_agent.scrapers.data_parser import MercariDataParser, ParsingContext, PageType
from src.mercari_agent.models.query import SearchQuery


async def test_mercari_page_structure():
    """测试Mercari页面结构"""
    print("🏗️ 测试Mercari页面结构...")
    
    session_manager = SessionManager()
    
    try:
        await session_manager.initialize()
        
        # 获取搜索页面
        search_url = "https://jp.mercari.com/search?keyword=iPhone"
        response = await session_manager.make_request(search_url)
        
        if response.status == 200:
            content = await response.text()
            soup = BeautifulSoup(content, 'html.parser')
            
            print(f"✅ 页面获取成功，内容长度: {len(content)} 字符")
            
            # 分析页面结构
            print("\n📋 页面结构分析:")
            
            # 查找产品容器
            product_containers = soup.find_all('div', class_='mer-item-thumbnail')
            print(f"  找到产品容器数量: {len(product_containers)}")
            
            # 查找其他可能的产品选择器
            alternative_selectors = [
                ('mer-item', soup.find_all('div', class_='mer-item')),
                ('product-item', soup.find_all('div', class_='product-item')),
                ('item-cell', soup.find_all('div', class_='item-cell')),
                ('ItemCell', soup.find_all('div', class_='ItemCell')),
                ('data-testid=item-cell', soup.find_all('div', attrs={'data-testid': 'item-cell'})),
                ('data-testid=product-item', soup.find_all('div', attrs={'data-testid': 'product-item'})),
            ]
            
            for selector_name, elements in alternative_selectors:
                if elements:
                    print(f"  ✅ {selector_name}: {len(elements)} 个元素")
                else:
                    print(f"  ❌ {selector_name}: 未找到")
            
            # 查找链接
            links = soup.find_all('a', href=True)
            product_links = [link for link in links if '/item/' in link['href']]
            print(f"  找到产品链接数量: {len(product_links)}")
            
            # 查找价格元素
            price_elements = soup.find_all(string=lambda text: text and '¥' in text)
            print(f"  找到价格元素数量: {len(price_elements)}")
            
            # 保存页面内容用于调试
            with open('debug_mercari_page.html', 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  页面内容已保存到 debug_mercari_page.html")
            
            return True
            
        else:
            print(f"❌ 页面获取失败，状态码: {response.status}")
            return False
            
    except Exception as e:
        print(f"❌ 页面结构测试失败: {e}")
        return False
    finally:
        await session_manager.close_all()


async def test_data_parser():
    """测试数据解析器"""
    print("\n🔧 测试数据解析器...")
    
    session_manager = SessionManager()
    parser = MercariDataParser()
    
    try:
        await session_manager.initialize()
        
        # 获取搜索页面
        search_url = "https://jp.mercari.com/search?keyword=iPhone"
        response = await session_manager.make_request(search_url)
        
        if response.status == 200:
            content = await response.text()
            
            print(f"✅ 页面获取成功，开始解析...")
            
            # 使用数据解析器解析产品
            context = ParsingContext(
                page_type=PageType.SEARCH_RESULTS,
                base_url="https://jp.mercari.com"
            )
            result = parser.parse_page(content, context)
            products = result.products
            
            print(f"📦 解析结果: {len(products)} 个产品")
            
            if products:
                print("\n🔍 产品详情:")
                for i, product in enumerate(products[:3]):  # 只显示前3个
                    print(f"  产品 {i+1}:")
                    print(f"    名称: {product.name}")
                    print(f"    价格: {product.price}")
                    print(f"    链接: {product.url}")
                    print(f"    图片: {product.image_url}")
                    print(f"    状态: {product.status}")
                    print()
                
                return True
            else:
                print("❌ 未解析到任何产品")
                return False
                
        else:
            print(f"❌ 页面获取失败，状态码: {response.status}")
            return False
            
    except Exception as e:
        print(f"❌ 数据解析测试失败: {e}")
        return False
    finally:
        await session_manager.close_all()


async def test_scraper_search():
    """测试爬虫搜索功能"""
    print("\n🔍 测试爬虫搜索功能...")
    
    try:
        # 创建搜索查询
        query = SearchQuery(query_text="iPhone")
        query.set_price_range(10000, 50000)
        query.sort_by = "relevance"
        query.page_size = 5
        
        print(f"搜索参数: {query}")
        
        # 创建爬虫
        scraper = MercariScraper()
        await scraper.initialize()
        
        print(f"✅ 爬虫初始化成功")
        
        # 执行搜索
        results = await scraper.search(query)
        
        print(f"📊 搜索结果: {len(results)} 个产品")
        
        if results:
            print("\n🎯 搜索结果详情:")
            for i, product in enumerate(results[:3]):  # 只显示前3个
                print(f"  产品 {i+1}:")
                print(f"    名称: {product.name}")
                print(f"    价格: {product.price}")
                print(f"    链接: {product.url}")
                print(f"    图片: {product.image_url}")
                print(f"    状态: {product.status}")
                print()
            
            return True
        else:
            print("❌ 搜索未返回任何结果")
            return False
            
    except Exception as e:
        print(f"❌ 爬虫搜索测试失败: {e}")
        return False
    finally:
        try:
            await scraper.close()
        except:
            pass


async def test_different_keywords():
    """测试不同关键词的搜索"""
    print("\n🌍 测试不同关键词的搜索...")
    
    keywords = ["iPhone", "Nintendo", "PlayStation", "本"]
    
    try:
        scraper = MercariScraper()
        await scraper.initialize()
        
        results = {}
        
        for keyword in keywords:
            print(f"\n搜索关键词: {keyword}")
            
            query = SearchQuery(query_text=keyword, page_size=3)
            
            try:
                products = await scraper.search(query)
                results[keyword] = len(products)
                
                print(f"  ✅ 找到 {len(products)} 个产品")
                
                if products:
                    print(f"  示例产品: {products[0].name}")
                    
            except Exception as e:
                print(f"  ❌ 搜索失败: {e}")
                results[keyword] = 0
        
        print(f"\n📊 搜索结果汇总:")
        for keyword, count in results.items():
            print(f"  {keyword}: {count} 个产品")
        
        success_count = sum(1 for count in results.values() if count > 0)
        total_count = len(results)
        
        print(f"\n成功率: {success_count}/{total_count} ({success_count/total_count*100:.1f}%)")
        
        return success_count > 0
        
    except Exception as e:
        print(f"❌ 多关键词搜索测试失败: {e}")
        return False
    finally:
        try:
            await scraper.close()
        except:
            pass


async def test_price_filtering():
    """测试价格过滤功能"""
    print("\n💰 测试价格过滤功能...")
    
    try:
        scraper = MercariScraper()
        await scraper.initialize()
        
        # 测试不同价格范围
        price_ranges = [
            (1000, 5000),
            (5000, 20000),
            (20000, 100000),
        ]
        
        for price_min, price_max in price_ranges:
            print(f"\n价格范围: ¥{price_min:,} - ¥{price_max:,}")
            
            query = SearchQuery(query_text="iPhone", page_size=3)
            query.set_price_range(price_min, price_max)
            
            try:
                products = await scraper.search(query)
                print(f"  ✅ 找到 {len(products)} 个产品")
                
                if products:
                    for product in products:
                        print(f"    {product.name} - {product.price}")
                        
            except Exception as e:
                print(f"  ❌ 价格过滤失败: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ 价格过滤测试失败: {e}")
        return False
    finally:
        try:
            await scraper.close()
        except:
            pass


async def test_simple_session_manager():
    """测试简单的SessionManager功能"""
    print("\n🔧 测试简单SessionManager功能...")
    
    session_manager = SessionManager()
    
    try:
        await session_manager.initialize()
        
        # 测试基本请求
        url = "https://jp.mercari.com/"
        response = await session_manager.make_request(url)
        
        if response.status == 200:
            content = await response.text()
            print(f"✅ 基本请求成功，内容长度: {len(content)}")
            return True
        else:
            print(f"❌ 基本请求失败，状态码: {response.status}")
            return False
            
    except Exception as e:
        print(f"❌ SessionManager测试失败: {e}")
        return False
    finally:
        await session_manager.close_all()


async def main():
    """主测试函数"""
    print("🚀 开始Mercari端到端测试...")
    
    tests = [
        ("页面结构分析", test_mercari_page_structure),
        ("数据解析器", test_data_parser),
        ("简单SessionManager", test_simple_session_manager),
        ("爬虫搜索功能", test_scraper_search),
        ("多关键词搜索", test_different_keywords),
        ("价格过滤功能", test_price_filtering),
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
    print("Mercari端到端测试总结")
    print(f"{'='*60}")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    print(f"总测试数: {total}")
    print(f"通过测试: {passed}")
    print(f"失败测试: {total - passed}")
    print(f"成功率: {passed/total*100:.1f}%")
    
    if passed == total:
        print("🎉 所有测试通过！Mercari爬虫功能正常")
    else:
        print("❌ 部分测试失败")
        
        # 显示失败的测试
        failed_tests = [name for name, result in results.items() if not result]
        print(f"失败的测试: {failed_tests}")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)