#!/usr/bin/env python3
"""
SSL连接测试脚本 - 紧急修复验证
验证所有TCPConnector的SSL配置是否正确工作
"""

import asyncio
import aiohttp
import time
import sys
import os
from pathlib import Path

# 添加项目路径到sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.mercari_agent.scrapers.enhanced_session_manager import EnhancedSessionManager
from src.mercari_agent.scrapers.session_manager import SessionManager
from src.mercari_agent.scrapers.base_scraper import BaseScraper, ScrapingConfig, ScrapingStrategy
from src.mercari_agent.scrapers.mercari_scraper import MercariScraper
from src.mercari_agent.utils.logger import get_logger

logger = get_logger(__name__)

class SSLConnectionTester:
    """SSL连接测试器"""
    
    def __init__(self):
        self.test_url = "https://jp.mercari.com/search?keyword=iPhone"
        self.results = {}
        
    async def test_direct_connection(self):
        """测试直接连接（使用修复后的TCPConnector）"""
        print("🧪 测试1: 直接连接测试")
        
        try:
            # 测试修复后的TCPConnector配置
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=30,
                ttl_dns_cache=300,
                use_dns_cache=True,
                ssl=False  # 修复后的配置
            )
            
            async with aiohttp.ClientSession(connector=connector) as session:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                }
                
                start_time = time.time()
                async with session.get(self.test_url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    response_time = time.time() - start_time
                    content = await response.text()
                    
                    result = {
                        'success': True,
                        'status_code': response.status,
                        'response_time': response_time,
                        'content_length': len(content),
                        'headers': dict(response.headers),
                        'error': None
                    }
                    
                    print(f"✅ 直接连接成功!")
                    print(f"   状态码: {response.status}")
                    print(f"   响应时间: {response_time:.2f}s")
                    print(f"   内容长度: {len(content)} 字符")
                    
                    self.results['direct_connection'] = result
                    return result
                    
        except Exception as e:
            error_msg = str(e)
            result = {
                'success': False,
                'error': error_msg,
                'error_type': type(e).__name__
            }
            
            print(f"❌ 直接连接失败: {error_msg}")
            self.results['direct_connection'] = result
            return result
    
    async def test_enhanced_session_manager(self):
        """测试增强会话管理器"""
        print("\n🧪 测试2: 增强会话管理器测试")
        
        try:
            enhanced_manager = EnhancedSessionManager(max_sessions=2)
            await enhanced_manager.initialize()
            
            start_time = time.time()
            response = await enhanced_manager.make_request(
                url=self.test_url,
                method="GET",
                timeout=30
            )
            response_time = time.time() - start_time
            
            content = await response.text()
            
            result = {
                'success': True,
                'status_code': response.status,
                'response_time': response_time,
                'content_length': len(content),
                'error': None
            }
            
            print(f"✅ 增强会话管理器成功!")
            print(f"   状态码: {response.status}")
            print(f"   响应时间: {response_time:.2f}s")
            print(f"   内容长度: {len(content)} 字符")
            
            await enhanced_manager.close()
            self.results['enhanced_session_manager'] = result
            return result
            
        except Exception as e:
            error_msg = str(e)
            result = {
                'success': False,
                'error': error_msg,
                'error_type': type(e).__name__
            }
            
            print(f"❌ 增强会话管理器失败: {error_msg}")
            self.results['enhanced_session_manager'] = result
            return result
    
    async def test_basic_session_manager(self):
        """测试基础会话管理器"""
        print("\n🧪 测试3: 基础会话管理器测试")
        
        try:
            basic_manager = SessionManager(max_sessions=2)
            await basic_manager.initialize()
            
            start_time = time.time()
            response = await basic_manager.make_request(
                url=self.test_url,
                method="GET",
                timeout=30
            )
            response_time = time.time() - start_time
            
            content = await response.text()
            
            result = {
                'success': True,
                'status_code': response.status,
                'response_time': response_time,
                'content_length': len(content),
                'error': None
            }
            
            print(f"✅ 基础会话管理器成功!")
            print(f"   状态码: {response.status}")
            print(f"   响应时间: {response_time:.2f}s")
            print(f"   内容长度: {len(content)} 字符")
            
            await basic_manager.close_all()
            self.results['basic_session_manager'] = result
            return result
            
        except Exception as e:
            error_msg = str(e)
            result = {
                'success': False,
                'error': error_msg,
                'error_type': type(e).__name__
            }
            
            print(f"❌ 基础会话管理器失败: {error_msg}")
            self.results['basic_session_manager'] = result
            return result
    
    async def test_mercari_scraper(self):
        """测试Mercari爬虫"""
        print("\n🧪 测试4: Mercari爬虫测试")
        
        try:
            scraper = MercariScraper(strategy=ScrapingStrategy.REQUESTS)
            await scraper.initialize()
            
            start_time = time.time()
            result = await scraper.scrape_page(self.test_url)
            response_time = time.time() - start_time
            
            test_result = {
                'success': result.success,
                'response_time': response_time,
                'products_count': len(result.products),
                'error': result.error_message,
                'metadata': result.metadata
            }
            
            if result.success:
                print(f"✅ Mercari爬虫成功!")
                print(f"   响应时间: {response_time:.2f}s")
                print(f"   产品数量: {len(result.products)}")
            else:
                print(f"❌ Mercari爬虫失败: {result.error_message}")
            
            await scraper.close()
            self.results['mercari_scraper'] = test_result
            return test_result
            
        except Exception as e:
            error_msg = str(e)
            result = {
                'success': False,
                'error': error_msg,
                'error_type': type(e).__name__
            }
            
            print(f"❌ Mercari爬虫异常: {error_msg}")
            self.results['mercari_scraper'] = result
            return result
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始SSL连接测试...")
        print("=" * 60)
        
        # 运行所有测试
        await self.test_direct_connection()
        await self.test_enhanced_session_manager()
        await self.test_basic_session_manager()
        await self.test_mercari_scraper()
        
        # 生成测试报告
        self.generate_report()
    
    def generate_report(self):
        """生成测试报告"""
        print("\n" + "=" * 60)
        print("📊 测试报告汇总")
        print("=" * 60)
        
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results.values() if r.get('success', False))
        
        print(f"总测试数: {total_tests}")
        print(f"成功测试: {successful_tests}")
        print(f"失败测试: {total_tests - successful_tests}")
        print(f"成功率: {(successful_tests / total_tests * 100):.1f}%")
        
        print("\n详细结果:")
        for test_name, result in self.results.items():
            status = "✅ 成功" if result.get('success', False) else "❌ 失败"
            print(f"  {test_name}: {status}")
            if not result.get('success', False):
                print(f"    错误: {result.get('error', 'Unknown error')}")
        
        # 诊断建议
        print("\n" + "=" * 60)
        print("🔍 诊断建议")
        print("=" * 60)
        
        if successful_tests == total_tests:
            print("🎉 所有测试都通过了！SSL配置修复成功。")
        elif successful_tests > 0:
            print("⚠️  部分测试通过，可能存在特定组件的问题。")
        else:
            print("🚨 所有测试都失败了，可能需要进一步调查。")
            
        # 检查是否仍有Connection closed错误
        connection_errors = [r for r in self.results.values() 
                           if 'Connection closed' in str(r.get('error', ''))]
        if connection_errors:
            print("⚠️  仍然存在'Connection closed'错误，可能需要进一步修复。")
        else:
            print("✅ 没有发现'Connection closed'错误。")

async def main():
    """主函数"""
    print("🔧 Mercari AI Agent - SSL连接测试")
    print("目标: 验证所有TCPConnector的SSL配置修复")
    print("测试URL: https://jp.mercari.com/search?keyword=iPhone")
    print("")
    
    tester = SSLConnectionTester()
    await tester.run_all_tests()
    
    print("\n🏁 测试完成！")

if __name__ == "__main__":
    asyncio.run(main())