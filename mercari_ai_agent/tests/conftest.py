"""
pytest 配置文件

该文件包含pytest的全局配置和固定装置（fixtures）。
提供测试所需的共享资源和配置。

Author: Mercari AI Agent Team
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock
from typing import Generator, AsyncGenerator

# 测试数据
from tests.fixtures.sample_data import (
    SAMPLE_PRODUCTS,
    SAMPLE_QUERIES,
    SAMPLE_RECOMMENDATIONS
)

# 项目模块
from mercari_agent.config import Settings, get_settings
from mercari_agent.models import (
    ProductData, 
    ParsedQuery, 
    RecommendationResult,
    create_empty_result
)
from mercari_agent.services.llm_service import LLMService
from mercari_agent.services.scraper_service import ScraperService
from mercari_agent.services.analysis_service import AnalysisService
from mercari_agent.utils.cache_manager import CacheManager
from mercari_agent.utils.logger import setup_logger


# =============================================================================
# 测试配置
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings():
    """测试配置"""
    settings = Settings()
    settings.environment = "testing"
    settings.debug = True
    settings.log.level = "DEBUG"
    settings.cache.enable_memory_cache = True
    settings.cache.enable_disk_cache = False
    settings.cache.enable_redis_cache = False
    settings.database.database_type = "sqlite"
    settings.database.sqlite_path = ":memory:"
    settings.api.enable_auth = False
    settings.api.enable_docs = False
    
    # 设置临时目录
    temp_dir = tempfile.mkdtemp()
    settings.data_dir = temp_dir
    settings.temp_dir = temp_dir
    settings.log.log_dir = temp_dir
    settings.cache.disk_cache_dir = temp_dir
    
    return settings


@pytest.fixture(scope="session")
def temp_dir():
    """临时目录"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture(scope="session")
def setup_test_logging(test_settings):
    """设置测试日志"""
    setup_logger()


# =============================================================================
# 模拟服务
# =============================================================================

@pytest.fixture
def mock_llm_service():
    """模拟LLM服务"""
    mock_service = Mock(spec=LLMService)
    mock_service.is_healthy.return_value = True
    
    # 模拟解析查询
    async def mock_parse_query(query: str, language: str = "ja"):
        return ParsedQuery(
            original_query=query,
            intent="search",
            keywords=["test", "product"],
            category="electronics",
            price_range=None,
            language=language
        )
    
    mock_service.parse_query = AsyncMock(side_effect=mock_parse_query)
    
    # 模拟生成推荐理由
    async def mock_generate_reason(product, query):
        return "这是一个测试推荐理由"
    
    mock_service.generate_recommendation_reason = AsyncMock(side_effect=mock_generate_reason)
    
    return mock_service


@pytest.fixture
def mock_scraper_service():
    """模拟爬虫服务"""
    mock_service = Mock(spec=ScraperService)
    mock_service.is_healthy.return_value = True
    
    # 模拟搜索产品
    async def mock_search_products(query, max_pages=3):
        return SAMPLE_PRODUCTS[:10]  # 返回前10个样本产品
    
    mock_service.search_products = AsyncMock(side_effect=mock_search_products)
    
    # 模拟获取产品详情
    async def mock_get_product_details(product_url):
        return SAMPLE_PRODUCTS[0]  # 返回第一个样本产品
    
    mock_service.get_product_details = AsyncMock(side_effect=mock_get_product_details)
    
    return mock_service


@pytest.fixture
def mock_analysis_service():
    """模拟分析服务"""
    mock_service = Mock(spec=AnalysisService)
    mock_service.is_healthy.return_value = True
    
    # 模拟分析产品
    async def mock_analyze_product(product):
        return {
            "price_score": 8.5,
            "quality_score": 7.8,
            "relevance_score": 9.2,
            "reputation_score": 8.0,
            "popularity_score": 7.5,
            "overall_score": 8.2
        }
    
    mock_service.analyze_product = AsyncMock(side_effect=mock_analyze_product)
    
    # 模拟批量分析
    async def mock_analyze_products(products):
        return [await mock_analyze_product(p) for p in products]
    
    mock_service.analyze_products = AsyncMock(side_effect=mock_analyze_products)
    
    return mock_service


@pytest.fixture
def mock_cache_manager():
    """模拟缓存管理器"""
    cache_data = {}
    
    mock_cache = Mock(spec=CacheManager)
    mock_cache.is_healthy.return_value = True
    
    # 模拟缓存操作
    async def mock_get(key):
        return cache_data.get(key)
    
    async def mock_set(key, value, ttl=None):
        cache_data[key] = value
        return True
    
    async def mock_delete(key):
        return cache_data.pop(key, None) is not None
    
    async def mock_clear():
        cache_data.clear()
        return True
    
    mock_cache.get = AsyncMock(side_effect=mock_get)
    mock_cache.set = AsyncMock(side_effect=mock_set)
    mock_cache.delete = AsyncMock(side_effect=mock_delete)
    mock_cache.clear = AsyncMock(side_effect=mock_clear)
    
    return mock_cache


# =============================================================================
# 测试数据固定装置
# =============================================================================

@pytest.fixture
def sample_product():
    """样本产品数据"""
    return SAMPLE_PRODUCTS[0]


@pytest.fixture
def sample_products():
    """样本产品列表"""
    return SAMPLE_PRODUCTS


@pytest.fixture
def sample_query():
    """样本查询"""
    return SAMPLE_QUERIES[0]


@pytest.fixture
def sample_queries():
    """样本查询列表"""
    return SAMPLE_QUERIES


@pytest.fixture
def sample_parsed_query():
    """样本解析查询"""
    return ParsedQuery(
        original_query="iPhone ケース",
        intent="search",
        keywords=["iPhone", "ケース"],
        category="electronics",
        price_range=None,
        language="ja",
        complexity="simple"
    )


@pytest.fixture
def sample_recommendation():
    """样本推荐"""
    return SAMPLE_RECOMMENDATIONS[0]


@pytest.fixture
def sample_recommendations():
    """样本推荐列表"""
    return SAMPLE_RECOMMENDATIONS


@pytest.fixture
def sample_recommendation_result():
    """样本推荐结果"""
    result = RecommendationResult(
        recommendations=SAMPLE_RECOMMENDATIONS,
        total_analyzed=48,
        processing_time=2.5
    )
    return result


@pytest.fixture
def empty_recommendation_result():
    """空推荐结果"""
    return create_empty_result()


# =============================================================================
# 测试工具固定装置
# =============================================================================

@pytest.fixture
def create_test_file():
    """创建测试文件的工具"""
    created_files = []
    
    def _create_file(path: str, content: str = ""):
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding='utf-8')
        created_files.append(file_path)
        return file_path
    
    yield _create_file
    
    # 清理创建的文件
    for file_path in created_files:
        if file_path.exists():
            file_path.unlink()


@pytest.fixture
def assert_logs():
    """断言日志的工具"""
    import logging
    
    def _assert_logs(logger_name: str, level: str, message: str):
        """断言日志消息"""
        logger = logging.getLogger(logger_name)
        with pytest.LogCaptureFixture() as log_capture:
            logger.log(getattr(logging, level.upper()), message)
            assert message in log_capture.text
    
    return _assert_logs


@pytest.fixture
def mock_http_response():
    """模拟HTTP响应"""
    def _create_response(
        status_code: int = 200,
        json_data: dict = None,
        text: str = "",
        headers: dict = None
    ):
        response = Mock()
        response.status_code = status_code
        response.json.return_value = json_data or {}
        response.text = text
        response.headers = headers or {}
        return response
    
    return _create_response


# =============================================================================
# 异步测试工具
# =============================================================================

@pytest.fixture
def async_test():
    """异步测试装饰器"""
    def _async_test(coro):
        """运行异步测试"""
        def wrapper(*args, **kwargs):
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(coro(*args, **kwargs))
        return wrapper
    
    return _async_test


@pytest.fixture
def wait_for():
    """等待异步操作完成"""
    async def _wait_for(coro, timeout=5.0):
        """等待协程完成"""
        return await asyncio.wait_for(coro, timeout=timeout)
    
    return _wait_for


# =============================================================================
# 性能测试工具
# =============================================================================

@pytest.fixture
def performance_timer():
    """性能计时器"""
    import time
    
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = time.time()
        
        def stop(self):
            self.end_time = time.time()
        
        @property
        def elapsed(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return None
        
        def __enter__(self):
            self.start()
            return self
        
        def __exit__(self, *args):
            self.stop()
    
    return Timer


@pytest.fixture
def memory_profiler():
    """内存分析器"""
    import tracemalloc
    
    class MemoryProfiler:
        def __init__(self):
            self.start_snapshot = None
            self.end_snapshot = None
        
        def start(self):
            tracemalloc.start()
            self.start_snapshot = tracemalloc.take_snapshot()
        
        def stop(self):
            self.end_snapshot = tracemalloc.take_snapshot()
            tracemalloc.stop()
        
        def get_stats(self):
            if self.start_snapshot and self.end_snapshot:
                return self.end_snapshot.compare_to(self.start_snapshot, 'lineno')
            return []
        
        def __enter__(self):
            self.start()
            return self
        
        def __exit__(self, *args):
            self.stop()
    
    return MemoryProfiler


# =============================================================================
# 测试标记
# =============================================================================

def pytest_configure(config):
    """pytest配置"""
    # 注册自定义标记
    config.addinivalue_line(
        "markers", "unit: 单元测试标记"
    )
    config.addinivalue_line(
        "markers", "integration: 集成测试标记"
    )
    config.addinivalue_line(
        "markers", "slow: 慢速测试标记"
    )
    config.addinivalue_line(
        "markers", "network: 需要网络的测试标记"
    )
    config.addinivalue_line(
        "markers", "external: 依赖外部服务的测试标记"
    )


def pytest_collection_modifyitems(config, items):
    """修改测试项"""
    for item in items:
        # 为单元测试添加标记
        if "unit" in item.nodeid:
            item.add_marker(pytest.mark.unit)
        
        # 为集成测试添加标记
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        
        # 为慢速测试添加标记
        if "slow" in item.name or "performance" in item.name:
            item.add_marker(pytest.mark.slow)


# =============================================================================
# 测试后清理
# =============================================================================

@pytest.fixture(autouse=True)
def cleanup_after_test():
    """测试后自动清理"""
    yield
    
    # 清理可能的异步任务
    try:
        loop = asyncio.get_event_loop()
        pending = asyncio.all_tasks(loop)
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    except:
        pass
    
    # 清理日志处理器
    import logging
    logging.getLogger().handlers.clear()