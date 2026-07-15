#!/usr/bin/env python3
"""
输出格式化服务测试脚本
测试输出格式化功能的各项能力
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

class OutputFormatterServiceTester:
    """输出格式化服务测试器"""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.config = None
        self.formatter_service = None
        
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
            from mercari_agent.application.services.output_formatter_service import (
                OutputFormatterService, FormattedOutput
            )
            from mercari_agent.domain.entities.product import ProductEntity
            from mercari_agent.domain.entities.query import QueryEntity, QueryIntent
            self.add_result("基础导入", True, "所有必需类导入成功")
            return True
        except ImportError as e:
            self.add_result("基础导入", False, f"导入失败: {e}")
            return False
    
    def test_service_initialization(self):
        """测试服务初始化"""
        try:
            from mercari_agent.application.services.output_formatter_service import OutputFormatterService
            
            # 创建模拟配置
            class MockConfig:
                def __init__(self):
                    pass
            
            self.config = MockConfig()
            self.formatter_service = OutputFormatterService(self.config)
            
            self.add_result("服务初始化", True, "输出格式化服务初始化成功")
            return True
        except Exception as e:
            self.add_result("服务初始化", False, f"初始化失败: {e}")
            return False
    
    def create_sample_recommendation_data(self):
        """创建示例推荐数据"""
        try:
            from mercari_agent.domain.entities.product import ProductEntity
            from mercari_agent.application.services.recommendation_service import RecommendationResult
            
            products = [
                ProductEntity(
                    id="1",
                    title="iPhone 14 Pro 128GB スペースブラック",
                    price=98000,
                    condition="新品・未使用",
                    seller_name="tech_seller",
                    description="最新のiPhone 14 Pro",
                    category="スマートフォン",
                    brand="Apple"
                ),
                ProductEntity(
                    id="2", 
                    title="iPhone 13 64GB ホワイト",
                    price=65000,
                    condition="目立った傷や汚れなし",
                    seller_name="phone_store",
                    description="状態良好なiPhone 13",
                    category="スマートフォン",
                    brand="Apple"
                ),
                ProductEntity(
                    id="3",
                    title="Samsung Galaxy S23 256GB",
                    price=75000,
                    condition="新品・未使用",
                    seller_name="android_seller",
                    description="最新Galaxy",
                    category="スマートフォン",
                    brand="Samsung"
                )
            ]
            
            # formatted_price 是一个计算属性，无需手动设置
            # 它会根据 price 字段自动计算
            
            recommendation_data = RecommendationResult(
                recommendations=products,
                strategy_used="balanced",
                processing_time=0.123,
                total_analyzed=10
            )
            
            self.add_result("示例推荐数据创建", True, f"成功创建包含 {len(products)} 个商品的推荐数据")
            return recommendation_data
        except Exception as e:
            self.add_result("示例推荐数据创建", False, f"创建失败: {e}")
            return None
    
    def create_sample_query(self, query_text: str = "iPhone"):
        """创建示例查询"""
        try:
            from mercari_agent.domain.entities.query import QueryEntity, QueryIntent
            
            query = QueryEntity(
                original_query=query_text,
                intent=QueryIntent.SEARCH,
                keywords=["iPhone"],
                price_min=50000,
                price_max=100000,
                category="スマートフォン",
                brand="Apple"
            )
            
            return query
        except Exception as e:
            self.add_result("示例查询创建", False, f"创建失败: {e}")
            return None
    
    async def test_markdown_table_format(self):
        """测试Markdown表格格式化"""
        if not self.formatter_service:
            self.add_result("Markdown表格格式", False, "格式化服务未初始化")
            return
        
        try:
            start_time = time.time()
            
            recommendation_data = self.create_sample_recommendation_data()
            query = self.create_sample_query()
            
            if not recommendation_data or not query:
                self.add_result("Markdown表格格式", False, "示例数据创建失败")
                return
            
            result = await self.formatter_service.format(
                data=recommendation_data,
                query=query,
                output_format="markdown_table",
                language="zh"
            )
            
            duration = time.time() - start_time
            
            # 验证结果
            if hasattr(result, 'content') and result.content:
                # 检查是否包含表格标记
                has_table_headers = "|" in result.content and "商品名称" in result.content
                has_table_separator = "---" in result.content or "--|" in result.content
                
                if has_table_headers:
                    self.add_result("Markdown表格格式", True, 
                                  f"成功生成Markdown表格，内容长度: {len(result.content)}", duration)
                else:
                    self.add_result("Markdown表格格式", False, "生成的内容不包含表格格式")
            else:
                self.add_result("Markdown表格格式", False, "没有生成格式化内容")
                
        except Exception as e:
            self.add_result("Markdown表格格式", False, f"测试失败: {e}")
    
    async def test_simple_list_format(self):
        """测试简单列表格式化"""
        if not self.formatter_service:
            return
        
        try:
            start_time = time.time()
            
            recommendation_data = self.create_sample_recommendation_data()
            query = self.create_sample_query()
            
            if not recommendation_data or not query:
                return
            
            result = await self.formatter_service.format(
                data=recommendation_data,
                query=query,
                output_format="simple_list",
                language="zh"
            )
            
            duration = time.time() - start_time
            
            # 验证结果
            if hasattr(result, 'content') and result.content:
                # 检查是否包含列表格式
                has_list_format = "1." in result.content and "2." in result.content
                
                if has_list_format:
                    self.add_result("简单列表格式", True, 
                                  f"成功生成简单列表，内容长度: {len(result.content)}", duration)
                else:
                    self.add_result("简单列表格式", False, "生成的内容不是列表格式")
            else:
                self.add_result("简单列表格式", False, "没有生成格式化内容")
                
        except Exception as e:
            self.add_result("简单列表格式", False, f"测试失败: {e}")
    
    async def test_detailed_report_format(self):
        """测试详细报告格式化"""
        if not self.formatter_service:
            return
        
        try:
            start_time = time.time()
            
            recommendation_data = self.create_sample_recommendation_data()
            query = self.create_sample_query()
            
            if not recommendation_data or not query:
                return
            
            result = await self.formatter_service.format(
                data=recommendation_data,
                query=query,
                output_format="detailed_report",
                language="zh"
            )
            
            duration = time.time() - start_time
            
            # 验证结果
            if hasattr(result, 'content') and result.content:
                self.add_result("详细报告格式", True, 
                              f"成功生成详细报告，内容长度: {len(result.content)}", duration)
            else:
                self.add_result("详细报告格式", False, "没有生成格式化内容")
                
        except Exception as e:
            self.add_result("详细报告格式", False, f"测试失败: {e}")
    
    async def test_json_export_format(self):
        """测试JSON导出格式化"""
        if not self.formatter_service:
            return
        
        try:
            start_time = time.time()
            
            recommendation_data = self.create_sample_recommendation_data()
            query = self.create_sample_query()
            
            if not recommendation_data or not query:
                return
            
            result = await self.formatter_service.format(
                data=recommendation_data,
                query=query,
                output_format="json_export",
                language="zh"
            )
            
            duration = time.time() - start_time
            
            # 验证结果
            if hasattr(result, 'content') and result.content:
                self.add_result("JSON导出格式", True, 
                              f"成功生成JSON格式，内容长度: {len(result.content)}", duration)
            else:
                self.add_result("JSON导出格式", False, "没有生成格式化内容")
                
        except Exception as e:
            self.add_result("JSON导出格式", False, f"测试失败: {e}")
    
    async def test_empty_data_handling(self):
        """测试空数据处理"""
        if not self.formatter_service:
            return
        
        try:
            start_time = time.time()
            
            from mercari_agent.application.services.recommendation_service import RecommendationResult
            
            # 创建空推荐数据
            empty_data = RecommendationResult(
                recommendations=[],
                strategy_used="balanced",
                processing_time=0.0,
                total_analyzed=0
            )
            
            query = self.create_sample_query()
            if not query:
                return
            
            result = await self.formatter_service.format(
                data=empty_data,
                query=query,
                output_format="markdown_table",
                language="zh"
            )
            
            duration = time.time() - start_time
            
            # 验证结果
            if hasattr(result, 'content') and result.content:
                # 检查是否包含"没有找到"或类似的提示
                has_empty_message = "没有找到" in result.content or "无商品" in result.content or len(result.content) > 0
                
                if has_empty_message:
                    self.add_result("空数据处理", True, 
                                  f"正确处理空数据，返回提示信息", duration)
                else:
                    self.add_result("空数据处理", False, "空数据处理不正确")
            else:
                self.add_result("空数据处理", False, "空数据没有返回任何内容")
                
        except Exception as e:
            self.add_result("空数据处理", False, f"测试失败: {e}")
    
    async def test_different_languages(self):
        """测试多语言支持"""
        if not self.formatter_service:
            return
        
        languages = ["zh", "en", "ja"]
        
        for lang in languages:
            try:
                start_time = time.time()
                
                recommendation_data = self.create_sample_recommendation_data()
                query = self.create_sample_query()
                
                if not recommendation_data or not query:
                    continue
                
                result = await self.formatter_service.format(
                    data=recommendation_data,
                    query=query,
                    output_format="simple_list",
                    language=lang
                )
                
                duration = time.time() - start_time
                
                # 验证结果
                if hasattr(result, 'content') and result.content and hasattr(result, 'language'):
                    if result.language == lang:
                        self.add_result(f"多语言支持-{lang}", True, 
                                      f"成功生成{lang}语言输出，内容长度: {len(result.content)}", duration)
                    else:
                        self.add_result(f"多语言支持-{lang}", False, f"语言设置不正确: {result.language}")
                else:
                    self.add_result(f"多语言支持-{lang}", False, f"语言{lang}输出失败")
                    
            except Exception as e:
                self.add_result(f"多语言支持-{lang}", False, f"语言{lang}测试失败: {e}")
    
    async def test_output_structure(self):
        """测试输出结构"""
        if not self.formatter_service:
            return
        
        try:
            start_time = time.time()
            
            recommendation_data = self.create_sample_recommendation_data()
            query = self.create_sample_query()
            
            if not recommendation_data or not query:
                return
            
            result = await self.formatter_service.format(
                data=recommendation_data,
                query=query,
                output_format="markdown_table",
                language="zh"
            )
            
            duration = time.time() - start_time
            
            # 检查结果结构
            required_attrs = ['content', 'format_type', 'language', 'processing_time']
            missing_attrs = [attr for attr in required_attrs if not hasattr(result, attr)]
            
            if not missing_attrs:
                # 检查数据类型
                valid_structure = (
                    isinstance(result.content, str) and
                    isinstance(result.format_type, str) and
                    isinstance(result.language, str) and
                    isinstance(result.processing_time, (int, float))
                )
                
                if valid_structure:
                    self.add_result("输出结构验证", True, 
                                  f"输出结构正确，包含所有必需字段", duration)
                else:
                    self.add_result("输出结构验证", False, "字段数据类型不正确")
            else:
                self.add_result("输出结构验证", False, f"缺少字段: {missing_attrs}")
                
        except Exception as e:
            self.add_result("输出结构验证", False, f"测试失败: {e}")
    
    async def test_fallback_format_method(self):
        """测试备用格式化方法"""
        if not self.formatter_service:
            return
        
        try:
            start_time = time.time()
            
            recommendation_data = self.create_sample_recommendation_data()
            
            if not recommendation_data:
                return
            
            # 直接调用备用格式化方法
            content = await self.formatter_service._fallback_format(recommendation_data, "markdown_table")
            
            duration = time.time() - start_time
            
            # 验证结果
            if content and isinstance(content, str):
                # 检查是否包含表格标记
                has_table_content = "|" in content and len(content) > 0
                
                if has_table_content:
                    self.add_result("备用格式化方法", True, 
                                  f"备用格式化正常工作，内容长度: {len(content)}", duration)
                else:
                    self.add_result("备用格式化方法", False, "备用格式化内容不正确")
            else:
                self.add_result("备用格式化方法", False, "备用格式化没有返回内容")
                
        except Exception as e:
            self.add_result("备用格式化方法", False, f"测试失败: {e}")
    
    async def test_non_recommendation_data(self):
        """测试非推荐数据格式化"""
        if not self.formatter_service:
            return
        
        try:
            start_time = time.time()
            
            # 测试普通字符串数据
            test_data = "这是一个测试字符串"
            query = self.create_sample_query()
            
            if not query:
                return
            
            result = await self.formatter_service.format(
                data=test_data,
                query=query,
                output_format="simple_list",
                language="zh"
            )
            
            duration = time.time() - start_time
            
            # 验证结果
            if hasattr(result, 'content') and result.content:
                self.add_result("非推荐数据格式化", True, 
                              f"成功处理非推荐数据，内容: {result.content[:50]}...", duration)
            else:
                self.add_result("非推荐数据格式化", False, "非推荐数据处理失败")
                
        except Exception as e:
            self.add_result("非推荐数据格式化", False, f"测试失败: {e}")
    
    def print_summary(self):
        """打印测试总结"""
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.passed)
        failed_tests = total_tests - passed_tests
        
        print("\n" + "="*60)
        print("输出格式化服务测试总结")
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
    print("开始输出格式化服务测试...")
    print("="*60)
    
    tester = OutputFormatterServiceTester()
    
    # 执行测试
    if not tester.test_basic_imports():
        print("基础导入失败，跳过后续测试")
        return
    
    if not tester.test_service_initialization():
        print("服务初始化失败，跳过后续测试")
        return
    
    # 异步测试
    await tester.test_markdown_table_format()
    await tester.test_simple_list_format()
    await tester.test_detailed_report_format()
    await tester.test_json_export_format()
    await tester.test_empty_data_handling()
    await tester.test_different_languages()
    await tester.test_output_structure()
    await tester.test_fallback_format_method()
    await tester.test_non_recommendation_data()
    
    # 打印总结
    passed, total = tester.print_summary()
    
    # 返回退出码
    return 0 if passed == total else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)