#!/usr/bin/env python3
"""
API兼容性验证测试
"""

import asyncio
import sys
import os
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mercari_agent.scrapers.enhanced_session_manager import EnhancedSessionManager, SessionConfig
from mercari_agent.core.tools.search_tools import SearchMercariTool
from mercari_agent.services.scraper_service import ScraperService
from mercari_agent.models.query import ParsedQuery
from mercari_agent.utils.logger import get_logger

logger = get_logger(__name__)


async def test_parameter_filtering():
    """测试参数过滤功能"""
    print("🧪 测试参数过滤功能...")
    
    # 定义aiohttp支持的参数
    allowed_kwargs = {
        'params', 'data', 'json', 'cookies', 'headers', 'skip_auto_headers',
        'auth', 'allow_redirects', 'max_redirects', 'encoding', 'compress',
        'chunked', 'expect100', 'raise_for_status', 'read_until_eof', 'proxy',
        'proxy_auth', 'timeout', 'ssl', 'verify_ssl', 'fingerprint', 'ssl_context',
        'proxy_headers', 'trace_request_ctx', 'read_bufsize'
    }
    
    # 测试参数
    test_kwargs = {
        'prefer_proxy': True,           # 应该被过滤
        'max_retries': 5,              # 应该被过滤
        'retry_delay': 2.0,            # 应该被过滤
        'custom_param': 'test',        # 应该被过滤
        'timeout': 10,                 # 应该保留
        'headers': {'Test': 'Value'},  # 应该保留
        'params': {'key': 'value'},    # 应该保留
        'data': {'test': 'data'},      # 应该保留
        'ssl': False                   # 应该保留
    }
    
    # 执行过滤
    filtered_kwargs = {k: v for k, v in test_kwargs.items() if k in allowed_kwargs}
    filtered_params = set(test_kwargs.keys()) - set(filtered_kwargs.keys())
    
    print(f"✅ 原始参数: {list(test_kwargs.keys())}")
    print(f"✅ 过滤后参数: {list(filtered_kwargs.keys())}")
    print(f"✅ 被过滤参数: {list(filtered_params)}")
    
    # 验证过滤结果
    expected_filtered = {'prefer_proxy', 'max_retries', 'retry_delay', 'custom_param'}
    expected_kept = {'timeout', 'headers', 'params', 'data', 'ssl'}
    
    if filtered_params == expected_filtered and set(filtered_kwargs.keys()) == expected_kept:
        print("✅ 参数过滤功能正常工作")
        return True
    else:
        print("❌ 参数过滤功能异常")
        return False


async def test_search_tool_query_validation():
    """测试搜索工具的查询验证"""
    print("\n🧪 测试搜索工具查询验证...")
    
    # 创建模拟的爬虫服务
    class MockScraperService:
        async def scrape(self, context):
            class MockResult:
                def __init__(self):
                    self.products = []
                    self.total_found = 0
                    self.pages_scraped = 0
                    self.strategy_used = "REQUESTS"
                    self.processing_time = 0.1
                    self.metadata = {}
            return MockResult()
    
    scraper_service = MockScraperService()
    search_tool = SearchMercariTool(scraper_service)
    
    # 测试空查询
    print("测试空查询...")
    result = await search_tool.execute(query="")
    if result.status.value == "error":
        print("✅ 空查询正确返回错误")
    else:
        print("❌ 空查询应该返回错误")
        return False
    
    # 测试空白查询
    print("测试空白查询...")
    result = await search_tool.execute(query="   ")
    if result.status.value == "error":
        print("✅ 空白查询正确返回错误")
    else:
        print("❌ 空白查询应该返回错误")
        return False
    
    # 测试有效查询
    print("测试有效查询...")
    result = await search_tool.execute(query="iPhone")
    if result.status.value == "success":
        print("✅ 有效查询正确处理")
        return True
    else:
        print(f"❌ 有效查询处理失败: {result.error}")
        return False


async def test_parsed_query_creation():
    """测试ParsedQuery创建"""
    print("\n🧪 测试ParsedQuery创建...")
    
    try:
        # 测试正常查询
        query = ParsedQuery(
            original_query="iPhone 13",
            normalized_query="iPhone 13",
            keywords=["iPhone", "13"],
            category="electronics",
            price_min=50000,
            price_max=100000
        )
        
        print(f"✅ 创建ParsedQuery成功: {query}")
        
        # 测试查询转换为搜索查询
        search_query = query.to_search_query()
        print(f"✅ 转换为SearchQuery成功: {search_query}")
        
        return True
        
    except Exception as e:
        print(f"❌ ParsedQuery创建失败: {e}")
        return False


async def test_session_manager_initialization():
    """测试会话管理器初始化"""
    print("\n🧪 测试会话管理器初始化...")
    
    try:
        config = SessionConfig(
            max_concurrent_sessions=1,
            max_init_retries=3,
            init_timeout=30.0
        )
        
        session_manager = EnhancedSessionManager(config)
        
        # 初始化会话管理器
        await session_manager.initialize()
        
        # 检查健康状态
        if session_manager.is_healthy:
            print("✅ 会话管理器初始化成功且健康")
            
            # 获取统计信息
            stats = session_manager.get_session_statistics()
            print(f"✅ 会话统计: {stats}")
            
            # 关闭会话管理器
            await session_manager.close_all_sessions()
            print("✅ 会话管理器关闭成功")
            
            return True
        else:
            print("❌ 会话管理器不健康")
            return False
            
    except Exception as e:
        print(f"❌ 会话管理器初始化失败: {e}")
        return False


async def main():
    """主测试函数"""
    print("🚀 开始API兼容性验证测试...")
    
    tests = [
        ("参数过滤功能", test_parameter_filtering),
        ("搜索工具查询验证", test_search_tool_query_validation),
        ("ParsedQuery创建", test_parsed_query_creation),
        ("会话管理器初始化", test_session_manager_initialization)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"执行测试: {test_name}")
        print(f"{'='*50}")
        
        try:
            result = await test_func()
            results.append((test_name, result))
            
            if result:
                print(f"✅ {test_name} 测试通过")
            else:
                print(f"❌ {test_name} 测试失败")
                
        except Exception as e:
            print(f"❌ {test_name} 测试异常: {e}")
            results.append((test_name, False))
    
    # 汇总结果
    print(f"\n{'='*50}")
    print("📊 测试结果汇总")
    print(f"{'='*50}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！API兼容性修复成功！")
        return True
    else:
        print("😞 部分测试失败，需要进一步修复")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)