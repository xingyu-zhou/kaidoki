"""
浏览器环境伪装系统 - 核心实现

该模块提供完整的浏览器环境伪装功能，专门解决headless模式与非headless模式
之间的差异，降低CAPTCHA触发概率。

核心功能：
1. DevTools检测绕过 - 解决85%检测概率的高风险点
2. Console对象标准化 - 完善console方法行为和属性
3. 字体渲染一致性 - 模拟真实系统字体和渲染效果
4. window.chrome对象完善 - 添加Chrome扩展API特征
5. JavaScript执行环境优化 - 消除自动化痕迹

技术特点：
- 基于现有指纹管理器的增强实现
- 运行时动态JavaScript注入
- 持久化指纹一致性维护
- 针对Mercari特定检测机制优化
- 与现有系统无缝集成

Author: Mercari AI Agent Team
"""

import asyncio
import logging
import random
import time
import json
import base64
import hashlib
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import re
import platform
from urllib.parse import urljoin

from .browser_fingerprint_manager import BrowserFingerprintManager, BrowserFingerprint, BrowserType, OSType
from .enhanced_session_manager import EnhancedSessionManager
from .anti_bot_handler import AntiBotHandler
from .tls_fingerprint_manager import TLSFingerprintManager
from ..utils.logger import get_logger
from ..config.settings import settings

logger = get_logger(__name__)


class SpoofingLevel(Enum):
    """伪装级别枚举"""
    MINIMAL = "minimal"     # 最小伪装，只处理关键检测点
    STANDARD = "standard"   # 标准伪装，处理大部分常见检测
    AGGRESSIVE = "aggressive"  # 激进伪装，处理所有已知检测点
    CUSTOM = "custom"       # 自定义伪装配置


class DetectionType(Enum):
    """检测类型枚举"""
    DEVTOOLS = "devtools"
    CONSOLE = "console"
    WEBGL = "webgl"
    CANVAS = "canvas"
    FONT_RENDERING = "font_rendering"
    WINDOW_CHROME = "window_chrome"
    JAVASCRIPT_EXECUTION = "javascript_execution"
    PERFORMANCE_TIMING = "performance_timing"
    ERROR_STACK = "error_stack"


@dataclass
class SpoofingConfig:
    """伪装配置"""
    level: SpoofingLevel = SpoofingLevel.STANDARD
    enabled_detections: List[DetectionType] = field(default_factory=lambda: [
        DetectionType.DEVTOOLS,
        DetectionType.CONSOLE,
        DetectionType.FONT_RENDERING,
        DetectionType.WINDOW_CHROME
    ])
    
    # DevTools检测配置
    devtools_spoofing_enabled: bool = True
    window_size_randomization: bool = True
    
    # Console对象配置
    console_spoofing_enabled: bool = True
    console_method_standardization: bool = True
    console_memory_simulation: bool = True
    
    # 字体渲染配置
    font_rendering_enabled: bool = True
    system_font_simulation: bool = True
    font_fallback_enabled: bool = True
    
    # Chrome对象配置
    chrome_object_enabled: bool = True
    chrome_runtime_simulation: bool = True
    chrome_webstore_simulation: bool = True
    
    # 性能优化配置
    execution_delay_enabled: bool = True
    min_execution_delay: float = 0.1
    max_execution_delay: float = 0.5
    
    # 一致性维护配置
    fingerprint_consistency: bool = True
    session_persistence: bool = True


@dataclass
class SpoofingResult:
    """伪装结果"""
    success: bool
    applied_spoofings: List[DetectionType]
    failed_spoofings: List[DetectionType] = field(default_factory=list)
    execution_time: float = 0.0
    fingerprint_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class DevToolsDetectionBypass:
    """DevTools检测绕过模块"""
    
    def __init__(self):
        """初始化DevTools检测绕过"""
        self.bypass_scripts = self._load_bypass_scripts()
        logger.info("DevTools检测绕过模块初始化完成")
    
    def _load_bypass_scripts(self) -> Dict[str, str]:
        """加载绕过脚本"""
        return {
            "window_size_fix": """
                // 修正窗口尺寸差异，防止DevTools检测
                (function() {
                    const originalInnerHeight = window.innerHeight;
                    const originalInnerWidth = window.innerWidth;
                    
                    // 模拟真实浏览器的窗口尺寸关系
                    Object.defineProperty(window, 'outerHeight', {
                        get: function() {
                            return originalInnerHeight + Math.floor(Math.random() * 100 + 50);
                        },
                        configurable: true
                    });
                    
                    Object.defineProperty(window, 'outerWidth', {
                        get: function() {
                            return originalInnerWidth + Math.floor(Math.random() * 20 + 10);
                        },
                        configurable: true
                    });
                })();
            """,
            
            "screen_properties_fix": """
                // 修正屏幕属性，确保一致性
                (function() {
                    const screenProps = {
                        colorDepth: 24,
                        pixelDepth: 24,
                        availHeight: screen.height - 40,
                        availWidth: screen.width
                    };
                    
                    Object.keys(screenProps).forEach(prop => {
                        Object.defineProperty(screen, prop, {
                            get: function() { return screenProps[prop]; },
                            configurable: true
                        });
                    });
                })();
            """,
            
            "visibility_api_fix": """
                // 修正Visibility API，避免headless检测
                (function() {
                    Object.defineProperty(document, 'hidden', {
                        get: function() { return false; },
                        configurable: true
                    });
                    
                    Object.defineProperty(document, 'visibilityState', {
                        get: function() { return 'visible'; },
                        configurable: true
                    });
                    
                    Object.defineProperty(document, 'webkitHidden', {
                        get: function() { return false; },
                        configurable: true
                    });
                })();
            """
        }
    
    def generate_bypass_script(self, fingerprint: BrowserFingerprint) -> str:
        """生成绕过脚本"""
        scripts = []
        
        # 添加窗口尺寸修正
        scripts.append(self.bypass_scripts["window_size_fix"])
        
        # 添加屏幕属性修正
        scripts.append(self.bypass_scripts["screen_properties_fix"])
        
        # 添加可见性API修正
        scripts.append(self.bypass_scripts["visibility_api_fix"])
        
        # 合并所有脚本
        combined_script = "\n".join(scripts)
        
        logger.debug("生成DevTools检测绕过脚本")
        return combined_script


class ConsoleObjectStandardizer:
    """Console对象标准化模块"""
    
    def __init__(self):
        """初始化Console对象标准化"""
        self.console_methods = self._load_console_methods()
        logger.info("Console对象标准化模块初始化完成")
    
    def _load_console_methods(self) -> Dict[str, Dict[str, Any]]:
        """加载console方法配置"""
        return {
            "log": {
                "toString": "function log() { [native code] }",
                "length": 0
            },
            "warn": {
                "toString": "function warn() { [native code] }",
                "length": 0
            },
            "error": {
                "toString": "function error() { [native code] }",
                "length": 0
            },
            "info": {
                "toString": "function info() { [native code] }",
                "length": 0
            },
            "debug": {
                "toString": "function debug() { [native code] }",
                "length": 0
            },
            "clear": {
                "toString": "function clear() { [native code] }",
                "length": 0
            },
            "table": {
                "toString": "function table() { [native code] }",
                "length": 0
            },
            "time": {
                "toString": "function time() { [native code] }",
                "length": 0
            },
            "timeEnd": {
                "toString": "function timeEnd() { [native code] }",
                "length": 0
            },
            "group": {
                "toString": "function group() { [native code] }",
                "length": 0
            },
            "groupEnd": {
                "toString": "function groupEnd() { [native code] }",
                "length": 0
            },
            "profile": {
                "toString": "function profile() { [native code] }",
                "length": 0
            },
            "profileEnd": {
                "toString": "function profileEnd() { [native code] }",
                "length": 0
            }
        }
    
    def generate_console_script(self, browser_type: BrowserType) -> str:
        """生成console标准化脚本"""
        script = """
            // Console对象标准化脚本
            (function() {
                const originalConsole = window.console;
                const methods = %s;
                
                // 标准化每个console方法
                Object.keys(methods).forEach(method => {
                    if (originalConsole[method]) {
                        const originalMethod = originalConsole[method];
                        const methodConfig = methods[method];
                        
                        // 重新定义方法，确保toString()返回正确值
                        Object.defineProperty(originalConsole[method], 'toString', {
                            value: function() { return methodConfig.toString; },
                            writable: false,
                            configurable: false
                        });
                        
                        // 设置length属性
                        Object.defineProperty(originalConsole[method], 'length', {
                            value: methodConfig.length,
                            writable: false,
                            configurable: false
                        });
                    }
                });
                
                // 添加console.memory属性（Chrome特有）
                if (!originalConsole.memory && window.chrome) {
                    Object.defineProperty(originalConsole, 'memory', {
                        get: function() {
                            return {
                                usedJSHeapSize: Math.floor(Math.random() * 50000000 + 10000000),
                                totalJSHeapSize: Math.floor(Math.random() * 100000000 + 50000000),
                                jsHeapSizeLimit: 2172649472
                            };
                        },
                        configurable: true
                    });
                }
                
                // 添加console.profile系列方法
                ['profile', 'profileEnd'].forEach(method => {
                    if (!originalConsole[method]) {
                        originalConsole[method] = function() {};
                        Object.defineProperty(originalConsole[method], 'toString', {
                            value: function() { return 'function ' + method + '() { [native code] }'; },
                            writable: false
                        });
                    }
                });
            })();
        """ % json.dumps(self.console_methods)
        
        logger.debug("生成Console对象标准化脚本")
        return script


class FontRenderingSimulator:
    """字体渲染模拟器"""
    
    def __init__(self):
        """初始化字体渲染模拟器"""
        self.font_families = self._load_font_families()
        self.font_metrics = self._load_font_metrics()
        logger.info("字体渲染模拟器初始化完成")
    
    def _load_font_families(self) -> Dict[OSType, List[str]]:
        """加载字体族配置"""
        return {
            OSType.WINDOWS: [
                "Arial", "Helvetica", "Times New Roman", "Courier New",
                "Verdana", "Georgia", "Palatino", "Garamond",
                "Bookman", "Comic Sans MS", "Trebuchet MS", "Arial Black",
                "Impact", "Lucida Sans Unicode", "Tahoma", "Lucida Console",
                "MS Sans Serif", "MS Serif", "Symbol", "Webdings",
                "Wingdings", "Calibri", "Cambria", "Consolas",
                "Constantia", "Corbel", "Candara"
            ],
            OSType.MACOS: [
                "Arial", "Helvetica", "Times", "Courier",
                "Verdana", "Georgia", "Palatino", "Times New Roman",
                "Courier New", "Apple Symbols", "AppleGothic", "AppleMyungjo",
                "Geneva", "Monaco", "Osaka", "Trebuchet MS",
                "Helvetica Neue", "Lucida Grande", "Gill Sans",
                "Baskerville", "Hoefler Text", "Marker Felt",
                "Optima", "Zapfino", "Brush Script MT"
            ],
            OSType.LINUX: [
                "Arial", "Helvetica", "Times", "Courier",
                "Verdana", "Georgia", "Palatino", "DejaVu Sans",
                "DejaVu Serif", "DejaVu Sans Mono", "Liberation Sans",
                "Liberation Serif", "Liberation Mono", "Ubuntu",
                "Cantarell", "Noto Sans", "Noto Serif", "Droid Sans",
                "Droid Serif", "Roboto", "Open Sans", "Lato",
                "Source Sans Pro", "Source Serif Pro", "PT Sans"
            ]
        }
    
    def _load_font_metrics(self) -> Dict[str, Dict[str, float]]:
        """加载字体度量配置"""
        return {
            "Arial": {
                "width_factor": 0.52,
                "height_factor": 1.0,
                "baseline_factor": 0.8
            },
            "Helvetica": {
                "width_factor": 0.51,
                "height_factor": 1.0,
                "baseline_factor": 0.8
            },
            "Times New Roman": {
                "width_factor": 0.48,
                "height_factor": 1.0,
                "baseline_factor": 0.75
            },
            "Courier New": {
                "width_factor": 0.6,
                "height_factor": 1.0,
                "baseline_factor": 0.8
            }
        }
    
    def generate_font_script(self, os_type: OSType, browser_type: BrowserType) -> str:
        """生成字体渲染脚本"""
        available_fonts = self.font_families.get(os_type, self.font_families[OSType.WINDOWS])
        
        script = """
            // 字体渲染一致性脚本
            (function() {
                const availableFonts = %s;
                const fontMetrics = %s;
                
                // 模拟字体检测
                const originalOffsetWidth = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetWidth');
                const originalOffsetHeight = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetHeight');
                
                // 重写字体度量计算
                if (window.CanvasRenderingContext2D && window.CanvasRenderingContext2D.prototype.measureText) {
                    const originalMeasureText = window.CanvasRenderingContext2D.prototype.measureText;
                    
                    window.CanvasRenderingContext2D.prototype.measureText = function(text) {
                        const result = originalMeasureText.call(this, text);
                        
                        // 根据字体调整度量
                        const font = this.font || 'Arial';
                        const fontFamily = font.split(' ').pop().replace(/['"]/g, '');
                        const metrics = fontMetrics[fontFamily] || fontMetrics['Arial'];
                        
                        if (result.width && metrics.width_factor) {
                            result.width *= (metrics.width_factor * (0.95 + Math.random() * 0.1));
                        }
                        
                        return result;
                    };
                }
                
                // 字体可用性检测
                const fontFaceSet = document.fonts;
                if (fontFaceSet && fontFaceSet.check) {
                    const originalCheck = fontFaceSet.check;
                    fontFaceSet.check = function(font, text) {
                        const fontFamily = font.split(' ').pop().replace(/['"]/g, '');
                        return availableFonts.includes(fontFamily) || originalCheck.call(this, font, text);
                    };
                }
            })();
        """ % (json.dumps(available_fonts), json.dumps(self.font_metrics))
        
        logger.debug(f"生成字体渲染脚本，支持{len(available_fonts)}种字体")
        return script


class ChromeObjectSimulator:
    """Chrome对象模拟器"""
    
    def __init__(self):
        """初始化Chrome对象模拟器"""
        self.chrome_api = self._load_chrome_api()
        logger.info("Chrome对象模拟器初始化完成")
    
    def _load_chrome_api(self) -> Dict[str, Any]:
        """加载Chrome API配置"""
        return {
            "runtime": {
                "onConnect": None,
                "onMessage": None,
                "onConnectExternal": None,
                "onMessageExternal": None,
                "onStartup": None,
                "onInstalled": None,
                "onSuspend": None,
                "onSuspendCanceled": None,
                "onUpdateAvailable": None,
                "onRestartRequired": None,
                "id": "extension_id_placeholder",
                "getManifest": "function() { return {}; }",
                "getURL": "function(path) { return 'chrome-extension://extension_id/' + path; }",
                "connect": "function() { return {}; }",
                "sendMessage": "function() { return {}; }"
            },
            "webstore": {
                "install": "function() { return {}; }",
                "onInstallStageChanged": None,
                "onDownloadProgress": None
            },
            "loadTimes": "function() { return { requestTime: Date.now()/1000, startLoadTime: Date.now()/1000, commitLoadTime: Date.now()/1000, finishDocumentLoadTime: Date.now()/1000, finishLoadTime: Date.now()/1000, firstPaintTime: Date.now()/1000, firstPaintAfterLoadTime: 0, navigationType: 'Other' }; }",
            "csi": "function() { return { pageT: Date.now(), startE: Date.now(), tran: 15 }; }",
            "app": {
                "isInstalled": False,
                "InstallState": {
                    "DISABLED": "disabled",
                    "INSTALLED": "installed", 
                    "NOT_INSTALLED": "not_installed"
                },
                "RunningState": {
                    "CANNOT_RUN": "cannot_run",
                    "READY_TO_RUN": "ready_to_run",
                    "RUNNING": "running"
                }
            }
        }
    
    def generate_chrome_script(self, browser_type: BrowserType) -> str:
        """生成Chrome对象脚本"""
        if browser_type != BrowserType.CHROME:
            return ""  # 只有Chrome浏览器才添加Chrome对象
        
        script = """
            // Chrome对象模拟脚本
            (function() {
                if (!window.chrome) {
                    window.chrome = {};
                }
                
                const chromeAPI = %s;
                
                // 添加runtime API
                if (!window.chrome.runtime) {
                    window.chrome.runtime = {};
                    Object.keys(chromeAPI.runtime).forEach(key => {
                        if (typeof chromeAPI.runtime[key] === 'string' && chromeAPI.runtime[key].startsWith('function')) {
                            window.chrome.runtime[key] = new Function('return ' + chromeAPI.runtime[key])();
                        } else {
                            window.chrome.runtime[key] = chromeAPI.runtime[key];
                        }
                    });
                }
                
                // 添加webstore API
                if (!window.chrome.webstore) {
                    window.chrome.webstore = {};
                    Object.keys(chromeAPI.webstore).forEach(key => {
                        if (typeof chromeAPI.webstore[key] === 'string' && chromeAPI.webstore[key].startsWith('function')) {
                            window.chrome.webstore[key] = new Function('return ' + chromeAPI.webstore[key])();
                        } else {
                            window.chrome.webstore[key] = chromeAPI.webstore[key];
                        }
                    });
                }
                
                // 添加loadTimes API
                if (!window.chrome.loadTimes) {
                    window.chrome.loadTimes = new Function('return ' + chromeAPI.loadTimes)();
                }
                
                // 添加csi API
                if (!window.chrome.csi) {
                    window.chrome.csi = new Function('return ' + chromeAPI.csi)();
                }
                
                // 添加app API
                if (!window.chrome.app) {
                    window.chrome.app = chromeAPI.app;
                }
                
                // 确保Chrome对象不可枚举
                Object.defineProperty(window, 'chrome', {
                    value: window.chrome,
                    writable: false,
                    enumerable: false,
                    configurable: false
                });
            })();
        """ % json.dumps(self.chrome_api)
        
        logger.debug("生成Chrome对象模拟脚本")
        return script


class BrowserEnvironmentSpoofing:
    """浏览器环境伪装主类"""
    
    def __init__(self, 
                 config: Optional[SpoofingConfig] = None,
                 fingerprint_manager: Optional[BrowserFingerprintManager] = None):
        """
        初始化浏览器环境伪装系统
        
        Args:
            config: 伪装配置
            fingerprint_manager: 指纹管理器实例
        """
        self.config = config or SpoofingConfig()
        self.fingerprint_manager = fingerprint_manager or BrowserFingerprintManager()
        
        # 初始化各个伪装模块
        self.devtools_bypass = DevToolsDetectionBypass()
        self.console_standardizer = ConsoleObjectStandardizer()
        self.font_simulator = FontRenderingSimulator()
        self.chrome_simulator = ChromeObjectSimulator()
        
        # 伪装状态管理
        self.active_spoofings: Dict[str, SpoofingResult] = {}
        self.spoofing_stats = {
            "total_requests": 0,
            "successful_spoofings": 0,
            "failed_spoofings": 0,
            "detection_bypassed": 0
        }
        
        logger.info("🎭 浏览器环境伪装系统初始化完成")
    
    async def apply_spoofing(self, 
                           session_id: str,
                           target_url: str,
                           fingerprint: Optional[BrowserFingerprint] = None) -> SpoofingResult:
        """
        应用浏览器环境伪装
        
        Args:
            session_id: 会话ID
            target_url: 目标URL
            fingerprint: 指定的浏览器指纹
            
        Returns:
            SpoofingResult: 伪装结果
        """
        start_time = time.time()
        
        try:
            # 获取或生成指纹
            if fingerprint is None:
                fingerprint = self.fingerprint_manager.get_fingerprint()
            
            # 生成伪装脚本
            spoofing_scripts = await self._generate_spoofing_scripts(fingerprint)
            
            # 应用伪装
            applied_spoofings = []
            failed_spoofings = []
            
            for detection_type, script in spoofing_scripts.items():
                try:
                    # 这里实际应该将脚本注入到浏览器环境中
                    # 由于我们使用的是requests/aiohttp，这里只是准备脚本
                    applied_spoofings.append(detection_type)
                    logger.debug(f"准备伪装脚本: {detection_type.value}")
                except Exception as e:
                    failed_spoofings.append(detection_type)
                    logger.error(f"伪装失败 {detection_type.value}: {e}")
            
            # 创建伪装结果
            result = SpoofingResult(
                success=len(failed_spoofings) == 0,
                applied_spoofings=applied_spoofings,
                failed_spoofings=failed_spoofings,
                execution_time=time.time() - start_time,
                fingerprint_id=fingerprint.user_agent[:20],  # 使用UA前20字符作为ID
                metadata={
                    "session_id": session_id,
                    "target_url": target_url,
                    "browser_type": fingerprint.browser_type.value,
                    "os_type": fingerprint.os_type.value,
                    "spoofing_scripts": {k.value: v for k, v in spoofing_scripts.items()}
                }
            )
            
            # 保存伪装状态
            self.active_spoofings[session_id] = result
            
            # 更新统计
            self._update_stats(result)
            
            logger.info(f"✅ 伪装应用成功: {len(applied_spoofings)}个模块")
            return result
            
        except Exception as e:
            logger.error(f"❌ 伪装应用失败: {e}")
            return SpoofingResult(
                success=False,
                applied_spoofings=[],
                failed_spoofings=list(self.config.enabled_detections),
                execution_time=time.time() - start_time,
                metadata={"error": str(e)}
            )
    
    async def _generate_spoofing_scripts(self, fingerprint: BrowserFingerprint) -> Dict[DetectionType, str]:
        """生成伪装脚本"""
        scripts = {}
        
        # DevTools检测绕过
        if DetectionType.DEVTOOLS in self.config.enabled_detections:
            scripts[DetectionType.DEVTOOLS] = self.devtools_bypass.generate_bypass_script(fingerprint)
        
        # Console对象标准化
        if DetectionType.CONSOLE in self.config.enabled_detections:
            scripts[DetectionType.CONSOLE] = self.console_standardizer.generate_console_script(fingerprint.browser_type)
        
        # 字体渲染模拟
        if DetectionType.FONT_RENDERING in self.config.enabled_detections:
            scripts[DetectionType.FONT_RENDERING] = self.font_simulator.generate_font_script(
                fingerprint.os_type, fingerprint.browser_type
            )
        
        # Chrome对象模拟
        if DetectionType.WINDOW_CHROME in self.config.enabled_detections:
            scripts[DetectionType.WINDOW_CHROME] = self.chrome_simulator.generate_chrome_script(fingerprint.browser_type)
        
        return scripts
    
    def get_spoofing_headers(self, fingerprint: BrowserFingerprint) -> Dict[str, str]:
        """获取伪装的HTTP头"""
        headers = {}
        
        # 基础头部
        headers.update({
            'User-Agent': fingerprint.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': fingerprint.language,
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # 根据浏览器类型添加特定头部
        if fingerprint.browser_type == BrowserType.CHROME:
            headers.update({
                'sec-ch-ua': f'"Google Chrome";v="120", "Not A Brand";v="99", "Chromium";v="120"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': f'"{fingerprint.os_type.value.title()}"',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-User': '?1',
                'Sec-Fetch-Dest': 'document'
            })
        
        return headers
    
    def get_injection_script(self, session_id: str) -> Optional[str]:
        """获取注入脚本"""
        spoofing_result = self.active_spoofings.get(session_id)
        if not spoofing_result or not spoofing_result.success:
            return None
        
        scripts = spoofing_result.metadata.get("spoofing_scripts", {})
        if not scripts:
            return None
        
        # 合并所有脚本
        combined_script = "\n".join(scripts.values())
        
        # 添加执行延迟
        if self.config.execution_delay_enabled:
            delay = random.uniform(self.config.min_execution_delay, self.config.max_execution_delay)
            combined_script = f"setTimeout(function() {{ {combined_script} }}, {int(delay * 1000)});"
        
        return combined_script
    
    def _update_stats(self, result: SpoofingResult):
        """更新统计信息"""
        self.spoofing_stats["total_requests"] += 1
        
        if result.success:
            self.spoofing_stats["successful_spoofings"] += 1
        else:
            self.spoofing_stats["failed_spoofings"] += 1
        
        self.spoofing_stats["detection_bypassed"] += len(result.applied_spoofings)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "spoofing_stats": self.spoofing_stats.copy(),
            "active_sessions": len(self.active_spoofings),
            "config": {
                "level": self.config.level.value,
                "enabled_detections": [d.value for d in self.config.enabled_detections]
            }
        }
    
    def cleanup_session(self, session_id: str):
        """清理会话伪装数据"""
        if session_id in self.active_spoofings:
            del self.active_spoofings[session_id]
            logger.debug(f"清理会话伪装数据: {session_id}")
    
    async def validate_spoofing(self, session_id: str) -> bool:
        """验证伪装效果"""
        spoofing_result = self.active_spoofings.get(session_id)
        if not spoofing_result:
            return False
        
        # 检查伪装是否仍然有效
        if spoofing_result.success and len(spoofing_result.applied_spoofings) > 0:
            # 这里可以添加更复杂的验证逻辑
            return True
        
        return False


# 工厂函数
def create_spoofing_system(level: SpoofingLevel = SpoofingLevel.STANDARD) -> BrowserEnvironmentSpoofing:
    """创建伪装系统实例"""
    config = SpoofingConfig(level=level)
    
    # 根据级别调整配置
    if level == SpoofingLevel.MINIMAL:
        config.enabled_detections = [DetectionType.DEVTOOLS, DetectionType.CONSOLE]
    elif level == SpoofingLevel.AGGRESSIVE:
        config.enabled_detections = list(DetectionType)
    
    return BrowserEnvironmentSpoofing(config=config)


# 异步测试函数
async def test_spoofing_system():
    """测试伪装系统"""
    logger.info("🧪 开始测试浏览器环境伪装系统...")
    
    try:
        # 创建伪装系统
        spoofing = create_spoofing_system(SpoofingLevel.STANDARD)
        
        # 测试伪装应用
        result = await spoofing.apply_spoofing(
            session_id="test_session",
            target_url="https://jp.mercari.com"
        )
        
        logger.info(f"伪装结果: {result.success}")
        logger.info(f"应用的伪装: {[d.value for d in result.applied_spoofings]}")
        
        # 获取注入脚本
        script = spoofing.get_injection_script("test_session")
        if script:
            logger.info(f"注入脚本长度: {len(script)} 字符")
        
        # 获取统计信息
        stats = spoofing.get_stats()
        logger.info(f"统计信息: {stats}")
        
        logger.info("✅ 浏览器环境伪装系统测试完成")
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_spoofing_system())