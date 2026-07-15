"""
插件配置管理器

该模块实现了插件配置的统一管理和热加载功能，提供：
- 配置文件管理和验证
- 热加载和动态更新
- 配置模板和schema验证
- 环境变量支持
- 配置版本控制
- 配置备份和恢复

核心设计原则：
- 支持多种配置格式（YAML, JSON, TOML）
- 配置热加载，无需重启
- Schema验证，确保配置正确性
- 环境隔离，支持开发/测试/生产环境

Author: Mercari AI Agent Team
"""

import asyncio
import json
import os
import shutil
import time
import yaml
from typing import Dict, List, Optional, Any, Union, Callable, Type
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor
import jsonschema
from jsonschema import validate, ValidationError
import weakref

from .interfaces import IPlugin, PluginType, PluginCapability, PluginConfiguration
from .schemas import (
    SchemaValidator, ConfigTemplateGenerator,
    validate_plugin_config, get_plugin_default_config,
    PLUGIN_SCHEMAS, SCHEMA_METADATA, generate_plugin_template
)
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ConfigFormat(Enum):
    """配置文件格式"""
    YAML = "yaml"
    JSON = "json"
    TOML = "toml"


class ConfigEnvironment(Enum):
    """配置环境"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class ConfigFile:
    """配置文件信息"""
    path: Path
    format: ConfigFormat
    environment: ConfigEnvironment = ConfigEnvironment.DEVELOPMENT
    plugin_id: Optional[str] = None
    last_modified: Optional[datetime] = None
    checksum: Optional[str] = None
    version: str = "1.0.0"
    
    def calculate_checksum(self) -> str:
        """计算文件校验和"""
        if not self.path.exists():
            return ""
        
        with open(self.path, 'rb') as f:
            content = f.read()
            return hashlib.md5(content).hexdigest()
    
    def is_modified(self) -> bool:
        """检查文件是否被修改"""
        if not self.path.exists():
            return False
        
        current_checksum = self.calculate_checksum()
        return current_checksum != self.checksum
    
    def update_info(self):
        """更新文件信息"""
        if self.path.exists():
            stat = self.path.stat()
            self.last_modified = datetime.fromtimestamp(stat.st_mtime)
            self.checksum = self.calculate_checksum()


@dataclass
class ConfigWatch:
    """配置监控"""
    config_file: ConfigFile
    callback: Callable[[Dict[str, Any]], None]
    last_check: datetime = field(default_factory=datetime.now)
    check_interval: float = 5.0  # 秒
    enabled: bool = True


@dataclass
class ConfigTemplate:
    """配置模板"""
    template_id: str
    plugin_type: PluginType
    schema: Dict[str, Any]
    default_values: Dict[str, Any] = field(default_factory=dict)
    required_fields: List[str] = field(default_factory=list)
    description: str = ""
    examples: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ConfigManagerStats:
    """配置管理器统计信息"""
    total_configs: int = 0
    loaded_configs: int = 0
    failed_configs: int = 0
    hot_reloads: int = 0
    validation_errors: int = 0
    schema_validations: int = 0
    backup_operations: int = 0
    
    # 性能统计
    average_load_time: float = 0.0
    average_validation_time: float = 0.0
    
    def update_load_stats(self, success: bool, load_time: float):
        """更新加载统计"""
        self.total_configs += 1
        if success:
            self.loaded_configs += 1
            # 更新平均加载时间
            if self.loaded_configs > 0:
                current_total = self.average_load_time * (self.loaded_configs - 1)
                self.average_load_time = (current_total + load_time) / self.loaded_configs
        else:
            self.failed_configs += 1


class PluginConfigManager:
    """
    插件配置管理器
    
    核心功能：
    1. 配置文件管理和验证
    2. 热加载和动态更新
    3. 配置模板和schema验证
    4. 环境变量支持
    5. 配置版本控制
    6. 配置备份和恢复
    """
    
    def __init__(self, framework_ref: Optional[weakref.ref] = None):
        self.framework_ref = framework_ref
        
        # 配置存储
        self.plugin_configs: Dict[str, Dict[str, Any]] = {}
        self.config_files: Dict[str, ConfigFile] = {}
        self.config_watches: Dict[str, ConfigWatch] = {}
        self.config_templates: Dict[str, ConfigTemplate] = {}
        
        # 环境配置
        self.current_environment = ConfigEnvironment.DEVELOPMENT
        self.config_directories: Dict[ConfigEnvironment, Path] = {}
        
        # 监控和热加载
        self.watch_enabled = True
        self.watch_task: Optional[asyncio.Task] = None
        self.config_lock = asyncio.Lock()
        
        # 线程池
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        
        # 统计信息
        self.stats = ConfigManagerStats()
        
        # Schema验证和模板生成器
        self.schema_validator = SchemaValidator()
        self.template_generator = ConfigTemplateGenerator()
        
        # 插件类型映射
        self.plugin_type_mapping: Dict[str, PluginType] = {}
        
        # 配置管理设置
        self.config = {
            'auto_reload': True,
            'watch_interval': 5.0,
            'backup_enabled': True,
            'backup_retention_days': 7,
            'validation_strict': True,
            'environment_override': True,
            'config_file_extensions': {'.yaml', '.yml', '.json', '.toml'},
            'default_config_dir': 'config/plugins'
        }
        
        # 初始化配置目录
        self._initialize_config_directories()
        
        logger.info("PluginConfigManager initialized")
    
    def _initialize_config_directories(self):
        """初始化配置目录"""
        base_dir = Path(self.config['default_config_dir'])
        
        self.config_directories = {
            ConfigEnvironment.DEVELOPMENT: base_dir / "development",
            ConfigEnvironment.TESTING: base_dir / "testing",
            ConfigEnvironment.STAGING: base_dir / "staging",
            ConfigEnvironment.PRODUCTION: base_dir / "production"
        }
        
        # 创建目录
        for env_dir in self.config_directories.values():
            env_dir.mkdir(parents=True, exist_ok=True)
    
    async def initialize(self):
        """初始化配置管理器"""
        try:
            logger.info("Initializing PluginConfigManager...")
            
            # 设置当前环境
            env_name = os.getenv('PLUGIN_ENV', 'development').lower()
            try:
                self.current_environment = ConfigEnvironment(env_name)
            except ValueError:
                logger.warning(f"Invalid environment '{env_name}', using development")
                self.current_environment = ConfigEnvironment.DEVELOPMENT
            
            # 加载配置模板
            await self._load_config_templates()
            
            # 生成默认配置模板文件
            await self._generate_default_templates()
            
            # 启动配置监控
            if self.config['auto_reload']:
                await self._start_config_watching()
            
            logger.info(f"PluginConfigManager initialized for environment: {self.current_environment.value}")
            
        except Exception as e:
            logger.error(f"Failed to initialize PluginConfigManager: {e}")
            raise
    
    async def load_plugin_config(self, plugin_id: str,
                                plugin_type: Optional[PluginType] = None,
                                config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """
        加载插件配置
        
        Args:
            plugin_id: 插件ID
            plugin_type: 插件类型（用于schema验证）
            config_path: 配置文件路径（可选，如果未指定则自动查找）
            
        Returns:
            Dict[str, Any]: 插件配置
        """
        async with self.config_lock:
            start_time = time.time()
            
            try:
                # 确定配置文件路径
                if config_path:
                    config_file_path = Path(config_path)
                else:
                    config_file_path = await self._find_config_file(plugin_id)
                
                # 如果没有找到配置文件，使用默认配置
                if not config_file_path or not config_file_path.exists():
                    if plugin_type:
                        logger.info(f"Config file not found for plugin {plugin_id}, using default config")
                        default_config = get_plugin_default_config(plugin_type)
                        self.plugin_configs[plugin_id] = default_config
                        self.plugin_type_mapping[plugin_id] = plugin_type
                        return default_config
                    else:
                        logger.warning(f"Config file not found for plugin {plugin_id} and no plugin_type specified")
                        return {}
                
                # 加载配置内容
                config_content = await self._load_config_file(config_file_path)
                
                # 处理环境变量替换
                config_content = self._resolve_environment_variables(config_content)
                
                # Schema验证配置
                if self.config['validation_strict'] and plugin_type:
                    validation_result = await self._validate_plugin_config_with_schema(plugin_type, config_content)
                    if validation_result['valid']:
                        config_content = validation_result['normalized_config']
                        logger.info(f"Plugin config validated successfully for {plugin_id}")
                    else:
                        logger.warning(f"Plugin config validation failed for {plugin_id}: {validation_result['errors']}")
                elif not plugin_type:
                    # 传统验证方式
                    await self._validate_plugin_config(plugin_id, config_content)
                
                # 创建配置文件信息
                config_file = ConfigFile(
                    path=config_file_path,
                    format=self._detect_config_format(config_file_path),
                    environment=self.current_environment,
                    plugin_id=plugin_id
                )
                config_file.update_info()
                
                # 存储配置
                self.plugin_configs[plugin_id] = config_content
                self.config_files[plugin_id] = config_file
                if plugin_type:
                    self.plugin_type_mapping[plugin_id] = plugin_type
                
                # 设置监控
                if self.config['auto_reload']:
                    await self._setup_config_watch(plugin_id, config_file)
                
                # 更新统计
                load_time = time.time() - start_time
                self.stats.update_load_stats(True, load_time)
                
                logger.info(f"Plugin config loaded for {plugin_id} in {load_time:.3f}s")
                return config_content.copy()
                
            except Exception as e:
                # 更新统计
                load_time = time.time() - start_time
                self.stats.update_load_stats(False, load_time)
                
                logger.error(f"Failed to load plugin config for {plugin_id}: {e}")
                return {}
    
    async def save_plugin_config(self, plugin_id: str, 
                                config: Dict[str, Any],
                                create_backup: bool = True) -> bool:
        """
        保存插件配置
        
        Args:
            plugin_id: 插件ID
            config: 配置内容
            create_backup: 是否创建备份
            
        Returns:
            bool: 保存是否成功
        """
        async with self.config_lock:
            try:
                # 获取配置文件信息
                config_file = self.config_files.get(plugin_id)
                if not config_file:
                    # 创建新的配置文件
                    config_file = await self._create_config_file(plugin_id)
                
                # 创建备份
                if create_backup and self.config['backup_enabled']:
                    await self._create_config_backup(config_file)
                
                # 验证配置
                if self.config['validation_strict']:
                    await self._validate_plugin_config(plugin_id, config)
                
                # 保存配置文件
                await self._save_config_file(config_file.path, config, config_file.format)
                
                # 更新内存中的配置
                self.plugin_configs[plugin_id] = config.copy()
                config_file.update_info()
                
                logger.info(f"Plugin config saved for {plugin_id}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to save plugin config for {plugin_id}: {e}")
                return False
    
    async def reload_plugin_config(self, plugin_id: str) -> bool:
        """
        重新加载插件配置
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            bool: 重新加载是否成功
        """
        try:
            logger.info(f"Reloading config for plugin {plugin_id}")
            
            # 重新加载配置
            new_config = await self.load_plugin_config(plugin_id)
            if not new_config:
                return False
            
            # 通知插件配置变更
            if self.framework_ref and self.framework_ref():
                framework = self.framework_ref()
                plugin = await framework.get_plugin(plugin_id)
                if plugin:
                    await plugin.reload_config(new_config)
            
            self.stats.hot_reloads += 1
            logger.info(f"Plugin config reloaded for {plugin_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reload plugin config for {plugin_id}: {e}")
            return False
    
    async def get_plugin_config(self, plugin_id: str, 
                              key: Optional[str] = None,
                              default: Any = None) -> Any:
        """
        获取插件配置
        
        Args:
            plugin_id: 插件ID
            key: 配置键（可选，支持点号分隔的嵌套键）
            default: 默认值
            
        Returns:
            Any: 配置值
        """
        config = self.plugin_configs.get(plugin_id, {})
        
        if key is None:
            return config.copy()
        
        # 支持嵌套键访问
        keys = key.split('.')
        value = config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    async def update_plugin_config(self, plugin_id: str, 
                                 key: str, 
                                 value: Any,
                                 save_immediately: bool = True) -> bool:
        """
        更新插件配置
        
        Args:
            plugin_id: 插件ID
            key: 配置键
            value: 配置值
            save_immediately: 是否立即保存
            
        Returns:
            bool: 更新是否成功
        """
        try:
            config = self.plugin_configs.get(plugin_id, {}).copy()
            
            # 支持嵌套键设置
            keys = key.split('.')
            current = config
            
            for k in keys[:-1]:
                if k not in current:
                    current[k] = {}
                current = current[k]
            
            current[keys[-1]] = value
            
            # 更新内存配置
            self.plugin_configs[plugin_id] = config
            
            # 立即保存
            if save_immediately:
                await self.save_plugin_config(plugin_id, config)
            
            logger.info(f"Plugin config updated for {plugin_id}: {key} = {value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update plugin config for {plugin_id}: {e}")
            return False
    
    async def register_config_template(self, template: ConfigTemplate) -> bool:
        """注册配置模板"""
        try:
            self.config_templates[template.template_id] = template
            logger.info(f"Config template registered: {template.template_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to register config template: {e}")
            return False
    
    async def create_config_from_template(self, plugin_id: str, 
                                        template_id: str,
                                        custom_values: Dict[str, Any] = None) -> bool:
        """从模板创建配置"""
        try:
            template = self.config_templates.get(template_id)
            if not template:
                logger.error(f"Config template not found: {template_id}")
                return False
            
            # 创建配置
            config = template.default_values.copy()
            if custom_values:
                config.update(custom_values)
            
            # 保存配置
            return await self.save_plugin_config(plugin_id, config)
            
        except Exception as e:
            logger.error(f"Failed to create config from template: {e}")
            return False
    
    async def _find_config_file(self, plugin_id: str) -> Optional[Path]:
        """查找插件配置文件"""
        # 当前环境目录
        env_dir = self.config_directories[self.current_environment]
        
        # 尝试多种文件名格式
        possible_names = [
            f"{plugin_id}.yaml",
            f"{plugin_id}.yml",
            f"{plugin_id}.json",
            f"{plugin_id}.toml",
            f"{plugin_id}_config.yaml",
            f"{plugin_id}_config.yml",
            f"{plugin_id}_config.json"
        ]
        
        for name in possible_names:
            config_path = env_dir / name
            if config_path.exists():
                return config_path
        
        return None
    
    async def _load_config_file(self, file_path: Path) -> Dict[str, Any]:
        """加载配置文件"""
        def _load():
            format = self._detect_config_format(file_path)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                if format == ConfigFormat.YAML:
                    return yaml.safe_load(f) or {}
                elif format == ConfigFormat.JSON:
                    return json.load(f) or {}
                elif format == ConfigFormat.TOML:
                    import tomli
                    content = f.read()
                    return tomli.loads(content) or {}
                else:
                    raise ValueError(f"Unsupported config format: {format}")
        
        return await asyncio.get_event_loop().run_in_executor(
            self.thread_pool, _load
        )
    
    async def _save_config_file(self, file_path: Path, 
                              config: Dict[str, Any],
                              format: ConfigFormat):
        """保存配置文件"""
        def _save():
            with open(file_path, 'w', encoding='utf-8') as f:
                if format == ConfigFormat.YAML:
                    yaml.dump(config, f, default_flow_style=False, indent=2)
                elif format == ConfigFormat.JSON:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                elif format == ConfigFormat.TOML:
                    import tomli_w
                    tomli_w.dump(config, f)
                else:
                    raise ValueError(f"Unsupported config format: {format}")
        
        await asyncio.get_event_loop().run_in_executor(
            self.thread_pool, _save
        )
    
    def _detect_config_format(self, file_path: Path) -> ConfigFormat:
        """检测配置文件格式"""
        suffix = file_path.suffix.lower()
        
        if suffix in ['.yaml', '.yml']:
            return ConfigFormat.YAML
        elif suffix == '.json':
            return ConfigFormat.JSON
        elif suffix == '.toml':
            return ConfigFormat.TOML
        else:
            # 默认使用YAML
            return ConfigFormat.YAML
    
    def _resolve_environment_variables(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """解析环境变量"""
        def _resolve_value(value):
            if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                env_var = value[2:-1]
                # 支持默认值语法: ${VAR_NAME:default_value}
                if ':' in env_var:
                    var_name, default = env_var.split(':', 1)
                    return os.getenv(var_name, default)
                else:
                    return os.getenv(env_var, value)
            elif isinstance(value, dict):
                return {k: _resolve_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [_resolve_value(item) for item in value]
            else:
                return value
        
        return _resolve_value(config)
    
    async def _validate_plugin_config_with_schema(self, plugin_type: PluginType, config: Dict[str, Any]) -> Dict[str, Any]:
        """使用schema验证插件配置"""
        start_time = time.time()
        
        try:
            validation_result = validate_plugin_config(plugin_type, config)
            
            self.stats.schema_validations += 1
            
            # 更新验证时间统计
            validation_time = time.time() - start_time
            if self.stats.schema_validations > 0:
                current_total = self.stats.average_validation_time * (self.stats.schema_validations - 1)
                self.stats.average_validation_time = (current_total + validation_time) / self.stats.schema_validations
            
            if not validation_result['valid']:
                self.stats.validation_errors += 1
                
            return validation_result
                
        except Exception as e:
            self.stats.validation_errors += 1
            return {
                'valid': False,
                'errors': [{'message': str(e)}],
                'warnings': [],
                'normalized_config': config
            }
    
    async def _validate_plugin_config(self, plugin_id: str, config: Dict[str, Any]):
        """验证插件配置（传统方式）"""
        start_time = time.time()
        
        try:
            # 尝试找到对应的配置模板
            template = None
            for t in self.config_templates.values():
                if plugin_id.startswith(t.plugin_type.value):
                    template = t
                    break
            
            if template and template.schema:
                validate(instance=config, schema=template.schema)
                
                # 检查必需字段
                for required_field in template.required_fields:
                    if required_field not in config:
                        raise ValidationError(f"Required field missing: {required_field}")
            
            self.stats.schema_validations += 1
            
            # 更新验证时间统计
            validation_time = time.time() - start_time
            if self.stats.schema_validations > 0:
                current_total = self.stats.average_validation_time * (self.stats.schema_validations - 1)
                self.stats.average_validation_time = (current_total + validation_time) / self.stats.schema_validations
                
        except ValidationError as e:
            self.stats.validation_errors += 1
            raise ValueError(f"Config validation failed: {e.message}")
    
    async def _create_config_file(self, plugin_id: str) -> ConfigFile:
        """创建新的配置文件"""
        env_dir = self.config_directories[self.current_environment]
        config_path = env_dir / f"{plugin_id}.yaml"
        
        config_file = ConfigFile(
            path=config_path,
            format=ConfigFormat.YAML,
            environment=self.current_environment,
            plugin_id=plugin_id
        )
        
        self.config_files[plugin_id] = config_file
        return config_file
    
    async def _create_config_backup(self, config_file: ConfigFile):
        """创建配置备份"""
        if not config_file.path.exists():
            return
        
        try:
            backup_dir = config_file.path.parent / "backups"
            backup_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{config_file.path.stem}_{timestamp}{config_file.path.suffix}"
            backup_path = backup_dir / backup_name
            
            shutil.copy2(config_file.path, backup_path)
            
            # 清理旧备份
            await self._cleanup_old_backups(backup_dir, config_file.path.stem)
            
            self.stats.backup_operations += 1
            logger.debug(f"Config backup created: {backup_path}")
            
        except Exception as e:
            logger.warning(f"Failed to create config backup: {e}")
    
    async def _cleanup_old_backups(self, backup_dir: Path, prefix: str):
        """清理旧备份文件"""
        try:
            retention_days = self.config['backup_retention_days']
            cutoff_time = datetime.now() - timedelta(days=retention_days)
            
            for backup_file in backup_dir.glob(f"{prefix}_*"):
                stat = backup_file.stat()
                if datetime.fromtimestamp(stat.st_mtime) < cutoff_time:
                    backup_file.unlink()
                    logger.debug(f"Old backup removed: {backup_file}")
                    
        except Exception as e:
            logger.warning(f"Failed to cleanup old backups: {e}")
    
    async def _setup_config_watch(self, plugin_id: str, config_file: ConfigFile):
        """设置配置文件监控"""
        async def config_change_callback(new_config: Dict[str, Any]):
            await self.reload_plugin_config(plugin_id)
        
        watch = ConfigWatch(
            config_file=config_file,
            callback=config_change_callback,
            check_interval=self.config['watch_interval']
        )
        
        self.config_watches[plugin_id] = watch
    
    async def _start_config_watching(self):
        """启动配置文件监控"""
        if self.watch_task is None or self.watch_task.done():
            self.watch_task = asyncio.create_task(self._config_watch_loop())
    
    async def _config_watch_loop(self):
        """配置文件监控循环"""
        while self.watch_enabled:
            try:
                await asyncio.sleep(1.0)  # 每秒检查一次
                
                for plugin_id, watch in self.config_watches.items():
                    if not watch.enabled:
                        continue
                    
                    # 检查是否需要检查
                    now = datetime.now()
                    if (now - watch.last_check).total_seconds() < watch.check_interval:
                        continue
                    
                    # 检查文件是否修改
                    if watch.config_file.is_modified():
                        logger.info(f"Config file changed for plugin {plugin_id}")
                        await watch.callback({})
                        watch.config_file.update_info()
                    
                    watch.last_check = now
                    
            except Exception as e:
                logger.error(f"Config watch loop error: {e}")
                await asyncio.sleep(5.0)  # 错误时等待更长时间
    
    async def _load_config_templates(self):
        """加载配置模板"""
        # 从schemas模块加载预定义的模板
        try:
            # 为每个插件类型创建配置模板
            for plugin_type, schema in PLUGIN_SCHEMAS.items():
                if plugin_type == "framework":
                    continue
                    
                metadata = SCHEMA_METADATA.get(plugin_type)
                if not metadata:
                    continue
                
                # 提取默认值
                default_values = {}
                properties = schema.get('properties', {})
                for key, prop in properties.items():
                    if 'default' in prop:
                        default_values[key] = prop['default']
                
                # 提取必需字段
                required_fields = schema.get('required', [])
                
                template = ConfigTemplate(
                    template_id=plugin_type.value,
                    plugin_type=plugin_type,
                    schema=schema,
                    default_values=default_values,
                    required_fields=required_fields,
                    description=metadata.description
                )
                
                await self.register_config_template(template)
                
            logger.info("Loaded config templates from schemas module")
            
        except Exception as e:
            logger.error(f"Failed to load config templates: {e}")
            # Fallback to basic templates
            await self._load_fallback_templates()
    
    async def _load_fallback_templates(self):
        """加载回退配置模板"""
        # 会话管理插件模板
        session_template = ConfigTemplate(
            template_id="session_management",
            plugin_type=PluginType.SESSION_MANAGEMENT,
            schema={
                "type": "object",
                "properties": {
                    "max_sessions": {"type": "integer", "minimum": 1},
                    "session_timeout": {"type": "number", "minimum": 0},
                    "pool_size": {"type": "integer", "minimum": 1}
                }
            },
            default_values={
                "max_sessions": 10,
                "session_timeout": 1800,
                "pool_size": 5
            },
            required_fields=["max_sessions"]
        )
        
        await self.register_config_template(session_template)
    
    async def _generate_default_templates(self):
        """生成默认配置模板文件"""
        try:
            templates_dir = self.config_directories[self.current_environment] / "templates"
            templates_dir.mkdir(exist_ok=True)
            
            # 为每个插件类型生成模板文件
            for plugin_type in PLUGIN_SCHEMAS.keys():
                if plugin_type == "framework":
                    template_filename = "framework_config.yaml"
                else:
                    template_filename = f"{plugin_type.value}_config.yaml"
                
                template_path = templates_dir / template_filename
                
                # 只在文件不存在时生成
                if not template_path.exists():
                    template_content = generate_plugin_template(plugin_type, format='yaml')
                    
                    with open(template_path, 'w', encoding='utf-8') as f:
                        f.write(template_content)
                    
                    logger.debug(f"Generated config template: {template_path}")
            
            logger.info(f"Default config templates generated in: {templates_dir}")
            
        except Exception as e:
            logger.warning(f"Failed to generate default templates: {e}")
    
    def get_plugin_configs(self) -> Dict[str, Dict[str, Any]]:
        """获取所有插件配置"""
        return {k: v.copy() for k, v in self.plugin_configs.items()}
    
    def get_config_files_info(self) -> Dict[str, Dict[str, Any]]:
        """获取配置文件信息"""
        return {
            plugin_id: {
                'path': str(config_file.path),
                'format': config_file.format.value,
                'environment': config_file.environment.value,
                'last_modified': config_file.last_modified.isoformat() if config_file.last_modified else None,
                'checksum': config_file.checksum,
                'version': config_file.version
            }
            for plugin_id, config_file in self.config_files.items()
        }
    
    def get_config_stats(self) -> Dict[str, Any]:
        """获取配置管理统计信息"""
        return {
            'total_configs': self.stats.total_configs,
            'loaded_configs': self.stats.loaded_configs,
            'failed_configs': self.stats.failed_configs,
            'hot_reloads': self.stats.hot_reloads,
            'validation_errors': self.stats.validation_errors,
            'schema_validations': self.stats.schema_validations,
            'backup_operations': self.stats.backup_operations,
            'average_load_time': self.stats.average_load_time,
            'average_validation_time': self.stats.average_validation_time,
            'current_environment': self.current_environment.value,
            'watch_enabled': self.watch_enabled,
            'config_templates': len(self.config_templates),
            'active_watches': len([w for w in self.config_watches.values() if w.enabled]),
            'schema_validator_available': self.schema_validator.validator_available,
            'supported_plugin_types': len(PLUGIN_SCHEMAS)
        }
    
    def get_plugin_validation_status(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """获取插件配置验证状态"""
        plugin_type = self.plugin_type_mapping.get(plugin_id)
        if not plugin_type:
            return None
        
        config = self.plugin_configs.get(plugin_id, {})
        validation_result = validate_plugin_config(plugin_type, config)
        
        return {
            'plugin_id': plugin_id,
            'plugin_type': plugin_type.value,
            'valid': validation_result['valid'],
            'errors': validation_result['errors'],
            'warnings': validation_result['warnings'],
            'last_validated': datetime.now().isoformat()
        }
    
    async def generate_config_template_file(self, plugin_type: PluginType,
                                          output_path: Optional[Path] = None,
                                          format: str = 'yaml') -> Path:
        """生成插件配置模板文件"""
        if output_path is None:
            templates_dir = self.config_directories[self.current_environment] / "templates"
            templates_dir.mkdir(exist_ok=True)
            
            if plugin_type == "framework":
                filename = f"framework_config.{format}"
            else:
                filename = f"{plugin_type.value}_config.{format}"
            
            output_path = templates_dir / filename
        
        # 生成模板内容
        template_content = self.template_generator.generate_template(plugin_type, format)
        
        # 写入文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(template_content)
        
        logger.info(f"Generated config template file: {output_path}")
        return output_path
    
    async def validate_all_configs(self) -> Dict[str, Dict[str, Any]]:
        """验证所有已加载的配置"""
        validation_results = {}
        
        for plugin_id, config in self.plugin_configs.items():
            plugin_type = self.plugin_type_mapping.get(plugin_id)
            if plugin_type:
                validation_result = await self._validate_plugin_config_with_schema(plugin_type, config)
                validation_results[plugin_id] = {
                    'plugin_type': plugin_type.value,
                    'valid': validation_result['valid'],
                    'errors': validation_result['errors'],
                    'warnings': validation_result['warnings']
                }
            else:
                validation_results[plugin_id] = {
                    'plugin_type': 'unknown',
                    'valid': None,
                    'errors': ['Plugin type not registered'],
                    'warnings': []
                }
        
        return validation_results
    
    async def stop(self):
        """停止配置管理器"""
        try:
            logger.info("Stopping PluginConfigManager...")
            
            # 停止监控
            self.watch_enabled = False
            if self.watch_task:
                self.watch_task.cancel()
                try:
                    await self.watch_task
                except asyncio.CancelledError:
                    pass
            
            # 关闭线程池
            self.thread_pool.shutdown(wait=False)
            
            # 清理资源
            self.config_watches.clear()
            
            logger.info("PluginConfigManager stopped")
            
        except Exception as e:
            logger.error(f"Failed to stop PluginConfigManager: {e}")
            raise


# 全局配置管理器实例
_global_config_manager: Optional[PluginConfigManager] = None

def get_config_manager() -> PluginConfigManager:
    """获取全局配置管理器实例"""
    global _global_config_manager
    if _global_config_manager is None:
        _global_config_manager = PluginConfigManager()
    return _global_config_manager