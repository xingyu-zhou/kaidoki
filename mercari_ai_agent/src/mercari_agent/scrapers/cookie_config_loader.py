"""
Cookie配置加载器

该模块负责加载和解析Cookie管理配置文件，支持YAML格式配置文件的读取、
验证和转换。提供灵活的配置管理机制，支持环境变量替换和配置继承。

主要功能：
- YAML配置文件加载和解析
- 配置验证和错误处理
- 环境变量替换支持
- 配置合并和继承
- 动态配置更新
- 配置缓存和性能优化

Author: Mercari AI Agent Team
"""

import os
import yaml
import logging
import re
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import copy

from ..utils.logger import get_logger
from ..config.settings import settings
from .smart_cookie_manager import CookieRule, CookieCategory

logger = get_logger(__name__)


@dataclass
class ConfigValidationError(Exception):
    """配置验证错误"""
    message: str
    field: str
    value: Any
    
    def __str__(self):
        return f"配置验证错误 - {self.field}: {self.message} (值: {self.value})"


class CookieConfigLoader:
    """
    Cookie配置加载器
    
    负责从YAML文件加载Cookie管理配置，支持环境变量替换、
    配置验证和动态更新。
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置加载器
        
        Args:
            config_path: 配置文件路径，如果为None则使用默认路径
        """
        self.config_path = config_path or self._get_default_config_path()
        self.config_cache: Optional[Dict[str, Any]] = None
        self.config_last_modified: Optional[datetime] = None
        self.environment_variables = {}
        
        # 加载环境变量
        self._load_environment_variables()
        
        logger.info(f"Cookie配置加载器初始化完成，配置文件: {self.config_path}")
    
    def _get_default_config_path(self) -> str:
        """获取默认配置文件路径"""
        # 尝试多个可能的路径
        possible_paths = [
            Path(settings.CONFIG_DIR) / "cookie_management.yaml",
            Path(__file__).parent.parent.parent.parent / "config" / "cookie_management.yaml",
            Path.cwd() / "config" / "cookie_management.yaml",
            Path.cwd() / "cookie_management.yaml"
        ]
        
        for path in possible_paths:
            if path.exists():
                return str(path)
        
        # 如果都不存在，返回第一个作为默认创建路径
        return str(possible_paths[0])
    
    def _load_environment_variables(self):
        """加载环境变量"""
        self.environment_variables = {
            key: value for key, value in os.environ.items()
            if key.startswith('COOKIE_') or key.startswith('MERCARI_')
        }
        
        logger.debug(f"加载了 {len(self.environment_variables)} 个环境变量")
    
    def load_config(self, force_reload: bool = False) -> Dict[str, Any]:
        """
        加载配置
        
        Args:
            force_reload: 是否强制重新加载
            
        Returns:
            Dict[str, Any]: 配置字典
        """
        config_path = Path(self.config_path)
        
        # 检查文件是否存在
        if not config_path.exists():
            logger.warning(f"配置文件不存在: {config_path}")
            return self._get_default_config()
        
        # 检查是否需要重新加载
        current_modified = datetime.fromtimestamp(config_path.stat().st_mtime)
        if (not force_reload and 
            self.config_cache and 
            self.config_last_modified and
            current_modified <= self.config_last_modified):
            logger.debug("使用缓存的配置")
            return self.config_cache
        
        try:
            # 读取YAML文件
            with open(config_path, 'r', encoding='utf-8') as file:
                raw_config = yaml.safe_load(file)
            
            # 处理环境变量替换
            config = self._process_environment_variables(raw_config)
            
            # 验证配置
            self._validate_config(config)
            
            # 处理配置继承和合并
            config = self._process_config_inheritance(config)
            
            # 缓存配置
            self.config_cache = config
            self.config_last_modified = current_modified
            
            logger.info("配置加载成功")
            return config
            
        except yaml.YAMLError as e:
            logger.error(f"YAML解析错误: {e}")
            raise ConfigValidationError("YAML解析失败", "yaml_content", str(e))
        
        except Exception as e:
            logger.error(f"配置加载失败: {e}")
            raise ConfigValidationError("配置加载失败", "config_file", str(e))
    
    def _process_environment_variables(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理环境变量替换
        
        Args:
            config: 原始配置
            
        Returns:
            Dict[str, Any]: 处理后的配置
        """
        def replace_env_vars(value: Any) -> Any:
            if isinstance(value, str):
                # 匹配 ${VAR_NAME} 或 ${VAR_NAME:default_value} 格式
                pattern = r'\$\{([^}:]+)(?::([^}]*))?\}'
                
                def replace_match(match):
                    var_name = match.group(1)
                    default_value = match.group(2) if match.group(2) is not None else ""
                    
                    # 首先检查自定义环境变量
                    if var_name in self.environment_variables:
                        return self.environment_variables[var_name]
                    
                    # 然后检查系统环境变量
                    return os.environ.get(var_name, default_value)
                
                return re.sub(pattern, replace_match, value)
            
            elif isinstance(value, dict):
                return {k: replace_env_vars(v) for k, v in value.items()}
            
            elif isinstance(value, list):
                return [replace_env_vars(item) for item in value]
            
            return value
        
        return replace_env_vars(config)
    
    def _validate_config(self, config: Dict[str, Any]):
        """
        验证配置
        
        Args:
            config: 配置字典
            
        Raises:
            ConfigValidationError: 配置验证失败时抛出
        """
        # 验证必需的顶级字段
        required_fields = ['global_config', 'cookie_rules']
        for field in required_fields:
            if field not in config:
                raise ConfigValidationError(
                    f"缺少必需字段", field, None
                )
        
        # 验证全局配置
        self._validate_global_config(config.get('global_config', {}))
        
        # 验证Cookie规则
        self._validate_cookie_rules(config.get('cookie_rules', {}))
        
        # 验证域名配置
        if 'domain_configs' in config:
            self._validate_domain_configs(config['domain_configs'])
        
        # 验证学习配置
        if 'learning_config' in config:
            self._validate_learning_config(config['learning_config'])
    
    def _validate_global_config(self, global_config: Dict[str, Any]):
        """验证全局配置"""
        # 验证布尔值字段
        bool_fields = [
            'learning_enabled', 'monitoring_enabled', 'preserve_critical_cookies',
            'preserve_important_cookies', 'preserve_optional_cookies',
            'filter_blacklist_cookies', 'filter_expired_cookies', 'strict_mode'
        ]
        
        for field in bool_fields:
            if field in global_config and not isinstance(global_config[field], bool):
                raise ConfigValidationError(
                    f"字段必须是布尔值", field, global_config[field]
                )
        
        # 验证数值字段
        numeric_fields = {
            'learning_threshold': (0.0, 1.0),
            'adaptation_rate': (0.0, 1.0),
            'max_cookies': (1, 1000000),
            'cleanup_interval': (1, 86400)
        }
        
        for field, (min_val, max_val) in numeric_fields.items():
            if field in global_config:
                value = global_config[field]
                if not isinstance(value, (int, float)) or value < min_val or value > max_val:
                    raise ConfigValidationError(
                        f"字段值必须在 {min_val} 到 {max_val} 之间", field, value
                    )
        
        # 验证字符串字段
        string_fields = ['default_category', 'default_action']
        for field in string_fields:
            if field in global_config and not isinstance(global_config[field], str):
                raise ConfigValidationError(
                    f"字段必须是字符串", field, global_config[field]
                )
        
        # 验证枚举值
        if 'default_category' in global_config:
            valid_categories = [cat.value for cat in CookieCategory]
            if global_config['default_category'] not in valid_categories:
                raise ConfigValidationError(
                    f"无效的默认分类，必须是 {valid_categories} 之一",
                    'default_category', global_config['default_category']
                )
    
    def _validate_cookie_rules(self, cookie_rules: Dict[str, Any]):
        """验证Cookie规则"""
        rule_categories = ['critical_cookies', 'important_cookies', 'optional_cookies', 'blacklist_cookies']
        
        for category in rule_categories:
            if category in cookie_rules:
                rules = cookie_rules[category]
                if not isinstance(rules, list):
                    raise ConfigValidationError(
                        f"规则分类必须是列表", category, type(rules)
                    )
                
                for i, rule in enumerate(rules):
                    self._validate_single_rule(rule, f"{category}[{i}]")
    
    def _validate_single_rule(self, rule: Dict[str, Any], rule_path: str):
        """验证单个规则"""
        # 验证必需字段
        required_fields = ['name_pattern', 'domain_pattern', 'category', 'priority']
        for field in required_fields:
            if field not in rule:
                raise ConfigValidationError(
                    f"规则缺少必需字段", f"{rule_path}.{field}", None
                )
        
        # 验证正则表达式
        try:
            re.compile(rule['name_pattern'])
        except re.error as e:
            raise ConfigValidationError(
                f"无效的正则表达式", f"{rule_path}.name_pattern", str(e)
            )
        
        try:
            re.compile(rule['domain_pattern'])
        except re.error as e:
            raise ConfigValidationError(
                f"无效的正则表达式", f"{rule_path}.domain_pattern", str(e)
            )
        
        # 验证分类
        valid_categories = [cat.value for cat in CookieCategory]
        if rule['category'] not in valid_categories:
            raise ConfigValidationError(
                f"无效的分类", f"{rule_path}.category", rule['category']
            )
        
        # 验证优先级
        if not isinstance(rule['priority'], int) or rule['priority'] < 0 or rule['priority'] > 100:
            raise ConfigValidationError(
                f"优先级必须是0-100之间的整数", f"{rule_path}.priority", rule['priority']
            )
    
    def _validate_domain_configs(self, domain_configs: Dict[str, Any]):
        """验证域名配置"""
        for domain, config in domain_configs.items():
            if not isinstance(config, dict):
                raise ConfigValidationError(
                    f"域名配置必须是字典", f"domain_configs.{domain}", type(config)
                )
            
            # 验证布尔字段
            bool_fields = ['strict_mode', 'preserve_optional_cookies', 'learning_enabled']
            for field in bool_fields:
                if field in config and not isinstance(config[field], bool):
                    raise ConfigValidationError(
                        f"字段必须是布尔值", f"domain_configs.{domain}.{field}", config[field]
                    )
    
    def _validate_learning_config(self, learning_config: Dict[str, Any]):
        """验证学习配置"""
        # 验证布尔字段
        bool_fields = ['enable_learning', 'auto_promote_rules', 'auto_demote_rules']
        for field in bool_fields:
            if field in learning_config and not isinstance(learning_config[field], bool):
                raise ConfigValidationError(
                    f"字段必须是布尔值", f"learning_config.{field}", learning_config[field]
                )
        
        # 验证数值字段
        numeric_fields = {
            'learning_rate': (0.0, 1.0),
            'confidence_threshold': (0.0, 1.0),
            'min_samples': (1, 10000),
            'adaptation_window': (1, 31536000),  # 1秒到1年
            'decay_factor': (0.0, 1.0),
            'stability_threshold': (0.0, 1.0),
            'max_dynamic_rules': (1, 100000)
        }
        
        for field, (min_val, max_val) in numeric_fields.items():
            if field in learning_config:
                value = learning_config[field]
                if not isinstance(value, (int, float)) or value < min_val or value > max_val:
                    raise ConfigValidationError(
                        f"字段值必须在 {min_val} 到 {max_val} 之间", 
                        f"learning_config.{field}", value
                    )
    
    def _process_config_inheritance(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理配置继承和合并
        
        Args:
            config: 原始配置
            
        Returns:
            Dict[str, Any]: 处理后的配置
        """
        # 深拷贝配置以避免修改原始配置
        processed_config = copy.deepcopy(config)
        
        # 处理域名配置继承
        if 'domain_configs' in processed_config:
            global_config = processed_config.get('global_config', {})
            
            for domain, domain_config in processed_config['domain_configs'].items():
                # 从全局配置继承缺失的字段
                for key, value in global_config.items():
                    if key not in domain_config:
                        domain_config[key] = value
        
        return processed_config
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'global_config': {
                'learning_enabled': True,
                'learning_threshold': 0.8,
                'adaptation_rate': 0.1,
                'max_cookies': 10000,
                'cleanup_interval': 300,
                'monitoring_enabled': True,
                'preserve_critical_cookies': True,
                'preserve_important_cookies': True,
                'preserve_optional_cookies': True,
                'filter_blacklist_cookies': True,
                'filter_expired_cookies': True,
                'default_category': 'optional',
                'default_action': 'allow',
                'strict_mode': False
            },
            'cookie_rules': {
                'critical_cookies': [
                    {
                        'name_pattern': '__cf_bm',
                        'domain_pattern': '.*',
                        'category': 'critical',
                        'priority': 100,
                        'action': 'preserve',
                        'description': 'Cloudflare Bot管理令牌'
                    }
                ],
                'important_cookies': [],
                'optional_cookies': [],
                'blacklist_cookies': []
            },
            'domain_configs': {},
            'learning_config': {
                'enable_learning': True,
                'learning_rate': 0.1,
                'confidence_threshold': 0.8,
                'min_samples': 10
            }
        }
    
    def get_rules_for_manager(self, config: Dict[str, Any]) -> List[CookieRule]:
        """
        将配置转换为SmartCookieManager可用的规则列表
        
        Args:
            config: 配置字典
            
        Returns:
            List[CookieRule]: 规则列表
        """
        rules = []
        cookie_rules = config.get('cookie_rules', {})
        
        # 处理各个分类的规则
        for category_name, category_rules in cookie_rules.items():
            if isinstance(category_rules, list):
                for rule_data in category_rules:
                    try:
                        rule = CookieRule(
                            name_pattern=rule_data['name_pattern'],
                            domain_pattern=rule_data['domain_pattern'],
                            path_pattern=rule_data.get('path_pattern', '/'),
                            category=CookieCategory(rule_data['category']),
                            action=rule_data.get('action', 'allow'),
                            priority=rule_data['priority'],
                            description=rule_data.get('description', '')
                        )
                        rules.append(rule)
                    except Exception as e:
                        logger.error(f"创建规则失败: {e}")
                        continue
        
        # 按优先级排序
        rules.sort(key=lambda x: x.priority, reverse=True)
        
        return rules
    
    def get_domain_config(self, config: Dict[str, Any], domain: str) -> Dict[str, Any]:
        """
        获取特定域名的配置
        
        Args:
            config: 全局配置
            domain: 域名
            
        Returns:
            Dict[str, Any]: 域名特定配置
        """
        global_config = config.get('global_config', {})
        domain_configs = config.get('domain_configs', {})
        
        # 查找匹配的域名配置
        domain_config = {}
        
        # 精确匹配
        if domain in domain_configs:
            domain_config = domain_configs[domain]
        else:
            # 模式匹配
            for pattern, config_data in domain_configs.items():
                if '*' in pattern:
                    # 简单的通配符匹配
                    regex_pattern = pattern.replace('*', '.*')
                    if re.match(regex_pattern, domain):
                        domain_config = config_data
                        break
        
        # 合并全局配置和域名配置
        merged_config = global_config.copy()
        merged_config.update(domain_config)
        
        return merged_config
    
    def save_config(self, config: Dict[str, Any], path: Optional[str] = None):
        """
        保存配置到文件
        
        Args:
            config: 配置字典
            path: 保存路径，如果为None则使用当前配置路径
        """
        save_path = path or self.config_path
        
        try:
            with open(save_path, 'w', encoding='utf-8') as file:
                yaml.dump(config, file, default_flow_style=False, 
                         allow_unicode=True, indent=2)
            
            logger.info(f"配置已保存到: {save_path}")
            
        except Exception as e:
            logger.error(f"配置保存失败: {e}")
            raise
    
    def reload_config(self) -> Dict[str, Any]:
        """
        重新加载配置
        
        Returns:
            Dict[str, Any]: 重新加载的配置
        """
        logger.info("重新加载配置...")
        return self.load_config(force_reload=True)
    
    def validate_config_file(self, path: str) -> bool:
        """
        验证配置文件
        
        Args:
            path: 配置文件路径
            
        Returns:
            bool: 验证是否成功
        """
        try:
            temp_loader = CookieConfigLoader(path)
            temp_loader.load_config()
            return True
        except Exception as e:
            logger.error(f"配置文件验证失败: {e}")
            return False