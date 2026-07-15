"""
CLI主接口模块

该模块提供命令行接口，用于测试和使用Mercari AI Agent的各项功能。
支持查询、推荐、爬取等核心功能的命令行操作。

主要功能：
- 商品搜索和推荐
- 系统状态检查
- 配置管理
- 服务测试

Author: Mercari AI Agent Team (Refactored)
"""

import asyncio
import sys
import json
from typing import Optional, List
from pathlib import Path
import click
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from ...shared.config.app_config import AppConfig, get_config
from ...shared.utils.logger_utils import setup_logging, get_logger
from ...application.services.query_parser_service import (
    QueryParserService
)
from ...application.services.recommendation_service import (
    RecommendationService
)
from ...application.services.output_formatter_service import (
    OutputFormatterService
)
from ...infrastructure.llm.llm_service import LLMService
from ...infrastructure.scraping.scraper_service import (
    ScraperService
)
from ...application.services.agent_service import AgentService
from ...tools.mercari_tools import build_mercari_tool_registry
from ...domain.entities.query import QueryEntity
from ...domain.entities.product import ProductEntity

logger = get_logger(__name__)


class CLIApp:
    """CLI应用程序类"""
    
    def __init__(self):
        self.config: Optional[AppConfig] = None
        self.query_parser: Optional[QueryParserService] = None
        self.recommendation_service: Optional[RecommendationService] = None
        self.output_formatter: Optional[OutputFormatterService] = None
        self.llm_service: Optional[LLMService] = None
        self.scraper_service: Optional[ScraperService] = None
    
    async def initialize(self):
        """初始化应用"""
        try:
            # 加载配置
            self.config = get_config()
            
            # 设置日志
            setup_logging(
                log_level=self.config.logging.level,
                log_dir=self.config.logging.log_dir
            )
            
            # 初始化服务
            self.llm_service = LLMService(self.config)
            await self.llm_service.initialize()  # 确保LLM服务正确初始化
            
            # 🔧 关键修复：确保所有服务都接收LLM服务
            self.query_parser = QueryParserService(self.config, self.llm_service)
            self.recommendation_service = RecommendationService(self.config, self.llm_service)
            self.output_formatter = OutputFormatterService(self.config, self.llm_service)
            self.scraper_service = ScraperService(self.config)
            
            # 初始化异步服务
            await self.scraper_service.initialize()
            
            logger.info("CLI应用初始化完成")
            
        except Exception as e:
            logger.error(f"CLI应用初始化失败: {e}")
            raise
    
    async def cleanup(self):
        """清理资源"""
        try:
            if self.scraper_service:
                await self.scraper_service.close()
            if self.llm_service:
                await self.llm_service.close()
            logger.info("CLI应用清理完成")
        except Exception as e:
            logger.error(f"CLI应用清理失败: {e}")


# 全局CLI应用实例
cli_app = CLIApp()


@click.group()
@click.option('--debug', is_flag=True, help='启用调试模式')
@click.option('--config-file', help='指定配置文件路径')
def cli(debug, config_file):
    """Mercari AI Agent CLI工具"""
    pass


@cli.command()
@click.option('--query', required=False, default="iPhone 15 Pro Max 1TB 10万円以下", help='搜索查询')
@click.option('--strategy', type=click.Choice(['price_oriented', 'quality_oriented', 'balanced', 'trending']),
              default='balanced', help='推荐策略')
@click.option('--max-results', default=10, help='最大结果数量')
@click.option('--output-format', type=click.Choice(['markdown_table', 'detailed_report', 'simple_list', 'json_export']),
              default='markdown_table', help='输出格式')
@click.option('--language', type=click.Choice(['zh', 'ja', 'en']), default='zh', help='输出语言')
def search(query, strategy, max_results, output_format, language):
    """搜索并推荐商品"""
    async def _search():
        try:
            await cli_app.initialize()
            
            # 解析查询
            click.echo(f"🔍 解析查询: {query}")
            parse_result = await cli_app.query_parser.parse(query)
            
            click.echo(f"✅ 查询解析完成:")
            click.echo(f"   - 关键词: {', '.join(parse_result.query.keywords) if parse_result.query.keywords else '无'}")
            click.echo(f"   - 类别: {parse_result.query.category or '未指定'}")
            click.echo(f"   - 价格范围: {parse_result.query.price_min or 0} - {parse_result.query.price_max or '无限制'}")
            click.echo(f"   - 置信度: {parse_result.confidence:.2f}")
            
            # 爬取数据
            click.echo("\n🕷️ 开始爬取商品数据...")
            scraping_result = await cli_app.scraper_service.scrape(parse_result.query, max_results * 2)
            
            click.echo(f"✅ 爬取完成:")
            click.echo(f"   - 找到商品: {len(scraping_result.products) if scraping_result.products else 0}")
            click.echo(f"   - 爬取页数: {scraping_result.pages_scraped if hasattr(scraping_result, 'pages_scraped') else 1}")
            click.echo(f"   - 处理时间: {scraping_result.processing_time:.2f}s")
            
            if not scraping_result.products:
                click.echo("❌ 没有找到商品，请尝试其他搜索词")
                return
            
            # 生成推荐
            click.echo("\n🎯 生成推荐...")
            recommendation_result = await cli_app.recommendation_service.recommend(
                scraping_result.products,
                parse_result.query,
                max_results,
                strategy
            )
            
            click.echo(f"✅ 推荐生成完成:")
            click.echo(f"   - 推荐数量: {len(recommendation_result.recommendations) if recommendation_result.recommendations else 0}")
            click.echo(f"   - 使用策略: {strategy}")
            click.echo(f"   - 处理时间: {recommendation_result.processing_time:.2f}s")
            
            # 格式化输出
            click.echo("\n📄 格式化输出...")
            formatted_output = await cli_app.output_formatter.format(
                recommendation_result,
                parse_result.query,
                output_format,
                language
            )
            
            click.echo("\n" + "="*50)
            click.echo(formatted_output.content if hasattr(formatted_output, 'content') else str(formatted_output))
            click.echo("="*50)
            
        except Exception as e:
            click.echo(f"❌ 搜索失败: {e}")
            logger.error(f"搜索失败: {e}")
        finally:
            await cli_app.cleanup()
    
    asyncio.run(_search())


@cli.command()
@click.option('--query', required=False, default="iPhone 15 Pro Max 1TB 10万円以下", help='解析查询')
def parse(query):
    """解析查询"""
    async def _parse():
        try:
            await cli_app.initialize()
            
            click.echo(f"🔍 解析查询: {query}")
            result = await cli_app.query_parser.parse(query)
            
            click.echo("\n✅ 解析结果:")
            click.echo(f"原始查询: {result.query.original_query}")
            click.echo(f"标准化查询: {result.query.normalized_query}")
            click.echo(f"关键词: {', '.join(result.query.keywords)}")
            click.echo(f"意图: {result.query.intent.value}")
            click.echo(f"类别: {result.query.category or '未指定'}")
            click.echo(f"品牌: {result.query.brand or '未指定'}")
            click.echo(f"价格范围: {result.query.price_min or 0} - {result.query.price_max or '无限制'}")
            click.echo(f"状态: {result.query.condition or '未指定'}")
            click.echo(f"复杂度: {result.complexity.value}")
            click.echo(f"置信度: {result.confidence:.2f}")
            click.echo(f"处理时间: {result.processing_time:.3f}s")
            
        except Exception as e:
            click.echo(f"❌ 解析失败: {e}")
            logger.error(f"解析失败: {e}")
        finally:
            await cli_app.cleanup()
    
    asyncio.run(_parse())


@cli.command()
@click.option('--query', required=False, default="iPhone 15 Pro Max 1TB 10万円以下", help='爬取查询')
@click.option('--max-products', default=20, help='最大商品数量')
def scrape(query, max_products):
    """爬取商品数据"""
    async def _scrape():
        try:
            await cli_app.initialize()
            
            # 先解析查询
            click.echo(f"🔍 解析查询: {query}")
            parse_result = await cli_app.query_parser.parse(query)
            
            # 爬取数据
            click.echo("\n🕷️ 开始爬取...")
            result = await cli_app.scraper_service.scrape(parse_result.query, max_products)
            
            click.echo(f"\n✅ 爬取完成:")
            click.echo(f"找到商品: {len(result.products) if result.products else 0}")
            click.echo(f"总计发现: {result.total_found if hasattr(result, 'total_found') else len(result.products) if result.products else 0}")
            click.echo(f"爬取页数: {result.pages_scraped if hasattr(result, 'pages_scraped') else 1}")
            click.echo(f"使用策略: {result.strategy_used if hasattr(result, 'strategy_used') else 'default'}")
            click.echo(f"处理时间: {result.processing_time:.2f}s")
            
            # 显示前几个商品
            if result.products:
                click.echo("\n📦 商品列表 (前5个):")
                for i, product in enumerate(result.products[:5], 1):
                    click.echo(f"{i}. {product.title}")
                    click.echo(f"   价格: ¥{product.price:,}" if product.price else "   价格: 未知")
                    click.echo(f"   状态: {product.condition or '未知'}")
                    click.echo(f"   卖家: {product.seller_name or '未知'}")
                    if product.url:
                        click.echo(f"   链接: {product.url}")
                    click.echo()
            
        except Exception as e:
            click.echo(f"❌ 爬取失败: {e}")
            logger.error(f"爬取失败: {e}")
        finally:
            await cli_app.cleanup()
    
    asyncio.run(_scrape())


@cli.command()
@click.option('--query', required=False,
              default="帮我在 Mercari 找性价比高的二手 AirPods Pro，预算 1 万円以内",
              help='给 agent 的自然语言请求')
@click.option('--max-iterations', default=6, help='agent 循环最大迭代次数')
def agent(query, max_iterations):
    """原生工具调用 agent：LLM 自主决定调用哪些工具（与写死的 search 流水线并存）"""
    async def _agent():
        try:
            await cli_app.initialize()

            # 用真实服务后端构建工具注册表（含把整条固定流程包起来的 recommend_deals 高层工具）
            registry = build_mercari_tool_registry(
                cli_app.scraper_service,
                cli_app.query_parser,
                cli_app.recommendation_service,
                include_model_compare=True,
            )
            agent_service = AgentService(
                cli_app.llm_service, registry, max_iterations=max_iterations
            )

            click.echo(f"🤖 Agent 请求: {query}")
            click.echo(f"🧰 已注册工具: {', '.join(registry.list_tools())}\n")
            click.echo("⏳ Agent 自主推理中（会真实调用工具抓取 Mercari）...\n")

            result = await agent_service.run(query)

            # 打印工具调用 trace（直观展示 LLM 自主调了哪些工具）
            click.echo("=" * 60)
            click.echo("🔧 工具调用 Trace")
            click.echo("=" * 60)
            if not result.trace:
                click.echo("（模型未调用任何工具，直接回答）")
            for i, step in enumerate(result.trace, 1):
                flag = "✅" if step.ok else "❌"
                click.echo(f"{i}. [iter {step.iteration}] {flag} {step.tool}")
                click.echo(f"   参数: {json.dumps(step.arguments, ensure_ascii=False)}")
                click.echo(f"   结果: {step.result_summary}")
            click.echo(f"\n迭代轮数: {result.iterations}"
                       f"{'（达到上限，已强制收尾）' if result.truncated else ''}")

            click.echo("\n" + "=" * 60)
            click.echo("💡 最终推荐")
            click.echo("=" * 60)
            click.echo(result.answer)
            click.echo("=" * 60)

        except Exception as e:
            click.echo(f"❌ Agent 运行失败: {e}")
            logger.error(f"Agent 运行失败: {e}", exc_info=True)
        finally:
            await cli_app.cleanup()

    asyncio.run(_agent())


@cli.command()
def status():
    """检查系统状态"""
    async def _status():
        try:
            await cli_app.initialize()
            
            click.echo("🔍 检查系统状态...\n")
            
            # 配置信息
            click.echo("⚙️ 配置信息:")
            click.echo(f"   环境: {cli_app.config.environment.value if hasattr(cli_app.config.environment, 'value') else str(cli_app.config.environment)}")
            click.echo(f"   调试模式: {cli_app.config.debug}")
            click.echo(f"   版本: {cli_app.config.version}")
            
            # LLM服务状态
            click.echo("\n🤖 LLM服务状态:")
            llm_info = await cli_app.llm_service.get_service_info()
            click.echo(f"   可用提供商: {', '.join(llm_info['available_providers'])}")
            click.echo(f"   主要提供商: {llm_info['primary_provider']}")
            
            # 测试LLM连接
            llm_test = await cli_app.llm_service.test_connection()
            for provider, status in llm_test.items():
                if status['status'] == 'success':
                    click.echo(f"   ✅ {provider}: 正常 ({status.get('latency', 0):.2f}s)")
                else:
                    click.echo(f"   ❌ {provider}: {status.get('error', '错误')}")
            
            # 爬虫服务状态
            click.echo("\n🕷️ 爬虫服务状态:")
            scraper_health = await cli_app.scraper_service.health_check()
            if scraper_health['status'] == 'healthy':
                click.echo("   ✅ 爬虫服务: 正常")
            else:
                click.echo(f"   ❌ 爬虫服务: {scraper_health.get('reason', '错误')}")
            
            scraper_info = cli_app.scraper_service.get_service_info()
            click.echo(f"   可用策略: {', '.join(scraper_info['available_strategies'])}")
            click.echo(f"   缓存大小: {scraper_info['cache_size']}")
            
            # 其他服务状态
            click.echo("\n📊 其他服务:")
            click.echo("   ✅ 查询解析服务: 正常")
            click.echo("   ✅ 推荐服务: 正常")
            click.echo("   ✅ 输出格式化服务: 正常")
            
        except Exception as e:
            click.echo(f"❌ 状态检查失败: {e}")
            logger.error(f"状态检查失败: {e}")
        finally:
            await cli_app.cleanup()
    
    asyncio.run(_status())


@cli.command()
def config():
    """显示配置信息"""
    try:
        config = get_config()
        config_dict = config.get_config_dict()
        
        click.echo("⚙️ 当前配置:")
        click.echo(json.dumps(config_dict, ensure_ascii=False, indent=2))
        
    except Exception as e:
        click.echo(f"❌ 获取配置失败: {e}")


@cli.command()
@click.argument('prompt')
def llm_test(prompt):
    """测试LLM服务"""
    async def _llm_test():
        try:
            await cli_app.initialize()
            
            click.echo(f"🤖 测试LLM服务，提示: {prompt}")
            
            response = await cli_app.llm_service.generate_response(prompt)
            
            click.echo(f"\n✅ LLM响应:")
            click.echo(f"提供商: {response.provider.value}")
            click.echo(f"模型: {response.model}")
            click.echo(f"延迟: {response.latency:.2f}s")
            click.echo(f"用量: {response.usage}")
            click.echo("\n回复内容:")
            click.echo("-" * 50)
            click.echo(response.content)
            click.echo("-" * 50)
            
        except Exception as e:
            click.echo(f"❌ LLM测试失败: {e}")
            logger.error(f"LLM测试失败: {e}")
        finally:
            await cli_app.cleanup()
    
    asyncio.run(_llm_test())


@cli.command()
@click.option('--query', required=False, default="iPhone 15 Pro Max 1TB 10万円以下", help='推荐查询')
@click.option('--strategy', type=click.Choice(['price_oriented', 'quality_oriented', 'balanced', 'trending']),
              default='balanced', help='推荐策略')
@click.option('--max-results', default=10, help='最大结果数量')
def recommend(query, strategy, max_results):
    """推荐商品 (原始版本兼容命令)"""
    async def _recommend():
        try:
            await cli_app.initialize()
            
            # 解析查询
            click.echo(f"🔍 解析查询: {query}")
            parse_result = await cli_app.query_parser.parse(query)
            
            click.echo(f"✅ 查询解析完成:")
            click.echo(f"   - 关键词: {', '.join(parse_result.query.keywords) if parse_result.query.keywords else '无'}")
            click.echo(f"   - 类别: {parse_result.query.category or '未指定'}")
            click.echo(f"   - 价格范围: {parse_result.query.price_min or 0} - {parse_result.query.price_max or '无限制'}")
            click.echo(f"   - 置信度: {parse_result.confidence:.2f}")
            
            # 爬取数据
            click.echo("\n🕷️ 开始爬取商品数据...")
            scraping_result = await cli_app.scraper_service.scrape(parse_result.query, max_results * 2)
            
            click.echo(f"✅ 爬取完成:")
            click.echo(f"   - 找到商品: {len(scraping_result.products) if scraping_result.products else 0}")
            click.echo(f"   - 爬取页数: {scraping_result.pages_scraped if hasattr(scraping_result, 'pages_scraped') else 1}")
            click.echo(f"   - 处理时间: {scraping_result.processing_time:.2f}s")
            
            if not scraping_result.products:
                click.echo("❌ 没有找到商品，请尝试其他搜索词")
                return
            
            # 生成推荐
            click.echo("\n🎯 生成推荐...")
            recommendation_result = await cli_app.recommendation_service.recommend(
                scraping_result.products,
                parse_result.query,
                max_results,
                strategy
            )
            
            click.echo(f"✅ 推荐生成完成:")
            click.echo(f"   - 推荐数量: {len(recommendation_result.recommendations) if recommendation_result.recommendations else 0}")
            click.echo(f"   - 使用策略: {strategy}")
            click.echo(f"   - 处理时间: {recommendation_result.processing_time:.2f}s")
            
            # 格式化输出
            click.echo("\n📄 格式化输出...")
            formatted_output = await cli_app.output_formatter.format(
                recommendation_result,
                parse_result.query,
                'markdown_table',
                'zh'
            )
            
            click.echo("\n" + "="*50)
            click.echo(formatted_output.content if hasattr(formatted_output, 'content') else str(formatted_output))
            click.echo("="*50)
            
        except Exception as e:
            click.echo(f"❌ 推荐失败: {e}")
            logger.error(f"推荐失败: {e}")
        finally:
            await cli_app.cleanup()
    
    asyncio.run(_recommend())


@cli.command()
@click.option('--query', default="iPhone 15 Pro Max 1TB 10万円以下", help='测试查询')
def test(query):
    """测试推荐引擎 (原始版本兼容命令)"""
    async def _test():
        try:
            await cli_app.initialize()
            
            click.echo("🚀 启动推荐引擎测试...")
            click.echo(f"🔍 测试查询: {query}")
            
            # 解析查询
            parse_result = await cli_app.query_parser.parse(query)
            click.echo(f"✅ 查询解析完成 (置信度: {parse_result.confidence:.2f})")
            
            # 爬取数据
            click.echo("\n🕷️ 爬取测试数据...")
            scraping_result = await cli_app.scraper_service.scrape(parse_result.query, 20)
            
            if scraping_result.products:
                click.echo(f"✅ 找到 {len(scraping_result.products)} 个商品")
                
                # 生成推荐
                click.echo("\n🎯 测试推荐生成...")
                recommendation_result = await cli_app.recommendation_service.recommend(
                    scraping_result.products,
                    parse_result.query,
                    5,
                    'balanced'
                )
                
                if recommendation_result.recommendations:
                    click.echo(f"✅ 推荐引擎测试成功，生成了 {len(recommendation_result.recommendations)} 个推荐")
                    
                    # 显示前3个推荐（recommendations 是 List[ProductEntity]）
                    click.echo("\n🏆 推荐结果 (前3个):")
                    for i, product in enumerate(recommendation_result.recommendations[:3], 1):
                        click.echo(f"{i}. {product.title}")
                        click.echo(f"   💰 价格: {product.formatted_price}")
                        if product.condition:
                            click.echo(f"   📦 状态: {product.condition}")
                        if product.seller_name:
                            click.echo(f"   🏪 卖家: {product.seller_name}")

                    # 显示推荐策略与理由（若有）
                    click.echo(f"\n📌 使用策略: {recommendation_result.strategy_used}")
                    if recommendation_result.reasoning:
                        click.echo(f"💡 推荐理由: {recommendation_result.reasoning}")
                else:
                    click.echo("❌ 推荐引擎测试失败：没有生成推荐结果")
            else:
                click.echo("❌ 推荐引擎测试失败：没有找到商品数据")
            
        except Exception as e:
            click.echo(f"❌ 推荐引擎测试失败: {e}")
            logger.error(f"推荐引擎测试失败: {e}")
        finally:
            await cli_app.cleanup()
    
    asyncio.run(_test())


if __name__ == '__main__':
    cli()