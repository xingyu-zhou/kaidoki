#!/usr/bin/env python3
"""
测试查询参数传递修复效果

该脚本用于验证修复后的查询参数传递是否正常工作。
"""

import asyncio
import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mercari_agent.core.query_parser import QueryParser, ParsedQueryResult
from mercari_agent.core.tool_orchestrator import ToolOrchestrator, ToolExecutionContext
from mercari_agent.models.query import ParsedQuery
from mercari_agent.services.llm_service import LLMService
from mercari_agent.services.scraper_service import ScraperService
from mercari_agent.services.analysis_service import AnalysisService
from mercari_agent.core.output_formatter import OutputFormatter
from mercari_agent.config.settings import settings


async def test_query_parameter_fix():
    """测试查询参数传递修复"""
    
    print("=" * 60)
    print("🧪 测试查询参数传递修复效果")
    print("=" * 60)
    
    # 初始化服务
    llm_service = LLMService()
    scraper_service = ScraperService()
    analysis_service = AnalysisService()
    output_formatter = OutputFormatter()
    
    # 初始化组件
    query_parser = QueryParser(llm_service)
    tool_orchestrator = ToolOrchestrator(
        llm_service=llm_service,
        scraper_service=scraper_service,
        analysis_service=analysis_service,
        output_formatter=output_formatter
    )
    
    # 测试用例
    test_cases = [
        {
            "name": "正常查询",
            "query": "iPhone 16",
            "expected_result": "query字段应包含'iPhone 16'"
        },
        {
            "name": "空查询",
            "query": "",
            "expected_result": "应使用回退查询"
        },
        {
            "name": "空白查询",
            "query": "   ",
            "expected_result": "应使用回退查询"
        },
        {
            "name": "日语查询",
            "query": "スマートフォン",
            "expected_result": "query字段应包含'スマートフォン'"
        }
    ]
    
    # 执行测试
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 测试案例 {i}: {test_case['name']}")
        print(f"🔍 查询: '{test_case['query']}'")
        print(f"📝 预期结果: {test_case['expected_result']}")
        
        try:
            # 1. 测试查询解析器
            print("\n🔧 测试查询解析器...")
            parsed_result = await query_parser.parse_query(test_case['query'])
            
            print(f"✅ 解析结果:")
            print(f"   - refined_query: '{parsed_result.refined_query}'")
            print(f"   - category: '{parsed_result.category}'")
            print(f"   - intent: '{parsed_result.intent}'")
            print(f"   - price_range: {parsed_result.price_range}")
            
            # 验证refined_query不为空
            if parsed_result.refined_query and parsed_result.refined_query.strip():
                print(f"✅ refined_query 字段已正确设置")
            else:
                print(f"❌ refined_query 字段为空或未设置")
            
            # 2. 测试工具调用
            print("\n🛠️  测试工具调用...")
            context = ToolExecutionContext(
                user_query=test_case['query'],
                user_id="test_user",
                session_id="test_session"
            )
            
            # 模拟工具调用（不实际执行，只验证参数处理）
            tool_name = "search_products"
            params = {"query": test_case['query']}
            
            # 测试参数修复
            fixed_params = tool_orchestrator._fix_tool_parameters(
                tool_name, params, context, {}
            )
            
            print(f"✅ 参数修复结果:")
            print(f"   - 原始参数: {params}")
            print(f"   - 修复后参数: {fixed_params}")
            
            # 验证修复后的参数
            if fixed_params.get('query') and fixed_params['query'].strip():
                print(f"✅ 查询参数已正确修复")
            else:
                print(f"❌ 查询参数修复失败")
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("🎯 测试完成！")
    print("=" * 60)


async def test_backward_compatibility():
    """测试向后兼容性"""
    
    print("\n" + "=" * 60)
    print("🔄 测试向后兼容性")
    print("=" * 60)
    
    # 测试ParsedQueryResult的向后兼容性
    try:
        # 创建一个模拟的ParsedQuery
        parsed_query = ParsedQuery(
            original_query="test query",
            normalized_query="test query",
            keywords=["test", "query"]
        )
        
        # 测试新的字段是否有默认值
        result = ParsedQueryResult(
            query=parsed_query,
            complexity="simple",
            confidence=0.8,
            processing_time=0.1
        )
        
        print("✅ ParsedQueryResult 向后兼容性测试通过")
        print(f"   - refined_query: '{result.refined_query}'")
        print(f"   - category: '{result.category}'")
        print(f"   - intent: '{result.intent}'")
        print(f"   - price_range: {result.price_range}")
        
    except Exception as e:
        print(f"❌ 向后兼容性测试失败: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主函数"""
    await test_query_parameter_fix()
    await test_backward_compatibility()


if __name__ == "__main__":
    asyncio.run(main())