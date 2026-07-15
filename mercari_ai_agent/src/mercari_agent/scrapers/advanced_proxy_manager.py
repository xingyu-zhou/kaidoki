"""
高级代理管理器

该模块提供全面的代理管理功能，包括地理位置分组、质量评估、匿名性检测等。
通过智能的代理选择和轮换策略，大幅提高网络请求的成功率和匿名性。

主要功能：
- 地理位置分组的代理管理
- 代理质量评估和监控
- 匿名性等级检测
- 智能代理轮换策略
- 代理池管理和优化
- 故障恢复和自动切换
- 负载均衡算法
- 代理验证和健康检查

技术特点：
- 支持HTTP/HTTPS/SOCKS4/SOCKS5代理
- 实时代理质量监控
- 智能故障检测和恢复
- 地理位置智能分组
- 多维度代理评分系统

Author: Mercari AI Agent Team
"""

import asyncio
import logging
import random
import time
import json
import hashlib
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from urllib.parse import urlparse
import aiohttp
from aiohttp import ClientSession, ClientTimeout, TCPConnector, ClientProxyConnectionError
from aiohttp.client_exceptions import ClientError
from collections import defaultdict, deque
import socket
import struct
import geoip2.database
import geoip2.errors
from concurrent.futures import ThreadPoolExecutor
import ssl

from ..utils.logger import get_logger
from ..config.settings import settings

logger = get_logger(__name__)


class ProxyType(Enum):
    """代理类型枚举"""
    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"


class ProxyStatus(Enum):
    """代理状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    TESTING = "testing"
    FAILED = "failed"
    BANNED = "banned"
    EXPIRED = "expired"


class AnonymityLevel(Enum):
    """匿名性等级枚举"""
    TRANSPARENT = "transparent"
    ANONYMOUS = "anonymous"
    ELITE = "elite"
    UNKNOWN = "unknown"


class ProxyRegion(Enum):
    """代理地区枚举"""
    NORTH_AMERICA = "north_america"
    EUROPE = "europe"
    ASIA = "asia"
    OCEANIA = "oceania"
    SOUTH_AMERICA = "south_america"
    AFRICA = "africa"
    UNKNOWN = "unknown"


@dataclass
class ProxyInfo:
    """代理信息数据结构"""
    proxy_id: str
    host: str
    port: int
    proxy_type: ProxyType
    username: Optional[str] = None
    password: Optional[str] = None
    country: Optional[str] = None
    region: Optional[ProxyRegion] = None
    city: Optional[str] = None
    isp: Optional[str] = None
    anonymity_level: AnonymityLevel = AnonymityLevel.UNKNOWN
    status: ProxyStatus = ProxyStatus.INACTIVE
    
    # 性能指标
    response_time: float = 0.0
    success_rate: float = 0.0
    last_test_time: Optional[datetime] = None
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    
    # 质量评分
    quality_score: float = 0.0
    stability_score: float = 0.0
    speed_score: float = 0.0
    anonymity_score: float = 0.0
    
    # 使用统计
    last_used: Optional[datetime] = None
    usage_count: int = 0
    consecutive_failures: int = 0
    
    # 标签和元数据
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'proxy_id': self.proxy_id,
            'host': self.host,
            'port': self.port,
            'proxy_type': self.proxy_type.value,
            'username': self.username,
            'password': self.password,
            'country': self.country,
            'region': self.region.value if self.region else None,
            'city': self.city,
            'isp': self.isp,
            'anonymity_level': self.anonymity_level.value,
            'status': self.status.value,
            'response_time': self.response_time,
            'success_rate': self.success_rate,
            'last_test_time': self.last_test_time.isoformat() if self.last_test_time else None,
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'quality_score': self.quality_score,
            'stability_score': self.stability_score,
            'speed_score': self.speed_score,
            'anonymity_score': self.anonymity_score,
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'usage_count': self.usage_count,
            'consecutive_failures': self.consecutive_failures,
            'tags': self.tags,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat()
        }
    
    def get_proxy_url(self) -> str:
        """获取代理URL"""
        if self.username and self.password:
            return f"{self.proxy_type.value}://{self.username}:{self.password}@{self.host}:{self.port}"
        else:
            return f"{self.proxy_type.value}://{self.host}:{self.port}"
    
    def update_metrics(self, success: bool, response_time: float = None):
        """更新代理指标"""
        self.total_requests += 1
        self.last_used = datetime.now()
        self.usage_count += 1
        
        if success:
            self.successful_requests += 1
            self.consecutive_failures = 0
            if response_time:
                # 更新平均响应时间
                if self.response_time > 0:
                    self.response_time = (self.response_time + response_time) / 2
                else:
                    self.response_time = response_time
        else:
            self.failed_requests += 1
            self.consecutive_failures += 1
        
        # 更新成功率
        if self.total_requests > 0:
            self.success_rate = self.successful_requests / self.total_requests
        
        # 更新质量评分
        self._update_quality_scores()
    
    def _update_quality_scores(self):
        """更新质量评分"""
        # 稳定性评分（基于成功率）
        self.stability_score = self.success_rate
        
        # 速度评分（基于响应时间）
        if self.response_time > 0:
            # 响应时间越短，分数越高
            if self.response_time < 1.0:
                self.speed_score = 1.0
            elif self.response_time < 3.0:
                self.speed_score = 0.8
            elif self.response_time < 5.0:
                self.speed_score = 0.6
            elif self.response_time < 10.0:
                self.speed_score = 0.4
            else:
                self.speed_score = 0.2
        
        # 匿名性评分
        anonymity_scores = {
            AnonymityLevel.ELITE: 1.0,
            AnonymityLevel.ANONYMOUS: 0.7,
            AnonymityLevel.TRANSPARENT: 0.3,
            AnonymityLevel.UNKNOWN: 0.5
        }
        self.anonymity_score = anonymity_scores.get(self.anonymity_level, 0.5)
        
        # 综合质量评分
        self.quality_score = (
            self.stability_score * 0.4 +
            self.speed_score * 0.3 +
            self.anonymity_score * 0.3
        )


@dataclass
class ProxyTestResult:
    """代理测试结果"""
    proxy_id: str
    test_url: str
    success: bool
    response_time: float
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    anonymity_level: AnonymityLevel = AnonymityLevel.UNKNOWN
    detected_ip: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    test_timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'proxy_id': self.proxy_id,
            'test_url': self.test_url,
            'success': self.success,
            'response_time': self.response_time,
            'status_code': self.status_code,
            'error_message': self.error_message,
            'anonymity_level': self.anonymity_level.value,
            'detected_ip': self.detected_ip,
            'headers': self.headers,
            'test_timestamp': self.test_timestamp.isoformat()
        }


@dataclass
class ProxyConfig:
    """代理配置"""
    max_concurrent_tests: int = 50
    test_timeout: float = 10.0
    test_interval: int = 300  # 5分钟
    max_consecutive_failures: int = 3
    proxy_rotation_interval: int = 180  # 3分钟
    
    # 地理位置配置
    enable_geolocation: bool = True
    geoip_database_path: Optional[str] = None
    preferred_regions: List[ProxyRegion] = field(default_factory=lambda: [ProxyRegion.ASIA, ProxyRegion.NORTH_AMERICA])
    
    # 质量标准
    min_quality_score: float = 0.6
    min_success_rate: float = 0.7
    max_response_time: float = 5.0
    required_anonymity_level: AnonymityLevel = AnonymityLevel.ANONYMOUS
    
    # 负载均衡
    load_balancing_algorithm: str = "weighted_round_robin"  # round_robin, weighted_round_robin, least_connections
    enable_sticky_sessions: bool = False
    session_affinity_duration: int = 300  # 5分钟
    
    # 故障恢复
    enable_auto_recovery: bool = True
    recovery_check_interval: int = 60  # 1分钟
    ban_duration: int = 1800  # 30分钟
    
    # 安全设置
    verify_ssl: bool = False
    custom_headers: Dict[str, str] = field(default_factory=dict)
    user_agent_rotation: bool = True


class GeoLocationService:
    """地理位置服务"""
    
    def __init__(self, config: ProxyConfig):
        self.config = config
        self.geoip_reader = None
        self.ip_cache: Dict[str, Dict[str, Any]] = {}
        
        if config.enable_geolocation and config.geoip_database_path:
            try:
                self.geoip_reader = geoip2.database.Reader(config.geoip_database_path)
                logger.info("GeoIP数据库加载成功")
            except Exception as e:
                logger.error(f"GeoIP数据库加载失败: {e}")
    
    def get_location_info(self, ip_address: str) -> Dict[str, Any]:
        """获取IP地理位置信息"""
        if ip_address in self.ip_cache:
            return self.ip_cache[ip_address]
        
        location_info = {
            'country': None,
            'region': ProxyRegion.UNKNOWN,
            'city': None,
            'isp': None,
            'coordinates': None
        }
        
        if self.geoip_reader:
            try:
                response = self.geoip_reader.city(ip_address)
                
                location_info['country'] = response.country.iso_code
                location_info['city'] = response.city.name
                
                # 映射到区域
                if response.continent.code:
                    region_mapping = {
                        'NA': ProxyRegion.NORTH_AMERICA,
                        'EU': ProxyRegion.EUROPE,
                        'AS': ProxyRegion.ASIA,
                        'OC': ProxyRegion.OCEANIA,
                        'SA': ProxyRegion.SOUTH_AMERICA,
                        'AF': ProxyRegion.AFRICA
                    }
                    location_info['region'] = region_mapping.get(response.continent.code, ProxyRegion.UNKNOWN)
                
                if response.location.latitude and response.location.longitude:
                    location_info['coordinates'] = (response.location.latitude, response.location.longitude)
                
                # 尝试获取ISP信息
                try:
                    isp_response = self.geoip_reader.isp(ip_address)
                    location_info['isp'] = isp_response.isp
                except:
                    pass
                
            except geoip2.errors.AddressNotFoundError:
                logger.debug(f"IP地址未找到地理位置信息: {ip_address}")
            except Exception as e:
                logger.error(f"获取地理位置信息失败: {e}")
        
        # 缓存结果
        self.ip_cache[ip_address] = location_info
        return location_info
    
    def calculate_distance(self, coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
        """计算两点之间的距离（公里）"""
        import math
        
        lat1, lon1 = coord1
        lat2, lon2 = coord2
        
        # 使用Haversine公式
        R = 6371  # 地球半径（公里）
        
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = (math.sin(dlat/2) * math.sin(dlat/2) +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon/2) * math.sin(dlon/2))
        
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = R * c
        
        return distance


class ProxyTester:
    """代理测试器"""
    
    def __init__(self, config: ProxyConfig):
        self.config = config
        self.test_urls = [
            "http://httpbin.org/ip",
            "https://httpbin.org/headers",
            "http://ifconfig.me/ip",
            "https://api.ipify.org?format=json"
        ]
        
        self.anonymity_test_headers = [
            'HTTP_VIA',
            'HTTP_X_FORWARDED_FOR',
            'HTTP_X_FORWARDED',
            'HTTP_X_CLUSTER_CLIENT_IP',
            'HTTP_FORWARDED_FOR',
            'HTTP_FORWARDED',
            'HTTP_CLIENT_IP',
            'REMOTE_ADDR'
        ]
        
        logger.info("代理测试器初始化完成")
    
    async def test_proxy(self, proxy_info: ProxyInfo) -> ProxyTestResult:
        """测试单个代理"""
        test_url = random.choice(self.test_urls)
        start_time = time.time()
        
        try:
            timeout = ClientTimeout(total=self.config.test_timeout)
            connector = TCPConnector(ssl=False if not self.config.verify_ssl else None)
            
            async with ClientSession(
                connector=connector,
                timeout=timeout,
                headers=self.config.custom_headers
            ) as session:
                
                proxy_url = proxy_info.get_proxy_url()
                
                async with session.get(test_url, proxy=proxy_url) as response:
                    response_time = time.time() - start_time
                    
                    if response.status == 200:
                        # 成功响应，检查匿名性
                        response_text = await response.text()
                        headers = dict(response.headers)
                        
                        # 检测匿名性级别
                        anonymity_level = await self._detect_anonymity_level(
                            response_text, headers, proxy_info.host
                        )
                        
                        # 提取检测到的IP
                        detected_ip = await self._extract_detected_ip(response_text, test_url)
                        
                        return ProxyTestResult(
                            proxy_id=proxy_info.proxy_id,
                            test_url=test_url,
                            success=True,
                            response_time=response_time,
                            status_code=response.status,
                            anonymity_level=anonymity_level,
                            detected_ip=detected_ip,
                            headers=headers
                        )
                    else:
                        return ProxyTestResult(
                            proxy_id=proxy_info.proxy_id,
                            test_url=test_url,
                            success=False,
                            response_time=response_time,
                            status_code=response.status,
                            error_message=f"HTTP {response.status}"
                        )
        
        except ClientProxyConnectionError as e:
            return ProxyTestResult(
                proxy_id=proxy_info.proxy_id,
                test_url=test_url,
                success=False,
                response_time=time.time() - start_time,
                error_message=f"代理连接失败: {str(e)}"
            )
        
        except asyncio.TimeoutError:
            return ProxyTestResult(
                proxy_id=proxy_info.proxy_id,
                test_url=test_url,
                success=False,
                response_time=time.time() - start_time,
                error_message="连接超时"
            )
        
        except Exception as e:
            return ProxyTestResult(
                proxy_id=proxy_info.proxy_id,
                test_url=test_url,
                success=False,
                response_time=time.time() - start_time,
                error_message=f"测试失败: {str(e)}"
            )
    
    async def _detect_anonymity_level(self, response_text: str, headers: Dict[str, str], 
                                    proxy_host: str) -> AnonymityLevel:
        """检测匿名性级别"""
        try:
            # 检查响应文本中是否包含真实IP
            if proxy_host in response_text:
                return AnonymityLevel.TRANSPARENT
            
            # 检查是否有代理相关头部
            proxy_headers_found = False
            for header_name in self.anonymity_test_headers:
                if header_name.lower() in [h.lower() for h in headers.keys()]:
                    proxy_headers_found = True
                    break
            
            if proxy_headers_found:
                return AnonymityLevel.ANONYMOUS
            else:
                return AnonymityLevel.ELITE
        
        except Exception as e:
            logger.error(f"匿名性检测失败: {e}")
            return AnonymityLevel.UNKNOWN
    
    async def _extract_detected_ip(self, response_text: str, test_url: str) -> Optional[str]:
        """提取检测到的IP地址"""
        try:
            if "httpbin.org/ip" in test_url:
                # 解析httpbin.org/ip响应
                import re
                ip_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
                matches = re.findall(ip_pattern, response_text)
                if matches:
                    return matches[0]
            
            elif "ipify.org" in test_url:
                # 解析ipify响应
                try:
                    import json
                    data = json.loads(response_text)
                    return data.get('ip')
                except:
                    return response_text.strip()
            
            elif "ifconfig.me" in test_url:
                # 解析ifconfig.me响应
                return response_text.strip()
            
        except Exception as e:
            logger.error(f"IP提取失败: {e}")
        
        return None
    
    async def batch_test_proxies(self, proxies: List[ProxyInfo]) -> List[ProxyTestResult]:
        """批量测试代理"""
        semaphore = asyncio.Semaphore(self.config.max_concurrent_tests)
        
        async def test_with_semaphore(proxy_info: ProxyInfo):
            async with semaphore:
                return await self.test_proxy(proxy_info)
        
        tasks = [test_with_semaphore(proxy) for proxy in proxies]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 过滤异常结果
        valid_results = []
        for result in results:
            if isinstance(result, ProxyTestResult):
                valid_results.append(result)
            elif isinstance(result, Exception):
                logger.error(f"代理测试异常: {result}")
        
        return valid_results


class LoadBalancer:
    """负载均衡器"""
    
    def __init__(self, config: ProxyConfig):
        self.config = config
        self.algorithm = config.load_balancing_algorithm
        self.round_robin_index = 0
        self.connection_counts: Dict[str, int] = defaultdict(int)
        self.session_affinity: Dict[str, Tuple[str, datetime]] = {}
        
        logger.info(f"负载均衡器初始化完成，算法: {self.algorithm}")
    
    def select_proxy(self, available_proxies: List[ProxyInfo], 
                    session_id: str = None) -> Optional[ProxyInfo]:
        """选择代理"""
        if not available_proxies:
            return None
        
        # 检查会话亲和性
        if session_id and self.config.enable_sticky_sessions:
            if session_id in self.session_affinity:
                proxy_id, timestamp = self.session_affinity[session_id]
                
                # 检查是否过期
                if (datetime.now() - timestamp).total_seconds() < self.config.session_affinity_duration:
                    # 找到对应的代理
                    for proxy in available_proxies:
                        if proxy.proxy_id == proxy_id:
                            return proxy
                else:
                    # 过期，删除记录
                    del self.session_affinity[session_id]
        
        # 根据算法选择代理
        if self.algorithm == "round_robin":
            selected_proxy = self._round_robin_select(available_proxies)
        elif self.algorithm == "weighted_round_robin":
            selected_proxy = self._weighted_round_robin_select(available_proxies)
        elif self.algorithm == "least_connections":
            selected_proxy = self._least_connections_select(available_proxies)
        else:
            # 默认随机选择
            selected_proxy = random.choice(available_proxies)
        
        # 更新会话亲和性
        if session_id and self.config.enable_sticky_sessions and selected_proxy:
            self.session_affinity[session_id] = (selected_proxy.proxy_id, datetime.now())
        
        # 更新连接计数
        if selected_proxy:
            self.connection_counts[selected_proxy.proxy_id] += 1
        
        return selected_proxy
    
    def _round_robin_select(self, proxies: List[ProxyInfo]) -> ProxyInfo:
        """轮询选择"""
        if not proxies:
            return None
        
        selected = proxies[self.round_robin_index % len(proxies)]
        self.round_robin_index += 1
        return selected
    
    def _weighted_round_robin_select(self, proxies: List[ProxyInfo]) -> ProxyInfo:
        """加权轮询选择"""
        if not proxies:
            return None
        
        # 根据质量评分创建权重
        weights = [max(0.1, proxy.quality_score) for proxy in proxies]
        
        # 使用numpy.random.choice进行加权选择
        try:
            import numpy as np
            weights = np.array(weights)
            weights = weights / weights.sum()  # 归一化
            
            selected_index = np.random.choice(len(proxies), p=weights)
            return proxies[selected_index]
        except ImportError:
            # 如果没有numpy，使用简单的加权选择
            total_weight = sum(weights)
            rand_value = random.uniform(0, total_weight)
            
            current_weight = 0
            for i, weight in enumerate(weights):
                current_weight += weight
                if rand_value <= current_weight:
                    return proxies[i]
            
            return proxies[-1]
    
    def _least_connections_select(self, proxies: List[ProxyInfo]) -> ProxyInfo:
        """最少连接选择"""
        if not proxies:
            return None
        
        # 选择连接数最少的代理
        min_connections = float('inf')
        selected_proxy = None
        
        for proxy in proxies:
            connections = self.connection_counts.get(proxy.proxy_id, 0)
            if connections < min_connections:
                min_connections = connections
                selected_proxy = proxy
        
        return selected_proxy
    
    def release_connection(self, proxy_id: str):
        """释放连接"""
        if proxy_id in self.connection_counts:
            self.connection_counts[proxy_id] = max(0, self.connection_counts[proxy_id] - 1)
    
    def get_load_statistics(self) -> Dict[str, Any]:
        """获取负载统计"""
        return {
            'algorithm': self.algorithm,
            'connection_counts': dict(self.connection_counts),
            'session_affinity_count': len(self.session_affinity),
            'round_robin_index': self.round_robin_index
        }


class ProxyPool:
    """代理池"""
    
    def __init__(self, config: ProxyConfig):
        self.config = config
        self.proxies: Dict[str, ProxyInfo] = {}
        self.active_proxies: Dict[str, ProxyInfo] = {}
        self.region_groups: Dict[ProxyRegion, List[str]] = defaultdict(list)
        self.quality_tiers: Dict[str, List[str]] = defaultdict(list)  # high, medium, low
        
        self.geolocation_service = GeoLocationService(config)
        self.proxy_tester = ProxyTester(config)
        self.load_balancer = LoadBalancer(config)
        
        # 测试和监控任务
        self.test_task = None
        self.monitor_task = None
        
        logger.info("代理池初始化完成")
    
    def add_proxy(self, host: str, port: int, proxy_type: ProxyType,
                 username: str = None, password: str = None,
                 tags: List[str] = None) -> str:
        """添加代理"""
        proxy_id = f"{host}:{port}:{proxy_type.value}"
        
        # 获取地理位置信息
        location_info = self.geolocation_service.get_location_info(host)
        
        proxy_info = ProxyInfo(
            proxy_id=proxy_id,
            host=host,
            port=port,
            proxy_type=proxy_type,
            username=username,
            password=password,
            country=location_info.get('country'),
            region=location_info.get('region', ProxyRegion.UNKNOWN),
            city=location_info.get('city'),
            isp=location_info.get('isp'),
            tags=tags or []
        )
        
        self.proxies[proxy_id] = proxy_info
        
        # 添加到地区分组
        if proxy_info.region:
            self.region_groups[proxy_info.region].append(proxy_id)
        
        logger.info(f"添加代理: {proxy_id} ({proxy_info.country}, {proxy_info.region})")
        return proxy_id
    
    def remove_proxy(self, proxy_id: str):
        """移除代理"""
        if proxy_id in self.proxies:
            proxy_info = self.proxies[proxy_id]
            
            # 从各个组中移除
            del self.proxies[proxy_id]
            
            if proxy_id in self.active_proxies:
                del self.active_proxies[proxy_id]
            
            if proxy_info.region in self.region_groups:
                if proxy_id in self.region_groups[proxy_info.region]:
                    self.region_groups[proxy_info.region].remove(proxy_id)
            
            # 从质量分层中移除
            for tier_proxies in self.quality_tiers.values():
                if proxy_id in tier_proxies:
                    tier_proxies.remove(proxy_id)
            
            logger.info(f"移除代理: {proxy_id}")
    
    def get_proxy(self, proxy_id: str) -> Optional[ProxyInfo]:
        """获取代理信息"""
        return self.proxies.get(proxy_id)
    
    def get_proxies_by_region(self, region: ProxyRegion) -> List[ProxyInfo]:
        """按地区获取代理"""
        proxy_ids = self.region_groups.get(region, [])
        return [self.proxies[proxy_id] for proxy_id in proxy_ids if proxy_id in self.proxies]
    
    def get_proxies_by_quality(self, quality_tier: str) -> List[ProxyInfo]:
        """按质量等级获取代理"""
        proxy_ids = self.quality_tiers.get(quality_tier, [])
        return [self.proxies[proxy_id] for proxy_id in proxy_ids if proxy_id in self.proxies]
    
    def get_available_proxies(self, min_quality: float = None, 
                            regions: List[ProxyRegion] = None,
                            anonymity_level: AnonymityLevel = None) -> List[ProxyInfo]:
        """获取可用代理"""
        available = []
        
        for proxy_info in self.active_proxies.values():
            # 检查质量分数
            if min_quality and proxy_info.quality_score < min_quality:
                continue
            
            # 检查地区
            if regions and proxy_info.region not in regions:
                continue
            
            # 检查匿名性级别
            if anonymity_level and proxy_info.anonymity_level != anonymity_level:
                continue
            
            available.append(proxy_info)
        
        return available
    
    def select_proxy(self, session_id: str = None, **filters) -> Optional[ProxyInfo]:
        """选择代理"""
        available_proxies = self.get_available_proxies(**filters)
        
        if not available_proxies:
            # 如果没有可用代理，尝试从所有代理中选择
            available_proxies = list(self.active_proxies.values())
        
        return self.load_balancer.select_proxy(available_proxies, session_id)
    
    async def start_monitoring(self):
        """启动监控任务"""
        if self.test_task is None:
            self.test_task = asyncio.create_task(self._test_loop())
        
        if self.monitor_task is None:
            self.monitor_task = asyncio.create_task(self._monitor_loop())
    
    async def _test_loop(self):
        """测试循环"""
        while True:
            try:
                await asyncio.sleep(self.config.test_interval)
                
                # 测试所有代理
                proxies_to_test = list(self.proxies.values())
                if proxies_to_test:
                    results = await self.proxy_tester.batch_test_proxies(proxies_to_test)
                    await self._process_test_results(results)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"代理测试循环出错: {e}")
    
    async def _monitor_loop(self):
        """监控循环"""
        while True:
            try:
                await asyncio.sleep(self.config.recovery_check_interval)
                
                # 检查故障恢复
                if self.config.enable_auto_recovery:
                    await self._check_recovery()
                
                # 更新质量分层
                self._update_quality_tiers()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"代理监控循环出错: {e}")
    
    async def _process_test_results(self, results: List[ProxyTestResult]):
        """处理测试结果"""
        for result in results:
            if result.proxy_id in self.proxies:
                proxy_info = self.proxies[result.proxy_id]
                
                # 更新代理指标
                proxy_info.update_metrics(result.success, result.response_time)
                proxy_info.last_test_time = result.test_timestamp
                
                # 更新匿名性级别
                if result.anonymity_level != AnonymityLevel.UNKNOWN:
                    proxy_info.anonymity_level = result.anonymity_level
                
                # 更新状态
                if result.success:
                    if proxy_info.status != ProxyStatus.ACTIVE:
                        proxy_info.status = ProxyStatus.ACTIVE
                        self.active_proxies[result.proxy_id] = proxy_info
                        logger.info(f"代理恢复活跃: {result.proxy_id}")
                else:
                    # 检查是否需要标记为失败
                    if proxy_info.consecutive_failures >= self.config.max_consecutive_failures:
                        proxy_info.status = ProxyStatus.FAILED
                        if result.proxy_id in self.active_proxies:
                            del self.active_proxies[result.proxy_id]
                        logger.warning(f"代理标记为失败: {result.proxy_id}")
    
    async def _check_recovery(self):
        """检查故障恢复"""
        current_time = datetime.now()
        
        for proxy_id, proxy_info in self.proxies.items():
            if proxy_info.status == ProxyStatus.FAILED:
                # 检查是否可以尝试恢复
                time_since_failure = (current_time - proxy_info.last_test_time).total_seconds() if proxy_info.last_test_time else 0
                
                if time_since_failure > self.config.recovery_check_interval:
                    # 尝试恢复测试
                    result = await self.proxy_tester.test_proxy(proxy_info)
                    
                    if result.success:
                        proxy_info.status = ProxyStatus.ACTIVE
                        proxy_info.consecutive_failures = 0
                        self.active_proxies[proxy_id] = proxy_info
                        logger.info(f"代理恢复成功: {proxy_id}")
    
    def _update_quality_tiers(self):
        """更新质量分层"""
        # 清空现有分层
        self.quality_tiers.clear()
        
        for proxy_id, proxy_info in self.active_proxies.items():
            if proxy_info.quality_score >= 0.8:
                self.quality_tiers['high'].append(proxy_id)
            elif proxy_info.quality_score >= 0.5:
                self.quality_tiers['medium'].append(proxy_id)
            else:
                self.quality_tiers['low'].append(proxy_id)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_proxies = len(self.proxies)
        active_proxies = len(self.active_proxies)
        
        # 按状态统计
        status_stats = defaultdict(int)
        for proxy_info in self.proxies.values():
            status_stats[proxy_info.status.value] += 1
        
        # 按地区统计
        region_stats = defaultdict(int)
        for proxy_info in self.proxies.values():
            region_stats[proxy_info.region.value if proxy_info.region else 'unknown'] += 1
        
        # 按匿名性统计
        anonymity_stats = defaultdict(int)
        for proxy_info in self.proxies.values():
            anonymity_stats[proxy_info.anonymity_level.value] += 1
        
        # 质量统计
        quality_stats = {
            'average_quality': sum(p.quality_score for p in self.active_proxies.values()) / len(self.active_proxies) if self.active_proxies else 0,
            'average_response_time': sum(p.response_time for p in self.active_proxies.values()) / len(self.active_proxies) if self.active_proxies else 0,
            'average_success_rate': sum(p.success_rate for p in self.active_proxies.values()) / len(self.active_proxies) if self.active_proxies else 0,
            'high_quality_count': len(self.quality_tiers['high']),
            'medium_quality_count': len(self.quality_tiers['medium']),
            'low_quality_count': len(self.quality_tiers['low'])
        }
        
        return {
            'total_proxies': total_proxies,
            'active_proxies': active_proxies,
            'status_distribution': dict(status_stats),
            'region_distribution': dict(region_stats),
            'anonymity_distribution': dict(anonymity_stats),
            'quality_statistics': quality_stats,
            'load_balancer_stats': self.load_balancer.get_load_statistics()
        }
    
    def export_proxies(self) -> str:
        """导出代理列表"""
        proxy_data = []
        for proxy_info in self.proxies.values():
            proxy_data.append(proxy_info.to_dict())
        
        return json.dumps(proxy_data, indent=2, ensure_ascii=False)
    
    def import_proxies(self, proxy_data: str):
        """导入代理列表"""
        try:
            proxies = json.loads(proxy_data)
            imported_count = 0
            
            for proxy_dict in proxies:
                try:
                    proxy_info = ProxyInfo(
                        proxy_id=proxy_dict['proxy_id'],
                        host=proxy_dict['host'],
                        port=proxy_dict['port'],
                        proxy_type=ProxyType(proxy_dict['proxy_type']),
                        username=proxy_dict.get('username'),
                        password=proxy_dict.get('password'),
                        country=proxy_dict.get('country'),
                        region=ProxyRegion(proxy_dict['region']) if proxy_dict.get('region') else None,
                        city=proxy_dict.get('city'),
                        isp=proxy_dict.get('isp'),
                        anonymity_level=AnonymityLevel(proxy_dict.get('anonymity_level', 'unknown')),
                        status=ProxyStatus(proxy_dict.get('status', 'inactive')),
                        tags=proxy_dict.get('tags', []),
                        metadata=proxy_dict.get('metadata', {})
                    )
                    
                    # 恢复统计数据
                    proxy_info.response_time = proxy_dict.get('response_time', 0.0)
                    proxy_info.success_rate = proxy_dict.get('success_rate', 0.0)
                    proxy_info.total_requests = proxy_dict.get('total_requests', 0)
                    proxy_info.successful_requests = proxy_dict.get('successful_requests', 0)
                    proxy_info.failed_requests = proxy_dict.get('failed_requests', 0)
                    proxy_info.quality_score = proxy_dict.get('quality_score', 0.0)
                    proxy_info.usage_count = proxy_dict.get('usage_count', 0)
                    proxy_info.consecutive_failures = proxy_dict.get('consecutive_failures', 0)
                    
                    if proxy_dict.get('last_test_time'):
                        proxy_info.last_test_time = datetime.fromisoformat(proxy_dict['last_test_time'])
                    
                    if proxy_dict.get('last_used'):
                        proxy_info.last_used = datetime.fromisoformat(proxy_dict['last_used'])
                    
                    if proxy_dict.get('created_at'):
                        proxy_info.created_at = datetime.fromisoformat(proxy_dict['created_at'])
                    
                    # 添加到池中
                    self.proxies[proxy_info.proxy_id] = proxy_info
                    
                    if proxy_info.status == ProxyStatus.ACTIVE:
                        self.active_proxies[proxy_info.proxy_id] = proxy_info
                    
                    # 添加到地区分组
                    if proxy_info.region:
                        self.region_groups[proxy_info.region].append(proxy_info.proxy_id)
                    
                    imported_count += 1
                    
                except Exception as e:
                    logger.error(f"导入代理失败: {e}")
                    continue
            
            # 更新质量分层
            self._update_quality_tiers()
            
            logger.info(f"成功导入 {imported_count} 个代理")
            
        except Exception as e:
            logger.error(f"代理导入失败: {e}")
    
    async def close(self):
        """关闭代理池"""
        if self.test_task:
            self.test_task.cancel()
            try:
                await self.test_task
            except asyncio.CancelledError:
                pass
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("代理池已关闭")


class AdvancedProxyManager:
    """高级代理管理器主类"""
    
    def __init__(self, config: Optional[ProxyConfig] = None):
        self.config = config or ProxyConfig()
        self.proxy_pool = ProxyPool(self.config)
        self.session_proxies: Dict[str, str] = {}  # session_id -> proxy_id
        self.proxy_usage_history: deque = deque(maxlen=1000)
        
        logger.info("高级代理管理器初始化完成")
    
    async def add_proxy(self, host: str, port: int, proxy_type: str,
                       username: str = None, password: str = None,
                       tags: List[str] = None) -> str:
        """添加代理"""
        proxy_type_enum = ProxyType(proxy_type.lower())
        return self.proxy_pool.add_proxy(host, port, proxy_type_enum, username, password, tags)
    
    async def remove_proxy(self, proxy_id: str):
        """移除代理"""
        self.proxy_pool.remove_proxy(proxy_id)
    
    async def get_proxy_for_session(self, session_id: str, **filters) -> Optional[ProxyInfo]:
        """为会话获取代理"""
        # 检查是否已有代理绑定
        if session_id in self.session_proxies:
            proxy_id = self.session_proxies[session_id]
            proxy_info = self.proxy_pool.get_proxy(proxy_id)
            
            if proxy_info and proxy_info.status == ProxyStatus.ACTIVE:
                return proxy_info
            else:
                # 代理不可用，移除绑定
                del self.session_proxies[session_id]
        
        # 选择新代理
        proxy_info = self.proxy_pool.select_proxy(session_id, **filters)
        
        if proxy_info:
            self.session_proxies[session_id] = proxy_info.proxy_id
            
            # 记录使用历史
            self.proxy_usage_history.append({
                'session_id': session_id,
                'proxy_id': proxy_info.proxy_id,
                'timestamp': datetime.now(),
                'filters': filters
            })
        
        return proxy_info
    
    async def release_proxy_for_session(self, session_id: str):
        """释放会话代理"""
        if session_id in self.session_proxies:
            proxy_id = self.session_proxies[session_id]
            self.proxy_pool.load_balancer.release_connection(proxy_id)
            del self.session_proxies[session_id]
    
    async def rotate_proxy_for_session(self, session_id: str, **filters) -> Optional[ProxyInfo]:
        """轮换会话代理"""
        await self.release_proxy_for_session(session_id)
        return await self.get_proxy_for_session(session_id, **filters)
    
    async def test_proxy(self, proxy_id: str) -> ProxyTestResult:
        """测试单个代理"""
        proxy_info = self.proxy_pool.get_proxy(proxy_id)
        if not proxy_info:
            raise ValueError(f"代理不存在: {proxy_id}")
        
        return await self.proxy_pool.proxy_tester.test_proxy(proxy_info)
    
    async def start_monitoring(self):
        """启动监控"""
        await self.proxy_pool.start_monitoring()
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        pool_stats = self.proxy_pool.get_statistics()
        
        # 添加会话统计
        pool_stats['session_statistics'] = {
            'active_sessions': len(self.session_proxies),
            'total_usage_history': len(self.proxy_usage_history)
        }
        
        return pool_stats
    
    def export_config(self) -> str:
        """导出配置"""
        return json.dumps({
            'proxies': self.proxy_pool.export_proxies(),
            'config': {
                'max_concurrent_tests': self.config.max_concurrent_tests,
                'test_timeout': self.config.test_timeout,
                'test_interval': self.config.test_interval,
                'max_consecutive_failures': self.config.max_consecutive_failures,
                'min_quality_score': self.config.min_quality_score,
                'min_success_rate': self.config.min_success_rate,
                'max_response_time': self.config.max_response_time,
                'load_balancing_algorithm': self.config.load_balancing_algorithm,
                'enable_auto_recovery': self.config.enable_auto_recovery
            }
        }, indent=2, ensure_ascii=False)
    
    async def import_config(self, config_data: str):
        """导入配置"""
        try:
            data = json.loads(config_data)
            
            # 导入代理
            if 'proxies' in data:
                self.proxy_pool.import_proxies(data['proxies'])
            
            # 导入配置
            if 'config' in data:
                config_dict = data['config']
                self.config.max_concurrent_tests = config_dict.get('max_concurrent_tests', self.config.max_concurrent_tests)
                self.config.test_timeout = config_dict.get('test_timeout', self.config.test_timeout)
                self.config.test_interval = config_dict.get('test_interval', self.config.test_interval)
                self.config.max_consecutive_failures = config_dict.get('max_consecutive_failures', self.config.max_consecutive_failures)
                self.config.min_quality_score = config_dict.get('min_quality_score', self.config.min_quality_score)
                self.config.min_success_rate = config_dict.get('min_success_rate', self.config.min_success_rate)
                self.config.max_response_time = config_dict.get('max_response_time', self.config.max_response_time)
                self.config.load_balancing_algorithm = config_dict.get('load_balancing_algorithm', self.config.load_balancing_algorithm)
                self.config.enable_auto_recovery = config_dict.get('enable_auto_recovery', self.config.enable_auto_recovery)
            
            logger.info("配置导入成功")
            
        except Exception as e:
            logger.error(f"配置导入失败: {e}")
    
    async def close(self):
        """关闭管理器"""
        await self.proxy_pool.close()
        logger.info("高级代理管理器已关闭")
    
    async def __aenter__(self):
        await self.start_monitoring()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# 工厂函数
def create_proxy_manager(config: Optional[ProxyConfig] = None) -> AdvancedProxyManager:
    """创建代理管理器实例"""
    return AdvancedProxyManager(config)


# 便捷函数
def create_high_performance_proxy_manager() -> AdvancedProxyManager:
    """创建高性能代理管理器"""
    config = ProxyConfig(
        max_concurrent_tests=100,
        test_timeout=5.0,
        test_interval=180,
        min_quality_score=0.8,
        min_success_rate=0.9,
        max_response_time=3.0,
        load_balancing_algorithm="weighted_round_robin",
        enable_auto_recovery=True
    )
    return AdvancedProxyManager(config)


def create_anonymous_proxy_manager() -> AdvancedProxyManager:
    """创建匿名代理管理器"""
    config = ProxyConfig(
        required_anonymity_level=AnonymityLevel.ELITE,
        min_quality_score=0.7,
        enable_geolocation=True,
        preferred_regions=[ProxyRegion.EUROPE, ProxyRegion.NORTH_AMERICA],
        verify_ssl=False
    )
    return AdvancedProxyManager(config)


if __name__ == "__main__":
    # 测试代码
    async def test_proxy_manager():
        """测试代理管理器"""
        async with create_proxy_manager() as manager:
            # 添加测试代理
            proxy_id = await manager.add_proxy("127.0.0.1", 8080, "http")
            print(f"添加代理: {proxy_id}")
            
            # 获取代理
            proxy_info = await manager.get_proxy_for_session("test_session")
            if proxy_info:
                print(f"获取代理: {proxy_info.proxy_id}")
                
                # 测试代理
                try:
                    result = await manager.test_proxy(proxy_info.proxy_id)
                    print(f"代理测试结果: {result.success}")
                except Exception as e:
                    print(f"代理测试失败: {e}")
            
            # 获取统计信息
            stats = manager.get_statistics()
            print(f"统计信息: {stats}")
    
    # 运行测试
    asyncio.run(test_proxy_manager())