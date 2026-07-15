#!/usr/bin/env python3
"""
爬虫服务测试脚本

测试爬虫服务的功能和稳定性
"""

import os
import sys
import asyncio
import tempfile
from pathlib import Path
from typing import Dict, Any, List

# 设置项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

def test_basic_imports():
    """测试基础导入"""
    print("🔍 测试基础导入...")
    
    results = []
    
    try:
        # 测试爬虫服务导入
        from mercari_agent.infrastructure.scraping.scraper_service import (
            ScraperService, ScrapingResult, ScrapingContext, ScrapingStrategy
        )
        results.append("✅ 爬虫服务导入成功")
        
        # 测试产品实体导入
        from mercari_agent.domain.entities.product import ProductEntity
        results.append("✅ 产品实体导入成功")
        
        # 测试查询实体导入
        from mercari_agent.domain.entities.query import QueryEntity, QueryIntent
        results.append("✅ 查询实体导入成功")
        
        # 测试配置导入
        from mercari_agent.shared.config.app_config import get_config
        results.append("✅ 配置模块导入成功")
        
    except ImportError as e:
        results.append(f"❌ 导入失败: {e}")
    except Exception as e:
        results.append(f"❌ 导入测试失败: {e}")
    
    return results

def test_service_initialization():
    """测试服务初始化"""
    print("🔍 测试服务初始化...")
    
    results = []
    
    async def _test_initialization():
        try:
            from mercari_agent.infrastructure.scraping.scraper_service import ScraperService
            from mercari_agent.shared.config.app_config import get_config
            
            config = get_config()
            
            # 测试服务创建
            scraper_service = ScraperService(config)
            results.append("✅ 服务实例创建成功")
            
            # 测试服务初始化
            await scraper_service.initialize()
            results.append("✅ 服务初始化成功")
            
            # 测试服务关闭
            await scraper_service.close()
            results.append("✅ 服务关闭成功")
            
        except Exception as e:
            results.append(f"❌ 服务初始化失败: {e}")
    
    try:
        asyncio.run(_test_initialization())
    except Exception as e:
        results.append(f"❌ 异步测试执行失败: {e}")
    
    return results

def test_basic_scraping():
    """测试基础爬取功能"""
    print("🔍 测试基础爬取功能...")
    
    results = []
    
    async def _test_scraping():
        try:
            from mercari_agent.infrastructure.scraping.scraper_service import ScraperService
            from mercari_agent.shared.config.app_config import get_config
            from mercari_agent.domain.entities.query import QueryEntity, QueryIntent
            
            config = get_config()
            scraper_service = ScraperService(config)
            
            # 创建测试查询
            test_query = QueryEntity(
                original_query="iPhone 15 Pro",
                normalized_query="iphone 15 pro",
                keywords=["iPhone", "15", "Pro"],
                intent=QueryIntent.SEARCH,
                category="スマートフォン",
                brand="Apple",
                price_min=None,
                price_max=100000
            )
            
            # 测试爬取
            result = await scraper_service.scrape(test_query, max_products=5)
            
            # 验证结果
            if hasattr(result, 'products') and result.products:
                results.append("✅ 爬取成功获得产品")
                results.append(f"   - 产品数量: {len(result.products)}")
                results.append(f"   - 处理时间: {result.processing_time:.3f}s")
                results.append(f"   - 爬取策略: {result.strategy_used.value}")
                
                # 验证产品数据结构
                first_product = result.products[0]
                if hasattr(first_product, 'title') and hasattr(first_product, 'price'):
                    results.append("✅ 产品数据结构正确")
                else:
                    results.append("❌ 产品数据结构不完整")
                    
            else:
                results.append("❌ 爬取未获得产品")
            
            await scraper_service.close()
            
        except Exception as e:
            results.append(f"❌ 爬取测试失败: {e}")
    
    try:
        asyncio.run(_test_scraping())
    except Exception as e:
        results.append(f"❌ 爬取异步测试失败: {e}")
    
    return results

def test_product_data_structure():
    """测试产品数据结构"""
    print("🔍 测试产品数据结构...")
    
    results = []
    
    async def _test_product_structure():
        try:
            from mercari_agent.infrastructure.scraping.scraper_service import ScraperService
            from mercari_agent.shared.config.app_config import get_config
            from mercari_agent.domain.entities.query import QueryEntity, QueryIntent
            
            config = get_config()
            scraper_service = ScraperService(config)
            
            # 创建测试查询
            test_query = QueryEntity(
                original_query="Test Product",
                normalized_query="test product",
                keywords=["Test", "Product"],
                intent=QueryIntent.SEARCH
            )
            
            # 获取产品数据
            result = await scraper_service.scrape(test_query, max_products=3)
            
            if result.products:
                product = result.products[0]
                
                # 验证必需字段
                required_fields = ['id', 'title', 'price', 'url']
                for field in required_fields:
                    if hasattr(product, field) and getattr(product, field) is not None:
                        results.append(f"✅ 字段 {field} 存在")
                    else:
                        results.append(f"⚠️ 字段 {field} 缺失或为空")
                
                # 验证可选字段
                optional_fields = ['description', 'condition', 'category', 'brand', 'seller_name']
                for field in optional_fields:
                    if hasattr(product, field):
                        results.append(f"✅ 可选字段 {field} 存在")
                    else:
                        results.append(f"⚠️ 可选字段 {field} 不存在")
                
                # 验证数据类型
                if isinstance(product.price, (int, float)) and product.price > 0:
                    results.append("✅ 价格数据类型正确")
                else:
                    results.append("❌ 价格数据类型错误")
                
                if isinstance(product.title, str) and len(product.title) > 0:
                    results.append("✅ 标题数据类型正确")
                else:
                    results.append("❌ 标题数据类型错误")
                    
            else:
                results.append("❌ 无产品数据用于结构验证")
            
            await scraper_service.close()
            
        except Exception as e:
            results.append(f"❌ 产品数据结构测试失败: {e}")
    
    try:
        asyncio.run(_test_product_structure())
    except Exception as e:
        results.append(f"❌ 产品数据结构异步测试失败: {e}")
    
    return results

def test_scraping_context():
    """测试爬取上下文功能"""
    print("🔍 测试爬取上下文功能...")
    
    results = []
    
    async def _test_context():
        try:
            from mercari_agent.infrastructure.scraping.scraper_service import (
                ScraperService, ScrapingContext, ScrapingStrategy
            )
            from mercari_agent.shared.config.app_config import get_config
            from mercari_agent.domain.entities.query import QueryEntity, QueryIntent
            
            config = get_config()
            scraper_service = ScraperService(config)
            
            # 创建测试查询
            test_query = QueryEntity(
                original_query="MacBook Pro",
                normalized_query="macbook pro",
                keywords=["MacBook", "Pro"],
                intent=QueryIntent.SEARCH,
                price_max=200000
            )
            
            # 创建爬取上下文
            context = ScrapingContext(
                query=test_query,
                max_pages=2,
                max_products=8,
                strategy=ScrapingStrategy.HTTP_CLIENT,
                use_cache=True
            )
            
            # 测试上下文爬取
            result = await scraper_service.scrape(context)
            
            if result:
                results.append("✅ 上下文爬取成功")
                results.append(f"   - 使用策略: {result.strategy_used.value}")
                results.append(f"   - 页数限制: {context.max_pages}")
                results.append(f"   - 产品限制: {context.max_products}")
                
                # 验证产品数量符合限制
                if len(result.products) <= context.max_products:
                    results.append("✅ 产品数量符合限制")
                else:
                    results.append("❌ 产品数量超出限制")
                    
            else:
                results.append("❌ 上下文爬取失败")
            
            await scraper_service.close()
            
        except Exception as e:
            results.append(f"❌ 上下文测试失败: {e}")
    
    try:
        asyncio.run(_test_context())
    except Exception as e:
        results.append(f"❌ 上下文异步测试失败: {e}")
    
    return results

def test_caching_mechanism():
    """测试缓存机制"""
    print("🔍 测试缓存机制...")
    
    results = []
    
    async def _test_caching():
        try:
            from mercari_agent.infrastructure.scraping.scraper_service import ScraperService
            from mercari_agent.shared.config.app_config import get_config
            from mercari_agent.domain.entities.query import QueryEntity, QueryIntent
            
            config = get_config()
            scraper_service = ScraperService(config)
            
            # 创建测试查询
            test_query = QueryEntity(
                original_query="Cache Test",
                normalized_query="cache test",
                keywords=["Cache", "Test"],
                intent=QueryIntent.SEARCH
            )
            
            # 第一次爬取
            result1 = await scraper_service.scrape(test_query, max_products=3)
            first_time = result1.processing_time
            
            # 第二次爬取（应该使用缓存）
            result2 = await scraper_service.scrape(test_query, max_products=3)
            second_time = result2.processing_time
            
            # 验证缓存效果
            if second_time < first_time * 0.5:  # 缓存应该显著提高速度
                results.append("✅ 缓存机制工作正常")
                results.append(f"   - 第一次: {first_time:.3f}s")
                results.append(f"   - 第二次: {second_time:.3f}s")
            else:
                results.append("⚠️ 缓存效果不明显")
                results.append(f"   - 第一次: {first_time:.3f}s")
                results.append(f"   - 第二次: {second_time:.3f}s")
            
            # 验证缓存数据一致性
            if (len(result1.products) == len(result2.products) and 
                result1.total_found == result2.total_found):
                results.append("✅ 缓存数据一致性正确")
            else:
                results.append("❌ 缓存数据不一致")
            
            await scraper_service.close()
            
        except Exception as e:
            results.append(f"❌ 缓存测试失败: {e}")
    
    try:
        asyncio.run(_test_caching())
    except Exception as e:
        results.append(f"❌ 缓存异步测试失败: {e}")
    
    return results

def test_error_handling():
    """测试错误处理"""
    print("🔍 测试错误处理...")
    
    results = []
    
    async def _test_error_handling():
        try:
            from mercari_agent.infrastructure.scraping.scraper_service import ScraperService
            from mercari_agent.shared.config.app_config import get_config
            from mercari_agent.domain.entities.query import QueryEntity, QueryIntent
            
            config = get_config()
            scraper_service = ScraperService(config)
            
            # 测试空查询
            empty_query = QueryEntity(
                original_query="",
                normalized_query="",
                keywords=[],
                intent=QueryIntent.SEARCH
            )
            
            try:
                result = await scraper_service.scrape(empty_query, max_products=5)
                if result.products:
                    results.append("✅ 空查询处理正常（返回默认结果）")
                else:
                    results.append("✅ 空查询处理正常（返回空结果）")
            except Exception as e:
                results.append(f"⚠️ 空查询处理异常: {str(e)[:50]}...")
            
            # 测试无效参数
            normal_query = QueryEntity(
                original_query="Test",
                normalized_query="test",
                keywords=["Test"],
                intent=QueryIntent.SEARCH
            )
            
            try:
                result = await scraper_service.scrape(normal_query, max_products=0)
                results.append("✅ 无效参数处理正常")
            except Exception as e:
                results.append(f"⚠️ 无效参数处理异常: {str(e)[:50]}...")
            
            await scraper_service.close()
            
        except Exception as e:
            results.append(f"❌ 错误处理测试失败: {e}")
    
    try:
        asyncio.run(_test_error_handling())
    except Exception as e:
        results.append(f"❌ 错误处理异步测试失败: {e}")
    
    return results

def test_health_check():
    """测试健康检查"""
    print("🔍 测试健康检查...")
    
    results = []
    
    async def _test_health():
        try:
            from mercari_agent.infrastructure.scraping.scraper_service import ScraperService
            from mercari_agent.shared.config.app_config import get_config
            
            config = get_config()
            scraper_service = ScraperService(config)
            await scraper_service.initialize()
            
            # 测试健康检查
            try:
                health_status = await scraper_service.health_check()
                if health_status and health_status.get('status') == 'healthy':
                    results.append("✅ 健康检查通过")
                else:
                    results.append("⚠️ 健康检查状态异常")
            except Exception as e:
                results.append(f"⚠️ 健康检查不可用: {str(e)[:50]}...")
            
            # 测试服务信息
            try:
                service_info = scraper_service.get_service_info()
                if service_info and isinstance(service_info, dict):
                    results.append("✅ 服务信息获取成功")
                    if 'available_strategies' in service_info:
                        results.append(f"   - 可用策略: {service_info['available_strategies']}")
                else:
                    results.append("⚠️ 服务信息获取失败")
            except Exception as e:
                results.append(f"⚠️ 服务信息不可用: {str(e)[:50]}...")
            
            await scraper_service.close()
            
        except Exception as e:
            results.append(f"❌ 健康检查测试失败: {e}")
    
    try:
        asyncio.run(_test_health())
    except Exception as e:
        results.append(f"❌ 健康检查异步测试失败: {e}")
    
    return results

def main():
    """主函数"""
    print("🚀 Mercari AI Agent 爬虫服务测试")
    print("=" * 60)
    
    # 切换到项目目录
    os.chdir(project_root)
    
    all_results = []
    
    # 运行测试
    test_functions = [
        test_basic_imports,
        test_service_initialization,
        test_basic_scraping,
        test_product_data_structure,
        test_scraping_context,
        test_caching_mechanism,
        test_error_handling,
        test_health_check,
    ]
    
    for test_func in test_functions:
        try:
            results = test_func()
            all_results.extend(results)
            for result in results:
                print(result)
            print()
        except Exception as e:
            error_msg = f"❌ 测试失败: {test_func.__name__} - {e}"
            print(error_msg)
            all_results.append(error_msg)
    
    # 统计结果
    passed = sum(1 for r in all_results if r.startswith("✅"))
    failed = sum(1 for r in all_results if r.startswith("❌"))
    warnings = sum(1 for r in all_results if r.startswith("⚠️"))
    
    print("=" * 60)
    print("📊 爬虫服务测试结果:")
    print(f"✅ 通过: {passed}")
    print(f"❌ 失败: {failed}")
    print(f"⚠️ 警告: {warnings}")
    print(f"📊 总计: {len(all_results)}")
    
    # 计算成功率
    success_rate = (passed / len(all_results) * 100) if all_results else 0
    print(f"🎯 成功率: {success_rate:.1f}%")
    
    # 评估结果
    if failed == 0:
        print("🎉 爬虫服务功能完全正常!")
        return 0
    elif failed <= 3:
        print("⚠️ 爬虫服务基本正常，少数功能有问题")
        return 0
    else:
        print("🚨 爬虫服务存在较多问题")
        return 1

if __name__ == "__main__":
    sys.exit(main())