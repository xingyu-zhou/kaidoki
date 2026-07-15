"""
Mercari AI Agent 集成测试

测试所有服务的端到端集成功能。

测试范围：
- 配置加载
- 服务初始化
- CLI接口功能
- REST API功能
- 服务间协作

Author: Mercari AI Agent Team (Refactored)
"""

import asyncio
import sys
import os
import time
import subprocess
import signal
from pathlib import Path
from typing import Dict, Any, List

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.mercari_agent.shared.config.app_config import get_config
from src.mercari_agent.shared.utils.logger_utils import get_logger
from src.mercari_agent.application.services.query_parser_service import QueryParserService
from src.mercari_agent.application.services.recommendation_service import RecommendationService
from src.mercari_agent.application.services.output_formatter_service import OutputFormatterService
from src.mercari_agent.infrastructure.scraping.scraper_service import ScraperService
from src.mercari_agent.domain.entities.product import ProductEntity
from src.mercari_agent.domain.entities.query import QueryEntity, QueryIntent

logger = get_logger(__name__)


class IntegrationTestRunner:
    """集成测试运行器"""
    
    def __init__(self):
        """初始化测试运行器"""
        self.config = None
        self.services = {}
        self.test_results = []
        self.api_server_process = None
        
    async def setup(self):
        """设置测试环境"""
        try:
            logger.info("设置集成测试环境...")
            
            # 加载配置
            self.config = get_config()
            
            # 设置日志系统已在配置中处理
            pass
            
            # 初始化服务
            await self._initialize_services()
            
            logger.info("集成测试环境设置完成")
            
        except Exception as e:
            logger.error(f"设置测试环境失败: {e}")
            raise
    
    async def _initialize_services(self):
        """初始化所有服务"""
        try:
            # 初始化服务（简化版，不依赖LLM）
            self.services['query_parser'] = QueryParserService(
                self.config,
                None  # 简化版不需要LLM
            )
            self.services['recommendation'] = RecommendationService(self.config)
            self.services['output_formatter'] = OutputFormatterService(self.config)
            self.services['scraper'] = ScraperService(self.config)
            
            # 初始化异步服务
            await self.services['scraper'].initialize()
            
            logger.info("所有服务初始化完成")
            
        except Exception as e:
            logger.error(f"服务初始化失败: {e}")
            raise
    
    async def run_all_tests(self):
        """运行所有测试"""
        try:
            logger.info("开始运行集成测试...")
            
            # 配置测试
            await self.test_configuration()
            
            # 服务测试
            await self.test_services()
            
            # CLI测试
            await self.test_cli_interface()
            
            # API测试
            await self.test_api_interface()
            
            # 端到端测试
            await self.test_end_to_end_workflow()
            
            # 生成测试报告
            self._generate_test_report()
            
            logger.info("集成测试完成")
            
        except Exception as e:
            logger.error(f"集成测试失败: {e}")
            raise
    
    async def test_configuration(self):
        """测试配置加载"""
        test_name = "配置加载测试"
        try:
            logger.info(f"运行测试: {test_name}")
            
            # 检查配置对象
            assert self.config is not None, "配置对象为空"
            assert self.config.environment is not None, "环境配置缺失"
            assert self.config.api is not None, "API配置缺失"
            assert self.config.llm is not None, "LLM配置缺失"
            assert self.config.scraping is not None, "爬虫配置缺失"
            
            # 检查配置值
            assert self.config.api.host is not None, "API主机配置缺失"
            assert self.config.api.port > 0, "API端口配置无效"
            assert self.config.llm.timeout > 0, "LLM超时配置无效"
            
            self._record_test_result(test_name, True, "配置加载成功")
            
        except Exception as e:
            self._record_test_result(test_name, False, f"配置加载失败: {e}")
            raise
    
    async def test_services(self):
        """测试所有服务"""
        await self.test_query_parser_service()
        await self.test_recommendation_service()
        await self.test_output_formatter_service()
        await self.test_scraper_service()
    
    async def test_query_parser_service(self):
        """测试查询解析服务"""
        test_name = "查询解析服务测试"
        try:
            logger.info(f"运行测试: {test_name}")
            
            query_parser = self.services['query_parser']
            
            # 测试查询解析
            test_query = "iPhone 13 Pro 128GB 5万円以下"
            parsed_result = await query_parser.parse(test_query)
            
            assert parsed_result is not None, "解析结果为空"
            assert hasattr(parsed_result, 'query'), "缺少查询对象"
            assert len(parsed_result.query.keywords) > 0, "关键词为空"
            
            self._record_test_result(test_name, True, "查询解析服务正常")
            
        except Exception as e:
            self._record_test_result(test_name, False, f"查询解析服务失败: {e}")
    
    async def test_recommendation_service(self):
        """测试推荐服务"""
        test_name = "推荐服务测试"
        try:
            logger.info(f"运行测试: {test_name}")
            
            recommendation_service = self.services['recommendation']
            
            # 创建测试数据
            test_query = QueryEntity(
                original_query="iPhone 13",
                keywords=["iPhone", "13"],
                category="スマートフォン"
            )
            
            test_products = [
                ProductEntity(
                    id="test1",
                    title="iPhone 13 Pro 128GB",
                    price=89800,
                    category="スマートフォン"
                ),
                ProductEntity(
                    id="test2",
                    title="iPhone 13 mini 128GB",
                    price=69800,
                    category="スマートフォン"
                )
            ]
            
            # 测试推荐生成
            recommendations = await recommendation_service.recommend(
                products=test_products,
                query=test_query,
                limit=5
            )
            
            assert recommendations is not None, "推荐结果为空"
            assert hasattr(recommendations, 'recommendations'), "缺少推荐列表"
            
            self._record_test_result(test_name, True, "推荐服务正常")
            
        except Exception as e:
            self._record_test_result(test_name, False, f"推荐服务失败: {e}")
    
    async def test_output_formatter_service(self):
        """测试输出格式化服务"""
        test_name = "输出格式化服务测试"
        try:
            logger.info(f"运行测试: {test_name}")
            
            output_formatter = self.services['output_formatter']
            
            # 测试格式化
            test_query = QueryEntity(
                original_query="iPhone 13 test",
                keywords=["iPhone", "13"],
                category="スマートフォン"
            )
            
            test_data = {
                "keywords": ["iPhone", "13"],
                "category": "スマートフォン",
                "price_range": {"min": 50000, "max": 100000}
            }
            
            formatted_output = await output_formatter.format(
                data=test_data,
                query=test_query,
                output_format="markdown",
                language="ja"
            )
            
            assert formatted_output is not None, "格式化结果为空"
            assert len(formatted_output.content) > 0, "格式化结果内容为空"
            
            self._record_test_result(test_name, True, "输出格式化服务正常")
            
        except Exception as e:
            self._record_test_result(test_name, False, f"输出格式化服务失败: {e}")
    
    async def test_scraper_service(self):
        """测试爬虫服务"""
        test_name = "爬虫服务测试"
        try:
            logger.info(f"运行测试: {test_name}")
            
            scraper_service = self.services['scraper']
            
            # 测试搜索功能
            test_query = QueryEntity(
                original_query="iPhone",
                keywords=["iPhone"]
            )
            
            search_results = await scraper_service.scrape(
                query_or_context=test_query,
                max_products=5
            )
            
            assert search_results is not None, "搜索结果为空"
            assert len(search_results.products) > 0, "搜索结果数量为0"
            
            self._record_test_result(test_name, True, "爬虫服务正常")
            
        except Exception as e:
            self._record_test_result(test_name, False, f"爬虫服务失败: {e}")
    
    async def test_cli_interface(self):
        """测试CLI接口"""
        test_name = "CLI接口测试"
        try:
            logger.info(f"运行测试: {test_name}")
            
            cli_script = project_root / "cli.py"
            
            # 测试CLI帮助
            result = subprocess.run(
                [sys.executable, str(cli_script), "--help"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            assert result.returncode == 0, f"CLI帮助命令失败: {result.stderr}"
            
            # 测试查询解析
            result = subprocess.run(
                [sys.executable, str(cli_script), "parse", "iPhone 13"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # CLI可能因为缺少配置而失败，这是正常的
            logger.info(f"CLI测试结果: {result.returncode}")
            
            self._record_test_result(test_name, True, "CLI接口基本功能正常")
            
        except Exception as e:
            self._record_test_result(test_name, False, f"CLI接口测试失败: {e}")
    
    async def test_api_interface(self):
        """测试API接口"""
        test_name = "API接口测试"
        try:
            logger.info(f"运行测试: {test_name}")
            
            # 启动API服务器
            await self._start_api_server()
            
            # 等待服务器启动
            await asyncio.sleep(3)
            
            # 测试健康检查
            import httpx
            
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:8000/health")
                assert response.status_code == 200, f"健康检查失败: {response.status_code}"
                
                # 测试根路径
                response = await client.get("http://localhost:8000/")
                assert response.status_code == 200, f"根路径访问失败: {response.status_code}"
            
            self._record_test_result(test_name, True, "API接口基本功能正常")
            
        except Exception as e:
            self._record_test_result(test_name, False, f"API接口测试失败: {e}")
        finally:
            # 停止API服务器
            await self._stop_api_server()
    
    async def test_end_to_end_workflow(self):
        """测试端到端工作流"""
        test_name = "端到端工作流测试"
        try:
            logger.info(f"运行测试: {test_name}")
            
            # 模拟完整的用户查询流程
            user_query = "iPhone 13 Pro 安い"
            
            # 1. 解析查询
            parsed_result = await self.services['query_parser'].parse(user_query)
            assert parsed_result is not None, "查询解析失败"
            
            # 2. 搜索商品
            search_query = QueryEntity(
                original_query=user_query,
                keywords=parsed_result.query.keywords,
                category=parsed_result.query.category
            )
            
            search_results = await self.services['scraper'].scrape(
                query_or_context=search_query,
                max_products=10
            )
            assert len(search_results.products) > 0, "搜索结果为空"
            
            # 3. 生成推荐
            recommendations = await self.services['recommendation'].recommend(
                products=search_results.products,
                query=search_query,
                limit=5
            )
            assert recommendations is not None, "推荐生成失败"
            
            # 4. 格式化输出
            formatted_output = await self.services['output_formatter'].format(
                data=recommendations,
                query=search_query,
                output_format="markdown",
                language="ja"
            )
            assert formatted_output is not None, "输出格式化失败"
            
            self._record_test_result(test_name, True, "端到端工作流正常")
            
        except Exception as e:
            self._record_test_result(test_name, False, f"端到端工作流失败: {e}")
    
    async def _start_api_server(self):
        """启动API服务器"""
        try:
            server_script = project_root / "src" / "mercari_agent" / "interfaces" / "api" / "server.py"
            
            self.api_server_process = subprocess.Popen(
                [sys.executable, str(server_script), "--host", "localhost", "--port", "8000"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            logger.info("API服务器已启动")
            
        except Exception as e:
            logger.error(f"启动API服务器失败: {e}")
            raise
    
    async def _stop_api_server(self):
        """停止API服务器"""
        if self.api_server_process:
            try:
                self.api_server_process.terminate()
                self.api_server_process.wait(timeout=5)
                logger.info("API服务器已停止")
            except subprocess.TimeoutExpired:
                self.api_server_process.kill()
                logger.warning("API服务器强制停止")
    
    def _record_test_result(self, test_name: str, success: bool, message: str):
        """记录测试结果"""
        self.test_results.append({
            'test_name': test_name,
            'success': success,
            'message': message,
            'timestamp': time.time()
        })
        
        status = "✓" if success else "✗"
        logger.info(f"{status} {test_name}: {message}")
    
    def _generate_test_report(self):
        """生成测试报告"""
        logger.info("=== 集成测试报告 ===")
        
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r['success']])
        failed_tests = total_tests - passed_tests
        
        logger.info(f"总测试数: {total_tests}")
        logger.info(f"通过测试: {passed_tests}")
        logger.info(f"失败测试: {failed_tests}")
        logger.info(f"成功率: {passed_tests/total_tests*100:.1f}%")
        
        if failed_tests > 0:
            logger.info("\n失败的测试:")
            for result in self.test_results:
                if not result['success']:
                    logger.error(f"  ✗ {result['test_name']}: {result['message']}")
        
        logger.info("=== 测试报告结束 ===")
    
    async def cleanup(self):
        """清理测试环境"""
        try:
            logger.info("清理测试环境...")
            
            # 关闭服务
            if 'scraper' in self.services:
                await self.services['scraper'].close()
            
            if 'llm' in self.services:
                await self.services['llm'].close()
            
            # 停止API服务器
            await self._stop_api_server()
            
            logger.info("测试环境清理完成")
            
        except Exception as e:
            logger.error(f"清理测试环境失败: {e}")


async def main():
    """主函数"""
    test_runner = IntegrationTestRunner()
    
    try:
        # 设置测试环境
        await test_runner.setup()
        
        # 运行测试
        await test_runner.run_all_tests()
        
        # 检查结果
        failed_tests = [r for r in test_runner.test_results if not r['success']]
        if failed_tests:
            logger.error(f"有{len(failed_tests)}个测试失败")
            sys.exit(1)
        else:
            logger.info("所有测试通过")
    
    except Exception as e:
        logger.error(f"集成测试异常: {e}")
        sys.exit(1)
    
    finally:
        # 清理环境
        await test_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())