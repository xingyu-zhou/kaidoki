#!/usr/bin/env python3
"""
测试日语价格解析问题的脚本

用于验证"万円"等日语数字单位的解析准确性
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "mercari_ai_agent_refactored" / "src"))
sys.path.insert(0, str(Path(__file__).parent / "mercari_ai_agent" / "src"))

# 测试用例
test_cases = [
    "Nintendo Switch 2万円以下",
    "MacBook Pro M3 15万円から20万円", 
    "新品未使用 iPhone 14",
    "中古良品 PlayStation 5",
    "送料無料 カメラ",
    # 额外测试用例
    "3万円",
    "10万円以上",
    "5万円以下", 
    "1万2千円",
    "20万円から30万円まで"
]

def extract_numbers_simple(text):
    """简单数字提取（当前的错误方式）"""
    import re
    numbers = re.findall(r'\d+', text)
    return [int(n) for n in numbers]

def extract_numbers_with_units(text):
    """带单位的数字提取（正确方式）"""
    import re
    
    # 处理万単位
    pattern = r'(\d+)万円'
    matches = re.findall(pattern, text)
    results = []
    
    for match in matches:
        # 将万単位转换为实际数值
        base_number = int(match)
        actual_value = base_number * 10000
        results.append(actual_value)
        print(f"  发现 {match}万円 -> {actual_value}円")
    
    # 处理普通円
    pattern = r'(\d+)円'
    matches = re.findall(pattern, text)
    for match in matches:
        if f"{match}万円" not in text:  # 避免重复计算
            results.append(int(match))
            print(f"  发现 {match}円")
    
    return results

async def test_current_parser():
    """测试当前的解析器"""
    try:
        # 尝试导入refactored版本
        from mercari_agent.application.services.query_parser_service import QueryParserService
        from mercari_agent.shared.config.app_config import get_config
        
        config = get_config()
        parser = QueryParserService(config, None)  # 暂时不需要LLM
        
        print("=== 测试 Refactored 版本解析器 ===")
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n{i}. 测试用例: {test_case}")
            try:
                result = await parser.parse(test_case)
                print(f"   解析结果:")
                print(f"   - 价格范围: {result.query.price_min} - {result.query.price_max}")
                print(f"   - 关键词: {result.query.keywords}")
                print(f"   - 置信度: {result.confidence}")
            except Exception as e:
                print(f"   解析失败: {e}")
        
    except ImportError as e:
        print(f"无法导入 refactored 版本: {e}")

def test_manual_parsing():
    """手动测试价格解析逻辑"""
    print("\n=== 手动测试价格解析逻辑 ===")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. 测试用例: {test_case}")
        
        print("  当前（错误）解析方式:")
        simple_numbers = extract_numbers_simple(test_case)
        print(f"    提取的数字: {simple_numbers}")
        
        print("  正确解析方式:")
        correct_numbers = extract_numbers_with_units(test_case)
        print(f"    解析结果: {correct_numbers}")
        
        # 分析差异
        if simple_numbers != correct_numbers:
            print(f"  ❌ 发现解析错误！应该是 {correct_numbers} 而不是 {simple_numbers}")
        else:
            print(f"  ✅ 解析正确")

if __name__ == "__main__":
    print("开始测试日语价格解析问题...")
    
    # 手动测试
    test_manual_parsing()
    
    # 尝试测试实际解析器
    try:
        asyncio.run(test_current_parser())
    except Exception as e:
        print(f"无法测试实际解析器: {e}")