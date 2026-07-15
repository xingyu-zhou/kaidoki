"""
指纹管理插件

该模块将现有的EnhancedFingerprintManager包装为标准插件，提供：
- 统一的插件接口
- 指纹池管理
- 质量评估和过滤
- 自动轮换机制
- 性能监控

基于现有的scrapers/enhanced_fingerprint_manager.py，提供插件化封装。

Author: Mercari AI Agent Team
"""

import asyncio
import time
import random
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import weakref

from .interfaces import IFingerprintPlugin, PluginType, PluginCapability, PluginConfiguration, unified_plugin
from ..captcha.plugin_interface import PluginStatus, PluginPriority, PluginMetadata, PluginCategory
from ..scrapers.enhanced_fingerprint_manager import EnhancedFingerprintManager
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FingerprintPluginConfig:
    """指纹插件配置"""
    # 指纹池配置
    max_fingerprints: int = 100
    min_fingerprints: int = 10
    rotation_interval: float = 1800.0  # 30分钟
    max_usage_count: int = 50
    
    # 质量配置
    min_quality_score: float = 0.6
    enable_quality_filter: bool = True
    quality_check_interval: float = 3600.0  # 1小时
    
    # 生成配置
    auto_generate: bool = True
    generation_batch_size: int = 10
    generation_interval: float = 7200.0  # 2小时
    
    # 平台配置
    supported_platforms: List[str] = field(default_factory=lambda: ['windows', 'macos', 'linux'])
    supported_browsers: List[str] = field(default_factory=lambda: ['chrome', 'firefox', 'safari', 'edge'])
    
    # 高级配置
    enable_canvas_fingerprinting: bool = True
    enable_webgl_fingerprinting: bool = True
    enable_audio_fingerprinting: bool = True
    randomize_timezone: bool = True
    randomize_language: bool = True
    
    # 性能配置
    cache_size: int = 50
    enable_fingerprint_cache: bool = True
    cache_ttl: float = 3600.0  # 1小时


@unified_plugin(
    plugin_type=PluginType.FINGERPRINT,
    priority=PluginPriority.HIGH,
    capabilities={
        PluginCapability.HOT_RELOAD,
        PluginCapability.CONFIGURATION_MANAGEMENT,
        PluginCapability.HEALTH_CHECK,
        PluginCapability.METRICS_COLLECTION,
        PluginCapability.BATCH_PROCESSING,
        PluginCapability.ASYNC_PROCESSING
    },
    version="1.0.0"
)
class FingerprintPlugin(IFingerprintPlugin):
    """
    指纹管理插件
    
    功能：
    1. 指纹生成和管理
    2. 质量评估和过滤
    3. 自动轮换机制
    4. 性能监控和统计
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        # 插件配置
        self.fingerprint_config = FingerprintPluginConfig()
        if config:
            self._load_plugin_config(config)
        
        # 核心指纹管理器
        self.fingerprint_manager: Optional[EnhancedFingerprintManager] = None
        
        # 指纹池和缓存
        self.fingerprint_pool: List[Dict[str, Any]] = []
        self.fingerprint_cache: Dict[str, Dict[str, Any]] = {}
        self.fingerprint_usage: Dict[str, int] = {}
        self.fingerprint_quality_scores: Dict[str, float] = {}
        
        # 指纹统计
        self.fingerprint_stats = {
            'total_fingerprints_generated': 0,
            'active_fingerprints': 0,
            'expired_fingerprints': 0,
            'quality_filtered_fingerprints': 0,
            'total_applications': 0,
            'successful_applications': 0,
            'failed_applications': 0,
            'average_quality_score': 0.0,
            'pool_utilization': 0.0
        }
        
        # 监控任务
        self.monitoring_tasks: List[asyncio.Task] = []
        
        # 设置能力
        self._capabilities = {
            PluginCapability.HOT_RELOAD,
            PluginCapability.CONFIGURATION_MANAGEMENT,
            PluginCapability.HEALTH_CHECK,
            PluginCapability.METRICS_COLLECTION,
            PluginCapability.BATCH_PROCESSING,
            PluginCapability.ASYNC_PROCESSING
        }
        
        logger.info("FingerprintPlugin initialized")
    
    def _create_metadata(self) -> PluginMetadata:
        """创建插件元数据"""
        return PluginMetadata(
            name="FingerprintPlugin",
            version="1.0.0",
            category=PluginCategory.FINGERPRINT,
            priority=PluginPriority.HIGH,
            author="Mercari AI Agent Team",
            description="Enhanced fingerprint management plugin with quality control and auto-rotation",
            dependencies=[],
            supported_features=[
                "fingerprint_generation",
                "quality_assessment",
                "automatic_rotation",
                "batch_processing",
                "performance_monitoring"
            ]
        )
    
    def _create_plugin_configuration(self) -> PluginConfiguration:
        """创建插件配置"""
        return PluginConfiguration(
            plugin_id="fingerprint_plugin",
            plugin_type=PluginType.FINGERPRINT,
            enabled=True,
            priority=PluginPriority.HIGH,
            capabilities=self._capabilities,
            dependencies=[],
            runtime_config=self._config.copy(),
            version="1.0.0"
        )
    
    def _load_plugin_config(self, config: Dict[str, Any]):
        """加载插件配置"""
        for key, value in config.items():
            if hasattr(self.fingerprint_config, key):
                setattr(self.fingerprint_config, key, value)
    
    async def _initialize_impl(self) -> bool:
        """具体初始化实现"""
        try:
            logger.info("Initializing FingerprintPlugin...")
            
            # 创建指纹管理器
            manager_config = {
                'pool': {
                    'max_fingerprints': self.fingerprint_config.max_fingerprints,
                    'rotation_interval': self.fingerprint_config.rotation_interval,
                    'max_usage_count': self.fingerprint_config.max_usage_count
                },
                'quality': {
                    'min_quality': 'good' if self.fingerprint_config.min_quality_score > 0.7 else 'fair'
                },
                'platforms': self.fingerprint_config.supported_platforms,
                'browsers': self.fingerprint_config.supported_browsers
            }
            
            self.fingerprint_manager = EnhancedFingerprintManager(manager_config)
            await self.fingerprint_manager.initialize()
            
            # 初始化指纹池
            await self._initialize_fingerprint_pool()
            
            # 启动监控任务
            self._start_monitoring_tasks()
            
            logger.info("FingerprintPlugin initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize FingerprintPlugin: {e}")
            return False
    
    async def _start_impl(self) -> bool:
        """具体启动实现"""
        try:
            if self.fingerprint_manager:
                await self.fingerprint_manager.start()
                logger.info("FingerprintPlugin started successfully")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to start FingerprintPlugin: {e}")
            return False
    
    async def _stop_impl(self) -> bool:
        """具体停止实现"""
        try:
            # 停止监控任务
            for task in self.monitoring_tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            self.monitoring_tasks.clear()
            
            # 停止指纹管理器
            if self.fingerprint_manager:
                await self.fingerprint_manager.stop()
            
            logger.info("FingerprintPlugin stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop FingerprintPlugin: {e}")
            return False
    
    async def _healthcheck_impl(self) -> Dict[str, Any]:
        """具体健康检查实现"""
        try:
            health_result = {
                'healthy': True,
                'fingerprint_manager_status': 'unknown',
                'pool_size': len(self.fingerprint_pool),
                'cached_fingerprints': len(self.fingerprint_cache),
                'average_quality': self.fingerprint_stats.get('average_quality_score', 0.0),
                'pool_utilization': self.fingerprint_stats.get('pool_utilization', 0.0),
                'last_check': datetime.now().isoformat()
            }
            
            if self.fingerprint_manager:
                # 检查指纹管理器状态
                manager_health = await self.fingerprint_manager.health_check()
                health_result['fingerprint_manager_status'] = 'healthy' if manager_health.get('healthy', False) else 'unhealthy'
                
                # 整体健康状态
                health_result['healthy'] = manager_health.get('healthy', False) and len(self.fingerprint_pool) >= self.fingerprint_config.min_fingerprints
            
            return health_result
            
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }
    
    async def generate_fingerprint(self, fingerprint_type: str = None) -> Dict[str, Any]:
        """生成指纹"""
        try:
            if not self.fingerprint_manager:
                raise RuntimeError("Fingerprint manager not initialized")
            
            # 生成指纹
            fingerprint = await self.fingerprint_manager.get_fingerprint()
            
            if fingerprint:
                # 评估质量
                quality_score = await self._assess_fingerprint_quality(fingerprint)
                
                # 检查质量是否合格
                if quality_score < self.fingerprint_config.min_quality_score and self.fingerprint_config.enable_quality_filter:
                    self.fingerprint_stats['quality_filtered_fingerprints'] += 1
                    logger.debug(f"Fingerprint filtered due to low quality: {quality_score}")
                    # 递归重新生成
                    return await self.generate_fingerprint(fingerprint_type)
                
                # 添加到池中
                fingerprint_id = self._generate_fingerprint_id(fingerprint)
                fingerprint['id'] = fingerprint_id
                fingerprint['created_at'] = datetime.now().isoformat()
                fingerprint['quality_score'] = quality_score
                fingerprint['usage_count'] = 0
                
                self.fingerprint_pool.append(fingerprint)
                self.fingerprint_quality_scores[fingerprint_id] = quality_score
                self.fingerprint_usage[fingerprint_id] = 0
                
                # 更新统计
                self.fingerprint_stats['total_fingerprints_generated'] += 1
                self.fingerprint_stats['active_fingerprints'] = len(self.fingerprint_pool)
                self._update_average_quality()
                
                logger.debug(f"Fingerprint generated: {fingerprint_id}, quality: {quality_score}")
                return fingerprint.copy()
            
            raise RuntimeError("Failed to generate fingerprint")
            
        except Exception as e:
            logger.error(f"Failed to generate fingerprint: {e}")
            raise
    
    async def apply_fingerprint(self, session: Any, fingerprint: Dict[str, Any]) -> bool:
        """应用指纹"""
        try:
            if not self.fingerprint_manager:
                return False
            
            # 应用指纹
            success = await self.fingerprint_manager.apply_fingerprint(session, fingerprint)
            
            # 更新使用统计
            fingerprint_id = fingerprint.get('id')
            if fingerprint_id:
                self.fingerprint_usage[fingerprint_id] = self.fingerprint_usage.get(fingerprint_id, 0) + 1
                
                # 检查是否需要轮换
                if self.fingerprint_usage[fingerprint_id] >= self.fingerprint_config.max_usage_count:
                    await self._retire_fingerprint(fingerprint_id)
            
            # 更新统计
            self.fingerprint_stats['total_applications'] += 1
            if success:
                self.fingerprint_stats['successful_applications'] += 1
            else:
                self.fingerprint_stats['failed_applications'] += 1
            
            return success
            
        except Exception as e:
            self.fingerprint_stats['failed_applications'] += 1
            logger.error(f"Failed to apply fingerprint: {e}")
            return False
    
    async def get_fingerprint_pool_stats(self) -> Dict[str, Any]:
        """获取指纹池统计"""
        try:
            stats = self.fingerprint_stats.copy()
            
            # 添加详细统计
            stats.update({
                'pool_size': len(self.fingerprint_pool),
                'cached_fingerprints': len(self.fingerprint_cache),
                'total_usage': sum(self.fingerprint_usage.values()),
                'quality_distribution': self._get_quality_distribution(),
                'platform_distribution': self._get_platform_distribution(),
                'browser_distribution': self._get_browser_distribution(),
                'rotation_stats': self._get_rotation_stats()
            })
            
            # 计算池利用率
            if self.fingerprint_config.max_fingerprints > 0:
                stats['pool_utilization'] = len(self.fingerprint_pool) / self.fingerprint_config.max_fingerprints * 100
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get fingerprint pool stats: {e}")
            return self.fingerprint_stats.copy()
    
    async def refresh_fingerprint_pool(self) -> bool:
        """刷新指纹池"""
        try:
            logger.info("Refreshing fingerprint pool...")
            
            # 清理过期指纹
            await self._cleanup_expired_fingerprints()
            
            # 生成新指纹补充池
            current_size = len(self.fingerprint_pool)
            target_size = self.fingerprint_config.max_fingerprints
            
            if current_size < target_size:
                batch_size = min(self.fingerprint_config.generation_batch_size, target_size - current_size)
                await self._generate_fingerprint_batch(batch_size)
            
            # 质量检查和过滤
            if self.fingerprint_config.enable_quality_filter:
                await self._filter_low_quality_fingerprints()
            
            logger.info(f"Fingerprint pool refreshed, size: {len(self.fingerprint_pool)}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to refresh fingerprint pool: {e}")
            return False
    
    async def _initialize_fingerprint_pool(self):
        """初始化指纹池"""
        initial_size = min(self.fingerprint_config.generation_batch_size, self.fingerprint_config.max_fingerprints)
        await self._generate_fingerprint_batch(initial_size)
    
    async def _generate_fingerprint_batch(self, batch_size: int):
        """批量生成指纹"""
        for _ in range(batch_size):
            try:
                await self.generate_fingerprint()
                await asyncio.sleep(0.1)  # 避免过快生成
            except Exception as e:
                logger.error(f"Failed to generate fingerprint in batch: {e}")
    
    def _generate_fingerprint_id(self, fingerprint: Dict[str, Any]) -> str:
        """生成指纹ID"""
        import hashlib
        
        # 使用关键字段生成唯一ID
        key_fields = [
            str(fingerprint.get('user_agent', '')),
            str(fingerprint.get('screen_resolution', '')),
            str(fingerprint.get('timezone', '')),
            str(fingerprint.get('language', ''))
        ]
        
        content = '|'.join(key_fields)
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    async def _assess_fingerprint_quality(self, fingerprint: Dict[str, Any]) -> float:
        """评估指纹质量"""
        try:
            score = 0.0
            total_checks = 0
            
            # 检查用户代理
            if fingerprint.get('user_agent'):
                score += 0.3
                total_checks += 1
            
            # 检查屏幕分辨率
            if fingerprint.get('screen_resolution'):
                score += 0.2
                total_checks += 1
            
            # 检查时区
            if fingerprint.get('timezone'):
                score += 0.1
                total_checks += 1
            
            # 检查语言设置
            if fingerprint.get('language'):
                score += 0.1
                total_checks += 1
            
            # 检查Canvas指纹
            if fingerprint.get('canvas_fingerprint'):
                score += 0.15
                total_checks += 1
            
            # 检查WebGL指纹
            if fingerprint.get('webgl_fingerprint'):
                score += 0.1
                total_checks += 1
            
            # 检查音频指纹
            if fingerprint.get('audio_fingerprint'):
                score += 0.05
                total_checks += 1
            
            # 计算最终分数
            if total_checks > 0:
                return min(score, 1.0)
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Failed to assess fingerprint quality: {e}")
            return 0.0
    
    async def _retire_fingerprint(self, fingerprint_id: str):
        """淘汰指纹"""
        try:
            # 从池中移除
            self.fingerprint_pool = [fp for fp in self.fingerprint_pool if fp.get('id') != fingerprint_id]
            
            # 清理统计
            if fingerprint_id in self.fingerprint_usage:
                del self.fingerprint_usage[fingerprint_id]
            if fingerprint_id in self.fingerprint_quality_scores:
                del self.fingerprint_quality_scores[fingerprint_id]
            if fingerprint_id in self.fingerprint_cache:
                del self.fingerprint_cache[fingerprint_id]
            
            self.fingerprint_stats['expired_fingerprints'] += 1
            self.fingerprint_stats['active_fingerprints'] = len(self.fingerprint_pool)
            
            logger.debug(f"Fingerprint retired: {fingerprint_id}")
            
        except Exception as e:
            logger.error(f"Failed to retire fingerprint {fingerprint_id}: {e}")
    
    async def _cleanup_expired_fingerprints(self):
        """清理过期指纹"""
        current_time = datetime.now()
        expired_fingerprints = []
        
        for fingerprint in self.fingerprint_pool:
            created_at = datetime.fromisoformat(fingerprint.get('created_at', current_time.isoformat()))
            age = (current_time - created_at).total_seconds()
            
            # 检查是否过期
            if (age > self.fingerprint_config.rotation_interval or
                self.fingerprint_usage.get(fingerprint.get('id'), 0) >= self.fingerprint_config.max_usage_count):
                expired_fingerprints.append(fingerprint.get('id'))
        
        # 移除过期指纹
        for fingerprint_id in expired_fingerprints:
            await self._retire_fingerprint(fingerprint_id)
    
    async def _filter_low_quality_fingerprints(self):
        """过滤低质量指纹"""
        filtered_fingerprints = []
        
        for fingerprint in self.fingerprint_pool:
            quality_score = fingerprint.get('quality_score', 0.0)
            if quality_score < self.fingerprint_config.min_quality_score:
                filtered_fingerprints.append(fingerprint.get('id'))
        
        # 移除低质量指纹
        for fingerprint_id in filtered_fingerprints:
            await self._retire_fingerprint(fingerprint_id)
            self.fingerprint_stats['quality_filtered_fingerprints'] += 1
    
    def _update_average_quality(self):
        """更新平均质量分数"""
        if self.fingerprint_quality_scores:
            self.fingerprint_stats['average_quality_score'] = sum(self.fingerprint_quality_scores.values()) / len(self.fingerprint_quality_scores)
    
    def _get_quality_distribution(self) -> Dict[str, int]:
        """获取质量分布"""
        distribution = {'low': 0, 'medium': 0, 'high': 0}
        
        for score in self.fingerprint_quality_scores.values():
            if score < 0.6:
                distribution['low'] += 1
            elif score < 0.8:
                distribution['medium'] += 1
            else:
                distribution['high'] += 1
        
        return distribution
    
    def _get_platform_distribution(self) -> Dict[str, int]:
        """获取平台分布"""
        distribution = {}
        
        for fingerprint in self.fingerprint_pool:
            platform = fingerprint.get('platform', 'unknown')
            distribution[platform] = distribution.get(platform, 0) + 1
        
        return distribution
    
    def _get_browser_distribution(self) -> Dict[str, int]:
        """获取浏览器分布"""
        distribution = {}
        
        for fingerprint in self.fingerprint_pool:
            user_agent = fingerprint.get('user_agent', '')
            browser = 'unknown'
            
            if 'chrome' in user_agent.lower():
                browser = 'chrome'
            elif 'firefox' in user_agent.lower():
                browser = 'firefox'
            elif 'safari' in user_agent.lower():
                browser = 'safari'
            elif 'edge' in user_agent.lower():
                browser = 'edge'
            
            distribution[browser] = distribution.get(browser, 0) + 1
        
        return distribution
    
    def _get_rotation_stats(self) -> Dict[str, Any]:
        """获取轮换统计"""
        return {
            'rotation_interval': self.fingerprint_config.rotation_interval,
            'max_usage_count': self.fingerprint_config.max_usage_count,
            'expired_count': self.fingerprint_stats.get('expired_fingerprints', 0),
            'next_rotation': 'auto'
        }
    
    def _start_monitoring_tasks(self):
        """启动监控任务"""
        # 质量检查任务
        if self.fingerprint_config.quality_check_interval > 0:
            self.monitoring_tasks.append(
                asyncio.create_task(self._quality_check_loop())
            )
        
        # 自动生成任务
        if self.fingerprint_config.auto_generate and self.fingerprint_config.generation_interval > 0:
            self.monitoring_tasks.append(
                asyncio.create_task(self._auto_generation_loop())
            )
        
        # 池管理任务
        self.monitoring_tasks.append(
            asyncio.create_task(self._pool_management_loop())
        )
    
    async def _quality_check_loop(self):
        """质量检查循环"""
        while True:
            try:
                await asyncio.sleep(self.fingerprint_config.quality_check_interval)
                
                if self.fingerprint_config.enable_quality_filter:
                    await self._filter_low_quality_fingerprints()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Quality check loop error: {e}")
                await asyncio.sleep(300)  # 错误时等待5分钟
    
    async def _auto_generation_loop(self):
        """自动生成循环"""
        while True:
            try:
                await asyncio.sleep(self.fingerprint_config.generation_interval)
                
                # 检查是否需要生成新指纹
                current_size = len(self.fingerprint_pool)
                if current_size < self.fingerprint_config.max_fingerprints:
                    batch_size = min(
                        self.fingerprint_config.generation_batch_size,
                        self.fingerprint_config.max_fingerprints - current_size
                    )
                    await self._generate_fingerprint_batch(batch_size)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Auto generation loop error: {e}")
                await asyncio.sleep(600)  # 错误时等待10分钟
    
    async def _pool_management_loop(self):
        """池管理循环"""
        while True:
            try:
                await asyncio.sleep(300)  # 每5分钟检查一次
                
                # 清理过期指纹
                await self._cleanup_expired_fingerprints()
                
                # 更新统计
                self._update_average_quality()
                
                # 更新池利用率
                if self.fingerprint_config.max_fingerprints > 0:
                    self.fingerprint_stats['pool_utilization'] = len(self.fingerprint_pool) / self.fingerprint_config.max_fingerprints * 100
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Pool management loop error: {e}")
                await asyncio.sleep(300)  # 错误时等待5分钟
    
    async def _apply_config_reload(self):
        """应用配置重新加载"""
        try:
            # 重新加载配置
            self._load_plugin_config(self._config)
            
            logger.info("Fingerprint plugin config reloaded")
            
        except Exception as e:
            logger.error(f"Failed to apply config reload: {e}")
            raise


# 便利函数
async def create_fingerprint_plugin(config: Dict[str, Any] = None) -> FingerprintPlugin:
    """创建指纹管理插件实例"""
    plugin = FingerprintPlugin(config)
    await plugin.initialize()
    await plugin.start()
    return plugin


def get_default_fingerprint_config() -> Dict[str, Any]:
    """获取默认指纹配置"""
    return {
        'max_fingerprints': 100,
        'min_fingerprints': 10,
        'rotation_interval': 1800.0,
        'max_usage_count': 50,
        'min_quality_score': 0.6,
        'enable_quality_filter': True,
        'quality_check_interval': 3600.0,
        'auto_generate': True,
        'generation_batch_size': 10,
        'generation_interval': 7200.0,
        'supported_platforms': ['windows', 'macos', 'linux'],
        'supported_browsers': ['chrome', 'firefox', 'safari', 'edge'],
        'enable_canvas_fingerprinting': True,
        'enable_webgl_fingerprinting': True,
        'enable_audio_fingerprinting': True,
        'randomize_timezone': True,
        'randomize_language': True,
        'cache_size': 50,
        'enable_fingerprint_cache': True,
        'cache_ttl': 3600.0
    }