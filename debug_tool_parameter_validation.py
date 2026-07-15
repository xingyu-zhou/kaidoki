#!/usr/bin/env python3
"""
调试工具参数验证问题

该脚本专门用于诊断 analyze_query 工具的参数验证失败问题。
"""

import asyncio
import json
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.mercari_agent.core.tools.search_tools import QueryAnalyzerTool
from src.mercari_agent.services.llm_service import LLMService
from src.mercari_agent.config.settings import load_settings


async def debug_tool_parameter_validation():
    """调试工具参数验证问题"""
    
    print("=== 调试工具参数验证问题 ===")
    
    # 1. 初始化LLM服务
    try:
        settings = load_settings()
        llm_service = LLMService(settings.llm)
        print("✅ LLM服务初始化成功")
    except Exception as e:
        print(f"❌ LLM服务初始化失败: {e}")
        return
    
    # 2. 创建QueryAnalyzerTool实例
    try:
        query_tool = QueryAnalyzerTool(llm_service)
        print("✅ QueryAnalyzerTool创建成功")
        print(f"工具名称: {query_tool.name}")
        print(f"工具描述: {query_tool.description}")
    except Exception as e:
        print(f"❌ QueryAnalyzerTool创建失败: {e}")
        return
    
    # 3. 检查工具schema
    try:
        schema = query_tool.schema
        print("✅ 工具schema获取成功")
        print("Schema定义:")
        print(json.dumps(schema, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"❌ 工具schema获取失败: {e}")
        return
    
    # 4. 测试参数验证
    test_cases = [
        {"query": "iPhone 16"},  # 正确参数
        {"query": "iPhone 16", "context": "搜索手机"},  # 正确参数（含可选参数）
        {},  # 缺少必需参数
        {"wrong_param": "value"},  # 错误参数名
    ]
    
    print("\n=== 测试参数验证 ===")
    for i, params in enumerate(test_cases):
        print(f"\n测试案例 {i+1}: {params}")
        
        try:
            is_valid = query_tool.validate_parameters(params)
            print(f"参数验证结果: {'通过' if is_valid else '失败'}")
            
            if is_valid:
                print("尝试执行工具...")
                result = await query_tool.call(**params)
                print(f"执行结果: {result.status.value}")
                if result.error:
                    print(f"错误信息: {result.error}")
                elif result.data:
                    print(f"返回数据类型: {type(result.data)}")
        except Exception as e:
            print(f"执行异常: {e}")
    
    # 5. 检查工具注册表的调用方式
    print("\n=== 检查工具注册表调用方式 ===")
    from src.mercari_agent.core.tools.tool_registry import ToolRegistry
    
    try:
        registry = ToolRegistry()
        registry.register(query_tool)
        print("✅ 工具注册成功")
        
        # 测试通过注册表调用
        test_params = {"query": "iPhone 16"}
        print(f"通过注册表调用工具，参数: {test_params}")
        result = await registry.call_tool("analyze_query", **test_params)
        print(f"调用结果: {result.status.value}")
        if result.error:
            print(f"错误信息: {result.error}")
        
    except Exception as e:
        print(f"❌ 工具注册表调用失败: {e}")
    
    # 6. 检查LLM响应格式
    print("\n=== 检查LLM响应格式 ===")
    try:
        test_prompt = """
        分析以下日语购物查询，提取结构化信息：
        
        查询: iPhone 16
        上下文: 
        
        请提取以下信息：
        1. 查询意图 (搜索/比较/推荐/过滤/排序/分析/问题)
        2. 关键词
        3. 价格范围
        4. 商品类别
        5. 品牌
        6. 商品状态
        7. 排序偏好
        8. 其他过滤条件
        
        返回JSON格式结果。
        """
        
        print("发送测试提示到LLM...")
        response = await llm_service.generate_response(
            test_prompt,
            response_format="json"
        )
        
        print(f"LLM响应类型: {type(response)}")
        if hasattr(response, 'content'):
            print(f"响应内容: {response.content}")
        else:
            print(f"响应内容: {response}")
        
    except Exception as e:
        print(f"❌ LLM响应测试失败: {e}")


if __name__ == "__main__":
    asyncio.run(debug_tool_parameter_validation())