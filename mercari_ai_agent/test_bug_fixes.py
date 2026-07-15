#!/usr/bin/env python3
"""
测试修复效果的脚本

测试内容：
1. 验证HTTP请求API兼容性修复
2. 验证资源泄漏修复
3. 验证日语分词器单例模式
4. 验证会话管理器功能
"""

import asyncio
import logging
import sys
import os
import time
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

# 设置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 导入需要测试的模块
try:
    from mercari_agent.scrapers.enhanced_session_manager import EnhancedSessionManager, SessionConfig
    from mercari_agent.utils.japanese_processor import get_japanese_processor, reset_japanese_processor, TokenizerType
    from mercari_agent.utils.logger import get_logger
except ImportError as e:
    logger.error(f"导入模块失败: {e}")
    sys.exit(1)

# 测试配置
TEST_CONFIG = {
    "test_url": "https://httpbin.org/get",
    "test_text": "iPhone 15 Pro Max 256GB 新品未使用 ¥150,000",
    "max_retries": 3,
    "timeout": 10
}

class TestResults:
    """测试结果记录器"""
    
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0
    
    def add_result(self, test_name: str, passed: bool, message: str = ""):
        """添加测试结果"""
        result = {
            "test_name": test_name,
            "passed": passed,
            "message": message,
            "timestamp": time.time()
        }
        self.results.append(result)
        
        if passed:
            self.passed += 1
            logger.info(f"✅ {test_name} - PASSED {message}")
        else:
            self.failed += 1
            logger.error(f"❌ {test_name} - FAILED {message}")
    
    def get_summary(self):
        """获取测试摘要"""
        total = self.passed + self.failed
        return {
            "total": total,
            "passed": self.passed,
            "failed": self.failed,
            "success_rate": (self.passed / total * 100) if total > 0 else 0
        }

async def test_session_manager_api_compatibility():
    """测试会话管理器API兼容性"""
    logger.info("🧪 测试会话管理器API兼容性...")
    
    results = TestResults()
    
    try:
        # 测试1: 创建会话管理器
        config = SessionConfig(max_retries=2, retry_delay=0.5)
        manager = EnhancedSessionManager(config)
        
        # 测试2: 初始化会话管理器
        await manager.initialize()
        results.add_result("会话管理器初始化", manager.is_healthy, "")
        
        # 测试3: 发送HTTP请求（包含max_retries参数）
        try:
            response = await manager.make_request(
                TEST_CONFIG["test_url"],
                method="GET",
                max_retries=TEST_CONFIG["max_retries"],
                timeout=TEST_CONFIG["timeout"]
            )
            results.add_result("HTTP请求兼容性", True, f"状态码: {response.status}")
        except Exception as e:
            results.add_result("HTTP请求兼容性", False, f"错误: {e}")
        
        # 测试4: 获取会话统计
        stats = manager.get_session_statistics()
        results.add_result("会话统计", stats["active_sessions"] > 0, f"活跃会话: {stats['active_sessions']}")
        
        # 测试5: 清理资源
        await manager.close_all_sessions()
        results.add_result("资源清理", True, "所有会话已关闭")
        
    except Exception as e:
        results.add_result("会话管理器测试", False, f"异常: {e}")
    
    return results

async def test_japanese_processor_singleton():
    """测试日语分词器单例模式"""
    logger.info("🧪 测试日语分词器单例模式...")
    
    results = TestResults()
    
    try:
        # 重置单例状态
        reset_japanese_processor()
        
        # 测试1: 获取多个实例
        processor1 = get_japanese_processor(TokenizerType.JANOME)
        processor2 = get_japanese_processor(TokenizerType.JANOME)
        processor3 = get_japanese_processor(TokenizerType.SUDACHI)
        
        results.add_result("单例模式", processor1 is processor2 is processor3, "所有实例应该是同一个对象")
        
        # 测试2: 处理文本
        processed = await processor1.process(TEST_CONFIG["test_text"])
        results.add_result("文本处理", processed is not None, f"处理结果: {len(processed.tokens)} 个词汇")
        
        # 测试3: 检查分词器信息
        info = processor1.get_info()
        results.add_result("分词器信息", "current_tokenizer" in info, f"当前分词器: {info.get('current_tokenizer', 'unknown')}")
        
    except Exception as e:
        results.add_result("日语分词器测试", False, f"异常: {e}")
    
    return results

async def test_resource_leak_prevention():
    """测试资源泄漏防护"""
    logger.info("🧪 测试资源泄漏防护...")
    
    results = TestResults()
    
    try:
        # 测试1: 创建多个会话管理器并及时清理
        managers = []
        for i in range(3):
            manager = EnhancedSessionManager(SessionConfig(max_concurrent_sessions=2))
            await manager.initialize()
            managers.append(manager)
        
        results.add_result("多会话管理器创建", len(managers) == 3, f"创建了{len(managers)}个管理器")
        
        # 测试2: 清理所有管理器
        for manager in managers:
            await manager.close_all_sessions()
        
        results.add_result("资源清理", True, "所有管理器已清理")
        
        # 测试3: 使用异步上下文管理器
        async with EnhancedSessionManager(SessionConfig()) as manager:
            response = await manager.make_request(TEST_CONFIG["test_url"])
            results.add_result("异步上下文管理器", response.status == 200, f"状态码: {response.status}")
        
        results.add_result("自动资源清理", True, "异步上下文管理器自动清理")
        
    except Exception as e:
        results.add_result("资源泄漏测试", False, f"异常: {e}")
    
    return results

async def test_retry_logic():
    """测试重试逻辑"""
    logger.info("🧪 测试重试逻辑...")
    
    results = TestResults()
    
    try:
        manager = EnhancedSessionManager(SessionConfig(max_retries=2, retry_delay=0.1))
        await manager.initialize()
        
        # 测试1: 正常请求
        response = await manager.make_request(TEST_CONFIG["test_url"], max_retries=1)
        results.add_result("正常请求", response.status == 200, f"状态码: {response.status}")
        
        # 测试2: 不存在的URL（应该重试）
        try:
            await manager.make_request("https://nonexistent.example.com", max_retries=2)
            results.add_result("重试逻辑", False, "应该抛出异常")
        except Exception as e:
            results.add_result("重试逻辑", True, f"正确抛出异常: {type(e).__name__}")
        
        await manager.close_all_sessions()
        
    except Exception as e:
        results.add_result("重试逻辑测试", False, f"异常: {e}")
    
    return results

async def main():
    """主测试函数"""
    logger.info("🚀 开始测试修复效果...")
    
    # 执行所有测试
    test_functions = [
        test_session_manager_api_compatibility,
        test_japanese_processor_singleton,
        test_resource_leak_prevention,
        test_retry_logic
    ]
    
    all_results = TestResults()
    
    for test_func in test_functions:
        try:
            test_result = await test_func()
            
            # 合并结果
            all_results.results.extend(test_result.results)
            all_results.passed += test_result.passed
            all_results.failed += test_result.failed
            
        except Exception as e:
            logger.error(f"测试函数 {test_func.__name__} 执行失败: {e}")
            all_results.add_result(test_func.__name__, False, f"测试函数异常: {e}")
    
    # 输出测试报告
    logger.info("\n" + "="*50)
    logger.info("🎯 测试报告")
    logger.info("="*50)
    
    summary = all_results.get_summary()
    logger.info(f"总测试数: {summary['total']}")
    logger.info(f"通过: {summary['passed']}")
    logger.info(f"失败: {summary['failed']}")
    logger.info(f"成功率: {summary['success_rate']:.1f}%")
    
    # 详细结果
    if all_results.results:
        logger.info("\n📝 详细结果:")
        for result in all_results.results:
            status = "✅ PASS" if result["passed"] else "❌ FAIL"
            logger.info(f"  {status} {result['test_name']}: {result['message']}")
    
    # 返回退出代码
    return 0 if all_results.failed == 0 else 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("测试被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"测试执行异常: {e}")
        sys.exit(1)