"""
反爬虫处理系统测试

该模块包含反爬虫处理系统的单元测试。
测试反爬虫检测、绕过策略、机器学习检测等功能。

Author: Mercari AI Agent Team
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from mercari_agent.scrapers.anti_bot_handler import (
    AntiBotHandler, BotDetectionResult, BotDetectionType, 
    BypassStrategy, MLBotDetector, JavaScriptEngine, 
    BrowserAutomation, FingerprintSpoofer, BehaviorMimicker,
    detect_bot_protection, is_captcha_page, bypass_cloudflare
)


class TestBotDetectionResult:
    """反爬虫检测结果测试"""
    
    def test_bot_detection_result_init(self):
        """测试反爬虫检测结果初始化"""
        result = BotDetectionResult(
            is_detected=True,
            detection_type=BotDetectionType.CAPTCHA,
            confidence=0.95,
            details={"captcha_type": "recaptcha"}
        )
        
        assert result.is_detected is True
        assert result.detection_type == BotDetectionType.CAPTCHA
        assert result.confidence == 0.95
        assert result.details["captcha_type"] == "recaptcha"
        assert result.timestamp is not None
        assert result.bypass_strategy is None
    
    def test_bot_detection_result_no_detection(self):
        """测试未检测到反爬虫"""
        result = BotDetectionResult(
            is_detected=False,
            detection_type=BotDetectionType.NONE,
            confidence=0.1
        )
        
        assert result.is_detected is False
        assert result.detection_type == BotDetectionType.NONE
        assert result.confidence == 0.1
        assert result.details == {}


class TestMLBotDetector:
    """机器学习反爬虫检测器测试"""
    
    def test_ml_bot_detector_init(self):
        """测试机器学习检测器初始化"""
        detector = MLBotDetector()
        
        assert detector.model is not None
        assert detector.vectorizer is not None
        assert detector.is_trained is False
        assert detector.detection_threshold == 0.7
    
    def test_extract_features(self):
        """测试特征提取"""
        detector = MLBotDetector()
        
        html = """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <div class="content">Regular content</div>
                <script>alert('test');</script>
            </body>
        </html>
        """
        
        features = detector._extract_features(html, "https://example.com")
        
        assert "html_length" in features
        assert "script_count" in features
        assert "link_count" in features
        assert "form_count" in features
        assert "meta_count" in features
        assert "has_captcha_keywords" in features
        assert "has_cloudflare_keywords" in features
        assert "response_time" in features
        
        assert features["html_length"] > 0
        assert features["script_count"] >= 1
        assert features["has_captcha_keywords"] is False
        assert features["has_cloudflare_keywords"] is False
    
    def test_extract_features_with_captcha(self):
        """测试包含CAPTCHA的特征提取"""
        detector = MLBotDetector()
        
        html = """
        <html>
            <body>
                <div class="g-recaptcha">reCAPTCHA</div>
                <form>
                    <input type="text" name="captcha">
                </form>
            </body>
        </html>
        """
        
        features = detector._extract_features(html, "https://example.com")
        
        assert features["has_captcha_keywords"] is True
        assert features["form_count"] >= 1
    
    def test_extract_features_with_cloudflare(self):
        """测试包含Cloudflare的特征提取"""
        detector = MLBotDetector()
        
        html = """
        <html>
            <body>
                <div>Checking your browser before accessing...</div>
                <div class="cf-browser-verification">Cloudflare</div>
            </body>
        </html>
        """
        
        features = detector._extract_features(html, "https://example.com")
        
        assert features["has_cloudflare_keywords"] is True
    
    def test_train_model(self):
        """测试训练模型"""
        detector = MLBotDetector()
        
        # 准备训练数据
        training_data = [
            ("Normal page content", False),
            ("Regular website with content", False),
            ("Please complete the CAPTCHA", True),
            ("Cloudflare browser verification", True),
            ("You are being rate limited", True),
            ("Access denied", True),
            ("Normal product listing", False),
            ("Search results page", False)
        ]
        
        detector.train_model(training_data)
        
        assert detector.is_trained is True
        assert detector.model is not None
        assert detector.vectorizer is not None
    
    def test_predict_bot_detection(self):
        """测试预测反爬虫检测"""
        detector = MLBotDetector()
        
        # 训练模型
        training_data = [
            ("Normal page content", False),
            ("Please complete the CAPTCHA", True),
            ("Cloudflare browser verification", True),
            ("Regular website content", False)
        ]
        detector.train_model(training_data)
        
        # 测试预测
        html_normal = "<html><body>Normal content</body></html>"
        html_captcha = "<html><body>Please complete the CAPTCHA</body></html>"
        
        result_normal = detector.predict_bot_detection(html_normal, "https://example.com")
        result_captcha = detector.predict_bot_detection(html_captcha, "https://example.com")
        
        assert result_normal.is_detected is False
        assert result_captcha.is_detected is True
    
    def test_predict_bot_detection_untrained(self):
        """测试未训练模型的预测"""
        detector = MLBotDetector()
        
        html = "<html><body>Test content</body></html>"
        
        result = detector.predict_bot_detection(html, "https://example.com")
        
        assert result.is_detected is False
        assert result.detection_type == BotDetectionType.NONE
        assert result.confidence == 0.0
    
    def test_update_model(self):
        """测试更新模型"""
        detector = MLBotDetector()
        
        # 初始训练
        initial_data = [
            ("Normal content", False),
            ("CAPTCHA detected", True)
        ]
        detector.train_model(initial_data)
        
        # 更新模型
        new_data = [
            ("Rate limit exceeded", True),
            ("Product listing", False)
        ]
        detector.update_model(new_data)
        
        assert detector.is_trained is True
    
    def test_get_model_stats(self):
        """测试获取模型统计"""
        detector = MLBotDetector()
        
        # 训练模型
        training_data = [
            ("Normal content", False),
            ("CAPTCHA page", True),
            ("Cloudflare check", True),
            ("Regular page", False)
        ]
        detector.train_model(training_data)
        
        stats = detector.get_model_stats()
        
        assert "is_trained" in stats
        assert "training_samples" in stats
        assert "feature_count" in stats
        assert "detection_threshold" in stats
        
        assert stats["is_trained"] is True
        assert stats["training_samples"] == 4
        assert stats["detection_threshold"] == 0.7


class TestJavaScriptEngine:
    """JavaScript引擎测试"""
    
    def test_javascript_engine_init(self):
        """测试JavaScript引擎初始化"""
        engine = JavaScriptEngine()
        
        assert engine.context is not None
        assert engine.timeout == 10
        assert engine.max_memory == 64 * 1024 * 1024  # 64MB
    
    def test_execute_script(self):
        """测试执行JavaScript"""
        engine = JavaScriptEngine()
        
        # 简单计算
        result = engine.execute_script("2 + 3")
        assert result == 5
        
        # 字符串操作
        result = engine.execute_script("'hello' + ' world'")
        assert result == "hello world"
        
        # 对象操作
        result = engine.execute_script("({name: 'test', value: 42}).value")
        assert result == 42
    
    def test_execute_script_with_timeout(self):
        """测试执行超时的JavaScript"""
        engine = JavaScriptEngine(timeout=1)
        
        # 无限循环应该超时
        with pytest.raises(Exception):
            engine.execute_script("while(true) {}")
    
    def test_execute_script_with_error(self):
        """测试执行错误的JavaScript"""
        engine = JavaScriptEngine()
        
        # 语法错误
        with pytest.raises(Exception):
            engine.execute_script("invalid javascript syntax")
        
        # 运行时错误
        with pytest.raises(Exception):
            engine.execute_script("throw new Error('test error')")
    
    def test_solve_math_challenge(self):
        """测试解决数学挑战"""
        engine = JavaScriptEngine()
        
        # 简单数学挑战
        challenge = "Math.pow(2, 3) + Math.floor(9.7)"
        result = engine.solve_math_challenge(challenge)
        assert result == 17  # 2^3 + floor(9.7) = 8 + 9 = 17
    
    def test_evaluate_protection_script(self):
        """测试评估保护脚本"""
        engine = JavaScriptEngine()
        
        # 模拟保护脚本
        script = """
        function checkBrowser() {
            return navigator.userAgent.indexOf('Chrome') !== -1;
        }
        checkBrowser();
        """
        
        result = engine.evaluate_protection_script(script)
        assert isinstance(result, bool)
    
    def test_extract_dynamic_content(self):
        """测试提取动态内容"""
        engine = JavaScriptEngine()
        
        # 模拟动态内容生成
        script = """
        var content = {
            title: 'Dynamic Title',
            price: 5000,
            items: ['item1', 'item2', 'item3']
        };
        JSON.stringify(content);
        """
        
        result = engine.extract_dynamic_content(script)
        assert "Dynamic Title" in result
        assert "5000" in result
    
    def test_bypass_js_protection(self):
        """测试绕过JavaScript保护"""
        engine = JavaScriptEngine()
        
        # 模拟简单的JavaScript保护
        protection_script = """
        var result = '';
        for (var i = 0; i < 5; i++) {
            result += String.fromCharCode(65 + i);
        }
        result;
        """
        
        result = engine.bypass_js_protection(protection_script)
        assert result == "ABCDE"
    
    def test_cleanup(self):
        """测试清理资源"""
        engine = JavaScriptEngine()
        
        # 执行一些脚本
        engine.execute_script("var test = 'cleanup test'")
        
        # 清理
        engine.cleanup()
        
        # 验证清理后的状态
        assert engine.context is None


class TestBrowserAutomation:
    """浏览器自动化测试"""
    
    def test_browser_automation_init(self):
        """测试浏览器自动化初始化"""
        automation = BrowserAutomation()
        
        assert automation.browser is None
        assert automation.page is None
        assert automation.headless is True
        assert automation.timeout == 30
    
    @pytest.mark.asyncio
    async def test_initialize_browser(self):
        """测试初始化浏览器"""
        automation = BrowserAutomation()
        
        with patch('playwright.async_api.async_playwright') as mock_playwright:
            mock_context = AsyncMock()
            mock_browser = AsyncMock()
            mock_page = AsyncMock()
            
            mock_playwright.return_value.__aenter__.return_value = mock_context
            mock_context.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page
            
            await automation.initialize_browser()
            
            assert automation.browser is not None
            assert automation.page is not None
            mock_context.chromium.launch.assert_called_once()
            mock_browser.new_page.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_navigate_to_page(self):
        """测试导航到页面"""
        automation = BrowserAutomation()
        
        # 模拟页面
        mock_page = AsyncMock()
        mock_page.goto.return_value = None
        mock_page.content.return_value = "<html><body>Test</body></html>"
        automation.page = mock_page
        
        content = await automation.navigate_to_page("https://example.com")
        
        assert content == "<html><body>Test</body></html>"
        mock_page.goto.assert_called_once_with("https://example.com", timeout=30000)
    
    @pytest.mark.asyncio
    async def test_solve_captcha(self):
        """测试解决CAPTCHA"""
        automation = BrowserAutomation()
        
        # 模拟页面
        mock_page = AsyncMock()
        mock_page.wait_for_selector.return_value = None
        mock_page.click.return_value = None
        mock_page.fill.return_value = None
        mock_page.content.return_value = "<html><body>Success</body></html>"
        automation.page = mock_page
        
        result = await automation.solve_captcha("text", "test_answer")
        
        assert result == "<html><body>Success</body></html>"
        mock_page.wait_for_selector.assert_called()
        mock_page.fill.assert_called()
    
    @pytest.mark.asyncio
    async def test_handle_cloudflare_challenge(self):
        """测试处理Cloudflare挑战"""
        automation = BrowserAutomation()
        
        # 模拟页面
        mock_page = AsyncMock()
        mock_page.wait_for_selector.return_value = None
        mock_page.wait_for_load_state.return_value = None
        mock_page.content.return_value = "<html><body>Bypassed</body></html>"
        automation.page = mock_page
        
        result = await automation.handle_cloudflare_challenge()
        
        assert result == "<html><body>Bypassed</body></html>"
        mock_page.wait_for_load_state.assert_called()
    
    @pytest.mark.asyncio
    async def test_wait_for_element(self):
        """测试等待元素"""
        automation = BrowserAutomation()
        
        # 模拟页面
        mock_page = AsyncMock()
        mock_element = AsyncMock()
        mock_page.wait_for_selector.return_value = mock_element
        automation.page = mock_page
        
        element = await automation.wait_for_element(".test-selector")
        
        assert element == mock_element
        mock_page.wait_for_selector.assert_called_once_with(".test-selector", timeout=30000)
    
    @pytest.mark.asyncio
    async def test_close_browser(self):
        """测试关闭浏览器"""
        automation = BrowserAutomation()
        
        # 模拟浏览器
        mock_browser = AsyncMock()
        mock_browser.close.return_value = None
        automation.browser = mock_browser
        
        await automation.close_browser()
        
        mock_browser.close.assert_called_once()
        assert automation.browser is None
        assert automation.page is None


class TestFingerprintSpoofer:
    """指纹伪造器测试"""
    
    def test_fingerprint_spoofer_init(self):
        """测试指纹伪造器初始化"""
        spoofer = FingerprintSpoofer()
        
        assert spoofer.user_agents is not None
        assert len(spoofer.user_agents) > 0
        assert spoofer.screen_resolutions is not None
        assert len(spoofer.screen_resolutions) > 0
    
    def test_generate_random_user_agent(self):
        """测试生成随机用户代理"""
        spoofer = FingerprintSpoofer()
        
        # 生成多个用户代理
        ua1 = spoofer.generate_random_user_agent()
        ua2 = spoofer.generate_random_user_agent()
        
        assert ua1 is not None
        assert ua2 is not None
        assert "Mozilla" in ua1
        assert "Mozilla" in ua2
        # 应该有一定概率生成不同的用户代理
        
        # 测试指定浏览器
        chrome_ua = spoofer.generate_random_user_agent(browser="chrome")
        firefox_ua = spoofer.generate_random_user_agent(browser="firefox")
        
        assert "Chrome" in chrome_ua
        assert "Firefox" in firefox_ua
    
    def test_generate_random_viewport(self):
        """测试生成随机视口"""
        spoofer = FingerprintSpoofer()
        
        viewport = spoofer.generate_random_viewport()
        
        assert "width" in viewport
        assert "height" in viewport
        assert viewport["width"] > 0
        assert viewport["height"] > 0
        assert viewport["width"] >= 800  # 最小宽度
        assert viewport["height"] >= 600  # 最小高度
    
    def test_generate_random_headers(self):
        """测试生成随机请求头"""
        spoofer = FingerprintSpoofer()
        
        headers = spoofer.generate_random_headers()
        
        assert "User-Agent" in headers
        assert "Accept" in headers
        assert "Accept-Language" in headers
        assert "Accept-Encoding" in headers
        assert "Connection" in headers
        
        # 检查特定值
        assert "Mozilla" in headers["User-Agent"]
        assert "gzip" in headers["Accept-Encoding"]
    
    def test_generate_canvas_fingerprint(self):
        """测试生成Canvas指纹"""
        spoofer = FingerprintSpoofer()
        
        fingerprint = spoofer.generate_canvas_fingerprint()
        
        assert isinstance(fingerprint, str)
        assert len(fingerprint) > 0
        # Canvas指纹应该是唯一的
        fingerprint2 = spoofer.generate_canvas_fingerprint()
        # 有一定概率生成不同的指纹
    
    def test_generate_webgl_fingerprint(self):
        """测试生成WebGL指纹"""
        spoofer = FingerprintSpoofer()
        
        fingerprint = spoofer.generate_webgl_fingerprint()
        
        assert isinstance(fingerprint, dict)
        assert "renderer" in fingerprint
        assert "vendor" in fingerprint
        assert "version" in fingerprint
        
        # 检查合理性
        assert fingerprint["renderer"] is not None
        assert fingerprint["vendor"] is not None
    
    def test_generate_timezone_offset(self):
        """测试生成时区偏移"""
        spoofer = FingerprintSpoofer()
        
        offset = spoofer.generate_timezone_offset()
        
        assert isinstance(offset, int)
        assert -12 * 60 <= offset <= 14 * 60  # 合理的时区范围
    
    def test_generate_full_fingerprint(self):
        """测试生成完整指纹"""
        spoofer = FingerprintSpoofer()
        
        fingerprint = spoofer.generate_full_fingerprint()
        
        assert "user_agent" in fingerprint
        assert "viewport" in fingerprint
        assert "headers" in fingerprint
        assert "canvas_fingerprint" in fingerprint
        assert "webgl_fingerprint" in fingerprint
        assert "timezone_offset" in fingerprint
        assert "language" in fingerprint
        assert "platform" in fingerprint
        
        # 检查类型
        assert isinstance(fingerprint["user_agent"], str)
        assert isinstance(fingerprint["viewport"], dict)
        assert isinstance(fingerprint["headers"], dict)
        assert isinstance(fingerprint["timezone_offset"], int)
    
    def test_spoof_request_headers(self):
        """测试伪造请求头"""
        spoofer = FingerprintSpoofer()
        
        original_headers = {
            "User-Agent": "OldAgent",
            "Accept": "text/html"
        }
        
        spoofed_headers = spoofer.spoof_request_headers(original_headers)
        
        assert spoofed_headers["User-Agent"] != "OldAgent"
        assert "Mozilla" in spoofed_headers["User-Agent"]
        assert "Accept" in spoofed_headers
        assert "Accept-Language" in spoofed_headers
        assert "Accept-Encoding" in spoofed_headers


class TestBehaviorMimicker:
    """行为模拟器测试"""
    
    def test_behavior_mimicker_init(self):
        """测试行为模拟器初始化"""
        mimicker = BehaviorMimicker()
        
        assert mimicker.mouse_patterns is not None
        assert mimicker.typing_patterns is not None
        assert mimicker.scroll_patterns is not None
        assert mimicker.min_delay == 0.1
        assert mimicker.max_delay == 2.0
    
    def test_generate_human_delay(self):
        """测试生成人类延迟"""
        mimicker = BehaviorMimicker()
        
        # 生成多个延迟
        delays = [mimicker.generate_human_delay() for _ in range(100)]
        
        # 检查范围
        assert all(0.1 <= delay <= 2.0 for delay in delays)
        
        # 检查分布（应该有变化）
        assert len(set(delays)) > 1
        
        # 自定义范围
        custom_delay = mimicker.generate_human_delay(min_delay=0.5, max_delay=1.0)
        assert 0.5 <= custom_delay <= 1.0
    
    def test_generate_mouse_movement(self):
        """测试生成鼠标移动"""
        mimicker = BehaviorMimicker()
        
        movement = mimicker.generate_mouse_movement(
            start_x=100, start_y=100,
            end_x=200, end_y=200
        )
        
        assert "path" in movement
        assert "duration" in movement
        assert "steps" in movement
        
        # 检查路径
        path = movement["path"]
        assert len(path) > 0
        assert path[0] == (100, 100)  # 起始点
        assert path[-1] == (200, 200)  # 结束点
        
        # 检查持续时间
        assert movement["duration"] > 0
        assert movement["steps"] > 0
    
    def test_generate_typing_pattern(self):
        """测试生成打字模式"""
        mimicker = BehaviorMimicker()
        
        pattern = mimicker.generate_typing_pattern("hello world")
        
        assert "keystrokes" in pattern
        assert "total_duration" in pattern
        assert "wpm" in pattern
        
        # 检查按键
        keystrokes = pattern["keystrokes"]
        assert len(keystrokes) == len("hello world")
        
        # 检查每个按键
        for keystroke in keystrokes:
            assert "key" in keystroke
            assert "delay" in keystroke
            assert "duration" in keystroke
        
        # 检查WPM合理性
        assert 20 <= pattern["wpm"] <= 120
    
    def test_generate_scroll_pattern(self):
        """测试生成滚动模式"""
        mimicker = BehaviorMimicker()
        
        pattern = mimicker.generate_scroll_pattern(
            start_position=0,
            end_position=1000,
            page_height=5000
        )
        
        assert "scrolls" in pattern
        assert "total_duration" in pattern
        assert "scroll_speed" in pattern
        
        # 检查滚动
        scrolls = pattern["scrolls"]
        assert len(scrolls) > 0
        
        # 检查每个滚动
        for scroll in scrolls:
            assert "position" in scroll
            assert "delay" in scroll
            assert "duration" in scroll
    
    def test_simulate_reading_behavior(self):
        """测试模拟阅读行为"""
        mimicker = BehaviorMimicker()
        
        text = "This is a test text with multiple words and sentences."
        behavior = mimicker.simulate_reading_behavior(text)
        
        assert "reading_time" in behavior
        assert "eye_movements" in behavior
        assert "scroll_actions" in behavior
        
        # 检查阅读时间合理性
        assert behavior["reading_time"] > 0
        
        # 检查眼动
        eye_movements = behavior["eye_movements"]
        assert len(eye_movements) > 0
        
        # 检查滚动动作
        scroll_actions = behavior["scroll_actions"]
        assert isinstance(scroll_actions, list)
    
    def test_simulate_browsing_session(self):
        """测试模拟浏览会话"""
        mimicker = BehaviorMimicker()
        
        session = mimicker.simulate_browsing_session(
            pages=["page1", "page2", "page3"],
            session_duration=300  # 5分钟
        )
        
        assert "page_visits" in session
        assert "total_duration" in session
        assert "user_actions" in session
        
        # 检查页面访问
        page_visits = session["page_visits"]
        assert len(page_visits) == 3
        
        # 检查每个页面访问
        for visit in page_visits:
            assert "page" in visit
            assert "duration" in visit
            assert "actions" in visit
        
        # 检查总时长
        assert session["total_duration"] <= 300
    
    def test_add_human_randomness(self):
        """测试添加人类随机性"""
        mimicker = BehaviorMimicker()
        
        # 原始动作
        original_action = {
            "type": "click",
            "x": 100,
            "y": 100,
            "delay": 0.5
        }
        
        randomized_action = mimicker.add_human_randomness(original_action)
        
        assert "type" in randomized_action
        assert "x" in randomized_action
        assert "y" in randomized_action
        assert "delay" in randomized_action
        
        # 检查随机化
        assert randomized_action["type"] == "click"
        # 位置应该有轻微变化
        assert abs(randomized_action["x"] - 100) <= 5
        assert abs(randomized_action["y"] - 100) <= 5
        # 延迟应该有变化
        assert randomized_action["delay"] != 0.5


class TestAntiBotHandler:
    """反爬虫处理器测试"""
    
    def test_anti_bot_handler_init(self):
        """测试反爬虫处理器初始化"""
        handler = AntiBotHandler()
        
        assert handler.ml_detector is not None
        assert handler.js_engine is not None
        assert handler.browser_automation is not None
        assert handler.fingerprint_spoofer is not None
        assert handler.behavior_mimicker is not None
        assert handler.detection_count == 0
        assert handler.bypass_count == 0
    
    def test_detect_bot_protection_basic(self):
        """测试基本反爬虫检测"""
        handler = AntiBotHandler()
        
        # 正常页面
        normal_html = "<html><body>Normal content</body></html>"
        result = handler.detect_bot_protection(normal_html, "https://example.com")
        
        assert result.is_detected is False
        assert result.detection_type == BotDetectionType.NONE
        
        # CAPTCHA页面
        captcha_html = "<html><body><div class='g-recaptcha'>CAPTCHA</div></body></html>"
        result = handler.detect_bot_protection(captcha_html, "https://example.com")
        
        assert result.is_detected is True
        assert result.detection_type == BotDetectionType.CAPTCHA
    
    def test_detect_bot_protection_cloudflare(self):
        """测试Cloudflare检测"""
        handler = AntiBotHandler()
        
        cloudflare_html = """
        <html>
            <body>
                <div>Checking your browser before accessing...</div>
                <div class="cf-browser-verification">Cloudflare</div>
            </body>
        </html>
        """
        
        result = handler.detect_bot_protection(cloudflare_html, "https://example.com")
        
        assert result.is_detected is True
        assert result.detection_type == BotDetectionType.CLOUDFLARE
    
    def test_detect_bot_protection_rate_limit(self):
        """测试速率限制检测"""
        handler = AntiBotHandler()
        
        rate_limit_html = """
        <html>
            <body>
                <h1>Too Many Requests</h1>
                <p>You have exceeded the rate limit.</p>
            </body>
        </html>
        """
        
        result = handler.detect_bot_protection(rate_limit_html, "https://example.com")
        
        assert result.is_detected is True
        assert result.detection_type == BotDetectionType.RATE_LIMIT
    
    def test_detect_bot_protection_access_denied(self):
        """测试访问拒绝检测"""
        handler = AntiBotHandler()
        
        access_denied_html = """
        <html>
            <body>
                <h1>Access Denied</h1>
                <p>Your request has been blocked.</p>
            </body>
        </html>
        """
        
        result = handler.detect_bot_protection(access_denied_html, "https://example.com")
        
        assert result.is_detected is True
        assert result.detection_type == BotDetectionType.ACCESS_DENIED
    
    def test_detect_bot_protection_javascript(self):
        """测试JavaScript挑战检测"""
        handler = AntiBotHandler()
        
        js_challenge_html = """
        <html>
            <body>
                <script>
                    // JavaScript challenge
                    if (typeof window !== 'undefined') {
                        window.location.href = '/verified';
                    }
                </script>
                <noscript>Please enable JavaScript</noscript>
            </body>
        </html>
        """
        
        result = handler.detect_bot_protection(js_challenge_html, "https://example.com")
        
        assert result.is_detected is True
        assert result.detection_type == BotDetectionType.JAVASCRIPT_CHALLENGE
    
    @pytest.mark.asyncio
    async def test_handle_block_captcha(self):
        """测试处理CAPTCHA阻止"""
        handler = AntiBotHandler()
        
        # 模拟CAPTCHA检测结果
        detection_result = BotDetectionResult(
            is_detected=True,
            detection_type=BotDetectionType.CAPTCHA,
            confidence=0.95
        )
        
        # 模拟会话
        mock_session = AsyncMock()
        
        with patch.object(handler.browser_automation, 'solve_captcha', return_value="<html>Success</html>"):
            result = await handler.handle_block(detection_result, mock_session, "https://example.com")
            
            assert result == "<html>Success</html>"
            assert handler.bypass_count == 1
    
    @pytest.mark.asyncio
    async def test_handle_block_cloudflare(self):
        """测试处理Cloudflare阻止"""
        handler = AntiBotHandler()
        
        # 模拟Cloudflare检测结果
        detection_result = BotDetectionResult(
            is_detected=True,
            detection_type=BotDetectionType.CLOUDFLARE,
            confidence=0.9
        )
        
        # 模拟会话
        mock_session = AsyncMock()
        
        with patch.object(handler.browser_automation, 'handle_cloudflare_challenge', return_value="<html>Bypassed</html>"):
            result = await handler.handle_block(detection_result, mock_session, "https://example.com")
            
            assert result == "<html>Bypassed</html>"
            assert handler.bypass_count == 1
    
    @pytest.mark.asyncio
    async def test_handle_block_rate_limit(self):
        """测试处理速率限制"""
        handler = AntiBotHandler()
        
        # 模拟速率限制检测结果
        detection_result = BotDetectionResult(
            is_detected=True,
            detection_type=BotDetectionType.RATE_LIMIT,
            confidence=0.8
        )
        
        # 模拟会话
        mock_session = AsyncMock()
        
        with patch('asyncio.sleep'):
            result = await handler.handle_block(detection_result, mock_session, "https://example.com")
            
            assert result is None  # 速率限制通常只是等待
            assert handler.bypass_count == 1
    
    def test_choose_bypass_strategy(self):
        """测试选择绕过策略"""
        handler = AntiBotHandler()
        
        # CAPTCHA
        captcha_result = BotDetectionResult(
            is_detected=True,
            detection_type=BotDetectionType.CAPTCHA,
            confidence=0.95
        )
        strategy = handler._choose_bypass_strategy(captcha_result)
        assert strategy == BypassStrategy.BROWSER_AUTOMATION
        
        # Cloudflare
        cloudflare_result = BotDetectionResult(
            is_detected=True,
            detection_type=BotDetectionType.CLOUDFLARE,
            confidence=0.9
        )
        strategy = handler._choose_bypass_strategy(cloudflare_result)
        assert strategy == BypassStrategy.BROWSER_AUTOMATION
        
        # JavaScript挑战
        js_result = BotDetectionResult(
            is_detected=True,
            detection_type=BotDetectionType.JAVASCRIPT_CHALLENGE,
            confidence=0.85
        )
        strategy = handler._choose_bypass_strategy(js_result)
        assert strategy == BypassStrategy.JAVASCRIPT_EXECUTION
        
        # 速率限制
        rate_limit_result = BotDetectionResult(
            is_detected=True,
            detection_type=BotDetectionType.RATE_LIMIT,
            confidence=0.8
        )
        strategy = handler._choose_bypass_strategy(rate_limit_result)
        assert strategy == BypassStrategy.DELAY_AND_RETRY
    
    def test_update_detection_stats(self):
        """测试更新检测统计"""
        handler = AntiBotHandler()
        
        # 初始状态
        assert handler.detection_count == 0
        assert handler.bypass_count == 0
        
        # 更新检测统计
        handler._update_detection_stats(BotDetectionType.CAPTCHA, True)
        assert handler.detection_count == 1
        assert handler.bypass_count == 1
        
        # 更新失败的绕过
        handler._update_detection_stats(BotDetectionType.CLOUDFLARE, False)
        assert handler.detection_count == 2
        assert handler.bypass_count == 1
    
    def test_get_stats(self):
        """测试获取统计信息"""
        handler = AntiBotHandler()
        
        # 设置一些统计数据
        handler.detection_count = 10
        handler.bypass_count = 8
        
        stats = handler.get_stats()
        
        assert stats["detection_count"] == 10
        assert stats["bypass_count"] == 8
        assert stats["success_rate"] == 80.0
        assert "detection_types" in stats
        assert "bypass_strategies" in stats
        assert "ml_detector_stats" in stats


class TestConvenienceFunctions:
    """便捷函数测试"""
    
    def test_detect_bot_protection_function(self):
        """测试反爬虫检测函数"""
        # 正常页面
        normal_html = "<html><body>Normal content</body></html>"
        result = detect_bot_protection(normal_html, "https://example.com")
        
        assert result.is_detected is False
        
        # CAPTCHA页面
        captcha_html = "<html><body><div class='g-recaptcha'>CAPTCHA</div></body></html>"
        result = detect_bot_protection(captcha_html, "https://example.com")
        
        assert result.is_detected is True
        assert result.detection_type == BotDetectionType.CAPTCHA
    
    def test_is_captcha_page_function(self):
        """测试CAPTCHA页面检测函数"""
        # 正常页面
        normal_html = "<html><body>Normal content</body></html>"
        assert is_captcha_page(normal_html) is False
        
        # CAPTCHA页面
        captcha_html = "<html><body><div class='g-recaptcha'>CAPTCHA</div></body></html>"
        assert is_captcha_page(captcha_html) is True
        
        # hCaptcha页面
        hcaptcha_html = "<html><body><div class='h-captcha'>hCAPTCHA</div></body></html>"
        assert is_captcha_page(hcaptcha_html) is True
    
    @pytest.mark.asyncio
    async def test_bypass_cloudflare_function(self):
        """测试绕过Cloudflare函数"""
        with patch('mercari_agent.scrapers.anti_bot_handler.BrowserAutomation') as mock_automation_class:
            mock_automation = AsyncMock()
            mock_automation.initialize_browser.return_value = None
            mock_automation.handle_cloudflare_challenge.return_value = "<html>Bypassed</html>"
            mock_automation.close_browser.return_value = None
            mock_automation_class.return_value = mock_automation
            
            result = await bypass_cloudflare("https://example.com")
            
            assert result == "<html>Bypassed</html>"
            mock_automation.initialize_browser.assert_called_once()
            mock_automation.handle_cloudflare_challenge.assert_called_once()
            mock_automation.close_browser.assert_called_once()


@pytest.fixture
def sample_captcha_html():
    """示例CAPTCHA HTML"""
    return """
    <html>
        <body>
            <div class="g-recaptcha" data-sitekey="test-site-key">
                <div>reCAPTCHA</div>
            </div>
            <form>
                <input type="text" name="captcha_response">
                <button type="submit">Submit</button>
            </form>
        </body>
    </html>
    """


@pytest.fixture
def sample_cloudflare_html():
    """示例Cloudflare HTML"""
    return """
    <html>
        <body>
            <div class="cf-browser-verification">
                <h1>Checking your browser before accessing...</h1>
                <p>This process is automatic. Your browser will redirect to your requested content shortly.</p>
                <div class="cf-spinner">Loading...</div>
            </div>
        </body>
    </html>
    """


@pytest.fixture
def sample_rate_limit_html():
    """示例速率限制HTML"""
    return """
    <html>
        <body>
            <h1>Too Many Requests</h1>
            <p>You have exceeded the rate limit. Please try again later.</p>
            <div class="retry-after">Retry after: 60 seconds</div>
        </body>
    </html>
    """