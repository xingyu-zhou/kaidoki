#!/usr/bin/env python3
"""
完整系统集成测试

测试修复后的系统是否能正常运行iPhone 16搜索工作流程
以及整个系统的端到端功能
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, Any
import json

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.mercari_agent.main import MercariAIAgent
from src.mercari_agent.config.settings import load_settings
from src.mercari_agent.utils.logger import get_logger
from src.mercari_agent.utils.timeout_manager import global_timeout_manager
from src.mercari_agent.utils.json_encoder import safe_json_serialize

logger = get_logger(__name__)

class SystemIntegrationTest:
    """系统集成测试类"""
    
    def __init__(self):
        self.agent = None
        self.test_results = {}
        
    async def run_full_test(self):
        """运行完整的系统测试"""
        logger.info("🚀 开始完整系统集成测试...")
        
        tests = [
            ("系统初始化测试", self.test_system_initialization),
            ("健康检查测试", self.test_health_check),
            ("工具注册验证", self.test_tool_registration),
            ("iPhone 16搜索工作流程", self.test_iphone16_workflow),
            ("系统清理测试", self.test_system_cleanup),
        ]
        
        for test_name, test_func in tests:
            logger.info(f"🔍 执行测试: {test_name}")
            try:
                result = await test_func()
                self.test_results[test_name] = {
                    "status": "PASS" if result else "FAIL",
                    "message": "测试通过" if result else "测试失败"
                }
                logger.info(f"✅ {test_name}: {'通过' if result else '失败'}")
            except Exception as e:
                self.test_results[test_name] = {
                    "status": "ERROR",
                    "message": str(e)
                }
                logger.error(f"❌ {test_name}: 错误 - {e}")
        
        # 生成最终报告
        self.generate_final_report()
        
    async def test_system_initialization(self) -> bool:
        """测试系统初始化（之前会死锁的地方）"""
        logger.info("测试系统初始化...")
        
        try:
            # 使用超时控制来初始化系统
            self.agent = await global_timeout_manager.with_timeout(
                self._initialize_agent(),
                timeout=60,  # 给予足够的时间
                task_name="系统初始化"
            )
            
            # 验证初始化状态
            assert self.agent.initialized, "系统未正确初始化"
            assert self.agent.llm_service is not None, "LLM服务未初始化"
            assert self.agent.tool_registry is not None, "工具注册表未初始化"
            assert self.agent.query_parser is not None, "查询解析器未初始化"
            assert self.agent.orchestrator is not None, "工具编排器未初始化"
            
            logger.info("✅ 系统初始化成功，所有组件已就绪")
            return True
            
        except Exception as e:
            logger.error(f"❌ 系统初始化失败: {e}")
            return False
    
    async def _initialize_agent(self) -> MercariAIAgent:
        """初始化Agent"""
        settings = load_settings()
        agent = MercariAIAgent(settings)
        await agent.initialize()
        return agent
    
    async def test_health_check(self) -> bool:
        """测试健康检查"""
        logger.info("测试健康检查...")
        
        try:
            if not self.agent:
                logger.error("Agent未初始化")
                return False
            
            # 获取健康状态
            health_status = await self.agent.health_check()
            
            # 验证健康状态结构
            assert isinstance(health_status, dict), "健康状态应为字典"
            assert "status" in health_status, "健康状态应包含status字段"
            assert "components" in health_status, "健康状态应包含components字段"
            
            # 测试JSON序列化（之前会失败的地方）
            json_output = safe_json_serialize(health_status)
            logger.info(f"健康状态JSON序列化成功: {json_output[:200]}...")
            
            logger.info("✅ 健康检查通过")
            return True
            
        except Exception as e:
            logger.error(f"❌ 健康检查失败: {e}")
            return False
    
    async def test_tool_registration(self) -> bool:
        """测试工具注册验证"""
        logger.info("测试工具注册验证...")
        
        try:
            if not self.agent:
                logger.error("Agent未初始化")
                return False
            
            # 验证工具注册表
            tools = list(self.agent.tool_registry._tools.keys())
            logger.info(f"已注册工具: {tools}")
            
            # 验证关键工具是否存在
            expected_tools = [
                "search_products",
                "analyze_query", 
                "suggest_category",
                "analyze_product",
                "analyze_price",
                "compare_products",
                "generate_summary",
                "format_text"
            ]
            
            for tool in expected_tools:
                if tool not in tools:
                    logger.error(f"缺少必要工具: {tool}")
                    return False
            
            logger.info(f"✅ 工具注册验证通过，共{len(tools)}个工具")
            return True
            
        except Exception as e:
            logger.error(f"❌ 工具注册验证失败: {e}")
            return False
    
    async def test_iphone16_workflow(self) -> bool:
        """测试iPhone 16搜索工作流程"""
        logger.info("测试iPhone 16搜索工作流程...")
        
        try:
            if not self.agent:
                logger.error("Agent未初始化")
                return False
            
            # 测试查询："iPhone 16 Pro Max 256GB"
            test_query = "iPhone 16 Pro Max 256GB"
            
            # 使用超时控制执行查询
            result = await global_timeout_manager.with_timeout(
                self.agent.process_query(test_query),
                timeout=120,  # 给予充分时间
                task_name="iPhone 16搜索工作流程"
            )
            
            # 验证结果结构
            assert isinstance(result, dict), "查询结果应为字典"
            assert "success" in result, "结果应包含success字段"
            
            # 测试结果JSON序列化
            json_result = safe_json_serialize(result)
            logger.info(f"查询结果JSON序列化成功: {json_result[:300]}...")
            
            if result.get("success"):
                logger.info("✅ iPhone 16搜索工作流程完成")
                return True
            else:
                logger.warning("⚠️ iPhone 16搜索工作流程返回失败状态")
                return False
            
        except Exception as e:
            logger.error(f"❌ iPhone 16搜索工作流程失败: {e}")
            return False
    
    async def test_system_cleanup(self) -> bool:
        """测试系统清理"""
        logger.info("测试系统清理...")
        
        try:
            if self.agent:
                await self.agent._cleanup_partial_init()
                logger.info("✅ 系统清理完成")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 系统清理失败: {e}")
            return False
    
    def generate_final_report(self):
        """生成最终测试报告"""
        logger.info("📊 完整系统集成测试报告:")
        logger.info("=" * 60)
        
        passed = 0
        failed = 0
        errors = 0
        
        for test_name, result in self.test_results.items():
            status = result["status"]
            message = result["message"]
            
            if status == "PASS":
                passed += 1
                logger.info(f"✅ {test_name}: 通过")
            elif status == "FAIL":
                failed += 1
                logger.error(f"❌ {test_name}: 失败 - {message}")
            else:  # ERROR
                errors += 1
                logger.error(f"⚠️ {test_name}: 错误 - {message}")
        
        logger.info("=" * 60)
        logger.info(f"总计: {len(self.test_results)} 项测试")
        logger.info(f"✅ 通过: {passed}")
        logger.info(f"❌ 失败: {failed}")
        logger.info(f"⚠️ 错误: {errors}")
        
        if failed == 0 and errors == 0:
            logger.info("🎉 所有测试通过！系统修复完全成功！")
            logger.info("🚀 系统现在可以正常运行iPhone 16搜索工作流程")
        else:
            logger.error("❌ 部分测试失败，系统仍需进一步修复")
        
        # 保存详细报告
        try:
            report_data = {
                "timestamp": "2025-07-25T12:06:50.722Z",
                "test_summary": {
                    "total": len(self.test_results),
                    "passed": passed,
                    "failed": failed,
                    "errors": errors
                },
                "test_results": self.test_results,
                "system_status": "READY" if (failed == 0 and errors == 0) else "NEEDS_REPAIR"
            }
            
            with open("integration_test_report.json", "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            logger.info("详细测试报告已保存到 integration_test_report.json")
            
        except Exception as e:
            logger.error(f"保存测试报告失败: {e}")

async def main():
    """主函数"""
    tester = SystemIntegrationTest()
    await tester.run_full_test()

if __name__ == "__main__":
    asyncio.run(main())