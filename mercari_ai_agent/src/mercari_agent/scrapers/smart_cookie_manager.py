"""
智能Cookie管理器

该模块实现了先进的Cookie管理策略，解决当前系统中Cookie处理不当导致的CAPTCHA检测准确性问题。
通过智能分类、选择性过滤和动态规则学习，确保关键安全Cookie得到正确处理。

核心功能：
- 智能Cookie分类系统（CRITICAL、IMPORTANT、OPTIONAL、BLACKLIST）
- 选择性Cookie过滤，保留身份验证关键Cookie
- 域名和路径特定的白名单/黑名单机制
- 动态Cookie分类和规则学习
- 增强的Cookie生命周期管理
- 性能优化和监控

关键Cookie类别：
- Cloudflare保护Cookie：__cf_bm、_cfuvid、cf_clearance
- 会话管理Cookie：session_id、JSESSIONID、PHPSESSID
- 反机器人令牌：各种bot protection服务的令牌

Author: Mercari AI Agent Team
"""

import asyncio
import logging
import time
import json
import hashlib
import re
from typing import Dict, List, Optional, Any, Set, Tuple, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from urllib.parse import urlparse
from pathlib import Path
from collections import defaultdict, deque
import aiohttp
from http.cookies import SimpleCookie

from ..utils.logger import get_logger
from ..config.settings import settings

logger = get_logger(__name__)


class CookieCategory(Enum):
    """Cookie分类枚举"""
    CRITICAL = "critical"      # 必须保留的安全和身份验证Cookie
    IMPORTANT = "important"    # 功能相关的重要Cookie
    OPTIONAL = "optional"      # 可选的偏好和统计Cookie
    BLACKLIST = "blacklist"    # 应该移除的Cookie


class CookieSource(Enum):
    """Cookie来源枚举"""
    RESPONSE_HEADER = "response_header"
    SET_COOKIE = "set_cookie"
    JAVASCRIPT = "javascript"
    MANUAL = "manual"


@dataclass
class CookieInfo:
    """增强的Cookie信息"""
    name: str
    value: str
    domain: str
    path: str = "/"
    expires: Optional[datetime] = None
    max_age: Optional[int] = None
    secure: bool = False
    http_only: bool = False
    same_site: Optional[str] = None
    category: CookieCategory = CookieCategory.OPTIONAL
    source: CookieSource = CookieSource.RESPONSE_HEADER
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    success_count: int = 0  # 成功使用次数
    failure_count: int = 0  # 失败使用次数
    priority: int = 0  # 优先级，数字越大优先级越高
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'name': self.name,
            'value': self.value,
            'domain': self.domain,
            'path': self.path,
            'expires': self.expires.isoformat() if self.expires else None,
            'max_age': self.max_age,
            'secure': self.secure,
            'http_only': self.http_only,
            'same_site': self.same_site,
            'category': self.category.value,
            'source': self.source.value,
            'created_at': self.created_at.isoformat(),
            'last_accessed': self.last_accessed.isoformat(),
            'access_count': self.access_count,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'priority': self.priority
        }
    
    def is_expired(self) -> bool:
        """检查Cookie是否过期"""
        if self.expires and datetime.now() > self.expires:
            return True
        if self.max_age and (datetime.now() - self.created_at).total_seconds() > self.max_age:
            return True
        return False
    
    def calculate_importance_score(self) -> float:
        """计算Cookie重要性分数"""
        base_score = {
            CookieCategory.CRITICAL: 100,
            CookieCategory.IMPORTANT: 75,
            CookieCategory.OPTIONAL: 50,
            CookieCategory.BLACKLIST: 0
        }[self.category]
        
        # 成功率加权
        total_uses = self.success_count + self.failure_count
        success_rate = self.success_count / total_uses if total_uses > 0 else 0.5
        
        # 使用频率加权
        frequency_weight = min(self.access_count / 100, 1.0)
        
        # 时间权重（较新的Cookie权重更高）
        age_hours = (datetime.now() - self.created_at).total_seconds() / 3600
        time_weight = max(0, 1.0 - age_hours / 168)  # 一周内权重逐渐降低
        
        return base_score * (0.4 + 0.3 * success_rate + 0.2 * frequency_weight + 0.1 * time_weight)


@dataclass
class CookieRule:
    """Cookie规则"""
    name_pattern: str
    domain_pattern: str
    path_pattern: str = "/"
    category: CookieCategory = CookieCategory.OPTIONAL
    action: str = "allow"  # allow, block, monitor
    priority: int = 0
    description: str = ""
    
    def matches(self, cookie: CookieInfo) -> bool:
        """检查规则是否匹配Cookie"""
        if not re.match(self.name_pattern, cookie.name):
            return False
        if not re.match(self.domain_pattern, cookie.domain):
            return False
        if not re.match(self.path_pattern, cookie.path):
            return False
        return True


@dataclass
class CookieStats:
    """Cookie统计信息"""
    total_cookies: int = 0
    critical_cookies: int = 0
    important_cookies: int = 0
    optional_cookies: int = 0
    blacklist_cookies: int = 0
    preserved_cookies: int = 0
    filtered_cookies: int = 0
    expired_cookies: int = 0
    success_rate: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)
    
    def update_stats(self, cookies: List[CookieInfo]):
        """更新统计信息"""
        self.total_cookies = len(cookies)
        self.critical_cookies = sum(1 for c in cookies if c.category == CookieCategory.CRITICAL)
        self.important_cookies = sum(1 for c in cookies if c.category == CookieCategory.IMPORTANT)
        self.optional_cookies = sum(1 for c in cookies if c.category == CookieCategory.OPTIONAL)
        self.blacklist_cookies = sum(1 for c in cookies if c.category == CookieCategory.BLACKLIST)
        self.expired_cookies = sum(1 for c in cookies if c.is_expired())
        self.last_updated = datetime.now()
        
        # 计算成功率
        total_uses = sum(c.success_count + c.failure_count for c in cookies)
        total_success = sum(c.success_count for c in cookies)
        self.success_rate = total_success / total_uses if total_uses > 0 else 0.0


class SmartCookieManager:
    """
    智能Cookie管理器
    
    核心功能：
    1. 智能Cookie分类和过滤
    2. 动态规则学习和适应
    3. 域名特定的Cookie策略
    4. 性能优化和监控
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化智能Cookie管理器
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.cookies: Dict[str, CookieInfo] = {}
        self.rules: List[CookieRule] = []
        self.domain_stats: Dict[str, CookieStats] = defaultdict(CookieStats)
        self.global_stats = CookieStats()
        
        # 学习参数
        self.learning_enabled = self.config.get('learning_enabled', True)
        self.learning_threshold = self.config.get('learning_threshold', 0.8)
        self.adaptation_rate = self.config.get('adaptation_rate', 0.1)
        
        # 性能参数
        self.max_cookies = self.config.get('max_cookies', 10000)
        self.cleanup_interval = self.config.get('cleanup_interval', 300)  # 5分钟
        self.last_cleanup = datetime.now()
        
        # 监控参数
        self.monitoring_enabled = self.config.get('monitoring_enabled', True)
        self.performance_log = deque(maxlen=1000)
        
        # 初始化默认规则
        self._initialize_default_rules()
        
        logger.info("智能Cookie管理器初始化完成")
    
    def _initialize_default_rules(self):
        """初始化默认Cookie规则"""
        # Cloudflare保护Cookie - 最高优先级
        critical_rules = [
            CookieRule(
                name_pattern=r"__cf_bm",
                domain_pattern=r".*",
                category=CookieCategory.CRITICAL,
                priority=100,
                description="Cloudflare Bot管理令牌"
            ),
            CookieRule(
                name_pattern=r"_cfuvid",
                domain_pattern=r".*",
                category=CookieCategory.CRITICAL,
                priority=100,
                description="Cloudflare用户验证标识"
            ),
            CookieRule(
                name_pattern=r"cf_clearance",
                domain_pattern=r".*",
                category=CookieCategory.CRITICAL,
                priority=100,
                description="Cloudflare挑战通过证明"
            ),
            CookieRule(
                name_pattern=r"__cfruid",
                domain_pattern=r".*",
                category=CookieCategory.CRITICAL,
                priority=100,
                description="Cloudflare请求标识符"
            )
        ]
        
        # 会话管理Cookie - 高优先级
        session_rules = [
            CookieRule(
                name_pattern=r"session_id|JSESSIONID|PHPSESSID|ASP\.NET_SessionId",
                domain_pattern=r".*",
                category=CookieCategory.IMPORTANT,
                priority=90,
                description="会话管理Cookie"
            ),
            CookieRule(
                name_pattern=r"_session|sessionid|sid",
                domain_pattern=r".*",
                category=CookieCategory.IMPORTANT,
                priority=85,
                description="会话相关Cookie"
            ),
            CookieRule(
                name_pattern=r"csrf_token|_csrf|xsrf_token",
                domain_pattern=r".*",
                category=CookieCategory.IMPORTANT,
                priority=80,
                description="CSRF保护令牌"
            )
        ]
        
        # 反机器人令牌 - 高优先级
        anti_bot_rules = [
            CookieRule(
                name_pattern=r".*captcha.*|.*recaptcha.*|.*hcaptcha.*",
                domain_pattern=r".*",
                category=CookieCategory.CRITICAL,
                priority=95,
                description="CAPTCHA相关令牌"
            ),
            CookieRule(
                name_pattern=r".*bot.*protection.*|.*verify.*|.*challenge.*",
                domain_pattern=r".*",
                category=CookieCategory.IMPORTANT,
                priority=85,
                description="反机器人保护令牌"
            )
        ]
        
        # 身份验证Cookie - 重要
        auth_rules = [
            CookieRule(
                name_pattern=r".*auth.*|.*login.*|.*user.*|.*token.*",
                domain_pattern=r".*",
                category=CookieCategory.IMPORTANT,
                priority=75,
                description="身份验证相关Cookie"
            )
        ]
        
        # 黑名单Cookie - 需要过滤
        blacklist_rules = [
            CookieRule(
                name_pattern=r".*tracking.*|.*analytics.*|.*ads.*|.*marketing.*",
                domain_pattern=r".*",
                category=CookieCategory.BLACKLIST,
                priority=0,
                description="追踪和广告Cookie"
            ),
            CookieRule(
                name_pattern=r".*facebook.*|.*google.*analytics.*|.*doubleclick.*",
                domain_pattern=r".*",
                category=CookieCategory.BLACKLIST,
                priority=0,
                description="第三方追踪Cookie"
            )
        ]
        
        # 合并所有规则
        self.rules = critical_rules + session_rules + anti_bot_rules + auth_rules + blacklist_rules
        
        # 按优先级排序
        self.rules.sort(key=lambda x: x.priority, reverse=True)
        
        logger.info(f"初始化了 {len(self.rules)} 个默认Cookie规则")
    
    def categorize_cookies(self, cookies: List[Any]) -> Dict[str, List[CookieInfo]]:
        """
        对Cookie进行智能分类
        
        Args:
            cookies: 原始Cookie列表
            
        Returns:
            Dict[str, List[CookieInfo]]: 分类后的Cookie字典
        """
        categorized = {
            'critical': [],
            'important': [],
            'optional': [],
            'blacklist': []
        }
        
        processed_cookies = []
        
        for cookie in cookies:
            try:
                # 解析Cookie信息
                cookie_info = self._parse_cookie(cookie)
                if cookie_info:
                    # 分类Cookie
                    self._classify_cookie(cookie_info)
                    processed_cookies.append(cookie_info)
                    
                    # 添加到分类字典
                    category_key = cookie_info.category.value
                    if category_key in categorized:
                        categorized[category_key].append(cookie_info)
                    else:
                        categorized['optional'].append(cookie_info)
                        
            except Exception as e:
                logger.error(f"Cookie分类失败: {e}")
                continue
        
        # 更新统计信息
        self.global_stats.update_stats(processed_cookies)
        
        logger.info(f"Cookie分类完成: critical={len(categorized['critical'])}, "
                   f"important={len(categorized['important'])}, "
                   f"optional={len(categorized['optional'])}, "
                   f"blacklist={len(categorized['blacklist'])}")
        
        return categorized
    
    def _parse_cookie(self, cookie: Any) -> Optional[CookieInfo]:
        """
        解析Cookie对象
        
        Args:
            cookie: 原始Cookie对象
            
        Returns:
            Optional[CookieInfo]: 解析后的Cookie信息
        """
        try:
            # 处理字符串类型的Cookie
            if isinstance(cookie, str):
                logger.debug(f"检测到字符串类型Cookie: {cookie}")
                # 尝试解析字符串Cookie
                return self._parse_string_cookie(cookie)
            
            # 处理标准Cookie对象
            name = None
            value = None
            domain = "localhost"
            path = "/"
            
            # 获取Cookie名称和值
            if hasattr(cookie, 'key') and hasattr(cookie, 'value'):
                name = cookie.key
                value = cookie.value
            elif hasattr(cookie, 'name') and hasattr(cookie, 'value'):
                name = cookie.name
                value = cookie.value
            else:
                logger.warning(f"Cookie缺少标准属性: {dir(cookie)}")
                return None
            
            # 获取其他属性
            if hasattr(cookie, 'domain'):
                domain = cookie.domain or domain
            if hasattr(cookie, 'path'):
                path = cookie.path or path
            
            # 创建CookieInfo对象
            cookie_info = CookieInfo(
                name=str(name),
                value=str(value) if value is not None else "",
                domain=domain,
                path=path,
                secure=getattr(cookie, 'secure', False),
                http_only=getattr(cookie, 'httponly', False),
                same_site=getattr(cookie, 'samesite', None),
                source=CookieSource.RESPONSE_HEADER
            )
            
            # 解析过期时间
            if hasattr(cookie, 'expires') and cookie.expires:
                try:
                    from email.utils import parsedate_to_datetime
                    cookie_info.expires = parsedate_to_datetime(cookie.expires)
                except Exception:
                    pass
            
            # 解析max-age
            if hasattr(cookie, 'max_age') and cookie.max_age:
                try:
                    cookie_info.max_age = int(cookie.max_age)
                except ValueError:
                    pass
            
            return cookie_info
            
        except Exception as e:
            logger.error(f"Cookie解析失败: {e}")
            return None
    
    def _parse_string_cookie(self, cookie_str: str) -> Optional[CookieInfo]:
        """
        解析字符串Cookie
        
        Args:
            cookie_str: Cookie字符串
            
        Returns:
            Optional[CookieInfo]: 解析后的Cookie信息
        """
        try:
            # 尝试使用SimpleCookie解析
            simple_cookie = SimpleCookie()
            simple_cookie.load(cookie_str)
            
            for name, morsel in simple_cookie.items():
                return CookieInfo(
                    name=name,
                    value=morsel.value,
                    domain=morsel.get('domain', 'localhost'),
                    path=morsel.get('path', '/'),
                    secure=morsel.get('secure', False),
                    http_only=morsel.get('httponly', False),
                    same_site=morsel.get('samesite'),
                    source=CookieSource.SET_COOKIE
                )
        except Exception as e:
            logger.debug(f"SimpleCookie解析失败: {e}")
        
        # 回退到简单解析
        if '=' in cookie_str:
            name, value = cookie_str.split('=', 1)
            return CookieInfo(
                name=name.strip(),
                value=value.strip(),
                domain='localhost',
                path='/',
                source=CookieSource.MANUAL
            )
        
        return None
    
    def _classify_cookie(self, cookie_info: CookieInfo):
        """
        分类Cookie
        
        Args:
            cookie_info: Cookie信息
        """
        # 应用规则进行分类
        for rule in self.rules:
            if rule.matches(cookie_info):
                cookie_info.category = rule.category
                cookie_info.priority = rule.priority
                logger.debug(f"Cookie '{cookie_info.name}' 分类为 {rule.category.value} (规则: {rule.description})")
                break
        
        # 如果没有匹配的规则，使用默认分类
        if cookie_info.category == CookieCategory.OPTIONAL:
            self._apply_heuristic_classification(cookie_info)
    
    def _apply_heuristic_classification(self, cookie_info: CookieInfo):
        """
        应用启发式分类
        
        Args:
            cookie_info: Cookie信息
        """
        name = cookie_info.name.lower()
        
        # 关键安全Cookie模式
        critical_patterns = [
            r'__cf_bm', r'_cfuvid', r'cf_clearance', r'__cfruid',
            r'captcha', r'recaptcha', r'hcaptcha', r'challenge'
        ]
        
        # 重要Cookie模式
        important_patterns = [
            r'session', r'auth', r'login', r'user', r'token', r'csrf',
            r'xsrf', r'security', r'verify', r'sid'
        ]
        
        # 黑名单模式
        blacklist_patterns = [
            r'tracking', r'analytics', r'ads', r'marketing', r'facebook',
            r'google.*analytics', r'doubleclick', r'_ga', r'_gid'
        ]
        
        # 检查关键模式
        for pattern in critical_patterns:
            if re.search(pattern, name):
                cookie_info.category = CookieCategory.CRITICAL
                cookie_info.priority = 100
                logger.debug(f"启发式分类: '{cookie_info.name}' -> CRITICAL")
                return
        
        # 检查重要模式
        for pattern in important_patterns:
            if re.search(pattern, name):
                cookie_info.category = CookieCategory.IMPORTANT
                cookie_info.priority = 75
                logger.debug(f"启发式分类: '{cookie_info.name}' -> IMPORTANT")
                return
        
        # 检查黑名单模式
        for pattern in blacklist_patterns:
            if re.search(pattern, name):
                cookie_info.category = CookieCategory.BLACKLIST
                cookie_info.priority = 0
                logger.debug(f"启发式分类: '{cookie_info.name}' -> BLACKLIST")
                return
        
        # 默认为可选
        cookie_info.category = CookieCategory.OPTIONAL
        cookie_info.priority = 50
        logger.debug(f"启发式分类: '{cookie_info.name}' -> OPTIONAL")
    
    def should_preserve_cookie(self, cookie_info: CookieInfo, domain: str, path: str) -> bool:
        """
        判断是否应该保留Cookie
        
        Args:
            cookie_info: Cookie信息
            domain: 域名
            path: 路径
            
        Returns:
            bool: 是否应该保留
        """
        # 检查过期
        if cookie_info.is_expired():
            logger.debug(f"Cookie '{cookie_info.name}' 已过期，不保留")
            return False
        
        # 黑名单Cookie直接拒绝
        if cookie_info.category == CookieCategory.BLACKLIST:
            logger.debug(f"Cookie '{cookie_info.name}' 在黑名单中，不保留")
            return False
        
        # 关键和重要Cookie保留
        if cookie_info.category in [CookieCategory.CRITICAL, CookieCategory.IMPORTANT]:
            logger.debug(f"Cookie '{cookie_info.name}' 为{cookie_info.category.value}级别，保留")
            return True
        
        # 可选Cookie根据配置决定
        preserve_optional = self.config.get('preserve_optional_cookies', True)
        if preserve_optional and cookie_info.category == CookieCategory.OPTIONAL:
            logger.debug(f"Cookie '{cookie_info.name}' 为可选级别，根据配置保留")
            return True
        
        logger.debug(f"Cookie '{cookie_info.name}' 不符合保留条件")
        return False
    
    def apply_filtering_policy(self, cookies: List[Any], domain: str) -> Dict[str, Any]:
        """
        应用过滤策略
        
        Args:
            cookies: 原始Cookie列表
            domain: 域名
            
        Returns:
            Dict[str, Any]: 过滤结果
        """
        start_time = time.time()
        
        # 分类Cookie
        categorized = self.categorize_cookies(cookies)
        
        # 过滤结果
        preserved_cookies = {}
        filtered_cookies = []
        stats = {
            'total_input': len(cookies),
            'critical_preserved': 0,
            'important_preserved': 0,
            'optional_preserved': 0,
            'blacklist_filtered': 0,
            'expired_filtered': 0
        }
        
        # 处理关键Cookie
        for cookie_info in categorized['critical']:
            if self.should_preserve_cookie(cookie_info, domain, '/'):
                preserved_cookies[cookie_info.name] = cookie_info.value
                stats['critical_preserved'] += 1
                self._update_cookie_success(cookie_info)
            else:
                filtered_cookies.append(cookie_info)
        
        # 处理重要Cookie
        for cookie_info in categorized['important']:
            if self.should_preserve_cookie(cookie_info, domain, '/'):
                preserved_cookies[cookie_info.name] = cookie_info.value
                stats['important_preserved'] += 1
                self._update_cookie_success(cookie_info)
            else:
                filtered_cookies.append(cookie_info)
        
        # 处理可选Cookie
        for cookie_info in categorized['optional']:
            if self.should_preserve_cookie(cookie_info, domain, '/'):
                preserved_cookies[cookie_info.name] = cookie_info.value
                stats['optional_preserved'] += 1
                self._update_cookie_success(cookie_info)
            else:
                filtered_cookies.append(cookie_info)
        
        # 统计黑名单和过期Cookie
        stats['blacklist_filtered'] = len(categorized['blacklist'])
        stats['expired_filtered'] = len([c for c in filtered_cookies if c.is_expired()])
        
        # 更新域名统计
        self.domain_stats[domain].preserved_cookies = len(preserved_cookies)
        self.domain_stats[domain].filtered_cookies = len(filtered_cookies)
        
        # 记录性能
        processing_time = time.time() - start_time
        self.performance_log.append({
            'timestamp': datetime.now().isoformat(),
            'domain': domain,
            'processing_time': processing_time,
            'total_cookies': len(cookies),
            'preserved_cookies': len(preserved_cookies)
        })
        
        logger.info(f"Cookie过滤完成 - 域名: {domain}, "
                   f"输入: {stats['total_input']}, "
                   f"保留: {len(preserved_cookies)}, "
                   f"过滤: {len(filtered_cookies)}, "
                   f"处理时间: {processing_time:.3f}s")
        
        return {
            'preserved_cookies': preserved_cookies,
            'filtered_cookies': filtered_cookies,
            'stats': stats,
            'categorized': categorized
        }
    
    def _update_cookie_success(self, cookie_info: CookieInfo):
        """更新Cookie成功使用统计"""
        cookie_info.success_count += 1
        cookie_info.last_accessed = datetime.now()
        cookie_info.access_count += 1
        
        # 保存到内部存储
        key = f"{cookie_info.domain}:{cookie_info.path}:{cookie_info.name}"
        self.cookies[key] = cookie_info
    
    def update_dynamic_rules(self, domain: str, success_indicators: Dict[str, Any]):
        """
        更新动态规则
        
        Args:
            domain: 域名
            success_indicators: 成功指标
        """
        if not self.learning_enabled:
            return
        
        # 分析成功指标
        captcha_success = success_indicators.get('captcha_success', False)
        session_maintained = success_indicators.get('session_maintained', False)
        request_success = success_indicators.get('request_success', False)
        
        # 更新Cookie成功率
        for cookie_info in self.cookies.values():
            if cookie_info.domain == domain:
                if captcha_success and 'captcha' in cookie_info.name.lower():
                    cookie_info.success_count += 1
                elif session_maintained and 'session' in cookie_info.name.lower():
                    cookie_info.success_count += 1
                elif request_success:
                    cookie_info.success_count += 1
                else:
                    cookie_info.failure_count += 1
        
        # 学习新规则
        self._learn_new_rules(domain, success_indicators)
        
        logger.debug(f"域名 {domain} 的动态规则已更新")
    
    def _learn_new_rules(self, domain: str, success_indicators: Dict[str, Any]):
        """
        学习新规则
        
        Args:
            domain: 域名
            success_indicators: 成功指标
        """
        # 如果CAPTCHA成功率高，提升相关Cookie的优先级
        if success_indicators.get('captcha_success_rate', 0) > self.learning_threshold:
            for cookie_info in self.cookies.values():
                if (cookie_info.domain == domain and 
                    any(pattern in cookie_info.name.lower() for pattern in ['captcha', 'challenge', 'verify'])):
                    
                    # 提升优先级
                    if cookie_info.category == CookieCategory.IMPORTANT:
                        cookie_info.category = CookieCategory.CRITICAL
                        cookie_info.priority = 100
                        logger.info(f"学习规则: 将Cookie '{cookie_info.name}' 提升为CRITICAL")
        
        # 如果某些Cookie导致失败，降低优先级
        high_failure_cookies = [
            cookie for cookie in self.cookies.values()
            if (cookie.domain == domain and 
                cookie.failure_count > cookie.success_count and
                cookie.failure_count > 5)
        ]
        
        for cookie_info in high_failure_cookies:
            if cookie_info.category == CookieCategory.IMPORTANT:
                cookie_info.category = CookieCategory.OPTIONAL
                cookie_info.priority = 50
                logger.info(f"学习规则: 将Cookie '{cookie_info.name}' 降级为OPTIONAL")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        # 清理过期数据
        self._cleanup_expired_data()
        
        return {
            'global_stats': asdict(self.global_stats),
            'domain_stats': {k: asdict(v) for k, v in self.domain_stats.items()},
            'total_cookies': len(self.cookies),
            'total_rules': len(self.rules),
            'performance_metrics': {
                'average_processing_time': self._calculate_average_processing_time(),
                'memory_usage': self._calculate_memory_usage(),
                'hit_rate': self._calculate_hit_rate()
            }
        }
    
    def _cleanup_expired_data(self):
        """清理过期数据"""
        if (datetime.now() - self.last_cleanup).total_seconds() < self.cleanup_interval:
            return
        
        # 清理过期Cookie
        expired_keys = [
            key for key, cookie in self.cookies.items()
            if cookie.is_expired()
        ]
        
        for key in expired_keys:
            del self.cookies[key]
        
        # 清理过期性能日志
        cutoff_time = datetime.now() - timedelta(hours=24)
        while (self.performance_log and 
               datetime.fromisoformat(self.performance_log[0]['timestamp']) < cutoff_time):
            self.performance_log.popleft()
        
        self.last_cleanup = datetime.now()
        logger.debug(f"清理了 {len(expired_keys)} 个过期Cookie")
    
    def _calculate_average_processing_time(self) -> float:
        """计算平均处理时间"""
        if not self.performance_log:
            return 0.0
        
        total_time = sum(log['processing_time'] for log in self.performance_log)
        return total_time / len(self.performance_log)
    
    def _calculate_memory_usage(self) -> int:
        """计算内存使用量"""
        import sys
        
        total_size = 0
        total_size += sys.getsizeof(self.cookies)
        total_size += sys.getsizeof(self.rules)
        total_size += sys.getsizeof(self.domain_stats)
        total_size += sys.getsizeof(self.performance_log)
        
        return total_size
    
    def _calculate_hit_rate(self) -> float:
        """计算命中率"""
        if not self.cookies:
            return 0.0
        
        total_uses = sum(c.success_count + c.failure_count for c in self.cookies.values())
        total_success = sum(c.success_count for c in self.cookies.values())
        
        return total_success / total_uses if total_uses > 0 else 0.0
    
    def export_configuration(self) -> Dict[str, Any]:
        """导出配置"""
        return {
            'rules': [asdict(rule) for rule in self.rules],
            'cookies': [cookie.to_dict() for cookie in self.cookies.values()],
            'config': self.config,
            'stats': self.get_statistics()
        }
    
    def import_configuration(self, config_data: Dict[str, Any]):
        """导入配置"""
        try:
            # 导入规则
            if 'rules' in config_data:
                self.rules = [
                    CookieRule(**rule_data) for rule_data in config_data['rules']
                ]
            
            # 导入Cookie
            if 'cookies' in config_data:
                self.cookies = {}
                for cookie_data in config_data['cookies']:
                    cookie_info = CookieInfo(**cookie_data)
                    key = f"{cookie_info.domain}:{cookie_info.path}:{cookie_info.name}"
                    self.cookies[key] = cookie_info
            
            # 导入配置
            if 'config' in config_data:
                self.config.update(config_data['config'])
            
            logger.info("配置导入成功")
            
        except Exception as e:
            logger.error(f"配置导入失败: {e}")
            raise