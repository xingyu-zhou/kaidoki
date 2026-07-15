#!/usr/bin/env python3
"""
CAPTCHA绕过策略测试
尝试不同的请求策略来绕过CAPTCHA检测
"""

import asyncio
import random
import time
import sys
sys.path.insert(0, '.')

from src.mercari_agent.scrapers.session_manager import SessionManager

class CaptchaBypassTester:
    """CAPTCHA绕过策略测试器"""
    
    def __init__(self):
        self.session_manager = None
        self.strategies = [
            self.strategy_basic_delay,
            self.strategy_random_headers,
            self.strategy_slow_browse,
            self.strategy_mobile_user_agent,
            self.strategy_sequence_requests
        ]
    
    async def strategy_basic_delay(self, url: str):
        """基础延迟策略"""
        print("🔄 测试基础延迟策略...")
        await asyncio.sleep(random.uniform(3, 7))
        
        response = await self.session_manager.make_request(url)
        return response
    
    async def strategy_random_headers(self, url: str):
        """随机请求头策略"""
        print("🔄 测试随机请求头策略...")
        
        # 随机选择不同的浏览器特征
        browsers = [
            {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Sec-Ch-Ua-Platform': '"Windows"'
            },
            {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
                'Sec-Ch-Ua-Platform': '"macOS"'
            },
            {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Sec-Ch-Ua-Platform': '"Linux"'
            }
        ]
        
        browser = random.choice(browsers)
        
        custom_headers = {
            **browser,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': f'ja-JP,ja;q=0.{random.randint(7,9)},en;q=0.{random.randint(5,7)}',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'DNT': '1',
            'Cache-Control': 'max-age=0'
        }
        
        response = await self.session_manager.make_request(url, headers=custom_headers)
        return response
    
    async def strategy_slow_browse(self, url: str):
        """慢速浏览策略"""
        print("🔄 测试慢速浏览策略...")
        
        # 模拟用户浏览行为
        await asyncio.sleep(random.uniform(2, 5))
        
        # 先访问主页
        main_response = await self.session_manager.make_request("https://jp.mercari.com/")
        if main_response.status != 200:
            return main_response
        
        # 等待
        await asyncio.sleep(random.uniform(3, 8))
        
        # 再访问目标页面
        response = await self.session_manager.make_request(url, headers={
            'Referer': 'https://jp.mercari.com/'
        })
        return response
    
    async def strategy_mobile_user_agent(self, url: str):
        """移动端用户代理策略"""
        print("🔄 测试移动端用户代理策略...")
        
        mobile_headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ja-JP,ja;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        }
        
        response = await self.session_manager.make_request(url, headers=mobile_headers)
        return response
    
    async def strategy_sequence_requests(self, url: str):
        """顺序请求策略"""
        print("🔄 测试顺序请求策略...")
        
        # 模拟正常用户的浏览序列
        sequence = [
            "https://jp.mercari.com/",
            "https://jp.mercari.com/categories",
            url
        ]
        
        for i, seq_url in enumerate(sequence):
            if i > 0:
                await asyncio.sleep(random.uniform(2, 6))
            
            headers = {}
            if i > 0:
                headers['Referer'] = sequence[i-1]
            
            response = await self.session_manager.make_request(seq_url, headers=headers)
            
            if seq_url == url:
                return response
            
            if response.status != 200:
                print(f"❌ 序列请求失败在步骤 {i+1}")
                return response
        
        return response
    
    async def test_all_strategies(self, test_url: str):
        """测试所有策略"""
        print(f"🚀 开始测试所有CAPTCHA绕过策略...")
        print(f"目标URL: {test_url}")
        
        self.session_manager = SessionManager()
        await self.session_manager.initialize()
        
        results = {}
        
        for i, strategy in enumerate(self.strategies):
            strategy_name = strategy.__name__
            print(f"\n{'='*50}")
            print(f"测试策略 {i+1}/{len(self.strategies)}: {strategy_name}")
            print(f"{'='*50}")
            
            try:
                response = await strategy(test_url)
                
                if response.status == 200:
                    content = await response.text()
                    
                    # 检查是否有CAPTCHA
                    has_captcha = 'captcha' in content.lower()
                    has_cloudflare = 'cloudflare' in content.lower()
                    content_length = len(content)
                    
                    results[strategy_name] = {
                        'success': True,
                        'status': response.status,
                        'has_captcha': has_captcha,
                        'has_cloudflare': has_cloudflare,
                        'content_length': content_length
                    }
                    
                    if not has_captcha and not has_cloudflare and content_length > 50000:
                        print(f"✅ {strategy_name} 成功绕过!")
                    elif not has_captcha and not has_cloudflare:
                        print(f"⚠️ {strategy_name} 可能成功，但内容较短")
                    else:
                        print(f"❌ {strategy_name} 仍检测到CAPTCHA")
                else:
                    results[strategy_name] = {
                        'success': False,
                        'status': response.status,
                        'error': f'HTTP {response.status}'
                    }
                    print(f"❌ {strategy_name} 失败: HTTP {response.status}")
                    
            except Exception as e:
                results[strategy_name] = {
                    'success': False,
                    'error': str(e)
                }
                print(f"❌ {strategy_name} 异常: {e}")
            
            # 策略之间的延迟
            if i < len(self.strategies) - 1:
                await asyncio.sleep(random.uniform(5, 10))
        
        await self.session_manager.close_all()
        
        # 输出总结
        print(f"\n{'='*50}")
        print("CAPTCHA绕过策略测试总结")
        print(f"{'='*50}")
        
        successful_strategies = []
        for strategy_name, result in results.items():
            if result.get('success') and not result.get('has_captcha', True):
                successful_strategies.append(strategy_name)
                print(f"✅ {strategy_name}: 成功")
            else:
                print(f"❌ {strategy_name}: {result.get('error', '检测到CAPTCHA')}")
        
        if successful_strategies:
            print(f"\n🎉 成功策略: {successful_strategies}")
        else:
            print(f"\n😞 所有策略都失败了")
        
        return results

async def main():
    """主测试函数"""
    tester = CaptchaBypassTester()
    
    test_urls = [
        "https://jp.mercari.com/search?keyword=iPhone",
        "https://jp.mercari.com/search?keyword=test"
    ]
    
    for url in test_urls:
        print(f"\n{'='*60}")
        print(f"测试URL: {url}")
        print(f"{'='*60}")
        
        results = await tester.test_all_strategies(url)
        
        # 间隔测试
        await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())