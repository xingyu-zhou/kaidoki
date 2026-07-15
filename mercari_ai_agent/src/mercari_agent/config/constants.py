"""
系统常量定义

该模块定义了系统中使用的各种常量。
包含URL、错误码、状态码、默认值等常量。

常量分类：
- 系统常量
- URL常量
- 错误码常量
- 状态码常量
- 默认值常量
- 正则表达式常量

Author: Mercari AI Agent Team
"""

import re
from enum import Enum
from typing import Dict, List, Pattern


# =============================================================================
# 系统常量
# =============================================================================

# 应用信息
APP_NAME = "Mercari AI Agent"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "Mercari日本智能购物AI代理系统"

# 编码
DEFAULT_ENCODING = "utf-8"
DEFAULT_LOCALE = "ja_JP"

# 时间格式
DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M:%S"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
ISO_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

# 文件大小限制
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_IMAGE_SIZE = 5 * 1024 * 1024   # 5MB
MAX_TEXT_SIZE = 1024 * 1024        # 1MB

# 请求限制
MAX_REQUEST_SIZE = 100 * 1024 * 1024  # 100MB
MAX_CONCURRENT_REQUESTS = 10
DEFAULT_TIMEOUT = 30

# 分页
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
DEFAULT_MAX_PAGES = 10


# =============================================================================
# URL常量
# =============================================================================

# Mercari URLs
MERCARI_BASE_URL = "https://jp.mercari.com"
MERCARI_SEARCH_URL = f"{MERCARI_BASE_URL}/search"
MERCARI_ITEM_URL = f"{MERCARI_BASE_URL}/item"
MERCARI_API_BASE_URL = "https://api.mercari.jp"
MERCARI_API_V2_URL = f"{MERCARI_API_BASE_URL}/v2"
MERCARI_CDN_URL = "https://static.mercdn.net"

# 搜索参数
MERCARI_SEARCH_PARAMS = {
    "sort": "created_time",
    "order": "desc",
    "status": "on_sale",
    "category_id": "",
    "brand_id": "",
    "price_min": "",
    "price_max": "",
    "item_condition_id": "",
    "shipping_payer_id": "",
    "keyword": ""
}

# API端点
API_ENDPOINTS = {
    "search": "/search",
    "item": "/item",
    "category": "/category",
    "brand": "/brand",
    "user": "/user",
    "recommendation": "/recommendation"
}


# =============================================================================
# 错误码常量
# =============================================================================

class ErrorCode(Enum):
    """错误码枚举"""
    # 系统错误 (1000-1999)
    SYSTEM_ERROR = 1000
    CONFIG_ERROR = 1001
    INITIALIZATION_ERROR = 1002
    SHUTDOWN_ERROR = 1003
    
    # 网络错误 (2000-2999)
    NETWORK_ERROR = 2000
    TIMEOUT_ERROR = 2001
    CONNECTION_ERROR = 2002
    SSL_ERROR = 2003
    
    # 认证错误 (3000-3999)
    AUTH_ERROR = 3000
    TOKEN_ERROR = 3001
    PERMISSION_ERROR = 3002
    RATE_LIMIT_ERROR = 3003
    
    # 数据错误 (4000-4999)
    DATA_ERROR = 4000
    VALIDATION_ERROR = 4001
    SERIALIZATION_ERROR = 4002
    DATABASE_ERROR = 4003
    
    # 业务错误 (5000-5999)
    BUSINESS_ERROR = 5000
    QUERY_ERROR = 5001
    SCRAPER_ERROR = 5002
    ANALYSIS_ERROR = 5003
    
    # 爬虫错误 (8000-8999)
    SCRAPER_NETWORK_ERROR = 8000
    SCRAPER_TIMEOUT_ERROR = 8001
    SCRAPER_PARSE_ERROR = 8002
    SCRAPER_ANTIBOT_ERROR = 8003
    SCRAPER_SESSION_ERROR = 8004
    SCRAPER_PROXY_ERROR = 8005
    SCRAPER_BROWSER_ERROR = 8006
    SCRAPER_JAVASCRIPT_ERROR = 8007
    SCRAPER_CAPTCHA_ERROR = 8008
    SCRAPER_FINGERPRINT_ERROR = 8009
    
    # LLM错误 (6000-6999)
    LLM_ERROR = 6000
    LLM_TIMEOUT_ERROR = 6001
    LLM_QUOTA_ERROR = 6002
    LLM_FORMAT_ERROR = 6003
    
    # 缓存错误 (7000-7999)
    CACHE_ERROR = 7000
    CACHE_MISS_ERROR = 7001
    CACHE_EXPIRED_ERROR = 7002
    CACHE_FULL_ERROR = 7003


# 错误消息映射
ERROR_MESSAGES = {
    ErrorCode.SYSTEM_ERROR: "系统错误",
    ErrorCode.CONFIG_ERROR: "配置错误",
    ErrorCode.INITIALIZATION_ERROR: "初始化错误",
    ErrorCode.SHUTDOWN_ERROR: "关闭错误",
    
    ErrorCode.NETWORK_ERROR: "网络错误",
    ErrorCode.TIMEOUT_ERROR: "请求超时",
    ErrorCode.CONNECTION_ERROR: "连接错误",
    ErrorCode.SSL_ERROR: "SSL错误",
    
    ErrorCode.AUTH_ERROR: "认证错误",
    ErrorCode.TOKEN_ERROR: "令牌错误",
    ErrorCode.PERMISSION_ERROR: "权限错误",
    ErrorCode.RATE_LIMIT_ERROR: "请求频率限制",
    
    ErrorCode.DATA_ERROR: "数据错误",
    ErrorCode.VALIDATION_ERROR: "数据验证错误",
    ErrorCode.SERIALIZATION_ERROR: "序列化错误",
    ErrorCode.DATABASE_ERROR: "数据库错误",
    
    ErrorCode.BUSINESS_ERROR: "业务错误",
    ErrorCode.QUERY_ERROR: "查询错误",
    ErrorCode.SCRAPER_ERROR: "爬虫错误",
    ErrorCode.ANALYSIS_ERROR: "分析错误",
    
    ErrorCode.LLM_ERROR: "LLM服务错误",
    ErrorCode.LLM_TIMEOUT_ERROR: "LLM请求超时",
    ErrorCode.LLM_QUOTA_ERROR: "LLM配额不足",
    ErrorCode.LLM_FORMAT_ERROR: "LLM响应格式错误",
    
    ErrorCode.CACHE_ERROR: "缓存错误",
    ErrorCode.CACHE_MISS_ERROR: "缓存未命中",
    
    ErrorCode.SCRAPER_NETWORK_ERROR: "爬虫网络错误",
    ErrorCode.SCRAPER_TIMEOUT_ERROR: "爬虫请求超时",
    ErrorCode.SCRAPER_PARSE_ERROR: "爬虫解析错误",
    ErrorCode.SCRAPER_ANTIBOT_ERROR: "反爬虫拦截错误",
    ErrorCode.SCRAPER_SESSION_ERROR: "会话管理错误",
    ErrorCode.SCRAPER_PROXY_ERROR: "代理服务错误",
    ErrorCode.SCRAPER_BROWSER_ERROR: "浏览器引擎错误",
    ErrorCode.SCRAPER_JAVASCRIPT_ERROR: "JavaScript执行错误",
    ErrorCode.SCRAPER_CAPTCHA_ERROR: "验证码处理错误",
    ErrorCode.SCRAPER_FINGERPRINT_ERROR: "指纹伪装错误",
    ErrorCode.CACHE_EXPIRED_ERROR: "缓存已过期",
    ErrorCode.CACHE_FULL_ERROR: "缓存已满"
}


# =============================================================================
# 状态码常量
# =============================================================================

class StatusCode(Enum):
    """状态码枚举"""
    # 成功状态
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    
    # 处理状态
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    
    # 错误状态
    ERROR = "error"
    FAILED = "failed"
    TIMEOUT = "timeout"
    
    # 数据状态
    EMPTY = "empty"
    INVALID = "invalid"
    EXPIRED = "expired"


# 状态消息映射
STATUS_MESSAGES = {
    StatusCode.SUCCESS: "操作成功",
    StatusCode.PARTIAL_SUCCESS: "部分成功",
    StatusCode.PENDING: "等待处理",
    StatusCode.PROCESSING: "处理中",
    StatusCode.COMPLETED: "已完成",
    StatusCode.CANCELLED: "已取消",
    StatusCode.ERROR: "操作失败",
    StatusCode.FAILED: "执行失败",
    StatusCode.TIMEOUT: "操作超时",
    StatusCode.EMPTY: "数据为空",
    StatusCode.INVALID: "数据无效",
    StatusCode.EXPIRED: "数据已过期"
}


# =============================================================================
# 默认值常量
# =============================================================================

# 分析相关
DEFAULT_ANALYSIS_DIMENSIONS = [
    "price",      # 价格
    "quality",    # 质量
    "relevance",  # 相关性
    "reputation", # 声誉
    "popularity"  # 受欢迎程度
]

DEFAULT_SCORING_WEIGHTS = {
    "price": 0.25,
    "quality": 0.25,
    "relevance": 0.20,
    "reputation": 0.15,
    "popularity": 0.15
}

DEFAULT_RANKING_STRATEGIES = [
    "balanced",       # 平衡
    "price_oriented", # 价格导向
    "quality_oriented", # 质量导向
    "trending",       # 趋势
    "personalized"    # 个性化
]

# 推荐相关
DEFAULT_RECOMMENDATION_COUNT = 10
MAX_RECOMMENDATION_COUNT = 50
DEFAULT_CONFIDENCE_THRESHOLD = 0.6
DEFAULT_SCORE_THRESHOLD = 6.0

# 缓存相关
DEFAULT_CACHE_TTL = 3600  # 1小时
DEFAULT_CACHE_SIZE = 1000
CACHE_KEY_PATTERNS = {
    "product": "product:{product_id}",
    "search": "search:{query_hash}",
    "analysis": "analysis:{product_id}:{version}",
    "recommendation": "recommendation:{query_hash}:{strategy}"
}

# 日志相关
LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
DEFAULT_LOG_LEVEL = "INFO"
LOG_FORMAT_PATTERNS = {
    "simple": "%(levelname)s - %(message)s",
    "detailed": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "json": "%(asctime)s %(name)s %(levelname)s %(message)s"
}

# 语言相关
SUPPORTED_LANGUAGES = ["ja", "en", "zh"]
DEFAULT_LANGUAGE = "ja"
LANGUAGE_NAMES = {
    "ja": "日本語",
    "en": "English",
    "zh": "中文"
}


# =============================================================================
# 正则表达式常量
# =============================================================================

# 价格相关
PRICE_PATTERNS = {
    "yen": re.compile(r"[¥￥]?[\d,]+円?"),
    "number": re.compile(r"[\d,]+"),
    "range": re.compile(r"(\d+)[～~-](\d+)"),
    "currency": re.compile(r"[¥￥円]")
}

# 日文相关
JAPANESE_PATTERNS = {
    "hiragana": re.compile(r"[\u3040-\u309F]+"),
    "katakana": re.compile(r"[\u30A0-\u30FF]+"),
    "kanji": re.compile(r"[\u4E00-\u9FAF]+"),
    "japanese": re.compile(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]+"),
    "romaji": re.compile(r"[a-zA-Z]+")
}

# 商品相关
PRODUCT_PATTERNS = {
    "condition": re.compile(r"(新品|未使用|目立った傷や汚れなし|やや傷や汚れあり|傷や汚れあり|全体的に状態が悪い)"),
    "size": re.compile(r"(XS|S|M|L|XL|XXL|XXXL|\d+cm|\d+号)"),
    "color": re.compile(r"(赤|青|黄|緑|黒|白|茶|灰|紫|橙|ピンク|その他)"),
    "brand": re.compile(r"[A-Z][a-zA-Z\s]+"),
    "model": re.compile(r"[A-Z0-9\-]+")
}

# URL相关
URL_PATTERNS = {
    "mercari_item": re.compile(r"https?://jp\.mercari\.com/item/[a-zA-Z0-9]+"),
    "mercari_search": re.compile(r"https?://jp\.mercari\.com/search"),
    "image": re.compile(r"https?://[^/]+/[^/]+\.(jpg|jpeg|png|gif|webp)"),
    "general": re.compile(r"https?://[^\s<>\"]+")
}

# 验证相关
VALIDATION_PATTERNS = {
    "email": re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"),
    "phone": re.compile(r"^[\d\-\+\(\)\s]{8,20}$"),
    "postal_code": re.compile(r"^\d{3}-\d{4}$"),
    "alphanumeric": re.compile(r"^[a-zA-Z0-9]+$"),
    "slug": re.compile(r"^[a-z0-9\-_]+$")
}


# =============================================================================
# 商品分类常量
# =============================================================================

# Mercari主要分类
MERCARI_CATEGORIES = {
    "レディース": {
        "id": 1,
        "subcategories": [
            "トップス", "ジャケット/アウター", "ワンピース", "スカート", 
            "パンツ", "靴", "バッグ", "アクセサリー", "ヘアアクセサリー", 
            "小物", "時計", "帽子", "ウィッグ/エクステ", "浴衣/水着", 
            "フォーマル/ドレス", "マタニティ", "その他"
        ]
    },
    "メンズ": {
        "id": 2,
        "subcategories": [
            "トップス", "ジャケット/アウター", "パンツ", "靴", "バッグ", 
            "スーツ", "帽子", "アクセサリー", "小物", "時計", "水着", 
            "レッグウェア", "アンダーウェア", "その他"
        ]
    },
    "ベビー・キッズ": {
        "id": 3,
        "subcategories": [
            "ベビー服(女の子用)", "ベビー服(男の子用)", "ベビー服(男女兼用)", 
            "キッズ服(女の子用)", "キッズ服(男の子用)", "キッズ服(男女兼用)", 
            "キッズ靴", "子ども用ファッション小物", "おむつ/トイレ/バス", 
            "外出/移動用品", "授乳/食事", "ベビー家具/寝具/室内用品", 
            "おもちゃ", "行事/記念品", "その他"
        ]
    },
    "インテリア・住まい・小物": {
        "id": 4,
        "subcategories": [
            "キッチン/食器", "ベッド/マットレス", "ソファ/ソファベッド", 
            "椅子/チェア", "机/テーブル", "収納家具", "ラグ/カーペット/マット", 
            "カーテン/ブラインド", "ライト/照明", "寝具", "インテリア小物", 
            "置物", "植物/観葉植物", "花/ガーデン", "文房具", "アート/写真", 
            "その他"
        ]
    },
    "本・音楽・ゲーム": {
        "id": 5,
        "subcategories": [
            "本", "漫画", "雑誌", "CD", "DVD/ブルーレイ", 
            "レコード", "テレビゲーム", "その他"
        ]
    }
}

# 商品状态
PRODUCT_CONDITIONS = {
    "新品、未使用": {"id": 1, "score": 10},
    "未使用に近い": {"id": 2, "score": 9},
    "目立った傷や汚れなし": {"id": 3, "score": 8},
    "やや傷や汚れあり": {"id": 4, "score": 6},
    "傷や汚れあり": {"id": 5, "score": 4},
    "全体的に状態が悪い": {"id": 6, "score": 2}
}

# 配送相关
SHIPPING_METHODS = {
    "らくらくメルカリ便": {"id": 1, "type": "mercari"},
    "ゆうゆうメルカリ便": {"id": 2, "type": "mercari"},
    "梱包・発送たのメル便": {"id": 3, "type": "mercari"},
    "未定": {"id": 4, "type": "other"},
    "普通郵便(定形、定形外)": {"id": 5, "type": "post"},
    "レターパック": {"id": 6, "type": "post"},
    "ゆうメール": {"id": 7, "type": "post"},
    "クリックポスト": {"id": 8, "type": "post"},
    "ゆうパック": {"id": 9, "type": "post"},
    "宅急便": {"id": 10, "type": "yamato"},
    "ネコポス": {"id": 11, "type": "yamato"},
    "宅急便コンパクト": {"id": 12, "type": "yamato"}
}

# 配送费用承担
SHIPPING_PAYER = {
    "送料込み(出品者負担)": {"id": 1, "type": "seller"},
    "着払い(購入者負担)": {"id": 2, "type": "buyer"}
}


# =============================================================================
# 用户代理常量
# =============================================================================

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0"
]

# HTTP头部
DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0"
}


# =============================================================================
# 消息模板常量
# =============================================================================

MESSAGE_TEMPLATES = {
    "welcome": "欢迎使用Mercari AI购物助手！",
    "search_started": "正在搜索商品，请稍候...",
    "search_completed": "搜索完成，找到 {count} 个商品",
    "analysis_started": "正在分析商品，请稍候...",
    "analysis_completed": "分析完成，生成 {count} 个推荐",
    "no_results": "抱歉，没有找到符合条件的商品",
    "error_occurred": "处理过程中发生错误：{error}",
    "timeout": "请求超时，请稍后重试",
    "invalid_query": "查询格式不正确，请检查输入",
    "system_busy": "系统繁忙，请稍后重试"
}

# 日志消息模板
LOG_TEMPLATES = {
    "request_started": "开始处理请求: {method} {url}",
    "request_completed": "请求处理完成: {status} - {duration}ms",
    "cache_hit": "缓存命中: {key}",
    "cache_miss": "缓存未命中: {key}",
    "scraper_started": "开始爬取: {url}",
    "scraper_completed": "爬取完成: {url} - {count} items",
    "analysis_started": "开始分析: {product_id}",
    "analysis_completed": "分析完成: {product_id} - score: {score}",
    "error_handled": "错误已处理: {error_type} - {message}"
}


# =============================================================================
# 工具函数
# =============================================================================

def get_error_message(error_code: ErrorCode) -> str:
    """获取错误消息"""
    return ERROR_MESSAGES.get(error_code, "未知错误")


def get_status_message(status_code: StatusCode) -> str:
    """获取状态消息"""
    return STATUS_MESSAGES.get(status_code, "未知状态")


def get_cache_key(pattern: str, **kwargs) -> str:
    """生成缓存键"""
    if pattern not in CACHE_KEY_PATTERNS:
        raise ValueError(f"未知的缓存键模式: {pattern}")
    
    return CACHE_KEY_PATTERNS[pattern].format(**kwargs)


def validate_pattern(pattern_name: str, text: str) -> bool:
    """验证文本是否符合模式"""
    if pattern_name not in VALIDATION_PATTERNS:
        raise ValueError(f"未知的验证模式: {pattern_name}")
    
    pattern = VALIDATION_PATTERNS[pattern_name]
    return bool(pattern.match(text))


def extract_pattern(pattern_name: str, text: str) -> List[str]:
    """提取匹配模式的文本"""
    patterns = {**PRICE_PATTERNS, **JAPANESE_PATTERNS, **PRODUCT_PATTERNS, **URL_PATTERNS}
    
    if pattern_name not in patterns:
        raise ValueError(f"未知的提取模式: {pattern_name}")
    
    pattern = patterns[pattern_name]
    return pattern.findall(text)


def get_category_info(category_name: str) -> Dict:
    """获取分类信息"""
    return MERCARI_CATEGORIES.get(category_name, {})


def get_condition_score(condition: str) -> int:
    """获取商品状态评分"""
    return PRODUCT_CONDITIONS.get(condition, {}).get("score", 0)


def format_message(template_name: str, **kwargs) -> str:
    """格式化消息"""
    if template_name not in MESSAGE_TEMPLATES:
        raise ValueError(f"未知的消息模板: {template_name}")
    
    template = MESSAGE_TEMPLATES[template_name]
    return template.format(**kwargs)


def format_log_message(template_name: str, **kwargs) -> str:
    """格式化日志消息"""
    if template_name not in LOG_TEMPLATES:
        raise ValueError(f"未知的日志模板: {template_name}")
    
    template = LOG_TEMPLATES[template_name]
    return template.format(**kwargs)


# =============================================================================
# 爬虫常量
# =============================================================================

# 爬虫配置常量
SCRAPER_CONSTANTS = {
    "DEFAULT_USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "MAX_CONCURRENT_REQUESTS": 10,
    "MAX_REQUESTS_PER_HOST": 30,
    "MAX_REQUESTS_PER_MINUTE": 30,
    "DEFAULT_TIMEOUT": 30,
    "MAX_RETRIES": 3,
    "MIN_REQUEST_INTERVAL": 2.0,
    "MAX_REQUEST_INTERVAL": 5.0,
    "SESSION_POOL_SIZE": 5,
    "BROWSER_POOL_SIZE": 2,
    "MAX_CONTENT_LENGTH": 1048576,  # 1MB
    "MAX_IMAGE_SIZE": 10485760,  # 10MB
    "DETECTION_THRESHOLD": 0.7,
    "MAX_CONSECUTIVE_ERRORS": 5,
    "MAX_BACKOFF_TIME": 60,
    "COOKIE_FILE_PATH": "./data/cookies.json",
    "ML_MODEL_PATH": "./data/bot_detection_model.pkl"
}

# 反爬虫检测常量
ANTI_BOT_CONSTANTS = {
    "DETECTION_PATTERNS": {
        "CAPTCHA": ["captcha", "recaptcha", "hcaptcha", "verification"],
        "RATE_LIMIT": ["too many requests", "rate limit", "slow down"],
        "IP_BLOCK": ["access denied", "blocked", "forbidden", "your ip"],
        "USER_AGENT": ["invalid browser", "unsupported browser", "browser required"],
        "CLOUDFLARE": ["cloudflare", "cf-ray", "checking security", "ddos protection"],
        "JAVASCRIPT": ["javascript required", "enable javascript", "browser verification"]
    },
    "BYPASS_STRATEGIES": {
        "WAIT_AND_RETRY": "wait_and_retry",
        "CHANGE_USER_AGENT": "change_user_agent",
        "USE_PROXY": "use_proxy",
        "ROTATE_SESSION": "rotate_session",
        "SOLVE_CAPTCHA": "solve_captcha",
        "EXECUTE_JAVASCRIPT": "execute_javascript",
        "USE_BROWSER_ENGINE": "use_browser_engine",
        "FINGERPRINT_SPOOFING": "fingerprint_spoofing",
        "BEHAVIOR_MIMICKING": "behavior_mimicking"
    },
    "DETECTION_TYPES": {
        "CAPTCHA": "captcha",
        "RATE_LIMIT": "rate_limit",
        "IP_BLOCK": "ip_block",
        "USER_AGENT_BLOCK": "user_agent_block",
        "JAVASCRIPT_CHALLENGE": "js_challenge",
        "CLOUDFLARE": "cloudflare",
        "FINGERPRINT_DETECTION": "fingerprint_detection",
        "BEHAVIOR_ANALYSIS": "behavior_analysis",
        "MACHINE_LEARNING": "machine_learning"
    }
}

# 会话管理常量
SESSION_CONSTANTS = {
    "MAX_SESSIONS": 5,
    "SESSION_TIMEOUT": 300,
    "MAX_REQUESTS_PER_SESSION": 100,
    "SESSION_HEALTH_CHECK_INTERVAL": 60,
    "PROXY_HEALTH_CHECK_INTERVAL": 300,
    "COOKIE_PERSISTENCE_INTERVAL": 30,
    "SESSION_ROTATION_INTERVAL": 3600,
    "MAX_SESSION_ERRORS": 10,
    "SESSION_COOLDOWN_TIME": 600
}

# 数据解析常量
PARSER_CONSTANTS = {
    "MAX_PARSE_TIME": 30,
    "MAX_RETRIES": 3,
    "CONTENT_QUALITY_THRESHOLD": 0.3,
    "MIN_TITLE_LENGTH": 1,
    "MAX_TITLE_LENGTH": 500,
    "MIN_DESCRIPTION_LENGTH": 0,
    "MAX_DESCRIPTION_LENGTH": 10000,
    "MIN_PRICE": 0,
    "MAX_PRICE": 10000000,
    "MIN_RATING": 0,
    "MAX_RATING": 5,
    "IMAGE_QUALITY_THRESHOLD": 0.5,
    "SUPPORTED_IMAGE_FORMATS": ["jpg", "jpeg", "png", "webp", "gif"]
}

# 页面类型常量
PAGE_TYPES = {
    "SEARCH_RESULTS": "search_results",
    "PRODUCT_DETAIL": "product_detail",
    "SELLER_PROFILE": "seller_profile",
    "CATEGORY_PAGE": "category_page",
    "UNKNOWN": "unknown"
}

# 爬虫选择器常量
SCRAPER_SELECTORS = {
    "search_results": {
        "item_container": "mer-item-thumbnail, [data-testid='item-cell']",
        "item_link": "a[href*='/item/']",
        "item_title": "[data-testid='name'], .mer-item-name",
        "item_price": "[data-testid='price'], .mer-item-price",
        "item_image": "img[src*='mercari'], img[data-src*='mercari']",
        "item_condition": "[data-testid='item-condition'], .mer-item-condition",
        "item_sold": "[data-testid='sold-out'], .mer-item-sold-out",
        "pagination_next": "a[data-testid='pagination-next'], .mer-pagination-next",
        "total_count": "[data-testid='search-result-count'], .mer-search-result-count"
    },
    "product_detail": {
        "title": "h1[data-testid='name'], .mer-item-name",
        "price": "[data-testid='price'], .mer-item-price",
        "condition": "[data-testid='item-condition'], .mer-item-condition",
        "description": "[data-testid='description'], .mer-item-description",
        "category": "[data-testid='breadcrumb'] a, .mer-breadcrumb a",
        "brand": "[data-testid='brand'], .mer-item-brand",
        "size": "[data-testid='size'], .mer-item-size",
        "color": "[data-testid='color'], .mer-item-color",
        "material": "[data-testid='material'], .mer-item-material",
        "seller_name": "[data-testid='seller-name'], .mer-seller-name",
        "seller_rating": "[data-testid='seller-rating'], .mer-seller-rating",
        "seller_review_count": "[data-testid='seller-review-count'], .mer-seller-review-count",
        "view_count": "[data-testid='view-count'], .mer-view-count",
        "like_count": "[data-testid='like-count'], .mer-like-count",
        "comment_count": "[data-testid='comment-count'], .mer-comment-count",
        "images": "img[data-testid='product-image'], .mer-item-image img",
        "specifications": "[data-testid='item-detail-table'] tr, .mer-item-detail-table tr",
        "shipping_cost": "[data-testid='shipping-cost'], .mer-shipping-cost",
        "shipping_method": "[data-testid='shipping-method'], .mer-shipping-method",
        "created_at": "[data-testid='created-at'], .mer-created-at",
        "updated_at": "[data-testid='updated-at'], .mer-updated-at"
    }
}

# 正则表达式常量
REGEX_PATTERNS = {
    "price": r'[\d,]+',
    "rating": r'(\d+\.?\d*)',
    "count": r'(\d+)',
    "item_id": r'/item/([a-zA-Z0-9]+)',
    "seller_id": r'/u/(\d+)',
    "category_id": r'/category/(\d+)',
    "japanese_numbers": r'[０-９]+',
    "size_pattern": r'(XS|S|M|L|XL|XXL|XXXL|\d+cm|\d+号)',
    "color_pattern": r'(赤|青|黄|緑|黒|白|灰|茶|紫|橙|ピンク|ベージュ|ネイビー|カーキ|ワイン)',
    "email": r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$',
    "url": r'^https?://[^\s/$.?#].[^\s]*$',
    "japanese_text": r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]+'
}

# 用户代理常量
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
]

# 浏览器引擎常量
BROWSER_ENGINE_CONSTANTS = {
    "PLAYWRIGHT": "playwright",
    "SELENIUM": "selenium",
    "DEFAULT_WAIT_TIME": 3,
    "PAGE_LOAD_TIMEOUT": 30,
    "ELEMENT_WAIT_TIMEOUT": 10,
    "SCREENSHOT_ENABLED": False,
    "HEADLESS_MODE": True,
    "DISABLE_IMAGES": True,
    "DISABLE_JAVASCRIPT": False,
    "VIEWPORT_WIDTH": 1920,
    "VIEWPORT_HEIGHT": 1080
}