#!/usr/bin/env python3
"""
集成测试脚本

该脚本验证Mercari AI Agent的集成是否正常工作。

功能：
- 测试组件初始化
- 测试基本工作流
- 验证配置加载
- 检查工具注册

Author: Mercari AI Agent Team
"""

import sys
import asyncio
from pathlib import Path
import json
from typing import Dict, Any

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from mercari_agent.main import MercariAIAgent
from mercari_agent.config.settings import Settings
from mercari_agent.utils.logger import get_logger

logger = get_logger(__name__)


class IntegrationTester:
    """集成测试器"""
    
    def __init__(self):
        self.agent = None
        self.test_results = []
    
    def log_test_result(self, test_name: str, success: bool, message: str = "", data: Any = None):
        """记录测试结果"""
        result = {
            "test_name": test_name,
            "success": success,
            "message": message,
            "data": data
        }
        self.test_results.append(result)
        
        status = "✅" if success else "❌"
        print(f"{status} {test_name}: {message}")
    
    async def test_configuration_loading(self):
        """测试配置加载"""
        try:
            settings = Settings()
            
            # 验证基本配置
            assert settings.app_name == "Mercari AI Agent"
            assert settings.app_version == "1.0.0"
            
            # 验证LLM配置
            assert hasattr(settings, 'llm')
            assert settings.llm.default_provider == "openai"
            
            # 验证工具配置
            assert hasattr(settings, 'tool')
            assert settings.tool.tool_timeout == 30
            
            # 验证配置验证
            errors = settings.validate()
            
            self.log_test_result(
                "Configuration Loading",
                True,
                f"配置加载成功，验证错误: {len(errors)}",
                {"errors": errors}
            )
            
        except Exception as e:
            self.log_test_result(
                "Configuration Loading",
                False,
                f"配置加载失败: {str(e)}"
            )
    
    async def test_agent_initialization(self):
        """测试Agent初始化"""
        try:
            self.agent = MercariAIAgent()
            await self.agent.initialize()
            
            # 验证初始化状态
            assert self.agent.initialized == True
            assert self.agent.llm_service is not None
            assert self.agent.tool_registry is not None
            assert self.agent.query_parser is not None
            assert self.agent.orchestrator is not None
            
            self.log_test_result(
                "Agent Initialization",
                True,
                "Agent初始化成功"
            )
            
        except Exception as e:
            self.log_test_result(
                "Agent Initialization",
                False,
                f"Agent初始化失败: {str(e)}"
            )
    
    async def test_tool_registration(self):
        """测试工具注册"""
        try:
            if not self.agent or not self.agent.tool_registry:
                raise Exception("Agent未正确初始化")
            
            # 获取已注册的工具
            tools = self.agent.tool_registry.list_tools()
            
            # 验证预期工具是否存在
            expected_tools = [
                "search_products",
                "market_analysis",
                "analyze_product",
                "price_analysis",
                "format_results",
                "generate_report"
            ]
            
            registered_tools = list(tools.keys())
            missing_tools = [tool for tool in expected_tools if tool not in registered_tools]
            
            success = len(missing_tools) == 0
            
            self.log_test_result(
                "Tool Registration",
                success,
                f"已注册工具: {len(registered_tools)}, 缺失工具: {missing_tools}",
                {"registered_tools": registered_tools, "missing_tools": missing_tools}
            )
            
        except Exception as e:
            self.log_test_result(
                "Tool Registration",
                False,
                f"工具注册测试失败: {str(e)}"
            )
    
    async def test_llm_service(self):
        """测试LLM服务"""
        try:
            if not self.agent or not self.agent.llm_service:
                raise Exception("Agent未正确初始化")
            
            # 获取可用提供商
            providers = self.agent.llm_service.get_available_providers()
            
            # 获取成本摘要
            cost_summary = self.agent.llm_service.get_cost_summary()
            
            # 获取限流状态
            rate_limit_status = self.agent.llm_service.get_rate_limit_status()
            
            success = len(providers) > 0
            
            self.log_test_result(
                "LLM Service",
                success,
                f"可用提供商: {providers}",
                {
                    "providers": providers,
                    "cost_summary": cost_summary,
                    "rate_limit_status": rate_limit_status
                }
            )
            
        except Exception as e:
            self.log_test_result(
                "LLM Service",
                False,
                f"LLM服务测试失败: {str(e)}"
            )
    
    async def test_health_check(self):
        """测试健康检查"""
        try:
            if not self.agent:
                raise Exception("Agent未正确初始化")
            
            health = await self.agent.health_check()
            
            # 验证健康检查结果
            assert "status" in health
            assert "components" in health
            assert "overall_healthy" in health
            
            success = health["overall_healthy"]
            
            self.log_test_result(
                "Health Check",
                success,
                f"系统健康状态: {health['status']}",
                health
            )
            
        except Exception as e:
            self.log_test_result(
                "Health Check",
                False,
                f"健康检查失败: {str(e)}"
            )
    
    async def test_system_info(self):
        """测试系统信息"""
        try:
            if not self.agent:
                raise Exception("Agent未正确初始化")
            
            info = await self.agent.get_system_info()
            
            # 验证系统信息
            assert "app_name" in info
            assert "version" in info
            assert "initialized" in info
            assert "available_tools" in info
            
            success = info["initialized"] == True
            
            self.log_test_result(
                "System Info",
                success,
                f"系统信息获取成功，工具数: {len(info['available_tools'])}",
                info
            )
            
        except Exception as e:
            self.log_test_result(
                "System Info",
                False,
                f"系统信息测试失败: {str(e)}"
            )
    
    async def test_basic_query_processing(self):
        """测试基本查询处理"""
        try:
            if not self.agent:
                raise Exception("Agent未正确初始化")
            
            # 使用简单的测试查询
            test_query = "iPhone"
            
            # 由于这是集成测试，我们只测试查询解析部分
            # 实际的产品搜索需要真实的API密钥
            
            # 测试查询解析器
            query_result = await self.agent.query_parser.parse_query(test_query)
            
            success = hasattr(query_result, 'refined_query')
            
            self.log_test_result(
                "Basic Query Processing",
                success,
                f"查询解析成功，精炼查询: {getattr(query_result, 'refined_query', 'N/A')}",
                {
                    "original_query": test_query,
                    "refined_query": getattr(query_result, 'refined_query', None),
                    "category": getattr(query_result, 'category', None),
                    "intent": getattr(query_result, 'intent', None)
                }
            )
            
        except Exception as e:
            self.log_test_result(
                "Basic Query Processing",
                False,
                f"查询处理测试失败: {str(e)}"
            )
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始集成测试...")
        print("=" * 50)
        
        # 运行测试
        await self.test_configuration_loading()
        await self.test_agent_initialization()
        await self.test_tool_registration()
        await self.test_llm_service()
        await self.test_health_check()
        await self.test_system_info()
        await self.test_basic_query_processing()
        
        # 汇总结果
        print("\n" + "=" * 50)
        print("📊 测试结果汇总:")
        print("=" * 50)
        
        passed = sum(1 for result in self.test_results if result["success"])
        total = len(self.test_results)
        
        print(f"总测试数: {total}")
        print(f"通过: {passed}")
        print(f"失败: {total - passed}")
        print(f"成功率: {passed/total*100:.1f}%")
        
        # 显示失败的测试
        failed_tests = [result for result in self.test_results if not result["success"]]
        if failed_tests:
            print("\n❌ 失败的测试:")
            for test in failed_tests:
                print(f"  - {test['test_name']}: {test['message']}")
        
        # 保存测试结果
        self.save_test_results()
        
        return passed == total
    
    def save_test_results(self):
        """保存测试结果"""
        results_file = project_root / "test_results.json"
        
        try:
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(self.test_results, f, ensure_ascii=False, indent=2, default=str)
            print(f"\n💾 测试结果已保存到: {results_file}")
        except Exception as e:
            print(f"\n⚠️  保存测试结果失败: {e}")


async def main():
    """主函数"""
    try:
        tester = IntegrationTester()
        success = await tester.run_all_tests()
        
        if success:
            print("\n🎉 所有集成测试通过!")
            return 0
        else:
            print("\n💥 部分集成测试失败!")
            return 1
            
    except Exception as e:
        print(f"\n💥 集成测试执行失败: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)