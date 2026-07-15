"""
验证码检测器模块

该模块提供多层次的验证码检测功能，专门用于识别验证码存在，包括：
- 基于规则的检测
- 基于DOM结构的检测
- 基于图像分析的检测

重要说明：
本系统完全基于人机交互设计，不进行任何自动化验证码破解或内容识别。
验证码检测仅用于识别验证码存在，不进行任何自动化破解或内容识别。
所有验证码解决都需要人工干预。
系统设计原则：
1. 仅检测验证码存在，不尝试自动解决
2. 不使用机器学习进行自动化识别
3. 所有验证码处理都需要人工参与
4. 完全符合人机交互设计理念
"""

import asyncio
import logging
import re
import time
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse
import aiohttp
from bs4 import BeautifulSoup

from .captcha_types import (
    CaptchaType, CaptchaChallenge, CaptchaDetectionResult,
    CaptchaStatus, CAPTCHA_PATTERNS, CAPTCHA_DETECTION_CONFIG
)
from .unified_captcha_detector import get_unified_detector
from ..utils.logger import get_logger

logger = get_logger(__name__)


class CaptchaDetector:
    """
    验证码检测器
    
    本检测器专门用于识别验证码存在，不进行任何自动化破解或内容识别。
    
    设计原则：
    1. 仅检测验证码存在，不尝试自动解决
    2. 不使用机器学习进行自动化识别
    3. 所有验证码处理都需要人工参与
    4. 完全符合人机交互设计理念
    
    支持的检测方法：
    - 基于规则的检测：通过预定义模式识别验证码
    - 基于DOM结构的检测：通过页面元素识别验证码
    - 基于图像分析的检测：通过图像URL识别验证码
    
    注意：ML检测已被禁用，确保系统完全基于人机交互
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化验证码检测器
        
        Args:
            config: 检测配置
        """
        self.config = config or CAPTCHA_DETECTION_CONFIG
        self.detection_patterns = CAPTCHA_PATTERNS
        self.ml_model = None
        self.detection_history = []
        
        # 统计信息
        self.total_detections = 0
        self.successful_detections = 0
        self.detection_times = []
        
        # 初始化ML模型
        self._initialize_ml_model()
        
        # 获取统一检测器实例
        self.unified_detector = get_unified_detector()
        
        logger.info("CaptchaDetector initialized with unified detector")
    
    def _initialize_ml_model(self):
        """
        初始化机器学习模型
        
        注意：本系统完全基于人机交互设计，不使用任何ML模型进行自动化识别
        验证码检测仅用于识别验证码存在，不进行任何自动化破解或内容识别
        所有验证码解决都需要人工干预
        """
        # 不初始化ML模型，确保系统完全基于人机交互
        self.ml_model = None
        logger.info("ML model initialization skipped - system designed for human interaction only")
    
    async def detect_captcha(self, content: str,
                           response: Optional[aiohttp.ClientResponse] = None,
                           url: Optional[str] = None) -> CaptchaDetectionResult:
        """
        检测验证码存在
        
        重要说明：
        本方法仅用于检测验证码存在，不进行任何自动化破解或内容识别。
        所有验证码解决都需要人工干预。
        系统完全基于人机交互设计。
        
        Args:
            content: 页面内容
            response: HTTP响应对象
            url: 页面URL
            
        Returns:
            CaptchaDetectionResult: 检测结果（仅表示是否存在验证码，不含破解信息）
            
        注意：
        - 检测结果仅用于提示用户验证码存在
        - 不提供任何自动化解决方案
        - 需要人工参与完成验证码处理
        """
        start_time = time.time()
        self.total_detections += 1
        
        try:
            # 🔧 修复：使用统一检测器进行检测
            unified_result = await self.unified_detector.detect_unified(content, response, url)
            
            # 转换为CaptchaDetectionResult格式
            final_result = unified_result.to_captcha_detection_result()
            
            # 如果统一检测器未检测到CAPTCHA，但检测到其他类型的保护，则执行原有检测逻辑作为后备
            if not unified_result.is_captcha and unified_result.is_detected:
                logger.debug("Unified detector found non-CAPTCHA protection, running fallback CAPTCHA detection")
                fallback_result = await self._fallback_detection(content, response, url)
                if fallback_result.detected:
                    final_result = fallback_result
            
            # 记录检测时间
            detection_time = time.time() - start_time
            final_result.detection_time = detection_time
            self.detection_times.append(detection_time)
            
            # 更新统计
            if final_result.detected:
                self.successful_detections += 1
                logger.info(f"CAPTCHA detected: {final_result.captcha_type.value}")
            else:
                logger.debug("No CAPTCHA detected")
            
            # 记录检测历史
            self._record_detection_history(final_result)
            
            return final_result
            
        except Exception as e:
            logger.error(f"CAPTCHA detection failed: {e}")
            return CaptchaDetectionResult(
                detected=False,
                detection_method="error",
                detection_time=time.time() - start_time
            )
    
    async def _rule_based_detection(self, content: str, url: Optional[str] = None) -> CaptchaDetectionResult:
        """基于规则的检测"""
        matched_patterns = []
        best_match = None
        highest_confidence = 0.0
        
        for captcha_type, patterns in self.detection_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
                if matches:
                    matched_patterns.append(pattern)
                    # 计算置信度
                    confidence = self._calculate_pattern_confidence(pattern, matches, content)
                    
                    if confidence > highest_confidence:
                        highest_confidence = confidence
                        best_match = captcha_type
        
        if best_match and highest_confidence >= self.config["confidence_threshold"]:
            # 创建验证码挑战
            challenge = await self._create_challenge(best_match, content, url)
            
            return CaptchaDetectionResult(
                detected=True,
                captcha_type=best_match,
                confidence=highest_confidence,
                detection_method="rule_based",
                challenge=challenge,
                patterns_matched=matched_patterns
            )
        
        return CaptchaDetectionResult(
            detected=False,
            detection_method="rule_based",
            patterns_matched=matched_patterns
        )
    
    async def _dom_based_detection(self, content: str, url: Optional[str] = None) -> CaptchaDetectionResult:
        """基于DOM结构的检测"""
        if not self.config.get("enable_dom_detection", True):
            return CaptchaDetectionResult(detected=False, detection_method="dom_disabled")
        
        try:
            soup = BeautifulSoup(content, 'html.parser')
            detected_elements = []
            captcha_type = None
            confidence = 0.0
            
            # 检测常见的验证码元素
            captcha_indicators = [
                # 图片验证码
                ('img[src*="captcha"]', CaptchaType.IMAGE_TEXT),
                ('img[src*="verifycode"]', CaptchaType.IMAGE_TEXT),
                ('img[alt*="验证码"]', CaptchaType.IMAGE_TEXT),
                
                # reCAPTCHA
                ('.g-recaptcha', CaptchaType.RECAPTCHA_V2),
                ('[data-sitekey]', CaptchaType.RECAPTCHA_V2),
                
                # hCaptcha
                ('.h-captcha', CaptchaType.HCAPTCHA),
                
                # 滑块验证码
                ('.slider-captcha', CaptchaType.SLIDE_PUZZLE),
                ('.slide-verify', CaptchaType.SLIDE_PUZZLE),
                
                # 点击验证码
                ('.click-captcha', CaptchaType.CLICK_SEQUENCE),
                ('.click-verify', CaptchaType.CLICK_SEQUENCE),
                
                # 极验验证码
                ('.geetest', CaptchaType.GEETEST),
                ('.gt-captcha', CaptchaType.GEETEST)
            ]
            
            for selector, detected_type in captcha_indicators:
                elements = soup.select(selector)
                if elements:
                    detected_elements.extend([elem.name for elem in elements])
                    captcha_type = detected_type
                    confidence = 0.9  # DOM检测置信度较高
                    break
            
            if captcha_type:
                challenge = await self._create_challenge(captcha_type, content, url)
                return CaptchaDetectionResult(
                    detected=True,
                    captcha_type=captcha_type,
                    confidence=confidence,
                    detection_method="dom_based",
                    challenge=challenge,
                    dom_elements=detected_elements
                )
            
            return CaptchaDetectionResult(
                detected=False,
                detection_method="dom_based",
                dom_elements=detected_elements
            )
            
        except Exception as e:
            logger.error(f"DOM detection failed: {e}")
            return CaptchaDetectionResult(
                detected=False,
                detection_method="dom_error"
            )
    
    async def _ml_based_detection(self, content: str,
                                response: Optional[aiohttp.ClientResponse] = None) -> CaptchaDetectionResult:
        """
        基于机器学习的检测
        
        注意：本系统完全基于人机交互设计，不使用ML进行自动化识别
        该方法保留框架但不执行任何实际的ML预测
        验证码检测仅用于识别验证码存在，不进行任何自动化破解或内容识别
        所有验证码解决都需要人工干预
        """
        # 不使用ML进行自动化识别，直接返回未检测状态
        logger.debug("ML detection skipped - system designed for human interaction only")
        
        return CaptchaDetectionResult(
            detected=False,
            detection_method="ml_disabled_by_design",
            ml_score=0.0
        )
    
    async def _image_based_detection(self, content: str, url: Optional[str] = None) -> CaptchaDetectionResult:
        """基于图像分析的检测"""
        if not self.config.get("enable_image_analysis", True):
            return CaptchaDetectionResult(detected=False, detection_method="image_disabled")
        
        try:
            # 提取图像URL
            image_urls = self._extract_image_urls(content, url)
            captcha_images = []
            
            for img_url in image_urls:
                if self._is_captcha_image_url(img_url):
                    captcha_images.append(img_url)
            
            if captcha_images:
                # 假设找到验证码图像
                captcha_type = CaptchaType.IMAGE_TEXT  # 默认为图片文字验证码
                challenge = await self._create_challenge(captcha_type, content, url)
                challenge.image_url = captcha_images[0]
                
                return CaptchaDetectionResult(
                    detected=True,
                    captcha_type=captcha_type,
                    confidence=0.8,
                    detection_method="image_based",
                    challenge=challenge
                )
            
            return CaptchaDetectionResult(
                detected=False,
                detection_method="image_based"
            )
            
        except Exception as e:
            logger.error(f"Image detection failed: {e}")
            return CaptchaDetectionResult(
                detected=False,
                detection_method="image_error"
            )
    
    def _fuse_detection_results(self, results: List[CaptchaDetectionResult]) -> CaptchaDetectionResult:
        """融合检测结果"""
        detected_results = [r for r in results if r.detected]
        
        if not detected_results:
            # 没有检测到验证码
            return CaptchaDetectionResult(
                detected=False,
                detection_method="fused_negative"
            )
        
        # 选择置信度最高的结果
        best_result = max(detected_results, key=lambda r: r.confidence)
        
        # 融合其他信息
        all_patterns = []
        all_dom_elements = []
        ml_scores = []
        
        for result in results:
            all_patterns.extend(result.patterns_matched)
            all_dom_elements.extend(result.dom_elements)
            if result.ml_score is not None:
                ml_scores.append(result.ml_score)
        
        # 创建融合结果
        fused_result = CaptchaDetectionResult(
            detected=True,
            captcha_type=best_result.captcha_type,
            confidence=best_result.confidence,
            detection_method=f"fused_{best_result.detection_method}",
            challenge=best_result.challenge,
            patterns_matched=list(set(all_patterns)),
            dom_elements=list(set(all_dom_elements)),
            ml_score=max(ml_scores) if ml_scores else None
        )
        
        return fused_result
    
    async def _create_challenge(self, captcha_type: CaptchaType, 
                              content: str, url: Optional[str] = None) -> CaptchaChallenge:
        """创建验证码挑战"""
        import uuid
        
        challenge_id = str(uuid.uuid4())
        challenge = CaptchaChallenge(
            challenge_id=challenge_id,
            captcha_type=captcha_type,
            status=CaptchaStatus.DETECTED,
            expires_at=datetime.now() + timedelta(minutes=5)
        )
        
        # 根据类型设置特定参数
        if captcha_type == CaptchaType.IMAGE_TEXT:
            challenge.instruction = "请输入图片中的文字"
            # 尝试提取图片URL
            img_url = self._extract_captcha_image_url(content, url)
            if img_url:
                challenge.image_url = img_url
        
        elif captcha_type == CaptchaType.SLIDE_PUZZLE:
            challenge.instruction = "请拖动滑块完成验证"
            
        elif captcha_type == CaptchaType.CLICK_SEQUENCE:
            challenge.instruction = "请按顺序点击指定区域"
            
        elif captcha_type == CaptchaType.RECAPTCHA_V2:
            challenge.instruction = "请完成Google reCAPTCHA验证"
            
        elif captcha_type == CaptchaType.GEETEST:
            challenge.instruction = "请完成极验验证"
        
        return challenge
    
    def _calculate_pattern_confidence(self, pattern: str, matches: List[str], content: str) -> float:
        """计算模式匹配置信度"""
        base_confidence = 0.6
        
        # 根据匹配数量调整
        match_count = len(matches)
        if match_count > 1:
            base_confidence += 0.1
        
        # 根据模式特异性调整
        if "captcha" in pattern.lower():
            base_confidence += 0.2
        
        if "验证码" in pattern:
            base_confidence += 0.2
        
        return min(base_confidence, 1.0)
    
    def _extract_ml_features(self, content: str, 
                           response: Optional[aiohttp.ClientResponse] = None) -> Dict[str, Any]:
        """提取机器学习特征"""
        features = {
            "content_length": len(content),
            "has_forms": content.count("<form") > 0,
            "has_images": content.count("<img") > 0,
            "has_scripts": content.count("<script") > 0,
            "captcha_keywords": self._count_captcha_keywords(content),
            "suspicious_patterns": self._count_suspicious_patterns(content)
        }
        
        if response:
            features.update({
                "status_code": response.status,
                "content_type": response.headers.get("content-type", ""),
                "server": response.headers.get("server", "")
            })
        
        return features
    
    def _count_captcha_keywords(self, content: str) -> int:
        """计算验证码关键词数量"""
        keywords = [
            "captcha", "验证码", "verifycode", "authcode", 
            "verification", "challenge", "puzzle", "slider"
        ]
        count = 0
        for keyword in keywords:
            count += content.lower().count(keyword)
        return count
    
    def _count_suspicious_patterns(self, content: str) -> int:
        """计算可疑模式数量"""
        patterns = [
            r'data-sitekey',
            r'g-recaptcha',
            r'hcaptcha',
            r'geetest',
            r'slide.*verify',
            r'click.*verify'
        ]
        count = 0
        for pattern in patterns:
            count += len(re.findall(pattern, content, re.IGNORECASE))
        return count
    
    def _map_ml_result_to_type(self, ml_type: str) -> CaptchaType:
        """映射ML结果到验证码类型"""
        mapping = {
            "image": CaptchaType.IMAGE_TEXT,
            "slider": CaptchaType.SLIDE_PUZZLE,
            "click": CaptchaType.CLICK_SEQUENCE,
            "recaptcha": CaptchaType.RECAPTCHA_V2,
            "geetest": CaptchaType.GEETEST
        }
        return mapping.get(ml_type, CaptchaType.CUSTOM)
    
    def _extract_image_urls(self, content: str, base_url: Optional[str] = None) -> List[str]:
        """提取图像URL"""
        soup = BeautifulSoup(content, 'html.parser')
        img_tags = soup.find_all('img')
        
        urls = []
        for img in img_tags:
            src = img.get('src')
            if src:
                if base_url and not src.startswith(('http://', 'https://')):
                    src = urljoin(base_url, src)
                urls.append(src)
        
        return urls
    
    def _is_captcha_image_url(self, url: str) -> bool:
        """判断是否为验证码图像URL"""
        captcha_indicators = [
            "captcha", "verifycode", "authcode", "verification", 
            "challenge", "verify", "code", "rand"
        ]
        
        url_lower = url.lower()
        return any(indicator in url_lower for indicator in captcha_indicators)
    
    def _extract_captcha_image_url(self, content: str, base_url: Optional[str] = None) -> Optional[str]:
        """提取验证码图像URL"""
        image_urls = self._extract_image_urls(content, base_url)
        
        for url in image_urls:
            if self._is_captcha_image_url(url):
                return url
        
        return None
    
    def _record_detection_history(self, result: CaptchaDetectionResult):
        """记录检测历史"""
        history_entry = {
            "timestamp": datetime.now().isoformat(),
            "detected": result.detected,
            "captcha_type": result.captcha_type.value if result.captcha_type else None,
            "confidence": result.confidence,
            "detection_method": result.detection_method,
            "detection_time": result.detection_time
        }
        
        self.detection_history.append(history_entry)
        
        # 保持历史记录在合理范围内
        if len(self.detection_history) > 1000:
            self.detection_history = self.detection_history[-500:]
    
    def get_detection_stats(self) -> Dict[str, Any]:
        """获取检测统计信息"""
        avg_detection_time = sum(self.detection_times) / len(self.detection_times) if self.detection_times else 0
        
        return {
            "total_detections": self.total_detections,
            "successful_detections": self.successful_detections,
            "detection_rate": self.successful_detections / self.total_detections if self.total_detections > 0 else 0,
            "average_detection_time": avg_detection_time,
            "history_count": len(self.detection_history)
        }

