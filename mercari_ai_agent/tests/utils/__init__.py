"""
测试工具模块

该模块包含测试所需的工具函数、Mock对象和测试数据。

主要功能：
- 测试辅助函数
- Mock对象创建
- 测试数据生成
- 测试装置设置

Author: Mercari AI Agent Team
"""

import asyncio
import json
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, AsyncMock, MagicMock
from dataclasses import dataclass, field
from datetime import datetime, timedelta

# 测试数据目录
TEST_DATA_DIR = Path(__file__).parent.parent / "data"
TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class TestProductData:
    """测试商品数据"""
    id: str
    title: str
    price: int
    description: str
    category: str
    condition: str
    seller_id: str
    image_urls: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class TestQueryData:
    """测试查询数据"""
    query: str
    category: Optional[str] = None
    price_range: Optional[tuple] = None
    condition: Optional[str] = None
    sort_by: str = "relevance"
    expected_results: int = 10


class MockLLMResponse:
    """Mock LLM响应"""
    
    def __init__(self, content: str, cost: float = 0.01, model: str = "gpt-4"):
        self.content = content
        self.cost = cost
        self.model = model
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "cost": self.cost,
            "model": self.model,
            "timestamp": self.timestamp.isoformat()
        }


class MockToolResult:
    """Mock工具执行结果"""
    
    def __init__(self, success: bool = True, data: Any = None, error: str = None):
        self.success = success
        self.data = data
        self.error = error
        self.execution_time = 0.1
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "execution_time": self.execution_time,
            "timestamp": self.timestamp.isoformat()
        }


def create_test_products(count: int = 10) -> List[TestProductData]:
    """创建测试商品数据"""
    products = []
    
    categories = ["ファッション", "家電", "本・雑誌", "スポーツ", "おもちゃ"]
    conditions = ["新品", "未使用に近い", "目立った傷や汚れなし", "やや傷や汚れあり"]
    
    for i in range(count):
        product = TestProductData(
            id=f"test_product_{i:03d}",
            title=f"テスト商品 {i + 1}",
            price=(i + 1) * 1000,
            description=f"これはテスト商品 {i + 1} の説明です。",
            category=categories[i % len(categories)],
            condition=conditions[i % len(conditions)],
            seller_id=f"seller_{i % 3:03d}",
            image_urls=[f"https://example.com/image_{i}_{j}.jpg" for j in range(3)],
            tags=[f"tag_{i}", f"category_{i % 5}"]
        )
        products.append(product)
    
    return products


def create_test_queries() -> List[TestQueryData]:
    """创建测试查询数据"""
    queries = [
        TestQueryData(
            query="iPhone 14 Pro",
            category="家電",
            price_range=(50000, 150000),
            condition="新品",
            expected_results=20
        ),
        TestQueryData(
            query="ナイキ スニーカー",
            category="ファッション",
            price_range=(5000, 30000),
            expected_results=15
        ),
        TestQueryData(
            query="プレイステーション5",
            category="おもちゃ",
            price_range=(40000, 80000),
            condition="未使用に近い",
            expected_results=5
        ),
        TestQueryData(
            query="村上春樹",
            category="本・雑誌",
            price_range=(300, 2000),
            expected_results=30
        )
    ]
    
    return queries


async def create_mock_llm_service() -> Mock:
    """创建Mock LLM服务"""
    mock_service = AsyncMock()
    
    # Mock生成响应
    mock_service.generate_response.return_value = MockLLMResponse(
        content="这是一个模拟的LLM响应。",
        cost=0.01,
        model="gpt-4"
    )
    
    # Mock流式响应
    async def mock_stream_response(prompt: str, **kwargs):
        for chunk in ["这是", "一个", "流式", "响应"]:
            yield chunk
    
    mock_service.stream_response = mock_stream_response
    
    # Mock成本统计
    mock_service.get_cost_summary.return_value = {
        "total_cost": 0.50,
        "request_count": 25,
        "average_cost": 0.02
    }
    
    return mock_service


def create_mock_tool_registry() -> Mock:
    """创建Mock工具注册表"""
    mock_registry = Mock()
    
    # Mock工具列表
    mock_registry.get_available_tools.return_value = [
        "search_products",
        "analyze_market",
        "format_results"
    ]
    
    # Mock工具执行
    mock_registry.execute_tool.return_value = MockToolResult(
        success=True,
        data={"results": create_test_products(5)}
    )
    
    return mock_registry


def create_mock_scraper_service() -> Mock:
    """创建Mock爬虫服务"""
    mock_service = AsyncMock()
    
    # Mock搜索结果
    mock_service.search_products.return_value = {
        "products": [p.__dict__ for p in create_test_products(10)],
        "total": 100,
        "page": 1,
        "per_page": 10
    }
    
    # Mock商品详情
    mock_service.get_product_details.return_value = create_test_products(1)[0].__dict__
    
    return mock_service


def create_test_config() -> Dict[str, Any]:
    """创建测试配置"""
    return {
        "app_name": "Test Mercari AI Agent",
        "environment": "test",
        "debug": True,
        "llm": {
            "openai_api_key": "test_key",
            "default_provider": "openai",
            "enable_caching": False,
            "enable_cost_tracking": True
        },
        "tool": {
            "tool_timeout": 5,
            "max_tool_iterations": 3,
            "enable_tool_cache": False
        },
        "scraper": {
            "timeout": 10,
            "max_retries": 2,
            "enable_cache": False
        },
        "database": {
            "database_type": "sqlite",
            "sqlite_path": ":memory:"
        }
    }


class TestDataManager:
    """测试数据管理器"""
    
    def __init__(self, data_dir: Path = TEST_DATA_DIR):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def save_test_data(self, filename: str, data: Any) -> Path:
        """保存测试数据"""
        filepath = self.data_dir / filename
        
        if isinstance(data, (dict, list)):
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        else:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(str(data))
        
        return filepath
    
    def load_test_data(self, filename: str) -> Any:
        """加载测试数据"""
        filepath = self.data_dir / filename
        
        if not filepath.exists():
            raise FileNotFoundError(f"测试数据文件不存在: {filepath}")
        
        if filepath.suffix == '.json':
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
    
    def create_temp_file(self, content: str, suffix: str = '.txt') -> Path:
        """创建临时文件"""
        temp_file = tempfile.NamedTemporaryFile(
            mode='w', 
            suffix=suffix, 
            delete=False, 
            encoding='utf-8'
        )
        temp_file.write(content)
        temp_file.close()
        return Path(temp_file.name)
    
    def cleanup(self):
        """清理测试数据"""
        if self.data_dir.exists():
            shutil.rmtree(self.data_dir)


def async_test(coro):
    """异步测试装饰器"""
    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro(*args, **kwargs))
    return wrapper


# 全局测试数据管理器
test_data_manager = TestDataManager()

# 创建默认测试数据
if not (TEST_DATA_DIR / "test_products.json").exists():
    test_products = [p.__dict__ for p in create_test_products(50)]
    test_data_manager.save_test_data("test_products.json", test_products)

if not (TEST_DATA_DIR / "test_queries.json").exists():
    test_queries = [q.__dict__ for q in create_test_queries()]
    test_data_manager.save_test_data("test_queries.json", test_queries)