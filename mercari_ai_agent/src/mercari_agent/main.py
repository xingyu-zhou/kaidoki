"""
Mercari AI Agent 主入口文件

该文件展示了如何集成和使用整个LLM增强的工具调用系统。

主要功能：
- 初始化所有核心组件
- 演示完整的查询处理流程
- 提供命令行接口
- 系统健康检查

Author: Mercari AI Agent Team
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import argparse
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 导入核心组件
from src.mercari_agent.config.settings import Settings, load_settings
from src.mercari_agent.services.llm_service import LLMService
from src.mercari_agent.core.tools.tool_registry import ToolRegistry
from src.mercari_agent.core.tools.search_tools import SearchMercariTool, QueryAnalyzerTool, CategorySuggestTool, SearchTools
from src.mercari_agent.core.tools.analysis_tools import ProductAnalysisTool, PriceAnalysisTool, ProductComparisonTool, RecommendationTool, AnalysisTools
from src.mercari_agent.core.tools.formatting_tools import ProductSummaryTool, ComparisonTableTool, RecommendationReportTool, DataVisualizationTool, TextFormattingTool, FormattingTools
from src.mercari_agent.core.query_parser import QueryParser
from src.mercari_agent.core.tool_orchestrator import (
    ToolOrchestrator,
    ToolExecutionContext,
    ToolExecutionResult
)
from src.mercari_agent.services.scraper_service import ScraperService
from src.mercari_agent.services.analysis_service import AnalysisService
from src.mercari_agent.core.output_formatter import OutputFormatter
from src.mercari_agent.utils.logger import get_logger

logger = get_logger(__name__)


class MercariAIAgent:
    """
    Mercari AI Agent 主类
    
    集成所有组件，提供统一的接口
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """初始化AI Agent"""
        self.settings = settings or load_settings()
        self.llm_service = None
        self.tool_registry = None
        self.query_parser = None
        self.orchestrator = None
        self.scraper_service = None
        self.analysis_service = None
        
        # 初始化标志
        self.initialized = False
    
    async def initialize(self):
        """异步初始化所有组件"""
        from src.mercari_agent.utils.timeout_manager import global_timeout_manager
        
        logger.info("开始初始化Mercari AI Agent...")
        
        try:
            # 1. 初始化LLM服务（使用超时控制）
            logger.info("初始化LLM服务...")
            self.llm_service = await global_timeout_manager.with_timeout(
                self._init_llm_service(),
                timeout=30,
                task_name="LLM服务初始化"
            )
            
            # 2. 初始化其他服务（使用超时控制）
            logger.info("初始化爬虫服务...")
            self.scraper_service = await global_timeout_manager.with_timeout(
                self._init_scraper_service(),
                timeout=10,
                task_name="爬虫服务初始化"
            )
            
            logger.info("初始化分析服务...")
            self.analysis_service = await global_timeout_manager.with_timeout(
                self._init_analysis_service(),
                timeout=10,
                task_name="分析服务初始化"
            )
            
            # 3. 初始化工具注册表（使用超时控制）
            logger.info("初始化工具注册表...")
            self.tool_registry = ToolRegistry()
            
            # 注册工具
            await global_timeout_manager.with_timeout(
                self._register_tools(),
                timeout=20,
                task_name="工具注册"
            )
            
            # 4. 初始化查询解析器（使用超时控制）
            logger.info("初始化查询解析器...")
            self.query_parser = await global_timeout_manager.with_timeout(
                self._init_query_parser(),
                timeout=10,
                task_name="查询解析器初始化"
            )
            
            # 5. 初始化工具编排器（使用超时控制）
            logger.info("初始化工具编排器...")
            self.orchestrator = await global_timeout_manager.with_timeout(
                self._init_orchestrator(),
                timeout=10,
                task_name="工具编排器初始化"
            )
            
            self.initialized = True
            logger.info("✅ Mercari AI Agent初始化完成!")
            
        except Exception as e:
            logger.error(f"❌ 初始化失败: {e}")
            # 清理部分初始化的组件
            await self._cleanup_partial_init()
            raise
    
    async def _init_llm_service(self):
        """初始化LLM服务"""
        logger.info("正在初始化LLM服务...")
        return LLMService(self.settings.llm)
    
    async def _init_scraper_service(self):
        """初始化爬虫服务"""
        logger.info("正在初始化爬虫服务...")
        return ScraperService()
    
    async def _init_analysis_service(self):
        """初始化分析服务"""
        logger.info("正在初始化分析服务...")
        return AnalysisService()
    
    async def _init_query_parser(self):
        """初始化查询解析器"""
        logger.info("正在初始化查询解析器...")
        return QueryParser(self.llm_service)
    
    async def _init_orchestrator(self):
        """初始化工具编排器"""
        logger.info("正在初始化工具编排器...")
        return ToolOrchestrator(
            llm_service=self.llm_service,
            scraper_service=self.scraper_service,
            analysis_service=self.analysis_service,
            output_formatter=OutputFormatter()
        )
    
    async def _register_tools(self):
        """注册所有工具"""
        logger.info("注册工具...")
        
        # 搜索工具
        search_tool = SearchMercariTool(self.scraper_service)
        self.tool_registry.register(search_tool)
        
        query_tool = QueryAnalyzerTool(self.llm_service)
        self.tool_registry.register(query_tool)
        
        category_tool = CategorySuggestTool(self.llm_service)
        self.tool_registry.register(category_tool)
        
        # 分析工具
        analysis_tool = ProductAnalysisTool(self.analysis_service, self.llm_service)
        self.tool_registry.register(analysis_tool)
        
        price_tool = PriceAnalysisTool(self.analysis_service, self.llm_service)
        self.tool_registry.register(price_tool)
        
        comparison_tool = ProductComparisonTool(self.analysis_service, self.llm_service)
        self.tool_registry.register(comparison_tool)
        
        # 格式化工具
        summary_tool = ProductSummaryTool(self.llm_service)
        self.tool_registry.register(summary_tool)
        
        text_format_tool = TextFormattingTool(self.llm_service)
        self.tool_registry.register(text_format_tool)
        
        logger.info(f"已注册 {len(self.tool_registry._tools)} 个工具")
    
    async def _cleanup_partial_init(self):
        """清理部分初始化的组件"""
        logger.info("清理部分初始化的组件...")
        
        # 清理LLM服务
        if hasattr(self, 'llm_service') and self.llm_service:
            try:
                # 如果LLM服务有清理方法，调用它
                if hasattr(self.llm_service, 'cleanup'):
                    await self.llm_service.cleanup()
            except Exception as e:
                logger.error(f"LLM服务清理失败: {e}")
        
        # 清理爬虫服务
        if hasattr(self, 'scraper_service') and self.scraper_service:
            try:
                if hasattr(self.scraper_service, 'close'):
                    await self.scraper_service.close()
            except Exception as e:
                logger.error(f"爬虫服务清理失败: {e}")
        
        # 清理分析服务
        if hasattr(self, 'analysis_service') and self.analysis_service:
            try:
                if hasattr(self.analysis_service, 'cleanup'):
                    await self.analysis_service.cleanup()
            except Exception as e:
                logger.error(f"分析服务清理失败: {e}")
        
        # 重置初始化状态
        self.initialized = False
        logger.info("组件清理完成")
    
    async def process_query(self, query: str, user_id: str = "default") -> Dict[str, Any]:
        """处理用户查询"""
        if not self.initialized:
            raise RuntimeError("Agent未初始化，请先调用initialize()")
        
        logger.info(f"处理用户查询: {query}")
        
        try:
            # 1. 解析查询
            logger.info("解析查询...")
            query_result = await self.query_parser.parse(query)
            
            # 2. 创建执行上下文
            context = ToolExecutionContext(
                user_query=query_result.refined_query,
                user_id=user_id,
                session_id=f"session_{datetime.now().timestamp()}",
                preferences={
                    "original_query": query,
                    "category": query_result.category,
                    "intent": query_result.intent,
                    "price_range": query_result.price_range
                }
            )
            
            # 3. 执行查询
            logger.info("执行查询...")
            
            # 使用工具编排器执行完整查询
            execution_result = await self.orchestrator.execute_query(context)
            
            if not execution_result.success:
                errors = '; '.join(execution_result.errors) if execution_result.errors else "未知错误"
                return {
                    "success": False,
                    "error": f"查询执行失败: {errors}",
                    "query": query
                }
            
            # 获取最终结果
            final_result = execution_result.get_final_result()
            
            return {
                "success": True,
                "data": final_result,
                "query": query,
                "execution_time": execution_result.execution_time,
                "tools_used": execution_result.tools_used
            }
            
            logger.info("✅ 查询处理完成")
            
        except Exception as e:
            logger.error(f"❌ 查询处理失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """系统健康检查"""
        logger.info("执行系统健康检查...")
        
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {},
            "overall_healthy": True
        }
        
        # 检查LLM服务
        try:
            providers = self.llm_service.get_available_providers()
            health_status["components"]["llm_service"] = {
                "status": "healthy",
                "available_providers": providers,
                "cost_summary": self.llm_service.get_cost_summary()
            }
        except Exception as e:
            health_status["components"]["llm_service"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["overall_healthy"] = False
        
        # 检查工具注册表
        try:
            tools = self.tool_registry.list_tools()
            health_status["components"]["tool_registry"] = {
                "status": "healthy",
                "registered_tools": len(tools),
                "tool_names": list(tools.keys())
            }
        except Exception as e:
            health_status["components"]["tool_registry"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["overall_healthy"] = False
        
        # 检查配置
        try:
            config_errors = self.settings.validate()
            health_status["components"]["configuration"] = {
                "status": "healthy" if not config_errors else "warning",
                "errors": config_errors
            }
        except Exception as e:
            health_status["components"]["configuration"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["overall_healthy"] = False
        
        health_status["status"] = "healthy" if health_status["overall_healthy"] else "unhealthy"
        
        logger.info(f"健康检查完成: {health_status['status']}")
        return health_status
    
    async def get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        return {
            "app_name": self.settings.app_name,
            "version": self.settings.app_version,
            "environment": self.settings.environment,
            "initialized": self.initialized,
            "available_tools": list(self.tool_registry._tools.keys()) if self.tool_registry else [],
            "llm_providers": self.llm_service.get_available_providers() if self.llm_service else [],
            "features": self.settings.enable_features
        }


async def demo_workflow():
    """演示完整工作流"""
    print("🚀 开始演示Mercari AI Agent工作流...")
    
    # 创建Agent实例
    agent = MercariAIAgent()
    
    # 初始化
    await agent.initialize()
    
    # 健康检查
    health = await agent.health_check()
    print(f"📊 系统健康状态: {health['status']}")
    
    # 处理示例查询
    demo_queries = [
        "iPhone 14 Pro",
        "ナイキのスニーカー",
        "村上春樹の小説",
        "プレイステーション5"
    ]
    
    for query in demo_queries:
        print(f"\n🔍 处理查询: {query}")
        result = await agent.process_query(query)
        
        if result["success"]:
            print(f"✅ 查询成功")
            print(f"   - 精炼查询: {result['refined_query']}")
            print(f"   - 分类: {result['category']}")
            print(f"   - 找到产品: {result['total_products']} 个")
            print(f"   - 分析产品: {len(result['analyzed_products'])} 个")
            print(f"   - 执行时间: {result['execution_time']:.2f}s")
        else:
            print(f"❌ 查询失败: {result['error']}")
    
    # 获取系统信息
    system_info = await agent.get_system_info()
    print(f"\n📱 系统信息:")
    print(f"   - 应用名称: {system_info['app_name']}")
    print(f"   - 版本: {system_info['version']}")
    print(f"   - 环境: {system_info['environment']}")
    print(f"   - 可用工具: {len(system_info['available_tools'])}")
    print(f"   - LLM提供商: {system_info['llm_providers']}")
    
    print("\n🎉 演示完成!")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Mercari AI Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--demo", 
        action="store_true", 
        help="运行演示工作流"
    )
    
    parser.add_argument(
        "--query", 
        type=str, 
        help="处理指定查询"
    )
    
    parser.add_argument(
        "--health", 
        action="store_true", 
        help="执行健康检查"
    )
    
    parser.add_argument(
        "--info", 
        action="store_true", 
        help="显示系统信息"
    )
    
    args = parser.parse_args()
    
    if args.demo:
        await demo_workflow()
    elif args.query:
        agent = MercariAIAgent()
        await agent.initialize()
        result = await agent.process_query(args.query)
        
        # 使用CustomJSONEncoder处理序列化
        from src.mercari_agent.utils.json_encoder import CustomJSONEncoder
        print(json.dumps(result, indent=2, ensure_ascii=False, cls=CustomJSONEncoder))
    elif args.health:
        agent = MercariAIAgent()
        await agent.initialize()
        health = await agent.health_check()
        print(json.dumps(health, indent=2, ensure_ascii=False))
    elif args.info:
        agent = MercariAIAgent()
        await agent.initialize()
        info = await agent.get_system_info()
        print(json.dumps(info, indent=2, ensure_ascii=False))
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())