"""
反检测系统配置管理器

该模块负责加载、验证和管理反检测系统的配置文件，
提供统一的配置访问接口和动态配置更新功能。

主要功能：
1. 配置文件加载和验证
2. 预设模式管理
3. 动态配置更新
4. 配置项访问接口
5. 配置导出和备份

Author: Mercari AI Agent Team
"""

import os
import yaml
import logging
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from pathlib import Path
import json
from datetime import datetime
import shutil

from ..utils.logger import get_logger
from ..config.settings import settings

logger = get_logger(__name__)


@dataclass
class ConfigValidationError(Exception):
    """配置验证错误"""
    message: str
    config_path: str
    validation_errors: List[str] = field(default_factory=list)


class AntiDetectionConfigManager:
    """反检测系统配置管理器"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件路径，默认使用内置配置
        """
        self.config_file = config_file or self._get_default_config_path()
        self.config_data: Dict[str, Any] = {}
        self.validation_rules = self._load_validation_rules()
        self.loaded_preset: Optional[str] = None
        
        # 加载配置
        self._load_config()
        
        logger.info(f"📝 反检测配置管理器初始化完成: {self.config_file}")
    
    def _get_default_config_path(self) -> str:
        """获取默认配置文件路径"""
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "config",
            "anti_detection_config.yaml"
        )
    
    def _load_config(self):
        """加载配置文件"""
        try:
            if not os.path.exists(self.config_file):
                raise FileNotFoundError(f"配置文件不存在: {self.config_file}")
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config_data = yaml.safe_load(f)
            
            # 验证配置
            self._validate_config()
            
            logger.info(f"✅ 配置文件加载成功: {self.config_file}")
            
        except Exception as e:
            logger.error(f"❌ 配置文件加载失败: {e}")
            raise ConfigValidationError(
                message=f"配置文件加载失败: {e}",
                config_path=self.config_file
            )
    
    def _validate_config(self):
        """验证配置文件"""
        validation_errors = []
        
        # 验证必需的配置节
        required_sections = [
            'global', 'environment_spoofing', 'fingerprint_management',
            'session_management', 'tls_fingerprinting', 'anti_bot_detection'
        ]
        
        for section in required_sections:
            if section not in self.config_data:
                validation_errors.append(f"缺少必需的配置节: {section}")
        
        # 验证全局配置
        if 'global' in self.config_data:
            global_config = self.config_data['global']
            if 'mode' not in global_config:
                validation_errors.append("缺少全局模式配置")
            elif global_config['mode'] not in ['stealth', 'balanced', 'performance', 'debugging']:
                validation_errors.append(f"无效的全局模式: {global_config['mode']}")
        
        # 验证伪装级别
        if 'environment_spoofing' in self.config_data:
            spoofing_config = self.config_data['environment_spoofing']
            if 'spoofing_level' in spoofing_config:
                if spoofing_config['spoofing_level'] not in ['minimal', 'standard', 'aggressive']:
                    validation_errors.append(f"无效的伪装级别: {spoofing_config['spoofing_level']}")
        
        # 验证质量配置
        if 'fingerprint_management' in self.config_data:
            fingerprint_config = self.config_data['fingerprint_management']
            if 'quality' in fingerprint_config and 'min_quality' in fingerprint_config['quality']:
                if fingerprint_config['quality']['min_quality'] not in ['excellent', 'good', 'fair', 'poor']:
                    validation_errors.append(f"无效的最小质量要求: {fingerprint_config['quality']['min_quality']}")
        
        # 验证数值范围
        self._validate_numeric_ranges(validation_errors)
        
        if validation_errors:
            raise ConfigValidationError(
                message="配置验证失败",
                config_path=self.config_file,
                validation_errors=validation_errors
            )
    
    def _validate_numeric_ranges(self, validation_errors: List[str]):
        """验证数值范围"""
        # 验证并发配置
        if 'session_management' in self.config_data:
            session_config = self.config_data['session_management']
            if 'concurrency' in session_config:
                concurrency = session_config['concurrency']
                if 'max_concurrent_sessions' in concurrency:
                    if not (1 <= concurrency['max_concurrent_sessions'] <= 50):
                        validation_errors.append("最大并发会话数必须在1-50之间")
        
        # 验证超时配置
        if 'session_management' in self.config_data:
            session_config = self.config_data['session_management']
            if 'timeouts' in session_config:
                timeouts = session_config['timeouts']
                if 'connection_timeout' in timeouts:
                    if not (1 <= timeouts['connection_timeout'] <= 300):
                        validation_errors.append("连接超时必须在1-300秒之间")
        
        # 验证请求间隔
        if 'session_management' in self.config_data:
            session_config = self.config_data['session_management']
            if 'request_intervals' in session_config:
                intervals = session_config['request_intervals']
                if 'min_interval' in intervals and 'max_interval' in intervals:
                    if intervals['min_interval'] >= intervals['max_interval']:
                        validation_errors.append("最小请求间隔必须小于最大请求间隔")
    
    def _load_validation_rules(self) -> Dict[str, Any]:
        """加载验证规则"""
        return {
            'global': {
                'mode': ['stealth', 'balanced', 'performance', 'debugging'],
                'enabled': [True, False]
            },
            'environment_spoofing': {
                'spoofing_level': ['minimal', 'standard', 'aggressive'],
                'enabled': [True, False]
            },
            'fingerprint_management': {
                'quality': {
                    'min_quality': ['excellent', 'good', 'fair', 'poor']
                }
            }
        }
    
    def get_config(self, path: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            path: 配置路径，使用点号分隔，如 'global.mode'
            default: 默认值
            
        Returns:
            配置值或默认值
        """
        try:
            parts = path.split('.')
            current = self.config_data
            
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return default
            
            return current
            
        except Exception as e:
            logger.error(f"获取配置失败: {path} - {e}")
            return default
    
    def set_config(self, path: str, value: Any):
        """
        设置配置值
        
        Args:
            path: 配置路径
            value: 配置值
        """
        try:
            parts = path.split('.')
            current = self.config_data
            
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            current[parts[-1]] = value
            
            logger.debug(f"设置配置: {path} = {value}")
            
        except Exception as e:
            logger.error(f"设置配置失败: {path} - {e}")
            raise
    
    def get_global_config(self) -> Dict[str, Any]:
        """获取全局配置"""
        return self.get_config('global', {})
    
    def get_environment_spoofing_config(self) -> Dict[str, Any]:
        """获取环境伪装配置"""
        return self.get_config('environment_spoofing', {})
    
    def get_fingerprint_management_config(self) -> Dict[str, Any]:
        """获取指纹管理配置"""
        return self.get_config('fingerprint_management', {})
    
    def get_session_management_config(self) -> Dict[str, Any]:
        """获取会话管理配置"""
        return self.get_config('session_management', {})
    
    def get_tls_fingerprinting_config(self) -> Dict[str, Any]:
        """获取TLS指纹配置"""
        return self.get_config('tls_fingerprinting', {})
    
    def get_anti_bot_detection_config(self) -> Dict[str, Any]:
        """获取反爬虫检测配置"""
        return self.get_config('anti_bot_detection', {})
    
    def get_mercari_specific_config(self) -> Dict[str, Any]:
        """获取Mercari特定配置"""
        return self.get_config('mercari_specific', {})
    
    def get_monitoring_config(self) -> Dict[str, Any]:
        """获取监控配置"""
        return self.get_config('monitoring', {})
    
    def load_preset(self, preset_name: str):
        """
        加载预设配置
        
        Args:
            preset_name: 预设名称 (stealth/performance/debugging)
        """
        if 'presets' not in self.config_data:
            raise ValueError("配置文件中没有预设配置")
        
        if preset_name not in self.config_data['presets']:
            raise ValueError(f"预设配置不存在: {preset_name}")
        
        preset_config = self.config_data['presets'][preset_name]
        
        # 应用预设配置
        for section, config in preset_config.items():
            if section in self.config_data:
                self._merge_config(self.config_data[section], config)
            else:
                self.config_data[section] = config
        
        self.loaded_preset = preset_name
        logger.info(f"✅ 已加载预设配置: {preset_name}")
    
    def _merge_config(self, base: Dict[str, Any], override: Dict[str, Any]):
        """递归合并配置"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value
    
    def save_config(self, backup: bool = True):
        """
        保存配置到文件
        
        Args:
            backup: 是否创建备份
        """
        try:
            if backup:
                self._create_backup()
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(self.config_data, f, default_flow_style=False, 
                         allow_unicode=True, indent=2)
            
            logger.info(f"✅ 配置文件保存成功: {self.config_file}")
            
        except Exception as e:
            logger.error(f"❌ 配置文件保存失败: {e}")
            raise
    
    def _create_backup(self):
        """创建配置备份"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"{self.config_file}.backup_{timestamp}"
            shutil.copy2(self.config_file, backup_file)
            logger.debug(f"创建配置备份: {backup_file}")
        except Exception as e:
            logger.warning(f"创建配置备份失败: {e}")
    
    def export_config(self, export_path: str, format: str = 'yaml'):
        """
        导出配置
        
        Args:
            export_path: 导出路径
            format: 导出格式 (yaml/json)
        """
        try:
            os.makedirs(os.path.dirname(export_path), exist_ok=True)
            
            if format.lower() == 'json':
                with open(export_path, 'w', encoding='utf-8') as f:
                    json.dump(self.config_data, f, indent=2, ensure_ascii=False)
            else:
                with open(export_path, 'w', encoding='utf-8') as f:
                    yaml.dump(self.config_data, f, default_flow_style=False,
                             allow_unicode=True, indent=2)
            
            logger.info(f"✅ 配置导出成功: {export_path}")
            
        except Exception as e:
            logger.error(f"❌ 配置导出失败: {e}")
            raise
    
    def get_all_presets(self) -> List[str]:
        """获取所有可用预设"""
        return list(self.config_data.get('presets', {}).keys())
    
    def is_enabled(self, feature_path: str) -> bool:
        """
        检查功能是否启用
        
        Args:
            feature_path: 功能路径，如 'environment_spoofing.enabled'
            
        Returns:
            bool: 是否启用
        """
        return self.get_config(feature_path, False)
    
    def get_mode(self) -> str:
        """获取当前模式"""
        return self.get_config('global.mode', 'balanced')
    
    def get_spoofing_level(self) -> str:
        """获取伪装级别"""
        return self.get_config('environment_spoofing.spoofing_level', 'standard')
    
    def get_min_fingerprint_quality(self) -> str:
        """获取最小指纹质量"""
        return self.get_config('fingerprint_management.quality.min_quality', 'fair')
    
    def get_max_concurrent_sessions(self) -> int:
        """获取最大并发会话数"""
        return self.get_config('session_management.concurrency.max_concurrent_sessions', 3)
    
    def get_request_intervals(self) -> Dict[str, float]:
        """获取请求间隔配置"""
        return self.get_config('session_management.request_intervals', {
            'min_interval': 8.0,
            'max_interval': 15.0
        })
    
    def get_enabled_detections(self) -> List[str]:
        """获取启用的检测类型"""
        return self.get_config('environment_spoofing.enabled_detections', [])
    
    def get_browser_distribution(self) -> Dict[str, float]:
        """获取浏览器分布"""
        return self.get_config('fingerprint_management.browser_distribution', {
            'chrome': 0.65,
            'firefox': 0.15,
            'safari': 0.10,
            'edge': 0.08,
            'opera': 0.02
        })
    
    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要"""
        return {
            'mode': self.get_mode(),
            'spoofing_level': self.get_spoofing_level(),
            'min_quality': self.get_min_fingerprint_quality(),
            'max_sessions': self.get_max_concurrent_sessions(),
            'loaded_preset': self.loaded_preset,
            'enabled_features': {
                'environment_spoofing': self.is_enabled('environment_spoofing.enabled'),
                'fingerprint_management': self.is_enabled('fingerprint_management.enabled'),
                'session_management': self.is_enabled('session_management.enabled'),
                'tls_fingerprinting': self.is_enabled('tls_fingerprinting.enabled'),
                'anti_bot_detection': self.is_enabled('anti_bot_detection.enabled')
            }
        }
    
    def validate_runtime_config(self) -> List[str]:
        """验证运行时配置"""
        warnings = []
        
        # 检查配置一致性
        if self.get_mode() == 'stealth' and self.get_spoofing_level() == 'minimal':
            warnings.append("隐身模式建议使用更高的伪装级别")
        
        if self.get_mode() == 'performance' and self.get_min_fingerprint_quality() == 'excellent':
            warnings.append("性能模式建议降低指纹质量要求")
        
        # 检查资源配置
        max_sessions = self.get_max_concurrent_sessions()
        if max_sessions > 10:
            warnings.append(f"过高的并发会话数({max_sessions})可能影响性能")
        
        intervals = self.get_request_intervals()
        if intervals['min_interval'] < 3.0:
            warnings.append("过短的请求间隔可能触发反爬虫检测")
        
        return warnings
    
    def reload_config(self):
        """重新加载配置文件"""
        self._load_config()
        logger.info("🔄 配置文件重新加载完成")


# 全局配置管理器实例
_config_manager: Optional[AntiDetectionConfigManager] = None


def get_config_manager(config_file: Optional[str] = None) -> AntiDetectionConfigManager:
    """获取配置管理器单例"""
    global _config_manager
    
    if _config_manager is None:
        _config_manager = AntiDetectionConfigManager(config_file)
    
    return _config_manager


def reload_config_manager(config_file: Optional[str] = None):
    """重新加载配置管理器"""
    global _config_manager
    _config_manager = AntiDetectionConfigManager(config_file)


# 便捷函数
def get_config(path: str, default: Any = None) -> Any:
    """获取配置值的便捷函数"""
    return get_config_manager().get_config(path, default)


def is_enabled(feature_path: str) -> bool:
    """检查功能是否启用的便捷函数"""
    return get_config_manager().is_enabled(feature_path)


def get_mode() -> str:
    """获取当前模式的便捷函数"""
    return get_config_manager().get_mode()


# 测试函数
def test_config_manager():
    """测试配置管理器"""
    logger.info("🧪 开始测试配置管理器...")
    
    try:
        # 测试配置加载
        config_manager = get_config_manager()
        logger.info(f"✅ 配置管理器创建成功")
        
        # 测试配置获取
        mode = config_manager.get_mode()
        logger.info(f"当前模式: {mode}")
        
        # 测试功能启用检查
        spoofing_enabled = config_manager.is_enabled('environment_spoofing.enabled')
        logger.info(f"环境伪装启用: {spoofing_enabled}")
        
        # 测试配置摘要
        summary = config_manager.get_config_summary()
        logger.info(f"配置摘要: {summary}")
        
        # 测试预设加载
        presets = config_manager.get_all_presets()
        logger.info(f"可用预设: {presets}")
        
        # 测试运行时验证
        warnings = config_manager.validate_runtime_config()
        if warnings:
            logger.warning(f"配置警告: {warnings}")
        
        logger.info("✅ 配置管理器测试完成")
        
    except Exception as e:
        logger.error(f"❌ 配置管理器测试失败: {e}")


if __name__ == "__main__":
    test_config_manager()