"""
行为模拟插件

该模块将现有的EnhancedBehaviorEngine包装为标准插件，提供：
- 统一的插件接口
- 鼠标行为模拟
- 键盘行为模拟
- 页面行为模拟
- 行为模式管理
- 性能监控

基于现有的scrapers/enhanced_behavior_engine.py，提供插件化封装。

Author: Mercari AI Agent Team
"""

import asyncio
import time
import random
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import weakref

from .interfaces import IBehaviorSimulationPlugin, PluginType, PluginCapability, PluginConfiguration, unified_plugin
from ..captcha.plugin_interface import PluginStatus, PluginPriority, PluginMetadata, PluginCategory
from ..scrapers.enhanced_behavior_engine import EnhancedBehaviorEngine
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BehaviorPluginConfig:
    """行为插件配置"""
    # 鼠标行为配置
    mouse_move_speed: float = 1.0  # 移动速度倍数
    mouse_click_delay: tuple = (0.1, 0.3)  # 点击延迟范围
    mouse_scroll_delay: tuple = (0.2, 0.5)  # 滚动延迟范围
    enable_mouse_curves: bool = True  # 启用鼠标轨迹曲线
    
    # 键盘行为配置
    typing_speed: float = 0.1  # 打字间隔
    typing_variation: float = 0.05  # 打字变化
    enable_typing_errors: bool = True  # 启用打字错误
    error_rate: float = 0.02  # 错误率
    
    # 页面行为配置
    page_load_wait: tuple = (1.0, 3.0)  # 页面加载等待时间
    element_search_delay: tuple = (0.5, 1.5)  # 元素搜索延迟
    scroll_behavior: str = 'natural'  # 滚动行为模式
    
    # 高级行为配置
    reading_behavior: bool = True  # 模拟阅读行为
    reading_speed: float = 200.0  # 阅读速度（字符/分钟）
    attention_span: tuple = (10.0, 30.0)  # 注意力持续时间
    
    # 随机化配置
    behavior_randomization: float = 0.2  # 行为随机化程度
    pattern_variation: float = 0.15  # 模式变化程度
    timing_jitter: float = 0.1  # 时间抖动
    
    # 适应性配置
    adaptive_timing: bool = True  # 自适应时间调整
    learning_enabled: bool = True  # 学习模式
    pattern_memory_size: int = 100  # 模式记忆大小


@unified_plugin(
    plugin_type=PluginType.BEHAVIOR_SIMULATION,
    priority=PluginPriority.NORMAL,
    capabilities={
        PluginCapability.HOT_RELOAD,
        PluginCapability.CONFIGURATION_MANAGEMENT,
        PluginCapability.HEALTH_CHECK,
        PluginCapability.METRICS_COLLECTION,
        PluginCapability.ASYNC_PROCESSING
    },
    version="1.0.0"
)
class BehaviorSimulationPlugin(IBehaviorSimulationPlugin):
    """
    行为模拟插件
    
    功能：
    1. 鼠标行为模拟
    2. 键盘行为模拟
    3. 页面行为模拟
    4. 行为模式学习
    5. 性能监控和统计
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        # 插件配置
        self.behavior_config = BehaviorPluginConfig()
        if config:
            self._load_plugin_config(config)
        
        # 核心行为引擎
        self.behavior_engine: Optional[EnhancedBehaviorEngine] = None
        
        # 行为统计
        self.behavior_stats = {
            'total_mouse_actions': 0,
            'total_keyboard_actions': 0,
            'total_page_actions': 0,
            'successful_actions': 0,
            'failed_actions': 0,
            'average_action_time': 0.0,
            'behavior_patterns_learned': 0,
            'adaptive_adjustments': 0
        }
        
        # 行为记录
        self.action_history: List[Dict[str, Any]] = []
        self.behavior_patterns: Dict[str, List[Dict[str, Any]]] = {}
        self.timing_stats: Dict[str, List[float]] = {}
        
        # 监控任务
        self.monitoring_tasks: List[asyncio.Task] = []
        
        # 设置能力
        self._capabilities = {
            PluginCapability.HOT_RELOAD,
            PluginCapability.CONFIGURATION_MANAGEMENT,
            PluginCapability.HEALTH_CHECK,
            PluginCapability.METRICS_COLLECTION,
            PluginCapability.ASYNC_PROCESSING
        }
        
        logger.info("BehaviorSimulationPlugin initialized")
    
    def _create_metadata(self) -> PluginMetadata:
        """创建插件元数据"""
        return PluginMetadata(
            name="BehaviorSimulationPlugin",
            version="1.0.0",
            category=PluginCategory.BEHAVIOR,
            priority=PluginPriority.NORMAL,
            author="Mercari AI Agent Team",
            description="Enhanced behavior simulation plugin with learning capabilities",
            dependencies=[],
            supported_features=[
                "mouse_simulation",
                "keyboard_simulation",
                "page_behavior",
                "pattern_learning",
                "adaptive_timing"
            ]
        )
    
    def _create_plugin_configuration(self) -> PluginConfiguration:
        """创建插件配置"""
        return PluginConfiguration(
            plugin_id="behavior_simulation_plugin",
            plugin_type=PluginType.BEHAVIOR_SIMULATION,
            enabled=True,
            priority=PluginPriority.NORMAL,
            capabilities=self._capabilities,
            dependencies=[],
            runtime_config=self._config.copy(),
            version="1.0.0"
        )
    
    def _load_plugin_config(self, config: Dict[str, Any]):
        """加载插件配置"""
        for key, value in config.items():
            if hasattr(self.behavior_config, key):
                setattr(self.behavior_config, key, value)
    
    async def _initialize_impl(self) -> bool:
        """具体初始化实现"""
        try:
            logger.info("Initializing BehaviorSimulationPlugin...")
            
            # 创建行为引擎
            engine_config = {
                'mouse_behavior': True,
                'keyboard_behavior': True,
                'page_behavior': True,
                'randomization_level': self.behavior_config.behavior_randomization,
                'adaptive_timing': self.behavior_config.adaptive_timing
            }
            
            self.behavior_engine = EnhancedBehaviorEngine(engine_config)
            await self.behavior_engine.initialize()
            
            # 初始化行为模式
            await self._initialize_behavior_patterns()
            
            # 启动监控任务
            self._start_monitoring_tasks()
            
            logger.info("BehaviorSimulationPlugin initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize BehaviorSimulationPlugin: {e}")
            return False
    
    async def _start_impl(self) -> bool:
        """具体启动实现"""
        try:
            if self.behavior_engine:
                await self.behavior_engine.start()
                logger.info("BehaviorSimulationPlugin started successfully")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to start BehaviorSimulationPlugin: {e}")
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
            
            # 停止行为引擎
            if self.behavior_engine:
                await self.behavior_engine.stop()
            
            logger.info("BehaviorSimulationPlugin stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop BehaviorSimulationPlugin: {e}")
            return False
    
    async def _healthcheck_impl(self) -> Dict[str, Any]:
        """具体健康检查实现"""
        try:
            health_result = {
                'healthy': True,
                'behavior_engine_status': 'unknown',
                'total_actions': sum([
                    self.behavior_stats.get('total_mouse_actions', 0),
                    self.behavior_stats.get('total_keyboard_actions', 0),
                    self.behavior_stats.get('total_page_actions', 0)
                ]),
                'success_rate': 0.0,
                'learned_patterns': len(self.behavior_patterns),
                'last_check': datetime.now().isoformat()
            }
            
            if self.behavior_engine:
                # 检查行为引擎状态
                engine_health = await self.behavior_engine.health_check()
                health_result['behavior_engine_status'] = 'healthy' if engine_health.get('healthy', False) else 'unhealthy'
                
                # 计算成功率
                total_actions = self.behavior_stats.get('successful_actions', 0) + self.behavior_stats.get('failed_actions', 0)
                if total_actions > 0:
                    health_result['success_rate'] = self.behavior_stats.get('successful_actions', 0) / total_actions * 100
                
                # 整体健康状态
                health_result['healthy'] = engine_health.get('healthy', False)
            
            return health_result
            
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }
    
    async def simulate_mouse_behavior(self, session: Any, behavior_config: Dict[str, Any] = None) -> bool:
        """模拟鼠标行为"""
        start_time = time.time()
        
        try:
            if not self.behavior_engine:
                return False
            
            # 合并配置
            config = behavior_config or {}
            
            # 执行鼠标行为
            success = await self.behavior_engine.simulate_mouse_behavior(session, config)
            
            # 记录行为
            action_record = {
                'type': 'mouse',
                'timestamp': datetime.now().isoformat(),
                'duration': time.time() - start_time,
                'success': success,
                'config': config
            }
            
            await self._record_behavior_action(action_record)
            
            # 更新统计
            self.behavior_stats['total_mouse_actions'] += 1
            if success:
                self.behavior_stats['successful_actions'] += 1
            else:
                self.behavior_stats['failed_actions'] += 1
            
            return success
            
        except Exception as e:
            self.behavior_stats['failed_actions'] += 1
            logger.error(f"Failed to simulate mouse behavior: {e}")
            return False
    
    async def simulate_keyboard_behavior(self, session: Any, behavior_config: Dict[str, Any] = None) -> bool:
        """模拟键盘行为"""
        start_time = time.time()
        
        try:
            if not self.behavior_engine:
                return False
            
            # 合并配置
            config = behavior_config or {}
            
            # 应用打字配置
            config.setdefault('typing_speed', self.behavior_config.typing_speed)
            config.setdefault('typing_variation', self.behavior_config.typing_variation)
            config.setdefault('enable_errors', self.behavior_config.enable_typing_errors)
            config.setdefault('error_rate', self.behavior_config.error_rate)
            
            # 执行键盘行为
            success = await self.behavior_engine.simulate_keyboard_behavior(session, config)
            
            # 记录行为
            action_record = {
                'type': 'keyboard',
                'timestamp': datetime.now().isoformat(),
                'duration': time.time() - start_time,
                'success': success,
                'config': config
            }
            
            await self._record_behavior_action(action_record)
            
            # 更新统计
            self.behavior_stats['total_keyboard_actions'] += 1
            if success:
                self.behavior_stats['successful_actions'] += 1
            else:
                self.behavior_stats['failed_actions'] += 1
            
            return success
            
        except Exception as e:
            self.behavior_stats['failed_actions'] += 1
            logger.error(f"Failed to simulate keyboard behavior: {e}")
            return False
    
    async def simulate_page_behavior(self, session: Any, behavior_config: Dict[str, Any] = None) -> bool:
        """模拟页面行为"""
        start_time = time.time()
        
        try:
            if not self.behavior_engine:
                return False
            
            # 合并配置
            config = behavior_config or {}
            
            # 应用页面行为配置
            config.setdefault('page_load_wait', self.behavior_config.page_load_wait)
            config.setdefault('element_search_delay', self.behavior_config.element_search_delay)
            config.setdefault('scroll_behavior', self.behavior_config.scroll_behavior)
            config.setdefault('reading_behavior', self.behavior_config.reading_behavior)
            
            # 执行页面行为
            success = await self.behavior_engine.simulate_page_behavior(session, config)
            
            # 记录行为
            action_record = {
                'type': 'page',
                'timestamp': datetime.now().isoformat(),
                'duration': time.time() - start_time,
                'success': success,
                'config': config
            }
            
            await self._record_behavior_action(action_record)
            
            # 更新统计
            self.behavior_stats['total_page_actions'] += 1
            if success:
                self.behavior_stats['successful_actions'] += 1
            else:
                self.behavior_stats['failed_actions'] += 1
            
            return success
            
        except Exception as e:
            self.behavior_stats['failed_actions'] += 1
            logger.error(f"Failed to simulate page behavior: {e}")
            return False
    
    async def get_behavior_stats(self) -> Dict[str, Any]:
        """获取行为统计"""
        try:
            stats = self.behavior_stats.copy()
            
            # 添加详细统计
            stats.update({
                'action_history_size': len(self.action_history),
                'learned_patterns': len(self.behavior_patterns),
                'timing_profiles': len(self.timing_stats),
                'recent_success_rate': await self._calculate_recent_success_rate(),
                'behavior_distribution': self._get_behavior_distribution(),
                'timing_analysis': self._get_timing_analysis(),
                'pattern_effectiveness': self._get_pattern_effectiveness()
            })
            
            # 计算平均动作时间
            total_actions = (stats.get('total_mouse_actions', 0) + 
                           stats.get('total_keyboard_actions', 0) + 
                           stats.get('total_page_actions', 0))
            
            if total_actions > 0 and self.action_history:
                total_time = sum(action.get('duration', 0) for action in self.action_history)
                stats['average_action_time'] = total_time / len(self.action_history)
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get behavior stats: {e}")
            return self.behavior_stats.copy()
    
    async def _record_behavior_action(self, action_record: Dict[str, Any]):
        """记录行为动作"""
        try:
            # 添加到历史记录
            self.action_history.append(action_record)
            
            # 限制历史记录大小
            max_history_size = self.behavior_config.pattern_memory_size * 2
            if len(self.action_history) > max_history_size:
                self.action_history = self.action_history[-max_history_size:]
            
            # 学习行为模式
            if self.behavior_config.learning_enabled:
                await self._learn_behavior_pattern(action_record)
            
            # 更新时间统计
            action_type = action_record.get('type', 'unknown')
            duration = action_record.get('duration', 0)
            
            if action_type not in self.timing_stats:
                self.timing_stats[action_type] = []
            
            self.timing_stats[action_type].append(duration)
            
            # 限制时间统计大小
            max_timing_size = self.behavior_config.pattern_memory_size
            if len(self.timing_stats[action_type]) > max_timing_size:
                self.timing_stats[action_type] = self.timing_stats[action_type][-max_timing_size:]
            
        except Exception as e:
            logger.error(f"Failed to record behavior action: {e}")
    
    async def _learn_behavior_pattern(self, action_record: Dict[str, Any]):
        """学习行为模式"""
        try:
            action_type = action_record.get('type', 'unknown')
            
            if action_type not in self.behavior_patterns:
                self.behavior_patterns[action_type] = []
            
            # 提取模式特征
            pattern = {
                'duration': action_record.get('duration', 0),
                'success': action_record.get('success', False),
                'timestamp': action_record.get('timestamp'),
                'config_hash': self._hash_config(action_record.get('config', {}))
            }
            
            self.behavior_patterns[action_type].append(pattern)
            
            # 限制模式大小
            max_pattern_size = self.behavior_config.pattern_memory_size
            if len(self.behavior_patterns[action_type]) > max_pattern_size:
                self.behavior_patterns[action_type] = self.behavior_patterns[action_type][-max_pattern_size:]
            
            self.behavior_stats['behavior_patterns_learned'] = sum(len(patterns) for patterns in self.behavior_patterns.values())
            
        except Exception as e:
            logger.error(f"Failed to learn behavior pattern: {e}")
    
    def _hash_config(self, config: Dict[str, Any]) -> str:
        """生成配置哈希"""
        import hashlib
        import json
        
        try:
            config_str = json.dumps(config, sort_keys=True)
            return hashlib.md5(config_str.encode()).hexdigest()[:8]
        except Exception:
            return "unknown"
    
    async def _calculate_recent_success_rate(self, recent_minutes: int = 30) -> float:
        """计算最近成功率"""
        try:
            cutoff_time = datetime.now() - timedelta(minutes=recent_minutes)
            
            recent_actions = [
                action for action in self.action_history
                if datetime.fromisoformat(action.get('timestamp', '')) > cutoff_time
            ]
            
            if not recent_actions:
                return 0.0
            
            successful = sum(1 for action in recent_actions if action.get('success', False))
            return successful / len(recent_actions) * 100
            
        except Exception as e:
            logger.error(f"Failed to calculate recent success rate: {e}")
            return 0.0
    
    def _get_behavior_distribution(self) -> Dict[str, int]:
        """获取行为分布"""
        distribution = {}
        
        for action in self.action_history:
            action_type = action.get('type', 'unknown')
            distribution[action_type] = distribution.get(action_type, 0) + 1
        
        return distribution
    
    def _get_timing_analysis(self) -> Dict[str, Dict[str, float]]:
        """获取时间分析"""
        analysis = {}
        
        for action_type, durations in self.timing_stats.items():
            if durations:
                analysis[action_type] = {
                    'min': min(durations),
                    'max': max(durations),
                    'avg': sum(durations) / len(durations),
                    'count': len(durations)
                }
        
        return analysis
    
    def _get_pattern_effectiveness(self) -> Dict[str, float]:
        """获取模式有效性"""
        effectiveness = {}
        
        for action_type, patterns in self.behavior_patterns.items():
            if patterns:
                successful = sum(1 for pattern in patterns if pattern.get('success', False))
                effectiveness[action_type] = successful / len(patterns) * 100
        
        return effectiveness
    
    async def _initialize_behavior_patterns(self):
        """初始化行为模式"""
        # 这里可以加载预定义的行为模式
        # 或从历史数据中恢复模式
        pass
    
    def _start_monitoring_tasks(self):
        """启动监控任务"""
        # 模式分析任务
        if self.behavior_config.learning_enabled:
            self.monitoring_tasks.append(
                asyncio.create_task(self._pattern_analysis_loop())
            )
        
        # 性能优化任务
        if self.behavior_config.adaptive_timing:
            self.monitoring_tasks.append(
                asyncio.create_task(self._adaptive_timing_loop())
            )
    
    async def _pattern_analysis_loop(self):
        """模式分析循环"""
        while True:
            try:
                await asyncio.sleep(1800)  # 每30分钟分析一次
                
                # 分析行为模式
                await self._analyze_behavior_patterns()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Pattern analysis loop error: {e}")
                await asyncio.sleep(900)  # 错误时等待15分钟
    
    async def _adaptive_timing_loop(self):
        """自适应时间调整循环"""
        while True:
            try:
                await asyncio.sleep(3600)  # 每小时调整一次
                
                # 调整时间参数
                await self._adjust_timing_parameters()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Adaptive timing loop error: {e}")
                await asyncio.sleep(1800)  # 错误时等待30分钟
    
    async def _analyze_behavior_patterns(self):
        """分析行为模式"""
        try:
            # 这里可以实现更复杂的模式分析逻辑
            # 例如：识别最有效的行为组合，检测异常模式等
            
            for action_type, patterns in self.behavior_patterns.items():
                if len(patterns) > 10:  # 有足够的数据
                    # 计算平均成功率
                    success_rate = sum(1 for p in patterns if p.get('success', False)) / len(patterns)
                    
                    # 如果成功率低，可以调整相关配置
                    if success_rate < 0.7:
                        logger.info(f"Low success rate for {action_type}: {success_rate:.2f}")
                        # 这里可以实现自动调整逻辑
            
        except Exception as e:
            logger.error(f"Failed to analyze behavior patterns: {e}")
    
    async def _adjust_timing_parameters(self):
        """调整时间参数"""
        try:
            # 基于历史表现调整时间参数
            for action_type, durations in self.timing_stats.items():
                if len(durations) > 10:
                    avg_duration = sum(durations) / len(durations)
                    
                    # 根据平均时长调整配置
                    if action_type == 'mouse' and avg_duration > 2.0:
                        # 鼠标动作太慢，可以适当加快
                        self.behavior_config.mouse_move_speed *= 1.1
                        self.behavior_stats['adaptive_adjustments'] += 1
                    elif action_type == 'keyboard' and avg_duration > 1.0:
                        # 键盘输入太慢，可以适当加快
                        self.behavior_config.typing_speed *= 0.9
                        self.behavior_stats['adaptive_adjustments'] += 1
            
        except Exception as e:
            logger.error(f"Failed to adjust timing parameters: {e}")
    
    async def _apply_config_reload(self):
        """应用配置重新加载"""
        try:
            # 重新加载配置
            self._load_plugin_config(self._config)
            
            logger.info("Behavior plugin config reloaded")
            
        except Exception as e:
            logger.error(f"Failed to apply config reload: {e}")
            raise


# 便利函数
async def create_behavior_plugin(config: Dict[str, Any] = None) -> BehaviorSimulationPlugin:
    """创建行为模拟插件实例"""
    plugin = BehaviorSimulationPlugin(config)
    await plugin.initialize()
    await plugin.start()
    return plugin


def get_default_behavior_config() -> Dict[str, Any]:
    """获取默认行为配置"""
    return {
        'mouse_move_speed': 1.0,
        'mouse_click_delay': (0.1, 0.3),
        'mouse_scroll_delay': (0.2, 0.5),
        'enable_mouse_curves': True,
        'typing_speed': 0.1,
        'typing_variation': 0.05,
        'enable_typing_errors': True,
        'error_rate': 0.02,
        'page_load_wait': (1.0, 3.0),
        'element_search_delay': (0.5, 1.5),
        'scroll_behavior': 'natural',
        'reading_behavior': True,
        'reading_speed': 200.0,
        'attention_span': (10.0, 30.0),
        'behavior_randomization': 0.2,
        'pattern_variation': 0.15,
        'timing_jitter': 0.1,
        'adaptive_timing': True,
        'learning_enabled': True,
        'pattern_memory_size': 100
    }