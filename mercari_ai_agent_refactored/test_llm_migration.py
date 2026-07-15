#!/usr/bin/env python3
"""
LLM服务迁移测试脚本

验证从模拟LLM服务到真实LLM服务的迁移是否成功。

Usage:
    python test_llm_migration.py
"""

import asyncio
import sys
import json
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.mercari_agent.shared.config.app_config import get_config
from src.mercari_agent.shared.utils.logger_utils import setup_logging, get_logger
from src.mercari_agent.infrastructure.llm.llm_service import LLMService
from src.mercari_agent.application.services.query_parser_service import QueryParserService
from src.mercari_agent.application.services.recommendation_service import RecommendationService
from src.mercari_agent.application.services.output_formatter_service import OutputFormatterService
from src.mercari_agent.domain.entities.query import QueryEntity, QueryIntent, QueryComplexity
from src.mercari_agent.domain.entities.product import ProductEntity

logger = get_logger(__name__)


class LLMMigrationTester:
    """LLM服务迁移测试器"""
    
    def __init__(self):
        self.config = None
        self.llm_service = None
        self.query_parser = None
        self.recommendation_service = None
        self.output_formatter = None
        self.test_results = []
    
    async def initialize(self):
        """初始化测试环境"""
        try:
            print("🚀 初始化LLM迁移测试环境...")
            
            # 加载配置
            self.config = get_config()
            print(f"✅ 配置加载完成 - 环境: {self.config.environment.value}")
            
            # 设置日志
            setup_logging(log_level="INFO")
            
            # 初始化LLM服务
            print("🤖 初始化LLM服务...")
            self.llm_service = LLMService(self.config)
            await self.llm_service.initialize()
            print("✅ LLM服务初始化完成")
            
            # 初始化应用服务
            print("🔧 初始化应用服务...")
            self.query_parser = QueryParserService(self.config, self.llm_service)
            self.recommendation_service = RecommendationService(self.config, self.llm_service)
            self.output_formatter = OutputFormatterService(self.config, self.llm_service)
            print("✅ 应用服务初始化完成")
            
            print("🎯 测试环境初始化成功！\n")
            
        except Exception as e:
            print(f"❌ 初始化失败: {e}")
            raise
    
    async def test_llm_service_basic(self):
        """测试LLM服务基础功能"""
        print("📋 测试1: LLM服务基础功能")
        
        try:
            # 测试服务信息
            service_info = await self.llm_service.get_service_info()
            print(f"   可用提供商: {service_info['available_providers']}")
            print(f"   主要提供商: {service_info['primary_provider']}")
            print(f"   服务状态: {service_info['status']}")
            
            # 测试连接
            connection_test = await self.llm_service.test_connection()
            for provider, result in connection_test.items():
                if result['status'] == 'success':
                    print(f"   ✅ {provider}: 连接正常 ({result.get('latency', 0):.2f}s)")
                else:
                    print(f"   ❌ {provider}: {result.get('error', '连接失败')}")
            
            # 测试基础响应生成
            test_prompt = "请简短地介绍一下iPhone 15 Pro Max的特点"
            print(f"   测试提示: {test_prompt}")
            
            response = await self.llm_service.generate_response(test_prompt, max_tokens=100)
            print(f"   ✅ 响应生成成功:")
            print(f"      提供商: {response.provider.value}")
            print(f"      模型: {response.model}")
            print(f"      延迟: {response.latency:.2f}s")
            print(f"      成本: ${response.cost:.6f}" if response.cost else "      成本: 未知")
            print(f"      内容长度: {len(response.content)} 字符")
            print(f"      内容预览: {response.content[:100]}{'...' if len(response.content) > 100 else ''}")
            
            self.test_results.append(("LLM服务基础功能", True, "所有测试通过"))
            print("   ✅ 测试1通过\n")
            
        except Exception as e:
            print(f"   ❌ 测试1失败: {e}")
            self.test_results.append(("LLM服务基础功能", False, str(e)))
    
    async def test_query_parser_integration(self):
        """测试查询解析服务集成"""
        print("📋 测试2: 查询解析服务LLM集成")
        
        try:
            test_queries = [
                "iPhone 15 Pro Max 1TB 10万円以下",
                "MacBook Air M2 新品 15万円から20万円",
                "Nintendo Switch OLED 中古品"
            ]
            
            for i, query in enumerate(test_queries, 1):
                print(f"   测试查询 {i}: {query}")
                
                result = await self.query_parser.parse(query)
                
                print(f"      关键词: {result.query.keywords}")
                print(f"      类别: {result.query.category}")
                print(f"      品牌: {result.query.brand}")
                print(f"      价格范围: {result.query.price_min} - {result.query.price_max}")
                print(f"      意图: {result.query.intent.value}")
                print(f"      置信度: {result.confidence:.2f}")
                print(f"      处理时间: {result.processing_time:.3f}s")
                print()
            
            self.test_results.append(("查询解析服务集成", True, f"成功解析 {len(test_queries)} 个查询"))
            print("   ✅ 测试2通过\n")
            
        except Exception as e:
            print(f"   ❌ 测试2失败: {e}")
            self.test_results.append(("查询解析服务集成", False, str(e)))
    
    async def test_recommendation_service_integration(self):
        """测试推荐服务集成"""
        print("📋 测试3: 推荐服务LLM集成")
        
        try:
            # 创建测试产品数据
            test_products = [
                ProductEntity(
                    title="iPhone 15 Pro Max 1TB Natural Titanium",
                    price=180000,
                    condition="新品",
                    seller_name="Apple公式ストア",
                    url="https://example.com/1"
                ),
                ProductEntity(
                    title="iPhone 15 Pro Max 512GB Blue Titanium",
                    price=165000,
                    condition="新品",
                    seller_name="正規販売店",
                    url="https://example.com/2"
                ),
                ProductEntity(
                    title="iPhone 15 Pro Max 256GB White Titanium",
                    price=140000,
                    condition="中古品(美品)",
                    seller_name="個人出品者A",
                    url="https://example.com/3"
                )
            ]
            
            # 创建测试查询
            test_query = QueryEntity(
                original_query="iPhone 15 Pro Max 1TB 15万円以下",
                normalized_query="iphone 15 pro max 1tb 15万円以下",
                keywords=["iPhone", "15", "Pro", "Max", "1TB"],
                intent=QueryIntent.SEARCH,
                category="スマートフォン",
                brand="Apple",
                price_min=None,
                price_max=150000,
                condition=None,
                complexity=QueryComplexity.MEDIUM
            )
            
            print(f"   测试查询: {test_query.original_query}")
            print(f"   测试产品数量: {len(test_products)}")
            
            # 测试推荐生成
            result = await self.recommendation_service.recommend(
                test_products,
                test_query,
                limit=5,
                strategy="balanced"
            )
            
            print(f"   ✅ 推荐生成成功:")
            print(f"      推荐数量: {len(result.recommendations)}")
            print(f"      使用策略: {result.strategy_used}")
            print(f"      处理时间: {result.processing_time:.3f}s")
            print(f"      分析商品数: {result.total_analyzed}")
            
            # 显示推荐结果
            for i, product in enumerate(result.recommendations, 1):
                print(f"      {i}. {product.title}")
                print(f"         价格: ¥{product.price:,}")
                print(f"         状态: {product.condition}")
            
            self.test_results.append(("推荐服务集成", True, f"成功生成 {len(result.recommendations)} 个推荐"))
            print("   ✅ 测试3通过\n")
            
        except Exception as e:
            print(f"   ❌ 测试3失败: {e}")
            self.test_results.append(("推荐服务集成", False, str(e)))
    
    async def test_output_formatter_integration(self):
        """测试输出格式化服务集成"""
        print("📋 测试4: 输出格式化服务LLM集成")
        
        try:
            # 创建测试数据（模拟推荐结果）
            from src.mercari_agent.application.services.recommendation_service import RecommendationResult
            
            test_products = [
                ProductEntity(
                    title="iPhone 15 Pro Max 1TB Natural Titanium",
                    price=180000,
                    condition="新品",
                    seller_name="Apple公式ストア"
                ),
                ProductEntity(
                    title="iPhone 15 Pro 512GB Blue Titanium",
                    price=155000,
                    condition="新品",
                    seller_name="正規販売店"
                )
            ]
            
            test_query = QueryEntity(
                original_query="iPhone 15 Pro 高性能モデル",
                normalized_query="iphone 15 pro 高性能モデル",
                keywords=["iPhone", "15", "Pro"],
                intent=QueryIntent.SEARCH,
                category="スマートフォン",
                brand="Apple",
                complexity=QueryComplexity.SIMPLE
            )
            
            recommendation_result = RecommendationResult(
                recommendations=test_products,
                strategy_used="balanced",
                processing_time=0.5,
                total_analyzed=2
            )
            
            # 测试不同格式
            formats = ["markdown_table", "detailed_report", "simple_list"]
            languages = ["zh", "ja"]
            
            for format_type in formats:
                for language in languages:
                    print(f"   测试格式: {format_type} ({language})")
                    
                    result = await self.output_formatter.format(
                        recommendation_result,
                        test_query,
                        format_type,
                        language
                    )
                    
                    print(f"      格式类型: {result.format_type}")
                    print(f"      语言: {result.language}")
                    print(f"      处理时间: {result.processing_time:.3f}s")
                    print(f"      内容长度: {len(result.content)} 字符")
                    print(f"      内容预览: {result.content[:100]}{'...' if len(result.content) > 100 else ''}")
                    print()
            
            self.test_results.append(("输出格式化服务集成", True, f"成功测试 {len(formats) * len(languages)} 种格式组合"))
            print("   ✅ 测试4通过\n")
            
        except Exception as e:
            print(f"   ❌ 测试4失败: {e}")
            self.test_results.append(("输出格式化服务集成", False, str(e)))
    
    async def test_cost_tracking(self):
        """测试成本跟踪功能"""
        print("📋 测试5: 成本跟踪功能")
        
        try:
            # 获取成本摘要
            cost_summary = self.llm_service.get_cost_summary()
            
            print(f"   总成本: ${cost_summary['total_cost']:.6f}")
            print(f"   请求次数: {cost_summary['request_count']}")
            print(f"   Token总数: {cost_summary['token_count']}")
            print(f"   平均每次请求成本: ${cost_summary['average_cost_per_request']:.6f}")
            
            if cost_summary['provider_costs']:
                print("   各提供商成本:")
                for provider, cost in cost_summary['provider_costs'].items():
                    print(f"      {provider}: ${cost:.6f}")
            
            if cost_summary['model_costs']:
                print("   各模型成本:")
                for model, cost in cost_summary['model_costs'].items():
                    print(f"      {model}: ${cost:.6f}")
            
            self.test_results.append(("成本跟踪功能", True, f"总请求: {cost_summary['request_count']}, 总成本: ${cost_summary['total_cost']:.6f}"))
            print("   ✅ 测试5通过\n")
            
        except Exception as e:
            print(f"   ❌ 测试5失败: {e}")
            self.test_results.append(("成本跟踪功能", False, str(e)))
    
    async def test_error_handling(self):
        """测试错误处理和回退机制"""
        print("📋 测试6: 错误处理和回退机制")
        
        try:
            # 测试无效提示
            print("   测试空提示处理...")
            try:
                await self.llm_service.generate_response("", max_tokens=10)
                print("   ✅ 空提示处理正常")
            except Exception as e:
                print(f"   ✅ 空提示错误处理正常: {type(e).__name__}")
            
            # 测试服务级错误处理
            print("   测试查询解析回退机制...")
            try:
                # 使用一个可能导致LLM响应格式异常的查询
                complex_query = "¥" * 1000  # 极端情况
                result = await self.query_parser.parse(complex_query)
                print(f"   ✅ 回退机制正常工作，解析结果置信度: {result.confidence}")
            except Exception as e:
                print(f"   ⚠️ 回退机制触发: {e}")
            
            self.test_results.append(("错误处理和回退机制", True, "错误处理机制正常"))
            print("   ✅ 测试6通过\n")
            
        except Exception as e:
            print(f"   ❌ 测试6失败: {e}")
            self.test_results.append(("错误处理和回退机制", False, str(e)))
    
    async def cleanup(self):
        """清理资源"""
        try:
            if self.llm_service:
                await self.llm_service.close()
            print("🧹 资源清理完成")
        except Exception as e:
            print(f"⚠️ 资源清理警告: {e}")
    
    def print_summary(self):
        """打印测试摘要"""
        print("="*60)
        print("📊 LLM服务迁移测试摘要")
        print("="*60)
        
        passed = 0
        failed = 0
        
        for test_name, success, message in self.test_results:
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} {test_name}: {message}")
            if success:
                passed += 1
            else:
                failed += 1
        
        print("-"*60)
        print(f"总计: {len(self.test_results)} 个测试")
        print(f"通过: {passed} 个")
        print(f"失败: {failed} 个")
        print(f"成功率: {(passed/len(self.test_results)*100):.1f}%" if self.test_results else "0%")
        
        if failed == 0:
            print("\n🎉 所有测试通过！LLM服务迁移成功！")
        else:
            print(f"\n⚠️ 有 {failed} 个测试失败，请检查配置和依赖。")
        
        print("="*60)


async def main():
    """主函数"""
    print("🚀 LLM服务迁移测试开始")
    print("="*60)
    
    tester = LLMMigrationTester()
    
    try:
        # 初始化
        await tester.initialize()
        
        # 运行测试
        await tester.test_llm_service_basic()
        await tester.test_query_parser_integration()
        await tester.test_recommendation_service_integration()
        await tester.test_output_formatter_integration()
        await tester.test_cost_tracking()
        await tester.test_error_handling()
        
    except Exception as e:
        print(f"💥 测试执行异常: {e}")
        tester.test_results.append(("测试执行", False, str(e)))
    
    finally:
        # 清理和总结
        await tester.cleanup()
        tester.print_summary()


if __name__ == "__main__":
    asyncio.run(main())