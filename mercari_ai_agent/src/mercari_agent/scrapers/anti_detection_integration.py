"""
反检测系统集成适配器

该模块作为反检测系统的统一入口，整合了浏览器环境伪装、增强指纹管理、
TLS指纹管理等多个组件，提供一站式的反检测解决方案。

主要功能：
1. 统一的反检测系统管理 - 协调所有反检测组件
2. 会话生命周期管理 - 从创建到销毁的完整管理
3. 智能检测响应 - 自动响应各种检测事件
4. 性能优化 - 资源复用和缓存管理
5. 兼容性保证 - 与现有系统的无缝集成

集成组件：
- BrowserEnvironmentSpoofing - 环境伪装
- EnhancedFingerprintManager - 增强指纹管理
- TLSFingerprintManager - TLS指纹管理
- AntiBotHandler - 反爬虫处理
- EnhancedSessionManager - 会话管理

Author: Mercari AI Agent Team
"""

import asyncio
import logging
import time
import json
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import aiohttp
from urllib.parse import urlparse

from .browser_environment_spoofing import (
    BrowserEnvironmentSpoofing, SpoofingConfig, SpoofingLevel, DetectionType
)
from .enhanced_fingerprint_manager import (
    EnhancedFingerprintManager, FingerprintQuality, create_enhanced_fingerprint_manager
)
from .enhanced_session_manager import EnhancedSessionManager, SessionConfig
from .anti_bot_handler import AntiBotHandler, BotDetectionResult, BypassResult
from .tls_fingerprint_manager import TLSFingerprintManager
from .browser_fingerprint_manager import FingerprintConfig
from ..utils.logger import get_logger
from ..config.settings import settings

logger = get_logger(__name__)


class IntegrationMode(Enum):
    """集成模式枚举"""
    STEALTH = "stealth"           # 隐身模式 - 最大程度避免检测
    BALANCED = "balanced"         # 平衡模式 - 性能与安全的平衡
    PERFORMANCE = "performance"   # 性能模式 - 优先考虑性能
    DEBUGGING = "debugging"       # 调试模式 - 用于问题排查


class DetectionEvent(Enum):
    """检测事件类型"""
    CAPTCHA_TRIGGERED = "captcha_triggered"
    IP_BLOCKED = "ip_blocked"
    SESSION_EXPIRED = "session_expired"
    RATE_LIMITED = "rate_limited"
    USER_AGENT_BLOCKED = "user_agent_blocked"
    FINGERPRINT_DETECTED = "fingerprint_detected"
    JAVASCRIPT_CHALLENGE = "javascript_challenge"


@dataclass
class IntegrationConfig:
    """集成配置"""
    mode: IntegrationMode = IntegrationMode.BALANCED
    
    # 组件启用配置
    enable_environment_spoofing: bool = True
    enable_enhanced_fingerprinting: bool = True
    enable_tls_fingerprinting: bool = True
    enable_anti_bot_handler: bool = True
    enable_session_management: bool = True
    
    # 性能配置
    max_concurrent_sessions: int = 3
    session_timeout: int = 1800
    fingerprint_cache_size: int = 50
    
    # 检测响应配置
    auto_handle_captcha: bool = True
    auto_rotate_on_detection: bool = True
    detection_cooldown_time: int = 300
    
    # 质量配置
    min_fingerprint_quality: FingerprintQuality = FingerprintQuality.FAIR
    preferred_spoofing_level: SpoofingLevel = SpoofingLevel.STANDARD
    
    # 调试配置
    debug_mode: bool = False
    log_all_requests: bool = False
    save_detection_samples: bool = False


@dataclass
class DetectionEventData:
    """检测事件数据"""
    event_type: DetectionEvent
    session_id: str
    timestamp: datetime
    url: str
    response_status: Optional[int] = None
    response_content: Optional[str] = None
    fingerprint_id: Optional[str] = None
    detection_details: Dict[str, Any] = field(default_factory=dict)
    handled: bool = False
    handler_result: Optional[Any] = None


@dataclass
class SessionContext:
    """会话上下文"""
    session_id: str
    session: Optional[aiohttp.ClientSession]
    fingerprint_id: Optional[str]
    creation_time: datetime
    last_activity: datetime
    request_count: int = 0
    detection_events: List[DetectionEventData] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AntiDetectionIntegration:
    """反检测系统集成主类"""
    
    def __init__(self, config: Optional[IntegrationConfig] = None):
        """
        初始化反检测集成系统
        
        Args:
            config: 集成配置
        """
        self.config = config or IntegrationConfig()
        
        # 初始化组件
        self.fingerprint_manager: Optional[EnhancedFingerprintManager] = None
        self.session_manager: Optional[EnhancedSessionManager] = None
        self.anti_bot_handler: Optional[AntiBotHandler] = None
        self.tls_manager: Optional[TLSFingerprintManager] = None
        
        # 会话管理
        self.active_sessions: Dict[str, SessionContext] = {}
        self.session_lock = asyncio.Lock()
        
        # 检测事件管理
        self.detection_events: List[DetectionEventData] = []
        self.event_handlers: Dict[DetectionEvent, List[Callable]] = {}
        
        # 统计信息
        self.stats = {
            "total_sessions": 0,
            "active_sessions": 0,
            "detection_events": 0,
            "successful_bypasses": 0,
            "failed_bypasses": 0,
            "average_session_duration": 0.0
        }
        
        # 初始化状态
        self._initialized = False
        self._initialization_lock = asyncio.Lock()
        
        logger.info("🔧 反检测系统集成器初始化完成")
    
    async def initialize(self):
        """异步初始化所有组件"""
        async with self._initialization_lock:
            if self._initialized:
                return
            
            try:
                logger.info("🚀 开始初始化反检测系统...")
                
                # 根据配置和模式初始化组件
                await self._initialize_components()
                
                # 注册默认事件处理器
                self._register_default_handlers()
                
                # 启动后台任务
                await self._start_background_tasks()
                
                self._initialized = True
                logger.info("✅ 反检测系统初始化完成")
                
            except Exception as e:
                logger.error(f"❌ 反检测系统初始化失败: {e}")
                raise
    
    async def _initialize_components(self):
        """初始化各个组件"""
        # 1. 初始化增强指纹管理器
        if self.config.enable_enhanced_fingerprinting:
            self.fingerprint_manager = await create_enhanced_fingerprint_manager(
                self.config.preferred_spoofing_level
            )
            logger.info("✅ 增强指纹管理器初始化完成")
        
        # 2. 初始化会话管理器
        if self.config.enable_session_management:
            session_config = SessionConfig(
                max_concurrent_sessions=self.config.max_concurrent_sessions,
                session_timeout=self.config.session_timeout
            )
            self.session_manager = EnhancedSessionManager(session_config)
            await self.session_manager.initialize()
            logger.info("✅ 会话管理器初始化完成")
        
        # 3. 初始化反爬虫处理器
        if self.config.enable_anti_bot_handler:
            self.anti_bot_handler = AntiBotHandler()
            logger.info("✅ 反爬虫处理器初始化完成")
        
        # 4. 初始化TLS指纹管理器
        if self.config.enable_tls_fingerprinting:
            self.tls_manager = TLSFingerprintManager()
            logger.info("✅ TLS指纹管理器初始化完成")
    
    def _register_default_handlers(self):
        """注册默认事件处理器"""
        # CAPTCHA处理
        self.register_event_handler(DetectionEvent.CAPTCHA_TRIGGERED, self._handle_captcha)
        
        # IP阻断处理
        self.register_event_handler(DetectionEvent.IP_BLOCKED, self._handle_ip_block)
        
        # 会话过期处理
        self.register_event_handler(DetectionEvent.SESSION_EXPIRED, self._handle_session_expired)
        
        # 速率限制处理
        self.register_event_handler(DetectionEvent.RATE_LIMITED, self._handle_rate_limit)
        
        # 指纹检测处理
        self.register_event_handler(DetectionEvent.FINGERPRINT_DETECTED, self._handle_fingerprint_detected)
        
        logger.info("✅ 默认事件处理器注册完成")
    
    async def _start_background_tasks(self):
        """启动后台任务"""
        # 定期清理过期会话
        asyncio.create_task(self._cleanup_expired_sessions())
        
        # 定期更新统计信息
        asyncio.create_task(self._update_stats_periodically())
        
        # 定期清理检测事件
        asyncio.create_task(self._cleanup_old_events())
        
        logger.info("✅ 后台任务启动完成")
    
    async def create_session(self, session_id: Optional[str] = None) -> str:
        """
        创建新会话
        
        Args:
            session_id: 指定会话ID，如果为None则自动生成
            
        Returns:
            str: 会话ID
        """
        if not self._initialized:
            await self.initialize()
        
        session_id = session_id or f"session_{int(time.time())}_{len(self.active_sessions)}"
        
        async with self.session_lock:
            # 检查会话是否已存在
            if session_id in self.active_sessions:
                logger.warning(f"会话 {session_id} 已存在")
                return session_id
            
            try:
                # 获取会话对象
                session = None
                if self.session_manager:
                    session = await self.session_manager.get_session_safe(session_id)
                
                # 创建会话上下文
                context = SessionContext(
                    session_id=session_id,
                    session=session,
                    fingerprint_id=None,
                    creation_time=datetime.now(),
                    last_activity=datetime.now()
                )
                
                self.active_sessions[session_id] = context
                self.stats["total_sessions"] += 1
                
                logger.info(f"✅ 创建会话: {session_id}")
                return session_id
                
            except Exception as e:
                logger.error(f"❌ 创建会话失败: {e}")
                raise
    
    async def prepare_request(self, 
                            session_id: str, 
                            url: str, 
                            method: str = "GET",
                            **kwargs) -> Dict[str, Any]:
        """
        准备请求（应用所有反检测措施）
        
        Args:
            session_id: 会话ID
            url: 目标URL
            method: HTTP方法
            **kwargs: 其他请求参数
            
        Returns:
            Dict[str, Any]: 准备好的请求参数
        """
        if not self._initialized:
            await self.initialize()
        
        # 获取会话上下文
        context = self.active_sessions.get(session_id)
        if not context:
            raise ValueError(f"会话 {session_id} 不存在")
        
        try:
            # 1. 获取或分配指纹
            fingerprint = await self._get_session_fingerprint(session_id, url)
            
            # 2. 准备请求头
            headers = self._prepare_headers(fingerprint, kwargs.get('headers', {}))
            
            # 3. 准备TLS配置
            ssl_context = None
            if self.tls_manager and fingerprint.tls_fingerprint:
                ssl_context = self.tls_manager.create_ssl_context(fingerprint.tls_fingerprint)
            
            # 4. 准备连接器
            connector = None
            if self.tls_manager and fingerprint.tls_fingerprint:
                connector = self.tls_manager.create_connector(fingerprint.tls_fingerprint)
            
            # 5. 准备JavaScript注入脚本
            injection_script = None
            if self.fingerprint_manager and fingerprint.spoofing_result:
                injection_script = self.fingerprint_manager.spoofing_system.get_injection_script(session_id)
            
            # 6. 更新会话活动
            context.last_activity = datetime.now()
            context.request_count += 1
            
            # 7. 组装请求参数
            request_params = {
                'method': method,
                'url': url,
                'headers': headers,
                'ssl': ssl_context,
                'connector': connector,
                'injection_script': injection_script,
                'session_id': session_id,
                'fingerprint_id': fingerprint.fingerprint_id
            }
            
            # 8. 合并用户提供的参数
            for key, value in kwargs.items():
                if key not in request_params:
                    request_params[key] = value
            
            logger.debug(f"✅ 请求准备完成: {session_id} -> {url}")
            return request_params
            
        except Exception as e:
            logger.error(f"❌ 请求准备失败: {e}")
            raise
    
    async def _get_session_fingerprint(self, session_id: str, url: str):
        """获取会话指纹"""
        context = self.active_sessions[session_id]
        
        # 如果已有指纹且仍有效，直接返回
        if context.fingerprint_id and self.fingerprint_manager:
            fingerprint = self.fingerprint_manager.fingerprint_pool.get(context.fingerprint_id)
            if fingerprint and fingerprint.is_usable:
                return fingerprint
        
        # 获取新指纹
        if self.fingerprint_manager:
            fingerprint = await self.fingerprint_manager.get_fingerprint_for_session(
                session_id=session_id,
                target_url=url,
                preferred_quality=self.config.min_fingerprint_quality
            )
            
            if fingerprint:
                context.fingerprint_id = fingerprint.fingerprint_id
                return fingerprint
        
        # 如果没有指纹管理器，返回基础指纹
        return None
    
    def _prepare_headers(self, fingerprint, user_headers: Dict[str, str]) -> Dict[str, str]:
        """准备请求头"""
        headers = {}
        
        # 基础头部
        if fingerprint and fingerprint.spoofing_result:
            headers.update(self.fingerprint_manager.spoofing_system.get_spoofing_headers(fingerprint.base_fingerprint))
        
        # 用户自定义头部
        headers.update(user_headers)
        
        return headers
    
    async def execute_request(self, 
                            session_id: str, 
                            url: str, 
                            method: str = "GET",
                            **kwargs) -> aiohttp.ClientResponse:
        """
        执行请求（带完整的反检测保护）
        
        Args:
            session_id: 会话ID
            url: 目标URL
            method: HTTP方法
            **kwargs: 其他请求参数
            
        Returns:
            aiohttp.ClientResponse: 响应对象
        """
        # 准备请求
        request_params = await self.prepare_request(session_id, url, method, **kwargs)
        
        # 获取会话
        context = self.active_sessions[session_id]
        session = context.session
        
        if not session:
            raise ValueError(f"会话 {session_id} 无效")
        
        try:
            # 移除非aiohttp参数
            clean_params = {k: v for k, v in request_params.items() 
                          if k in ['headers', 'params', 'data', 'json', 'cookies', 'timeout', 'ssl']}
            
            # 执行请求
            response = await session.request(method, url, **clean_params)
            
            # 检测响应
            await self._analyze_response(session_id, response)
            
            return response
            
        except Exception as e:
            logger.error(f"❌ 请求执行失败: {e}")
            await self._handle_request_error(session_id, e)
            raise
    
    async def _analyze_response(self, session_id: str, response: aiohttp.ClientResponse):
        """分析响应并检测反爬虫"""
        try:
            # 读取响应内容
            content = await response.text()
            
            # 检测反爬虫
            if self.anti_bot_handler:
                detection_result = self.anti_bot_handler.detect_bot_protection(content, response)
                
                if detection_result.is_detected:
                    # 触发检测事件
                    await self._trigger_detection_event(
                        session_id=session_id,
                        event_type=self._map_detection_to_event(detection_result.detection_type),
                        response=response,
                        content=content,
                        detection_details=detection_result.details
                    )
            
        except Exception as e:
            logger.error(f"响应分析失败: {e}")
    
    def _map_detection_to_event(self, detection_type) -> DetectionEvent:
        """将检测类型映射到事件类型"""
        mapping = {
            'captcha': DetectionEvent.CAPTCHA_TRIGGERED,
            'ip_block': DetectionEvent.IP_BLOCKED,
            'rate_limit': DetectionEvent.RATE_LIMITED,
            'user_agent_block': DetectionEvent.USER_AGENT_BLOCKED,
            'fingerprint_detection': DetectionEvent.FINGERPRINT_DETECTED,
            'js_challenge': DetectionEvent.JAVASCRIPT_CHALLENGE
        }
        return mapping.get(detection_type.value, DetectionEvent.FINGERPRINT_DETECTED)
    
    async def _trigger_detection_event(self, 
                                     session_id: str, 
                                     event_type: DetectionEvent,
                                     response: aiohttp.ClientResponse,
                                     content: str,
                                     detection_details: Dict[str, Any]):
        """触发检测事件"""
        event_data = DetectionEventData(
            event_type=event_type,
            session_id=session_id,
            timestamp=datetime.now(),
            url=str(response.url),
            response_status=response.status,
            response_content=content[:1000] if content else None,  # 限制内容长度
            detection_details=detection_details
        )
        
        # 添加到事件列表
        self.detection_events.append(event_data)
        self.stats["detection_events"] += 1
        
        # 触发事件处理器
        await self._handle_detection_event(event_data)
        
        logger.warning(f"🚨 检测事件触发: {event_type.value} - {session_id}")
    
    async def _handle_detection_event(self, event_data: DetectionEventData):
        """处理检测事件"""
        handlers = self.event_handlers.get(event_data.event_type, [])
        
        for handler in handlers:
            try:
                result = await handler(event_data)
                if result:
                    event_data.handled = True
                    event_data.handler_result = result
                    self.stats["successful_bypasses"] += 1
                    break
            except Exception as e:
                logger.error(f"事件处理器失败: {e}")
                self.stats["failed_bypasses"] += 1
    
    # 事件处理器
    async def _handle_captcha(self, event_data: DetectionEventData) -> bool:
        """处理CAPTCHA事件"""
        if not self.config.auto_handle_captcha:
            return False
        
        logger.info(f"🔧 处理CAPTCHA: {event_data.session_id}")
        
        # 报告CAPTCHA给指纹管理器
        if self.fingerprint_manager:
            await self.fingerprint_manager.report_captcha(event_data.session_id)
        
        # 如果配置了自动轮换，轮换指纹
        if self.config.auto_rotate_on_detection:
            await self._rotate_session_fingerprint(event_data.session_id)
        
        return True
    
    async def _handle_ip_block(self, event_data: DetectionEventData) -> bool:
        """处理IP阻断事件"""
        logger.info(f"🔧 处理IP阻断: {event_data.session_id}")
        
        # 这里可以集成代理轮换逻辑
        # 暂时只是记录事件
        return False
    
    async def _handle_session_expired(self, event_data: DetectionEventData) -> bool:
        """处理会话过期事件"""
        logger.info(f"🔧 处理会话过期: {event_data.session_id}")
        
        # 重新创建会话
        await self.close_session(event_data.session_id)
        await self.create_session(event_data.session_id)
        
        return True
    
    async def _handle_rate_limit(self, event_data: DetectionEventData) -> bool:
        """处理速率限制事件"""
        logger.info(f"🔧 处理速率限制: {event_data.session_id}")
        
        # 添加冷却时间
        await asyncio.sleep(self.config.detection_cooldown_time)
        
        return True
    
    async def _handle_fingerprint_detected(self, event_data: DetectionEventData) -> bool:
        """处理指纹检测事件"""
        logger.info(f"🔧 处理指纹检测: {event_data.session_id}")
        
        # 报告检测给指纹管理器
        if self.fingerprint_manager:
            await self.fingerprint_manager.report_detection(
                event_data.session_id, 
                event_data.event_type.value
            )
        
        # 轮换指纹
        if self.config.auto_rotate_on_detection:
            await self._rotate_session_fingerprint(event_data.session_id)
        
        return True
    
    async def _rotate_session_fingerprint(self, session_id: str):
        """轮换会话指纹"""
        context = self.active_sessions.get(session_id)
        if not context:
            return
        
        # 释放当前指纹
        if self.fingerprint_manager and context.fingerprint_id:
            await self.fingerprint_manager.release_session(session_id)
        
        # 重置指纹ID
        context.fingerprint_id = None
        
        logger.info(f"🔄 轮换会话指纹: {session_id}")
    
    async def _handle_request_error(self, session_id: str, error: Exception):
        """处理请求错误"""
        logger.error(f"请求错误: {session_id} - {error}")
        
        # 可以根据错误类型触发相应的事件
        # 这里暂时只是记录
    
    def register_event_handler(self, event_type: DetectionEvent, handler: Callable):
        """注册事件处理器"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    async def close_session(self, session_id: str):
        """关闭会话"""
        async with self.session_lock:
            context = self.active_sessions.get(session_id)
            if not context:
                return
            
            # 释放指纹
            if self.fingerprint_manager and context.fingerprint_id:
                await self.fingerprint_manager.release_session(session_id)
            
            # 关闭会话
            if context.session and not context.session.closed:
                await context.session.close()
            
            # 从活跃会话中移除
            del self.active_sessions[session_id]
            
            logger.info(f"✅ 关闭会话: {session_id}")
    
    async def _cleanup_expired_sessions(self):
        """清理过期会话"""
        while True:
            try:
                await asyncio.sleep(300)  # 5分钟检查一次
                
                current_time = datetime.now()
                expired_sessions = []
                
                for session_id, context in self.active_sessions.items():
                    if (current_time - context.last_activity).total_seconds() > self.config.session_timeout:
                        expired_sessions.append(session_id)
                
                for session_id in expired_sessions:
                    await self.close_session(session_id)
                    
            except Exception as e:
                logger.error(f"清理过期会话失败: {e}")
    
    async def _update_stats_periodically(self):
        """定期更新统计信息"""
        while True:
            try:
                await asyncio.sleep(60)  # 1分钟更新一次
                
                self.stats["active_sessions"] = len(self.active_sessions)
                
                # 计算平均会话时长
                if self.active_sessions:
                    total_duration = sum(
                        (datetime.now() - ctx.creation_time).total_seconds()
                        for ctx in self.active_sessions.values()
                    )
                    self.stats["average_session_duration"] = total_duration / len(self.active_sessions)
                
            except Exception as e:
                logger.error(f"更新统计信息失败: {e}")
    
    async def _cleanup_old_events(self):
        """清理旧事件"""
        while True:
            try:
                await asyncio.sleep(3600)  # 1小时清理一次
                
                cutoff_time = datetime.now() - timedelta(hours=24)
                self.detection_events = [
                    event for event in self.detection_events
                    if event.timestamp > cutoff_time
                ]
                
            except Exception as e:
                logger.error(f"清理旧事件失败: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.stats.copy()
        
        # 添加组件统计
        if self.fingerprint_manager:
            stats["fingerprint_stats"] = self.fingerprint_manager.get_enhanced_stats()
        
        if self.session_manager:
            stats["session_stats"] = self.session_manager.get_session_statistics()
        
        return stats
    
    async def shutdown(self):
        """关闭系统"""
        logger.info("🔄 开始关闭反检测系统...")
        
        # 关闭所有会话
        session_ids = list(self.active_sessions.keys())
        for session_id in session_ids:
            await self.close_session(session_id)
        
        # 关闭会话管理器
        if self.session_manager:
            await self.session_manager.close_all_sessions()
        
        logger.info("✅ 反检测系统已关闭")


# 工厂函数
async def create_anti_detection_system(mode: IntegrationMode = IntegrationMode.BALANCED) -> AntiDetectionIntegration:
    """创建反检测系统"""
    config = IntegrationConfig(mode=mode)
    
    # 根据模式调整配置
    if mode == IntegrationMode.STEALTH:
        config.preferred_spoofing_level = SpoofingLevel.AGGRESSIVE
        config.min_fingerprint_quality = FingerprintQuality.GOOD
        config.auto_rotate_on_detection = True
    elif mode == IntegrationMode.PERFORMANCE:
        config.preferred_spoofing_level = SpoofingLevel.MINIMAL
        config.min_fingerprint_quality = FingerprintQuality.FAIR
        config.max_concurrent_sessions = 10
    elif mode == IntegrationMode.DEBUGGING:
        config.debug_mode = True
        config.log_all_requests = True
        config.save_detection_samples = True
    
    system = AntiDetectionIntegration(config)
    await system.initialize()
    
    return system


# 测试函数
async def test_anti_detection_integration():
    """测试反检测集成系统"""
    logger.info("🧪 开始测试反检测集成系统...")
    
    try:
        # 创建系统
        system = await create_anti_detection_system(IntegrationMode.BALANCED)
        
        # 创建会话
        session_id = await system.create_session()
        logger.info(f"✅ 创建会话: {session_id}")
        
        # 准备请求
        request_params = await system.prepare_request(session_id, "https://jp.mercari.com")
        logger.info(f"✅ 请求准备完成: {len(request_params)} 个参数")
        
        # 获取统计信息
        stats = system.get_stats()
        logger.info(f"统计信息: {stats}")
        
        # 关闭会话
        await system.close_session(session_id)
        
        # 关闭系统
        await system.shutdown()
        
        logger.info("✅ 反检测集成系统测试完成")
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_anti_detection_integration())