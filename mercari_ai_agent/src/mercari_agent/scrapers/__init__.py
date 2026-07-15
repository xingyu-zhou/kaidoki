"""
爬虫组件模块

该模块包含系统的爬虫组件，负责从Mercari平台获取商品数据。

主要组件：
- BaseScraper: 基础爬虫抽象类
- MercariScraper: Mercari专用爬虫实现
- AntiBotHandler: 反爬虫处理器

技术特点：
- 多种爬虫策略支持（requests、Selenium、Playwright）
- 智能反爬虫检测和处理
- 自动重试和错误恢复
- 会话管理和请求节流
- 数据提取和验证

设计原则：
- 可扩展性：易于添加新的爬虫策略
- 鲁棒性：完善的错误处理和恢复机制
- 高效性：智能缓存和请求优化
- 合规性：遵守网站使用条款和爬虫礼仪

Author: Mercari AI Agent Team
"""

from .base_scraper import BaseScraper, ScrapingStrategy
from .mercari_scraper import MercariScraper, MercariScrapingResult, SearchFilters
from .anti_bot_handler import AntiBotHandler, BotDetectionResult, BotDetectionType
from .session_manager import SessionManager, SessionInfo, ProxyInfo
from .data_parser import MercariDataParser, ParsingContext, PageType
from .scraper_utils import (
    HTMLSelectorTool, JapaneseTextTool, PriceNumberTool,
    URLTool, DataValidationTool, ImageTool, TimeTool
)

__all__ = [
    "BaseScraper",
    "ScrapingStrategy",
    "MercariScraper",
    "MercariScrapingResult",
    "SearchFilters",
    "AntiBotHandler",
    "BotDetectionResult",
    "BotDetectionType",
    "SessionManager",
    "SessionInfo",
    "ProxyInfo",
    "MercariDataParser",
    "ParsingContext",
    "PageType",
    "HTMLSelectorTool",
    "JapaneseTextTool",
    "PriceNumberTool",
    "URLTool",
    "DataValidationTool",
    "ImageTool",
    "TimeTool"
]