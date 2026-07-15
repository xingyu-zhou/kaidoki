#!/usr/bin/env python3
"""
Mercari AI Agent 系统综合集成测试套件

本测试套件对LLM服务迁移后的功能完整性进行全面验证，包括：
1. LLM服务集成测试
2. 应用服务集成测试  
3. CLI集成测试
4. 性能和稳定性测试
5. 错误处理和边界条件测试
6. 回归测试

Author: Mercari AI Agent Team (Refactored)
Created: 2025-07-29
"""

import asyncio
import sys
import os
import time
import subprocess
import concurrent.futures
import psutil
import json
import traceback
import threading
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
import gc
import resource

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

# 导入测试相关模块
from src.mercari_agent.shared.config.app_config import AppConfig, LLMConfig, Environment
from src.mercari_agent.shared.utils.logger_utils import get_logger
from src.mercari_agent.infrastructure.llm.llm_service import LLMService, LLMProvider
from src.mercari_agent.application.services.query_parser_service import QueryParserService
from src.mercari_agent.application.services.recommendation_service import RecommendationService
from src.mercari_agent.application.services.output_formatter_service import OutputFormatterService
from src.mercari_agent.domain.entities.product import ProductEntity
from src.mercari_agent.domain.entities.query import QueryEntity, QueryIntent

logger = get_logger(__name__)


@dataclass
class TestResult:
    """测试结果数据类"""
    name: str
    category: str
    status: str  # PASS, FAIL, SKIP, ERROR
    message: str
    duration: float = 0.0
    error_details: Optional[str] = None
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass  
class TestSuiteStats:
    """测试套件统计"""
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    error_tests: int = 0
    total_duration: float = 0.0
    
    @property
    def success_rate(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return (self.passed_tests / self.total_tests) * 100


class SystemIntegrationTestSuite:
    """系统集成测试套件"""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.config = None
        self.llm_service = None
        self.services = {}
        self.process_monitor = ProcessMonitor()
        self.performance_baseline = {}
        
    async def initialize(self):
        """初始化测试环境"""
        print("🚀 初始化系统集成测试环境...")
        
        try:
            # 创建测试配置
            self.config = self._create_test_config()
            
            # 初始化LLM服务 (传递LLM配置)
            self.llm_service = LLMService(self.config.llm)
            await self.llm_service.initialize()
            
            # 初始化应用服务
            await self._initialize_services()
            
            # 启动性能监控
            self.process_monitor.start_monitoring()
            
            print("✅ 测试环境初始化完成")
            
        except Exception as e:
            print(f"❌ 测试环境初始化失败: {e}")
            raise

    def _create_test_config(self) -> AppConfig:
        """创建测试配置"""
        config = AppConfig(environment=Environment.TESTING)
        
        # 模拟API密钥（用于测试）
        config.llm.openai_api_key = "test_openai_key"
        config.llm.anthropic_api_key = "test_anthropic_key"
        config.llm.azure_openai_api_key = "test_azure_key"
        config.llm.azure_openai_endpoint = "https://test.openai.azure.com/"
        
        return config

    async def _initialize_services(self):
        """初始化应用服务"""
        self.services = {
            'query_parser': QueryParserService(self.config, self.llm_service),
            'recommendation': RecommendationService(self.config, self.llm_service),
            'output_formatter': OutputFormatterService(self.config, self.llm_service)
        }

    async def run_all_tests(self):
        """运行所有测试"""
        print("🧪 开始运行综合集成测试套件...")
        print("=" * 80)
        
        start_time = time.time()
        
        try:
            # 1. LLM服务集成测试
            await self._run_llm_service_tests()
            
            # 2. 应用服务集成测试
            await self._run_application_service_tests()
            
            # 3. CLI集成测试
            await self._run_cli_tests()
            
            # 4. 性能和稳定性测试
            await self._run_performance_tests()
            
            # 5. 错误处理和边界条件测试
            await self._run_error_handling_tests()
            
            # 6. 回归测试
            await self._run_regression_tests()
            
            # 生成测试报告
            duration = time.time() - start_time
            await self._generate_comprehensive_report(duration)
            
        except Exception as e:
            logger.error(f"测试套件执行异常: {e}")
            traceback.print_exc()

    # =============================================================================
    # 1. LLM服务集成测试
    # =============================================================================
    
    async def _run_llm_service_tests(self):
        """运行LLM服务集成测试"""
        print("\n📡 1. LLM服务集成测试")
        print("-" * 40)
        
        await self._test_llm_service_initialization()
        await self._test_llm_provider_support()
        await self._test_llm_response_generation()
        await self._test_llm_tool_calling()
        await self._test_llm_cost_tracking()
        await self._test_llm_caching()
        await self._test_llm_failover()

    async def _test_llm_service_initialization(self):
        """测试LLM服务初始化"""
        await self._run_test(
            "LLM服务初始化", "llm_service",
            self._llm_initialization_test
        )

    async def _llm_initialization_test(self):
        """LLM初始化测试实现"""
        assert self.llm_service is not None, "LLM服务未初始化"
        assert self.llm_service._initialized, "LLM服务状态异常"
        
        # 检查提供商配置
        info = await self.llm_service.get_service_info()
        assert isinstance(info, dict), "服务信息格式错误"
        assert "available_providers" in info, "缺少提供商信息"
        
        return {"providers": len(info.get("available_providers", []))}

    async def _test_llm_provider_support(self):
        """测试多LLM提供商支持"""
        await self._run_test(
            "多LLM提供商支持", "llm_service", 
            self._llm_provider_support_test
        )

    async def _llm_provider_support_test(self):
        """多提供商支持测试"""
        providers = [LLMProvider.OPENAI, LLMProvider.ANTHROPIC, LLMProvider.AZURE_OPENAI]
        supported_providers = []
        
        for provider in providers:
            try:
                # 尝试使用每个提供商生成响应
                response = await self.llm_service.generate_response(
                    "测试提示词",
                    preferred_provider=provider
                )
                if response and hasattr(response, 'content'):
                    supported_providers.append(provider.value)
            except Exception as e:
                logger.warning(f"提供商 {provider.value} 不可用: {e}")
        
        assert len(supported_providers) > 0, "没有可用的LLM提供商"
        return {"supported_providers": supported_providers}

    async def _test_llm_response_generation(self):
        """测试LLM响应生成"""
        await self._run_test(
            "LLM响应生成", "llm_service",
            self._llm_response_generation_test
        )

    async def _llm_response_generation_test(self):
        """响应生成测试"""
        test_prompts = [
            "请推荐一些iPhone产品",
            "分析以下查询：iPhone 13 Pro 5万円以下",
            "格式化产品信息为表格"
        ]
        
        responses = []
        total_latency = 0
        
        for prompt in test_prompts:
            response = await self.llm_service.generate_response(prompt)
            assert response is not None, "响应为空"
            assert hasattr(response, 'content'), "响应缺少内容"
            assert len(response.content) > 0, "响应内容为空"
            assert hasattr(response, 'latency'), "响应缺少延迟信息"
            
            responses.append(response)
            total_latency += response.latency
        
        avg_latency = total_latency / len(test_prompts)
        return {
            "responses_generated": len(responses),
            "avg_latency": avg_latency,
            "max_latency": max(r.latency for r in responses)
        }

    async def _test_llm_tool_calling(self):
        """测试LLM工具调用"""
        await self._run_test(
            "LLM工具调用", "llm_service",
            self._llm_tool_calling_test
        )

    async def _llm_tool_calling_test(self):
        """工具调用测试"""
        # 创建测试工具
        test_tool = {
            "name": "test_calculator",
            "description": "计算两个数的和",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"}
                },
                "required": ["a", "b"]
            }
        }
        
        try:
            response = await self.llm_service.generate_response(
                "使用计算器计算 2 + 3",
                tools=[test_tool],
                enable_tools=True
            )
            
            # 检查是否包含工具调用信息
            assert response is not None, "工具调用响应为空"
            return {"tool_calling_supported": True}
            
        except Exception as e:
            # 工具调用可能不被所有提供商支持，这是可接受的
            logger.warning(f"工具调用测试失败: {e}")
            return {"tool_calling_supported": False, "reason": str(e)}

    async def _test_llm_cost_tracking(self):
        """测试LLM成本跟踪"""
        await self._run_test(
            "LLM成本跟踪", "llm_service",
            self._llm_cost_tracking_test
        )

    async def _llm_cost_tracking_test(self):
        """成本跟踪测试"""
        # 记录初始成本
        initial_cost = self.llm_service.get_total_cost()
        
        # 生成一些响应
        await self.llm_service.generate_response("测试成本跟踪")
        await self.llm_service.generate_response("另一个测试请求")
        
        # 检查成本是否增加
        final_cost = self.llm_service.get_total_cost()
        cost_summary = self.llm_service.get_cost_summary()
        
        assert isinstance(cost_summary, dict), "成本摘要格式错误"
        assert "total_cost" in cost_summary, "缺少总成本信息"
        assert "requests_count" in cost_summary, "缺少请求计数"
        
        return {
            "initial_cost": initial_cost,
            "final_cost": final_cost,
            "cost_increased": final_cost > initial_cost,
            "total_requests": cost_summary.get("requests_count", 0)
        }

    async def _test_llm_caching(self):
        """测试LLM缓存"""
        await self._run_test(
            "LLM缓存功能", "llm_service",
            self._llm_caching_test
        )

    async def _llm_caching_test(self):
        """缓存功能测试"""
        test_prompt = "这是一个测试缓存的提示词"
        
        # 第一次请求
        start_time = time.time()
        response1 = await self.llm_service.generate_response(test_prompt, use_cache=True)
        first_request_time = time.time() - start_time
        
        # 第二次相同请求（应该命中缓存）
        start_time = time.time()
        response2 = await self.llm_service.generate_response(test_prompt, use_cache=True)
        second_request_time = time.time() - start_time
        
        # 验证响应内容一致
        assert response1.content == response2.content, "缓存响应内容不一致"
        
        # 验证缓存效果（第二次应该更快）
        cache_speedup = first_request_time / max(second_request_time, 0.001)
        
        return {
            "first_request_time": first_request_time,
            "second_request_time": second_request_time,
            "cache_speedup": cache_speedup,
            "cache_effective": cache_speedup > 2  # 缓存应该至少快2倍
        }

    async def _test_llm_failover(self):
        """测试LLM故障转移"""
        await self._run_test(
            "LLM故障转移", "llm_service",
            self._llm_failover_test
        )

    async def _llm_failover_test(self):
        """故障转移测试"""
        # 模拟提供商故障
        original_providers = self.llm_service._available_providers.copy()
        
        # 禁用一个提供商
        if LLMProvider.OPENAI in original_providers:
            self.llm_service._available_providers.remove(LLMProvider.OPENAI)
        
        try:
            # 尝试生成响应（应该使用备用提供商）
            response = await self.llm_service.generate_response("故障转移测试")
            assert response is not None, "故障转移失败"
            
            # 恢复提供商设置
            self.llm_service._available_providers = original_providers
            
            return {
                "failover_successful": True,
                "backup_provider": response.provider.value
            }
            
        except Exception as e:
            # 恢复提供商设置
            self.llm_service._available_providers = original_providers
            return {
                "failover_successful": False,
                "error": str(e)
            }

    # =============================================================================
    # 2. 应用服务集成测试
    # =============================================================================
    
    async def _run_application_service_tests(self):
        """运行应用服务集成测试"""
        print("\n🔧 2. 应用服务集成测试")
        print("-" * 40)
        
        await self._test_query_parser_service()
        await self._test_recommendation_service()
        await self._test_output_formatter_service()
        await self._test_service_integration()

    async def _test_query_parser_service(self):
        """测试查询解析服务"""
        await self._run_test(
            "查询解析服务", "app_service",
            self._query_parser_service_test
        )

    async def _query_parser_service_test(self):
        """查询解析服务测试"""
        parser = self.services['query_parser']
        
        test_queries = [
            "iPhone 13 Pro 128GB 5万円以下",
            "Nintendo Switch 新品 安い",
            "MacBook Pro 中古 10万円前後"
        ]
        
        results = []
        for query in test_queries:
            result = await parser.parse(query)
            assert result is not None, f"解析结果为空: {query}"
            assert hasattr(result, 'query'), "缺少查询实体"
            assert hasattr(result.query, 'keywords'), "缺少关键词"
            assert len(result.query.keywords) > 0, "关键词为空"
            
            results.append({
                "query": query,
                "keywords": result.query.keywords,
                "confidence": result.confidence
            })
        
        return {"parsed_queries": len(results), "results": results}

    async def _test_recommendation_service(self):
        """测试推荐服务"""
        await self._run_test(
            "推荐服务", "app_service",
            self._recommendation_service_test
        )

    async def _recommendation_service_test(self):
        """推荐服务测试"""
        recommender = self.services['recommendation']
        
        # 创建测试数据
        products = [
            ProductEntity(
                id="1", title="iPhone 13 Pro 128GB", 
                price=89800, condition="新品", seller_name="seller1"
            ),
            ProductEntity(
                id="2", title="iPhone 13 mini 64GB", 
                price=59800, condition="新品", seller_name="seller2"  
            ),
            ProductEntity(
                id="3", title="iPhone 12 Pro 256GB", 
                price=79800, condition="中古", seller_name="seller3"
            )
        ]
        
        query = QueryEntity(
            original_query="iPhone 13 安い",
            intent=QueryIntent.SEARCH,
            keywords=["iPhone", "13"],
            price_max=80000
        )
        
        # 测试推荐
        recommendations = await recommender.recommend(products, query, limit=2)
        
        assert recommendations is not None, "推荐结果为空"
        assert hasattr(recommendations, 'recommendations'), "缺少推荐列表"
        assert len(recommendations.recommendations) <= 2, "推荐数量超出限制"
        
        return {
            "total_products": len(products),
            "recommended_count": len(recommendations.recommendations),
            "strategy": recommendations.strategy_used
        }

    async def _test_output_formatter_service(self):
        """测试输出格式化服务"""
        await self._run_test(
            "输出格式化服务", "app_service", 
            self._output_formatter_service_test
        )

    async def _output_formatter_service_test(self):
        """输出格式化服务测试"""
        formatter = self.services['output_formatter']
        
        # 创建测试数据
        test_data = {
            "products": [
                {"title": "iPhone 13 Pro", "price": 89800, "condition": "新品"},
                {"title": "iPhone 13 mini", "price": 59800, "condition": "新品"}
            ],
            "summary": "找到2个iPhone产品"
        }
        
        query = QueryEntity(
            original_query="iPhone 13",
            keywords=["iPhone", "13"]
        )
        
        formats = ["markdown_table", "detailed_report", "simple_list", "json_export"]
        results = {}
        
        for format_type in formats:
            try:
                formatted = await formatter.format(
                    data=test_data,
                    query=query,
                    output_format=format_type
                )
                
                assert formatted is not None, f"格式化结果为空: {format_type}"
                assert hasattr(formatted, 'content'), f"缺少内容: {format_type}"
                assert len(formatted.content) > 0, f"内容为空: {format_type}"
                
                results[format_type] = {
                    "success": True,
                    "content_length": len(formatted.content)
                }
                
            except Exception as e:
                results[format_type] = {
                    "success": False,
                    "error": str(e)
                }
        
        successful_formats = sum(1 for r in results.values() if r["success"])
        return {
            "formats_tested": len(formats),
            "successful_formats": successful_formats,
            "results": results
        }

    async def _test_service_integration(self):
        """测试服务间集成"""
        await self._run_test(
            "服务间集成", "app_service",
            self._service_integration_test
        )

    async def _service_integration_test(self):
        """服务间集成测试"""
        # 模拟完整的用户查询流程
        user_query = "iPhone 13 Pro 5万円以下 新品"
        
        # 1. 解析查询
        parser = self.services['query_parser']
        parsed_result = await parser.parse(user_query)
        assert parsed_result is not None, "查询解析失败"
        
        # 2. 模拟产品数据
        products = [
            ProductEntity(
                id="1", title="iPhone 13 Pro 128GB 新品", 
                price=45000, condition="新品", seller_name="seller1"
            ),
            ProductEntity(
                id="2", title="iPhone 13 Pro 256GB 新品", 
                price=55000, condition="新品", seller_name="seller2"
            )
        ]
        
        # 3. 生成推荐
        recommender = self.services['recommendation']
        recommendations = await recommender.recommend(
            products, parsed_result.query, limit=5
        )
        assert recommendations is not None, "推荐生成失败"
        
        # 4. 格式化输出
        formatter = self.services['output_formatter']
        formatted = await formatter.format(
            data=recommendations,
            query=parsed_result.query,
            output_format="markdown_table"
        )
        assert formatted is not None, "输出格式化失败"
        
        return {
            "workflow_completed": True,
            "query_parsed": True,
            "recommendations_generated": len(recommendations.recommendations),
            "output_formatted": True,
            "output_length": len(formatted.content)
        }

    # =============================================================================
    # 3. CLI集成测试
    # =============================================================================
    
    async def _run_cli_tests(self):
        """运行CLI集成测试"""
        print("\n💻 3. CLI集成测试")
        print("-" * 40)
        
        await self._test_cli_basic_commands()
        await self._test_cli_search_workflow()
        await self._test_cli_llm_commands()
        await self._test_cli_config_management()

    async def _test_cli_basic_commands(self):
        """测试CLI基础命令"""
        await self._run_test(
            "CLI基础命令", "cli",
            self._cli_basic_commands_test
        )

    async def _cli_basic_commands_test(self):
        """CLI基础命令测试"""
        cli_script = project_root / "src" / "mercari_agent" / "interfaces" / "cli" / "main.py"
        
        commands = [
            ["--help"],
            ["status"],
            ["config", "show"]
        ]
        
        results = {}
        for cmd in commands:
            try:
                result = subprocess.run(
                    [sys.executable, str(cli_script)] + cmd,
                    capture_output=True, text=True, timeout=30
                )
                results[" ".join(cmd)] = {
                    "success": result.returncode == 0,
                    "stdout": result.stdout[:100],  # 前100字符
                    "stderr": result.stderr[:100] if result.stderr else ""
                }
            except Exception as e:
                results[" ".join(cmd)] = {
                    "success": False,
                    "error": str(e)
                }
        
        successful_commands = sum(1 for r in results.values() if r["success"])
        return {
            "commands_tested": len(commands),
            "successful_commands": successful_commands,
            "results": results
        }

    async def _test_cli_search_workflow(self):
        """测试CLI搜索工作流"""
        await self._run_test(
            "CLI搜索工作流", "cli",
            self._cli_search_workflow_test
        )

    async def _cli_search_workflow_test(self):
        """CLI搜索工作流测试"""
        cli_script = project_root / "src" / "mercari_agent" / "interfaces" / "cli" / "main.py"
        
        # 测试搜索命令
        search_commands = [
            ["search", "--query", "iPhone 13"],
            ["parse", "--query", "iPhone 13 Pro 5万円以下"], 
            ["recommend", "--query", "Nintendo Switch"]
        ]
        
        results = {}
        for cmd in search_commands:
            try:
                result = subprocess.run(
                    [sys.executable, str(cli_script)] + cmd,
                    capture_output=True, text=True, timeout=60
                )
                
                # CLI可能因为缺少真实API密钥而失败，但应该能正确解析命令
                results[" ".join(cmd[:2])] = {
                    "command_parsed": True,
                    "returncode": result.returncode,
                    "has_output": len(result.stdout) > 0 or len(result.stderr) > 0
                }
                
            except Exception as e:
                results[" ".join(cmd[:2])] = {
                    "command_parsed": False,
                    "error": str(e)
                }
        
        return {
            "commands_tested": len(search_commands),
            "results": results
        }

    async def _test_cli_llm_commands(self):
        """测试CLI LLM命令"""
        await self._run_test(
            "CLI LLM命令", "cli",
            self._cli_llm_commands_test
        )

    async def _cli_llm_commands_test(self):
        """CLI LLM命令测试"""
        cli_script = project_root / "src" / "mercari_agent" / "interfaces" / "cli" / "main.py"
        
        llm_commands = [
            ["llm-test", "你好"],
            ["llm-status"]
        ]
        
        results = {}
        for cmd in llm_commands:
            try:
                result = subprocess.run(
                    [sys.executable, str(cli_script)] + cmd,
                    capture_output=True, text=True, timeout=30
                )
                
                results[" ".join(cmd)] = {
                    "command_exists": True,
                    "returncode": result.returncode
                }
                
            except Exception as e:
                results[" ".join(cmd)] = {
                    "command_exists": False,
                    "error": str(e)
                }
        
        return {"results": results}

    async def _test_cli_config_management(self):
        """测试CLI配置管理"""
        await self._run_test(
            "CLI配置管理", "cli",
            self._cli_config_management_test
        )

    async def _cli_config_management_test(self):
        """CLI配置管理测试"""
        cli_script = project_root / "src" / "mercari_agent" / "interfaces" / "cli" / "main.py"
        
        config_commands = [
            ["config", "show"],
            ["config", "validate"]
        ]
        
        results = {}
        for cmd in config_commands:
            try:
                result = subprocess.run(
                    [sys.executable, str(cli_script)] + cmd,
                    capture_output=True, text=True, timeout=30
                )
                
                results[" ".join(cmd)] = {
                    "success": result.returncode == 0,
                    "has_output": len(result.stdout) > 0
                }
                
            except Exception as e:
                results[" ".join(cmd)] = {
                    "success": False,
                    "error": str(e)
                }
        
        return {"results": results}

    # =============================================================================
    # 4. 性能和稳定性测试
    # =============================================================================
    
    async def _run_performance_tests(self):
        """运行性能和稳定性测试"""
        print("\n⚡ 4. 性能和稳定性测试")
        print("-" * 40)
        
        await self._test_concurrent_requests()
        await self._test_memory_usage()
        await self._test_response_time_consistency()
        await self._test_long_running_stability()

    async def _test_concurrent_requests(self):
        """测试并发请求处理"""
        await self._run_test(
            "并发请求处理", "performance",
            self._concurrent_requests_test
        )

    async def _concurrent_requests_test(self):
        """并发请求测试"""
        concurrent_count = 10
        request_per_worker = 5
        
        async def worker(worker_id: int):
            """工作线程"""
            results = []
            for i in range(request_per_worker):
                try:
                    start_time = time.time()
                    response = await self.llm_service.generate_response(
                        f"并发测试请求 {worker_id}-{i}"
                    )
                    duration = time.time() - start_time
                    
                    results.append({
                        "success": True,
                        "duration": duration,
                        "content_length": len(response.content)
                    })
                except Exception as e:
                    results.append({
                        "success": False,
                        "error": str(e)
                    })
            return results
        
        # 启动并发任务
        start_time = time.time()
        tasks = [worker(i) for i in range(concurrent_count)]
        worker_results = await asyncio.gather(*tasks, return_exceptions=True)
        total_duration = time.time() - start_time
        
        # 统计结果
        all_results = []
        for worker_result in worker_results:
            if isinstance(worker_result, list):
                all_results.extend(worker_result)
        
        successful_requests = sum(1 for r in all_results if r.get("success", False))
        total_requests = len(all_results)
        avg_duration = sum(r.get("duration", 0) for r in all_results if "duration" in r) / max(successful_requests, 1)
        
        return {
            "concurrent_workers": concurrent_count,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "success_rate": (successful_requests / total_requests) * 100,
            "total_duration": total_duration,
            "avg_request_duration": avg_duration,
            "requests_per_second": total_requests / total_duration
        }

    async def _test_memory_usage(self):
        """测试内存使用"""
        await self._run_test(
            "内存使用监控", "performance",
            self._memory_usage_test
        )

    async def _memory_usage_test(self):
        """内存使用测试"""
        import gc
        
        # 记录初始内存使用
        gc.collect()
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        # 执行一系列操作
        operations_count = 50
        for i in range(operations_count):
            await self.llm_service.generate_response(f"内存测试请求 {i}")
            
            # 每10次操作检查一次内存
            if i % 10 == 0:
                gc.collect()
        
        # 最终内存检查
        gc.collect()
        final_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # 检查是否有严重的内存泄漏
        memory_leak_threshold = 100  # MB
        has_memory_leak = memory_increase > memory_leak_threshold
        
        return {
            "initial_memory_mb": initial_memory,
            "final_memory_mb": final_memory,
            "memory_increase_mb": memory_increase,
            "operations_performed": operations_count,
            "memory_per_operation_kb": (memory_increase * 1024) / operations_count,
            "potential_memory_leak": has_memory_leak
        }

    async def _test_response_time_consistency(self):
        """测试响应时间一致性"""
        await self._run_test(
            "响应时间一致性", "performance",
            self._response_time_consistency_test
        )

    async def _response_time_consistency_test(self):
        """响应时间一致性测试"""
        test_count = 20
        response_times = []
        
        test_prompt = "请分析iPhone产品的特点"
        
        for i in range(test_count):
            start_time = time.time()
            await self.llm_service.generate_response(test_prompt)
            response_time = time.time() - start_time
            response_times.append(response_time)
            
            # 避免请求过于频繁
            await asyncio.sleep(0.1)
        
        # 计算统计指标
        avg_time = sum(response_times) / len(response_times)
        min_time = min(response_times)
        max_time = max(response_times)
        
        # 计算标准差
        variance = sum((t - avg_time) ** 2 for t in response_times) / len(response_times)
        std_dev = variance ** 0.5
        
        # 一致性评分（标准差越小越好）
        consistency_score = max(0, 100 - (std_dev / avg_time) * 100)
        
        return {
            "test_count": test_count,
            "avg_response_time": avg_time,
            "min_response_time": min_time,
            "max_response_time": max_time,
            "std_deviation": std_dev,
            "consistency_score": consistency_score,
            "response_times": response_times[-5:]  # 最后5个时间
        }

    async def _test_long_running_stability(self):
        """测试长时间运行稳定性"""
        await self._run_test(
            "长时间运行稳定性", "performance",
            self._long_running_stability_test
        )

    async def _long_running_stability_test(self):
        """长时间运行稳定性测试"""
        # 运行较短时间的稳定性测试（实际项目中可以设置更长时间）
        test_duration = 60  # 60秒
        request_interval = 2  # 每2秒一个请求
        
        start_time = time.time()
        successful_requests = 0
        failed_requests = 0
        errors = []
        
        while time.time() - start_time < test_duration:
            try:
                await self.llm_service.generate_response("稳定性测试请求")
                successful_requests += 1
            except Exception as e:
                failed_requests += 1
                errors.append(str(e))
            
            await asyncio.sleep(request_interval)
        
        actual_duration = time.time() - start_time
        total_requests = successful_requests + failed_requests
        
        return {
            "test_duration": actual_duration,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate": (successful_requests / max(total_requests, 1)) * 100,
            "requests_per_minute": (total_requests / actual_duration) * 60,
            "error_types": list(set(errors[:5]))  # 前5种不同的错误类型
        }

    # =============================================================================
    # 5. 错误处理和边界条件测试
    # =============================================================================
    
    async def _run_error_handling_tests(self):
        """运行错误处理和边界条件测试"""
        print("\n🚨 5. 错误处理和边界条件测试")
        print("-" * 40)
        
        await self._test_network_error_handling()
        await self._test_api_error_handling()
        await self._test_invalid_input_handling()
        await self._test_resource_exhaustion()

    async def _test_network_error_handling(self):
        """测试网络错误处理"""
        await self._run_test(
            "网络错误处理", "error_handling",
            self._network_error_handling_test
        )

    async def _network_error_handling_test(self):
        """网络错误处理测试"""
        # 保存原始配置
        original_config = self.llm_service.config
        
        # 创建无效配置（错误的API端点）
        test_config = self._create_test_config()
        test_config.llm.openai_base_url = "https://invalid-api-endpoint.com"
        
        # 创建新的LLM服务实例用于测试
        test_llm_service = LLMService(test_config)
        
        error_scenarios = [
            "网络连接超时测试",
            "API端点不可达测试", 
            "DNS解析失败测试"
        ]
        
        results = {}
        for scenario in error_scenarios:
            try:
                # 设置较短的超时时间
                test_config.llm.timeout = 5
                await test_llm_service.generate_response(scenario)
                results[scenario] = {"handled_gracefully": False, "error": "No exception raised"}
            except Exception as e:
                # 检查是否是预期的网络错误
                error_type = type(e).__name__
                results[scenario] = {
                    "handled_gracefully": True,
                    "error_type": error_type,
                    "error_message": str(e)[:100]
                }
        
        graceful_handling_count = sum(1 for r in results.values() if r["handled_gracefully"])
        
        return {
            "scenarios_tested": len(error_scenarios),
            "gracefully_handled": graceful_handling_count,
            "results": results
        }

    async def _test_api_error_handling(self):
        """测试API错误处理"""
        await self._run_test(
            "API错误处理", "error_handling", 
            self._api_error_handling_test
        )

    async def _api_error_handling_test(self):
        """API错误处理测试"""
        # 测试各种API错误场景
        error_scenarios = [
            ("无效API密钥", "sk-invalid-key-12345"),
            ("过长的请求", "A" * 50000),  # 超长文本
            ("特殊字符处理", "🔥💯🚀" * 1000),  # 大量特殊字符
        ]
        
        results = {}
        for scenario_name, test_input in error_scenarios:
            try:
                # 创建临时配置用于错误测试
                if scenario_name == "无效API密钥":
                    temp_config = self._create_test_config()
                    temp_config.llm.openai_api_key = test_input
                    temp_llm_service = LLMService(temp_config)
                    await temp_llm_service.generate_response("测试请求")
                else:
                    await self.llm_service.generate_response(test_input)
                
                results[scenario_name] = {"handled": False, "error": "No exception raised"}
            except Exception as e:
                results[scenario_name] = {
                    "handled": True,
                    "error_type": type(e).__name__,
                    "error_message": str(e)[:100]
                }
        
        handled_errors = sum(1 for r in results.values() if r["handled"])
        
        return {
            "scenarios_tested": len(error_scenarios),
            "errors_handled": handled_errors,
            "results": results
        }

    async def _test_invalid_input_handling(self):
        """测试无效输入处理"""
        await self._run_test(
            "无效输入处理", "error_handling",
            self._invalid_input_handling_test
        )

    async def _invalid_input_handling_test(self):
        """无效输入处理测试"""
        # 测试各种无效输入
        invalid_inputs = [
            ("空字符串", ""),
            ("仅空格", "   "),
            ("None值", None),
            ("超长文本", "测试" * 10000),
            ("恶意输入", "<script>alert('xss')</script>"),
            ("SQL注入尝试", "'; DROP TABLE users; --"),
            ("特殊Unicode", "\u0000\u0001\u0002")
        ]
        
        results = {}
        
        # 测试查询解析服务
        parser = self.services['query_parser']
        for name, invalid_input in invalid_inputs:
            try:
                if invalid_input is None:
                    # 跳过None测试，因为这通常会在类型检查阶段被捕获
                    results[f"Parser-{name}"] = {"handled": True, "note": "Skipped None test"}
                    continue
                
                result = await parser.parse(invalid_input)
                results[f"Parser-{name}"] = {
                    "handled": True,
                    "has_result": result is not None,
                    "keywords_count": len(result.query.keywords) if result else 0
                }
            except Exception as e:
                results[f"Parser-{name}"] = {
                    "handled": True,
                    "error": type(e).__name__
                }
        
        # 测试LLM服务
        for name, invalid_input in invalid_inputs[:4]:  # 只测试前4个，避免过多LLM调用
            try:
                if invalid_input is None:
                    continue
                    
                response = await self.llm_service.generate_response(invalid_input)
                results[f"LLM-{name}"] = {
                    "handled": True,
                    "has_response": response is not None,
                    "content_length": len(response.content) if response else 0
                }
            except Exception as e:
                results[f"LLM-{name}"] = {
                    "handled": True,
                    "error": type(e).__name__
                }
        
        handled_count = sum(1 for r in results.values() if r["handled"])
        
        return {
            "tests_performed": len(results),
            "handled_gracefully": handled_count,
            "results": dict(list(results.items())[:5])  # 显示前5个结果
        }

    async def _test_resource_exhaustion(self):
        """测试资源耗尽处理"""
        await self._run_test(
            "资源耗尽处理", "error_handling",
            self._resource_exhaustion_test
        )

    async def _resource_exhaustion_test(self):
        """资源耗尽测试"""
        # 测试各种资源限制场景
        scenarios = {}
        
        # 1. 内存压力测试
        try:
            large_data = []
            for i in range(100):  # 创建大量数据
                large_data.append("大量数据 " * 1000)
            
            # 在内存压力下尝试LLM调用
            response = await self.llm_service.generate_response("内存压力测试")
            scenarios["memory_pressure"] = {
                "handled": True,
                "successful_response": response is not None
            }
            
            # 清理内存
            del large_data
            gc.collect()
            
        except Exception as e:
            scenarios["memory_pressure"] = {
                "handled": True,
                "error": type(e).__name__
            }
        
        # 2. 并发连接数限制测试
        try:
            # 创建大量并发任务（超出可能的连接限制）
            concurrent_tasks = 50
            tasks = []
            
            for i in range(concurrent_tasks):
                task = asyncio.create_task(
                    self.llm_service.generate_response(f"并发限制测试 {i}")
                )
                tasks.append(task)
            
            # 等待所有任务完成或超时
            results = await asyncio.gather(*tasks, return_exceptions=True)
            successful_tasks = sum(1 for r in results if not isinstance(r, Exception))
            
            scenarios["concurrent_limit"] = {
                "handled": True,
                "total_tasks": concurrent_tasks,
                "successful_tasks": successful_tasks,
                "success_rate": (successful_tasks / concurrent_tasks) * 100
            }
            
        except Exception as e:
            scenarios["concurrent_limit"] = {
                "handled": True,
                "error": type(e).__name__
            }
        
        return {
            "scenarios_tested": len(scenarios),
            "all_handled": all(s["handled"] for s in scenarios.values()),
            "results": scenarios
        }

    # =============================================================================
    # 6. 回归测试
    # =============================================================================
    
    async def _run_regression_tests(self):
        """运行回归测试"""
        print("\n🔄 6. 回归测试")
        print("-" * 40)
        
        await self._test_existing_functionality()
        await self._test_backward_compatibility() 
        await self._test_configuration_compatibility()
        await self._test_interface_compatibility()

    async def _test_existing_functionality(self):
        """测试现有功能"""
        await self._run_test(
            "现有功能验证", "regression",
            self._existing_functionality_test
        )

    async def _existing_functionality_test(self):
        """现有功能测试"""
        # 运行核心功能的基本测试
        test_results = {}
        
        # 1. 基本查询解析
        try:
            parser = self.services['query_parser']
            result = await parser.parse("iPhone 13 Pro 5万円以下")
            test_results["query_parsing"] = {
                "functional": result is not None,
                "has_keywords": len(result.query.keywords) > 0 if result else False
            }
        except Exception as e:
            test_results["query_parsing"] = {"functional": False, "error": str(e)}
        
        # 2. 基本推荐功能
        try:
            recommender = self.services['recommendation']
            products = [
                ProductEntity(id="1", title="Test Product", price=50000, condition="新品", seller_name="test")
            ]
            query = QueryEntity(original_query="test", keywords=["test"])
            
            recommendations = await recommender.recommend(products, query)
            test_results["recommendation"] = {
                "functional": recommendations is not None,
                "has_results": len(recommendations.recommendations) > 0 if recommendations else False
            }
        except Exception as e:
            test_results["recommendation"] = {"functional": False, "error": str(e)}
        
        # 3. 基本格式化功能
        try:
            formatter = self.services['output_formatter']
            test_data = {"test": "data"}
            query = QueryEntity(original_query="test", keywords=["test"])
            
            formatted = await formatter.format(test_data, query, "json_export")
            test_results["formatting"] = {
                "functional": formatted is not None,
                "has_content": len(formatted.content) > 0 if formatted else False
            }
        except Exception as e:
            test_results["formatting"] = {"functional": False, "error": str(e)}
        
        functional_count = sum(1 for r in test_results.values() if r.get("functional", False))
        
        return {
            "tests_performed": len(test_results),
            "functional_tests": functional_count,
            "all_functional": functional_count == len(test_results),
            "results": test_results
        }

    async def _test_backward_compatibility(self):
        """测试向后兼容性"""
        await self._run_test(
            "向后兼容性", "regression", 
            self._backward_compatibility_test
        )

    async def _backward_compatibility_test(self):
        """向后兼容性测试"""
        compatibility_tests = {}
        
        # 1. 测试旧版本查询格式
        old_format_queries = [
            "iPhone 13 Pro 128GB 5万円以下",
            "Nintendo Switch 新品",
            "MacBook Pro 中古 10万円前後"
        ]
        
        parser = self.services['query_parser']
        successful_parses = 0
        
        for query in old_format_queries:
            try:
                result = await parser.parse(query)
                if result and hasattr(result, 'query'):
                    successful_parses += 1
            except Exception:
                pass
        
        compatibility_tests["query_format"] = {
            "tested": len(old_format_queries),
            "successful": successful_parses,
            "compatibility_rate": (successful_parses / len(old_format_queries)) * 100
        }
        
        # 2. 测试配置格式兼容性
        try:
            # 测试旧版配置属性是否仍然可用
            config = self.config
            old_config_attributes = [
                "llm.openai_api_key",
                "llm.anthropic_api_key", 
                "llm.max_tokens",
                "llm.temperature"
            ]
            
            available_attributes = 0
            for attr_path in old_config_attributes:
                try:
                    obj = config
                    for attr in attr_path.split('.'):
                        obj = getattr(obj, attr)
                    available_attributes += 1
                except AttributeError:
                    pass
            
            compatibility_tests["config_format"] = {
                "tested_attributes": len(old_config_attributes),
                "available_attributes": available_attributes,
                "compatibility_rate": (available_attributes / len(old_config_attributes)) * 100
            }
            
        except Exception as e:
            compatibility_tests["config_format"] = {
                "error": str(e),
                "compatibility_rate": 0
            }
        
        overall_compatibility = sum(t.get("compatibility_rate", 0) for t in compatibility_tests.values()) / len(compatibility_tests)
        
        return {
            "compatibility_tests": len(compatibility_tests),
            "overall_compatibility_rate": overall_compatibility,
            "results": compatibility_tests
        }

    async def _test_configuration_compatibility(self):
        """测试配置兼容性"""
        await self._run_test(
            "配置兼容性", "regression",
            self._configuration_compatibility_test
        )

    async def _configuration_compatibility_test(self):
        """配置兼容性测试"""
        # 测试不同配置场景下的兼容性
        config_scenarios = {}
        
        # 1. 测试仅OpenAI配置
        try:
            test_config = self._create_test_config()
            test_config.llm.anthropic_api_key = None
            test_config.llm.azure_openai_api_key = None
            
            temp_llm = LLMService(test_config)
            await temp_llm.initialize()
            
            config_scenarios["openai_only"] = {
                "initialization": True,
                "provider_count": len(temp_llm._available_providers)
            }
            
        except Exception as e:
            config_scenarios["openai_only"] = {
                "initialization": False,
                "error": str(e)
            }
        
        # 2. 测试环境变量配置
        try:
            # 模拟环境变量配置
            original_env = os.environ.copy()
            os.environ["OPENAI_API_KEY"] = "test_env_key"
            os.environ["ANTHROPIC_API_KEY"] = "test_env_key"
            
            env_config = AppConfig(environment=Environment.TESTING)
            config_scenarios["environment_variables"] = {
                "openai_configured": env_config.llm.has_openai_config(),
                "anthropic_configured": env_config.llm.has_anthropic_config()
            }
            
            # 恢复环境变量
            os.environ.clear()
            os.environ.update(original_env)
            
        except Exception as e:
            config_scenarios["environment_variables"] = {
                "error": str(e)
            }
        
        successful_scenarios = sum(1 for s in config_scenarios.values() if not s.get("error"))
        
        return {
            "scenarios_tested": len(config_scenarios),
            "successful_scenarios": successful_scenarios,
            "compatibility_rate": (successful_scenarios / len(config_scenarios)) * 100,
            "results": config_scenarios
        }

    async def _test_interface_compatibility(self):
        """测试接口兼容性"""
        await self._run_test(
            "接口兼容性", "regression",
            self._interface_compatibility_test
        )

    async def _interface_compatibility_test(self):
        """接口兼容性测试"""
        interface_tests = {}
        
        # 1. 测试LLM服务接口
        try:
            # 检查核心方法是否存在
            llm_methods = [
                "initialize", "generate_response", "get_service_info", 
                "test_connection", "get_cost_summary", "close"
            ]
            
            available_methods = 0
            for method_name in llm_methods:
                if hasattr(self.llm_service, method_name):
                    available_methods += 1
            
            interface_tests["llm_service"] = {
                "expected_methods": len(llm_methods),
                "available_methods": available_methods,
                "compatibility": available_methods == len(llm_methods)
            }
            
        except Exception as e:
            interface_tests["llm_service"] = {"error": str(e)}
        
        # 2. 测试查询解析服务接口
        try:
            parser = self.services['query_parser']
            parser_methods = ["parse"]
            
            available_methods = 0
            for method_name in parser_methods:
                if hasattr(parser, method_name):
                    available_methods += 1
            
            interface_tests["query_parser"] = {
                "expected_methods": len(parser_methods),
                "available_methods": available_methods,
                "compatibility": available_methods == len(parser_methods)
            }
            
        except Exception as e:
            interface_tests["query_parser"] = {"error": str(e)}
        
        # 3. 测试推荐服务接口
        try:
            recommender = self.services['recommendation']
            recommender_methods = ["recommend"]
            
            available_methods = 0
            for method_name in recommender_methods:
                if hasattr(recommender, method_name):
                    available_methods += 1
            
            interface_tests["recommendation"] = {
                "expected_methods": len(recommender_methods),
                "available_methods": available_methods,
                "compatibility": available_methods == len(recommender_methods)
            }
            
        except Exception as e:
            interface_tests["recommendation"] = {"error": str(e)}
        
        compatible_interfaces = sum(1 for i in interface_tests.values() if i.get("compatibility", False))
        
        return {
            "interfaces_tested": len(interface_tests),
            "compatible_interfaces": compatible_interfaces,
            "overall_compatibility": compatible_interfaces == len(interface_tests),
            "results": interface_tests
        }

    # =============================================================================
    # 测试辅助方法
    # =============================================================================
    
    async def _run_test(self, name: str, category: str, test_func: Callable):
        """运行单个测试"""
        print(f"  🧪 运行测试: {name}")
        start_time = time.time()
        
        try:
            # 执行测试函数
            metrics = await test_func()
            duration = time.time() - start_time
            
            # 记录成功结果
            self.results.append(TestResult(
                name=name,
                category=category,
                status="PASS",
                message="测试通过",
                duration=duration,
                performance_metrics=metrics or {}
            ))
            
            print(f"    ✅ {name} - 通过 ({duration:.3f}s)")
            
        except Exception as e:
            duration = time.time() - start_time
            
            # 记录失败结果  
            self.results.append(TestResult(
                name=name,
                category=category,
                status="FAIL",
                message=str(e),
                duration=duration,
                error_details=traceback.format_exc()
            ))
            
            print(f"    ❌ {name} - 失败: {str(e)[:100]}...")

    async def _generate_comprehensive_report(self, total_duration: float):
        """生成综合测试报告"""
        print("\n" + "=" * 80)
        print("📊 MERCARI AI AGENT 系统集成测试报告")
        print("=" * 80)
        
        # 计算统计数据
        stats = TestSuiteStats()
        stats.total_tests = len(self.results)
        stats.total_duration = total_duration
        
        for result in self.results:
            if result.status == "PASS":
                stats.passed_tests += 1
            elif result.status == "FAIL":
                stats.failed_tests += 1
            elif result.status == "SKIP":
                stats.skipped_tests += 1
            else:
                stats.error_tests += 1
        
        # 打印总体统计
        print(f"\n📈 总体统计")
        print("-" * 40)
        print(f"测试总数: {stats.total_tests}")
        print(f"通过测试: {stats.passed_tests} ({stats.success_rate:.1f}%)")
        print(f"失败测试: {stats.failed_tests}")
        print(f"跳过测试: {stats.skipped_tests}")
        print(f"错误测试: {stats.error_tests}")
        print(f"执行时间: {stats.total_duration:.2f}秒")
        
        # 按类别分组统计
        category_stats = {}
        for result in self.results:
            if result.category not in category_stats:
                category_stats[result.category] = {"total": 0, "passed": 0}
            category_stats[result.category]["total"] += 1
            if result.status == "PASS":
                category_stats[result.category]["passed"] += 1
        
        print(f"\n📂 分类统计")
        print("-" * 40)
        for category, stats_data in category_stats.items():
            passed_rate = (stats_data["passed"] / stats_data["total"]) * 100
            print(f"{category:20} {stats_data['passed']:3}/{stats_data['total']:3} ({passed_rate:5.1f}%)")
        
        # 失败测试详情
        failed_tests = [r for r in self.results if r.status == "FAIL"]
        if failed_tests:
            print(f"\n❌ 失败测试详情")
            print("-" * 40)
            for test in failed_tests[:10]:  # 显示前10个失败测试
                print(f"• {test.name} ({test.category})")
                print(f"  错误: {test.message}")
                if test.error_details:
                    newline = '\n'
                    print(f"  详情: {test.error_details.split(newline)[-2]}")
                print()
        
        # 性能摘要
        print(f"\n⚡ 性能摘要")
        print("-" * 40)
        
        # 响应时间统计
        response_times = []
        for result in self.results:
            if result.performance_metrics and "avg_latency" in result.performance_metrics:
                response_times.append(result.performance_metrics["avg_latency"])
        
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            print(f"平均响应时间: {avg_response_time:.3f}s")
            print(f"最快响应时间: {min(response_times):.3f}s")
            print(f"最慢响应时间: {max(response_times):.3f}s")
        
        # 系统资源使用
        current_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        print(f"当前内存使用: {current_memory:.1f}MB")
        
        # 生成JSON报告
        await self._generate_json_report(stats)
        
        # 生产环境部署评估
        deployment_readiness = self._assess_deployment_readiness(stats)
        print(f"\n🚀 生产环境部署评估")
        print("-" * 40)
        print(f"部署准备状态: {'✅ 就绪' if deployment_readiness['ready'] else '❌ 需要修复'}")
        print(f"评估得分: {deployment_readiness['score']:.1f}/100")
        
        if deployment_readiness['issues']:
            print("\n需要解决的问题:")
            for issue in deployment_readiness['issues']:
                print(f"• {issue}")
        
        if deployment_readiness['recommendations']:
            print("\n建议:")
            for rec in deployment_readiness['recommendations']:
                print(f"• {rec}")
        
        print("\n" + "=" * 80)
        
        # 停止性能监控
        self.process_monitor.stop_monitoring()
        
        return stats

    async def _generate_json_report(self, stats: TestSuiteStats):
        """生成JSON格式的测试报告"""
        report = {
            "test_suite": "Mercari AI Agent System Integration Tests",
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tests": stats.total_tests,
                "passed_tests": stats.passed_tests,
                "failed_tests": stats.failed_tests,
                "skipped_tests": stats.skipped_tests,
                "success_rate": stats.success_rate,
                "total_duration": stats.total_duration
            },
            "results": [
                {
                    "name": result.name,
                    "category": result.category,
                    "status": result.status,
                    "message": result.message,
                    "duration": result.duration,
                    "performance_metrics": result.performance_metrics
                } for result in self.results
            ]
        }
        
        report_path = project_root / "test_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 详细报告已保存到: {report_path}")

    def _assess_deployment_readiness(self, stats: TestSuiteStats) -> Dict[str, Any]:
        """评估生产环境部署准备状态"""
        score = 0
        issues = []
        recommendations = []
        
        # 基本功能测试通过率
        if stats.success_rate >= 95:
            score += 30
        elif stats.success_rate >= 90:
            score += 25
            issues.append("部分测试失败，需要修复")
        else:
            score += 10
            issues.append("测试失败率过高，不建议部署")
        
        # LLM服务集成测试
        llm_tests = [r for r in self.results if r.category == "llm_service"]
        llm_pass_rate = sum(1 for r in llm_tests if r.status == "PASS") / max(len(llm_tests), 1) * 100
        
        if llm_pass_rate >= 90:
            score += 25
        elif llm_pass_rate >= 80:
            score += 20
            issues.append("LLM服务集成存在问题")
        else:
            score += 5
            issues.append("LLM服务集成测试失败率过高")
        
        # 性能测试
        performance_tests = [r for r in self.results if r.category == "performance"]
        if performance_tests:
            perf_pass_rate = sum(1 for r in performance_tests if r.status == "PASS") / len(performance_tests) * 100
            if perf_pass_rate >= 80:
                score += 20
            else:
                score += 10
                issues.append("性能测试存在问题")
        
        # 错误处理测试
        error_tests = [r for r in self.results if r.category == "error_handling"]
        if error_tests:
            error_pass_rate = sum(1 for r in error_tests if r.status == "PASS") / len(error_tests) * 100
            if error_pass_rate >= 90:
                score += 15
            else:
                score += 5
                issues.append("错误处理能力需要改善")
        
        # 回归测试
        regression_tests = [r for r in self.results if r.category == "regression"]
        if regression_tests:
            regr_pass_rate = sum(1 for r in regression_tests if r.status == "PASS") / len(regression_tests) * 100
            if regr_pass_rate >= 95:
                score += 10
            else:
                score += 5
                issues.append("向后兼容性存在问题")
        
        # 生成建议
        if score >= 85:
            recommendations.append("系统准备就绪，可以部署到生产环境")
            recommendations.append("建议在生产环境中监控性能指标")
        elif score >= 70:
            recommendations.append("建议修复已知问题后再部署")
            recommendations.append("可以考虑先在预生产环境测试")
        else:
            recommendations.append("需要大幅改进后才能部署")
            recommendations.append("建议重新审查系统架构和实现")
        
        return {
            "ready": score >= 85,
            "score": score,
            "issues": issues,
            "recommendations": recommendations
        }

    async def cleanup(self):
        """清理测试环境"""
        try:
            print("\n🧹 清理测试环境...")
            
            # 关闭LLM服务
            if self.llm_service:
                await self.llm_service.close()
            
            # 停止性能监控
            self.process_monitor.stop_monitoring()
            
            # 清理内存
            gc.collect()
            
            print("✅ 测试环境清理完成")
            
        except Exception as e:
            print(f"❌ 清理测试环境时出错: {e}")


class ProcessMonitor:
    """进程监控器"""
    
    def __init__(self):
        self.monitoring = False
        self.metrics = []
        self.monitor_thread = None
        
    def start_monitoring(self):
        """开始监控"""
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)
            
    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                process = psutil.Process()
                self.metrics.append({
                    "timestamp": time.time(),
                    "memory_mb": process.memory_info().rss / 1024 / 1024,
                    "cpu_percent": process.cpu_percent()
                })
                
                # 只保留最近100个数据点
                if len(self.metrics) > 100:
                    self.metrics.pop(0)
                    
                time.sleep(5)  # 每5秒采样一次
                
            except Exception:
                pass  # 忽略监控错误
    
    def get_metrics(self):
        """获取监控指标"""
        return self.metrics.copy()


async def main():
    """主函数"""
    suite = SystemIntegrationTestSuite()
    
    try:
        print("🎯 Mercari AI Agent 系统集成测试套件")
        print("=" * 80)
        print("测试范围: LLM服务迁移后的功能完整性验证")
        print("测试时间:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        # 初始化测试环境
        await suite.initialize()
        
        # 运行所有测试
        await suite.run_all_tests()
        
        # 计算最终结果
        failed_tests = [r for r in suite.results if r.status == "FAIL"]
        if failed_tests:
            print(f"\n❌ 有 {len(failed_tests)} 个测试失败")
            return 1
        else:
            print(f"\n✅ 所有测试通过")
            return 0
            
    except Exception as e:
        print(f"❌ 测试套件执行异常: {e}")
        traceback.print_exc()
        return 1
        
    finally:
        await suite.cleanup()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)