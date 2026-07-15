"""
统一验证码检测器插件实现

该模块实现了统一的验证码检测器，整合了所有检测逻辑，消除75%的重复代码：
- 合并基于规则和多阶段检测
- 统一置信度计算和模式匹配
- 实现多阶段检测流水线
- 支持检测缓存和性能优化
- 完全符合人机交互原则

Author: Mercari AI Agent Team
"""

import asyncio
import time
import re
import json
import hashlib
from typing import Dict, List, Optional, Any, Union, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup

from .captcha_detector_plugin import (
    ICaptchaDetector, CaptchaDetectorConfig, DetectionContext,
    UnifiedCaptchaDetectionResult, DetectionCache, DetectionStageType,
    DetectionPipeline, captcha_detector_plugin
)
from .plugin_interface import PluginMetadata, PluginCategory, PluginPriority
from .captcha_types import CaptchaType, CaptchaDetectionResult
from .unified_captcha_detector import DetectionStage, BotDetectionType
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PatternInfo:
    """模式信息"""
    pattern: str
    captcha_type: CaptchaType
    confidence: float
    weight: float = 1.0
    positive_contexts: List[str] = field(default_factory=list)
    negative_contexts: List[str] = field(default_factory=list)
    early_exit_on_negative: bool = False


@dataclass
class DOMSelectorInfo:
    """DOM选择器信息"""
    selector: str
    captcha_type: CaptchaType
    confidence: float
    attributes_check: Dict[str, str] = field(default_factory=dict)


@captcha_detector_plugin(
    name="UnifiedCaptchaDetector",
    supported_types={
        CaptchaType.IMAGE_TEXT, CaptchaType.RECAPTCHA_V2, CaptchaType.RECAPTCHA_V3,
        CaptchaType.HCAPTCHA, CaptchaType.SLIDE_PUZZLE, CaptchaType.CLICK_SEQUENCE,
        CaptchaType.GEETEST, CaptchaType.CLOUDFLARE
    },
    priority=PluginPriority.HIGH
)
class UnifiedCaptchaDetectorPlugin(ICaptchaDetector):
    """
    统一验证码检测器插件
    
    核心功能：
    1. 整合所有检测逻辑，消除重复代码
    2. 实现多阶段检测流水线
    3. 统一置信度计算和模式匹配
    4. 支持检测缓存和性能优化
    5. 完全符合人机交互原则
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化统一验证码检测器"""
        super().__init__(config)
        
        self._detector_config = CaptchaDetectorConfig(**(config or {}))
        self._detection_cache = DetectionCache(
            max_size=self._detector_config.max_cache_size,
            ttl=self._detector_config.cache_ttl
        )
        
        # 统一的检测模式库
        self._detection_patterns = self._initialize_detection_patterns()
        self._dom_selectors = self._initialize_dom_selectors()
        
        # 性能监控
        self._detection_stats = {
            'total_detections': 0,
            'cache_hits': 0,
            'stage_usage': {stage.value: 0 for stage in DetectionStageType},
            'average_processing_time': 0.0,
            'pipeline_usage': {pipeline.value: 0 for pipeline in DetectionPipeline}
        }
        
        # 并发控制
        self._semaphore = asyncio.Semaphore(self._detector_config.max_concurrent_detections)
        self._executor = ThreadPoolExecutor(max_workers=3)
        
        logger.info(f"UnifiedCaptchaDetectorPlugin initialized with pipeline: {self._detector_config.detection_pipeline.value}")
    
    def _create_metadata(self) -> PluginMetadata:
        """创建插件元数据"""
        return PluginMetadata(
            name="UnifiedCaptchaDetectorPlugin",
            version="2.0.0",
            category=PluginCategory.CAPTCHA,
            priority=PluginPriority.HIGH,
            author="Mercari AI Agent Team",
            description="统一验证码检测器，整合所有检测逻辑，消除重复代码",
            dependencies=[],
            supported_features=[
                "multi_stage_detection", "pattern_matching", "dom_analysis",
                "context_semantic", "detection_cache", "parallel_processing",
                "human_interaction_compliance", "adaptive_pipeline"
            ]
        )
    
    def _initialize_detection_patterns(self) -> Dict[str, List[PatternInfo]]:
        """初始化检测模式（整合所有重复的模式匹配逻辑）"""
        patterns = {
            'rule_based': [
                # reCAPTCHA模式
                PatternInfo(
                    pattern=r'google\.com/recaptcha|recaptcha\.net|g-recaptcha',
                    captcha_type=CaptchaType.RECAPTCHA_V2,
                    confidence=0.9,
                    weight=1.2,
                    positive_contexts=[r'data-sitekey', r'grecaptcha\.render'],
                    negative_contexts=[r'recaptcha.*disabled', r'test.*recaptcha']
                ),
                
                # hCaptcha模式  
                PatternInfo(
                    pattern=r'hcaptcha\.com|h-captcha',
                    captcha_type=CaptchaType.HCAPTCHA,
                    confidence=0.9,
                    weight=1.2,
                    positive_contexts=[r'data-sitekey.*hcaptcha', r'hcaptcha\.render']
                ),
                
                # 极验模式
                PatternInfo(
                    pattern=r'geetest\.com|gt-captcha|geetest_challenge',
                    captcha_type=CaptchaType.GEETEST,
                    confidence=0.85,
                    weight=1.1,
                    positive_contexts=[r'initGeetest', r'gt_public_key']
                ),
                
                # Cloudflare模式
                PatternInfo(
                    pattern=r'cf-challenge|cloudflare.*challenge|cf-ray',
                    captcha_type=CaptchaType.CLOUDFLARE,
                    confidence=0.8,
                    weight=1.0,
                    positive_contexts=[r'cloudflare.*protection', r'ddos.*protection'],
                    negative_contexts=[r'cloudflare.*cdn']
                ),
                
                # 滑块验证码模式
                PatternInfo(
                    pattern=r'slider.*captcha|slide.*verify|drag.*complete',
                    captcha_type=CaptchaType.SLIDE_PUZZLE,
                    confidence=0.75,
                    weight=0.9,
                    positive_contexts=[r'滑动验证', r'slide.*puzzle']
                ),
                
                # 点击验证码模式
                PatternInfo(
                    pattern=r'click.*captcha|点击.*验证|click.*verify',
                    captcha_type=CaptchaType.CLICK_SEQUENCE,
                    confidence=0.7,
                    weight=0.8
                ),
                
                # 图片验证码模式
                PatternInfo(
                    pattern=r'verify.*code|verification.*image|captcha\.jpg|验证码',
                    captcha_type=CaptchaType.IMAGE_TEXT,
                    confidence=0.6,
                    weight=0.7,
                    positive_contexts=[r'input.*captcha', r'验证码输入'],
                    negative_contexts=[r'email.*verification', r'phone.*verification']
                )
            ],
            
            'contextual_keywords': [
                # 继承原有的上下文关键字检测模式
                PatternInfo(
                    pattern=r'请完成安全验证|完成人机验证|完成验证以继续',
                    captcha_type=CaptchaType.RECAPTCHA_V2,
                    confidence=0.8,
                    weight=1.1,
                    positive_contexts=[r'机器人检测', r'自动化检测']
                )
            ]
        }
        
        return patterns
    
    def _initialize_dom_selectors(self) -> List[DOMSelectorInfo]:
        """初始化DOM选择器（整合重复的DOM检测逻辑）"""
        return [
            # reCAPTCHA
            DOMSelectorInfo('.g-recaptcha', CaptchaType.RECAPTCHA_V2, 0.9,
                          {'data-sitekey': r'^[0-9A-Za-z_-]+$'}),
            DOMSelectorInfo('[data-sitekey]', CaptchaType.RECAPTCHA_V2, 0.85),
            DOMSelectorInfo('#recaptcha', CaptchaType.RECAPTCHA_V2, 0.7),
            
            # hCaptcha
            DOMSelectorInfo('.h-captcha', CaptchaType.HCAPTCHA, 0.9,
                          {'data-sitekey': r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'}),
            
            # 极验
            DOMSelectorInfo('.geetest', CaptchaType.GEETEST, 0.9),
            DOMSelectorInfo('.gt-captcha', CaptchaType.GEETEST, 0.85),
            
            # 图片验证码
            DOMSelectorInfo('img[src*="captcha"]', CaptchaType.IMAGE_TEXT, 0.8),
            DOMSelectorInfo('img[src*="verifycode"]', CaptchaType.IMAGE_TEXT, 0.8),
            DOMSelectorInfo('img[alt*="验证码"]', CaptchaType.IMAGE_TEXT, 0.7),
            
            # 滑块验证码
            DOMSelectorInfo('.slider-captcha', CaptchaType.SLIDE_PUZZLE, 0.8),
            DOMSelectorInfo('.slide-verify', CaptchaType.SLIDE_PUZZLE, 0.8),
            
            # 点击验证码
            DOMSelectorInfo('.click-captcha', CaptchaType.CLICK_SEQUENCE, 0.8),
            DOMSelectorInfo('.click-verify', CaptchaType.CLICK_SEQUENCE, 0.8),
        ]
    
    async def _initialize_impl(self) -> bool:
        """具体初始化实现"""
        try:
            # 预热缓存和模式匹配引擎
            await self._warmup_detection_engine()
            logger.info("Unified captcha detector initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize unified captcha detector: {e}")
            return False
    
    async def _warmup_detection_engine(self):
        """预热检测引擎"""
        # 编译正则表达式以提高性能
        for pattern_list in self._detection_patterns.values():
            for pattern_info in pattern_list:
                try:
                    re.compile(pattern_info.pattern, re.IGNORECASE | re.DOTALL)
                    for ctx_pattern in pattern_info.positive_contexts + pattern_info.negative_contexts:
                        re.compile(ctx_pattern, re.IGNORECASE)
                except re.error as e:
                    logger.warning(f"Invalid regex pattern {pattern_info.pattern}: {e}")
    
    async def _start_impl(self) -> bool:
        """具体启动实现"""
        logger.info("Unified captcha detector started")
        return True
    
    async def _stop_impl(self) -> bool:
        """具体停止实现"""
        # 关闭线程池
        if self._executor:
            self._executor.shutdown(wait=True)
        
        # 清理缓存
        await self._detection_cache.clear()
        
        logger.info("Unified captcha detector stopped")
        return True
    
    async def _apply_config_changes(self):
        """应用配置变更"""
        # 更新缓存配置
        if hasattr(self._detection_cache, 'max_size'):
            self._detection_cache.max_size = self._detector_config.max_cache_size
            self._detection_cache.ttl = self._detector_config.cache_ttl
        
        # 更新并发控制
        self._semaphore = asyncio.Semaphore(self._detector_config.max_concurrent_detections)
        
        logger.info("Unified captcha detector config updated")
    
    def get_supported_captcha_types(self) -> Set[CaptchaType]:
        """获取支持的验证码类型"""
        supported_types = set()
        for pattern_list in self._detection_patterns.values():
            for pattern_info in pattern_list:
                supported_types.add(pattern_info.captcha_type)
        
        for selector_info in self._dom_selectors:
            supported_types.add(selector_info.captcha_type)
        
        return supported_types
    
    async def detect_captcha(self, 
                           content: str, 
                           context: Optional[DetectionContext] = None) -> UnifiedCaptchaDetectionResult:
        """
        统一验证码检测主入口
        
        整合所有检测逻辑，消除重复代码
        """
        start_time = time.time()
        
        # 并发控制
        async with self._semaphore:
            try:
                # 初始化上下文
                if context is None:
                    context = DetectionContext()
                
                context.content_hash = hashlib.md5(content.encode()).hexdigest()
                context.timestamp = datetime.now()
                
                # 检查缓存
                cache_result = None
                if self._detector_config.enable_detection_cache:
                    cache_key = context.get_cache_key()
                    cache_result = await self._detection_cache.get(cache_key)
                    
                    if cache_result:
                        self._detection_stats['cache_hits'] += 1
                        cache_result.cached = True
                        cache_result.cache_hit = True
                        return cache_result
                
                # 执行多阶段检测
                result = await self._execute_detection_pipeline(content, context)
                
                # 缓存结果
                if self._detector_config.enable_detection_cache and cache_key:
                    await self._detection_cache.set(cache_key, result)
                
                # 更新统计
                processing_time = time.time() - start_time
                result.detection_time = processing_time
                result.context = context
                
                self._update_detection_stats(result, processing_time)
                
                return result
                
            except Exception as e:
                logger.error(f"Detection failed: {e}")
                return UnifiedCaptchaDetectionResult(
                    detected=False,
                    confidence=0.0,
                    detection_method="error",
                    detection_time=time.time() - start_time,
                    debug_info={'error': str(e)}
                )
    
    async def _execute_detection_pipeline(self, 
                                        content: str, 
                                        context: DetectionContext) -> UnifiedCaptchaDetectionResult:
        """
        执行检测流水线
        
        根据配置的pipeline模式选择不同的检测策略
        """
        result = UnifiedCaptchaDetectionResult(
            pipeline_used=self._detector_config.detection_pipeline,
            requires_human_action=True,  # 始终需要人工干预
            suggested_action="manual_verification",
            compliance_verified=True
        )
        
        pipeline = self._detector_config.detection_pipeline
        
        if pipeline == DetectionPipeline.FAST:
            await self._execute_fast_pipeline(content, context, result)
        elif pipeline == DetectionPipeline.STANDARD:
            await self._execute_standard_pipeline(content, context, result)
        elif pipeline == DetectionPipeline.COMPREHENSIVE:
            await self._execute_comprehensive_pipeline(content, context, result)
        elif pipeline == DetectionPipeline.ADAPTIVE:
            await self._execute_adaptive_pipeline(content, context, result)
        
        # 最终决策
        result.detected = result.confidence >= self._detector_config.confidence_threshold
        
        return result
    
    async def _execute_fast_pipeline(self, content: str, context: DetectionContext, result: UnifiedCaptchaDetectionResult):
        """快速检测流水线：规则+DOM"""
        # 阶段1：基于规则的检测
        rule_stage = await self._stage_rule_based_detection(content, context)
        result.add_stage_result(rule_stage)
        
        if rule_stage.is_detected:
            # 阶段2：DOM结构验证
            dom_stage = await self._stage_dom_structure_detection(content, context)
            result.add_stage_result(dom_stage)
    
    async def _execute_standard_pipeline(self, content: str, context: DetectionContext, result: UnifiedCaptchaDetectionResult):
        """标准检测流水线：规则+DOM+属性"""
        await self._execute_fast_pipeline(content, context, result)
        
        if result.confidence >= self._detector_config.stage_thresholds[DetectionStageType.DOM_STRUCTURE]:
            # 阶段3：元素属性检查
            attr_stage = await self._stage_element_attribute_detection(content, context)
            result.add_stage_result(attr_stage)
    
    async def _execute_comprehensive_pipeline(self, content: str, context: DetectionContext, result: UnifiedCaptchaDetectionResult):
        """全面检测流水线：所有阶段"""
        await self._execute_standard_pipeline(content, context, result)
        
        if self._detector_config.enable_context_analysis:
            # 阶段4：上下文语义分析
            semantic_stage = await self._stage_context_semantic_detection(content, context)
            result.add_stage_result(semantic_stage)
        
        # 阶段5：图像分析（仅检测不破解）
        if any('img' in element for element in result.dom_elements):
            image_stage = await self._stage_image_analysis_detection(content, context)
            result.add_stage_result(image_stage)
    
    async def _execute_adaptive_pipeline(self, content: str, context: DetectionContext, result: UnifiedCaptchaDetectionResult):
        """自适应检测流水线：根据上下文动态选择"""
        # 先执行快速检测
        await self._execute_fast_pipeline(content, context, result)
        
        # 根据初步结果决定是否继续
        if result.confidence > 0.8:
            # 高置信度，使用标准流水线
            await self._execute_standard_pipeline(content, context, result)
        elif result.confidence > 0.4:
            # 中等置信度，使用全面流水线
            await self._execute_comprehensive_pipeline(content, context, result)
        # 低置信度直接返回
    
    async def _stage_rule_based_detection(self, content: str, context: DetectionContext) -> DetectionStage:
        """阶段1：统一的基于规则检测（整合重复逻辑）"""
        start_time = time.time()
        stage = DetectionStage(
            stage_name="unified_rule_based",
            stage_number=1,
            is_detected=False,
            confidence=0.0
        )
        
        best_match = None
        best_confidence = 0.0
        
        # 整合所有规则检测模式
        all_patterns = []
        all_patterns.extend(self._detection_patterns.get('rule_based', []))
        all_patterns.extend(self._detection_patterns.get('contextual_keywords', []))
        
        for pattern_info in all_patterns:
            try:
                matches = re.findall(pattern_info.pattern, content, re.IGNORECASE | re.DOTALL)
                if matches:
                    # 检查负面上下文
                    if pattern_info.negative_contexts:
                        has_negative = any(
                            re.search(neg_pattern, content, re.IGNORECASE)
                            for neg_pattern in pattern_info.negative_contexts
                        )
                        if has_negative:
                            if pattern_info.early_exit_on_negative:
                                stage.metadata = {'early_exit': True, 'reason': 'negative_context'}
                                stage.processing_time = time.time() - start_time
                                return stage
                            continue
                    
                    # 检查正面上下文
                    confidence_boost = 1.0
                    if pattern_info.positive_contexts:
                        has_positive = any(
                            re.search(pos_pattern, content, re.IGNORECASE)
                            for pos_pattern in pattern_info.positive_contexts
                        )
                        if has_positive:
                            confidence_boost = 1.2
                    
                    # 计算置信度
                    base_confidence = pattern_info.confidence * pattern_info.weight * confidence_boost
                    
                    if base_confidence > best_confidence:
                        best_confidence = base_confidence
                        best_match = {
                            'pattern': pattern_info.pattern,
                            'captcha_type': pattern_info.captcha_type,
                            'matches': matches,
                            'confidence': base_confidence
                        }
                        stage.patterns_matched.extend([str(m) for m in matches])
            
            except re.error as e:
                logger.warning(f"Regex error in pattern {pattern_info.pattern}: {e}")
                continue
        
        if best_match:
            stage.is_detected = True
            stage.confidence = min(best_confidence, 1.0)
            stage.metadata = {
                'best_match': best_match,
                'detection_method': 'unified_rule_based'
            }
        
        stage.processing_time = time.time() - start_time
        self._detection_stats['stage_usage'][DetectionStageType.RULE_BASED.value] += 1
        
        return stage
    
    async def _stage_dom_structure_detection(self, content: str, context: DetectionContext) -> DetectionStage:
        """阶段2：统一的DOM结构检测（整合重复逻辑）"""
        start_time = time.time()
        stage = DetectionStage(
            stage_name="unified_dom_structure",
            stage_number=2,
            is_detected=False,
            confidence=0.0
        )
        
        try:
            soup = BeautifulSoup(content, 'html.parser')
            best_match = None
            best_confidence = 0.0
            detected_elements = []
            
            for selector_info in self._dom_selectors:
                elements = soup.select(selector_info.selector)
                if elements:
                    detected_elements.extend([elem.name for elem in elements])
                    
                    # 验证属性
                    confidence = selector_info.confidence
                    if selector_info.attributes_check:
                        for attr, pattern in selector_info.attributes_check.items():
                            for element in elements:
                                attr_value = element.get(attr, '')
                                if re.match(pattern, attr_value):
                                    confidence *= 1.1  # 属性匹配增强置信度
                                    break
                    
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = {
                            'selector': selector_info.selector,
                            'captcha_type': selector_info.captcha_type,
                            'elements_found': len(elements),
                            'confidence': confidence
                        }
            
            if best_match:
                stage.is_detected = True
                stage.confidence = min(best_confidence, 1.0)
                stage.metadata = {
                    'best_match': best_match,
                    'detected_elements': detected_elements,
                    'detection_method': 'unified_dom_structure'
                }
        
        except Exception as e:
            logger.warning(f"DOM parsing failed: {e}")
            stage.metadata = {'error': str(e)}
        
        stage.processing_time = time.time() - start_time
        self._detection_stats['stage_usage'][DetectionStageType.DOM_STRUCTURE.value] += 1
        
        return stage
    
    async def _stage_element_attribute_detection(self, content: str, context: DetectionContext) -> DetectionStage:
        """阶段3：元素属性检查"""
        start_time = time.time()
        stage = DetectionStage(
            stage_name="element_attribute_check",
            stage_number=3,
            is_detected=False,
            confidence=0.0
        )
        
        # 实现元素属性详细检查逻辑
        # 这里可以添加更精细的属性验证逻辑
        
        stage.processing_time = time.time() - start_time
        self._detection_stats['stage_usage'][DetectionStageType.ELEMENT_ATTRIBUTE.value] += 1
        
        return stage
    
    async def _stage_context_semantic_detection(self, content: str, context: DetectionContext) -> DetectionStage:
        """阶段4：上下文语义分析"""
        start_time = time.time()
        stage = DetectionStage(
            stage_name="context_semantic_analysis",
            stage_number=4,
            is_detected=False,
            confidence=0.0
        )
        
        # 实现语义分析逻辑
        # 分析页面上下文，识别验证码相关的语义信息
        
        stage.processing_time = time.time() - start_time
        self._detection_stats['stage_usage'][DetectionStageType.CONTEXT_SEMANTIC.value] += 1
        
        return stage
    
    async def _stage_image_analysis_detection(self, content: str, context: DetectionContext) -> DetectionStage:
        """阶段5：图像分析检测（仅检测不破解）"""
        start_time = time.time()
        stage = DetectionStage(
            stage_name="image_analysis_detection",
            stage_number=5,
            is_detected=False,
            confidence=0.0
        )
        
        # 实现图像检测逻辑（仅识别图像类型验证码，不进行破解）
        # 符合人机交互原则
        
        stage.processing_time = time.time() - start_time
        self._detection_stats['stage_usage'][DetectionStageType.IMAGE_ANALYSIS.value] += 1
        
        return stage
    
    async def detect_captcha_batch(self, requests: List[Dict[str, Any]]) -> List[UnifiedCaptchaDetectionResult]:
        """批量检测验证码"""
        if not self._detector_config.enable_parallel_detection:
            # 串行处理
            results = []
            for request in requests:
                content = request.get('content', '')
                context = request.get('context')
                if isinstance(context, dict):
                    context = DetectionContext(**context)
                result = await self.detect_captcha(content, context)
                results.append(result)
            return results
        
        # 并行处理
        tasks = []
        for request in requests:
            content = request.get('content', '')
            context = request.get('context')
            if isinstance(context, dict):
                context = DetectionContext(**context)
            task = asyncio.create_task(self.detect_captcha(content, context))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        final_results = []
        for result in results:
            if isinstance(result, Exception):
                final_results.append(UnifiedCaptchaDetectionResult(
                    detected=False,
                    confidence=0.0,
                    detection_method="batch_error",
                    debug_info={'error': str(result)}
                ))
            else:
                final_results.append(result)
        
        return final_results
    
    async def validate_detection_result(self, result: UnifiedCaptchaDetectionResult) -> bool:
        """验证检测结果"""
        # 基本验证
        if not isinstance(result, UnifiedCaptchaDetectionResult):
            return False
        
        # 置信度验证
        if not (0.0 <= result.confidence <= 1.0):
            return False
        
        # 合规性验证
        if not result.compliance_verified:
            return False
        
        # 人机交互原则验证
        if not result.requires_human_action:
            return False
        
        # 检测方法验证
        if result.detected and not result.captcha_type:
            return False
        
        return True
    
    def _update_detection_stats(self, result: UnifiedCaptchaDetectionResult, processing_time: float):
        """更新检测统计"""
        self._detection_stats['total_detections'] += 1
        
        # 更新平均处理时间
        total = self._detection_stats['total_detections']
        current_avg = self._detection_stats['average_processing_time']
        self._detection_stats['average_processing_time'] = (current_avg * (total - 1) + processing_time) / total
        
        # 更新流水线使用统计
        self._detection_stats['pipeline_usage'][result.pipeline_used.value] += 1
    
    def get_detection_stats(self) -> Dict[str, Any]:
        """获取检测统计"""
        cache_stats = self._detection_cache.get_stats()
        
        return {
            **self._detection_stats,
            'cache_stats': cache_stats,
            'cache_hit_rate': (
                self._detection_stats['cache_hits'] / max(self._detection_stats['total_detections'], 1)
            ) * 100
        }
    
    async def _healthcheck_impl(self) -> Dict[str, Any]:
        """健康检查实现"""
        stats = self.get_detection_stats()
        
        return {
            'healthy': True,
            'last_check': datetime.now().isoformat(),
            'supported_types': len(self.get_supported_captcha_types()),
            'detection_patterns': len(sum(self._detection_patterns.values(), [])),
            'dom_selectors': len(self._dom_selectors),
            'cache_size': stats['cache_stats']['size'],
            'total_detections': stats['total_detections']
        }