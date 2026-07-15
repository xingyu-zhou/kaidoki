"""
验证码插件集成模块

该模块负责将统一验证码检测器插件集成到反检测管理器中，提供：
- 插件自动注册
- 向后兼容性保证
- 热插拔支持
- 配置管理
- 性能监控

Author: Mercari AI Agent Team
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime

from .unified_captcha_detector_plugin import UnifiedCaptchaDetectorPlugin
from .captcha_detector_plugin import (
    ICaptchaDetector, CaptchaDetectorConfig, DetectionContext,
    UnifiedCaptchaDetectionResult, DetectionPipeline
)
from .plugin_registry import PluginRegistry
from .enhanced_anti_detection_manager import EnhancedAntiDetectionManager
from .captcha_types import CaptchaType, CaptchaDetectionResult
from .unified_captcha_detector import UnifiedDetectionResult
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CaptchaPluginConfig:
    """验证码插件配置"""
    # 插件启用配置
    enable_unified_detector: bool = True
    enable_legacy_detector: bool = True
    plugin_switching_enabled: bool = True
    
    # 性能配置
    max_concurrent_detections: int = 5
    detection_timeout: float = 30.0
    enable_detection_cache: bool = True
    cache_ttl: int = 300
    
    # 检测配置
    confidence_threshold: float = 0.6
    detection_pipeline: str = "standard"  # fast, standard, comprehensive, adaptive
    enable_context_analysis: bool = True
    enable_debug_logging: bool = False
    
    # 热插拔配置
    enable_hot_reload: bool = False
    plugin_health_check_interval: float = 60.0
    auto_fallback_on_failure: bool = True
    
    # 兼容性配置
    maintain_legacy_api: bool = True
    convert_results_format: bool = True


class CaptchaPluginManager:
    """验证码插件管理器"""
    
    def __init__(self, config: Optional[CaptchaPluginConfig] = None):
        self.config = config or CaptchaPluginConfig()
        self.plugin_registry = PluginRegistry.get_instance()
        
        # 插件实例
        self.unified_detector: Optional[UnifiedCaptchaDetectorPlugin] = None
        self.legacy_detector: Optional[Any] = None
        
        # 活跃插件
        self.active_detector: Optional[ICaptchaDetector] = None
        self.fallback_detector: Optional[ICaptchaDetector] = None
        
        # 状态管理
        self.initialized = False
        self.health_check_task: Optional[asyncio.Task] = None
        
        # 统计信息
        self.plugin_stats = {
            'unified_detector': {'requests': 0, 'errors': 0, 'avg_time': 0.0},
            'legacy_detector': {'requests': 0, 'errors': 0, 'avg_time': 0.0},
            'plugin_switches': 0,
            'fallback_activations': 0
        }
        
        logger.info("CaptchaPluginManager initialized")
    
    async def initialize(self):
        """初始化插件管理器"""
        if self.initialized:
            return True
        
        try:
            logger.info("Initializing CaptchaPluginManager...")
            
            # 1. 注册统一验证码检测器插件
            if self.config.enable_unified_detector:
                await self._register_unified_detector()
            
            # 2. 保持旧版检测器兼容性
            if self.config.enable_legacy_detector:
                await self._register_legacy_detector()
            
            # 3. 设置活跃检测器
            await self._setup_active_detector()
            
            # 4. 启动健康检查
            if self.config.plugin_health_check_interval > 0:
                self.health_check_task = asyncio.create_task(
                    self._health_check_loop()
                )
            
            self.initialized = True
            logger.info("CaptchaPluginManager initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize CaptchaPluginManager: {e}")
            return False
    
    async def _register_unified_detector(self):
        """注册统一验证码检测器插件"""
        try:
            # 创建插件配置
            detector_config = {
                'confidence_threshold': self.config.confidence_threshold,
                'enable_context_analysis': self.config.enable_context_analysis,
                'enable_debug_logging': self.config.enable_debug_logging,
                'max_processing_time': self.config.detection_timeout,
                'detection_pipeline': DetectionPipeline(self.config.detection_pipeline),
                'enable_detection_cache': self.config.enable_detection_cache,
                'cache_ttl': self.config.cache_ttl,
                'max_concurrent_detections': self.config.max_concurrent_detections,
                'enable_parallel_detection': True,
                'detection_timeout': self.config.detection_timeout,
                'require_human_interaction': True,
                'disable_auto_solving': True,
                'enable_compliance_check': True
            }
            
            # 创建插件实例
            self.unified_detector = UnifiedCaptchaDetectorPlugin(detector_config)
            
            # 注册到插件系统
            success = self.plugin_registry.register_plugin(
                UnifiedCaptchaDetectorPlugin,
                plugin_name="unified_captcha_detector",
                config=detector_config,
                auto_start=True,
                singleton=True
            )
            
            if success:
                # 初始化插件
                await self.unified_detector.initialize()
                await self.unified_detector.start()
                
                logger.info("Unified captcha detector plugin registered and started")
            else:
                logger.error("Failed to register unified captcha detector plugin")
                
        except Exception as e:
            logger.error(f"Failed to register unified detector: {e}")
            raise
    
    async def _register_legacy_detector(self):
        """注册旧版检测器（向后兼容）"""
        try:
            from .unified_captcha_detector import UnifiedCaptchaDetector
            
            # 创建旧版检测器实例
            self.legacy_detector = UnifiedCaptchaDetector()
            
            # 设置配置
            self.legacy_detector.confidence_threshold = self.config.confidence_threshold
            self.legacy_detector.enable_context_analysis = self.config.enable_context_analysis
            self.legacy_detector.enable_debug_logging = self.config.enable_debug_logging
            self.legacy_detector.max_processing_time = self.config.detection_timeout
            
            logger.info("Legacy captcha detector initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize legacy detector: {e}")
            # 不抛出异常，因为旧版检测器是可选的
    
    async def _setup_active_detector(self):
        """设置活跃检测器"""
        if self.unified_detector and self.config.enable_unified_detector:
            self.active_detector = self.unified_detector
            self.fallback_detector = self.legacy_detector
            logger.info("Using unified detector as active detector")
        elif self.legacy_detector:
            self.active_detector = self.legacy_detector
            logger.info("Using legacy detector as active detector")
        else:
            raise RuntimeError("No captcha detector available")
    
    async def detect_captcha(self, 
                           content: str, 
                           response: Optional[Any] = None,
                           url: Optional[str] = None) -> Union[UnifiedCaptchaDetectionResult, UnifiedDetectionResult]:
        """
        统一验证码检测入口
        
        提供向后兼容的API，支持新旧两种检测结果格式
        """
        if not self.initialized:
            await self.initialize()
        
        start_time = asyncio.get_event_loop().time()
        detector_used = "unknown"
        
        try:
            # 使用活跃检测器
            if isinstance(self.active_detector, UnifiedCaptchaDetectorPlugin):
                # 新版统一检测器
                detector_used = "unified_detector"
                context = DetectionContext(
                    url=url,
                    timestamp=datetime.now()
                )
                
                if response:
                    # 从响应中提取上下文信息
                    if hasattr(response, 'headers'):
                        context.user_agent = response.headers.get('user-agent')
                        context.referer = response.headers.get('referer')
                
                result = await self.active_detector.detect_captcha(content, context)
                
                # 如果需要向后兼容，转换结果格式
                if self.config.convert_results_format:
                    return result  # 返回新格式
                else:
                    return result.to_legacy_result()  # 转换为旧格式
            
            else:
                # 旧版检测器
                detector_used = "legacy_detector"
                result = await self.active_detector.detect_unified(content, response, url)
                return result
        
        except Exception as e:
            logger.error(f"Detection failed with {detector_used}: {e}")
            
            # 自动回退
            if self.config.auto_fallback_on_failure and self.fallback_detector:
                logger.info(f"Falling back to fallback detector")
                try:
                    self.plugin_stats['fallback_activations'] += 1
                    
                    if isinstance(self.fallback_detector, UnifiedCaptchaDetectorPlugin):
                        context = DetectionContext(url=url, timestamp=datetime.now())
                        result = await self.fallback_detector.detect_captcha(content, context)
                        return result if self.config.convert_results_format else result.to_legacy_result()
                    else:
                        result = await self.fallback_detector.detect_unified(content, response, url)
                        return result
                        
                except Exception as fallback_error:
                    logger.error(f"Fallback detection also failed: {fallback_error}")
            
            # 返回失败结果
            if self.config.convert_results_format:
                return UnifiedCaptchaDetectionResult(
                    detected=False,
                    confidence=0.0,
                    detection_method="error",
                    debug_info={'error': str(e), 'detector_used': detector_used}
                )
            else:
                return UnifiedDetectionResult(
                    is_detected=False,
                    confidence=0.0,
                    detection_method="error",
                    details={'error': str(e), 'detector_used': detector_used}
                )
        
        finally:
            # 更新统计信息
            processing_time = asyncio.get_event_loop().time() - start_time
            self._update_stats(detector_used, processing_time, success=True)
    
    async def switch_detector(self, detector_type: str) -> bool:
        """切换检测器"""
        if not self.config.plugin_switching_enabled:
            logger.warning("Plugin switching is disabled")
            return False
        
        try:
            if detector_type == "unified" and self.unified_detector:
                old_detector = self.active_detector
                self.active_detector = self.unified_detector
                self.fallback_detector = old_detector
                logger.info("Switched to unified detector")
                
            elif detector_type == "legacy" and self.legacy_detector:
                old_detector = self.active_detector
                self.active_detector = self.legacy_detector
                self.fallback_detector = old_detector
                logger.info("Switched to legacy detector")
                
            else:
                logger.error(f"Invalid or unavailable detector type: {detector_type}")
                return False
            
            self.plugin_stats['plugin_switches'] += 1
            return True
            
        except Exception as e:
            logger.error(f"Failed to switch detector: {e}")
            return False
    
    async def hot_reload_unified_detector(self, new_config: Optional[Dict[str, Any]] = None) -> bool:
        """热重载统一检测器"""
        if not self.config.enable_hot_reload:
            logger.warning("Hot reload is disabled")
            return False
        
        try:
            if self.unified_detector:
                # 更新配置
                if new_config:
                    merged_config = {**self.unified_detector.config, **new_config}
                    new_detector_config = CaptchaDetectorConfig(**merged_config)
                    await self.unified_detector.update_detection_config(new_detector_config)
                
                logger.info("Unified detector hot reloaded successfully")
                return True
            else:
                logger.warning("Unified detector not available for hot reload")
                return False
                
        except Exception as e:
            logger.error(f"Hot reload failed: {e}")
            return False
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while True:
            try:
                await asyncio.sleep(self.config.plugin_health_check_interval)
                
                # 检查活跃检测器健康状态
                if self.active_detector:
                    if hasattr(self.active_detector, 'healthcheck'):
                        health_result = await self.active_detector.healthcheck()
                        if not health_result.get('healthy', True):
                            logger.warning(f"Active detector health check failed: {health_result}")
                            
                            # 自动切换到回退检测器
                            if self.config.auto_fallback_on_failure and self.fallback_detector:
                                logger.info("Auto-switching to fallback detector due to health check failure")
                                await self.switch_detector("legacy" if self.active_detector == self.unified_detector else "unified")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
    
    def _update_stats(self, detector_type: str, processing_time: float, success: bool):
        """更新统计信息"""
        if detector_type in self.plugin_stats:
            stats = self.plugin_stats[detector_type]
            stats['requests'] += 1
            if not success:
                stats['errors'] += 1
            
            # 更新平均处理时间
            current_avg = stats['avg_time']
            total_requests = stats['requests']
            stats['avg_time'] = (current_avg * (total_requests - 1) + processing_time) / total_requests
    
    def get_plugin_stats(self) -> Dict[str, Any]:
        """获取插件统计信息"""
        stats = {
            'plugin_stats': self.plugin_stats.copy(),
            'active_detector': type(self.active_detector).__name__ if self.active_detector else None,
            'fallback_detector': type(self.fallback_detector).__name__ if self.fallback_detector else None,
            'unified_detector_available': self.unified_detector is not None,
            'legacy_detector_available': self.legacy_detector is not None,
            'config': {
                'enable_unified_detector': self.config.enable_unified_detector,
                'enable_legacy_detector': self.config.enable_legacy_detector,
                'detection_pipeline': self.config.detection_pipeline,
                'confidence_threshold': self.config.confidence_threshold
            }
        }
        
        # 添加具体检测器的统计信息
        if self.unified_detector and hasattr(self.unified_detector, 'get_detection_stats'):
            stats['unified_detector_stats'] = self.unified_detector.get_detection_stats()
        
        return stats
    
    async def shutdown(self):
        """关闭插件管理器"""
        try:
            # 取消健康检查任务
            if self.health_check_task:
                self.health_check_task.cancel()
                try:
                    await self.health_check_task
                except asyncio.CancelledError:
                    pass
            
            # 停止插件
            if self.unified_detector:
                await self.unified_detector.stop()
            
            logger.info("CaptchaPluginManager shut down successfully")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


# 全局插件管理器实例
_captcha_plugin_manager: Optional[CaptchaPluginManager] = None


def get_captcha_plugin_manager(config: Optional[CaptchaPluginConfig] = None) -> CaptchaPluginManager:
    """获取验证码插件管理器实例"""
    global _captcha_plugin_manager
    
    if _captcha_plugin_manager is None:
        _captcha_plugin_manager = CaptchaPluginManager(config)
    
    return _captcha_plugin_manager


async def initialize_captcha_plugins(config: Optional[CaptchaPluginConfig] = None) -> bool:
    """初始化验证码插件系统"""
    manager = get_captcha_plugin_manager(config)
    return await manager.initialize()


async def shutdown_captcha_plugins():
    """关闭验证码插件系统"""
    global _captcha_plugin_manager
    
    if _captcha_plugin_manager:
        await _captcha_plugin_manager.shutdown()
        _captcha_plugin_manager = None


# 便捷函数：统一检测入口
async def detect_captcha_unified(content: str, 
                               response: Optional[Any] = None,
                               url: Optional[str] = None,
                               config: Optional[CaptchaPluginConfig] = None) -> Union[UnifiedCaptchaDetectionResult, UnifiedDetectionResult]:
    """
    统一验证码检测便捷函数
    
    这个函数提供了一个简单的入口点，自动处理插件初始化和检测
    """
    manager = get_captcha_plugin_manager(config)
    
    if not manager.initialized:
        await manager.initialize()
    
    return await manager.detect_captcha(content, response, url)