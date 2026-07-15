"""
应用配置模块

该模块负责管理应用的配置信息，包括环境变量、数据库连接、LLM服务配置等。
支持多环境配置和配置验证。

主要功能：
- 环境变量加载和验证
- 多环境配置支持
- 配置项验证
- 敏感信息保护

Author: Mercari AI Agent Team (Refactored)
"""

import os
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path

from ..exceptions.config_exceptions import ConfigurationError


class Environment(Enum):
    """环境枚举"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class DatabaseConfig:
    """数据库配置"""
    sqlite_path: Optional[str] = "./data/mercari_agent.db"
    postgres_host: Optional[str] = None
    postgres_port: int = 5432
    postgres_db: Optional[str] = None
    postgres_user: Optional[str] = None
    postgres_password: Optional[str] = None
    
    def get_sqlite_path(self) -> str:
        """获取SQLite数据库路径"""
        if self.sqlite_path:
            # 确保目录存在
            db_path = Path(self.sqlite_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            return str(db_path)
        return "./data/mercari_agent.db"
    
    def get_postgres_url(self) -> Optional[str]:
        """获取PostgreSQL连接URL"""
        if all([self.postgres_host, self.postgres_db, self.postgres_user, self.postgres_password]):
            return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        return None


@dataclass
class LLMConfig:
    """LLM服务配置"""
    # OpenAI配置
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: Optional[str] = None
    
    # Anthropic配置
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    anthropic_base_url: Optional[str] = None
    
    # Azure OpenAI配置
    azure_openai_api_key: Optional[str] = None
    azure_openai_endpoint: Optional[str] = None
    azure_openai_deployment: str = "gpt-4"
    azure_openai_api_version: str = "2023-12-01-preview"

    # AWS Bedrock (Claude) 配置 —— 新增主 provider
    # model_id 可被 env(BEDROCK_MODEL_ID) 覆盖；不同账号开通的模型不同，务必用 env 覆盖
    # 默认 = 2026 最新 Sonnet（质量/成本均衡，支持工具调用）
    # 备选：us.anthropic.claude-haiku-4-5-20251001-v1:0（更便宜/更快）
    #      us.anthropic.claude-opus-4-7（更强/更贵，旗舰）
    bedrock_model_id: str = "us.anthropic.claude-sonnet-4-6"
    bedrock_region: str = "us-west-2"
    aws_profile: str = "sandbox-Oregon"

    # 通用配置
    max_tokens: int = 4000
    temperature: float = 0.7
    timeout: int = 30

    def has_openai_config(self) -> bool:
        """检查是否有OpenAI配置"""
        return bool(self.openai_api_key)

    def has_anthropic_config(self) -> bool:
        """检查是否有Anthropic配置"""
        return bool(self.anthropic_api_key)

    def has_azure_config(self) -> bool:
        """检查是否有Azure OpenAI配置"""
        return bool(self.azure_openai_api_key and self.azure_openai_endpoint)

    def has_bedrock_config(self) -> bool:
        """检查是否有 AWS Bedrock 配置（model_id 有值即算配好，默认 True）"""
        return bool(self.bedrock_model_id)


@dataclass
class ScrapingConfig:
    """爬虫配置"""
    max_retries: int = 3
    timeout: int = 30
    delay_range: tuple = (1, 3)
    max_pages: int = 5
    max_products: int = 50
    use_cache: bool = True
    cache_ttl: int = 300  # 5分钟
    
    # 请求配置
    concurrent_requests: int = 5
    request_interval: float = 1.0
    
    # User-Agent配置
    user_agents: List[str] = field(default_factory=lambda: [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
    ])


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_dir: str = "./logs"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    
    def get_log_dir(self) -> Path:
        """获取日志目录"""
        log_path = Path(self.log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        return log_path


@dataclass
class APIConfig:
    """API配置"""
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False
    secret_key: str = "dev-secret-key-change-in-production"
    cors_origins: List[str] = field(default_factory=lambda: ["*"])
    rate_limit: int = 100  # 每分钟请求数


class AppConfig:
    """
    应用配置类
    
    负责加载和管理应用的所有配置信息。
    支持从环境变量、配置文件等多种来源加载配置。
    """
    
    def __init__(self, environment: Optional[Environment] = None):
        """
        初始化应用配置
        
        Args:
            environment: 运行环境
        """
        self.environment = environment or self._detect_environment()
        
        # 配置组件
        self.database = DatabaseConfig()
        self.llm = LLMConfig()
        self.scraping = ScrapingConfig()
        self.logging = LoggingConfig()
        self.api = APIConfig()
        
        # 基础配置
        self.debug = False
        self.version = "2.0.0"
        self.project_name = "Mercari AI Agent"
        
        # 加载配置
        self._load_configuration()
        
        # 验证配置
        self._validate_configuration()
    
    def _detect_environment(self) -> Environment:
        """检测运行环境"""
        env_name = os.getenv("ENVIRONMENT", "development").lower()
        
        for env in Environment:
            if env.value == env_name:
                return env
        
        return Environment.DEVELOPMENT
    
    def _load_configuration(self):
        """加载配置"""
        # 1. 加载环境变量
        self._load_environment_variables()
        
        # 2. 加载配置文件
        self._load_config_file()
        
        # 3. 加载.env文件
        self._load_env_file()
    
    def _load_environment_variables(self):
        """加载环境变量"""
        # 基础配置
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        
        # 数据库配置
        self.database.sqlite_path = os.getenv("SQLITE_PATH", self.database.sqlite_path)
        self.database.postgres_host = os.getenv("POSTGRES_HOST")
        self.database.postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
        self.database.postgres_db = os.getenv("POSTGRES_DB")
        self.database.postgres_user = os.getenv("POSTGRES_USER")
        self.database.postgres_password = os.getenv("POSTGRES_PASSWORD")
        
        # LLM配置
        self.llm.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.llm.openai_model = os.getenv("OPENAI_MODEL", self.llm.openai_model)
        self.llm.openai_base_url = os.getenv("OPENAI_BASE_URL")
        
        self.llm.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.llm.anthropic_model = os.getenv("ANTHROPIC_MODEL", self.llm.anthropic_model)
        self.llm.anthropic_base_url = os.getenv("ANTHROPIC_BASE_URL")
        
        self.llm.azure_openai_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.llm.azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.llm.azure_openai_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", self.llm.azure_openai_deployment)
        self.llm.azure_openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION", self.llm.azure_openai_api_version)

        # AWS Bedrock (Claude) —— 均可被 env 覆盖
        self.llm.bedrock_model_id = os.getenv("BEDROCK_MODEL_ID", self.llm.bedrock_model_id)
        self.llm.bedrock_region = os.getenv("BEDROCK_REGION", self.llm.bedrock_region)
        self.llm.aws_profile = os.getenv("AWS_PROFILE", self.llm.aws_profile)

        # API配置
        self.api.host = os.getenv("API_HOST", self.api.host)
        self.api.port = int(os.getenv("API_PORT", str(self.api.port)))
        self.api.secret_key = os.getenv("API_SECRET_KEY", self.api.secret_key)
        
        # 日志配置
        self.logging.level = os.getenv("LOG_LEVEL", self.logging.level)
        self.logging.log_dir = os.getenv("LOG_DIR", self.logging.log_dir)
    
    def _load_config_file(self):
        """加载配置文件"""
        try:
            config_file = Path(f"config/{self.environment.value}.json")
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                # 合并配置
                self._merge_config(config_data)
                
        except Exception as e:
            # 配置文件不存在或加载失败不是致命错误
            pass
    
    def _load_env_file(self):
        """加载.env文件"""
        try:
            env_file = Path(".env")
            if env_file.exists():
                with open(env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            os.environ.setdefault(key.strip(), value.strip())
                
                # 重新加载环境变量
                self._load_environment_variables()
                
        except Exception as e:
            # .env文件不存在或加载失败不是致命错误
            pass
    
    def _merge_config(self, config_data: Dict[str, Any]):
        """合并配置数据"""
        # 这里可以实现更复杂的配置合并逻辑
        for key, value in config_data.items():
            if hasattr(self, key):
                if isinstance(value, dict):
                    # 合并字典类型的配置
                    config_obj = getattr(self, key)
                    for sub_key, sub_value in value.items():
                        if hasattr(config_obj, sub_key):
                            setattr(config_obj, sub_key, sub_value)
                else:
                    setattr(self, key, value)
    
    def _validate_configuration(self):
        """验证配置"""
        errors = []
        
        # 验证LLM配置
        if not (self.llm.has_openai_config() or 
                self.llm.has_anthropic_config() or 
                self.llm.has_azure_config()):
            errors.append("至少需要配置一个LLM提供商")
        
        # 验证API密钥长度
        if self.api.secret_key == "dev-secret-key-change-in-production" and self.environment == Environment.PRODUCTION:
            errors.append("生产环境必须设置安全的API密钥")
        
        # 验证日志级别
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.logging.level.upper() not in valid_log_levels:
            errors.append(f"无效的日志级别: {self.logging.level}")
        
        if errors:
            raise ConfigurationError(f"配置验证失败: {'; '.join(errors)}")
    
    def get_database_url(self) -> str:
        """获取数据库连接URL"""
        postgres_url = self.database.get_postgres_url()
        if postgres_url:
            return postgres_url
        return f"sqlite:///{self.database.get_sqlite_path()}"
    
    def is_development(self) -> bool:
        """是否为开发环境"""
        return self.environment == Environment.DEVELOPMENT
    
    def is_production(self) -> bool:
        """是否为生产环境"""
        return self.environment == Environment.PRODUCTION
    
    def has_openai_config(self) -> bool:
        """检查是否有OpenAI配置"""
        return self.llm.has_openai_config()
    
    def has_anthropic_config(self) -> bool:
        """检查是否有Anthropic配置"""
        return self.llm.has_anthropic_config()
    
    def has_azure_config(self) -> bool:
        """检查是否有Azure OpenAI配置"""
        return self.llm.has_azure_config()

    def has_bedrock_config(self) -> bool:
        """检查是否有 AWS Bedrock 配置"""
        return self.llm.has_bedrock_config()
    
    def get_config_dict(self) -> Dict[str, Any]:
        """获取配置字典（用于日志和调试）"""
        config_dict = {
            "environment": self.environment.value if hasattr(self.environment, 'value') else str(self.environment),
            "debug": self.debug,
            "version": self.version,
            "project_name": self.project_name,
            "database": {
                "sqlite_path": self.database.sqlite_path,
                "postgres_host": self.database.postgres_host,
                "postgres_port": self.database.postgres_port,
                "postgres_db": self.database.postgres_db,
                # 不输出敏感信息
            },
            "llm": {
                "openai_configured": self.llm.has_openai_config(),
                "anthropic_configured": self.llm.has_anthropic_config(),
                "azure_configured": self.llm.has_azure_config(),
                "bedrock_configured": self.llm.has_bedrock_config(),
                "openai_model": self.llm.openai_model,
                "anthropic_model": self.llm.anthropic_model,
                "bedrock_model_id": self.llm.bedrock_model_id,
                "bedrock_region": self.llm.bedrock_region,
                "max_tokens": self.llm.max_tokens,
                "temperature": self.llm.temperature,
            },
            "scraping": {
                "max_retries": self.scraping.max_retries,
                "timeout": self.scraping.timeout,
                "max_pages": self.scraping.max_pages,
                "max_products": self.scraping.max_products,
                "use_cache": self.scraping.use_cache,
            },
            "api": {
                "host": self.api.host,
                "port": self.api.port,
                "debug": self.api.debug,
                "rate_limit": self.api.rate_limit,
            },
            "logging": {
                "level": self.logging.level,
                "log_dir": self.logging.log_dir,
            }
        }
        return config_dict
    
    def __repr__(self) -> str:
        """字符串表示"""
        return f"AppConfig(environment={self.environment.value}, debug={self.debug})"


# 全局配置实例
_global_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """获取全局配置实例"""
    global _global_config
    if _global_config is None:
        _global_config = AppConfig()
    return _global_config


def set_config(config: AppConfig):
    """设置全局配置实例"""
    global _global_config
    _global_config = config


def create_config(environment: Optional[Environment] = None) -> AppConfig:
    """创建新的配置实例"""
    return AppConfig(environment=environment)


# 别名以兼容__init__.py中的导入
ApplicationConfig = AppConfig

# 其他配置函数
def load_application_config() -> AppConfig:
    """加载应用配置"""
    return get_config()

def get_app_config() -> AppConfig:
    """获取应用配置"""
    return get_config()

def set_app_config(config: AppConfig):
    """设置应用配置"""
    set_config(config)

def get_database_config() -> DatabaseConfig:
    """获取数据库配置"""
    return get_config().database

def get_llm_config() -> LLMConfig:
    """获取LLM配置"""
    return get_config().llm

def get_scraping_config() -> ScrapingConfig:
    """获取爬虫配置"""
    return get_config().scraping

def get_cache_config() -> dict:
    """获取缓存配置"""
    return {"enabled": True, "ttl": 300}

def get_logging_config() -> LoggingConfig:
    """获取日志配置"""
    return get_config().logging

def get_security_config() -> dict:
    """获取安全配置"""
    return {"enabled": True}

def get_monitoring_config() -> dict:
    """获取监控配置"""
    return {"enabled": True}

def is_development() -> bool:
    """是否为开发环境"""
    return get_config().is_development()

def is_production() -> bool:
    """是否为生产环境"""
    return get_config().is_production()

def is_testing() -> bool:
    """是否为测试环境"""
    return get_config().environment == Environment.TESTING

# 其他配置类
CacheConfig = dict
SecurityConfig = dict
MonitoringConfig = dict