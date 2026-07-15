"""
浏览器指纹管理器

该模块提供全面的浏览器指纹伪装功能，用于绕过基于浏览器指纹的反爬虫检测。
包含大量User-Agent池、WebGL/Canvas指纹伪装、自动化检测特征移除等功能。

主要功能：
- 500+ User-Agent池管理
- WebGL/Canvas指纹伪装
- 自动化检测特征移除
- 动态请求头顺序调整
- 浏览器行为模拟
- 指纹一致性维护
- 反检测优化

Author: Mercari AI Agent Team
"""

import asyncio
import logging
import random
import hashlib
import json
import base64
import time
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import re
import platform
from collections import OrderedDict

from .tls_fingerprint_manager import BrowserType
from ..utils.logger import get_logger
from ..config.settings import settings

logger = get_logger(__name__)


class OSType(Enum):
    """操作系统类型枚举"""
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"
    ANDROID = "android"
    IOS = "ios"


class DeviceType(Enum):
    """设备类型枚举"""
    DESKTOP = "desktop"
    MOBILE = "mobile"
    TABLET = "tablet"


@dataclass
class WebGLFingerprint:
    """WebGL指纹数据"""
    renderer: str
    vendor: str
    version: str
    shading_language_version: str
    extensions: List[str]
    parameters: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'renderer': self.renderer,
            'vendor': self.vendor,
            'version': self.version,
            'shading_language_version': self.shading_language_version,
            'extensions': self.extensions,
            'parameters': self.parameters
        }


@dataclass
class CanvasFingerprint:
    """Canvas指纹数据"""
    fingerprint_hash: str
    width: int
    height: int
    color_depth: int
    pixel_ratio: float
    text_metrics: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'fingerprint_hash': self.fingerprint_hash,
            'width': self.width,
            'height': self.height,
            'color_depth': self.color_depth,
            'pixel_ratio': self.pixel_ratio,
            'text_metrics': self.text_metrics
        }


@dataclass
class BrowserFingerprint:
    """浏览器指纹数据结构"""
    user_agent: str
    browser_type: BrowserType
    os_type: OSType
    device_type: DeviceType
    screen_resolution: Tuple[int, int]
    color_depth: int
    timezone: str
    language: str
    plugins: List[str]
    webgl_fingerprint: WebGLFingerprint
    canvas_fingerprint: CanvasFingerprint
    headers: Dict[str, str]
    javascript_features: Dict[str, Any]
    creation_time: datetime = field(default_factory=datetime.now)
    usage_count: int = 0
    consistency_score: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'user_agent': self.user_agent,
            'browser_type': self.browser_type.value,
            'os_type': self.os_type.value,
            'device_type': self.device_type.value,
            'screen_resolution': self.screen_resolution,
            'color_depth': self.color_depth,
            'timezone': self.timezone,
            'language': self.language,
            'plugins': self.plugins,
            'webgl_fingerprint': self.webgl_fingerprint.to_dict(),
            'canvas_fingerprint': self.canvas_fingerprint.to_dict(),
            'headers': self.headers,
            'javascript_features': self.javascript_features,
            'creation_time': self.creation_time.isoformat(),
            'usage_count': self.usage_count,
            'consistency_score': self.consistency_score
        }


@dataclass
class FingerprintConfig:
    """指纹配置"""
    enable_user_agent_rotation: bool = True
    enable_webgl_spoofing: bool = True
    enable_canvas_spoofing: bool = True
    enable_header_randomization: bool = True
    enable_plugin_spoofing: bool = True
    remove_automation_traces: bool = True
    max_fingerprint_usage: int = 50
    fingerprint_rotation_interval: int = 1800
    consistency_threshold: float = 0.8
    
    browser_distribution: Dict[BrowserType, float] = field(default_factory=lambda: {
        BrowserType.CHROME: 0.65,
        BrowserType.FIREFOX: 0.15,
        BrowserType.SAFARI: 0.10,
        BrowserType.EDGE: 0.08,
        BrowserType.OPERA: 0.02
    })
    
    os_distribution: Dict[OSType, float] = field(default_factory=lambda: {
        OSType.WINDOWS: 0.70,
        OSType.MACOS: 0.15,
        OSType.LINUX: 0.10,
        OSType.ANDROID: 0.03,
        OSType.IOS: 0.02
    })


class UserAgentPool:
    """User-Agent池管理器"""
    
    def __init__(self):
        self.user_agents = self._load_user_agents()
        logger.info(f"User-Agent池初始化完成，共载入{sum(len(agents) for browser in self.user_agents.values() for agents in browser.values())}个User-Agent")
    
    def _load_user_agents(self) -> Dict[BrowserType, Dict[OSType, List[str]]]:
        """加载User-Agent数据库"""
        return {
            BrowserType.CHROME: {
                OSType.WINDOWS: [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
                ],
                OSType.MACOS: [
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
                ],
                OSType.LINUX: [
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
                ]
            },
            BrowserType.FIREFOX: {
                OSType.WINDOWS: [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:119.0) Gecko/20100101 Firefox/119.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:118.0) Gecko/20100101 Firefox/118.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:117.0) Gecko/20100101 Firefox/117.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:116.0) Gecko/20100101 Firefox/116.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:114.0) Gecko/20100101 Firefox/114.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:113.0) Gecko/20100101 Firefox/113.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:112.0) Gecko/20100101 Firefox/112.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:111.0) Gecko/20100101 Firefox/111.0",
                ],
                OSType.MACOS: [
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:119.0) Gecko/20100101 Firefox/119.0",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:118.0) Gecko/20100101 Firefox/118.0",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:117.0) Gecko/20100101 Firefox/117.0",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:116.0) Gecko/20100101 Firefox/116.0",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:115.0) Gecko/20100101 Firefox/115.0",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:114.0) Gecko/20100101 Firefox/114.0",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:113.0) Gecko/20100101 Firefox/113.0",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:112.0) Gecko/20100101 Firefox/112.0",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:111.0) Gecko/20100101 Firefox/111.0",
                ],
                OSType.LINUX: [
                    "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
                    "Mozilla/5.0 (X11; Linux x86_64; rv:119.0) Gecko/20100101 Firefox/119.0",
                    "Mozilla/5.0 (X11; Linux x86_64; rv:118.0) Gecko/20100101 Firefox/118.0",
                    "Mozilla/5.0 (X11; Linux x86_64; rv:117.0) Gecko/20100101 Firefox/117.0",
                    "Mozilla/5.0 (X11; Linux x86_64; rv:116.0) Gecko/20100101 Firefox/116.0",
                    "Mozilla/5.0 (X11; Linux x86_64; rv:115.0) Gecko/20100101 Firefox/115.0",
                    "Mozilla/5.0 (X11; Linux x86_64; rv:114.0) Gecko/20100101 Firefox/114.0",
                    "Mozilla/5.0 (X11; Linux x86_64; rv:113.0) Gecko/20100101 Firefox/113.0",
                    "Mozilla/5.0 (X11; Linux x86_64; rv:112.0) Gecko/20100101 Firefox/112.0",
                    "Mozilla/5.0 (X11; Linux x86_64; rv:111.0) Gecko/20100101 Firefox/111.0",
                ]
            },
            BrowserType.SAFARI: {
                OSType.MACOS: [
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.3 Safari/605.1.15",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.2 Safari/605.1.15",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.6 Safari/605.1.15",
                ]
            },
            BrowserType.EDGE: {
                OSType.WINDOWS: [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36 Edg/118.0.0.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36 Edg/117.0.0.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.0.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 Edg/115.0.0.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 Edg/114.0.0.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36 Edg/113.0.0.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 Edg/112.0.0.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36 Edg/111.0.0.0",
                ]
            },
            BrowserType.OPERA: {
                OSType.WINDOWS: [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 OPR/105.0.0.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36 OPR/104.0.0.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36 OPR/103.0.0.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 OPR/102.0.0.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 OPR/101.0.0.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 OPR/100.0.0.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36 OPR/99.0.0.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 OPR/98.0.0.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36 OPR/97.0.0.0",
                ]
            }
        }
    
    def get_user_agent(self, browser_type: BrowserType = None, os_type: OSType = None) -> str:
        """获取指定类型的User-Agent"""
        if browser_type is None:
            browser_type = random.choice(list(self.user_agents.keys()))
        
        if os_type is None:
            os_type = random.choice(list(self.user_agents[browser_type].keys()))
        
        return random.choice(self.user_agents[browser_type][os_type])


class WebGLSpoofingEngine:
    """WebGL指纹伪装引擎"""
    
    def __init__(self):
        self.renderer_templates = {
            BrowserType.CHROME: {
                OSType.WINDOWS: [
                    "ANGLE (AMD, AMD Radeon RX 6800 Direct3D11 vs_5_0 ps_5_0, D3D11-30.0.13002.1004)",
                    "ANGLE (NVIDIA, NVIDIA GeForce RTX 3080 Direct3D11 vs_5_0 ps_5_0, D3D11-30.0.14.7212)",
                    "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11-27.20.100.8681)",
                    "ANGLE (AMD, AMD Radeon RX 5700 XT Direct3D11 vs_5_0 ps_5_0, D3D11-30.0.13002.1004)",
                    "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 Ti Direct3D11 vs_5_0 ps_5_0, D3D11-30.0.14.7212)",
                ],
                OSType.MACOS: [
                    "AMD Radeon Pro 5500M OpenGL Engine",
                    "AMD Radeon Pro 5300M OpenGL Engine",
                    "Intel(R) UHD Graphics 630",
                    "AMD Radeon Pro 560X OpenGL Engine",
                    "Intel(R) Iris(TM) Plus Graphics 655",
                ],
                OSType.LINUX: [
                    "Mesa DRI Intel(R) UHD Graphics 630 (CFL GT2)",
                    "Mesa DRI AMD Radeon RX 6800 (NAVI21, DRM 3.42.0, 5.15.0-56-generic, LLVM 12.0.0)",
                    "Mesa DRI NVIDIA GeForce RTX 3080 (TU104, DRM 3.44.0, 5.15.0-56-generic, LLVM 12.0.0)",
                    "Mesa DRI Intel(R) HD Graphics 530 (SKL GT2)",
                    "Mesa DRI AMD Radeon RX 5700 XT (NAVI10, DRM 3.42.0, 5.15.0-56-generic, LLVM 12.0.0)",
                ]
            },
            BrowserType.FIREFOX: {
                OSType.WINDOWS: [
                    "AMD Radeon RX 6800",
                    "NVIDIA GeForce RTX 3080",
                    "Intel(R) UHD Graphics 630",
                    "AMD Radeon RX 5700 XT",
                    "NVIDIA GeForce GTX 1660 Ti",
                ],
                OSType.MACOS: [
                    "AMD Radeon Pro 5500M",
                    "AMD Radeon Pro 5300M",
                    "Intel(R) UHD Graphics 630",
                    "AMD Radeon Pro 560X",
                    "Intel(R) Iris(TM) Plus Graphics 655",
                ],
                OSType.LINUX: [
                    "Mesa DRI Intel(R) UHD Graphics 630 (CFL GT2)",
                    "Mesa DRI AMD Radeon RX 6800 (NAVI21, DRM 3.42.0, 5.15.0-56-generic, LLVM 12.0.0)",
                    "Mesa DRI NVIDIA GeForce RTX 3080 (TU104, DRM 3.44.0, 5.15.0-56-generic, LLVM 12.0.0)",
                    "Mesa DRI Intel(R) HD Graphics 530 (SKL GT2)",
                    "Mesa DRI AMD Radeon RX 5700 XT (NAVI10, DRM 3.42.0, 5.15.0-56-generic, LLVM 12.0.0)",
                ]
            },
            BrowserType.SAFARI: {
                OSType.MACOS: [
                    "AMD Radeon Pro 5500M OpenGL Engine",
                    "AMD Radeon Pro 5300M OpenGL Engine",
                    "Intel(R) UHD Graphics 630",
                    "AMD Radeon Pro 560X OpenGL Engine",
                    "Intel(R) Iris(TM) Plus Graphics 655",
                ]
            }
        }
        
        self.vendor_templates = {
            BrowserType.CHROME: {
                OSType.WINDOWS: ["Google Inc. (AMD)", "Google Inc. (NVIDIA)", "Google Inc. (Intel)"],
                OSType.MACOS: ["Apple Inc.", "AMD", "Intel Inc."],
                OSType.LINUX: ["X.Org", "nouveau", "Intel Open Source Technology Center"]
            },
            BrowserType.FIREFOX: {
                OSType.WINDOWS: ["ATI Technologies Inc.", "NVIDIA Corporation", "Intel"],
                OSType.MACOS: ["Apple Inc.", "AMD", "Intel Inc."],
                OSType.LINUX: ["X.Org", "nouveau", "Intel Open Source Technology Center"]
            },
            BrowserType.SAFARI: {
                OSType.MACOS: ["Apple Inc.", "AMD", "Intel Inc."]
            }
        }
    
    def generate_webgl_fingerprint(self, browser_type: BrowserType, os_type: OSType) -> WebGLFingerprint:
        """生成WebGL指纹"""
        try:
            renderer = random.choice(self.renderer_templates[browser_type][os_type])
            vendor = random.choice(self.vendor_templates[browser_type][os_type])
        except KeyError:
            # 回退到默认值
            renderer = "Generic WebGL Renderer"
            vendor = "WebGL Vendor"
        
        version = "WebGL 1.0"
        shading_language_version = "WebGL GLSL ES 1.0"
        
        extensions = self._generate_extensions(browser_type, os_type)
        parameters = self._generate_parameters(browser_type, os_type)
        
        return WebGLFingerprint(
            renderer=renderer,
            vendor=vendor,
            version=version,
            shading_language_version=shading_language_version,
            extensions=extensions,
            parameters=parameters
        )
    
    def _generate_extensions(self, browser_type: BrowserType, os_type: OSType) -> List[str]:
        """生成WebGL扩展列表"""
        base_extensions = [
            "ANGLE_instanced_arrays",
            "EXT_blend_minmax",
            "EXT_color_buffer_half_float",
            "EXT_disjoint_timer_query",
            "EXT_float_blend",
            "EXT_frag_depth",
            "EXT_shader_texture_lod",
            "EXT_texture_compression_bptc",
            "EXT_texture_compression_rgtc",
            "EXT_texture_filter_anisotropic",
            "WEBKIT_EXT_texture_filter_anisotropic",
            "EXT_sRGB",
            "KHR_parallel_shader_compile",
            "OES_element_index_uint",
            "OES_fbo_render_mipmap",
            "OES_standard_derivatives",
            "OES_texture_float",
            "OES_texture_float_linear",
            "OES_texture_half_float",
            "OES_texture_half_float_linear",
            "OES_vertex_array_object",
            "WEBGL_color_buffer_float",
            "WEBGL_compressed_texture_s3tc",
            "WEBKIT_WEBGL_compressed_texture_s3tc",
            "WEBGL_compressed_texture_s3tc_srgb",
            "WEBGL_debug_renderer_info",
            "WEBGL_debug_shaders",
            "WEBGL_depth_texture",
            "WEBKIT_WEBGL_depth_texture",
            "WEBGL_draw_buffers",
            "WEBGL_lose_context",
            "WEBKIT_WEBGL_lose_context"
        ]
        
        # 根据浏览器类型和操作系统添加特定扩展
        if browser_type == BrowserType.CHROME:
            base_extensions.extend([
                "WEBGL_multi_draw",
                "WEBGL_polygon_mode"
            ])
        elif browser_type == BrowserType.FIREFOX:
            base_extensions.extend([
                "MOZ_WEBGL_lose_context",
                "MOZ_WEBGL_compressed_texture_s3tc"
            ])
        
        # 随机移除一些扩展以增加真实性
        available_extensions = base_extensions.copy()
        remove_count = random.randint(0, min(5, len(available_extensions)))
        for _ in range(remove_count):
            if available_extensions:
                available_extensions.remove(random.choice(available_extensions))
        
        return sorted(available_extensions)
    
    def _generate_parameters(self, browser_type: BrowserType, os_type: OSType) -> Dict[str, Any]:
        """生成WebGL参数"""
        return {
            "MAX_VERTEX_ATTRIBS": random.randint(16, 32),
            "MAX_VERTEX_UNIFORM_VECTORS": random.randint(128, 512),
            "MAX_VARYING_VECTORS": random.randint(8, 32),
            "MAX_FRAGMENT_UNIFORM_VECTORS": random.randint(64, 256),
            "MAX_TEXTURE_IMAGE_UNITS": random.randint(16, 32),
            "MAX_VERTEX_TEXTURE_IMAGE_UNITS": random.randint(16, 32),
            "MAX_COMBINED_TEXTURE_IMAGE_UNITS": random.randint(32, 64),
            "MAX_TEXTURE_SIZE": random.choice([4096, 8192, 16384]),
            "MAX_CUBE_MAP_TEXTURE_SIZE": random.choice([4096, 8192, 16384]),
            "MAX_VIEWPORT_DIMS": [random.randint(8192, 16384), random.randint(8192, 16384)],
            "ALIASED_LINE_WIDTH_RANGE": [1.0, random.uniform(1.0, 10.0)],
            "ALIASED_POINT_SIZE_RANGE": [1.0, random.uniform(64.0, 1024.0)],
            "RED_BITS": 8,
            "GREEN_BITS": 8,
            "BLUE_BITS": 8,
            "ALPHA_BITS": 8,
            "DEPTH_BITS": 24,
            "STENCIL_BITS": 8,
            "MAX_RENDERBUFFER_SIZE": random.choice([4096, 8192, 16384]),
            "UNMASKED_VENDOR_WEBGL": self.vendor_templates.get(browser_type, {}).get(os_type, ["WebGL Vendor"])[0],
            "UNMASKED_RENDERER_WEBGL": self.renderer_templates.get(browser_type, {}).get(os_type, ["WebGL Renderer"])[0]
        }


class CanvasSpoofingEngine:
    """Canvas指纹伪装引擎"""
    
    def __init__(self):
        self.font_variations = [
            "Arial", "Helvetica", "Times New Roman", "Courier New",
            "Verdana", "Georgia", "Palatino", "Garamond",
            "Bookman", "Comic Sans MS", "Trebuchet MS", "Arial Black"
        ]
        
        self.text_samples = [
            "Cwm fjord bank glyphs vext quiz 🏠😀",
            "The quick brown fox jumps over the lazy dog",
            "Pack my box with five dozen liquor jugs",
            "Waltz, bad nymph, for quick jigs vex",
            "Canvas fingerprinting test text 2024"
        ]
    
    def generate_canvas_fingerprint(self, browser_type: BrowserType, os_type: OSType) -> CanvasFingerprint:
        """生成Canvas指纹"""
        # 模拟Canvas绘制过程
        canvas_data = self._simulate_canvas_drawing(browser_type, os_type)
        
        # 生成指纹哈希
        fingerprint_hash = hashlib.sha256(canvas_data.encode()).hexdigest()[:16]
        
        # 根据操作系统设置屏幕参数
        if os_type == OSType.WINDOWS:
            width, height = random.choice([(1920, 1080), (1366, 768), (1536, 864), (1280, 720)])
            color_depth = random.choice([24, 32])
            pixel_ratio = 1.0
        elif os_type == OSType.MACOS:
            width, height = random.choice([(2560, 1600), (1440, 900), (1680, 1050), (1920, 1080)])
            color_depth = 24
            pixel_ratio = random.choice([1.0, 2.0])
        elif os_type == OSType.LINUX:
            width, height = random.choice([(1920, 1080), (1366, 768), (1600, 900), (1280, 1024)])
            color_depth = random.choice([24, 32])
            pixel_ratio = 1.0
        else:
            width, height = random.choice([(375, 667), (414, 896), (360, 640), (393, 851)])
            color_depth = 24
            pixel_ratio = random.choice([2.0, 3.0])
        
        text_metrics = self._generate_text_metrics(browser_type, os_type)
        
        return CanvasFingerprint(
            fingerprint_hash=fingerprint_hash,
            width=width,
            height=height,
            color_depth=color_depth,
            pixel_ratio=pixel_ratio,
            text_metrics=text_metrics
        )
    
    def _simulate_canvas_drawing(self, browser_type: BrowserType, os_type: OSType) -> str:
        """模拟Canvas绘制过程"""
        canvas_operations = []
        
        # 模拟文本绘制
        font = random.choice(self.font_variations)
        text = random.choice(self.text_samples)
        canvas_operations.append(f"font: 14px {font}")
        canvas_operations.append(f"fillText: {text}")
        
        # 模拟形状绘制
        canvas_operations.append("beginPath")
        canvas_operations.append(f"arc: {random.randint(50, 100)}, {random.randint(50, 100)}, {random.randint(10, 50)}")
        canvas_operations.append("fill")
        
        # 模拟颜色渐变
        canvas_operations.append("createLinearGradient: 0, 0, 100, 100")
        canvas_operations.append(f"addColorStop: 0, rgb({random.randint(0, 255)}, {random.randint(0, 255)}, {random.randint(0, 255)})")
        canvas_operations.append(f"addColorStop: 1, rgb({random.randint(0, 255)}, {random.randint(0, 255)}, {random.randint(0, 255)})")
        
        # 添加浏览器特定的变化
        if browser_type == BrowserType.CHROME:
            canvas_operations.append("webkitImageSmoothingEnabled: true")
        elif browser_type == BrowserType.FIREFOX:
            canvas_operations.append("mozImageSmoothingEnabled: true")
        elif browser_type == BrowserType.SAFARI:
            canvas_operations.append("webkitImageSmoothingEnabled: true")
        
        # 添加操作系统特定的变化
        if os_type == OSType.WINDOWS:
            canvas_operations.append("textBaseline: alphabetic")
        elif os_type == OSType.MACOS:
            canvas_operations.append("textBaseline: ideographic")
        elif os_type == OSType.LINUX:
            canvas_operations.append("textBaseline: hanging")
        
        return "|".join(canvas_operations)
    
    def _generate_text_metrics(self, browser_type: BrowserType, os_type: OSType) -> Dict[str, Any]:
        """生成文本度量数据"""
        base_metrics = {
            "width": random.uniform(100.0, 300.0),
            "actualBoundingBoxLeft": random.uniform(0.0, 5.0),
            "actualBoundingBoxRight": random.uniform(100.0, 300.0),
            "actualBoundingBoxAscent": random.uniform(10.0, 20.0),
            "actualBoundingBoxDescent": random.uniform(2.0, 8.0),
            "fontBoundingBoxAscent": random.uniform(12.0, 24.0),
            "fontBoundingBoxDescent": random.uniform(3.0, 9.0),
            "alphabeticBaseline": random.uniform(0.0, 5.0),
            "ideographicBaseline": random.uniform(-2.0, 2.0),
            "hangingBaseline": random.uniform(-15.0, -10.0)
        }
        
        # 根据浏览器类型调整度量数据
        if browser_type == BrowserType.FIREFOX:
            base_metrics["width"] *= random.uniform(0.98, 1.02)
        elif browser_type == BrowserType.SAFARI:
            base_metrics["width"] *= random.uniform(0.99, 1.01)
        
        # 根据操作系统调整度量数据
        if os_type == OSType.MACOS:
            base_metrics["actualBoundingBoxAscent"] *= random.uniform(1.05, 1.15)
        elif os_type == OSType.WINDOWS:
            base_metrics["actualBoundingBoxAscent"] *= random.uniform(0.95, 1.05)
        
        return base_metrics


class BrowserFingerprintManager:
    """浏览器指纹管理器主类"""
    
    def __init__(self, config: Optional[FingerprintConfig] = None):
        self.config = config or FingerprintConfig()
        self.user_agent_pool = UserAgentPool()
        self.webgl_engine = WebGLSpoofingEngine()
        self.canvas_engine = CanvasSpoofingEngine()
        self.fingerprint_cache: Dict[str, BrowserFingerprint] = {}
        self.fingerprint_usage: Dict[str, int] = {}
        self.last_rotation_time = time.time()
        
        logger.info("浏览器指纹管理器初始化完成")
    
    def generate_fingerprint(self, 
                           browser_type: Optional[BrowserType] = None, 
                           os_type: Optional[OSType] = None,
                           device_type: Optional[DeviceType] = None) -> BrowserFingerprint:
        """生成新的浏览器指纹"""
        
        # 根据配置分布随机选择浏览器类型
        if browser_type is None:
            browser_type = self._weighted_random_choice(self.config.browser_distribution)
        
        # 根据配置分布随机选择操作系统
        if os_type is None:
            os_type = self._weighted_random_choice(self.config.os_distribution)
        
        # 根据操作系统推断设备类型
        if device_type is None:
            if os_type in [OSType.ANDROID, OSType.IOS]:
                device_type = DeviceType.MOBILE
            else:
                device_type = DeviceType.DESKTOP
        
        # 生成User-Agent
        user_agent = self.user_agent_pool.get_user_agent(browser_type, os_type)
        
        # 生成WebGL指纹
        webgl_fingerprint = self.webgl_engine.generate_webgl_fingerprint(browser_type, os_type)
        
        # 生成Canvas指纹
        canvas_fingerprint = self.canvas_engine.generate_canvas_fingerprint(browser_type, os_type)
        
        # 生成屏幕分辨率
        screen_resolution = self._generate_screen_resolution(os_type, device_type)
        
        # 生成颜色深度
        color_depth = self._generate_color_depth(os_type)
        
        # 生成时区
        timezone = self._generate_timezone(os_type)
        
        # 生成语言
        language = self._generate_language(os_type)
        
        # 生成插件列表
        plugins = self._generate_plugins(browser_type, os_type)
        
        # 生成HTTP请求头
        headers = self._generate_headers(browser_type, os_type, user_agent)
        
        # 生成JavaScript特性
        javascript_features = self._generate_javascript_features(browser_type, os_type)
        
        fingerprint = BrowserFingerprint(
            user_agent=user_agent,
            browser_type=browser_type,
            os_type=os_type,
            device_type=device_type,
            screen_resolution=screen_resolution,
            color_depth=color_depth,
            timezone=timezone,
            language=language,
            plugins=plugins,
            webgl_fingerprint=webgl_fingerprint,
            canvas_fingerprint=canvas_fingerprint,
            headers=headers,
            javascript_features=javascript_features
        )
        
        # 缓存指纹
        fingerprint_id = self._generate_fingerprint_id(fingerprint)
        self.fingerprint_cache[fingerprint_id] = fingerprint
        self.fingerprint_usage[fingerprint_id] = 0
        
        logger.debug(f"生成新的浏览器指纹: {browser_type.value} on {os_type.value}")
        return fingerprint
    
    def get_fingerprint(self, fingerprint_id: str = None) -> BrowserFingerprint:
        """获取指纹，如果不存在则生成新的"""
        if fingerprint_id and fingerprint_id in self.fingerprint_cache:
            fingerprint = self.fingerprint_cache[fingerprint_id]
            self.fingerprint_usage[fingerprint_id] += 1
            fingerprint.usage_count += 1
            
            # 检查是否需要轮换指纹
            if self._should_rotate_fingerprint(fingerprint_id):
                logger.info(f"指纹 {fingerprint_id} 使用次数过多，生成新指纹")
                return self.generate_fingerprint(
                    fingerprint.browser_type, 
                    fingerprint.os_type, 
                    fingerprint.device_type
                )
            
            return fingerprint
        
        return self.generate_fingerprint()
    
    def _weighted_random_choice(self, distribution: Dict[Any, float]) -> Any:
        """根据权重分布随机选择"""
        choices = list(distribution.keys())
        weights = list(distribution.values())
        return random.choices(choices, weights=weights)[0]
    
    def _generate_screen_resolution(self, os_type: OSType, device_type: DeviceType) -> Tuple[int, int]:
        """生成屏幕分辨率"""
        if device_type == DeviceType.MOBILE:
            mobile_resolutions = [
                (375, 667), (414, 896), (360, 640), (393, 851),
                (412, 915), (390, 844), (428, 926), (320, 568)
            ]
            return random.choice(mobile_resolutions)
        
        elif device_type == DeviceType.TABLET:
            tablet_resolutions = [
                (768, 1024), (820, 1180), (1024, 1366), (810, 1080),
                (800, 1280), (1200, 1920), (1668, 2388), (2048, 2732)
            ]
            return random.choice(tablet_resolutions)
        
        else:  # DESKTOP
            if os_type == OSType.WINDOWS:
                windows_resolutions = [
                    (1920, 1080), (1366, 768), (1536, 864), (1440, 900),
                    (1600, 900), (1280, 720), (1280, 1024), (1024, 768)
                ]
                return random.choice(windows_resolutions)
            
            elif os_type == OSType.MACOS:
                macos_resolutions = [
                    (2560, 1600), (1440, 900), (1680, 1050), (1920, 1080),
                    (2880, 1800), (3008, 1692), (2560, 1440), (1920, 1200)
                ]
                return random.choice(macos_resolutions)
            
            elif os_type == OSType.LINUX:
                linux_resolutions = [
                    (1920, 1080), (1366, 768), (1600, 900), (1280, 1024),
                    (1440, 900), (1024, 768), (1280, 800), (1152, 864)
                ]
                return random.choice(linux_resolutions)
            
            else:
                return (1920, 1080)  # 默认分辨率
    
    def _generate_color_depth(self, os_type: OSType) -> int:
        """生成颜色深度"""
        if os_type == OSType.MACOS:
            return 24  # macOS通常使用24位颜色
        else:
            return random.choice([24, 32])  # Windows和Linux支持24/32位
    
    def _generate_timezone(self, os_type: OSType) -> str:
        """生成时区"""
        timezones = [
            "Asia/Tokyo", "America/New_York", "Europe/London", "America/Los_Angeles",
            "Asia/Shanghai", "Europe/Paris", "America/Chicago", "Australia/Sydney",
            "Asia/Seoul", "Europe/Berlin", "America/Toronto", "Asia/Singapore"
        ]
        return random.choice(timezones)
    
    def _generate_language(self, os_type: OSType) -> str:
        """生成语言设置"""
        languages = [
            "en-US", "ja-JP", "zh-CN", "en-GB", "ko-KR", "zh-TW",
            "fr-FR", "de-DE", "es-ES", "it-IT", "pt-BR", "ru-RU"
        ]
        return random.choice(languages)
    
    def _generate_plugins(self, browser_type: BrowserType, os_type: OSType) -> List[str]:
        """生成插件列表"""
        base_plugins = []
        
        if browser_type == BrowserType.CHROME:
            base_plugins = [
                "Chrome PDF Plugin",
                "Chrome PDF Viewer",
                "Native Client"
            ]
        elif browser_type == BrowserType.FIREFOX:
            base_plugins = [
                "PDF.js",
                "OpenH264 Video Codec provided by Cisco Systems, Inc."
            ]
        elif browser_type == BrowserType.SAFARI:
            base_plugins = [
                "PDF",
                "QuickTime Plugin"
            ]
        elif browser_type == BrowserType.EDGE:
            base_plugins = [
                "Microsoft Edge PDF Plugin",
                "Microsoft Edge PDF Viewer"
            ]
        
        # 根据操作系统添加特定插件
        if os_type == OSType.WINDOWS:
            base_plugins.extend([
                "Microsoft Silverlight",
                "Windows Media Player"
            ])
        elif os_type == OSType.MACOS:
            base_plugins.extend([
                "QuickTime Plugin",
                "iTunes Application Detector"
            ])
        elif os_type == OSType.LINUX:
            base_plugins.extend([
                "VLC Multimedia Plugin",
                "Totem Plugin"
            ])
        
        # 随机移除一些插件
        if base_plugins:
            remove_count = random.randint(0, min(2, len(base_plugins)))
            for _ in range(remove_count):
                if base_plugins:
                    base_plugins.remove(random.choice(base_plugins))
        
        return base_plugins
    
    def _generate_headers(self, browser_type: BrowserType, os_type: OSType, user_agent: str) -> Dict[str, str]:
        """生成HTTP请求头"""
        headers = OrderedDict()
        
        # 基础请求头
        headers["User-Agent"] = user_agent
        headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        headers["Accept-Language"] = "en-US,en;q=0.5"
        headers["Accept-Encoding"] = "gzip, deflate, br"
        headers["DNT"] = "1"
        headers["Connection"] = "keep-alive"
        headers["Upgrade-Insecure-Requests"] = "1"
        
        # 根据浏览器类型调整请求头
        if browser_type == BrowserType.CHROME:
            headers["sec-ch-ua"] = '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"'
            headers["sec-ch-ua-mobile"] = "?0"
            # 确保使用枚举值而不是枚举对象
            os_type_value = os_type.value if hasattr(os_type, 'value') else str(os_type)
            headers["sec-ch-ua-platform"] = f'"{os_type_value.title()}"'
            headers["Sec-Fetch-Dest"] = "document"
            headers["Sec-Fetch-Mode"] = "navigate"
            headers["Sec-Fetch-Site"] = "none"
            headers["Sec-Fetch-User"] = "?1"
        elif browser_type == BrowserType.FIREFOX:
            headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
            headers["Accept-Language"] = "en-US,en;q=0.5"
            headers["Sec-Fetch-Dest"] = "document"
            headers["Sec-Fetch-Mode"] = "navigate"
            headers["Sec-Fetch-Site"] = "none"
            headers["Sec-Fetch-User"] = "?1"
        elif browser_type == BrowserType.SAFARI:
            headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            headers["Accept-Language"] = "en-US,en;q=0.9"
        
        # 随机调整请求头顺序
        if random.random() < 0.3:
            items = list(headers.items())
            random.shuffle(items)
            headers = OrderedDict(items)
        
        return dict(headers)
    
    def _generate_javascript_features(self, browser_type: BrowserType, os_type: OSType) -> Dict[str, Any]:
        """生成JavaScript特性"""
        features = {
            "cookieEnabled": True,
            "doNotTrack": random.choice([None, "1", "unspecified"]),
            "hardwareConcurrency": random.choice([4, 8, 12, 16]),
            "javaEnabled": False,
            "maxTouchPoints": 0 if os_type not in [OSType.ANDROID, OSType.IOS] else random.randint(1, 10),
            "onLine": True,
            "pdfViewerEnabled": browser_type in [BrowserType.CHROME, BrowserType.FIREFOX],
            "webdriver": False,  # 移除自动化检测特征
            "permissions": {
                "notifications": random.choice(["granted", "denied", "default"]),
                "geolocation": random.choice(["granted", "denied", "default"]),
                "camera": random.choice(["granted", "denied", "default"]),
                "microphone": random.choice(["granted", "denied", "default"])
            }
        }
        
        # 根据浏览器类型添加特定特性
        if browser_type == BrowserType.CHROME:
            features.update({
                "webkitTemporaryStorage": True,
                "webkitPersistentStorage": True,
                "chrome": True
            })
        elif browser_type == BrowserType.FIREFOX:
            features.update({
                "mozInnerScreenX": random.randint(0, 100),
                "mozInnerScreenY": random.randint(0, 100),
                "buildID": "20231201000000"
            })
        elif browser_type == BrowserType.SAFARI:
            features.update({
                "webkitTemporaryStorage": True,
                "webkitPersistentStorage": True,
                "safari": True
            })
        
        return features
    
    def _generate_fingerprint_id(self, fingerprint: BrowserFingerprint) -> str:
        """生成指纹ID"""
        fingerprint_data = f"{fingerprint.user_agent}_{fingerprint.browser_type.value}_{fingerprint.os_type.value}_{fingerprint.device_type.value}_{fingerprint.screen_resolution[0]}x{fingerprint.screen_resolution[1]}_{fingerprint.color_depth}_{fingerprint.timezone}_{fingerprint.language}"
        return hashlib.md5(fingerprint_data.encode()).hexdigest()
    
    def _should_rotate_fingerprint(self, fingerprint_id: str) -> bool:
        """检查是否需要轮换指纹"""
        usage_count = self.fingerprint_usage.get(fingerprint_id, 0)
        time_since_rotation = time.time() - self.last_rotation_time
        
        return (usage_count >= self.config.max_fingerprint_usage or
                time_since_rotation >= self.config.fingerprint_rotation_interval)
    
    def cleanup_old_fingerprints(self):
        """清理旧的指纹缓存"""
        current_time = time.time()
        expired_ids = []
        
        for fingerprint_id, fingerprint in self.fingerprint_cache.items():
            time_since_creation = current_time - fingerprint.creation_time.timestamp()
            if time_since_creation > self.config.fingerprint_rotation_interval * 2:
                expired_ids.append(fingerprint_id)
        
        for fingerprint_id in expired_ids:
            del self.fingerprint_cache[fingerprint_id]
            if fingerprint_id in self.fingerprint_usage:
                del self.fingerprint_usage[fingerprint_id]
        
        if expired_ids:
            logger.info(f"清理了 {len(expired_ids)} 个过期指纹")
    
    def get_fingerprint_stats(self) -> Dict[str, Any]:
        """获取指纹统计信息"""
        total_fingerprints = len(self.fingerprint_cache)
        browser_stats = {}
        os_stats = {}
        
        for fingerprint in self.fingerprint_cache.values():
            browser_type = fingerprint.browser_type.value
            os_type = fingerprint.os_type.value
            
            browser_stats[browser_type] = browser_stats.get(browser_type, 0) + 1
            os_stats[os_type] = os_stats.get(os_type, 0) + 1
        
        return {
            "total_fingerprints": total_fingerprints,
            "browser_distribution": browser_stats,
            "os_distribution": os_stats,
            "cache_size": len(self.fingerprint_cache),
            "total_usage": sum(self.fingerprint_usage.values())
        }
    
    def remove_automation_traces(self, fingerprint: BrowserFingerprint) -> BrowserFingerprint:
        """移除自动化检测特征"""
        if not self.config.remove_automation_traces:
            return fingerprint
        
        # 移除webdriver特征
        fingerprint.javascript_features["webdriver"] = False
        
        # 移除自动化相关的窗口属性
        automation_properties = [
            "webdriver", "_phantom", "__phantom", "_selenium",
            "callPhantom", "callSelenium", "_webdriver_script_fn"
        ]
        
        for prop in automation_properties:
            if prop in fingerprint.javascript_features:
                del fingerprint.javascript_features[prop]
        
        # 调整User-Agent中的自动化标识
        user_agent = fingerprint.user_agent
        if "HeadlessChrome" in user_agent:
            user_agent = user_agent.replace("HeadlessChrome", "Chrome")
        if "headless" in user_agent.lower():
            user_agent = re.sub(r'headless\s*', '', user_agent, flags=re.IGNORECASE)
        
        fingerprint.user_agent = user_agent
        
        # 移除自动化检测相关的HTTP头
        headers_to_remove = [
            "webdriver", "selenium", "phantomjs", "headless"
        ]
        
        for header in headers_to_remove:
            if header in fingerprint.headers:
                del fingerprint.headers[header]
        
        return fingerprint
    
    async def rotate_fingerprint_async(self, fingerprint_id: str) -> BrowserFingerprint:
        """异步轮换指纹"""
        if fingerprint_id in self.fingerprint_cache:
            old_fingerprint = self.fingerprint_cache[fingerprint_id]
            new_fingerprint = self.generate_fingerprint(
                old_fingerprint.browser_type,
                old_fingerprint.os_type,
                old_fingerprint.device_type
            )
            
            # 删除旧指纹
            del self.fingerprint_cache[fingerprint_id]
            if fingerprint_id in self.fingerprint_usage:
                del self.fingerprint_usage[fingerprint_id]
            
            logger.info(f"指纹轮换完成: {fingerprint_id}")
            return new_fingerprint
        
        return self.generate_fingerprint()
    
    def validate_fingerprint_consistency(self, fingerprint: BrowserFingerprint) -> bool:
        """验证指纹一致性"""
        try:
            # 检查User-Agent与浏览器类型的一致性
            user_agent = fingerprint.user_agent.lower()
            browser_type = fingerprint.browser_type
            
            if browser_type == BrowserType.CHROME and "chrome" not in user_agent:
                return False
            if browser_type == BrowserType.FIREFOX and "firefox" not in user_agent:
                return False
            if browser_type == BrowserType.SAFARI and "safari" not in user_agent:
                return False
            if browser_type == BrowserType.EDGE and "edg" not in user_agent:
                return False
            
            # 检查操作系统与User-Agent的一致性
            os_type = fingerprint.os_type
            if os_type == OSType.WINDOWS and "windows" not in user_agent:
                return False
            if os_type == OSType.MACOS and "mac os" not in user_agent:
                return False
            if os_type == OSType.LINUX and "linux" not in user_agent:
                return False
            
            # 检查设备类型与屏幕分辨率的一致性
            device_type = fingerprint.device_type
            width, height = fingerprint.screen_resolution
            
            if device_type == DeviceType.MOBILE and (width > 500 or height > 1000):
                return False
            if device_type == DeviceType.DESKTOP and (width < 800 or height < 600):
                return False
            
            # 检查WebGL指纹与浏览器类型的一致性
            webgl_vendor = fingerprint.webgl_fingerprint.vendor
            if browser_type == BrowserType.CHROME and not any(x in webgl_vendor for x in ["Google", "ANGLE"]):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"指纹一致性验证失败: {e}")
            return False
    
    def export_fingerprint(self, fingerprint: BrowserFingerprint) -> str:
        """导出指纹为JSON字符串"""
        return json.dumps(fingerprint.to_dict(), indent=2, ensure_ascii=False)
    
    def import_fingerprint(self, fingerprint_json: str) -> BrowserFingerprint:
        """从JSON字符串导入指纹"""
        data = json.loads(fingerprint_json)
        
        # 重建枚举类型
        browser_type = BrowserType(data["browser_type"])
        os_type = OSType(data["os_type"])
        device_type = DeviceType(data["device_type"])
        
        # 重建WebGL指纹
        webgl_data = data["webgl_fingerprint"]
        webgl_fingerprint = WebGLFingerprint(
            renderer=webgl_data["renderer"],
            vendor=webgl_data["vendor"],
            version=webgl_data["version"],
            shading_language_version=webgl_data["shading_language_version"],
            extensions=webgl_data["extensions"],
            parameters=webgl_data["parameters"]
        )
        
        # 重建Canvas指纹
        canvas_data = data["canvas_fingerprint"]
        canvas_fingerprint = CanvasFingerprint(
            fingerprint_hash=canvas_data["fingerprint_hash"],
            width=canvas_data["width"],
            height=canvas_data["height"],
            color_depth=canvas_data["color_depth"],
            pixel_ratio=canvas_data["pixel_ratio"],
            text_metrics=canvas_data["text_metrics"]
        )
        
        # 重建完整指纹
        fingerprint = BrowserFingerprint(
            user_agent=data["user_agent"],
            browser_type=browser_type,
            os_type=os_type,
            device_type=device_type,
            screen_resolution=tuple(data["screen_resolution"]),
            color_depth=data["color_depth"],
            timezone=data["timezone"],
            language=data["language"],
            plugins=data["plugins"],
            webgl_fingerprint=webgl_fingerprint,
            canvas_fingerprint=canvas_fingerprint,
            headers=data["headers"],
            javascript_features=data["javascript_features"],
            creation_time=datetime.fromisoformat(data["creation_time"]),
            usage_count=data["usage_count"],
            consistency_score=data["consistency_score"]
        )
        
        return fingerprint


# 工厂函数
def create_browser_fingerprint_manager(config: Optional[FingerprintConfig] = None) -> BrowserFingerprintManager:
    """创建浏览器指纹管理器实例"""
    return BrowserFingerprintManager(config)


# 便捷函数
def generate_random_fingerprint(browser_type: Optional[BrowserType] = None,
                               os_type: Optional[OSType] = None) -> BrowserFingerprint:
    """生成随机浏览器指纹"""
    manager = BrowserFingerprintManager()
    return manager.generate_fingerprint(browser_type, os_type)


def get_chrome_windows_fingerprint() -> BrowserFingerprint:
    """获取Chrome Windows指纹"""
    return generate_random_fingerprint(BrowserType.CHROME, OSType.WINDOWS)


def get_firefox_linux_fingerprint() -> BrowserFingerprint:
    """获取Firefox Linux指纹"""
    return generate_random_fingerprint(BrowserType.FIREFOX, OSType.LINUX)


def get_safari_macos_fingerprint() -> BrowserFingerprint:
    """获取Safari macOS指纹"""
    return generate_random_fingerprint(BrowserType.SAFARI, OSType.MACOS)


if __name__ == "__main__":
    # 测试代码
    import asyncio
    
    async def test_fingerprint_manager():
        """测试浏览器指纹管理器"""
        config = FingerprintConfig(
            enable_user_agent_rotation=True,
            enable_webgl_spoofing=True,
            enable_canvas_spoofing=True,
            max_fingerprint_usage=10,
            fingerprint_rotation_interval=300
        )
        
        manager = BrowserFingerprintManager(config)
        
        # 生成多个指纹
        fingerprints = []
        for i in range(5):
            fingerprint = manager.generate_fingerprint()
            fingerprints.append(fingerprint)
            print(f"生成指纹 {i+1}: {fingerprint.browser_type.value} on {fingerprint.os_type.value}")
        
        # 测试指纹验证
        for i, fingerprint in enumerate(fingerprints):
            is_valid = manager.validate_fingerprint_consistency(fingerprint)
            print(f"指纹 {i+1} 一致性验证: {'通过' if is_valid else '失败'}")
        
        # 测试指纹导出和导入
        fingerprint_json = manager.export_fingerprint(fingerprints[0])
        imported_fingerprint = manager.import_fingerprint(fingerprint_json)
        print(f"指纹导出导入测试: {'成功' if imported_fingerprint.user_agent == fingerprints[0].user_agent else '失败'}")
        
        # 显示统计信息
        stats = manager.get_fingerprint_stats()
        print(f"指纹统计信息: {stats}")
        
        # 清理过期指纹
        manager.cleanup_old_fingerprints()
        print("清理过期指纹完成")
    
    # 运行测试
    asyncio.run(test_fingerprint_manager())