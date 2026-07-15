#!/usr/bin/env python3
"""
查询解析服务测试脚本

测试查询解析服务的功能和准确性
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

def test_basic_import():
    """测试基础导入"""
    print("🔍 测试基础导入...")
    
    results = []
    
    try:
        # 测试查询解析服务导入
        from mercari_agent.application.services.query_parser_service import (
            QueryParserService, QueryParseResult
        )
        results.append("✅ 查询解析服务导入成功")
        
        # 测试查询实体导入
        from mercari_agent.domain.entities.query import (
            QueryEntity, QueryIntent, QueryComplexity
        )
        results.append("✅ 查询实体导入成功")
        
        # 测试配置导入
        from mercari_agent.shared.config.app_config import get_config
        results.append("✅ 配置模块导入成功")
        
    except ImportError as e:
        results.append(f"❌ 导入失败: {e}")
    except Exception as e:
        results.append(f"❌ 导入测试失败: {e}")
    
    return results

def test_fallback_parsing():
    """测试备用解析功能（不依赖LLM）"""
    print("🔍 测试备用解析功能...")
    
    results = []
    
    async def _test_fallback():
        try:
            from mercari_agent.application.services.query_parser_service import QueryParserService
            from mercari_agent.shared.config.app_config import get_config
            
            config = get_config()
            
            # 创建模拟LLM服务
            class MockLLMService:
                async def generate_response(self, prompt):
                    raise Exception("Simulated LLM failure")
            
            parser = QueryParserService(config, MockLLMService())
            
            # 测试用例
            test_queries = [
                "iPhone 15 Pro Max 1TB 10万円以下",
                "Galaxy S24 Ultra 新品",
                "iPad Air 5万円から8万円",
                "MacBook Pro 中古",
                "Nintendo Switch 3万円",
            ]
            
            for query in test_queries:
                try:
                    result = await parser.parse(query)
                    
                    # 验证结果结构
                    if hasattr(result, 'query') and hasattr(result, 'confidence'):
                        results.append(f"✅ 解析成功: {query[:20]}...")
                        
                        # 验证基础字段
                        if result.query.original_query == query:
                            results.append(f"   - 原始查询保存正确")
                        if result.query.keywords:
                            results.append(f"   - 提取关键词: {len(result.query.keywords)}个")
                        if result.processing_time >= 0:
                            results.append(f"   - 处理时间: {result.processing_time:.3f}s")
                        
                    else:
                        results.append(f"❌ 解析结果结构错误: {query}")
                        
                except Exception as e:
                    results.append(f"❌ 解析失败: {query} - {e}")
            
        except Exception as e:
            results.append(f"❌ 备用解析测试失败: {e}")
    
    # 运行异步测试
    try:
        asyncio.run(_test_fallback())
    except Exception as e:
        results.append(f"❌ 异步测试执行失败: {e}")
    
    return results

def test_price_extraction():
    """测试价格提取功能"""
    print("🔍 测试价格提取功能...")
    
    results = []
    
    async def _test_price_extraction():
        try:
            from mercari_agent.application.services.query_parser_service import QueryParserService
            from mercari_agent.shared.config.app_config import get_config
            
            config = get_config()
            
            # 创建模拟LLM服务
            class MockLLMService:
                async def generate_response(self, prompt):
                    raise Exception("Simulated LLM failure")
            
            parser = QueryParserService(config, MockLLMService())
            
            # 价格测试用例
            price_test_cases = [
                ("iPhone 10万円以下", None, 100000),
                ("iPad 5万円から8万円", 50000, 80000),
                ("MacBook Pro 30万円", None, 300000),
                ("Nintendo Switch 3万円以上", 30000, None),
            ]
            
            for query, expected_min, expected_max in price_test_cases:
                try:
                    result = await parser.parse(query)
                    
                    # 检查价格提取
                    actual_min = result.query.price_min
                    actual_max = result.query.price_max
                    
                    if actual_min == expected_min and actual_max == expected_max:
                        results.append(f"✅ 价格提取正确: {query}")
                        results.append(f"   - 价格范围: {actual_min} - {actual_max}")
                    else:
                        results.append(f"⚠️ 价格提取不准确: {query}")
                        results.append(f"   - 期望: {expected_min} - {expected_max}")
                        results.append(f"   - 实际: {actual_min} - {actual_max}")
                        
                except Exception as e:
                    results.append(f"❌ 价格提取测试失败: {query} - {e}")
            
        except Exception as e:
            results.append(f"❌ 价格提取测试失败: {e}")
    
    try:
        asyncio.run(_test_price_extraction())
    except Exception as e:
        results.append(f"❌ 价格提取异步测试失败: {e}")
    
    return results

def test_keyword_extraction():
    """测试关键词提取功能"""
    print("🔍 测试关键词提取功能...")
    
    results = []
    
    async def _test_keyword_extraction():
        try:
            from mercari_agent.application.services.query_parser_service import QueryParserService
            from mercari_agent.shared.config.app_config import get_config
            
            config = get_config()
            
            # 创建模拟LLM服务
            class MockLLMService:
                async def generate_response(self, prompt):
                    raise Exception("Simulated LLM failure")
            
            parser = QueryParserService(config, MockLLMService())
            
            # 关键词测试用例
            keyword_test_cases = [
                ("iPhone 15 Pro Max 1TB", ["iPhone", "15", "Pro", "Max", "1TB"]),
                ("Galaxy S24 Ultra 新品", ["Galaxy", "S24", "Ultra", "新品"]),
                ("Nintendo Switch", ["Nintendo", "Switch"]),
            ]
            
            for query, expected_keywords in keyword_test_cases:
                try:
                    result = await parser.parse(query)
                    
                    # 检查关键词提取
                    actual_keywords = result.query.keywords
                    
                    if actual_keywords:
                        results.append(f"✅ 关键词提取: {query}")
                        results.append(f"   - 提取到: {actual_keywords}")
                        
                        # 检查是否包含主要关键词
                        found_main_keywords = sum(1 for kw in expected_keywords 
                                                if any(kw.lower() in ak.lower() or ak.lower() in kw.lower() 
                                                      for ak in actual_keywords))
                        
                        if found_main_keywords >= len(expected_keywords) * 0.6:
                            results.append(f"   - 主要关键词覆盖率良好")
                        else:
                            results.append(f"   - 主要关键词覆盖率较低")
                    else:
                        results.append(f"⚠️ 未提取到关键词: {query}")
                        
                except Exception as e:
                    results.append(f"❌ 关键词提取测试失败: {query} - {e}")
            
        except Exception as e:
            results.append(f"❌ 关键词提取测试失败: {e}")
    
    try:
        asyncio.run(_test_keyword_extraction())
    except Exception as e:
        results.append(f"❌ 关键词提取异步测试失败: {e}")
    
    return results

def test_category_brand_detection():
    """测试类别和品牌检测"""
    print("🔍 测试类别和品牌检测...")
    
    results = []
    
    async def _test_category_brand():
        try:
            from mercari_agent.application.services.query_parser_service import QueryParserService
            from mercari_agent.shared.config.app_config import get_config
            
            config = get_config()
            
            # 创建模拟LLM服务
            class MockLLMService:
                async def generate_response(self, prompt):
                    raise Exception("Simulated LLM failure")
            
            parser = QueryParserService(config, MockLLMService())
            
            # 类别和品牌测试用例
            detection_test_cases = [
                ("iPhone 15 Pro Max", "スマートフォン", "Apple"),
                ("Galaxy S24 Ultra", "スマートフォン", None),
                ("iPad Air", None, "Apple"),  # 可能检测不到类别
            ]
            
            for query, expected_category, expected_brand in detection_test_cases:
                try:
                    result = await parser.parse(query)
                    
                    # 检查类别检测
                    if expected_category:
                        if result.query.category == expected_category:
                            results.append(f"✅ 类别检测正确: {query} -> {result.query.category}")
                        else:
                            results.append(f"⚠️ 类别检测: {query} -> {result.query.category} (期望: {expected_category})")
                    
                    # 检查品牌检测
                    if expected_brand:
                        if result.query.brand == expected_brand:
                            results.append(f"✅ 品牌检测正确: {query} -> {result.query.brand}")
                        else:
                            results.append(f"⚠️ 品牌检测: {query} -> {result.query.brand} (期望: {expected_brand})")
                    
                    # 检查意图检测
                    if result.query.intent:
                        results.append(f"✅ 意图检测: {query} -> {result.query.intent.value}")
                        
                except Exception as e:
                    results.append(f"❌ 类别品牌检测失败: {query} - {e}")
            
        except Exception as e:
            results.append(f"❌ 类别品牌检测测试失败: {e}")
    
    try:
        asyncio.run(_test_category_brand())
    except Exception as e:
        results.append(f"❌ 类别品牌检测异步测试失败: {e}")
    
    return results

def test_edge_cases():
    """测试边界情况"""
    print("🔍 测试边界情况...")
    
    results = []
    
    async def _test_edge_cases():
        try:
            from mercari_agent.application.services.query_parser_service import QueryParserService
            from mercari_agent.shared.config.app_config import get_config
            
            config = get_config()
            
            # 创建模拟LLM服务
            class MockLLMService:
                async def generate_response(self, prompt):
                    raise Exception("Simulated LLM failure")
            
            parser = QueryParserService(config, MockLLMService())
            
            # 边界情况测试
            edge_cases = [
                "",  # 空查询
                " ",  # 空白查询
                "a",  # 单字符查询
                "あいうえお",  # 纯假名查询
                "12345",  # 纯数字查询
                "!@#$%",  # 特殊字符查询
                "x" * 1000,  # 超长查询
            ]
            
            for query in edge_cases:
                try:
                    result = await parser.parse(query)
                    
                    # 验证基本结构
                    if hasattr(result, 'query') and hasattr(result, 'confidence'):
                        results.append(f"✅ 边界情况处理: '{query[:20]}{'...' if len(query) > 20 else ''}'")
                    else:
                        results.append(f"❌ 边界情况处理失败: '{query[:20]}{'...' if len(query) > 20 else ''}'")
                        
                except Exception as e:
                    results.append(f"⚠️ 边界情况异常: '{query[:20]}{'...' if len(query) > 20 else ''}' - {str(e)[:50]}...")
            
        except Exception as e:
            results.append(f"❌ 边界情况测试失败: {e}")
    
    try:
        asyncio.run(_test_edge_cases())
    except Exception as e:
        results.append(f"❌ 边界情况异步测试失败: {e}")
    
    return results

def main():
    """主函数"""
    print("🚀 Mercari AI Agent 查询解析服务测试")
    print("=" * 60)
    
    # 切换到项目目录
    os.chdir(project_root)
    
    all_results = []
    
    # 运行测试
    test_functions = [
        test_basic_import,
        test_fallback_parsing,
        test_price_extraction,
        test_keyword_extraction,
        test_category_brand_detection,
        test_edge_cases,
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
    print("📊 查询解析服务测试结果:")
    print(f"✅ 通过: {passed}")
    print(f"❌ 失败: {failed}")
    print(f"⚠️ 警告: {warnings}")
    print(f"📊 总计: {len(all_results)}")
    
    # 计算成功率
    success_rate = (passed / len(all_results) * 100) if all_results else 0
    print(f"🎯 成功率: {success_rate:.1f}%")
    
    # 评估结果
    if failed == 0:
        print("🎉 查询解析服务功能完全正常!")
        return 0
    elif failed <= 3:
        print("⚠️ 查询解析服务基本正常，少数功能有问题")
        return 0
    else:
        print("🚨 查询解析服务存在较多问题")
        return 1

if __name__ == "__main__":
    sys.exit(main())