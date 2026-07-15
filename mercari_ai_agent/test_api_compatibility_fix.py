#!/usr/bin/env python3
"""
API兼容性修复测试脚本

测试修复后的HTTP请求功能和产品搜索功能
"""

import asyncio
import logging
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mercari_agent.scrapers.enhanced_session_manager import EnhancedSessionManager, SessionConfig
from mercari_agent.core.tools.search_tools import SearchMercariTool
from mercari_agent.services.scraper_service import ScraperService
from mercari_agent.utils.logger import get_logger

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = get_logger(__name__)


async def test_session_manager_http_requests():
    """测试会话管理器的HTTP请求功能"""
    logger.info("🧪 测试会话管理器HTTP请求功能...")
    
    try:
        # 创建会话管理器
        config = SessionConfig(
            max_concurrent_sessions=2,
            max_init_retries=3,
            init_timeout=30.0
        )
        
        async with EnhancedSessionManager(config) as session_manager:
            # 测试基本HTTP请求
            logger.info("测试基本HTTP请求...")
            
            # 测试带有不兼容参数的请求
            async with session_manager.get_session_safe() as session:
                if session is None:
                    logger.error("❌ 无法获取会话")
                    return False
                
                async with session.request(
                    method="GET",
                    url="https://httpbin.org/get",
                    timeout=10,
                    headers={"User-Agent": "Test Agent"}
                ) as response:
                    if response.status == 200:
                        logger.info("✅ HTTP请求成功")
                        # 读取响应内容
                        content = await response.text()
                        logger.info(f"响应内容长度: {len(content)} 字符")
                    else:
                        logger.error(f"❌ HTTP请求失败，状态码: {response.status}")
                        return False
            
            # 测试会话统计
            stats = session_manager.get_session_statistics()
            logger.info(f"会话统计: {stats}")
            
            # 测试会话健康状态
            logger.info(f"会话管理器健康状态: {session_manager.is_healthy}")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ 会话管理器测试失败: {e}")
        return False


async def test_search_tools_with_empty_query():
    """测试搜索工具的空查询处理"""
    logger.info("🧪 测试搜索工具空查询处理...")
    
    try:
        # 创建模拟的爬虫服务
        class MockScraperService:
            async def scrape(self, context):
                # 模拟返回结果
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
        logger.info("测试空查询...")
        result = await search_tool.execute(query="")
        
        if result.status.value == "error":
            logger.info("✅ 空查询正确返回错误")
        else:
            logger.error("❌ 空查询应该返回错误")
            return False
        
        # 测试有效查询
        logger.info("测试有效查询...")
        result = await search_tool.execute(query="iPhone")
        
        if result.status.value == "success":
            logger.info("✅ 有效查询正确处理")
        else:
            logger.error(f"❌ 有效查询处理失败: {result.error}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 搜索工具测试失败: {e}")
        return False


async def test_parameter_filtering():
    """测试参数过滤功能"""
    logger.info("🧪 测试参数过滤功能...")
    
    try:
        config = SessionConfig(max_concurrent_sessions=1)
        
        async with EnhancedSessionManager(config) as session_manager:
            # 测试各种不兼容参数
            test_params = {
                "url": "https://httpbin.org/get",
                "method": "GET",
                "prefer_proxy": True,           # 不兼容，应该被过滤
                "max_retries": 5,              # 不兼容，应该被过滤
                "retry_delay": 2.0,            # 不兼容，应该被过滤
                "custom_param": "test",        # 不兼容，应该被过滤
                "timeout": 10,                 # 兼容，应该保留
                "headers": {"Test": "Value"},  # 兼容，应该保留
                "params": {"key": "value"}     # 兼容，应该保留
            }
            
            logger.info("发送包含不兼容参数的请求...")
            response = await session_manager.make_request(**test_params)
            
            if response.status == 200:
                logger.info("✅ 参数过滤功能正常工作")
                return True
            else:
                logger.error(f"❌ 请求失败，状态码: {response.status}")
                return False
                
    except Exception as e:
        logger.error(f"❌ 参数过滤测试失败: {e}")
        return False


async def main():
    """主测试函数"""
    logger.info("🚀 开始API兼容性修复测试...")
    
    tests = [
        ("会话管理器HTTP请求", test_session_manager_http_requests),
        ("搜索工具空查询处理", test_search_tools_with_empty_query),
        ("参数过滤功能", test_parameter_filtering)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"执行测试: {test_name}")
        logger.info(f"{'='*50}")
        
        try:
            result = await test_func()
            results.append((test_name, result))
            
            if result:
                logger.info(f"✅ {test_name} 测试通过")
            else:
                logger.error(f"❌ {test_name} 测试失败")
                
        except Exception as e:
            logger.error(f"❌ {test_name} 测试异常: {e}")
            results.append((test_name, False))
    
    # 汇总结果
    logger.info(f"\n{'='*50}")
    logger.info("📊 测试结果汇总")
    logger.info(f"{'='*50}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"{test_name}: {status}")
    
    logger.info(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        logger.info("🎉 所有测试通过！API兼容性修复成功！")
        return True
    else:
        logger.error("😞 部分测试失败，需要进一步修复")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)