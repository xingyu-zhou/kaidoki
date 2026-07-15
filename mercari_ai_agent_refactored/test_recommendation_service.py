#!/usr/bin/env python3
"""
推荐服务测试脚本
测试推荐算法的各项功能
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

class RecommendationServiceTester:
    """推荐服务测试器"""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.config = None
        self.recommendation_service = None
        
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
            from mercari_agent.application.services.recommendation_service import (
                RecommendationService, RecommendationResult
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
            from mercari_agent.application.services.recommendation_service import RecommendationService
            
            # 创建模拟配置
            class MockConfig:
                def __init__(self):
                    pass
            
            self.config = MockConfig()
            self.recommendation_service = RecommendationService(self.config)
            
            self.add_result("服务初始化", True, "推荐服务初始化成功")
            return True
        except Exception as e:
            self.add_result("服务初始化", False, f"初始化失败: {e}")
            return False
    
    def create_sample_products(self):
        """创建示例商品数据"""
        try:
            from mercari_agent.domain.entities.product import ProductEntity
            
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
                ),
                ProductEntity(
                    id="4",
                    title="iPad Air 第5世代 64GB",
                    price=55000,
                    condition="やや傷や汚れあり",
                    seller_name="tablet_shop",
                    description="軽い使用感のiPad",
                    category="タブレット",
                    brand="Apple"
                ),
                ProductEntity(
                    id="5",
                    title="MacBook Air M2 256GB",
                    price=120000,
                    condition="新品・未使用",
                    seller_name="mac_store",
                    description="最新MacBook Air",
                    category="ノートパソコン",
                    brand="Apple"
                )
            ]
            
            self.add_result("示例商品创建", True, f"成功创建 {len(products)} 个示例商品")
            return products
        except Exception as e:
            self.add_result("示例商品创建", False, f"创建失败: {e}")
            return []
    
    def create_sample_query(self, query_text: str, price_min: Optional[int] = None, 
                          price_max: Optional[int] = None, keywords: Optional[List[str]] = None):
        """创建示例查询"""
        try:
            from mercari_agent.domain.entities.query import QueryEntity, QueryIntent
            
            query = QueryEntity(
                original_query=query_text,
                intent=QueryIntent.SEARCH,
                keywords=keywords or [],
                price_min=price_min,
                price_max=price_max,
                category=None,
                brand=None
            )
            
            return query
        except Exception as e:
            self.add_result("示例查询创建", False, f"创建失败: {e}")
            return None
    
    async def test_fallback_recommendation(self):
        """测试备用推荐逻辑"""
        if not self.recommendation_service:
            self.add_result("备用推荐测试", False, "推荐服务未初始化")
            return
        
        try:
            start_time = time.time()
            
            products = self.create_sample_products()
            query = self.create_sample_query("iPhone", price_min=50000, price_max=100000, 
                                           keywords=["iPhone"])
            
            if not products or not query:
                self.add_result("备用推荐测试", False, "示例数据创建失败")
                return
            
            # 测试备用推荐逻辑（不使用LLM）
            result = await self.recommendation_service.recommend(
                products=products,
                query=query,
                limit=3,
                strategy="balanced"
            )
            
            duration = time.time() - start_time
            
            # 验证结果
            if hasattr(result, 'recommendations') and len(result.recommendations) > 0:
                # 检查是否正确过滤了价格范围外的商品
                valid_prices = all(
                    p.price and 50000 <= p.price <= 100000 
                    for p in result.recommendations if p.price
                )
                
                if valid_prices:
                    self.add_result("备用推荐测试", True, 
                                  f"成功生成 {len(result.recommendations)} 个推荐，价格过滤正确", duration)
                else:
                    self.add_result("备用推荐测试", False, "价格过滤不正确")
            else:
                self.add_result("备用推荐测试", False, "没有生成推荐结果")
                
        except Exception as e:
            self.add_result("备用推荐测试", False, f"测试失败: {e}")
    
    async def test_empty_products_handling(self):
        """测试空商品列表处理"""
        if not self.recommendation_service:
            return
        
        try:
            start_time = time.time()
            
            query = self.create_sample_query("test query")
            if not query:
                return
            
            result = await self.recommendation_service.recommend(
                products=[],
                query=query,
                limit=5,
                strategy="balanced"
            )
            
            duration = time.time() - start_time
            
            if hasattr(result, 'recommendations') and len(result.recommendations) == 0:
                self.add_result("空商品列表处理", True, "正确处理空商品列表", duration)
            else:
                self.add_result("空商品列表处理", False, "空商品列表处理不正确")
                
        except Exception as e:
            self.add_result("空商品列表处理", False, f"测试失败: {e}")
    
    async def test_price_filtering(self):
        """测试价格过滤功能"""
        if not self.recommendation_service:
            return
            
        try:
            start_time = time.time()
            
            products = self.create_sample_products()
            
            # 测试价格上限过滤
            query = self.create_sample_query("スマートフォン", price_max=70000)
            if not products or not query:
                return
            
            result = await self.recommendation_service.recommend(
                products=products,
                query=query,
                limit=10,
                strategy="balanced"
            )
            
            duration = time.time() - start_time
            
            # 检查所有推荐商品的价格是否在限制范围内
            valid_prices = all(
                p.price and p.price <= 70000 
                for p in result.recommendations if p.price
            )
            
            if valid_prices and len(result.recommendations) > 0:
                self.add_result("价格过滤功能", True, 
                              f"价格上限过滤正确，返回 {len(result.recommendations)} 个商品", duration)
            else:
                self.add_result("价格过滤功能", False, "价格过滤不正确或无结果")
                
        except Exception as e:
            self.add_result("价格过滤功能", False, f"测试失败: {e}")
    
    async def test_keyword_matching(self):
        """测试关键词匹配功能"""
        if not self.recommendation_service:
            return
            
        try:
            start_time = time.time()
            
            products = self.create_sample_products()
            query = self.create_sample_query("Apple iPhone", keywords=["iPhone", "Apple"])
            
            if not products or not query:
                return
            
            result = await self.recommendation_service.recommend(
                products=products,
                query=query,
                limit=10,
                strategy="balanced"
            )
            
            duration = time.time() - start_time
            
            # 检查推荐结果中是否包含关键词匹配的商品
            if len(result.recommendations) > 0:
                # 至少应该有iPhone相关的商品
                iphone_products = [p for p in result.recommendations 
                                 if "iPhone" in p.title]
                
                if len(iphone_products) > 0:
                    self.add_result("关键词匹配功能", True, 
                                  f"关键词匹配正确，找到 {len(iphone_products)} 个iPhone商品", duration)
                else:
                    self.add_result("关键词匹配功能", False, "没有找到关键词匹配的商品")
            else:
                self.add_result("关键词匹配功能", False, "没有返回任何推荐结果")
                
        except Exception as e:
            self.add_result("关键词匹配功能", False, f"测试失败: {e}")
    
    async def test_recommendation_result_structure(self):
        """测试推荐结果结构"""
        if not self.recommendation_service:
            return
            
        try:
            start_time = time.time()
            
            products = self.create_sample_products()
            query = self.create_sample_query("test")
            
            if not products or not query:
                return
            
            result = await self.recommendation_service.recommend(
                products=products,
                query=query,
                limit=3,
                strategy="balanced"
            )
            
            duration = time.time() - start_time
            
            # 检查结果结构
            required_attrs = ['recommendations', 'strategy_used', 'processing_time', 'total_analyzed']
            missing_attrs = [attr for attr in required_attrs if not hasattr(result, attr)]
            
            if not missing_attrs:
                # 检查数据类型
                valid_structure = (
                    isinstance(result.recommendations, list) and
                    isinstance(result.strategy_used, str) and
                    isinstance(result.processing_time, (int, float)) and
                    isinstance(result.total_analyzed, int)
                )
                
                if valid_structure:
                    self.add_result("推荐结果结构", True, 
                                  f"结果结构正确，包含所有必需字段", duration)
                else:
                    self.add_result("推荐结果结构", False, "字段数据类型不正确")
            else:
                self.add_result("推荐结果结构", False, f"缺少字段: {missing_attrs}")
                
        except Exception as e:
            self.add_result("推荐结果结构", False, f"测试失败: {e}")
    
    async def test_different_strategies(self):
        """测试不同推荐策略"""
        if not self.recommendation_service:
            return
            
        strategies = ["balanced", "price_oriented", "quality_oriented", "trending"]
        
        for strategy in strategies:
            try:
                start_time = time.time()
                
                products = self.create_sample_products()
                query = self.create_sample_query("smartphone")
                
                if not products or not query:
                    continue
                
                result = await self.recommendation_service.recommend(
                    products=products,
                    query=query,
                    limit=3,
                    strategy=strategy
                )
                
                duration = time.time() - start_time
                
                if hasattr(result, 'recommendations') and len(result.recommendations) > 0:
                    self.add_result(f"推荐策略-{strategy}", True, 
                                  f"策略 {strategy} 执行成功，返回 {len(result.recommendations)} 个推荐", duration)
                else:
                    self.add_result(f"推荐策略-{strategy}", False, f"策略 {strategy} 没有返回结果")
                    
            except Exception as e:
                self.add_result(f"推荐策略-{strategy}", False, f"策略 {strategy} 执行失败: {e}")
    
    async def test_limit_parameter(self):
        """测试限制参数"""
        if not self.recommendation_service:
            return
            
        try:
            start_time = time.time()
            
            products = self.create_sample_products()
            query = self.create_sample_query("test")
            
            if not products or not query:
                return
            
            # 测试不同的限制值
            for limit in [1, 3, 10]:
                result = await self.recommendation_service.recommend(
                    products=products,
                    query=query,
                    limit=limit,
                    strategy="balanced"
                )
                
                actual_count = len(result.recommendations)
                expected_count = min(limit, len(products))
                
                if actual_count <= expected_count:
                    self.add_result(f"限制参数-{limit}", True, 
                                  f"限制 {limit} 正确，返回 {actual_count} 个推荐")
                else:
                    self.add_result(f"限制参数-{limit}", False, 
                                  f"限制 {limit} 不正确，返回 {actual_count} 个推荐")
            
            duration = time.time() - start_time
            
        except Exception as e:
            self.add_result("限制参数测试", False, f"测试失败: {e}")
    
    def print_summary(self):
        """打印测试总结"""
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.passed)
        failed_tests = total_tests - passed_tests
        
        print("\n" + "="*60)
        print("推荐服务测试总结")
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
    print("开始推荐服务测试...")
    print("="*60)
    
    tester = RecommendationServiceTester()
    
    # 执行测试
    if not tester.test_basic_imports():
        print("基础导入失败，跳过后续测试")
        return
    
    if not tester.test_service_initialization():
        print("服务初始化失败，跳过后续测试")
        return
    
    # 异步测试
    await tester.test_fallback_recommendation()
    await tester.test_empty_products_handling()
    await tester.test_price_filtering()
    await tester.test_keyword_matching()
    await tester.test_recommendation_result_structure()
    await tester.test_different_strategies()
    await tester.test_limit_parameter()
    
    # 打印总结
    passed, total = tester.print_summary()
    
    # 返回退出码
    return 0 if passed == total else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)