#!/usr/bin/env python3
"""
日语价格解析问题诊断和验证

核心问题分析：
1. query_parser_service.py 中的价格解析逻辑过于简单
2. 没有处理日语数字单位"万"（万 = 10,000倍）
3. 对"2万円"只提取"2"而不是转换为"20000"
"""

import re
from typing import Optional, Tuple


def current_broken_logic(price_text: str) -> Optional[int]:
    """当前有问题的价格解析逻辑（复现问题）"""
    # 这是当前 query_parser_service.py 中的逻辑
    try:
        price_num = int(''.join(filter(str.isdigit, price_text)))
        return price_num
    except:
        return None


def fixed_japanese_price_logic(price_text: str) -> Optional[int]:
    """修复后的日语价格解析逻辑"""
    if not price_text:
        return None
    
    # 处理万単位 (1万 = 10,000)
    man_pattern = r'(\d+)万円'
    man_match = re.search(man_pattern, price_text)
    if man_match:
        base_number = int(man_match.group(1))
        return base_number * 10000
    
    # 处理千単位 (1千 = 1,000)
    sen_pattern = r'(\d+)千円'
    sen_match = re.search(sen_pattern, price_text)
    if sen_match:
        base_number = int(sen_match.group(1))
        return base_number * 1000
    
    # 处理普通円
    yen_pattern = r'(\d+)円'
    yen_match = re.search(yen_pattern, price_text)
    if yen_match:
        return int(yen_match.group(1))
    
    # 处理纯数字
    number_pattern = r'(\d+)'
    number_match = re.search(number_pattern, price_text)
    if number_match:
        return int(number_match.group(1))
    
    return None


def extract_price_conditions(text: str) -> Tuple[Optional[int], Optional[int]]:
    """提取价格条件（最小值、最大值）"""
    price_min = None
    price_max = None
    
    # 检查"以下"或"未満"（最大值条件）
    if "以下" in text or "未満" in text:
        price = fixed_japanese_price_logic(text)
        if price:
            price_max = price
    
    # 检查"以上"（最小值条件）
    elif "以上" in text:
        price = fixed_japanese_price_logic(text)
        if price:
            price_min = price
    
    # 检查价格范围 "Xから Y"
    range_pattern = r'(\d+(?:万|千)?)円?から(\d+(?:万|千)?)円?'
    range_match = re.search(range_pattern, text)
    if range_match:
        min_text = range_match.group(1) + ("円" if "円" not in range_match.group(1) else "")
        max_text = range_match.group(2) + ("円" if "円" not in range_match.group(2) else "")
        
        price_min = fixed_japanese_price_logic(min_text)
        price_max = fixed_japanese_price_logic(max_text)
    
    return price_min, price_max


def test_diagnosis():
    """测试诊断"""
    test_cases = [
        "Nintendo Switch 2万円以下",
        "MacBook Pro M3 15万円から20万円",
        "新品未使用 iPhone 14", 
        "中古良品 PlayStation 5",
        "送料無料 カメラ",
        "3万円",
        "10万円以上",
        "5万円以下",
        "1万2千円",  # 复杂情况
        "20万円から30万円まで"
    ]
    
    print("=== 日语价格解析问题诊断 ===\n")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"{i}. 测试用例: '{test_case}'")
        
        # 当前错误的解析方式
        current_result = current_broken_logic(test_case)
        print(f"   当前（错误）结果: {current_result}")
        
        # 修复后的解析方式
        fixed_result = fixed_japanese_price_logic(test_case)
        print(f"   修复后价格解析: {fixed_result}")
        
        # 条件解析
        price_min, price_max = extract_price_conditions(test_case)
        print(f"   价格范围: {price_min} - {price_max}")
        
        # 分析差异
        if current_result != fixed_result:
            if current_result and fixed_result:
                factor = fixed_result // current_result if current_result else 0
                print(f"   ❌ 问题发现：当前解析错误 {factor}倍！")
            else:
                print(f"   ❌ 问题发现：解析逻辑错误")
        else:
            print(f"   ✅ 解析正确")
        
        print()


if __name__ == "__main__":
    test_diagnosis()