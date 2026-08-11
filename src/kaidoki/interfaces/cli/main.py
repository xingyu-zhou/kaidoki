"""
CLI主接口模块

该模块提供命令行接口，用于测试和使用Kaidoki的各项功能。
支持查询、推荐、爬取等核心功能的命令行操作。

主要功能：
- 商品搜索和推荐
- 系统状态检查
- 配置管理
- 服务测试

Author: Kaidoki Team (Refactored)
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
from ...application.services.benchmark_service import (
    SCORING_VERSION,
    BenchmarkService,
    load_records,
    rescore_record,
    summarize,
)
from ...infrastructure.search.google_search import GoogleCseClient
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
    """Kaidoki CLI工具"""
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
@click.option('--trace-file', default=None, type=click.Path(dir_okay=False),
              help='把完整过程（system prompt / 每轮推理 / 每次工具调用的完整入参与返回 / '
                   '完整对话）写成 JSON，用于事后复盘和改 prompt')
@click.option('--result-chars', default=1200, show_default=True,
              help='终端上每次工具返回打印多少字符（完整内容用 --trace-file 落盘）')
@click.option('--google-benchmark/--no-google-benchmark', default=False, show_default=True,
              help='跑完后额外记一份 Google 检索结果作对照基线（只用于打分，不进 agent 的输入）。'
                   '**默认关闭**：Custom Search API 侧还没跑通，且核心比较语义仍在打磨中，'
                   '先不让一个未验证的记分板产生误导性的战绩。需要时显式加此 flag')
def agent(query, max_iterations, trace_file, result_chars, google_benchmark):
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

            # ---- 完整过程：按迭代轮把「模型怎么想的」和「工具返回了什么」交错打出 ----
            # 只打摘要会藏掉判断依据（newer_lookup / confidence / warnings /
            # condition_filter 都在细节里），复盘时看不出结论错在哪一环。
            click.echo("=" * 60)
            click.echo("🔍 执行过程（模型推理 + 工具调用）")
            click.echo("=" * 60)
            if not result.trace and not result.notes:
                click.echo("（模型未调用任何工具，直接回答）")

            steps_by_iter = {}
            for step in result.trace:
                steps_by_iter.setdefault(step.iteration, []).append(step)

            for note in result.notes:
                it = note["iteration"]
                click.echo(f"\n── iter {it} ──")
                if note["text"].strip():
                    click.echo("🧠 模型判断:")
                    for line in note["text"].strip().splitlines():
                        click.echo(f"   {line}")
                else:
                    click.echo("🧠 模型判断: （无文字，直接调工具）")
                called = [t for t in note["tools_called"] if t]
                click.echo(f"🧰 本轮调用: {', '.join(called) if called else '（无，输出最终回答）'}")

                for j, step in enumerate(steps_by_iter.get(it, []), 1):
                    flag = "✅" if step.ok else "❌"
                    click.echo(f"\n  {j}) {flag} {step.tool}  ({step.duration_ms} ms)")
                    click.echo(f"     入参: {json.dumps(step.arguments, ensure_ascii=False)}")
                    click.echo(f"     摘要: {step.result_summary}")
                    body = step.result_full or ""
                    shown = body[:result_chars]
                    click.echo("     返回: " + shown.replace("\n", "\n           "))
                    if len(body) > len(shown):
                        click.echo(f"     …（已截断 {len(body) - len(shown)} 字符，"
                                   f"完整内容见 --trace-file）")

            click.echo(f"\n迭代轮数: {result.iterations}"
                       f"{'（达到上限，已强制收尾）' if result.truncated else ''}")

            # 无来源的价格：prompt 规则管不住模型编价格，这道检查能让它可见
            if result.ungrounded_prices:
                click.echo("\n⚠️  回答里有工具返回中查不到的金额（可能是模型自有知识）:")
                for p in result.ungrounded_prices:
                    click.echo(f"     ¥{p:,}")
                click.echo("     → 这些数字没有来源，使用前请自行核对")

            if trace_file:
                payload = result.to_dict()
                payload["query"] = query
                payload["system_prompt"] = agent_service.system_prompt
                payload["registered_tools"] = registry.list_tools()
                path = Path(trace_file)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8",
                )
                click.echo(f"📄 完整过程已写入: {path}")

            click.echo("\n" + "=" * 60)
            click.echo("💡 最终推荐")
            click.echo("=" * 60)
            click.echo(result.answer)
            click.echo("=" * 60)

            # ---- Google 对照基线 ----
            # 放在最后、包在自己的 try 里：推荐已经拿到了，打分失败绝不能连带毁掉它。
            # 只读 result，不回写 result.messages —— 否则模型下次会抄 Google 的数字。
            if google_benchmark:
                try:
                    await _run_google_benchmark(query, result)
                except Exception as e:  # noqa: BLE001
                    click.echo(f"⚠️  Google 对照失败（不影响以上推荐）: {e}")
                    logger.warning(f"Google 对照失败: {e}", exc_info=True)

        except Exception as e:
            click.echo(f"❌ Agent 运行失败: {e}")
            logger.error(f"Agent 运行失败: {e}", exc_info=True)
        finally:
            await cli_app.cleanup()

    asyncio.run(_agent())


def _benchmark_config():
    """拿 BenchmarkConfig。

    `benchmark` 子命令不需要 LLM/浏览器，因此不走 cli_app.initialize()，
    那时 cli_app.config 还是 None —— 直接 get_config()，否则会静默忽略
    BENCHMARK_PATH 之类的环境变量、去读一个错误的默认路径。
    """
    if getattr(cli_app, "config", None) is not None:
        return cli_app.config.benchmark
    return get_config().benchmark


def _verdict_icon(verdict: str) -> str:
    return {"win": "🏆", "tie": "🤝", "loss": "❌", "n/a": "➖"}.get(verdict, "➖")


def _print_comparison(label: str, comp: dict) -> None:
    """打一段对照结果。loss 时把漏项列出来 —— 那才是要改的东西。"""
    verdict = comp.get("verdict", "n/a")
    click.echo(f"  [{label}] {_verdict_icon(verdict)} {verdict.upper()} — {comp.get('reason', '')}")
    if comp.get("our_best"):
        ob = comp["our_best"]
        extra = f" [{'/'.join(ob.get('model_nos') or []) or '型番不明'}]"
        click.echo(f"     我方最低: ¥{ob['price']:,} ({ob.get('source')}){extra} "
                   f"{ob.get('title', '')[:40]}")
    if comp.get("google_best"):
        gb = comp["google_best"]
        mark = "" if gb.get("verified") else " ⚠未核验(摘要提取)"
        click.echo(f"     Google 最低: ¥{gb['price']:,} #{gb.get('rank')}{mark} "
                   f"{gb.get('title', '')[:40]}")
    # 同型番才谈得上"谁更便宜"。不同型号之间的价差里混着规格差异，
    # 只看数字会得出反向结论（实测 kakaku ¥28,000 的是 Lightning 版旧款尾货）。
    kind = comp.get("comparability")
    if kind == "different_model":
        click.echo("     ⚠ 双方最低价不是同一型番 —— 价差含规格差异，不能当性价比结论")
    elif kind == "unknown":
        click.echo("     ⚠ 至少一侧未注明型番 —— 无法确认是否同款")
    # 只有真拿到 Google 数据才谈排名。取数失败时这个键根本不存在 ——
    # 若照样打"未出现在 top-N"，会被误读成"查过了、确实没有"，正是要避免的那类假结论。
    if "our_pick_google_rank" in comp:
        rank = comp["our_pick_google_rank"]
        click.echo(f"     我方推荐在 Google 的排名: {rank if rank else '未出现在 top-N'}")
    for m in (comp.get("miss") or [])[:3]:
        mark = "" if m.get("verified") else " ⚠未核验"
        click.echo(f"     ↳ 漏项 #{m['rank']} ¥{m['price']:,}{mark} {m.get('title', '')[:40]}")
        click.echo(f"        {m.get('link', '')}")


async def _run_google_benchmark(query: str, result) -> None:
    """跑一次 Google 对照并打摘要。未配 key 就提示一句后跳过。"""
    bench_cfg = _benchmark_config()
    client = GoogleCseClient(
        api_key=bench_cfg.google_api_key,
        cse_id=bench_cfg.google_cse_id,
        top_n=bench_cfg.serp_top_n,
        ca_bundle=bench_cfg.ca_bundle,
    )
    output = Path(bench_cfg.output_path)
    service = BenchmarkService(client, output)

    if not service.enabled:
        click.echo("\n➖ Google 对照未启用（未配置 GOOGLE_API_KEY / GOOGLE_CSE_ID）")
        return

    click.echo("\n" + "=" * 60)
    click.echo("📊 Google 对照基线（google_cse，不参与 agent 推理）")
    click.echo("=" * 60)
    record = await service.compare(query, result)
    click.echo(f"原样 query: {record.get('raw_query')}")
    click.echo(f"公平 query: {record.get('fair_query') or '（未能从 trace 构造）'}")
    for label in ("fair", "raw"):
        comp = (record.get("comparisons") or {}).get(label)
        if comp:
            _print_comparison(label, comp)
    click.echo(f"📄 已追加到: {output}")


@cli.command()
@click.option('--last', default=10, show_default=True, help='显示最近 N 条')
@click.option('--key', type=click.Choice(['fair', 'raw']), default='fair', show_default=True,
              help='用哪份 query 的分数统计（fair = 日文型号+最安値，基线更硬）')
@click.option('--rescore', is_flag=True,
              help='用当前打分逻辑重算历史记录（从已存的原始结果算，不再打 Google API）')
@click.option('--write', is_flag=True,
              help='配合 --rescore：把重算结果写回文件（会覆盖原文件）')
def benchmark(last, key, rescore, write):
    """查看 / 重算 Google 对照记分板"""
    path = Path(_benchmark_config().output_path)
    records = load_records(path)
    if not records:
        click.echo(f"暂无记录: {path}")
        return

    if rescore:
        records = [rescore_record(r) for r in records]
        click.echo(f"♻️  已用当前打分逻辑（scoring_version={SCORING_VERSION}）重算 {len(records)} 条")
        if write:
            path.write_text(
                "".join(json.dumps(r, ensure_ascii=False, default=str) + "\n" for r in records),
                encoding="utf-8",
            )
            click.echo(f"💾 已写回 {path}")

    stats = summarize(records, key=key)
    click.echo(f"\n📊 记分板（{path}，按 {key} query 统计）")
    click.echo(f"   共 {stats['total']} 条，其中可判定 {stats['decided']} 条")
    click.echo(f"   🏆 win {stats['win']}  🤝 tie {stats['tie']}  ❌ loss {stats['loss']}"
               f"  ➖ n/a {stats['n/a']}")
    if stats["win_rate"] is not None:
        click.echo(f"   胜率: {stats['win_rate']:.1%}")

    click.echo(f"\n最近 {min(last, len(records))} 条:")
    for r in records[-last:]:
        comp = (r.get("comparisons") or {}).get(key) or {}
        verdict = comp.get("verdict", "n/a")
        click.echo(f"\n─ {r.get('ts')}  {_verdict_icon(verdict)} {verdict.upper()}")
        click.echo(f"  query: {r.get('raw_query')}")
        if comp:
            _print_comparison(key, comp)


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