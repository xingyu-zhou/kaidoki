"""
统一验证码检测器
用于解决CAPTCHA检测逻辑矛盾问题

该模块提供统一的CAPTCHA检测标准和接口，确保所有检测器使用相同的逻辑。
"""

import asyncio
import logging
import re
import time
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import aiohttp
from bs4 import BeautifulSoup

from .captcha_types import CaptchaType, CaptchaDetectionResult
from ..scrapers.anti_bot_handler import BotDetectionType, BotDetectionResult
from .error_handler import get_error_handler, ErrorContext, ErrorCategory
from ..utils.logger import get_logger

logger = get_logger(__name__)


class DetectionStageType(Enum):
    """检测阶段类型"""
    KEYWORD_DETECTION = "keyword_detection"
    DOM_STRUCTURE_VALIDATION = "dom_structure_validation"
    ELEMENT_ATTRIBUTE_CHECK = "element_attribute_check"
    CONTEXT_SEMANTIC_ANALYSIS = "context_semantic_analysis"


class ContextType(Enum):
    """上下文类型"""
    FORM_VALIDATION = "form_validation"
    SIMPLE_REFERENCE = "simple_reference"
    DOCUMENTATION = "documentation"
    ERROR_MESSAGE = "error_message"
    CHALLENGE_ACTIVE = "challenge_active"


@dataclass
class DetectionStage:
    """检测阶段结果"""
    stage_name: str
    stage_number: int
    is_detected: bool
    confidence: float
    patterns_matched: List[str] = field(default_factory=list)
    dom_elements: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    processing_time: float = 0.0


@dataclass
class UnifiedDetectionResult:
    """统一检测结果 - 增强版"""
    # 基础检测信息
    is_detected: bool
    detection_type: Union[BotDetectionType, CaptchaType]
    confidence: float
    detection_method: str
    
    # 多阶段检测结果
    stage_results: List[DetectionStage] = field(default_factory=list)
    final_stage_reached: int = 0
    
    # 详细信息
    details: Dict[str, Any] = field(default_factory=dict)
    patterns_matched: List[str] = field(default_factory=list)
    dom_elements: List[str] = field(default_factory=list)
    
    # 兼容性字段
    is_captcha: bool = False
    captcha_type: Optional[CaptchaType] = None
    
    # 检测元数据
    detection_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    context_info: Dict[str, Any] = field(default_factory=dict)
    debug_info: Dict[str, Any] = field(default_factory=dict)
    
    # 置信度评分细节
    confidence_breakdown: Dict[str, float] = field(default_factory=dict)
    confidence_factors: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """初始化后处理"""
        # 确保兼容性
        if self.detection_type == BotDetectionType.CAPTCHA:
            self.is_captcha = True
            # 根据检测到的具体类型设置captcha_type
            if 'captcha_type' in self.details:
                self.captcha_type = self.details['captcha_type']
            else:
                self.captcha_type = CaptchaType.UNKNOWN
        elif isinstance(self.detection_type, CaptchaType):
            self.is_captcha = True
            self.captcha_type = self.detection_type
            self.detection_type = BotDetectionType.CAPTCHA
    
    def add_stage_result(self, stage: DetectionStage):
        """添加阶段检测结果"""
        self.stage_results.append(stage)
        self.final_stage_reached = max(self.final_stage_reached, stage.stage_number)
        
        # 更新总体结果
        if stage.is_detected:
            self.patterns_matched.extend(stage.patterns_matched)
            self.dom_elements.extend(stage.dom_elements)
            self.details.update(stage.metadata)
    
    def get_stage_summary(self) -> Dict[str, Any]:
        """获取阶段检测摘要"""
        return {
            'total_stages': len(self.stage_results),
            'stages_detected': sum(1 for stage in self.stage_results if stage.is_detected),
            'final_stage_reached': self.final_stage_reached,
            'stage_confidences': {stage.stage_name: stage.confidence for stage in self.stage_results}
        }
    
    def to_bot_detection_result(self) -> BotDetectionResult:
        """转换为BotDetectionResult"""
        from ..scrapers.anti_bot_handler import BypassStrategy
        
        return BotDetectionResult(
            is_detected=self.is_detected,
            detection_type=self.detection_type,
            confidence=self.confidence,
            details=self.details,
            suggested_strategy=BypassStrategy.SOLVE_CAPTCHA if self.is_captcha else BypassStrategy.WAIT_AND_RETRY,
            patterns_matched=self.patterns_matched
        )
    
    def to_captcha_detection_result(self) -> CaptchaDetectionResult:
        """转换为CaptchaDetectionResult - 修复版本，确保生成有效的CaptchaChallenge对象"""
        from .captcha_types import ChallengeBuilder
        
        # 确保captcha_type不为None
        captcha_type = self.captcha_type or CaptchaType.UNKNOWN
        
        # 创建CaptchaChallenge对象（如果检测到CAPTCHA）
        challenge = None
        if self.is_detected:
            try:
                challenge = ChallengeBuilder.create_challenge(
                    captcha_type=captcha_type,
                    detection_result=self,
                    metadata={
                        'detection_source': 'unified_detector',
                        'stage_summary': self.get_stage_summary(),
                        'confidence_breakdown': self.confidence_breakdown,
                        'confidence_factors': self.confidence_factors
                    }
                )
                
                # 记录成功创建挑战对象
                logger.info(f"Successfully created CaptchaChallenge: {challenge.challenge_id} "
                           f"for type {captcha_type.value} with confidence {self.confidence:.2f}")
                
            except Exception as e:
                # 如果创建挑战对象失败，创建紧急挑战对象
                logger.error(f"Failed to create CaptchaChallenge: {e}")
                try:
                    challenge = ChallengeBuilder.create_emergency_challenge(
                        task_id=self.context_info.get('task_id', 'unknown'),
                        captcha_type=captcha_type,
                        reason=f"Challenge creation failed: {str(e)}"
                    )
                    logger.warning(f"Created emergency challenge: {challenge.challenge_id}")
                except Exception as emergency_error:
                    logger.error(f"Failed to create emergency challenge: {emergency_error}")
                    # 最后的降级处理：创建最基本的挑战对象
                    challenge = self._create_minimal_challenge(captcha_type)
        
        return CaptchaDetectionResult(
            detected=self.is_detected,
            captcha_type=captcha_type,
            confidence=self.confidence,
            detection_method=self.detection_method,
            challenge=challenge,
            patterns_matched=self.patterns_matched,
            dom_elements=self.dom_elements,
            detection_time=self.detection_time
        )
    
    def _create_minimal_challenge(self, captcha_type: CaptchaType) -> 'CaptchaChallenge':
        """创建最基本的挑战对象（作为最后的降级处理）"""
        from .captcha_types import CaptchaChallenge, CaptchaStatus
        import uuid
        from datetime import datetime, timedelta
        
        challenge_id = f"minimal_{uuid.uuid4().hex[:8]}"
        
        return CaptchaChallenge(
            challenge_id=challenge_id,
            captcha_type=captcha_type,
            status=CaptchaStatus.DETECTED,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(minutes=5),
            metadata={
                'minimal_creation': True,
                'creation_reason': 'Fallback minimal challenge creation',
                'confidence': self.confidence,
                'detection_method': self.detection_method
            },
            instruction="检测到验证码，请手动完成验证",
            hint="系统检测到验证码但无法确定详细信息，请根据页面提示手动完成验证",
            challenge_params={
                'input_type': 'manual',
                'requires_user_input': True,
                'minimal_mode': True
            }
        )


class UnifiedCaptchaDetector:
    """统一验证码检测器 - 多阶段检测版本"""
    
    def __init__(self):
        """初始化统一检测器"""
        self.detection_patterns = self._load_unified_patterns()
        self.confidence_threshold = 0.6  # 降低到0.6避免authCode误检测
        self.stage_thresholds = {
            DetectionStageType.KEYWORD_DETECTION: 0.5,
            DetectionStageType.DOM_STRUCTURE_VALIDATION: 0.6,
            DetectionStageType.ELEMENT_ATTRIBUTE_CHECK: 0.7,
            DetectionStageType.CONTEXT_SEMANTIC_ANALYSIS: 0.8
        }
        
        # 检测统计
        self.detection_stats = {
            'total_detections': 0,
            'captcha_detections': 0,
            'false_positives': 0,
            'false_negatives': 0,
            'stage_statistics': {stage.value: 0 for stage in DetectionStageType}
        }
        
        # 配置参数
        self.enable_context_analysis = True
        self.enable_debug_logging = True
        self.max_processing_time = 30.0  # 最大处理时间（秒）
        
        # 获取错误处理器
        self.error_handler = get_error_handler()
        
        logger.info("UnifiedCaptchaDetector initialized with multi-stage detection")
    
    def _load_unified_patterns(self) -> Dict[str, List[Dict[str, Any]]]:
        """加载统一的检测模式 - 多阶段版本"""
        return {
            # 阶段1：上下文感知的关键字检测
            'contextual_keywords': [
                {
                    'pattern': r'(?i)(?:^|[^a-zA-Z])(captcha|验证码)(?=[^a-zA-Z]|$)',
                    'type': CaptchaType.UNKNOWN,
                    'confidence': 0.7,
                    'weight': 1.0,
                    'context_required': True,
                    'negative_contexts': [r'(?i)(about|documentation|tutorial|guide|说明|介绍|教程)']
                },
                {
                    'pattern': r'(?i)(?:^|[^a-zA-Z])(challenge|puzzle|滑动验证|点击验证)(?=[^a-zA-Z]|$)',
                    'type': CaptchaType.SLIDE_PUZZLE,
                    'confidence': 0.75,
                    'weight': 0.9,
                    'context_required': True,
                    'positive_contexts': [r'(?i)(complete|solve|verify|验证|完成|解决)']
                },
                {
                    'pattern': r'(?i)(?:^|[^a-zA-Z])(verifycode|authcode|verification)(?=[^a-zA-Z]|$)',
                    'type': CaptchaType.IMAGE_TEXT,
                    'confidence': 0.6,  # 降低置信度避免误检测
                    'weight': 0.8,      # 降低权重
                    'context_required': True,
                    'negative_contexts': [
                        r'(?i)(parameter|param|key|token|secret|config|documentation|doc|api|code\s*[:=])',
                        r'(?i)(function|method|variable|const|let|var|class|interface)',
                        r'(?i)(about|tutorial|guide|example|说明|示例|教程|指南)',
                        r'(?i)(debug|log|console|print|trace|error)',
                        r'(?i)(test|mock|stub|fake|sample)',
                        r'(?i)(auth.*token|access.*token|refresh.*token|bearer)'
                    ],
                    'early_exit_on_negative': True  # 遇到负面上下文立即退出
                }
            ],
            
            # 阶段2：DOM结构验证
            'dom_structure_patterns': [
                {
                    'selector': 'img[src*="captcha"]',
                    'type': CaptchaType.IMAGE_TEXT,
                    'confidence': 0.9,
                    'weight': 1.0,
                    'required_attributes': ['src'],
                    'context_selectors': ['form', 'input[type="text"]']
                },
                {
                    'selector': '.g-recaptcha',
                    'type': CaptchaType.RECAPTCHA_V2,
                    'confidence': 0.95,
                    'weight': 1.0,
                    'required_attributes': ['data-sitekey'],
                    'context_selectors': ['form']
                },
                {
                    'selector': '.h-captcha',
                    'type': CaptchaType.HCAPTCHA,
                    'confidence': 0.95,
                    'weight': 1.0,
                    'required_attributes': ['data-sitekey'],
                    'context_selectors': ['form']
                },
                {
                    'selector': '.slider-captcha, .slide-verify',
                    'type': CaptchaType.SLIDE_PUZZLE,
                    'confidence': 0.9,
                    'weight': 1.0,
                    'context_selectors': ['form', '.captcha-container']
                },
                {
                    'selector': '.geetest, .gt-captcha',
                    'type': CaptchaType.GEETEST,
                    'confidence': 0.95,
                    'weight': 1.0,
                    'context_selectors': ['form']
                }
            ],
            
            # 阶段3：特定元素属性检查
            'element_attributes': [
                {
                    'attribute': 'data-sitekey',
                    'type': CaptchaType.RECAPTCHA_V2,
                    'confidence': 0.95,
                    'weight': 1.0,
                    'validation_pattern': r'^[0-9A-Za-z_-]{40}$'
                },
                {
                    'attribute': 'data-callback',
                    'type': CaptchaType.RECAPTCHA_V2,
                    'confidence': 0.8,
                    'weight': 0.8,
                    'context_required': True
                },
                {
                    'selector': 'iframe[src*="recaptcha"]',
                    'type': CaptchaType.RECAPTCHA_V2,
                    'confidence': 0.9,
                    'weight': 1.0
                },
                {
                    'selector': 'iframe[src*="hcaptcha"]',
                    'type': CaptchaType.HCAPTCHA,
                    'confidence': 0.9,
                    'weight': 1.0
                },
                {
                    'selector': 'script[src*="recaptcha"]',
                    'type': CaptchaType.RECAPTCHA_V2,
                    'confidence': 0.85,
                    'weight': 0.9
                },
                {
                    'selector': 'input[name*="captcha"], input[name*="verify"]',
                    'type': CaptchaType.IMAGE_TEXT,
                    'confidence': 0.8,
                    'weight': 0.9
                }
            ],
            
            # 阶段4：上下文语义分析
            'context_semantic_patterns': [
                {
                    'pattern': r'(?i)(please\s+complete|complete\s+the|solve\s+the|verify\s+that|请完成|请验证|完成验证)',
                    'type': CaptchaType.UNKNOWN,
                    'confidence': 0.7,
                    'weight': 0.8,
                    'context_type': ContextType.CHALLENGE_ACTIVE
                },
                {
                    'pattern': r'(?i)(failed\s+verification|verification\s+failed|验证失败|验证码错误)',
                    'type': CaptchaType.UNKNOWN,
                    'confidence': 0.8,
                    'weight': 0.9,
                    'context_type': ContextType.ERROR_MESSAGE
                },
                {
                    'pattern': r'(?i)(drag\s+to\s+complete|slide\s+to\s+verify|拖动完成|滑动验证)',
                    'type': CaptchaType.SLIDE_PUZZLE,
                    'confidence': 0.9,
                    'weight': 1.0,
                    'context_type': ContextType.CHALLENGE_ACTIVE
                }
            ],
            
            # HTTP状态码检测
            'status_codes': [
                {
                    'code': 429,
                    'type': BotDetectionType.RATE_LIMIT,
                    'confidence': 0.9,
                    'weight': 1.0
                },
                {
                    'code': 403,
                    'type': BotDetectionType.IP_BLOCK,
                    'confidence': 0.7,
                    'weight': 0.8
                }
            ]
        }
    
    async def detect_unified(self,
                           content: str,
                           response: Optional[aiohttp.ClientResponse] = None,
                           url: Optional[str] = None) -> UnifiedDetectionResult:
        """
        统一检测方法 - 多阶段检测版本
        
        Args:
            content: 页面内容
            response: HTTP响应对象
            url: 页面URL
            
        Returns:
            UnifiedDetectionResult: 统一检测结果
        """
        start_time = time.time()
        self.detection_stats['total_detections'] += 1
        
        if self.enable_debug_logging:
            logger.info(f"Starting multi-stage CAPTCHA detection for URL: {url}")
        
        try:
            # 1. 状态码检测（预检）
            status_result = self._check_status_code(response)
            if status_result.is_detected:
                status_result.detection_time = time.time() - start_time
                if self.enable_debug_logging:
                    logger.info(f"Detection completed via status code: {status_result.detection_type}")
                return status_result
            
            # 2. 多阶段内容检测
            multi_stage_result = await self._multi_stage_detection(content, url)
            multi_stage_result.detection_time = time.time() - start_time
            
            if multi_stage_result.is_captcha:
                self.detection_stats['captcha_detections'] += 1
            
            # 3. 更新统计信息
            self.detection_stats['stage_statistics'][DetectionStageType.KEYWORD_DETECTION.value] += 1
            if multi_stage_result.final_stage_reached >= 2:
                self.detection_stats['stage_statistics'][DetectionStageType.DOM_STRUCTURE_VALIDATION.value] += 1
            if multi_stage_result.final_stage_reached >= 3:
                self.detection_stats['stage_statistics'][DetectionStageType.ELEMENT_ATTRIBUTE_CHECK.value] += 1
            if multi_stage_result.final_stage_reached >= 4:
                self.detection_stats['stage_statistics'][DetectionStageType.CONTEXT_SEMANTIC_ANALYSIS.value] += 1
            
            if self.enable_debug_logging:
                logger.info(f"Multi-stage detection completed. Final result: {multi_stage_result.is_detected}, "
                           f"Confidence: {multi_stage_result.confidence:.2f}, "
                           f"Stages reached: {multi_stage_result.final_stage_reached}")
            
            return multi_stage_result
            
        except Exception as e:
            logger.error(f"Multi-stage detection failed: {e}")
            return UnifiedDetectionResult(
                is_detected=False,
                detection_type=BotDetectionType.UNKNOWN,
                confidence=0.0,
                detection_method="multi_stage_error",
                detection_time=time.time() - start_time,
                details={'error': str(e)},
                debug_info={'exception': str(e), 'url': url}
            )
    async def _multi_stage_detection(self, content: str, url: Optional[str] = None) -> UnifiedDetectionResult:
        """
        多阶段检测核心方法
        
        Args:
            content: 页面内容
            url: 页面URL
            
        Returns:
            UnifiedDetectionResult: 检测结果
        """
        detection_result = UnifiedDetectionResult(
            is_detected=False,
            detection_type=BotDetectionType.UNKNOWN,
            confidence=0.0,
            detection_method="multi_stage",
            context_info={'url': url, 'content_length': len(content)}
        )
        
        # 阶段1：上下文感知关键字检测
        stage1_result = await self._stage1_keyword_detection(content)
        detection_result.add_stage_result(stage1_result)
        
        if stage1_result.is_detected and stage1_result.confidence >= self.stage_thresholds[DetectionStageType.KEYWORD_DETECTION]:
            if self.enable_debug_logging:
                logger.info(f"Stage 1 detected CAPTCHA with confidence {stage1_result.confidence:.2f}")
            
            # 阶段2：DOM结构验证
            stage2_result = await self._stage2_dom_structure_validation(content)
            detection_result.add_stage_result(stage2_result)
            
            # 累积置信度
            accumulated_confidence = self._calculate_accumulated_confidence([stage1_result, stage2_result])
            
            if stage2_result.is_detected or accumulated_confidence >= self.stage_thresholds[DetectionStageType.DOM_STRUCTURE_VALIDATION]:
                if self.enable_debug_logging:
                    logger.info(f"Stage 2 validation passed with confidence {accumulated_confidence:.2f}")
                
                # 阶段3：元素属性检查
                stage3_result = await self._stage3_element_attribute_check(content)
                detection_result.add_stage_result(stage3_result)
                
                accumulated_confidence = self._calculate_accumulated_confidence([stage1_result, stage2_result, stage3_result])
                
                if stage3_result.is_detected or accumulated_confidence >= self.stage_thresholds[DetectionStageType.ELEMENT_ATTRIBUTE_CHECK]:
                    if self.enable_debug_logging:
                        logger.info(f"Stage 3 validation passed with confidence {accumulated_confidence:.2f}")
                    
                    # 阶段4：上下文语义分析
                    if self.enable_context_analysis:
                        stage4_result = await self._stage4_context_semantic_analysis(content)
                        detection_result.add_stage_result(stage4_result)
                        
                        accumulated_confidence = self._calculate_accumulated_confidence([stage1_result, stage2_result, stage3_result, stage4_result])
                    
                    # 最终决策
                    if accumulated_confidence >= self.confidence_threshold:
                        detection_result.is_detected = True
                        detection_result.confidence = accumulated_confidence
                        detection_result.detection_type = self._determine_captcha_type([stage1_result, stage2_result, stage3_result, stage4_result if self.enable_context_analysis else None])
                        detection_result.confidence_breakdown = self._build_confidence_breakdown([stage1_result, stage2_result, stage3_result, stage4_result if self.enable_context_analysis else None])
        
        return detection_result
    
    async def _stage1_keyword_detection(self, content: str) -> DetectionStage:
        """
        阶段1：上下文感知关键字检测
        
        Args:
            content: 页面内容
            
        Returns:
            DetectionStage: 检测阶段结果
        """
        start_time = time.time()
        stage_result = DetectionStage(
            stage_name="keyword_detection",
            stage_number=1,
            is_detected=False,
            confidence=0.0
        )
        
        patterns = self.detection_patterns['contextual_keywords']
        best_match = None
        best_confidence = 0.0
        
        for pattern_info in patterns:
            matches = re.findall(pattern_info['pattern'], content)
            if matches:
                # 检查负面上下文（排除误报）
                if pattern_info.get('negative_contexts'):
                    has_negative_context = any(
                        re.search(neg_pattern, content, re.IGNORECASE)
                        for neg_pattern in pattern_info['negative_contexts']
                    )
                    if has_negative_context:
                        if self.enable_debug_logging:
                            logger.debug(f"Keyword match rejected due to negative context: {matches}")
                        
                        # 早期退出机制：如果是高优先级模式且检测到负面上下文，立即退出
                        if pattern_info.get('early_exit_on_negative', False):
                            if self.enable_debug_logging:
                                logger.debug(f"Early exit triggered for pattern: {pattern_info['pattern']}")
                            stage_result.metadata = {
                                'early_exit': True,
                                'reason': 'negative_context_detected',
                                'rejected_matches': matches,
                                'negative_patterns_found': [
                                    neg_pattern for neg_pattern in pattern_info['negative_contexts']
                                    if re.search(neg_pattern, content, re.IGNORECASE)
                                ]
                            }
                            stage_result.processing_time = time.time() - start_time
                            return stage_result  # 立即返回，避免误报累积
                        continue
                
                # 检查正面上下文（增强置信度）
                confidence_boost = 1.0
                if pattern_info.get('positive_contexts'):
                    has_positive_context = any(
                        re.search(pos_pattern, content, re.IGNORECASE)
                        for pos_pattern in pattern_info['positive_contexts']
                    )
                    if has_positive_context:
                        confidence_boost = 1.2
                
                # 计算基础置信度
                base_confidence = pattern_info['confidence'] * pattern_info['weight'] * confidence_boost
                
                if base_confidence > best_confidence:
                    best_confidence = base_confidence
                    best_match = {
                        'pattern': pattern_info['pattern'],
                        'matches': matches,
                        'type': pattern_info['type'],
                        'confidence': base_confidence
                    }
                    stage_result.patterns_matched.extend(matches)
        
        if best_match:
            stage_result.is_detected = True
            stage_result.confidence = min(best_confidence, 1.0)  # 确保不超过1.0
            stage_result.metadata = {
                'best_match': best_match,
                'detection_method': 'contextual_keyword'
            }
            
            if self.enable_debug_logging:
                logger.info(f"Stage 1 keyword detection: {best_match['matches']} with confidence {stage_result.confidence:.2f}")
        
        stage_result.processing_time = time.time() - start_time
        return stage_result
    
    async def _stage2_dom_structure_validation(self, content: str) -> DetectionStage:
        """
        阶段2：DOM结构验证
        
        Args:
            content: 页面内容
            
        Returns:
            DetectionStage: 检测阶段结果
        """
        start_time = time.time()
        stage_result = DetectionStage(
            stage_name="dom_structure_validation",
            stage_number=2,
            is_detected=False,
            confidence=0.0
        )
        
        try:
            soup = BeautifulSoup(content, 'html.parser')
            patterns = self.detection_patterns['dom_structure_patterns']
            
            detection_scores = []
            
            for pattern_info in patterns:
                elements = soup.select(pattern_info['selector'])
                if elements:
                    # 检查必需属性
                    valid_elements = []
                    for element in elements:
                        if pattern_info.get('required_attributes'):
                            has_required_attrs = all(
                                element.has_attr(attr) for attr in pattern_info['required_attributes']
                            )
                            if has_required_attrs:
                                valid_elements.append(element)
                        else:
                            valid_elements.append(element)
                    
                    if valid_elements:
                        # 检查上下文选择器
                        context_boost = 1.0
                        if pattern_info.get('context_selectors'):
                            for context_selector in pattern_info['context_selectors']:
                                context_elements = soup.select(context_selector)
                                if context_elements:
                                    context_boost = 1.1
                                    break
                        
                        score = pattern_info['confidence'] * pattern_info['weight'] * context_boost
                        detection_scores.append({
                            'score': score,
                            'type': pattern_info['type'],
                            'elements': len(valid_elements),
                            'selector': pattern_info['selector']
                        })
                        
                        stage_result.dom_elements.extend([elem.name for elem in valid_elements])
            
            if detection_scores:
                best_detection = max(detection_scores, key=lambda x: x['score'])
                stage_result.is_detected = True
                stage_result.confidence = min(best_detection['score'], 1.0)
                stage_result.metadata = {
                    'best_detection': best_detection,
                    'all_detections': detection_scores,
                    'detection_method': 'dom_structure'
                }
                
                if self.enable_debug_logging:
                    logger.info(f"Stage 2 DOM validation: {best_detection['selector']} with confidence {stage_result.confidence:.2f}")
        
        except Exception as e:
            logger.warning(f"Stage 2 DOM validation failed: {e}")
            stage_result.metadata = {'error': str(e)}
        
        stage_result.processing_time = time.time() - start_time
        return stage_result
    
    async def _stage3_element_attribute_check(self, content: str) -> DetectionStage:
        """
        阶段3：元素属性检查
        
        Args:
            content: 页面内容
            
        Returns:
            DetectionStage: 检测阶段结果
        """
        start_time = time.time()
        stage_result = DetectionStage(
            stage_name="element_attribute_check",
            stage_number=3,
            is_detected=False,
            confidence=0.0
        )
        
        try:
            soup = BeautifulSoup(content, 'html.parser')
            patterns = self.detection_patterns['element_attributes']
            
            detection_scores = []
            
            for pattern_info in patterns:
                if pattern_info.get('attribute'):
                    # 检查特定属性
                    elements = soup.find_all(attrs={pattern_info['attribute']: True})
                    if elements:
                        # 验证属性值格式
                        valid_elements = []
                        for element in elements:
                            attr_value = element.get(pattern_info['attribute'])
                            if pattern_info.get('validation_pattern'):
                                if re.match(pattern_info['validation_pattern'], attr_value):
                                    valid_elements.append(element)
                            else:
                                valid_elements.append(element)
                        
                        if valid_elements:
                            score = pattern_info['confidence'] * pattern_info['weight']
                            detection_scores.append({
                                'score': score,
                                'type': pattern_info['type'],
                                'attribute': pattern_info['attribute'],
                                'elements': len(valid_elements)
                            })
                
                elif pattern_info.get('selector'):
                    # 检查选择器
                    elements = soup.select(pattern_info['selector'])
                    if elements:
                        score = pattern_info['confidence'] * pattern_info['weight']
                        detection_scores.append({
                            'score': score,
                            'type': pattern_info['type'],
                            'selector': pattern_info['selector'],
                            'elements': len(elements)
                        })
                        
                        stage_result.dom_elements.extend([elem.name for elem in elements])
            
            if detection_scores:
                best_detection = max(detection_scores, key=lambda x: x['score'])
                stage_result.is_detected = True
                stage_result.confidence = min(best_detection['score'], 1.0)
                stage_result.metadata = {
                    'best_detection': best_detection,
                    'all_detections': detection_scores,
                    'detection_method': 'element_attribute'
                }
                
                if self.enable_debug_logging:
                    logger.info(f"Stage 3 attribute check: {best_detection.get('attribute', best_detection.get('selector'))} with confidence {stage_result.confidence:.2f}")
        
        except Exception as e:
            logger.warning(f"Stage 3 attribute check failed: {e}")
            stage_result.metadata = {'error': str(e)}
        
        stage_result.processing_time = time.time() - start_time
        return stage_result
    
    async def _stage4_context_semantic_analysis(self, content: str) -> DetectionStage:
        """
        阶段4：上下文语义分析
        
        Args:
            content: 页面内容
            
        Returns:
            DetectionStage: 检测阶段结果
        """
        start_time = time.time()
        stage_result = DetectionStage(
            stage_name="context_semantic_analysis",
            stage_number=4,
            is_detected=False,
            confidence=0.0
        )
        
        patterns = self.detection_patterns['context_semantic_patterns']
        
        detection_scores = []
        
        for pattern_info in patterns:
            matches = re.findall(pattern_info['pattern'], content)
            if matches:
                # 上下文类型分析
                context_type = pattern_info.get('context_type', ContextType.SIMPLE_REFERENCE)
                
                # 根据上下文类型调整置信度
                context_multiplier = 1.0
                if context_type == ContextType.CHALLENGE_ACTIVE:
                    context_multiplier = 1.3
                elif context_type == ContextType.ERROR_MESSAGE:
                    context_multiplier = 1.2
                elif context_type == ContextType.FORM_VALIDATION:
                    context_multiplier = 1.1
                elif context_type == ContextType.DOCUMENTATION:
                    context_multiplier = 0.5  # 降低文档中的置信度
                
                score = pattern_info['confidence'] * pattern_info['weight'] * context_multiplier
                detection_scores.append({
                    'score': score,
                    'type': pattern_info['type'],
                    'context_type': context_type,
                    'matches': matches
                })
                
                stage_result.patterns_matched.extend(matches)
        
        if detection_scores:
            best_detection = max(detection_scores, key=lambda x: x['score'])
            stage_result.is_detected = True
            stage_result.confidence = min(best_detection['score'], 1.0)
            stage_result.metadata = {
                'best_detection': best_detection,
                'all_detections': detection_scores,
                'detection_method': 'context_semantic'
            }
            
            if self.enable_debug_logging:
                logger.info(f"Stage 4 context analysis: {best_detection['context_type']} with confidence {stage_result.confidence:.2f}")
        
        stage_result.processing_time = time.time() - start_time
        return stage_result
    
    def _calculate_accumulated_confidence(self, stage_results: List[DetectionStage]) -> float:
        """
        计算累积置信度
        
        Args:
            stage_results: 阶段结果列表
            
        Returns:
            float: 累积置信度
        """
        if not stage_results:
            return 0.0
        
        # 过滤掉None值
        valid_stages = [stage for stage in stage_results if stage is not None]
        
        if not valid_stages:
            return 0.0
        
        # 加权平均计算累积置信度
        total_weight = 0.0
        weighted_sum = 0.0
        
        for stage in valid_stages:
            if stage.is_detected:
                # 根据阶段重要性分配权重
                stage_weight = self._get_stage_weight(stage.stage_number)
                total_weight += stage_weight
                weighted_sum += stage.confidence * stage_weight
        
        if total_weight > 0:
            return min(weighted_sum / total_weight, 1.0)
        
        return 0.0
    
    def _get_stage_weight(self, stage_number: int) -> float:
        """
        获取阶段权重
        
        Args:
            stage_number: 阶段编号
            
        Returns:
            float: 阶段权重
        """
        stage_weights = {
            1: 0.8,  # 关键字检测权重
            2: 1.0,  # DOM结构验证权重（最重要）
            3: 0.9,  # 元素属性检查权重
            4: 0.7   # 上下文语义分析权重
        }
        return stage_weights.get(stage_number, 0.5)
    
    def _determine_captcha_type(self, stage_results: List[Optional[DetectionStage]]) -> CaptchaType:
        """
        确定验证码类型
        
        Args:
            stage_results: 阶段结果列表
            
        Returns:
            CaptchaType: 验证码类型
        """
        # 收集所有检测到的类型及其置信度
        type_scores = {}
        
        for stage in stage_results:
            if stage is None or not stage.is_detected:
                continue
                
            if 'best_detection' in stage.metadata:
                detection = stage.metadata['best_detection']
                captcha_type = detection.get('type', CaptchaType.UNKNOWN)
                
                # 累积类型分数
                if captcha_type in type_scores:
                    type_scores[captcha_type] += stage.confidence
                else:
                    type_scores[captcha_type] = stage.confidence
            
            elif 'best_match' in stage.metadata:
                match = stage.metadata['best_match']
                captcha_type = match.get('type', CaptchaType.UNKNOWN)
                
                if captcha_type in type_scores:
                    type_scores[captcha_type] += stage.confidence
                else:
                    type_scores[captcha_type] = stage.confidence
        
        # 返回得分最高的类型
        if type_scores:
            return max(type_scores, key=type_scores.get)
        
        return CaptchaType.UNKNOWN
    
    def _build_confidence_breakdown(self, stage_results: List[Optional[DetectionStage]]) -> Dict[str, float]:
        """
        构建置信度分解
        
        Args:
            stage_results: 阶段结果列表
            
        Returns:
            Dict[str, float]: 置信度分解
        """
        breakdown = {}
        
        for stage in stage_results:
            if stage is None:
                continue
                
            stage_key = f"stage_{stage.stage_number}_{stage.stage_name}"
            breakdown[stage_key] = stage.confidence
        
        # 添加累积置信度
        breakdown['accumulated_confidence'] = self._calculate_accumulated_confidence(stage_results)
        
        return breakdown
    
        
        detection_scores = []
        
        for pattern_info in patterns:
            matches = re.findall(pattern_info['pattern'], content)
            if matches:
                # 上下文类型分析
                context_type = pattern_info.get('context_type', ContextType.SIMPLE_REFERENCE)
                
                # 根据上下文类型调整置信度
                context_multiplier = 1.0
                if context_type == ContextType.CHALLENGE_ACTIVE:
                    context_multiplier = 1.3
                elif context_type == ContextType.ERROR_MESSAGE:
                    context_multiplier = 1.2
                elif context_type == ContextType.FORM_VALIDATION:
                    context_multiplier = 1.1
                elif context_type == ContextType.DOCUMENTATION:
                    context_multiplier = 0.5  # 降低文档中的置信度
                
                score = pattern_info['confidence'] * pattern_info['weight'] * context_multiplier
                detection_scores.append({
                    'score': score,
                    'type': pattern_info['type'],
                    'context_type': context_type,
                    'matches': matches
                })
                
                stage_result.patterns_matched.extend(matches)
        
        if detection_scores:
            best_detection = max(detection_scores, key=lambda x: x['score'])
            stage_result.is_detected = True
            stage_result.confidence = min(best_detection['score'], 1.0)
            stage_result.metadata = {
                'best_detection': best_detection,
                'all_detections': detection_scores,
                'detection_method': 'context_semantic'
            }
            
            if self.enable_debug_logging:
                logger.info(f"Stage 4 context analysis: {best_detection['context_type']} with confidence {stage_result.confidence:.2f}")
        
        stage_result.processing_time = time.time() - start_time
        return stage_result
    
    
    def _check_status_code(self, response: Optional[aiohttp.ClientResponse]) -> UnifiedDetectionResult:
        """检查HTTP状态码"""
        if not response:
            return UnifiedDetectionResult(
                is_detected=False,
                detection_type=BotDetectionType.UNKNOWN,
                confidence=0.0,
                detection_method="status_code_unavailable"
            )
        
        for status_info in self.detection_patterns['status_codes']:
            if response.status == status_info['code']:
                return UnifiedDetectionResult(
                    is_detected=True,
                    detection_type=status_info['type'],
                    confidence=status_info['confidence'],
                    detection_method="status_code",
                    details={'status_code': response.status}
                )
        
        return UnifiedDetectionResult(
            is_detected=False,
            detection_type=BotDetectionType.UNKNOWN,
            confidence=0.0,
            detection_method="status_code_normal"
        )
    
    async def _detect_content(self, content: str, url: Optional[str] = None) -> UnifiedDetectionResult:
        """检测页面内容"""
        detection_scores = []
        matched_patterns = []
        dom_elements = []
        
        # 1. 关键词检测
        for pattern_info in self.detection_patterns['captcha_keywords']:
            matches = re.findall(pattern_info['pattern'], content)
            if matches:
                score = pattern_info['confidence'] * pattern_info['weight']
                detection_scores.append({
                    'score': score,
                    'type': pattern_info['type'],
                    'method': 'keyword',
                    'matches': matches
                })
                matched_patterns.extend(matches)
        
        # 2. DOM检测
        try:
            soup = BeautifulSoup(content, 'html.parser')
            for selector_info in self.detection_patterns['dom_selectors']:
                elements = soup.select(selector_info['selector'])
                if elements:
                    score = selector_info['confidence'] * selector_info['weight']
                    detection_scores.append({
                        'score': score,
                        'type': selector_info['type'],
                        'method': 'dom',
                        'elements': len(elements)
                    })
                    dom_elements.extend([elem.name for elem in elements])
        except Exception as e:
            logger.warning(f"DOM detection failed: {e}")
        
        # 3. 评估结果
        if not detection_scores:
            return UnifiedDetectionResult(
                is_detected=False,
                detection_type=BotDetectionType.UNKNOWN,
                confidence=0.0,
                detection_method="content_negative"
            )
        
        # 选择最高分数的检测结果
        best_detection = max(detection_scores, key=lambda x: x['score'])
        
        if best_detection['score'] >= self.confidence_threshold:
            return UnifiedDetectionResult(
                is_detected=True,
                detection_type=best_detection['type'],
                confidence=best_detection['score'],
                detection_method=f"content_{best_detection['method']}",
                patterns_matched=matched_patterns,
                dom_elements=dom_elements,
                details={
                    'best_match': best_detection,
                    'all_scores': detection_scores
                }
            )
        else:
            return UnifiedDetectionResult(
                is_detected=False,
                detection_type=BotDetectionType.UNKNOWN,
                confidence=best_detection['score'],
                detection_method="content_low_confidence",
                patterns_matched=matched_patterns,
                dom_elements=dom_elements,
                details={
                    'best_match': best_detection,
                    'threshold': self.confidence_threshold
                }
            )
    
    async def is_captcha_detected(self, 
                                content: str,
                                response: Optional[aiohttp.ClientResponse] = None,
                                url: Optional[str] = None) -> bool:
        """
        简化的CAPTCHA检测方法
        
        Args:
            content: 页面内容
            response: HTTP响应对象
            url: 页面URL
            
        Returns:
            bool: 是否检测到CAPTCHA
        """
        result = await self.detect_unified(content, response, url)
        return result.is_captcha
    
    def get_detection_stats(self) -> Dict[str, Any]:
        """获取检测统计信息"""
        total = self.detection_stats['total_detections']
        return {
            **self.detection_stats,
            'captcha_rate': (self.detection_stats['captcha_detections'] / total * 100) if total > 0 else 0,
            'accuracy': (total - self.detection_stats['false_positives'] - self.detection_stats['false_negatives']) / total * 100 if total > 0 else 0
        }
    
    def update_confidence_threshold(self, new_threshold: float):
        """更新置信度阈值"""
        self.confidence_threshold = max(0.1, min(1.0, new_threshold))
        logger.info(f"Confidence threshold updated to {self.confidence_threshold}")
    
    def log_detection_result(self, result: UnifiedDetectionResult, task_id: str = None):
        """记录检测结果"""
        log_data = {
            'task_id': task_id,
            'detected': result.is_detected,
            'is_captcha': result.is_captcha,
            'detection_type': result.detection_type.value if hasattr(result.detection_type, 'value') else str(result.detection_type),
            'confidence': result.confidence,
            'method': result.detection_method,
            'detection_time': result.detection_time
        }
        
        if result.is_detected:
            if result.is_captcha:
                logger.info(f"CAPTCHA detected for task {task_id}: {result.captcha_type.value if result.captcha_type else 'unknown'}", extra=log_data)
            else:
                logger.info(f"Bot protection detected for task {task_id}: {result.detection_type.value}", extra=log_data)
        else:
            logger.debug(f"No captcha detected for task {task_id}", extra=log_data)


# 全局实例
_unified_detector = None

def get_unified_detector() -> UnifiedCaptchaDetector:
    """获取统一检测器实例"""
    global _unified_detector
    if _unified_detector is None:
        _unified_detector = UnifiedCaptchaDetector()
    return _unified_detector