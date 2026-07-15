"""
系统配置模块

该模块定义了系统的各种配置参数。
包含数据库、API、缓存、日志等配置。

主要配置类：
- LLMConfig: LLM服务配置
- ToolConfig: 工具配置
- CostTrackingConfig: 成本跟踪配置
- CacheConfig: 缓存配置
- ScraperConfig: 爬虫配置
- LogConfig: 日志配置
- DatabaseConfig: 数据库配置
- APIConfig: API配置
- Settings: 主配置类

Author: Mercari AI Agent Team
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union, Any
from pathlib import Path


@dataclass
class LLMConfig:
    """LLM服务配置"""
    # OpenAI配置
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_base_url: Optional[str] = None  # 添加缺少的属性
    openai_model: str = "gpt-4o-mini"
    openai_temperature: float = 0.7
    openai_max_tokens: int = 2000
    openai_timeout: int = 30
    
    # Anthropic配置
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    anthropic_model: str = "claude-3.5-sonnet-20241022"
    anthropic_temperature: float = 0.7
    anthropic_max_tokens: int = 2000
    anthropic_timeout: int = 30
    
    # Azure配置
    azure_endpoint: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_ENDPOINT", ""))
    azure_api_key: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_API_KEY", ""))
    azure_api_version: str = "2023-12-01-preview"
    azure_deployment: str = "gpt-4o-mini"
    
    # 通用配置
    default_provider: str = "openai"  # openai, anthropic, azure
    max_retries: int = 3
    retry_delay: float = 1.0
    enable_fallback: bool = True
    fallback_order: List[str] = field(default_factory=lambda: ["openai", "anthropic", "azure"])
    
    # 请求配置
    request_timeout: int = 60
    concurrent_requests: int = 5
    rate_limit_requests: int = 100
    rate_limit_window: int = 60
    
    # 新增配置
    enable_caching: bool = True
    enable_cost_tracking: bool = True
    enable_streaming: bool = True
    
    def get_provider_config(self, provider: str) -> Dict:
        """获取指定提供商的配置"""
        if provider == "openai":
            return {
                "api_key": self.openai_api_key,
                "model": self.openai_model,
                "temperature": self.openai_temperature,
                "max_tokens": self.openai_max_tokens,
                "timeout": self.openai_timeout
            }
        elif provider == "anthropic":
            return {
                "api_key": self.anthropic_api_key,
                "model": self.anthropic_model,
                "temperature": self.anthropic_temperature,
                "max_tokens": self.anthropic_max_tokens,
                "timeout": self.anthropic_timeout
            }
        elif provider == "azure":
            return {
                "api_key": self.azure_api_key,
                "endpoint": self.azure_endpoint,
                "api_version": self.azure_api_version,
                "deployment": self.azure_deployment,
                "timeout": self.openai_timeout
            }
        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    def is_provider_available(self, provider: str) -> bool:
        """检查提供商是否可用"""
        config = self.get_provider_config(provider)
        if provider == "azure":
            return bool(config.get("api_key")) and bool(config.get("endpoint"))
        else:
            return bool(config.get("api_key"))


@dataclass
class ToolConfig:
    """工具调用配置"""
    # 工具调用超时
    tool_timeout: int = 30
    max_tool_iterations: int = 5
    
    # 工具缓存
    enable_tool_cache: bool = True
    tool_cache_ttl: int = 3600
    
    # 工具执行
    max_concurrent_tools: int = 3
    tool_retry_count: int = 2
    tool_retry_delay: float = 1.0
    
    # 工具发现
    auto_register_tools: bool = True
    tool_discovery_paths: List[str] = field(default_factory=lambda: [
        "mercari_agent.core.tools.search_tools",
        "mercari_agent.core.tools.analysis_tools", 
        "mercari_agent.core.tools.formatting_tools"
    ])
    
    # 工具安全
    enable_tool_sandboxing: bool = True
    allowed_tool_categories: List[str] = field(default_factory=lambda: [
        "search", "analysis", "formatting"
    ])
    
    # 工具监控
    enable_tool_metrics: bool = True
    tool_metrics_interval: int = 60


@dataclass
class CostTrackingConfig:
    """成本跟踪配置"""
    # 启用成本跟踪
    enable_cost_tracking: bool = True
    
    # 成本预警
    daily_cost_limit: float = 50.0  # USD
    monthly_cost_limit: float = 1000.0  # USD
    cost_alert_threshold: float = 0.8  # 80%
    
    # 成本优化
    enable_cost_optimization: bool = True
    prefer_cheaper_models: bool = True
    
    # 成本报告
    cost_report_interval: int = 3600  # 1小时
    enable_cost_alerts: bool = True
    cost_alert_email: str = ""
    
    # 定价信息更新
    pricing_update_interval: int = 86400  # 24小时
    pricing_api_endpoint: str = ""


@dataclass
class CacheConfig:
    """缓存配置"""
    # 启用缓存
    enable_memory_cache: bool = True
    enable_disk_cache: bool = True
    enable_redis_cache: bool = False
    
    # 内存缓存配置
    memory_cache_size: int = 1000
    memory_cache_ttl: int = 3600
    
    # 磁盘缓存配置
    disk_cache_dir: str = "./cache"
    disk_cache_size: int = 104857600  # 100MB
    disk_cache_ttl: int = 86400  # 24小时
    
    # Redis配置
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    redis_ttl: int = 3600
    
    # 缓存策略
    cache_strategy: str = "lru"
    max_cache_size: int = 10000
    
    # 缓存键配置
    key_prefix: str = "mercari_agent"
    key_separator: str = ":"
    
    # 清理配置
    auto_cleanup: bool = True
    cleanup_interval: int = 3600


@dataclass
class ScraperConfig:
    """爬虫配置"""
    # 请求配置
    user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # 并发配置
    max_concurrent_requests: int = 10
    max_requests_per_host: int = 30
    rate_limit_delay: float = 0.5
    max_requests_per_minute: int = 30
    
    # 请求间隔配置
    REQUEST_INTERVALS: Dict[str, float] = field(default_factory=lambda: {
        "requests": 1.0,
        "selenium": 2.0,
        "playwright": 1.5,
        "hybrid": 1.0
    })
    
    # 反爬虫配置
    enable_proxy: bool = False
    proxy_list: List[str] = field(default_factory=list)
    proxy_rotation: bool = True
    rotate_user_agents: bool = True
    
    # 会话配置
    session_pool_size: int = 5
    session_timeout: int = 300
    max_sessions: int = 5
    
    # 浏览器配置
    headless: bool = True
    browser_timeout: int = 30
    page_load_timeout: int = 20
    enable_javascript: bool = True
    
    # 缓存配置
    enable_cache: bool = True
    cache_ttl: int = 3600
    
    # Mercari特定配置
    mercari_base_url: str = "https://jp.mercari.com"
    mercari_search_url: str = "https://jp.mercari.com/search"
    mercari_api_url: str = "https://api.mercari.jp/v2"
    
    # 页面配置
    max_pages: int = 10
    items_per_page: int = 48
    
    # 反爬虫检测配置
    enable_anti_bot_detection: bool = True
    detection_threshold: float = 0.7
    enable_ml_detection: bool = True
    ml_model_path: str = "./data/bot_detection_model.pkl"
    
    # 浏览器引擎配置
    preferred_browser_engine: str = "playwright"  # playwright, selenium
    enable_browser_engine: bool = True
    browser_pool_size: int = 2
    
    # 数据解析配置
    enable_data_validation: bool = True
    enable_data_cleaning: bool = True
    max_content_length: int = 1048576  # 1MB
    
    # 指纹伪装配置
    enable_fingerprint_spoofing: bool = True
    canvas_fingerprint_enabled: bool = True
    webgl_fingerprint_enabled: bool = True
    
    # 请求间隔配置
    min_request_interval: float = 2.0
    max_request_interval: float = 5.0
    adaptive_interval: bool = True
    
    # 错误处理配置
    max_consecutive_errors: int = 5
    error_backoff_factor: float = 2.0
    max_backoff_time: int = 60
    
    # 数据持久化配置
    enable_cookie_persistence: bool = True
    cookie_file_path: str = "./data/cookies.json"
    
    # 监控配置
    enable_performance_monitoring: bool = True
    enable_error_tracking: bool = True
    
    # 内容过滤配置
    enable_content_filtering: bool = True
    min_content_quality_score: float = 0.3
    
    # 图片处理配置
    enable_image_processing: bool = True
    image_quality_threshold: float = 0.5
    max_image_size: int = 10485760  # 10MB


@dataclass
class LogConfig:
    """日志配置"""
    # 基本配置
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # 文件配置
    log_dir: str = "./logs"
    log_file: str = "mercari_agent.log"
    max_file_size: int = 10485760  # 10MB
    backup_count: int = 5
    
    # 控制台配置
    console_output: bool = True
    console_level: str = "INFO"
    
    # 结构化日志
    enable_json_logging: bool = True
    include_traceback: bool = True
    
    # 性能日志
    enable_performance_logging: bool = True
    slow_query_threshold: float = 1.0


@dataclass
class DatabaseConfig:
    """数据库配置"""
    # SQLite配置
    sqlite_path: str = "./data/mercari_agent.db"
    sqlite_timeout: int = 30
    
    # PostgreSQL配置
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "mercari_agent"
    postgres_password: str = field(default_factory=lambda: os.getenv("POSTGRES_PASSWORD", ""))
    postgres_database: str = "mercari_agent"
    
    # 连接池配置
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    
    # 数据库类型
    database_type: str = "sqlite"
    
    # 迁移配置
    enable_auto_migration: bool = True
    migration_dir: str = "./migrations"


@dataclass
class APIConfig:
    """API配置"""
    # 服务器配置
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    # 认证配置
    enable_auth: bool = False
    secret_key: str = field(default_factory=lambda: os.getenv("SECRET_KEY", "dev-secret-key"))
    access_token_expire: int = 3600
    
    # CORS配置
    enable_cors: bool = True
    cors_origins: List[str] = field(default_factory=lambda: ["*"])
    
    # 限流配置
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_window: int = 60
    
    # 文档配置
    enable_docs: bool = True
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    
    # 中间件配置
    enable_gzip: bool = True
    enable_request_logging: bool = True
    
    # 上传配置
    max_file_size: int = 10485760  # 10MB
    allowed_file_types: List[str] = field(default_factory=lambda: [".txt", ".json", ".csv"])


@dataclass
class Settings:
    """主配置类"""
    # 应用基本信息
    app_name: str = "Mercari AI Agent"
    app_version: str = "1.0.0"
    app_description: str = "Mercari日本智能购物AI代理系统"
    environment: str = "development"
    debug: bool = False
    
    # 数据目录
    data_dir: str = "./data"
    temp_dir: str = "./temp"
    config_dir: str = "./config"
    
    # 性能配置
    max_workers: int = 4
    max_memory_usage: int = 1073741824  # 1GB
    
    # 国际化配置
    default_language: str = "ja"
    supported_languages: List[str] = field(default_factory=lambda: ["ja", "en", "zh"])
    
    # 特性开关
    enable_features: Dict[str, bool] = field(default_factory=lambda: {
        "advanced_analysis": True,
        "market_trend": True,
        "price_prediction": True,
        "seller_verification": True,
        "image_analysis": False,
        "recommendation_learning": True,
        "tool_orchestration": True,
        "cost_tracking": True,
        "prompt_optimization": True
    })
    
    # 配置组件
    llm: LLMConfig = field(default_factory=LLMConfig)
    tool: ToolConfig = field(default_factory=ToolConfig)
    cost_tracking: CostTrackingConfig = field(default_factory=CostTrackingConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    scraper: ScraperConfig = field(default_factory=ScraperConfig)
    log: LogConfig = field(default_factory=LogConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    api: APIConfig = field(default_factory=APIConfig)
    
    @property
    def DATA_DIR(self) -> str:
        """向后兼容的DATA_DIR属性"""
        return self.data_dir
    
    @property
    def CONFIG_DIR(self) -> str:
        """向后兼容的CONFIG_DIR属性"""
        return self.config_dir
    
    @property
    def REQUEST_INTERVALS(self) -> Dict[str, float]:
        """向后兼容的REQUEST_INTERVALS属性"""
        return self.scraper.REQUEST_INTERVALS
    
    @classmethod
    def from_yaml(cls, config_file: str) -> "Settings":
        """从YAML文件加载配置"""
        import yaml
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        # 展开环境变量
        config_data = cls._expand_env_vars(config_data)
        
        # 创建嵌套的数据类对象
        llm_config = LLMConfig(**config_data.pop('llm', {}))
        tool_config = ToolConfig(**config_data.pop('tool', {}))
        cost_tracking_config = CostTrackingConfig(**config_data.pop('cost_tracking', {}))
        cache_config = CacheConfig(**config_data.pop('cache', {}))
        scraper_config = ScraperConfig(**config_data.pop('scraper', {}))
        log_config = LogConfig(**config_data.pop('log', {}))
        database_config = DatabaseConfig(**config_data.pop('database', {}))
        api_config = APIConfig(**config_data.pop('api', {}))
        
        # 创建配置实例
        return cls(
            llm=llm_config,
            tool=tool_config,
            cost_tracking=cost_tracking_config,
            cache=cache_config,
            scraper=scraper_config,
            log=log_config,
            database=database_config,
            api=api_config,
            **config_data
        )
    
    @staticmethod
    def _expand_env_vars(data):
        """递归展开环境变量"""
        if isinstance(data, dict):
            return {k: Settings._expand_env_vars(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [Settings._expand_env_vars(item) for item in data]
        elif isinstance(data, str) and data.startswith("${") and data.endswith("}"):
            env_var = data[2:-1]
            return os.getenv(env_var, "")
        return data
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        from dataclasses import asdict
        return asdict(self)
    
    def validate(self) -> List[str]:
        """验证配置"""
        errors = []
        
        # 验证LLM配置
        if not any([self.llm.openai_api_key, self.llm.anthropic_api_key, self.llm.azure_api_key]):
            errors.append("至少需要配置一个LLM提供商的API密钥")
        
        # 验证目录
        for dir_path in [self.data_dir, self.temp_dir, self.config_dir, self.log.log_dir]:
            if not os.path.exists(dir_path):
                try:
                    os.makedirs(dir_path, exist_ok=True)
                except Exception as e:
                    errors.append(f"无法创建目录 {dir_path}: {e}")
        
        # 验证成本限制
        if self.cost_tracking.enable_cost_tracking:
            if self.cost_tracking.daily_cost_limit <= 0:
                errors.append("日成本限制必须大于0")
            if self.cost_tracking.monthly_cost_limit <= 0:
                errors.append("月成本限制必须大于0")
        
        return errors


# 全局配置实例
def load_settings() -> Settings:
    """加载配置"""
    config_file = os.getenv("CONFIG_FILE", "config/development.yaml")
    
    if os.path.exists(config_file):
        try:
            return Settings.from_yaml(config_file)
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            print("使用默认配置")
    
    return Settings()


# 全局配置实例
settings = load_settings()

# 验证配置
config_errors = settings.validate()
if config_errors:
    print("配置验证失败:")
    for error in config_errors:
        print(f"  - {error}")
else:
    print("配置验证成功")