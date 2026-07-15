#!/usr/bin/env python3
"""
Mercari AI Agent 系统冒烟测试

验证系统基本功能是否正常工作的轻量级测试套件。
"""

import asyncio
import sys
import time
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from mercari_agent.shared.config.app_config import get_config
from mercari_agent.infrastructure.llm.llm_service import LLMService
from mercari_agent.application.services.query_parser_service import QueryParserService
from mercari_agent.infrastructure.scraping.scraper_service import ScraperService


class SmokeTestRunner:
    """冒烟测试运行器"""
    
    def __init__(self):
        self.config = None
        self.llm_service = None
        self.query_parser = None
        self.scraper_service = None
        self.test_results = []
    
    def add_result(self, test_name: str, passed: bool, message: str, duration: float = 0.0):
        """添加测试结果"""
        self.test_results.append({
            'name': test_name,
            'passed': passed,
            'message': message,
            'duration': duration
        })
        
        status = "✅" if passed else "❌"
        print(f"{status} {test_name}: {message}")
        if duration > 0:
            print(f"    ⏱️  耗时: {duration:.2f}s")
    
    async def test_config_loading(self):
        """测试配置加载"""
        start_time = time.time()
        try:
            self.config = get_config()
            duration = time.time() - start_time
            
            if self.config.has_openai_config():
                self.add_result("配置加载", True, "配置加载成功，OpenAI已配置", duration)
            else:
                self.add_result("配置加载", False, "配置加载成功，但未配置OpenAI", duration)
                
        except Exception as e:
            duration = time.time() - start_time
            self.add_result("配置加载", False, f"配置加载失败: {e}", duration)
    
    async def test_llm_service_initialization(self):
        """测试LLM服务初始化"""
        if not self.config:
            self.add_result("LLM服务初始化", False, "配置未加载")
            return
            
        start_time = time.time()
        try:
            self.llm_service = LLMService(self.config)
            await self.llm_service.initialize()
            duration = time.time() - start_time
            
            self.add_result("LLM服务初始化", True, "LLM服务初始化成功", duration)
            
        except Exception as e:
            duration = time.time() - start_time
            self.add_result("LLM服务初始化", False, f"LLM服务初始化失败: {e}", duration)
    
    async def test_llm_basic_request(self):
        """测试LLM基本请求"""
        if not self.llm_service:
            self.add_result("LLM基本请求", False, "LLM服务未初始化")
            return
            
        start_time = time.time()
        try:
            response = await self.llm_service.generate_response("你好", max_tokens=10)
            duration = time.time() - start_time
            
            if response and response.content:
                self.add_result("LLM基本请求", True, f"LLM响应正常，内容长度: {len(response.content)}", duration)
            else:
                self.add_result("LLM基本请求", False, "LLM响应为空", duration)
                
        except Exception as e:
            duration = time.time() - start_time
            self.add_result("LLM基本请求", False, f"LLM请求失败: {e}", duration)
    
    async def test_query_parser_service(self):
        """测试查询解析服务"""
        if not self.llm_service:
            self.add_result("查询解析服务", False, "LLM服务未初始化")
            return
            
        start_time = time.time()
        try:
            self.query_parser = QueryParserService(self.config, self.llm_service)
            result = await self.query_parser.parse("iPhone 15 Pro Max")
            duration = time.time() - start_time
            
            if result and result.query and result.query.keywords:
                self.add_result("查询解析服务", True, 
                             f"查询解析成功，关键词: {', '.join(result.query.keywords)}", duration)
            else:
                self.add_result("查询解析服务", False, "查询解析结果为空", duration)
                
        except Exception as e:
            duration = time.time() - start_time
            self.add_result("查询解析服务", False, f"查询解析失败: {e}", duration)
    
    async def test_scraper_service_health(self):
        """测试爬虫服务健康检查"""
        start_time = time.time()
        try:
            self.scraper_service = ScraperService(self.config)
            await self.scraper_service.initialize()
            
            health = await self.scraper_service.health_check()
            duration = time.time() - start_time
            
            if health and health.get('status') == 'healthy':
                self.add_result("爬虫服务健康检查", True, "爬虫服务健康", duration)
            else:
                self.add_result("爬虫服务健康检查", False, f"爬虫服务不健康: {health}", duration)
                
        except Exception as e:
            duration = time.time() - start_time
            self.add_result("爬虫服务健康检查", False, f"爬虫服务检查失败: {e}", duration)
    
    async def cleanup(self):
        """清理资源"""
        try:
            if self.scraper_service:
                await self.scraper_service.close()
            if self.llm_service:
                await self.llm_service.close()
            print("🧹 资源清理完成")
        except Exception as e:
            print(f"⚠️ 资源清理警告: {e}")
    
    def print_summary(self):
        """打印测试总结"""
        print("\n" + "="*50)
        print("🚀 系统冒烟测试总结")
        print("="*50)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r['passed'])
        failed_tests = total_tests - passed_tests
        
        print(f"总测试数: {total_tests}")
        print(f"通过: {passed_tests}")
        print(f"失败: {failed_tests}")
        
        if failed_tests > 0:
            print("\n❌ 失败的测试:")
            for result in self.test_results:
                if not result['passed']:
                    print(f"  - {result['name']}: {result['message']}")
        
        total_duration = sum(r['duration'] for r in self.test_results)
        print(f"\n总耗时: {total_duration:.2f}s")
        
        if failed_tests == 0:
            print("\n🎉 所有冒烟测试通过！系统基本功能正常。")
        else:
            print(f"\n⚠️ 有 {failed_tests} 个测试失败，系统可能存在问题。")
        
        print("="*50)


async def main():
    """主函数"""
    print("🚀 开始系统冒烟测试...")
    print("="*50)
    
    tester = SmokeTestRunner()
    
    try:
        # 运行基本测试
        await tester.test_config_loading()
        await tester.test_llm_service_initialization()
        await tester.test_llm_basic_request()
        await tester.test_query_parser_service()
        await tester.test_scraper_service_health()
        
    except Exception as e:
        print(f"💥 测试执行异常: {e}")
        
    finally:
        # 清理和总结
        await tester.cleanup()
        tester.print_summary()


if __name__ == "__main__":
    asyncio.run(main())