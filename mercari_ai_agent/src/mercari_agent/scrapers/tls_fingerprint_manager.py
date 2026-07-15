"""
TLS指纹伪装管理器

该模块提供TLS指纹伪装功能，用于绕过基于TLS指纹的反爬虫检测。
实现JA3/JA4 TLS指纹伪装和HTTP/2协议特征模拟。

主要功能：
- JA3/JA4 TLS指纹伪装
- HTTP/2协议特征模拟
- 动态TLS配置机制
- 多种TLS版本和密码套件支持
- 浏览器TLS特征模拟
- 指纹随机化和轮换

技术特点：
- 基于aiohttp的SSL上下文定制
- 支持多种浏览器TLS特征
- 动态指纹生成和管理
- 反检测优化配置

Author: Mercari AI Agent Team
"""

import asyncio
import logging
import ssl
import random
import hashlib
import json
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import aiohttp
import socket
from urllib.parse import urlparse

from ..utils.logger import get_logger
from ..config.settings import settings

logger = get_logger(__name__)


class TLSVersion(Enum):
    """TLS版本枚举"""
    TLS_1_0 = ssl.TLSVersion.TLSv1
    TLS_1_1 = ssl.TLSVersion.TLSv1_1
    TLS_1_2 = ssl.TLSVersion.TLSv1_2
    TLS_1_3 = ssl.TLSVersion.TLSv1_3


class BrowserType(Enum):
    """浏览器类型枚举"""
    CHROME = "chrome"
    FIREFOX = "firefox"
    SAFARI = "safari"
    EDGE = "edge"
    OPERA = "opera"


@dataclass
class TLSFingerprint:
    """TLS指纹数据结构"""
    ja3_hash: str
    ja4_hash: str
    cipher_suites: List[str]
    extensions: List[str]
    elliptic_curves: List[str]
    signature_algorithms: List[str]
    tls_version: TLSVersion
    browser_type: BrowserType
    user_agent: str
    http2_settings: Dict[str, Any]
    creation_time: datetime = field(default_factory=datetime.now)
    usage_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'ja3_hash': self.ja3_hash,
            'ja4_hash': self.ja4_hash,
            'cipher_suites': self.cipher_suites,
            'extensions': self.extensions,
            'elliptic_curves': self.elliptic_curves,
            'signature_algorithms': self.signature_algorithms,
            'tls_version': self.tls_version.value,
            'browser_type': self.browser_type.value,
            'user_agent': self.user_agent,
            'http2_settings': self.http2_settings,
            'creation_time': self.creation_time.isoformat(),
            'usage_count': self.usage_count
        }


@dataclass
class TLSConfig:
    """TLS配置"""
    min_tls_version: TLSVersion = TLSVersion.TLS_1_2
    max_tls_version: TLSVersion = TLSVersion.TLS_1_3
    enable_fingerprint_rotation: bool = True
    fingerprint_rotation_interval: int = 300  # 5分钟
    max_fingerprint_usage: int = 100
    enable_ja3_spoofing: bool = True
    enable_ja4_spoofing: bool = True
    enable_http2: bool = True
    custom_cipher_suites: Optional[List[str]] = None
    verify_ssl: bool = True
    
    # 浏览器分布配置
    browser_distribution: Dict[BrowserType, float] = field(default_factory=lambda: {
        BrowserType.CHROME: 0.65,
        BrowserType.FIREFOX: 0.15,
        BrowserType.SAFARI: 0.10,
        BrowserType.EDGE: 0.08,
        BrowserType.OPERA: 0.02
    })


class TLSFingerprintGenerator:
    """TLS指纹生成器"""
    
    def __init__(self):
        self.cipher_suites_db = self._load_cipher_suites()
        self.extensions_db = self._load_extensions()
        self.curves_db = self._load_elliptic_curves()
        self.signature_algorithms_db = self._load_signature_algorithms()
        self.browser_profiles = self._load_browser_profiles()
    
    def _load_cipher_suites(self) -> Dict[BrowserType, List[str]]:
        """加载密码套件数据库"""
        return {
            BrowserType.CHROME: [
                "TLS_AES_128_GCM_SHA256",
                "TLS_AES_256_GCM_SHA384",
                "TLS_CHACHA20_POLY1305_SHA256",
                "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256",
                "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
                "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384",
                "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
                "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256",
                "TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256",
                "TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA",
                "TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA",
                "TLS_RSA_WITH_AES_128_GCM_SHA256",
                "TLS_RSA_WITH_AES_256_GCM_SHA384",
                "TLS_RSA_WITH_AES_128_CBC_SHA",
                "TLS_RSA_WITH_AES_256_CBC_SHA"
            ],
            BrowserType.FIREFOX: [
                "TLS_AES_128_GCM_SHA256",
                "TLS_CHACHA20_POLY1305_SHA256",
                "TLS_AES_256_GCM_SHA384",
                "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256",
                "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
                "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256",
                "TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256",
                "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384",
                "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
                "TLS_ECDHE_ECDSA_WITH_AES_256_CBC_SHA",
                "TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA",
                "TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA",
                "TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA",
                "TLS_DHE_RSA_WITH_AES_128_CBC_SHA",
                "TLS_DHE_RSA_WITH_AES_256_CBC_SHA"
            ],
            BrowserType.SAFARI: [
                "TLS_AES_128_GCM_SHA256",
                "TLS_AES_256_GCM_SHA384",
                "TLS_CHACHA20_POLY1305_SHA256",
                "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384",
                "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256",
                "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
                "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
                "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256",
                "TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256",
                "TLS_ECDHE_ECDSA_WITH_AES_256_CBC_SHA384",
                "TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA256",
                "TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA384",
                "TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA256",
                "TLS_ECDHE_ECDSA_WITH_AES_256_CBC_SHA",
                "TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA"
            ],
            BrowserType.EDGE: [
                "TLS_AES_128_GCM_SHA256",
                "TLS_AES_256_GCM_SHA384",
                "TLS_CHACHA20_POLY1305_SHA256",
                "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256",
                "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
                "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384",
                "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
                "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256",
                "TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256",
                "TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA",
                "TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA",
                "TLS_RSA_WITH_AES_128_GCM_SHA256",
                "TLS_RSA_WITH_AES_256_GCM_SHA384",
                "TLS_RSA_WITH_AES_128_CBC_SHA",
                "TLS_RSA_WITH_AES_256_CBC_SHA"
            ],
            BrowserType.OPERA: [
                "TLS_AES_128_GCM_SHA256",
                "TLS_AES_256_GCM_SHA384",
                "TLS_CHACHA20_POLY1305_SHA256",
                "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256",
                "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
                "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384",
                "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
                "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256",
                "TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256",
                "TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA",
                "TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA",
                "TLS_RSA_WITH_AES_128_GCM_SHA256",
                "TLS_RSA_WITH_AES_256_GCM_SHA384"
            ]
        }
    
    def _load_extensions(self) -> Dict[BrowserType, List[str]]:
        """加载扩展数据库"""
        return {
            BrowserType.CHROME: [
                "server_name",
                "extended_master_secret",
                "renegotiation_info",
                "supported_groups",
                "ec_point_formats",
                "session_ticket",
                "application_layer_protocol_negotiation",
                "status_request",
                "signature_algorithms",
                "signed_certificate_timestamp",
                "key_share",
                "pre_shared_key",
                "supported_versions",
                "cookie",
                "psk_key_exchange_modes",
                "certificate_authorities",
                "oid_filters",
                "post_handshake_auth",
                "signature_algorithms_cert"
            ],
            BrowserType.FIREFOX: [
                "server_name",
                "extended_master_secret",
                "renegotiation_info",
                "supported_groups",
                "ec_point_formats",
                "session_ticket",
                "application_layer_protocol_negotiation",
                "status_request",
                "signature_algorithms",
                "signed_certificate_timestamp",
                "key_share",
                "pre_shared_key",
                "supported_versions",
                "cookie",
                "psk_key_exchange_modes",
                "certificate_authorities"
            ],
            BrowserType.SAFARI: [
                "server_name",
                "extended_master_secret",
                "renegotiation_info",
                "supported_groups",
                "ec_point_formats",
                "session_ticket",
                "application_layer_protocol_negotiation",
                "status_request",
                "signature_algorithms",
                "signed_certificate_timestamp",
                "key_share",
                "pre_shared_key",
                "supported_versions",
                "psk_key_exchange_modes"
            ],
            BrowserType.EDGE: [
                "server_name",
                "extended_master_secret",
                "renegotiation_info",
                "supported_groups",
                "ec_point_formats",
                "session_ticket",
                "application_layer_protocol_negotiation",
                "status_request",
                "signature_algorithms",
                "signed_certificate_timestamp",
                "key_share",
                "pre_shared_key",
                "supported_versions",
                "cookie",
                "psk_key_exchange_modes",
                "certificate_authorities",
                "oid_filters",
                "post_handshake_auth",
                "signature_algorithms_cert"
            ],
            BrowserType.OPERA: [
                "server_name",
                "extended_master_secret",
                "renegotiation_info",
                "supported_groups",
                "ec_point_formats",
                "session_ticket",
                "application_layer_protocol_negotiation",
                "status_request",
                "signature_algorithms",
                "signed_certificate_timestamp",
                "key_share",
                "pre_shared_key",
                "supported_versions",
                "cookie",
                "psk_key_exchange_modes"
            ]
        }
    
    def _load_elliptic_curves(self) -> List[str]:
        """加载椭圆曲线数据库"""
        return [
            "x25519",
            "secp256r1",
            "secp384r1",
            "secp521r1",
            "ffdhe2048",
            "ffdhe3072",
            "ffdhe4096",
            "ffdhe6144",
            "ffdhe8192"
        ]
    
    def _load_signature_algorithms(self) -> List[str]:
        """加载签名算法数据库"""
        return [
            "ecdsa_secp256r1_sha256",
            "ecdsa_secp384r1_sha384",
            "ecdsa_secp521r1_sha512",
            "ed25519",
            "ed448",
            "rsa_pss_pss_sha256",
            "rsa_pss_pss_sha384",
            "rsa_pss_pss_sha512",
            "rsa_pss_rsae_sha256",
            "rsa_pss_rsae_sha384",
            "rsa_pss_rsae_sha512",
            "rsa_pkcs1_sha256",
            "rsa_pkcs1_sha384",
            "rsa_pkcs1_sha512",
            "ecdsa_sha224",
            "ecdsa_sha1",
            "rsa_pkcs1_sha224",
            "rsa_pkcs1_sha1",
            "dsa_sha224",
            "dsa_sha1",
            "dsa_sha256",
            "dsa_sha384",
            "dsa_sha512"
        ]
    
    def _load_browser_profiles(self) -> Dict[BrowserType, Dict[str, Any]]:
        """加载浏览器配置文件"""
        return {
            BrowserType.CHROME: {
                "user_agents": [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ],
                "http2_settings": {
                    "HEADER_TABLE_SIZE": 65536,
                    "ENABLE_PUSH": 1,
                    "MAX_CONCURRENT_STREAMS": 1000,
                    "INITIAL_WINDOW_SIZE": 6291456,
                    "MAX_FRAME_SIZE": 16384,
                    "MAX_HEADER_LIST_SIZE": 262144
                }
            },
            BrowserType.FIREFOX: {
                "user_agents": [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0",
                    "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"
                ],
                "http2_settings": {
                    "HEADER_TABLE_SIZE": 65536,
                    "ENABLE_PUSH": 1,
                    "MAX_CONCURRENT_STREAMS": 1000,
                    "INITIAL_WINDOW_SIZE": 131072,
                    "MAX_FRAME_SIZE": 16384
                }
            },
            BrowserType.SAFARI: {
                "user_agents": [
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1"
                ],
                "http2_settings": {
                    "HEADER_TABLE_SIZE": 4096,
                    "ENABLE_PUSH": 1,
                    "MAX_CONCURRENT_STREAMS": 100,
                    "INITIAL_WINDOW_SIZE": 32768,
                    "MAX_FRAME_SIZE": 16384
                }
            },
            BrowserType.EDGE: {
                "user_agents": [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
                ],
                "http2_settings": {
                    "HEADER_TABLE_SIZE": 65536,
                    "ENABLE_PUSH": 1,
                    "MAX_CONCURRENT_STREAMS": 1000,
                    "INITIAL_WINDOW_SIZE": 6291456,
                    "MAX_FRAME_SIZE": 16384,
                    "MAX_HEADER_LIST_SIZE": 262144
                }
            },
            BrowserType.OPERA: {
                "user_agents": [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0"
                ],
                "http2_settings": {
                    "HEADER_TABLE_SIZE": 65536,
                    "ENABLE_PUSH": 1,
                    "MAX_CONCURRENT_STREAMS": 1000,
                    "INITIAL_WINDOW_SIZE": 6291456,
                    "MAX_FRAME_SIZE": 16384
                }
            }
        }
    
    def generate_fingerprint(self, browser_type: BrowserType) -> TLSFingerprint:
        """生成TLS指纹"""
        # 选择密码套件
        cipher_suites = self.cipher_suites_db[browser_type].copy()
        # 随机打乱顺序以增加多样性
        random.shuffle(cipher_suites)
        
        # 选择扩展
        extensions = self.extensions_db[browser_type].copy()
        random.shuffle(extensions)
        
        # 选择椭圆曲线
        curves = random.sample(self.curves_db, k=random.randint(4, 6))
        
        # 选择签名算法
        sig_algorithms = random.sample(self.signature_algorithms_db, k=random.randint(8, 12))
        
        # 生成JA3指纹
        ja3_string = self._generate_ja3_string(
            tls_version=TLSVersion.TLS_1_3,
            cipher_suites=cipher_suites,
            extensions=extensions,
            curves=curves,
            sig_algorithms=sig_algorithms
        )
        ja3_hash = hashlib.md5(ja3_string.encode()).hexdigest()
        
        # 生成JA4指纹
        ja4_string = self._generate_ja4_string(
            tls_version=TLSVersion.TLS_1_3,
            cipher_suites=cipher_suites,
            extensions=extensions,
            sig_algorithms=sig_algorithms
        )
        ja4_hash = hashlib.sha256(ja4_string.encode()).hexdigest()[:32]
        
        # 选择用户代理
        user_agents = self.browser_profiles[browser_type]["user_agents"]
        user_agent = random.choice(user_agents)
        
        # HTTP/2设置
        http2_settings = self.browser_profiles[browser_type]["http2_settings"].copy()
        
        return TLSFingerprint(
            ja3_hash=ja3_hash,
            ja4_hash=ja4_hash,
            cipher_suites=cipher_suites,
            extensions=extensions,
            elliptic_curves=curves,
            signature_algorithms=sig_algorithms,
            tls_version=TLSVersion.TLS_1_3,
            browser_type=browser_type,
            user_agent=user_agent,
            http2_settings=http2_settings
        )
    
    def _generate_ja3_string(self, tls_version: TLSVersion, cipher_suites: List[str], 
                            extensions: List[str], curves: List[str], 
                            sig_algorithms: List[str]) -> str:
        """生成JA3字符串"""
        # JA3格式：TLSVersion,CipherSuites,Extensions,EllipticCurves,EllipticCurvePointFormats
        tls_ver = "771"  # TLS 1.3
        cipher_str = "-".join([str(hash(cs) % 65536) for cs in cipher_suites[:10]])
        ext_str = "-".join([str(hash(ext) % 65536) for ext in extensions[:15]])
        curve_str = "-".join([str(hash(curve) % 65536) for curve in curves])
        
        return f"{tls_ver},{cipher_str},{ext_str},{curve_str},"
    
    def _generate_ja4_string(self, tls_version: TLSVersion, cipher_suites: List[str], 
                            extensions: List[str], sig_algorithms: List[str]) -> str:
        """生成JA4字符串"""
        # JA4格式：TLSVersion_CipherSuites_Extensions_SignatureAlgorithms
        tls_ver = "t13"  # TLS 1.3
        cipher_str = "".join([str(hash(cs) % 16) for cs in cipher_suites[:8]])
        ext_str = "".join([str(hash(ext) % 16) for ext in extensions[:12]])
        sig_str = "".join([str(hash(sig) % 16) for sig in sig_algorithms[:6]])
        
        return f"{tls_ver}_{cipher_str}_{ext_str}_{sig_str}"


class TLSFingerprintManager:
    """TLS指纹管理器"""
    
    def __init__(self, config: Optional[TLSConfig] = None):
        self.config = config or TLSConfig()
        self.generator = TLSFingerprintGenerator()
        self.active_fingerprints: Dict[str, TLSFingerprint] = {}
        self.fingerprint_history: List[TLSFingerprint] = []
        self.last_rotation_time = datetime.now()
        
        # 初始化指纹池
        self._initialize_fingerprint_pool()
        
        logger.info("TLS指纹管理器初始化完成")
    
    def _initialize_fingerprint_pool(self):
        """初始化指纹池"""
        for browser_type in BrowserType:
            # 为每种浏览器生成多个指纹
            for _ in range(3):
                fingerprint = self.generator.generate_fingerprint(browser_type)
                key = f"{browser_type.value}_{len(self.active_fingerprints)}"
                self.active_fingerprints[key] = fingerprint
    
    def get_fingerprint(self, preferred_browser: Optional[BrowserType] = None) -> TLSFingerprint:
        """获取TLS指纹"""
        # 检查是否需要轮换指纹
        if self._should_rotate_fingerprints():
            self._rotate_fingerprints()
        
        # 根据浏览器分布选择指纹
        if preferred_browser:
            browser_type = preferred_browser
        else:
            browser_type = self._select_browser_by_distribution()
        
        # 查找匹配的指纹
        matching_fingerprints = [
            fp for key, fp in self.active_fingerprints.items()
            if fp.browser_type == browser_type and fp.usage_count < self.config.max_fingerprint_usage
        ]
        
        if not matching_fingerprints:
            # 如果没有可用指纹，生成新的
            fingerprint = self.generator.generate_fingerprint(browser_type)
            key = f"{browser_type.value}_{len(self.active_fingerprints)}"
            self.active_fingerprints[key] = fingerprint
            return fingerprint
        
        # 选择使用次数最少的指纹
        fingerprint = min(matching_fingerprints, key=lambda x: x.usage_count)
        fingerprint.usage_count += 1
        
        logger.debug(f"选择TLS指纹: {fingerprint.browser_type.value}, 使用次数: {fingerprint.usage_count}")
        return fingerprint
    
    def _should_rotate_fingerprints(self) -> bool:
        """检查是否需要轮换指纹"""
        if not self.config.enable_fingerprint_rotation:
            return False
        
        time_since_rotation = (datetime.now() - self.last_rotation_time).total_seconds()
        return time_since_rotation > self.config.fingerprint_rotation_interval
    
    def _rotate_fingerprints(self):
        """轮换指纹"""
        logger.info("开始轮换TLS指纹")
        
        # 将过期的指纹移到历史记录
        expired_keys = []
        for key, fingerprint in self.active_fingerprints.items():
            if fingerprint.usage_count >= self.config.max_fingerprint_usage:
                expired_keys.append(key)
                self.fingerprint_history.append(fingerprint)
        
        # 移除过期指纹
        for key in expired_keys:
            del self.active_fingerprints[key]
        
        # 生成新指纹补充
        for browser_type in BrowserType:
            current_count = sum(1 for fp in self.active_fingerprints.values() 
                              if fp.browser_type == browser_type)
            if current_count < 2:  # 每种浏览器至少保持2个指纹
                fingerprint = self.generator.generate_fingerprint(browser_type)
                key = f"{browser_type.value}_{len(self.active_fingerprints)}"
                self.active_fingerprints[key] = fingerprint
        
        self.last_rotation_time = datetime.now()
        logger.info(f"指纹轮换完成，当前活动指纹数: {len(self.active_fingerprints)}")
    
    def _select_browser_by_distribution(self) -> BrowserType:
        """根据分布选择浏览器"""
        rand = random.random()
        cumulative = 0.0
        
        for browser_type, probability in self.config.browser_distribution.items():
            cumulative += probability
            if rand <= cumulative:
                return browser_type
        
        # 默认返回Chrome
        return BrowserType.CHROME
    
    def create_ssl_context(self, fingerprint: TLSFingerprint) -> ssl.SSLContext:
        """创建SSL上下文"""
        context = ssl.create_default_context()
        
        # 设置TLS版本
        context.minimum_version = self.config.min_tls_version.value
        context.maximum_version = self.config.max_tls_version.value
        
        # 设置密码套件
        if self.config.custom_cipher_suites:
            cipher_list = ":".join(self.config.custom_cipher_suites)
        else:
            # 使用指纹中的密码套件
            cipher_list = ":".join(fingerprint.cipher_suites[:10])
        
        try:
            context.set_ciphers(cipher_list)
        except ssl.SSLError as e:
            logger.warning(f"设置密码套件失败，使用默认: {e}")
        
        # 设置验证模式
        if not self.config.verify_ssl:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        
        return context
    
    def create_connector(self, fingerprint: TLSFingerprint) -> aiohttp.TCPConnector:
        """创建连接器"""
        ssl_context = self.create_ssl_context(fingerprint)
        
        connector = aiohttp.TCPConnector(
            ssl=ssl_context,
            limit=100,
            limit_per_host=30,
            ttl_dns_cache=300,
            use_dns_cache=True,
            enable_cleanup_closed=True
        )
        
        return connector
    
    def get_headers(self, fingerprint: TLSFingerprint) -> Dict[str, str]:
        """获取HTTP头"""
        headers = {
            'User-Agent': fingerprint.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,ja;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Charset': 'UTF-8',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        }
        
        # 根据浏览器类型添加特定头
        if fingerprint.browser_type == BrowserType.CHROME:
            headers.update({
                'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"'
            })
        elif fingerprint.browser_type == BrowserType.FIREFOX:
            headers.update({
                'DNT': '1',
                'Sec-GPC': '1'
            })
        
        return headers
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        browser_stats = {}
        for browser_type in BrowserType:
            count = sum(1 for fp in self.active_fingerprints.values() 
                       if fp.browser_type == browser_type)
            usage = sum(fp.usage_count for fp in self.active_fingerprints.values() 
                       if fp.browser_type == browser_type)
            browser_stats[browser_type.value] = {
                'count': count,
                'total_usage': usage,
                'avg_usage': usage / count if count > 0 else 0
            }
        
        return {
            'active_fingerprints': len(self.active_fingerprints),
            'historical_fingerprints': len(self.fingerprint_history),
            'last_rotation': self.last_rotation_time.isoformat(),
            'browser_distribution': browser_stats,
            'config': {
                'rotation_enabled': self.config.enable_fingerprint_rotation,
                'rotation_interval': self.config.fingerprint_rotation_interval,
                'max_usage': self.config.max_fingerprint_usage
            }
        }
    
    def reset_fingerprints(self):
        """重置指纹池"""
        self.active_fingerprints.clear()
        self.fingerprint_history.clear()
        self._initialize_fingerprint_pool()
        self.last_rotation_time = datetime.now()
        logger.info("TLS指纹池已重置")