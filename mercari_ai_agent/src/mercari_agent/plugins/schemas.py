"""
插件配置Schema定义

该模块定义了所有插件的配置schema，提供：
- 标准化的配置结构
- 配置验证和类型检查
- 默认值定义
- 配置模板生成
- 热加载支持

使用JSON Schema进行配置验证，确保配置的正确性和一致性。

Author: Mercari AI Agent Team
"""

import os
import json
import yaml
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .interfaces import PluginType, PluginCapability
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SchemaVersion(Enum):
    """Schema版本"""
    V1_0 = "1.0"
    V1_1 = "1.1"
    CURRENT = "1.1"


@dataclass
class SchemaMetadata:
    """Schema元数据"""
    version: str
    plugin_type: PluginType
    name: str
    description: str
    author: str = "Mercari AI Agent Team"
    created_at: str = ""
    updated_at: str = ""


# 基础插件配置Schema
BASE_PLUGIN_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "enabled": {
            "type": "boolean",
            "default": True,
            "description": "是否启用该插件"
        },
        "priority": {
            "type": "string",
            "enum": ["CRITICAL", "HIGH", "NORMAL", "LOW", "OPTIONAL"],
            "default": "NORMAL",
            "description": "插件优先级"
        },
        "version": {
            "type": "string",
            "pattern": "^\\d+\\.\\d+(\\.\\d+)?$",
            "default": "1.0.0",
            "description": "插件版本"
        },
        "log_level": {
            "type": "string",
            "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            "default": "INFO",
            "description": "日志级别"
        },
        "timeout": {
            "type": "number",
            "minimum": 0.1,
            "maximum": 300.0,
            "default": 30.0,
            "description": "操作超时时间（秒）"
        },
        "retry_count": {
            "type": "integer",
            "minimum": 0,
            "maximum": 10,
            "default": 3,
            "description": "重试次数"
        },
        "health_check_interval": {
            "type": "number",
            "minimum": 10.0,
            "default": 60.0,
            "description": "健康检查间隔（秒）"
        }
    },
    "required": ["enabled"],
    "additionalProperties": True
}

# 会话管理插件Schema
SESSION_MANAGEMENT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "会话管理插件配置",
    "description": "会话管理插件的配置schema",
    "type": "object",
    "allOf": [
        BASE_PLUGIN_SCHEMA
    ],
    "properties": {
        "max_concurrent_sessions": {
            "type": "integer",
            "minimum": 1,
            "maximum": 100,
            "default": 10,
            "description": "最大并发会话数"
        },
        "session_timeout": {
            "type": "number",
            "minimum": 60.0,
            "default": 1800.0,
            "description": "会话超时时间（秒）"
        },
        "connection_timeout": {
            "type": "number",
            "minimum": 5.0,
            "maximum": 120.0,
            "default": 30.0,
            "description": "连接超时时间（秒）"
        },
        "read_timeout": {
            "type": "number",
            "minimum": 10.0,
            "maximum": 300.0,
            "default": 60.0,
            "description": "读取超时时间（秒）"
        },
        "total_timeout": {
            "type": "number",
            "minimum": 30.0,
            "maximum": 600.0,
            "default": 120.0,
            "description": "总超时时间（秒）"
        },
        "pool_size": {
            "type": "integer",
            "minimum": 1,
            "maximum": 50,
            "default": 5,
            "description": "连接池大小"
        },
        "max_pool_size": {
            "type": "integer",
            "minimum": 5,
            "maximum": 100,
            "default": 20,
            "description": "最大连接池大小"
        },
        "min_pool_size": {
            "type": "integer",
            "minimum": 1,
            "maximum": 10,
            "default": 2,
            "description": "最小连接池大小"
        },
        "enable_connection_pooling": {
            "type": "boolean",
            "default": True,
            "description": "是否启用连接池"
        },
        "enable_session_reuse": {
            "type": "boolean",
            "default": True,
            "description": "是否启用会话重用"
        },
        "enable_keep_alive": {
            "type": "boolean",
            "default": True,
            "description": "是否启用Keep-Alive"
        }
    },
    "required": ["max_concurrent_sessions", "session_timeout"]
}

# 指纹管理插件Schema
FINGERPRINT_MANAGEMENT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "指纹管理插件配置",
    "description": "指纹管理插件的配置schema",
    "type": "object",
    "allOf": [
        BASE_PLUGIN_SCHEMA
    ],
    "properties": {
        "max_fingerprints": {
            "type": "integer",
            "minimum": 10,
            "maximum": 1000,
            "default": 100,
            "description": "最大指纹数量"
        },
        "min_fingerprints": {
            "type": "integer",
            "minimum": 5,
            "maximum": 50,
            "default": 10,
            "description": "最小指纹数量"
        },
        "rotation_interval": {
            "type": "number",
            "minimum": 300.0,
            "default": 1800.0,
            "description": "指纹轮换间隔（秒）"
        },
        "max_usage_count": {
            "type": "integer",
            "minimum": 1,
            "maximum": 200,
            "default": 50,
            "description": "单个指纹最大使用次数"
        },
        "min_quality_score": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "default": 0.6,
            "description": "最小质量分数"
        },
        "enable_quality_filter": {
            "type": "boolean",
            "default": True,
            "description": "是否启用质量过滤"
        },
        "quality_check_interval": {
            "type": "number",
            "minimum": 600.0,
            "default": 3600.0,
            "description": "质量检查间隔（秒）"
        },
        "auto_generate": {
            "type": "boolean",
            "default": True,
            "description": "是否自动生成指纹"
        },
        "generation_batch_size": {
            "type": "integer",
            "minimum": 1,
            "maximum": 50,
            "default": 10,
            "description": "批量生成大小"
        },
        "generation_interval": {
            "type": "number",
            "minimum": 1800.0,
            "default": 7200.0,
            "description": "生成间隔（秒）"
        },
        "supported_platforms": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["windows", "macos", "linux", "android", "ios"]
            },
            "default": ["windows", "macos", "linux"],
            "description": "支持的平台"
        },
        "supported_browsers": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["chrome", "firefox", "safari", "edge", "opera"]
            },
            "default": ["chrome", "firefox", "safari", "edge"],
            "description": "支持的浏览器"
        },
        "enable_canvas_fingerprinting": {
            "type": "boolean",
            "default": True,
            "description": "是否启用Canvas指纹"
        },
        "enable_webgl_fingerprinting": {
            "type": "boolean",
            "default": True,
            "description": "是否启用WebGL指纹"
        },
        "enable_audio_fingerprinting": {
            "type": "boolean",
            "default": True,
            "description": "是否启用音频指纹"
        },
        "randomize_timezone": {
            "type": "boolean",
            "default": True,
            "description": "是否随机化时区"
        },
        "randomize_language": {
            "type": "boolean",
            "default": True,
            "description": "是否随机化语言"
        }
    },
    "required": ["max_fingerprints", "min_fingerprints", "rotation_interval"]
}

# 行为模拟插件Schema
BEHAVIOR_SIMULATION_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "行为模拟插件配置",
    "description": "行为模拟插件的配置schema",
    "type": "object",
    "allOf": [
        BASE_PLUGIN_SCHEMA
    ],
    "properties": {
        "mouse_move_speed": {
            "type": "number",
            "minimum": 0.1,
            "maximum": 10.0,
            "default": 1.0,
            "description": "鼠标移动速度倍数"
        },
        "mouse_click_delay": {
            "type": "array",
            "items": {
                "type": "number",
                "minimum": 0.01
            },
            "minItems": 2,
            "maxItems": 2,
            "default": [0.1, 0.3],
            "description": "鼠标点击延迟范围（秒）"
        },
        "mouse_scroll_delay": {
            "type": "array",
            "items": {
                "type": "number",
                "minimum": 0.01
            },
            "minItems": 2,
            "maxItems": 2,
            "default": [0.2, 0.5],
            "description": "鼠标滚动延迟范围（秒）"
        },
        "enable_mouse_curves": {
            "type": "boolean",
            "default": True,
            "description": "是否启用鼠标轨迹曲线"
        },
        "typing_speed": {
            "type": "number",
            "minimum": 0.01,
            "maximum": 1.0,
            "default": 0.1,
            "description": "打字间隔（秒）"
        },
        "typing_variation": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 0.5,
            "default": 0.05,
            "description": "打字变化"
        },
        "enable_typing_errors": {
            "type": "boolean",
            "default": True,
            "description": "是否启用打字错误"
        },
        "error_rate": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 0.1,
            "default": 0.02,
            "description": "错误率"
        },
        "page_load_wait": {
            "type": "array",
            "items": {
                "type": "number",
                "minimum": 0.1
            },
            "minItems": 2,
            "maxItems": 2,
            "default": [1.0, 3.0],
            "description": "页面加载等待时间范围（秒）"
        },
        "element_search_delay": {
            "type": "array",
            "items": {
                "type": "number",
                "minimum": 0.1
            },
            "minItems": 2,
            "maxItems": 2,
            "default": [0.5, 1.5],
            "description": "元素搜索延迟范围（秒）"
        },
        "scroll_behavior": {
            "type": "string",
            "enum": ["natural", "smooth", "instant", "auto"],
            "default": "natural",
            "description": "滚动行为模式"
        },
        "reading_behavior": {
            "type": "boolean",
            "default": True,
            "description": "是否启用阅读行为模拟"
        },
        "reading_speed": {
            "type": "number",
            "minimum": 50.0,
            "maximum": 1000.0,
            "default": 200.0,
            "description": "阅读速度（字符/分钟）"
        },
        "attention_span": {
            "type": "array",
            "items": {
                "type": "number",
                "minimum": 1.0
            },
            "minItems": 2,
            "maxItems": 2,
            "default": [10.0, 30.0],
            "description": "注意力持续时间范围（秒）"
        },
        "behavior_randomization": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "default": 0.2,
            "description": "行为随机化程度"
        },
        "pattern_variation": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "default": 0.15,
            "description": "模式变化程度"
        },
        "timing_jitter": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 0.5,
            "default": 0.1,
            "description": "时间抖动"
        },
        "adaptive_timing": {
            "type": "boolean",
            "default": True,
            "description": "是否启用自适应时间调整"
        },
        "learning_enabled": {
            "type": "boolean",
            "default": True,
            "description": "是否启用学习模式"
        },
        "pattern_memory_size": {
            "type": "integer",
            "minimum": 10,
            "maximum": 1000,
            "default": 100,
            "description": "模式记忆大小"
        }
    },
    "required": ["mouse_move_speed", "typing_speed"]
}

# CAPTCHA检测插件Schema
CAPTCHA_DETECTION_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "CAPTCHA检测插件配置",
    "description": "CAPTCHA检测插件的配置schema",
    "type": "object",
    "allOf": [
        BASE_PLUGIN_SCHEMA
    ],
    "properties": {
        "confidence_threshold": {
            "type": "number",
            "minimum": 0.1,
            "maximum": 1.0,
            "default": 0.6,
            "description": "置信度阈值"
        },
        "enable_context_analysis": {
            "type": "boolean",
            "default": True,
            "description": "是否启用上下文分析"
        },
        "enable_debug_logging": {
            "type": "boolean",
            "default": False,
            "description": "是否启用调试日志"
        },
        "max_processing_time": {
            "type": "number",
            "minimum": 1.0,
            "maximum": 120.0,
            "default": 30.0,
            "description": "最大处理时间（秒）"
        },
        "detection_pipeline": {
            "type": "string",
            "enum": ["fast", "standard", "comprehensive", "adaptive"],
            "default": "standard",
            "description": "检测流水线模式"
        },
        "stage_thresholds": {
            "type": "object",
            "properties": {
                "rule_based": {"type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.5},
                "dom_structure": {"type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.7},
                "element_attribute": {"type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.6},
                "context_semantic": {"type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.8},
                "image_analysis": {"type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.9}
            },
            "description": "各阶段检测阈值"
        },
        "enable_detection_cache": {
            "type": "boolean",
            "default": True,
            "description": "是否启用检测缓存"
        },
        "cache_ttl": {
            "type": "integer",
            "minimum": 60,
            "maximum": 3600,
            "default": 300,
            "description": "缓存TTL（秒）"
        },
        "max_cache_size": {
            "type": "integer",
            "minimum": 100,
            "maximum": 10000,
            "default": 1000,
            "description": "最大缓存大小"
        },
        "enable_parallel_detection": {
            "type": "boolean",
            "default": True,
            "description": "是否启用并行检测"
        },
        "max_concurrent_detections": {
            "type": "integer",
            "minimum": 1,
            "maximum": 20,
            "default": 5,
            "description": "最大并发检测数"
        },
        "detection_timeout": {
            "type": "number",
            "minimum": 1.0,
            "maximum": 60.0,
            "default": 10.0,
            "description": "单次检测超时时间（秒）"
        },
        "require_human_interaction": {
            "type": "boolean",
            "default": True,
            "description": "是否需要人工交互"
        },
        "disable_auto_solving": {
            "type": "boolean",
            "default": True,
            "description": "是否禁用自动解决"
        },
        "enable_compliance_check": {
            "type": "boolean",
            "default": True,
            "description": "是否启用合规检查"
        }
    },
    "required": ["confidence_threshold"]
}

# 插件框架Schema
PLUGIN_FRAMEWORK_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "插件框架配置",
    "description": "插件框架的配置schema",
    "type": "object",
    "properties": {
        "max_plugins": {
            "type": "integer",
            "minimum": 1,
            "maximum": 200,
            "default": 50,
            "description": "最大插件数量"
        },
        "plugin_timeout": {
            "type": "number",
            "minimum": 5.0,
            "maximum": 300.0,
            "default": 30.0,
            "description": "插件操作超时时间（秒）"
        },
        "enable_hot_reload": {
            "type": "boolean",
            "default": True,
            "description": "是否启用热重载"
        },
        "enable_performance_monitoring": {
            "type": "boolean",
            "default": True,
            "description": "是否启用性能监控"
        },
        "enable_health_checks": {
            "type": "boolean",
            "default": True,
            "description": "是否启用健康检查"
        },
        "max_concurrent_operations": {
            "type": "integer",
            "minimum": 1,
            "maximum": 100,
            "default": 20,
            "description": "最大并发操作数"
        },
        "event_queue_size": {
            "type": "integer",
            "minimum": 100,
            "maximum": 10000,
            "default": 1000,
            "description": "事件队列大小"
        },
        "inter_plugin_timeout": {
            "type": "number",
            "minimum": 1.0,
            "maximum": 60.0,
            "default": 10.0,
            "description": "插件间通信超时时间（秒）"
        },
        "metrics_collection_interval": {
            "type": "number",
            "minimum": 10.0,
            "default": 60.0,
            "description": "指标收集间隔（秒）"
        },
        "health_check_interval": {
            "type": "number",
            "minimum": 60.0,
            "default": 300.0,
            "description": "健康检查间隔（秒）"
        },
        "plugin_gc_interval": {
            "type": "number",
            "minimum": 600.0,
            "default": 3600.0,
            "description": "插件垃圾回收间隔（秒）"
        },
        "max_retry_attempts": {
            "type": "integer",
            "minimum": 1,
            "maximum": 10,
            "default": 3,
            "description": "最大重试次数"
        },
        "failure_threshold": {
            "type": "integer",
            "minimum": 1,
            "maximum": 20,
            "default": 5,
            "description": "故障阈值"
        },
        "recovery_timeout": {
            "type": "number",
            "minimum": 60.0,
            "default": 300.0,
            "description": "恢复超时时间（秒）"
        },
        "enable_persistent_config": {
            "type": "boolean",
            "default": True,
            "description": "是否启用持久化配置"
        }
    },
    "required": ["max_plugins"]
}

# Schema映射表
PLUGIN_SCHEMAS = {
    PluginType.SESSION_MANAGEMENT: SESSION_MANAGEMENT_SCHEMA,
    PluginType.FINGERPRINT: FINGERPRINT_MANAGEMENT_SCHEMA,
    PluginType.BEHAVIOR_SIMULATION: BEHAVIOR_SIMULATION_SCHEMA,
    PluginType.CAPTCHA_DETECTION: CAPTCHA_DETECTION_SCHEMA,
    "framework": PLUGIN_FRAMEWORK_SCHEMA
}

# Schema元数据映射表
SCHEMA_METADATA = {
    PluginType.SESSION_MANAGEMENT: SchemaMetadata(
        version=SchemaVersion.CURRENT.value,
        plugin_type=PluginType.SESSION_MANAGEMENT,
        name="会话管理插件配置Schema",
        description="定义会话管理插件的配置结构和验证规则"
    ),
    PluginType.FINGERPRINT: SchemaMetadata(
        version=SchemaVersion.CURRENT.value,
        plugin_type=PluginType.FINGERPRINT,
        name="指纹管理插件配置Schema",
        description="定义指纹管理插件的配置结构和验证规则"
    ),
    PluginType.BEHAVIOR_SIMULATION: SchemaMetadata(
        version=SchemaVersion.CURRENT.value,
        plugin_type=PluginType.BEHAVIOR_SIMULATION,
        name="行为模拟插件配置Schema",
        description="定义行为模拟插件的配置结构和验证规则"
    ),
    PluginType.CAPTCHA_DETECTION: SchemaMetadata(
        version=SchemaVersion.CURRENT.value,
        plugin_type=PluginType.CAPTCHA_DETECTION,
        name="CAPTCHA检测插件配置Schema",
        description="定义CAPTCHA检测插件的配置结构和验证规则"
    )
}


class SchemaValidator:
    """Schema验证器"""
    
    def __init__(self):
        try:
            import jsonschema
            self.jsonschema = jsonschema
            self.validator_available = True
        except ImportError:
            logger.warning("jsonschema not available, schema validation disabled")
            self.validator_available = False
        
        self.compiled_validators = {}
        self._compile_validators()
    
    def _compile_validators(self):
        """编译验证器"""
        if not self.validator_available:
            return
        
        for plugin_type, schema in PLUGIN_SCHEMAS.items():
            try:
                validator = self.jsonschema.Draft7Validator(schema)
                self.compiled_validators[plugin_type] = validator
            except Exception as e:
                logger.error(f"Failed to compile validator for {plugin_type}: {e}")
    
    def validate_config(self, plugin_type: Union[PluginType, str], config: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证插件配置
        
        Args:
            plugin_type: 插件类型
            config: 配置字典
            
        Returns:
            Dict[str, Any]: 验证结果
        """
        result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'normalized_config': config.copy()
        }
        
        if not self.validator_available:
            result['warnings'].append("Schema validation not available (jsonschema not installed)")
            return result
        
        validator = self.compiled_validators.get(plugin_type)
        if not validator:
            result['warnings'].append(f"No validator available for plugin type: {plugin_type}")
            return result
        
        try:
            # 验证配置
            errors = list(validator.iter_errors(config))
            
            if errors:
                result['valid'] = False
                result['errors'] = [
                    {
                        'path': '.'.join(str(p) for p in error.absolute_path),
                        'message': error.message,
                        'value': error.instance
                    }
                    for error in errors
                ]
            else:
                # 应用默认值
                result['normalized_config'] = self._apply_defaults(plugin_type, config)
                
        except Exception as e:
            result['valid'] = False
            result['errors'].append(f"Validation error: {str(e)}")
        
        return result
    
    def _apply_defaults(self, plugin_type: Union[PluginType, str], config: Dict[str, Any]) -> Dict[str, Any]:
        """应用默认值"""
        schema = PLUGIN_SCHEMAS.get(plugin_type, {})
        normalized = config.copy()
        
        def apply_defaults_recursive(schema_part: Dict[str, Any], config_part: Dict[str, Any]) -> Dict[str, Any]:
            properties = schema_part.get('properties', {})
            
            for key, prop_schema in properties.items():
                if key not in config_part and 'default' in prop_schema:
                    config_part[key] = prop_schema['default']
                elif key in config_part and isinstance(config_part[key], dict) and prop_schema.get('type') == 'object':
                    config_part[key] = apply_defaults_recursive(prop_schema, config_part[key])
            
            return config_part
        
        return apply_defaults_recursive(schema, normalized)
    
    def get_schema(self, plugin_type: Union[PluginType, str]) -> Optional[Dict[str, Any]]:
        """获取插件类型的schema"""
        return PLUGIN_SCHEMAS.get(plugin_type)
    
    def get_default_config(self, plugin_type: Union[PluginType, str]) -> Dict[str, Any]:
        """获取插件类型的默认配置"""
        return self._apply_defaults(plugin_type, {})


class ConfigTemplateGenerator:
    """配置模板生成器"""
    
    def __init__(self):
        self.validator = SchemaValidator()
    
    def generate_template(self, plugin_type: Union[PluginType, str], 
                         format: str = 'yaml', 
                         include_comments: bool = True) -> str:
        """
        生成配置模板
        
        Args:
            plugin_type: 插件类型
            format: 输出格式 ('yaml', 'json')
            include_comments: 是否包含注释
            
        Returns:
            str: 配置模板字符串
        """
        default_config = self.validator.get_default_config(plugin_type)
        schema = self.validator.get_schema(plugin_type)
        
        if format.lower() == 'yaml':
            return self._generate_yaml_template(default_config, schema, include_comments)
        elif format.lower() == 'json':
            return self._generate_json_template(default_config, schema, include_comments)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _generate_yaml_template(self, config: Dict[str, Any], 
                               schema: Optional[Dict[str, Any]] = None,
                               include_comments: bool = True) -> str:
        """生成YAML模板"""
        import io
        
        output = io.StringIO()
        
        if include_comments and schema:
            title = schema.get('title', 'Plugin Configuration')
            description = schema.get('description', '')
            output.write(f"# {title}\n")
            if description:
                output.write(f"# {description}\n")
            output.write(f"# Generated at: {os.environ.get('TZ', 'UTC')}\n\n")
        
        # 递归生成YAML内容
        def write_yaml_recursive(data: Dict[str, Any], schema_props: Dict[str, Any] = None, indent: int = 0):
            schema_props = schema_props or {}
            
            for key, value in data.items():
                indent_str = "  " * indent
                
                # 写注释
                if include_comments and schema_props and key in schema_props:
                    prop_schema = schema_props[key]
                    description = prop_schema.get('description')
                    if description:
                        output.write(f"{indent_str}# {description}\n")
                    
                    # 添加类型信息
                    prop_type = prop_schema.get('type')
                    if prop_type:
                        output.write(f"{indent_str}# Type: {prop_type}\n")
                
                # 写值
                if isinstance(value, dict):
                    output.write(f"{indent_str}{key}:\n")
                    nested_props = schema_props.get(key, {}).get('properties', {}) if schema_props else {}
                    write_yaml_recursive(value, nested_props, indent + 1)
                elif isinstance(value, list):
                    output.write(f"{indent_str}{key}:\n")
                    for item in value:
                        output.write(f"{indent_str}  - {repr(item) if isinstance(item, str) else item}\n")
                else:
                    if isinstance(value, str):
                        output.write(f"{indent_str}{key}: {repr(value)}\n")
                    else:
                        output.write(f"{indent_str}{key}: {value}\n")
                
                output.write("\n")
        
        properties = schema.get('properties', {}) if schema else {}
        write_yaml_recursive(config, properties)
        
        return output.getvalue()
    
    def _generate_json_template(self, config: Dict[str, Any], 
                               schema: Optional[Dict[str, Any]] = None,
                               include_comments: bool = True) -> str:
        """生成JSON模板"""
        if include_comments:
            # JSON不支持注释，添加特殊字段
            template = {
                "_schema_info": {
                    "title": schema.get('title', 'Plugin Configuration') if schema else 'Plugin Configuration',
                    "description": schema.get('description', '') if schema else '',
                    "version": schema.get('version', '1.0') if schema else '1.0'
                },
                **config
            }
        else:
            template = config
        
        return json.dumps(template, indent=2, ensure_ascii=False)
    
    def save_template_file(self, plugin_type: Union[PluginType, str], 
                          output_path: Path,
                          format: str = 'yaml') -> bool:
        """保存模板文件"""
        try:
            template_content = self.generate_template(plugin_type, format, include_comments=True)
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(template_content)
            
            logger.info(f"Configuration template saved: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save template file: {e}")
            return False
    
    def generate_all_templates(self, output_dir: Path, format: str = 'yaml') -> bool:
        """生成所有插件的配置模板"""
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            
            for plugin_type in PLUGIN_SCHEMAS.keys():
                if plugin_type == "framework":
                    filename = f"framework_config.{format}"
                else:
                    filename = f"{plugin_type.value}_config.{format}"
                
                template_path = output_dir / filename
                self.save_template_file(plugin_type, template_path, format)
            
            logger.info(f"All configuration templates generated in: {output_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate all templates: {e}")
            return False


# 全局实例
_schema_validator: Optional[SchemaValidator] = None
_template_generator: Optional[ConfigTemplateGenerator] = None

def get_schema_validator() -> SchemaValidator:
    """获取全局schema验证器"""
    global _schema_validator
    if _schema_validator is None:
        _schema_validator = SchemaValidator()
    return _schema_validator

def get_template_generator() -> ConfigTemplateGenerator:
    """获取全局模板生成器"""
    global _template_generator
    if _template_generator is None:
        _template_generator = ConfigTemplateGenerator()
    return _template_generator

# 便利函数
def validate_plugin_config(plugin_type: Union[PluginType, str], config: Dict[str, Any]) -> Dict[str, Any]:
    """验证插件配置"""
    validator = get_schema_validator()
    return validator.validate_config(plugin_type, config)

def get_plugin_default_config(plugin_type: Union[PluginType, str]) -> Dict[str, Any]:
    """获取插件默认配置"""
    validator = get_schema_validator()
    return validator.get_default_config(plugin_type)

def generate_plugin_template(plugin_type: Union[PluginType, str], format: str = 'yaml') -> str:
    """生成插件配置模板"""
    generator = get_template_generator()
    return generator.generate_template(plugin_type, format)