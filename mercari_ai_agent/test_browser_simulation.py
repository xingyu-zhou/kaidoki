#!/usr/bin/env python3
"""
浏览器模拟测试
测试改进后的浏览器模拟效果
"""

import sys
import asyncio
import aiohttp
import json

# 添加模块路径
sys.path.insert(0, '.')

from src.mercari_agent.scrapers.session_manager import SessionManager


async def test_improved_headers():
    """测试改进后的请求头"""
    print("🌐 测试改进后的浏览器模拟...")
    
    session_manager = SessionManager()
    
    try:
        await session_manager.initialize()
        
        # 使用httpbin.org/headers来查看我们的请求头
        test_url = "https://httpbin.org/headers"
        
        print(f"访问URL: {test_url}")
        response = await session_manager.make_request(test_url)
        
        if response.status == 200:
            content = await response.text()
            data = json.loads(content)
            
            print(f"✅ 请求成功，状态码: {response.status}")
            print("\n📋 我们发送的请求头:")
            
            headers = data.get('headers', {})
            for key, value in headers.items():
                print(f"  {key}: {value}")
            
            # 检查关键的浏览器特征
            browser_features = [
                'User-Agent',
                'Sec-Ch-Ua',
                'Sec-Ch-Ua-Mobile',
                'Sec-Ch-Ua-Platform',
                'Sec-Fetch-User',
                'Accept',
                'Accept-Language'
            ]
            
            print("\n🔍 浏览器特征检查:")
            for feature in browser_features:
                if feature in headers:
                    print(f"  ✅ {feature}: {headers[feature]}")
                else:
                    print(f"  ❌ {feature}: 缺失")
            
            return True
            
        else:
            print(f"❌ 请求失败，状态码: {response.status}")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False
    finally:
        await session_manager.close_all()


async def test_multiple_endpoints():
    """测试多个端点"""
    print("\n🔧 测试多个端点...")
    
    session_manager = SessionManager()
    
    try:
        await session_manager.initialize()
        
        # 测试不同的端点
        endpoints = [
            ("httpbin.org/json", "https://httpbin.org/json"),
            ("httpbin.org/user-agent", "https://httpbin.org/user-agent"),
            ("JSONPlaceholder", "https://jsonplaceholder.typicode.com/posts/1"),
            ("GitHub API", "https://api.github.com/users/octocat"),
        ]
        
        results = []
        
        for name, url in endpoints:
            try:
                print(f"\n测试 {name}: {url}")
                response = await session_manager.make_request(url)
                
                if response.status == 200:
                    content = await response.text()
                    print(f"✅ {name}: 成功 (状态码: {response.status}, 内容长度: {len(content)})")
                    results.append((name, True, response.status))
                else:
                    print(f"❌ {name}: 失败 (状态码: {response.status})")
                    results.append((name, False, response.status))
                    
            except Exception as e:
                print(f"❌ {name}: 异常 - {e}")
                results.append((name, False, str(e)))
        
        success_count = sum(1 for _, success, _ in results if success)
        total_count = len(results)
        
        print(f"\n📊 测试结果: {success_count}/{total_count} 成功")
        
        return success_count == total_count
        
    except Exception as e:
        print(f"❌ 多端点测试失败: {e}")
        return False
    finally:
        await session_manager.close_all()


async def test_mercari_with_improved_headers():
    """测试使用改进请求头访问Mercari"""
    print("\n🏪 测试改进后的Mercari访问...")
    
    session_manager = SessionManager()
    
    try:
        await session_manager.initialize()
        
        # 测试Mercari主页
        mercari_url = "https://jp.mercari.com/"
        print(f"访问Mercari主页: {mercari_url}")
        
        response = await session_manager.make_request(mercari_url)
        
        if response.status == 200:
            content = await response.text()
            print(f"✅ Mercari主页访问成功")
            print(f"  状态码: {response.status}")
            print(f"  内容长度: {len(content)} 字符")
            
            # 检查关键内容
            if "Mercari" in content or "メルカリ" in content:
                print("  ✅ 页面内容验证通过")
                
                # 测试搜索页面
                search_url = "https://jp.mercari.com/search?keyword=iPhone"
                print(f"\n访问搜索页面: {search_url}")
                
                search_response = await session_manager.make_request(search_url)
                
                if search_response.status == 200:
                    search_content = await search_response.text()
                    print(f"✅ 搜索页面访问成功")
                    print(f"  状态码: {search_response.status}")
                    print(f"  内容长度: {len(search_content)} 字符")
                    return True
                else:
                    print(f"❌ 搜索页面访问失败，状态码: {search_response.status}")
                    return False
            else:
                print("  ❌ 页面内容验证失败")
                return False
        else:
            print(f"❌ Mercari主页访问失败，状态码: {response.status}")
            return False
            
    except Exception as e:
        print(f"❌ Mercari测试失败: {e}")
        return False
    finally:
        await session_manager.close_all()


async def test_with_referer():
    """测试添加Referer头"""
    print("\n🔗 测试添加Referer头...")
    
    session_manager = SessionManager()
    
    try:
        await session_manager.initialize()
        
        # 先访问主页
        main_url = "https://jp.mercari.com/"
        response1 = await session_manager.make_request(main_url)
        
        if response1.status == 200:
            print(f"✅ 主页访问成功")
            
            # 然后访问搜索页面，带上Referer
            search_url = "https://jp.mercari.com/search?keyword=iPhone"
            additional_headers = {
                "Referer": main_url
            }
            
            response2 = await session_manager.make_request(
                search_url, 
                headers=additional_headers
            )
            
            if response2.status == 200:
                content = await response2.text()
                print(f"✅ 带Referer的搜索请求成功")
                print(f"  状态码: {response2.status}")
                print(f"  内容长度: {len(content)} 字符")
                return True
            else:
                print(f"❌ 带Referer的搜索请求失败，状态码: {response2.status}")
                return False
        else:
            print(f"❌ 主页访问失败，状态码: {response1.status}")
            return False
            
    except Exception as e:
        print(f"❌ Referer测试失败: {e}")
        return False
    finally:
        await session_manager.close_all()


async def main():
    """主测试函数"""
    print("🚀 开始浏览器模拟测试...")
    
    tests = [
        ("改进后的请求头", test_improved_headers),
        ("多个端点测试", test_multiple_endpoints),
        ("Mercari访问测试", test_mercari_with_improved_headers),
        ("Referer头测试", test_with_referer),
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
    print("浏览器模拟测试总结")
    print(f"{'='*60}")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    print(f"总测试数: {total}")
    print(f"通过测试: {passed}")
    print(f"失败测试: {total - passed}")
    print(f"成功率: {passed/total*100:.1f}%")
    
    if passed == total:
        print("🎉 所有测试通过！浏览器模拟效果良好")
    else:
        print("❌ 部分测试失败")
        
        # 显示失败的测试
        failed_tests = [name for name, result in results.items() if not result]
        print(f"失败的测试: {failed_tests}")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)