"""
迁移验证脚本

验证基础设施层迁移的核心组件是否正常工作。

Author: Mercari AI Agent Team
"""

import sys
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

# 添加项目根路径到sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MigrationValidator:
    """迁移验证器"""
    
    def __init__(self):
        self.test_results: Dict[str, Dict[str, Any]] = {}
        self.success_count = 0
        self.failure_count = 0
    
    def run_all_tests(self) -> bool:
        """运行所有验证测试"""
        logger.info("开始验证迁移结果...")
        
        test_methods = [
            self.test_exceptions,
            self.test_price_value_objects,
            self.test_product_attributes,
            self.test_query_attributes,
            self.test_product_entity,
            self.test_query_entity,
            self.test_price_utils,
            self.test_timeout_utils,
            self.test_config_system,
        ]
        
        for test_method in test_methods:
            try:
                test_name = test_method.__name__
                logger.info(f"运行测试: {test_name}")
                
                if asyncio.iscoroutinefunction(test_method):
                    result = asyncio.run(test_method())
                else:
                    result = test_method()
                
                self.test_results[test_name] = {
                    "status": "success" if result else "failed",
                    "timestamp": datetime.now().isoformat()
                }
                
                if result:
                    self.success_count += 1
                    logger.info(f"✅ {test_name} 通过")
                else:
                    self.failure_count += 1
                    logger.error(f"❌ {test_name} 失败")
                    
            except Exception as e:
                self.failure_count += 1
                self.test_results[test_method.__name__] = {
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                logger.error(f"💥 {test_method.__name__} 异常: {e}")
        
        total_tests = len(test_methods)
        logger.info(f"\n验证完成: {self.success_count}/{total_tests} 测试通过")
        
        return self.failure_count == 0
    
    def test_exceptions(self) -> bool:
        """测试异常体系"""
        try:
            from mercari_agent.shared.exceptions import (
                MercariAgentException,
                ValidationError,
                ProductNotFoundError,
                PriceParsingError,
                ConfigurationError,
                NetworkError
            )
            
            # 测试基础异常
            try:
                raise ValidationError("测试验证错误", field="test_field", value="test_value")
            except ValidationError as e:
                assert e.message == "测试验证错误"
                assert e.details["field"] == "test_field"
                assert e.details["value"] == "test_value"
                assert e.error_code == "VALIDATION_ERROR"
            
            # 测试产品异常
            try:
                raise ProductNotFoundError("商品未找到", product_id="test123")
            except ProductNotFoundError as e:
                assert e.details["product_id"] == "test123"
                assert e.error_code == "PRODUCT_NOT_FOUND"
            
            # 测试价格异常
            try:
                raise PriceParsingError("价格解析失败", price_text="invalid price")
            except PriceParsingError as e:
                assert e.details["price_text"] == "invalid price"
            
            logger.info("异常体系验证通过")
            return True
            
        except Exception as e:
            logger.error(f"异常体系验证失败: {e}")
            return False
    
    def test_price_value_objects(self) -> bool:
        """测试价格值对象"""
        try:
            from mercari_agent.domain.value_objects.price import (
                Price, PriceRange, PriceHistory, Currency
            )
            from decimal import Decimal
            
            # 测试价格对象
            price = Price.from_float(1000.0, Currency.JPY)
            assert price.amount == Decimal('1000')
            assert price.currency == Currency.JPY
            assert price.format() == "¥1,000"
            
            # 测试价格范围
            price_range = PriceRange.from_floats(500, 2000)
            assert price_range.is_valid()
            assert price_range.contains_price(price)
            
            # 测试价格历史
            price_history = PriceHistory("test_product")
            price_history.add_price_record(price)
            assert price_history.get_current_price() == price
            
            logger.info("价格值对象验证通过")
            return True
            
        except Exception as e:
            logger.error(f"价格值对象验证失败: {e}")
            return False
    
    def test_product_attributes(self) -> bool:
        """测试商品属性值对象"""
        try:
            from mercari_agent.domain.value_objects.product_attributes import (
                ProductImage, ProductImages, ProductMetadata, SellerInfo,
                ProductStatus, ProductCategory, ProductCondition
            )
            
            # 测试商品图片
            image = ProductImage.create_primary("https://example.com/image.jpg")
            assert image.is_primary
            assert image.url == "https://example.com/image.jpg"
            
            # 测试图片集合
            images = ProductImages.create_with_primary(
                "https://example.com/primary.jpg",
                ["https://example.com/additional.jpg"]
            )
            assert images.count() == 2
            assert images.get_primary_image() is not None
            
            # 测试卖家信息
            seller = SellerInfo("seller123", "测试卖家")
            assert seller.seller_id == "seller123"
            assert seller.seller_name == "测试卖家"
            
            # 测试元数据
            metadata = ProductMetadata.create_mercari("product123")
            assert metadata.source == "mercari"
            assert metadata.source_id == "product123"
            
            logger.info("商品属性值对象验证通过")
            return True
            
        except Exception as e:
            logger.error(f"商品属性值对象验证失败: {e}")
            return False
    
    def test_query_attributes(self) -> bool:
        """测试查询属性值对象"""
        try:
            from mercari_agent.domain.value_objects.query_attributes import (
                SearchFilters, SearchCriteria, QueryContext, QueryMetadata,
                QueryIntent, QueryType, QueryComplexity
            )
            from mercari_agent.domain.value_objects.price import PriceRange
            
            # 测试搜索过滤器
            filters = SearchFilters.create_empty()
            filters = filters.with_category("electronics")
            assert filters.category == "electronics"
            
            # 测试搜索条件
            criteria = SearchCriteria.create_keyword_search(["iPhone", "手机"])
            assert len(criteria.keywords) == 2
            assert criteria.has_keywords()
            
            # 测试查询上下文
            context = QueryContext.create_japanese()
            assert context.language == "ja"
            
            # 测试查询元数据
            metadata = QueryMetadata()
            metadata = metadata.with_confidence(0.9)
            assert metadata.confidence == 0.9
            
            logger.info("查询属性值对象验证通过")
            return True
            
        except Exception as e:
            logger.error(f"查询属性值对象验证失败: {e}")
            return False
    
    def test_product_entity(self) -> bool:
        """测试商品实体"""
        try:
            from mercari_agent.domain.entities.product import Product
            from mercari_agent.domain.value_objects.price import Price, Currency
            
            # 创建商品
            price = Price.from_float(1500.0, Currency.JPY)
            product = Product.create_new(
                title="测试商品",
                price=price,
                url="https://example.com/product"
            )
            
            assert product.title == "测试商品"
            assert product.price == price
            assert product.is_available()
            
            # 测试价格更新
            new_price = Price.from_float(1200.0, Currency.JPY)
            product.update_price(new_price)
            assert product.price == new_price
            
            # 测试统计数据
            product.increment_view_count()
            assert product.view_count == 1
            
            logger.info("商品实体验证通过")
            return True
            
        except Exception as e:
            logger.error(f"商品实体验证失败: {e}")
            return False
    
    def test_query_entity(self) -> bool:
        """测试查询实体"""
        try:
            from mercari_agent.domain.entities.query import Query
            from mercari_agent.domain.value_objects.query_attributes import QueryIntent
            
            # 创建查询
            query = Query.create_simple("iPhone 手机")
            assert query.original_text == "iPhone 手机"
            assert query.intent == QueryIntent.SEARCH
            
            # 处理查询
            query.process_query()
            assert query.processed_at is not None
            
            # 测试关键词添加
            query.add_keyword("新品")
            assert "新品" in query.get_keywords()
            
            logger.info("查询实体验证通过")
            return True
            
        except Exception as e:
            logger.error(f"查询实体验证失败: {e}")
            return False
    
    async def test_price_utils(self) -> bool:
        """测试价格工具类"""
        try:
            from mercari_agent.shared.utils.price_utils import (
                PriceParser, PriceFormatter, PriceValidator,
                parse_price, normalize_price, format_price
            )
            
            # 测试价格解析
            parser = PriceParser()
            result = await parser.parse_price_text("¥1,500")
            assert result is not None
            assert result.price is not None
            assert result.price.to_float() == 1500.0
            
            # 测试便利函数
            price = await parse_price("2000円")
            assert price is not None
            assert price.to_float() == 2000.0
            
            # 测试规范化
            normalized = await normalize_price("¥3,500")
            assert normalized == 3500.0
            
            # 测试格式化
            formatted = format_price(price)
            assert "¥" in formatted or "円" in formatted
            
            logger.info("价格工具类验证通过")
            return True
            
        except Exception as e:
            logger.error(f"价格工具类验证失败: {e}")
            return False
    
    async def test_timeout_utils(self) -> bool:
        """测试超时工具类"""
        try:
            from mercari_agent.shared.utils.timeout_utils import (
                TimeoutManager, execute_with_timeout, timeout_decorator
            )
            
            # 测试超时管理器
            manager = TimeoutManager(default_timeout=1.0)
            
            # 测试正常执行
            async def quick_task():
                await asyncio.sleep(0.1)
                return "success"
            
            result = await manager.execute_with_timeout(quick_task(), task_name="test_task")
            assert result == "success"
            
            # 测试超时
            async def slow_task():
                await asyncio.sleep(2.0)
                return "should_timeout"
            
            try:
                await manager.execute_with_timeout(slow_task(), timeout=0.5, task_name="slow_task")
                assert False, "应该超时"
            except asyncio.TimeoutError:
                pass  # 预期的超时异常
            
            # 测试装饰器
            @timeout_decorator(timeout=0.5)
            async def decorated_task():
                await asyncio.sleep(0.1)
                return "decorated_success"
            
            result = await decorated_task()
            assert result == "decorated_success"
            
            logger.info("超时工具类验证通过")
            return True
            
        except Exception as e:
            logger.error(f"超时工具类验证失败: {e}")
            return False
    
    def test_config_system(self) -> bool:
        """测试配置管理系统"""
        try:
            from mercari_agent.shared.config import (
                ConfigManager, EnvironmentConfigSource, DictConfigSource,
                ApplicationConfig, DatabaseConfig
            )
            
            # 测试配置管理器
            config_manager = ConfigManager()
            
            # 添加字典配置源
            test_config = {
                "app": {
                    "environment": "test",
                    "debug": True
                },
                "database": {
                    "host": "localhost",
                    "port": 5432
                }
            }
            config_manager.add_dict_source(test_config)
            
            # 测试配置获取
            env = config_manager.get_str("app.environment")
            assert env == "test"
            
            debug = config_manager.get_bool("app.debug")
            assert debug is True
            
            port = config_manager.get_int("database.port")
            assert port == 5432
            
            # 测试应用配置
            app_config = ApplicationConfig.from_config_manager(config_manager)
            assert app_config.environment == "test"
            assert app_config.debug is True
            assert app_config.database.host == "localhost"
            assert app_config.database.port == 5432
            
            logger.info("配置管理系统验证通过")
            return True
            
        except Exception as e:
            logger.error(f"配置管理系统验证失败: {e}")
            return False
    
    def generate_report(self) -> Dict[str, Any]:
        """生成验证报告"""
        return {
            "validation_summary": {
                "total_tests": len(self.test_results),
                "success_count": self.success_count,
                "failure_count": self.failure_count,
                "success_rate": f"{(self.success_count / len(self.test_results) * 100):.1f}%"
                if self.test_results else "0%"
            },
            "test_results": self.test_results,
            "validation_time": datetime.now().isoformat()
        }


def main():
    """主函数"""
    validator = MigrationValidator()
    
    print("=" * 60)
    print("Mercari AI Agent - 基础设施层迁移验证")
    print("=" * 60)
    
    success = validator.run_all_tests()
    
    print("\n" + "=" * 60)
    print("验证报告")
    print("=" * 60)
    
    report = validator.generate_report()
    summary = report["validation_summary"]
    
    print(f"总测试数: {summary['total_tests']}")
    print(f"成功: {summary['success_count']}")
    print(f"失败: {summary['failure_count']}")
    print(f"成功率: {summary['success_rate']}")
    
    if success:
        print("\n🎉 所有验证测试都通过了！基础设施层迁移成功。")
        return 0
    else:
        print("\n⚠️ 部分验证测试失败，请检查以上错误信息。")
        
        # 显示失败的测试
        failed_tests = [
            name for name, result in report["test_results"].items()
            if result["status"] != "success"
        ]
        if failed_tests:
            print(f"\n失败的测试: {', '.join(failed_tests)}")
        
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)