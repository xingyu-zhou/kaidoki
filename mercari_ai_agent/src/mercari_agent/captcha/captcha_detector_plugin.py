"""
统一验证码检测器插件接口
 
该模块定义了验证码检测器的插件接口，支持：
- 多阶段检测流水线
- 插件化检测器注册
- 统一的置信度计算
- 检测结果缓存
- 人机交互原则保证

Author: Mercari AI Agent Team
"""

import asyncio
import time
import re
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import weakref

from .plugin_interface import (
    IAntiDetectionPlugin, IDetectionPlugin, PluginCategory, PluginPriority, PluginMetadata
)
from .captcha_types import CaptchaType, CaptchaDetectionResult
from .unified_captcha_detector import UnifiedDetectionResult, DetectionStage, BotDetectionType
from ..utils.logger import get_logger

logger = get_logger(__name__)


class DetectionStageType(Enum):
    """检测阶段类型"""
    RULE_BASED = "rule_based"
    DOM_STRUCTURE = "dom_structure" 
    ELEMENT_ATTRIBUTE = "element_attribute"
    CONTEXT_SEMANTIC = "context_semantic"
    IMAGE_ANALYSIS = "image_analysis"  # 仅检测不破解
    CACHE_LOOKUP = "cache_lookup"


class DetectionPipeline(Enum):
    """检测流水线模式"""
    FAST = "fast"           # 快速检测，仅规则+DOM
    STANDARD = "standard"   # 标准检测，规则+DOM+属性
    COMPREHENSIVE = "comprehensive"  # 全面检测，所有阶段
    ADAPTIVE = "adaptive"   # 自适应检测，根据上下文选择


@dataclass
class CaptchaDetectorConfig:
    """验证码检测器配置"""
    confidence_threshold: float = 0.6
    enable_context_analysis: bool = True
    enable_debug_logging: bool = False
    max_processing_time: float = 30.0
    detection_pipeline: DetectionPipeline = DetectionPipeline.STANDARD
    
    # 阶段阈值配置
    stage_thresholds: Dict[DetectionStageType, float] = field(default_factory=lambda: {
        DetectionStageType.RULE_BASED: 0.5,
        DetectionStageType.DOM_STRUCTURE: 0.7,
        DetectionStageType.ELEMENT_ATTRIBUTE: 0.6,
        DetectionStageType.CONTEXT_SEMANTIC: 0.8,
        DetectionStageType.IMAGE_ANALYSIS: 0.9,
        DetectionStageType.CACHE_LOOKUP: 0.95
    })
    
    # 缓存配置
    enable_detection_cache: bool = True
    cache_ttl: int = 300  # 5分钟
    max_cache_size: int = 1000
    
    # 性能配置
    enable_parallel_detection: bool = True
    max_concurrent_detections: int = 5
    detection_timeout: float = 10.0
    
    # 人机交互原则
    require_human_interaction: bool = True
    disable_auto_solving: bool = True
    enable_compliance_check: bool = True


@dataclass 
class DetectionContext:
    """检测上下文"""
    url: Optional[str] = None
    user_agent: Optional[str] = None
    referer: Optional[str] = None
    content_hash: Optional[str] = None
    session_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    previous_detections: List[str] = field(default_factory=list)
    
    def get_cache_key(self) -> str:
        """生成缓存键"""
        key_parts = [
            self.url or "unknown",
            self.content_hash or "unknown",
            str(int(self.timestamp.timestamp() // 60))  # 按分钟分组
        ]
        return hashlib.md5(":".join(key_parts).encode()).hexdigest()


@dataclass
class UnifiedCaptchaDetectionResult:
    """统一验证码检测结果"""
    # 基本检测信息
    detected: bool = False
    captcha_type: Optional[CaptchaType] = None
    confidence: float = 0.0
    detection_method: str = "unknown"
    detection_time: float = 0.0
    
    # 阶段检测结果
    stage_results: List[DetectionStage] = field(default_factory=list)
    pipeline_used: DetectionPipeline = DetectionPipeline.STANDARD
    
    # 详细信息
    patterns_matched: List[str] = field(default_factory=list)
    dom_elements: List[str] = field(default_factory=list)
    context_signals: Dict[str, Any] = field(default_factory=dict)
    
    # 缓存和性能信息
    cached: bool = False
    cache_hit: bool = False
    processing_stages: int = 0
    
    # 人机交互信息
    requires_human_action: bool = True
    suggested_action: str = "manual_verification"
    compliance_verified: bool = True
    
    # 元数据
    debug_info: Dict[str, Any] = field(default_factory=dict)
    context: Optional[DetectionContext] = None
    
    def add_stage_result(self, stage: DetectionStage):
        """添加阶段结果"""
        self.stage_results.append(stage)
        self.processing_stages = len(self.stage_results)
        
        # 更新整体置信度（使用加权平均）
        if stage.is_detected:
            weights = [1.0, 0.8, 0.6, 0.4]  # 阶段权重递减
            weighted_confidences = []
            
            for i, result in enumerate(self.stage_results):
                if result.is_detected:
                    weight = weights[min(i, len(weights) - 1)]
                    weighted_confidences.append(result.confidence * weight)
            
            if weighted_confidences:
                self.confidence = sum(weighted_confidences) / len(weighted_confidences)
                
    def to_legacy_result(self) -> CaptchaDetectionResult:
        """转换为旧版检测结果格式（向后兼容）"""
        return CaptchaDetectionResult(
            detected=self.detected,
            captcha_type=self.captcha_type,
            confidence=self.confidence,
            detection_method=self.detection_method,
            detection_time=self.detection_time,
            patterns_matched=self.patterns_matched,
            dom_elements=self.dom_elements,
            debug_info=self.debug_info
        )


class ICaptchaDetector(IDetectionPlugin):
    """
    验证码检测器插件接口
    
    所有验证码检测器都应该实现此接口，提供统一的检测功能。
    该接口扩展了IDetectionPlugin，添加了验证码特定的功能。
    """
    
    @abstractmethod
    async def detect_captcha(self, 
                           content: str, 
                           context: Optional[DetectionContext] = None) -> UnifiedCaptchaDetectionResult:
        """
        检测验证码
        
        Args:
            content: 页面内容
            context: 检测上下文
            
        Returns:
            UnifiedCaptchaDetectionResult: 统一检测结果
        """
        pass
    
    @abstractmethod
    async def detect_captcha_batch(self, 
                                 requests: List[Dict[str, Any]]) -> List[UnifiedCaptchaDetectionResult]:
        """
        批量检测验证码
        
        Args:
            requests: 检测请求列表，每个请求包含content和context
            
        Returns:
            List[UnifiedCaptchaDetectionResult]: 检测结果列表
        """
        pass
    
    @abstractmethod
    def get_supported_captcha_types(self) -> Set[CaptchaType]:
        """获取支持的验证码类型"""
        pass
    
    @abstractmethod
    async def validate_detection_result(self, 
                                      result: UnifiedCaptchaDetectionResult) -> bool:
        """
        验证检测结果
        
        Args:
            result: 检测结果
            
        Returns:
            bool: 结果是否有效
        """
        pass
    
    async def get_detection_config(self) -> CaptchaDetectorConfig:
        """获取检测器配置"""
        return getattr(self, '_detector_config', CaptchaDetectorConfig())
    
    async def update_detection_config(self, config: CaptchaDetectorConfig):
        """更新检测器配置"""
        self._detector_config = config
        await self._apply_config_changes()
    
    @abstractmethod
    async def _apply_config_changes(self):
        """应用配置变更"""
        pass
    
    # 实现IDetectionPlugin接口
    async def detect(self, content: str, response: Any = None, url: str = None) -> Dict[str, Any]:
        """实现IDetectionPlugin的detect方法"""
        context = DetectionContext(url=url)
        if response:
            context.user_agent = getattr(response, 'request', {}).get('User-Agent')
            context.referer = getattr(response, 'request', {}).get('Referer')
        
        result = await self.detect_captcha(content, context)
        
        return {
            'detected': result.detected,
            'captcha_type': result.captcha_type.value if result.captcha_type else None,
            'confidence': result.confidence,
            'detection_method': result.detection_method,
            'requires_human_action': result.requires_human_action,
            'suggested_action': result.suggested_action,
            'compliance_verified': result.compliance_verified,
            'stage_results': [
                {
                    'stage_name': stage.stage_name,
                    'confidence': stage.confidence,
                    'detected': stage.is_detected,
                    'processing_time': stage.processing_time
                }
                for stage in result.stage_results
            ]
        }


class DetectionCache:
    """检测结果缓存"""
    
    def __init__(self, max_size: int = 1000, ttl: int = 300):
        self.max_size = max_size
        self.ttl = ttl
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.access_times: Dict[str, float] = {}
        self.lock = asyncio.Lock()
    
    async def get(self, cache_key: str) -> Optional[UnifiedCaptchaDetectionResult]:
        """获取缓存结果"""
        async with self.lock:
            if cache_key not in self.cache:
                return None
            
            # 检查是否过期
            cache_data = self.cache[cache_key]
            if time.time() - cache_data['timestamp'] > self.ttl:
                del self.cache[cache_key]
                del self.access_times[cache_key]
                return None
            
            # 更新访问时间
            self.access_times[cache_key] = time.time()
            
            # 恢复结果对象
            result_data = cache_data['result']
            result = UnifiedCaptchaDetectionResult(**result_data)
            result.cached = True
            result.cache_hit = True
            
            return result
    
    async def set(self, cache_key: str, result: UnifiedCaptchaDetectionResult):
        """设置缓存结果"""
        async with self.lock:
            # 检查缓存大小限制
            if len(self.cache) >= self.max_size:
                await self._evict_old_entries()
            
            # 序列化结果对象
            result_data = {
                'detected': result.detected,
                'captcha_type': result.captcha_type,
                'confidence': result.confidence,
                'detection_method': result.detection_method,
                'detection_time': result.detection_time,
                'stage_results': result.stage_results,
                'pipeline_used': result.pipeline_used,
                'patterns_matched': result.patterns_matched,
                'dom_elements': result.dom_elements,
                'context_signals': result.context_signals,
                'requires_human_action': result.requires_human_action,
                'suggested_action': result.suggested_action,
                'compliance_verified': result.compliance_verified
            }
            
            self.cache[cache_key] = {
                'result': result_data,
                'timestamp': time.time()
            }
            self.access_times[cache_key] = time.time()
    
    async def _evict_old_entries(self):
        """驱逐旧的缓存条目"""
        # 按访问时间排序，移除最旧的条目
        sorted_keys = sorted(self.access_times.keys(), 
                           key=lambda k: self.access_times[k])
        
        # 移除最旧的20%
        num_to_remove = max(1, len(sorted_keys) // 5)
        for key in sorted_keys[:num_to_remove]:
            del self.cache[key]
            del self.access_times[key]
    
    async def clear(self):
        """清空缓存"""
        async with self.lock:
            self.cache.clear()
            self.access_times.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'ttl': self.ttl,
            'hit_rate': getattr(self, '_hit_rate', 0.0)
        }


# 插件装饰器
def captcha_detector_plugin(
    name: str = None,
    supported_types: Set[CaptchaType] = None,
    priority: PluginPriority = PluginPriority.NORMAL
):
    """
    验证码检测器插件装饰器
    
    Args:
        name: 插件名称
        supported_types: 支持的验证码类型
        priority: 插件优先级
    """
    def decorator(cls):
        # 设置插件元数据
        cls._plugin_name = name or cls.__name__
        cls._supported_types = supported_types or set()
        cls._plugin_priority = priority
        cls._plugin_category = PluginCategory.CAPTCHA
        
        # 确保实现了必要的接口
        if not issubclass(cls, ICaptchaDetector):
            raise TypeError(f"Plugin {cls.__name__} must implement ICaptchaDetector")
        
        return cls
    
    return decorator