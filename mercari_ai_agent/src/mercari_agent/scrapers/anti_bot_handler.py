"""
反爬虫处理器模块 (增强版)

该模块提供智能反爬虫检测和处理功能。
能够识别常见的反爬虫机制并自动采取应对措施。

主要功能：
- 多层次反爬虫检测算法
- 智能绕过策略选择
- JavaScript引擎集成
- 浏览器自动化支持
- 机器学习检测模型
- Cloudflare专用处理
- 验证码识别接口
- 行为模式分析
- 指纹伪装技术

技术特点：
- 基于规则和机器学习的混合检测
- 动态策略调整
- 多重绕过机制
- 实时学习和适应
- 完整的统计和监控

Author: Mercari AI Agent Team
"""

import asyncio
import logging
import time
import random
import json
import base64
import hashlib
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse
import re
import aiohttp
from bs4 import BeautifulSoup
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import SVC
import pickle
import os

from ..utils.logger import get_logger
from ..config.settings import settings

logger = get_logger(__name__)


class BotDetectionType(Enum):
    """反爬虫检测类型"""
    CAPTCHA = "captcha"
    RATE_LIMIT = "rate_limit"
    IP_BLOCK = "ip_block"
    USER_AGENT_BLOCK = "user_agent_block"
    JAVASCRIPT_CHALLENGE = "js_challenge"
    CLOUDFLARE = "cloudflare"
    FINGERPRINT_DETECTION = "fingerprint_detection"
    BEHAVIOR_ANALYSIS = "behavior_analysis"
    MACHINE_LEARNING = "machine_learning"
    UNKNOWN = "unknown"


class BypassStrategy(Enum):
    """绕过策略"""
    WAIT_AND_RETRY = "wait_and_retry"
    CHANGE_USER_AGENT = "change_user_agent"
    USE_PROXY = "use_proxy"
    ROTATE_SESSION = "rotate_session"
    SOLVE_CAPTCHA = "solve_captcha"
    EXECUTE_JAVASCRIPT = "execute_javascript"
    USE_BROWSER_ENGINE = "use_browser_engine"
    FINGERPRINT_SPOOFING = "fingerprint_spoofing"
    BEHAVIOR_MIMICKING = "behavior_mimicking"
    MANUAL_INTERVENTION = "manual_intervention"


@dataclass
class DetectionPattern:
    """检测模式"""
    pattern: str
    detection_type: BotDetectionType
    confidence: float
    description: str
    bypass_strategy: BypassStrategy
    
    def matches(self, text: str) -> bool:
        """检查是否匹配"""
        return bool(re.search(self.pattern, text, re.IGNORECASE))


@dataclass
class BotDetectionResult:
    """反爬虫检测结果"""
    is_detected: bool
    detection_type: BotDetectionType
    confidence: float
    details: Dict[str, Any]
    suggested_strategy: BypassStrategy
    patterns_matched: List[str] = field(default_factory=list)
    ml_score: Optional[float] = None
    response_analysis: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


@dataclass
class BypassResult:
    """绕过结果"""
    success: bool
    strategy_used: BypassStrategy
    content: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class JavaScriptEngine:
    """JavaScript引擎"""
    
    def __init__(self):
        """初始化JavaScript引擎"""
        self.enabled = self._check_nodejs_available()
        if not self.enabled:
            logger.warning("Node.js not available, JavaScript engine disabled")
    
    def _check_nodejs_available(self) -> bool:
        """检查Node.js是否可用"""
        try:
            import subprocess
            result = subprocess.run(['node', '--version'], capture_output=True, text=True)
            return result.returncode == 0
        except Exception:
            return False
    
    async def execute_challenge(self, challenge_code: str) -> Optional[str]:
        """执行JavaScript挑战"""
        if not self.enabled:
            return None
        
        try:
            import subprocess
            import tempfile
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
                f.write(challenge_code)
                f.flush()
                
                result = subprocess.run(
                    ['node', f.name],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                os.unlink(f.name)
                
                if result.returncode == 0:
                    return result.stdout.strip()
                else:
                    logger.error(f"JavaScript execution failed: {result.stderr}")
                    return None
        
        except Exception as e:
            logger.error(f"JavaScript engine error: {e}")
            return None
    
    def extract_challenge_from_html(self, html: str) -> Optional[str]:
        """从HTML中提取JavaScript挑战"""
        patterns = [
            r'<script[^>]*>(.*?var\s+[a-zA-Z_][a-zA-Z0-9_]*\s*=.*?)</script>',
            r'setTimeout\(function\(\)\s*\{(.*?)\}',
            r'eval\((.*?)\)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            if matches:
                return matches[0]
        
        return None


class BrowserEngine:
    """浏览器引擎"""
    
    def __init__(self):
        """初始化浏览器引擎"""
        self.playwright_available = self._check_playwright_available()
        self.selenium_available = self._check_selenium_available()
        
        if not (self.playwright_available or self.selenium_available):
            logger.warning("No browser engine available")
    
    def _check_playwright_available(self) -> bool:
        """检查Playwright是否可用"""
        try:
            import playwright
            return True
        except ImportError:
            return False
    
    def _check_selenium_available(self) -> bool:
        """检查Selenium是否可用"""
        try:
            from selenium import webdriver
            return True
        except ImportError:
            return False
    
    async def render_page(self, url: str, wait_time: int = 3) -> Optional[str]:
        """渲染页面"""
        if self.playwright_available:
            return await self._render_with_playwright(url, wait_time)
        elif self.selenium_available:
            return await self._render_with_selenium(url, wait_time)
        else:
            logger.error("No browser engine available")
            return None
    
    async def _render_with_playwright(self, url: str, wait_time: int) -> Optional[str]:
        """使用Playwright渲染页面"""
        try:
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                page = await context.new_page()
                
                await page.goto(url)
                await page.wait_for_timeout(wait_time * 1000)
                
                content = await page.content()
                await browser.close()
                
                return content
        
        except Exception as e:
            logger.error(f"Playwright rendering failed: {e}")
            return None
    
    async def _render_with_selenium(self, url: str, wait_time: int) -> Optional[str]:
        """使用Selenium渲染页面"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            driver = webdriver.Chrome(options=options)
            driver.get(url)
            time.sleep(wait_time)
            
            content = driver.page_source
            driver.quit()
            
            return content
        
        except Exception as e:
            logger.error(f"Selenium rendering failed: {e}")
            return None


class MLDetector:
    """机器学习检测器"""
    
    def __init__(self):
        """初始化ML检测器"""
        self.vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        self.classifier = SVC(probability=True, random_state=42)
        self.model_path = os.path.join(settings.DATA_DIR, "bot_detection_model.pkl")
        self.is_trained = False
        
        # 加载预训练模型
        self._load_model()
    
    def _load_model(self):
        """加载预训练模型"""
        try:
            if os.path.exists(self.model_path):
                with open(self.model_path, 'rb') as f:
                    model_data = pickle.load(f)
                    self.vectorizer = model_data['vectorizer']
                    self.classifier = model_data['classifier']
                    self.is_trained = True
                    logger.info("ML detection model loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to load ML model: {e}")
    
    def _save_model(self):
        """保存模型"""
        try:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            with open(self.model_path, 'wb') as f:
                pickle.dump({
                    'vectorizer': self.vectorizer,
                    'classifier': self.classifier
                }, f)
            logger.info("ML detection model saved successfully")
        except Exception as e:
            logger.error(f"Failed to save ML model: {e}")
    
    def extract_features(self, html_content: str, response_headers: Dict[str, str]) -> Dict[str, float]:
        """提取特征"""
        features = {}
        
        # HTML内容特征
        features['html_length'] = len(html_content)
        features['script_count'] = len(re.findall(r'<script', html_content, re.IGNORECASE))
        features['form_count'] = len(re.findall(r'<form', html_content, re.IGNORECASE))
        features['input_count'] = len(re.findall(r'<input', html_content, re.IGNORECASE))
        features['challenge_keywords'] = len(re.findall(r'challenge|verification|captcha', html_content, re.IGNORECASE))
        
        # HTTP头特征
        features['server_cloudflare'] = 1 if 'cloudflare' in response_headers.get('server', '').lower() else 0
        features['has_cf_ray'] = 1 if 'cf-ray' in response_headers else 0
        features['content_encoding'] = 1 if 'content-encoding' in response_headers else 0
        
        # 页面结构特征
        soup = BeautifulSoup(html_content, 'html.parser')
        features['title_length'] = len(soup.title.string) if soup.title else 0
        features['meta_count'] = len(soup.find_all('meta'))
        features['link_count'] = len(soup.find_all('a'))
        
        return features
    
    def predict_bot_detection(self, html_content: str, response_headers: Dict[str, str]) -> float:
        """预测反爬虫检测概率"""
        if not self.is_trained:
            return 0.0
        
        try:
            # 提取特征
            features = self.extract_features(html_content, response_headers)
            
            # 文本向量化
            text_features = self.vectorizer.transform([html_content])
            
            # 结构化特征
            structured_features = np.array(list(features.values())).reshape(1, -1)
            
            # 组合特征
            combined_features = np.hstack([text_features.toarray(), structured_features])
            
            # 预测概率
            probability = self.classifier.predict_proba(combined_features)[0][1]
            
            return probability
        
        except Exception as e:
            logger.error(f"ML prediction failed: {e}")
            return 0.0
    
    def update_model(self, positive_samples: List[str], negative_samples: List[str]):
        """更新模型"""
        try:
            # 准备训练数据
            X = positive_samples + negative_samples
            y = [1] * len(positive_samples) + [0] * len(negative_samples)
            
            # 向量化
            X_vectorized = self.vectorizer.fit_transform(X)
            
            # 训练模型
            self.classifier.fit(X_vectorized, y)
            self.is_trained = True
            
            # 保存模型
            self._save_model()
            
            logger.info(f"ML model updated with {len(X)} samples")
        
        except Exception as e:
            logger.error(f"Model update failed: {e}")


class AntiBotHandler:
    """
    反爬虫处理器类 (增强版)
    
    负责检测和处理各种反爬虫机制。
    提供智能化的绕过策略和恢复机制。
    """
    
    def __init__(self):
        """初始化反爬虫处理器"""
        self.detection_patterns = self._load_detection_patterns()
        self.bypass_strategies = self._load_bypass_strategies()
        self.detection_stats = {}
        self.bypass_success_rate = {}
        
        # 初始化组件
        self.js_engine = JavaScriptEngine()
        self.browser_engine = BrowserEngine()
        self.ml_detector = MLDetector()
        
        # 策略权重
        self.strategy_weights = {
            BypassStrategy.WAIT_AND_RETRY: 0.8,
            BypassStrategy.CHANGE_USER_AGENT: 0.7,
            BypassStrategy.USE_PROXY: 0.6,
            BypassStrategy.ROTATE_SESSION: 0.5,
            BypassStrategy.EXECUTE_JAVASCRIPT: 0.4,
            BypassStrategy.USE_BROWSER_ENGINE: 0.3,
            BypassStrategy.FINGERPRINT_SPOOFING: 0.2,
            BypassStrategy.BEHAVIOR_MIMICKING: 0.1
        }
        
        # 学习参数
        self.learning_rate = 0.1
        self.adaptation_threshold = 0.6
        
        logger.info("Enhanced AntiBotHandler initialized")
    
    def is_blocked(self, content: str, response: Optional[aiohttp.ClientResponse] = None) -> bool:
        """
        检查是否被反爬虫拦截
        
        Args:
            content: 页面内容
            response: HTTP响应对象
            
        Returns:
            bool: 是否被拦截
        """
        detection_result = self.detect_bot_protection(content, response)
        return detection_result.is_detected
    
    def detect_bot_protection(
        self,
        content: str,
        response: Optional[aiohttp.ClientResponse] = None
    ) -> BotDetectionResult:
        """
        检测反爬虫保护 (增强版)
        
        Args:
            content: 页面内容
            response: HTTP响应对象
            
        Returns:
            BotDetectionResult: 检测结果
        """
        detection_results = []
        
        # 1. 基于规则的检测
        rule_result = self._rule_based_detection(content, response)
        detection_results.append(rule_result)
        
        # 2. 机器学习检测
        ml_result = self._ml_based_detection(content, response)
        detection_results.append(ml_result)
        
        # 3. 行为分析检测
        behavior_result = self._behavior_analysis_detection(content, response)
        detection_results.append(behavior_result)
        
        # 4. 指纹检测
        fingerprint_result = self._fingerprint_detection(content, response)
        detection_results.append(fingerprint_result)
        
        # 融合结果
        final_result = self._fuse_detection_results(detection_results)
        
        # 更新统计
        self._update_detection_stats(final_result)
        
        return final_result
    
    def _rule_based_detection(
        self,
        content: str,
        response: Optional[aiohttp.ClientResponse] = None
    ) -> BotDetectionResult:
        """基于规则的检测"""
        matched_patterns = []
        max_confidence = 0.0
        detected_type = BotDetectionType.UNKNOWN
        suggested_strategy = BypassStrategy.WAIT_AND_RETRY
        
        # 检查HTTP状态码
        if response:
            status_result = self._check_status_code(response)
            if status_result.is_detected:
                return status_result
        
        # 检查内容模式
        for pattern in self.detection_patterns:
            if pattern.matches(content):
                matched_patterns.append(pattern.pattern)
                if pattern.confidence > max_confidence:
                    max_confidence = pattern.confidence
                    detected_type = pattern.detection_type
                    suggested_strategy = pattern.bypass_strategy
        
        is_detected = len(matched_patterns) > 0
        
        return BotDetectionResult(
            is_detected=is_detected,
            detection_type=detected_type,
            confidence=max_confidence,
            details={"matched_patterns": matched_patterns},
            suggested_strategy=suggested_strategy,
            patterns_matched=matched_patterns
        )
    
    def _ml_based_detection(
        self,
        content: str,
        response: Optional[aiohttp.ClientResponse] = None
    ) -> BotDetectionResult:
        """基于机器学习的检测"""
        if not response:
            return BotDetectionResult(
                is_detected=False,
                detection_type=BotDetectionType.UNKNOWN,
                confidence=0.0,
                details={},
                suggested_strategy=BypassStrategy.WAIT_AND_RETRY
            )
        
        # 提取响应头
        headers = dict(response.headers)
        
        # ML预测
        ml_score = self.ml_detector.predict_bot_detection(content, headers)
        
        is_detected = ml_score > 0.7
        
        return BotDetectionResult(
            is_detected=is_detected,
            detection_type=BotDetectionType.MACHINE_LEARNING,
            confidence=ml_score,
            details={"ml_score": ml_score},
            suggested_strategy=BypassStrategy.USE_BROWSER_ENGINE,
            ml_score=ml_score
        )
    
    def _behavior_analysis_detection(
        self,
        content: str,
        response: Optional[aiohttp.ClientResponse] = None
    ) -> BotDetectionResult:
        """行为分析检测"""
        # 分析页面加载时间
        load_time_suspicious = False
        if response:
            # 检查响应时间模式
            response_time = getattr(response, '_response_time', 0)
            if response_time < 0.1:  # 太快可能是缓存或重定向
                load_time_suspicious = True
        
        # 分析页面内容复杂度
        complexity_score = self._calculate_content_complexity(content)
        
        # 检查JavaScript挑战
        js_challenge_detected = self._detect_js_challenge(content)
        
        is_detected = load_time_suspicious or js_challenge_detected or complexity_score < 0.3
        confidence = 0.6 if is_detected else 0.1
        
        return BotDetectionResult(
            is_detected=is_detected,
            detection_type=BotDetectionType.BEHAVIOR_ANALYSIS,
            confidence=confidence,
            details={
                "load_time_suspicious": load_time_suspicious,
                "complexity_score": complexity_score,
                "js_challenge_detected": js_challenge_detected
            },
            suggested_strategy=BypassStrategy.BEHAVIOR_MIMICKING
        )
    
    def _fingerprint_detection(
        self,
        content: str,
        response: Optional[aiohttp.ClientResponse] = None
    ) -> BotDetectionResult:
        """指纹检测"""
        fingerprint_scripts = [
            'canvas fingerprint',
            'webgl fingerprint',
            'audio fingerprint',
            'font fingerprint',
            'screen fingerprint'
        ]
        
        detected_fingerprints = []
        for script in fingerprint_scripts:
            if script in content.lower():
                detected_fingerprints.append(script)
        
        is_detected = len(detected_fingerprints) > 0
        confidence = len(detected_fingerprints) * 0.2
        
        return BotDetectionResult(
            is_detected=is_detected,
            detection_type=BotDetectionType.FINGERPRINT_DETECTION,
            confidence=min(confidence, 1.0),
            details={"detected_fingerprints": detected_fingerprints},
            suggested_strategy=BypassStrategy.FINGERPRINT_SPOOFING
        )
    
    def _fuse_detection_results(self, results: List[BotDetectionResult]) -> BotDetectionResult:
        """融合检测结果"""
        if not results:
            return BotDetectionResult(
                is_detected=False,
                detection_type=BotDetectionType.UNKNOWN,
                confidence=0.0,
                details={},
                suggested_strategy=BypassStrategy.WAIT_AND_RETRY
            )
        
        # 计算加权平均置信度
        total_confidence = 0.0
        weights = [1.0, 0.8, 0.6, 0.4]  # 不同检测方法的权重
        
        for i, result in enumerate(results):
            if result.is_detected:
                weight = weights[i] if i < len(weights) else 0.2
                total_confidence += result.confidence * weight
        
        # 选择最高置信度的检测类型
        best_result = max(results, key=lambda x: x.confidence if x.is_detected else 0)
        
        is_detected = total_confidence > 0.5
        
        return BotDetectionResult(
            is_detected=is_detected,
            detection_type=best_result.detection_type,
            confidence=min(total_confidence, 1.0),
            details={"fusion_results": [r.details for r in results]},
            suggested_strategy=best_result.suggested_strategy,
            patterns_matched=best_result.patterns_matched,
            ml_score=best_result.ml_score
        )
    
    async def handle_block(
        self,
        session: aiohttp.ClientSession,
        url: str,
        detection_result: Optional[BotDetectionResult] = None
    ) -> str:
        """
        处理反爬虫拦截 (增强版)
        
        Args:
            session: HTTP会话
            url: 目标URL
            detection_result: 检测结果
            
        Returns:
            str: 处理后的页面内容
        """
        if not detection_result:
            # 重新检测
            response = await session.get(url)
            content = await response.text()
            detection_result = self.detect_bot_protection(content, response)
        
        # 选择最佳策略
        strategy = self._select_best_strategy(detection_result)
        
        # 执行绕过策略
        bypass_result = await self._execute_bypass_strategy(
            session, url, strategy, detection_result
        )
        
        # 更新策略权重
        self._update_strategy_weights(strategy, bypass_result.success)
        
        if bypass_result.success:
            return bypass_result.content
        else:
            raise AntiBotError(f"Failed to bypass protection: {bypass_result.error_message}")
    
    def _select_best_strategy(self, detection_result: BotDetectionResult) -> BypassStrategy:
        """选择最佳绕过策略"""
        # 基于检测结果的建议策略
        suggested_strategy = detection_result.suggested_strategy
        
        # 考虑策略权重
        strategy_score = self.strategy_weights.get(suggested_strategy, 0.5)
        
        # 考虑历史成功率
        historical_success = self.bypass_success_rate.get(detection_result.detection_type, {})
        strategy_key = suggested_strategy.value if hasattr(suggested_strategy, 'value') else str(suggested_strategy)
        if strategy_key in historical_success:
            historical_score = historical_success[strategy_key]
            strategy_score = strategy_score * 0.7 + historical_score * 0.3
        
        # 如果策略得分太低，选择备用策略
        if strategy_score < self.adaptation_threshold:
            backup_strategies = [
                BypassStrategy.USE_BROWSER_ENGINE,
                BypassStrategy.WAIT_AND_RETRY,
                BypassStrategy.CHANGE_USER_AGENT
            ]
            
            for backup in backup_strategies:
                if self.strategy_weights.get(backup, 0) > strategy_score:
                    return backup
        
        return suggested_strategy
    
    async def _execute_bypass_strategy(
        self,
        session: aiohttp.ClientSession,
        url: str,
        strategy: BypassStrategy,
        detection_result: BotDetectionResult
    ) -> BypassResult:
        """执行绕过策略"""
        start_time = time.time()
        
        try:
            if strategy == BypassStrategy.WAIT_AND_RETRY:
                return await self._strategy_wait_and_retry(session, url)
            
            elif strategy == BypassStrategy.CHANGE_USER_AGENT:
                return await self._strategy_change_user_agent(session, url)
            
            elif strategy == BypassStrategy.USE_PROXY:
                return await self._strategy_use_proxy(session, url)
            
            elif strategy == BypassStrategy.ROTATE_SESSION:
                return await self._strategy_rotate_session(session, url)
            
            elif strategy == BypassStrategy.EXECUTE_JAVASCRIPT:
                return await self._strategy_execute_javascript(session, url, detection_result)
            
            elif strategy == BypassStrategy.USE_BROWSER_ENGINE:
                return await self._strategy_use_browser_engine(url)
            
            elif strategy == BypassStrategy.FINGERPRINT_SPOOFING:
                return await self._strategy_fingerprint_spoofing(session, url)
            
            elif strategy == BypassStrategy.BEHAVIOR_MIMICKING:
                return await self._strategy_behavior_mimicking(session, url)
            
            else:
                return BypassResult(
                    success=False,
                    strategy_used=strategy,
                    error_message=f"Unsupported strategy: {strategy}"
                )
        
        except Exception as e:
            return BypassResult(
                success=False,
                strategy_used=strategy,
                error_message=str(e),
                execution_time=time.time() - start_time
            )
    
    async def _strategy_wait_and_retry(self, session: aiohttp.ClientSession, url: str) -> BypassResult:
        """等待重试策略"""
        wait_time = random.uniform(5, 15)
        await asyncio.sleep(wait_time)
        
        response = await session.get(url)
        content = await response.text()
        
        return BypassResult(
            success=True,
            strategy_used=BypassStrategy.WAIT_AND_RETRY,
            content=content,
            metadata={"wait_time": wait_time}
        )
    
    async def _strategy_change_user_agent(self, session: aiohttp.ClientSession, url: str) -> BypassResult:
        """更换User-Agent策略"""
        headers = self._get_random_headers()
        
        response = await session.get(url, headers=headers)
        content = await response.text()
        
        return BypassResult(
            success=True,
            strategy_used=BypassStrategy.CHANGE_USER_AGENT,
            content=content,
            metadata={"headers": headers}
        )
    
    async def _strategy_use_proxy(self, session: aiohttp.ClientSession, url: str) -> BypassResult:
        """使用代理策略"""
        proxy = self._get_random_proxy()
        
        if not proxy:
            return BypassResult(
                success=False,
                strategy_used=BypassStrategy.USE_PROXY,
                error_message="No proxy available"
            )
        
        response = await session.get(url, proxy=proxy)
        content = await response.text()
        
        return BypassResult(
            success=True,
            strategy_used=BypassStrategy.USE_PROXY,
            content=content,
            metadata={"proxy": proxy}
        )
    
    async def _strategy_rotate_session(self, session: aiohttp.ClientSession, url: str) -> BypassResult:
        """轮换会话策略"""
        # 创建新会话
        new_session = aiohttp.ClientSession()
        
        try:
            headers = self._get_random_headers()
            response = await new_session.get(url, headers=headers)
            content = await response.text()
            
            return BypassResult(
                success=True,
                strategy_used=BypassStrategy.ROTATE_SESSION,
                content=content,
                metadata={"new_session": True}
            )
        
        finally:
            await new_session.close()
    
    async def _strategy_execute_javascript(
        self,
        session: aiohttp.ClientSession,
        url: str,
        detection_result: BotDetectionResult
    ) -> BypassResult:
        """执行JavaScript策略"""
        # 先获取页面内容
        response = await session.get(url)
        content = await response.text()
        
        # 提取JavaScript挑战
        challenge_code = self.js_engine.extract_challenge_from_html(content)
        
        if not challenge_code:
            return BypassResult(
                success=False,
                strategy_used=BypassStrategy.EXECUTE_JAVASCRIPT,
                error_message="No JavaScript challenge found"
            )
        
        # 执行挑战
        result = await self.js_engine.execute_challenge(challenge_code)
        
        if result:
            # 使用结果重新请求
            headers = self._get_browser_headers()
            headers['X-Challenge-Result'] = result
            
            response = await session.get(url, headers=headers)
            content = await response.text()
            
            return BypassResult(
                success=True,
                strategy_used=BypassStrategy.EXECUTE_JAVASCRIPT,
                content=content,
                metadata={"challenge_result": result}
            )
        else:
            return BypassResult(
                success=False,
                strategy_used=BypassStrategy.EXECUTE_JAVASCRIPT,
                error_message="JavaScript challenge execution failed"
            )
    
    async def _strategy_use_browser_engine(self, url: str) -> BypassResult:
        """使用浏览器引擎策略"""
        content = await self.browser_engine.render_page(url)
        
        if content:
            return BypassResult(
                success=True,
                strategy_used=BypassStrategy.USE_BROWSER_ENGINE,
                content=content,
                metadata={"browser_engine": True}
            )
        else:
            return BypassResult(
                success=False,
                strategy_used=BypassStrategy.USE_BROWSER_ENGINE,
                error_message="Browser engine rendering failed"
            )
    
    async def _strategy_fingerprint_spoofing(self, session: aiohttp.ClientSession, url: str) -> BypassResult:
        """指纹伪装策略"""
        # 生成伪装的指纹信息
        spoofed_headers = self._generate_spoofed_headers()
        
        response = await session.get(url, headers=spoofed_headers)
        content = await response.text()
        
        return BypassResult(
            success=True,
            strategy_used=BypassStrategy.FINGERPRINT_SPOOFING,
            content=content,
            metadata={"spoofed_headers": spoofed_headers}
        )
    
    async def _strategy_behavior_mimicking(self, session: aiohttp.ClientSession, url: str) -> BypassResult:
        """行为模拟策略"""
        # 模拟真实用户行为
        headers = self._get_browser_headers()
        
        # 添加随机延迟
        await asyncio.sleep(random.uniform(1, 3))
        
        # 模拟多步骤访问
        response = await session.get(url, headers=headers)
        content = await response.text()
        
        return BypassResult(
            success=True,
            strategy_used=BypassStrategy.BEHAVIOR_MIMICKING,
            content=content,
            metadata={"behavior_mimicking": True}
        )
    
    def _load_detection_patterns(self) -> List[DetectionPattern]:
        """加载检测模式"""
        patterns = [
            # Captcha patterns
            DetectionPattern(
                pattern=r'captcha|recaptcha|hcaptcha',
                detection_type=BotDetectionType.CAPTCHA,
                confidence=0.9,
                description="CAPTCHA challenge detected",
                bypass_strategy=BypassStrategy.SOLVE_CAPTCHA
            ),
            
            # Rate limiting patterns
            DetectionPattern(
                pattern=r'too many requests|rate limit|slow down',
                detection_type=BotDetectionType.RATE_LIMIT,
                confidence=0.85,
                description="Rate limiting detected",
                bypass_strategy=BypassStrategy.WAIT_AND_RETRY
            ),
            
            # IP blocking patterns
            DetectionPattern(
                pattern=r'access denied|blocked|forbidden|your ip',
                detection_type=BotDetectionType.IP_BLOCK,
                confidence=0.8,
                description="IP blocking detected",
                bypass_strategy=BypassStrategy.USE_PROXY
            ),
            
            # JavaScript challenge patterns
            DetectionPattern(
                pattern=r'javascript.*required|enable.*javascript|browser.*verification',
                detection_type=BotDetectionType.JAVASCRIPT_CHALLENGE,
                confidence=0.75,
                description="JavaScript challenge detected",
                bypass_strategy=BypassStrategy.EXECUTE_JAVASCRIPT
            ),
            
            # Cloudflare patterns
            DetectionPattern(
                pattern=r'cloudflare|cf-ray|checking.*security|ddos protection',
                detection_type=BotDetectionType.CLOUDFLARE,
                confidence=0.9,
                description="Cloudflare protection detected",
                bypass_strategy=BypassStrategy.USE_BROWSER_ENGINE
            ),
            
            # User agent blocking patterns
            DetectionPattern(
                pattern=r'invalid.*browser|unsupported.*browser|browser.*required',
                detection_type=BotDetectionType.USER_AGENT_BLOCK,
                confidence=0.7,
                description="User agent blocking detected",
                bypass_strategy=BypassStrategy.CHANGE_USER_AGENT
            )
        ]
        
        return patterns
    
    def _load_bypass_strategies(self) -> Dict[BotDetectionType, List[BypassStrategy]]:
        """加载绕过策略映射"""
        return {
            BotDetectionType.CAPTCHA: [
                BypassStrategy.SOLVE_CAPTCHA,
                BypassStrategy.USE_BROWSER_ENGINE,
                BypassStrategy.MANUAL_INTERVENTION
            ],
            BotDetectionType.RATE_LIMIT: [
                BypassStrategy.WAIT_AND_RETRY,
                BypassStrategy.USE_PROXY,
                BypassStrategy.ROTATE_SESSION
            ],
            BotDetectionType.IP_BLOCK: [
                BypassStrategy.USE_PROXY,
                BypassStrategy.ROTATE_SESSION
            ],
            BotDetectionType.JAVASCRIPT_CHALLENGE: [
                BypassStrategy.EXECUTE_JAVASCRIPT,
                BypassStrategy.USE_BROWSER_ENGINE
            ],
            BotDetectionType.CLOUDFLARE: [
                BypassStrategy.USE_BROWSER_ENGINE,
                BypassStrategy.WAIT_AND_RETRY
            ],
            BotDetectionType.USER_AGENT_BLOCK: [
                BypassStrategy.CHANGE_USER_AGENT,
                BypassStrategy.FINGERPRINT_SPOOFING
            ],
            BotDetectionType.FINGERPRINT_DETECTION: [
                BypassStrategy.FINGERPRINT_SPOOFING,
                BypassStrategy.USE_BROWSER_ENGINE
            ],
            BotDetectionType.BEHAVIOR_ANALYSIS: [
                BypassStrategy.BEHAVIOR_MIMICKING,
                BypassStrategy.USE_BROWSER_ENGINE
            ]
        }
    
    def _check_status_code(self, response: aiohttp.ClientResponse) -> BotDetectionResult:
        """检查HTTP状态码"""
        if response.status == 403:
            return BotDetectionResult(
                is_detected=True,
                detection_type=BotDetectionType.IP_BLOCK,
                confidence=0.8,
                details={"status_code": response.status},
                suggested_strategy=BypassStrategy.USE_PROXY
            )
        elif response.status == 429:
            return BotDetectionResult(
                is_detected=True,
                detection_type=BotDetectionType.RATE_LIMIT,
                confidence=0.9,
                details={"status_code": response.status},
                suggested_strategy=BypassStrategy.WAIT_AND_RETRY
            )
        elif response.status in [503, 504]:
            return BotDetectionResult(
                is_detected=True,
                detection_type=BotDetectionType.CLOUDFLARE,
                confidence=0.7,
                details={"status_code": response.status},
                suggested_strategy=BypassStrategy.USE_BROWSER_ENGINE
            )
        
        return BotDetectionResult(
            is_detected=False,
            detection_type=BotDetectionType.UNKNOWN,
            confidence=0.0,
            details={},
            suggested_strategy=BypassStrategy.WAIT_AND_RETRY
        )
    
    def _calculate_content_complexity(self, content: str) -> float:
        """计算内容复杂度"""
        if not content:
            return 0.0
        
        # 基本指标
        word_count = len(content.split())
        char_count = len(content)
        
        if char_count == 0:
            return 0.0
        
        # HTML标签数量
        html_tags = len(re.findall(r'<[^>]+>', content))
        
        # JavaScript代码量
        js_code = len(re.findall(r'<script[^>]*>.*?</script>', content, re.DOTALL))
        
        # CSS代码量
        css_code = len(re.findall(r'<style[^>]*>.*?</style>', content, re.DOTALL))
        
        # 计算复杂度分数
        complexity = (
            min(word_count / 1000, 1.0) * 0.3 +
            min(html_tags / 100, 1.0) * 0.3 +
            min(js_code / 10, 1.0) * 0.2 +
            min(css_code / 10, 1.0) * 0.2
        )
        
        return complexity
    
    def _detect_js_challenge(self, content: str) -> bool:
        """检测JavaScript挑战"""
        challenge_patterns = [
            r'var\s+[a-zA-Z_][a-zA-Z0-9_]*\s*=\s*\d+',
            r'setTimeout\(function\(\)',
            r'eval\(',
            r'document\.cookie\s*=',
            r'window\.location\.href\s*='
        ]
        
        for pattern in challenge_patterns:
            if re.search(pattern, content):
                return True
        
        return False
    
    def _get_random_headers(self) -> Dict[str, str]:
        """获取随机请求头"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0"
        ]
        
        return {
            "User-Agent": random.choice(user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0"
        }
    
    def _get_browser_headers(self) -> Dict[str, str]:
        """获取浏览器头部"""
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "DNT": "1"
        }
    
    def _generate_spoofed_headers(self) -> Dict[str, str]:
        """生成伪装头部"""
        base_headers = self._get_browser_headers()
        
        # 添加伪装的指纹信息
        spoofed_headers = base_headers.copy()
        spoofed_headers.update({
            "X-Forwarded-For": f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}",
            "X-Real-IP": f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://jp.mercari.com",
            "Referer": "https://jp.mercari.com/"
        })
        
        return spoofed_headers
    
    def _get_random_proxy(self) -> Optional[str]:
        """获取随机代理"""
        if hasattr(settings, 'PROXY_LIST') and settings.PROXY_LIST:
            return random.choice(settings.PROXY_LIST)
        return None
    
    def _update_strategy_weights(self, strategy: BypassStrategy, success: bool):
        """更新策略权重"""
        current_weight = self.strategy_weights.get(strategy, 0.5)
        
        if success:
            # 增加权重
            new_weight = min(1.0, current_weight + self.learning_rate)
        else:
            # 减少权重
            new_weight = max(0.0, current_weight - self.learning_rate)
        
        self.strategy_weights[strategy] = new_weight
    
    def _update_detection_stats(self, detection_result: BotDetectionResult):
        """更新检测统计"""
        detection_type = detection_result.detection_type
        
        if detection_type not in self.detection_stats:
            self.detection_stats[detection_type] = {"total": 0, "detected": 0}
        
        self.detection_stats[detection_type]["total"] += 1
        if detection_result.is_detected:
            self.detection_stats[detection_type]["detected"] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "detection_stats": {
                str(k): v for k, v in self.detection_stats.items()
            },
            "bypass_success_rate": {
                str(k): v for k, v in self.bypass_success_rate.items()
            },
            "strategy_weights": {
                str(k): v for k, v in self.strategy_weights.items()
            },
            "components": {
                "js_engine_enabled": self.js_engine.enabled,
                "browser_engine_available": self.browser_engine.playwright_available or self.browser_engine.selenium_available,
                "ml_model_trained": self.ml_detector.is_trained
            }
        }
    
    def reset_stats(self):
        """重置统计信息"""
        self.detection_stats.clear()
        self.bypass_success_rate.clear()
        logger.info("反爬虫统计信息已重置")
    
    async def train_ml_model(self, training_data: List[Tuple[str, bool]]):
        """训练机器学习模型"""
        positive_samples = [sample for sample, label in training_data if label]
        negative_samples = [sample for sample, label in training_data if not label]
        
        self.ml_detector.update_model(positive_samples, negative_samples)
        logger.info(f"ML model trained with {len(training_data)} samples")


class AntiBotError(Exception):
    """反爬虫处理异常"""
    pass