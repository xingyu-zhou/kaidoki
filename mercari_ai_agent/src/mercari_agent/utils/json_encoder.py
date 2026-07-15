"""
自定义JSON编码器

提供对枚举对象和其他特殊类型的JSON序列化支持
"""

import json
from enum import Enum
from datetime import datetime, date
from typing import Any
from dataclasses import is_dataclass, asdict
from pathlib import Path

# 移除循环导入
# from ..services.llm_service import LLMProvider


def safe_enum_value(obj: Any) -> Any:
    """
    安全地获取枚举值，处理枚举对象和字符串值混用问题
    
    Args:
        obj: 可能是枚举对象或字符串的对象
        
    Returns:
        枚举的值或原始字符串
    """
    if hasattr(obj, 'value'):
        return obj.value
    elif isinstance(obj, str):
        return obj
    else:
        return str(obj) if obj is not None else None


class CustomJSONEncoder(json.JSONEncoder):
    """自定义JSON编码器，支持枚举、日期时间和数据类"""
    
    def default(self, obj: Any) -> Any:
        """自定义序列化逻辑"""
        
        # 处理枚举类型
        if isinstance(obj, Enum):
            return obj.value
        
        # 处理日期时间
        if isinstance(obj, datetime):
            return obj.isoformat()
        
        if isinstance(obj, date):
            return obj.isoformat()
        
        # 处理数据类
        if is_dataclass(obj):
            return asdict(obj)
        
        # 处理Path对象
        if isinstance(obj, Path):
            return str(obj)
        
        # 处理set类型
        if isinstance(obj, set):
            return list(obj)
        
        # 处理bytes类型
        if isinstance(obj, bytes):
            return obj.decode('utf-8', errors='ignore')
        
        # 调用父类的default方法
        return super().default(obj)


def dumps(obj: Any, **kwargs) -> str:
    """使用自定义编码器的dumps函数"""
    return json.dumps(obj, cls=CustomJSONEncoder, **kwargs)


def dump(obj: Any, fp, **kwargs) -> None:
    """使用自定义编码器的dump函数"""
    return json.dump(obj, fp, cls=CustomJSONEncoder, **kwargs)


def safe_json_serialize(obj: Any) -> str:
    """安全的JSON序列化，处理异常"""
    try:
        return dumps(obj, ensure_ascii=False, indent=2)
    except Exception as e:
        # 如果序列化失败，返回对象的字符串表示
        return f"<JSON序列化失败: {type(obj).__name__} - {str(e)[:100]}>"


def prepare_for_json(obj: Any) -> Any:
    """准备对象用于JSON序列化"""
    if isinstance(obj, dict):
        return {k: prepare_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [prepare_for_json(item) for item in obj]
    elif isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif is_dataclass(obj):
        return prepare_for_json(asdict(obj))
    elif isinstance(obj, Path):
        return str(obj)
    elif isinstance(obj, set):
        return list(obj)
    elif isinstance(obj, bytes):
        return obj.decode('utf-8', errors='ignore')
    else:
        return obj