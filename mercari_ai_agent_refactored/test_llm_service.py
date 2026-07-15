#!/usr/bin/env python3
"""
LLM服务集成测试脚本
测试LLM服务的各项功能和集成
"""

import asyncio
import sys
import os
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
import time

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

# 测试结果类
@dataclass
class TestResult:
    name: str
    passed: bool
    message: str
    duration: float = 0.0

class LLMServiceTester:
    """LLM服务测试器"""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.config = None
        self.llm_service = None
        
    def add_result(self, name: str, passed: bool, message: str, duration: float = 0.0):
        """添加测试结果"""
        result = TestResult(name, passed, message, duration)
        self.results.append(result)
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {name}: {message}")
        if duration > 0:
            print(f"    ⏱️  执行时间: {duration:.3f}s")
    
    def test_basic_imports(self):
        """测试基础导入"""
        try:
            from mercari_agent.infrastructure.llm.llm_service import (
                LLMService, LLMResponse, LLMProvider
            )
            self.add_result("基础导入", True, "所有必需类导入成功")
            return True
        except ImportError as e:
            self.add_result("基础导入", False, f"导入失败: {e}")
            return False
    
    def test_service_initialization(self):
        """测试服务初始化"""
        try:
            from mercari_agent.infrastructure.llm.llm_service import LLMService
            
            # 创建模拟配置，符合实际配置类结构
            from mercari_agent.shared.config.app_config import LLMConfig
            
            class MockConfig:
                def __init__(self):
                    self.llm = LLMConfig()
                    self.llm.openai_api_key = "test_key"
                    self.llm.anthropic_api_key = "test_key"
                    self.llm.azure_openai_api_key = "test_key"
                    self.llm.azure_openai_endpoint = "test_endpoint"
            
            self.config = MockConfig()
            self.llm_service = LLMService(self.config)
            
            self.add_result("服务初始化", True, "LLM服务初始化成功")
            return True
        except Exception as e:
            self.add_result("服务初始化", False, f"初始化失败: {e}")
            return False
    
    async def test_service_initialization_async(self):
        """测试异步服务初始化"""
        if not self.llm_service:
            self.add_result("异步初始化", False, "LLM服务未初始化")
            return
        
        try:
            start_time = time.time()
            
            await self.llm_service.initialize()
            
            duration = time.time() - start_time
            
            if self.llm_service._initialized:
                self.add_result("异步初始化", True, "异步初始化成功", duration)
            else:
                self.add_result("异步初始化", False, "初始化状态不正确")
                
        except Exception as e:
            self.add_result("异步初始化", False, f"异步初始化失败: {e}")
    
    async def test_generate_response(self):
        """测试生成响应"""
        if not self.llm_service:
            return
        
        try:
            start_time = time.time()
            
            test_prompt = "请推荐一些iPhone产品"
            response = await self.llm_service.generate_response(test_prompt)
            
            duration = time.time() - start_time
            
            # 验证响应结构
            if hasattr(response, 'content') and hasattr(response, 'provider') and hasattr(response, 'model'):
                if response.content and isinstance(response.content, str):
                    self.add_result("生成响应", True, 
                                  f"成功生成响应，内容长度: {len(response.content)}", duration)
                else:
                    self.add_result("生成响应", False, "响应内容为空")
            else:
                self.add_result("生成响应", False, "响应结构不正确")
                
        except Exception as e:
            self.add_result("生成响应", False, f"生成响应失败: {e}")
    
    async def test_response_structure(self):
        """测试响应结构"""
        if not self.llm_service:
            return
        
        try:
            start_time = time.time()
            
            response = await self.llm_service.generate_response("test prompt")
            
            duration = time.time() - start_time
            
            # 检查所有必需属性
            required_attrs = ['content', 'provider', 'model', 'latency', 'usage']
            missing_attrs = [attr for attr in required_attrs if not hasattr(response, attr)]
            
            if not missing_attrs:
                # 检查数据类型
                valid_types = (
                    isinstance(response.content, str) and
                    hasattr(response.provider, 'value') and  # Enum类型
                    isinstance(response.model, str) and
                    isinstance(response.latency, (int, float)) and
                    isinstance(response.usage, dict)
                )
                
                if valid_types:
                    self.add_result("响应结构", True, 
                                  f"响应结构正确，包含所有必需字段", duration)
                else:
                    self.add_result("响应结构", False, "字段数据类型不正确")
            else:
                self.add_result("响应结构", False, f"缺少字段: {missing_attrs}")
                
        except Exception as e:
            self.add_result("响应结构", False, f"测试失败: {e}")
    
    async def test_service_info(self):
        """测试服务信息"""
        if not self.llm_service:
            return
        
        try:
            start_time = time.time()
            
            info = await self.llm_service.get_service_info()
            
            duration = time.time() - start_time
            
            # 验证信息结构
            if isinstance(info, dict):
                required_keys = ['available_providers', 'primary_provider', 'status']
                missing_keys = [key for key in required_keys if key not in info]
                
                if not missing_keys:
                    providers = info.get('available_providers', [])
                    if isinstance(providers, list) and len(providers) > 0:
                        self.add_result("服务信息", True, 
                                      f"服务信息正确，可用提供商: {len(providers)}", duration)
                    else:
                        self.add_result("服务信息", False, "提供商列表为空")
                else:
                    self.add_result("服务信息", False, f"缺少信息字段: {missing_keys}")
            else:
                self.add_result("服务信息", False, "服务信息不是字典格式")
                
        except Exception as e:
            self.add_result("服务信息", False, f"获取服务信息失败: {e}")
    
    async def test_connection_test(self):
        """测试连接测试"""
        if not self.llm_service:
            return
        
        try:
            start_time = time.time()
            
            test_result = await self.llm_service.test_connection()
            
            duration = time.time() - start_time
            
            # 验证连接测试结果
            if isinstance(test_result, dict):
                if len(test_result) > 0:
                    successful_connections = sum(1 for conn in test_result.values() 
                                               if conn.get('status') == 'success')
                    
                    if successful_connections > 0:
                        self.add_result("连接测试", True, 
                                      f"连接测试成功，{successful_connections}/{len(test_result)} 个提供商可用", duration)
                    else:
                        self.add_result("连接测试", False, "没有可用的提供商")
                else:
                    self.add_result("连接测试", False, "连接测试结果为空")
            else:
                self.add_result("连接测试", False, "连接测试结果格式不正确")
                
        except Exception as e:
            self.add_result("连接测试", False, f"连接测试失败: {e}")
    
    async def test_multiple_requests(self):
        """测试多次请求"""
        if not self.llm_service:
            return
        
        try:
            start_time = time.time()
            
            requests = [
                "分析iPhone产品",
                "推荐Android手机",
                "比较不同品牌"
            ]
            
            responses = []
            for request in requests:
                response = await self.llm_service.generate_response(request)
                responses.append(response)
            
            duration = time.time() - start_time
            
            # 验证所有响应
            if len(responses) == len(requests):
                valid_responses = all(
                    hasattr(r, 'content') and r.content 
                    for r in responses
                )
                
                if valid_responses:
                    avg_latency = sum(r.latency for r in responses) / len(responses)
                    self.add_result("多次请求", True, 
                                  f"处理 {len(requests)} 个请求成功，平均延迟: {avg_latency:.3f}s", duration)
                else:
                    self.add_result("多次请求", False, "部分响应无效")
            else:
                self.add_result("多次请求", False, "响应数量不匹配")
                
        except Exception as e:
            self.add_result("多次请求", False, f"多次请求测试失败: {e}")
    
    async def test_integration_with_query_parser(self):
        """测试与查询解析服务的集成"""
        try:
            start_time = time.time()
            
            from mercari_agent.application.services.query_parser_service import QueryParserService
            
            # 创建查询解析服务并传入LLM服务
            query_parser = QueryParserService(self.config, self.llm_service)
            
            # 测试查询解析
            test_query = "找一个5万日元以下的iPhone"
            parsed_query = await query_parser.parse(test_query)
            
            duration = time.time() - start_time
            
            if parsed_query and hasattr(parsed_query, 'original_query'):
                self.add_result("查询解析集成", True, 
                              f"查询解析集成成功，解析查询: {parsed_query.original_query}", duration)
            else:
                self.add_result("查询解析集成", False, "查询解析集成失败")
                
        except Exception as e:
            self.add_result("查询解析集成", False, f"查询解析集成测试失败: {e}")
    
    async def test_integration_with_recommendation_service(self):
        """测试与推荐服务的集成"""
        try:
            start_time = time.time()
            
            from mercari_agent.application.services.recommendation_service import RecommendationService
            from mercari_agent.domain.entities.product import ProductEntity
            from mercari_agent.domain.entities.query import QueryEntity, QueryIntent
            
            # 创建推荐服务并传入LLM服务
            recommendation_service = RecommendationService(self.config, self.llm_service)
            
            # 创建测试数据
            products = [
                ProductEntity(
                    id="1", 
                    title="iPhone 14 Pro", 
                    price=98000, 
                    condition="新品",
                    seller_name="seller1"
                )
            ]
            
            query = QueryEntity(
                original_query="iPhone推荐",
                intent=QueryIntent.SEARCH,
                keywords=["iPhone"],
                price_min=None,
                price_max=None,
                category=None,
                brand=None
            )
            
            # 测试推荐
            recommendations = await recommendation_service.recommend(products, query, limit=1)
            
            duration = time.time() - start_time
            
            if recommendations and hasattr(recommendations, 'recommendations'):
                self.add_result("推荐服务集成", True, 
                              f"推荐服务集成成功，生成 {len(recommendations.recommendations)} 个推荐", duration)
            else:
                self.add_result("推荐服务集成", False, "推荐服务集成失败")
                
        except Exception as e:
            self.add_result("推荐服务集成", False, f"推荐服务集成测试失败: {e}")
    
    async def test_integration_with_output_formatter(self):
        """测试与输出格式化服务的集成"""
        try:
            start_time = time.time()
            
            from mercari_agent.application.services.output_formatter_service import OutputFormatterService
            from mercari_agent.application.services.recommendation_service import RecommendationResult
            from mercari_agent.domain.entities.product import ProductEntity
            from mercari_agent.domain.entities.query import QueryEntity, QueryIntent
            
            # 创建输出格式化服务并传入LLM服务
            formatter_service = OutputFormatterService(self.config, self.llm_service)
            
            # 创建测试数据
            products = [
                ProductEntity(
                    id="1", 
                    title="iPhone 14 Pro", 
                    price=98000, 
                    condition="新品",
                    seller_name="seller1"
                )
            ]
            
            recommendation_data = RecommendationResult(
                recommendations=products,
                strategy_used="balanced",
                processing_time=0.1,
                total_analyzed=1
            )
            
            query = QueryEntity(
                original_query="iPhone推荐",
                intent=QueryIntent.SEARCH,
                keywords=["iPhone"],
                price_min=None,
                price_max=None,
                category=None,
                brand=None
            )
            
            # 测试格式化
            formatted_output = await formatter_service.format(
                recommendation_data, 
                query, 
                output_format="markdown_table"
            )
            
            duration = time.time() - start_time
            
            if formatted_output and hasattr(formatted_output, 'content'):
                self.add_result("输出格式化集成", True, 
                              f"输出格式化集成成功，生成内容长度: {len(formatted_output.content)}", duration)
            else:
                self.add_result("输出格式化集成", False, "输出格式化集成失败")
                
        except Exception as e:
            self.add_result("输出格式化集成", False, f"输出格式化集成测试失败: {e}")
    
    async def test_service_close(self):
        """测试服务关闭"""
        if not self.llm_service:
            return
        
        try:
            start_time = time.time()
            
            await self.llm_service.close()
            
            duration = time.time() - start_time
            
            # 服务关闭后应该仍能正常工作（因为这是模拟服务）
            self.add_result("服务关闭", True, "服务关闭成功", duration)
                
        except Exception as e:
            self.add_result("服务关闭", False, f"服务关闭失败: {e}")
    
    async def test_error_handling(self):
        """测试错误处理"""
        if not self.llm_service:
            return
        
        try:
            start_time = time.time()
            
            # 测试空提示
            response = await self.llm_service.generate_response("")
            
            duration = time.time() - start_time
            
            # 即使是空提示，也应该能正常处理
            if hasattr(response, 'content'):
                self.add_result("错误处理", True, "空提示处理正常", duration)
            else:
                self.add_result("错误处理", False, "空提示处理失败")
                
        except Exception as e:
            self.add_result("错误处理", False, f"错误处理测试失败: {e}")
    
    def print_summary(self):
        """打印测试总结"""
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.passed)
        failed_tests = total_tests - passed_tests
        
        print("\n" + "="*60)
        print("LLM服务集成测试总结")
        print("="*60)
        print(f"总测试数: {total_tests}")
        print(f"通过: {passed_tests} ({passed_tests/total_tests*100:.1f}%)")
        print(f"失败: {failed_tests} ({failed_tests/total_tests*100:.1f}%)")
        
        if failed_tests > 0:
            print("\n失败的测试:")
            for result in self.results:
                if not result.passed:
                    print(f"  ❌ {result.name}: {result.message}")
        
        # 显示平均执行时间
        timed_results = [r for r in self.results if r.duration > 0]
        if timed_results:
            avg_time = sum(r.duration for r in timed_results) / len(timed_results)
            print(f"\n平均执行时间: {avg_time:.3f}s")
        
        print("="*60)
        
        return passed_tests, total_tests

async def main():
    """主测试函数"""
    print("开始LLM服务集成测试...")
    print("="*60)
    
    tester = LLMServiceTester()
    
    # 执行测试
    if not tester.test_basic_imports():
        print("基础导入失败，跳过后续测试")
        return
    
    if not tester.test_service_initialization():
        print("服务初始化失败，跳过后续测试")
        return
    
    # 异步测试
    await tester.test_service_initialization_async()
    await tester.test_generate_response()
    await tester.test_response_structure()
    await tester.test_service_info()
    await tester.test_connection_test()
    await tester.test_multiple_requests()
    await tester.test_integration_with_query_parser()
    await tester.test_integration_with_recommendation_service()
    await tester.test_integration_with_output_formatter()
    await tester.test_error_handling()
    await tester.test_service_close()
    
    # 打印总结
    passed, total = tester.print_summary()
    
    # 返回退出码
    return 0 if passed == total else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)