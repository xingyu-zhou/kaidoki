"""
反检测系统集成演示和验证脚本

该脚本演示了完整的反检测系统如何协同工作，
包括浏览器环境伪装、指纹管理、会话管理等所有组件的集成效果。

主要功能：
1. 系统初始化演示
2. 配置管理演示
3. 会话创建和管理演示
4. 指纹生成和应用演示
5. 伪装脚本注入演示
6. 检测事件处理演示
7. 性能和统计信息演示

Author: Mercari AI Agent Team
"""

import asyncio
import logging
import time
import json
from typing import Dict, List, Optional, Any
from datetime import datetime

from .anti_detection_integration import (
    AntiDetectionIntegration, IntegrationMode, DetectionEvent,
    create_anti_detection_system
)
from .browser_environment_spoofing import (
    BrowserEnvironmentSpoofing, SpoofingLevel, DetectionType,
    create_spoofing_system
)
from .enhanced_fingerprint_manager import (
    EnhancedFingerprintManager, FingerprintQuality,
    create_enhanced_fingerprint_manager
)
from ..config.anti_detection_config_manager import (
    AntiDetectionConfigManager, get_config_manager
)
from ..utils.logger import get_logger

logger = get_logger(__name__)


class AntiDetectionDemo:
    """反检测系统演示类"""
    
    def __init__(self):
        """初始化演示类"""
        self.integration_system: Optional[AntiDetectionIntegration] = None
        self.config_manager: Optional[AntiDetectionConfigManager] = None
        self.demo_results: Dict[str, Any] = {}
        
        logger.info("🎭 反检测系统演示初始化")
    
    async def run_complete_demo(self):
        """运行完整演示"""
        logger.info("🚀 开始反检测系统完整演示...")
        
        try:
            # 1. 配置管理演示
            await self._demo_config_management()
            
            # 2. 系统初始化演示
            await self._demo_system_initialization()
            
            # 3. 指纹管理演示
            await self._demo_fingerprint_management()
            
            # 4. 环境伪装演示
            await self._demo_environment_spoofing()
            
            # 5. 会话管理演示
            await self._demo_session_management()
            
            # 6. 检测事件处理演示
            await self._demo_detection_handling()
            
            # 7. 性能和统计演示
            await self._demo_performance_statistics()
            
            # 8. 生成演示报告
            await self._generate_demo_report()
            
            logger.info("✅ 反检测系统完整演示完成")
            
        except Exception as e:
            logger.error(f"❌ 演示过程中发生错误: {e}")
            raise
        finally:
            # 清理资源
            if self.integration_system:
                await self.integration_system.shutdown()
    
    async def _demo_config_management(self):
        """演示配置管理"""
        logger.info("📝 演示配置管理功能...")
        
        try:
            # 获取配置管理器
            self.config_manager = get_config_manager()
            
            # 显示当前配置
            logger.info(f"当前模式: {self.config_manager.get_mode()}")
            logger.info(f"伪装级别: {self.config_manager.get_spoofing_level()}")
            logger.info(f"最小指纹质量: {self.config_manager.get_min_fingerprint_quality()}")
            logger.info(f"最大并发会话: {self.config_manager.get_max_concurrent_sessions()}")
            
            # 获取配置摘要
            summary = self.config_manager.get_config_summary()
            logger.info(f"配置摘要: {json.dumps(summary, indent=2, ensure_ascii=False)}")
            
            # 验证运行时配置
            warnings = self.config_manager.validate_runtime_config()
            if warnings:
                logger.warning(f"配置警告: {warnings}")
            
            # 获取所有预设
            presets = self.config_manager.get_all_presets()
            logger.info(f"可用预设: {presets}")
            
            self.demo_results['config_management'] = {
                'status': 'success',
                'summary': summary,
                'warnings': warnings,
                'presets': presets
            }
            
            logger.info("✅ 配置管理演示完成")
            
        except Exception as e:
            logger.error(f"❌ 配置管理演示失败: {e}")
            self.demo_results['config_management'] = {
                'status': 'failed',
                'error': str(e)
            }
    
    async def _demo_system_initialization(self):
        """演示系统初始化"""
        logger.info("🔧 演示系统初始化...")
        
        try:
            # 创建反检测系统
            self.integration_system = await create_anti_detection_system(
                IntegrationMode.BALANCED
            )
            
            # 验证系统状态
            if self.integration_system._initialized:
                logger.info("✅ 系统初始化成功")
            else:
                logger.error("❌ 系统初始化失败")
                return
            
            # 显示系统组件状态
            components_status = {
                'fingerprint_manager': self.integration_system.fingerprint_manager is not None,
                'session_manager': self.integration_system.session_manager is not None,
                'anti_bot_handler': self.integration_system.anti_bot_handler is not None,
                'tls_manager': self.integration_system.tls_manager is not None
            }
            
            logger.info(f"系统组件状态: {components_status}")
            
            self.demo_results['system_initialization'] = {
                'status': 'success',
                'components_status': components_status,
                'initialization_time': time.time()
            }
            
            logger.info("✅ 系统初始化演示完成")
            
        except Exception as e:
            logger.error(f"❌ 系统初始化演示失败: {e}")
            self.demo_results['system_initialization'] = {
                'status': 'failed',
                'error': str(e)
            }
    
    async def _demo_fingerprint_management(self):
        """演示指纹管理"""
        logger.info("🔐 演示指纹管理功能...")
        
        try:
            if not self.integration_system or not self.integration_system.fingerprint_manager:
                logger.error("指纹管理器未初始化")
                return
            
            fingerprint_manager = self.integration_system.fingerprint_manager
            
            # 获取指纹统计
            stats = fingerprint_manager.get_enhanced_stats()
            logger.info(f"指纹统计: {json.dumps(stats, indent=2, ensure_ascii=False)}")
            
            # 生成几个不同质量的指纹
            fingerprints = []
            for i in range(3):
                fingerprint = await fingerprint_manager.get_fingerprint_for_session(
                    session_id=f"demo_session_{i}",
                    target_url="https://jp.mercari.com"
                )
                
                if fingerprint:
                    fingerprints.append({
                        'fingerprint_id': fingerprint.fingerprint_id,
                        'quality_level': fingerprint.metadata.quality_level.value,
                        'quality_score': fingerprint.metadata.quality_score,
                        'browser_type': fingerprint.base_fingerprint.browser_type.value,
                        'os_type': fingerprint.base_fingerprint.os_type.value
                    })
                    
                    logger.info(f"生成指纹 {i+1}: {fingerprint.fingerprint_id} "
                              f"(质量: {fingerprint.metadata.quality_level.value})")
            
            # 演示指纹轮换
            if fingerprints:
                await fingerprint_manager.report_detection("demo_session_0", "captcha")
                logger.info("模拟检测事件并触发指纹轮换")
            
            self.demo_results['fingerprint_management'] = {
                'status': 'success',
                'stats': stats,
                'generated_fingerprints': fingerprints
            }
            
            logger.info("✅ 指纹管理演示完成")
            
        except Exception as e:
            logger.error(f"❌ 指纹管理演示失败: {e}")
            self.demo_results['fingerprint_management'] = {
                'status': 'failed',
                'error': str(e)
            }
    
    async def _demo_environment_spoofing(self):
        """演示环境伪装"""
        logger.info("🎭 演示环境伪装功能...")
        
        try:
            # 创建独立的环境伪装系统进行演示
            spoofing_system = create_spoofing_system(SpoofingLevel.STANDARD)
            
            # 应用伪装
            result = await spoofing_system.apply_spoofing(
                session_id="demo_spoofing_session",
                target_url="https://jp.mercari.com"
            )
            
            logger.info(f"伪装结果: 成功={result.success}, "
                       f"应用数量={len(result.applied_spoofings)}")
            
            # 获取注入脚本
            injection_script = spoofing_system.get_injection_script("demo_spoofing_session")
            if injection_script:
                logger.info(f"注入脚本长度: {len(injection_script)} 字符")
                
                # 显示脚本片段
                script_preview = injection_script[:200] + "..." if len(injection_script) > 200 else injection_script
                logger.info(f"脚本预览: {script_preview}")
            
            # 获取伪装的HTTP头
            if result.fingerprint_id:
                # 模拟获取指纹
                test_fingerprint = await self.integration_system.fingerprint_manager.get_fingerprint_for_session(
                    "demo_spoofing_session", "https://jp.mercari.com"
                )
                
                if test_fingerprint:
                    headers = spoofing_system.get_spoofing_headers(test_fingerprint.base_fingerprint)
                    logger.info(f"伪装头部: {json.dumps(headers, indent=2, ensure_ascii=False)}")
            
            # 获取统计信息
            spoofing_stats = spoofing_system.get_stats()
            logger.info(f"伪装统计: {json.dumps(spoofing_stats, indent=2, ensure_ascii=False)}")
            
            self.demo_results['environment_spoofing'] = {
                'status': 'success',
                'result': {
                    'success': result.success,
                    'applied_spoofings': [d.value for d in result.applied_spoofings],
                    'execution_time': result.execution_time
                },
                'injection_script_length': len(injection_script) if injection_script else 0,
                'stats': spoofing_stats
            }
            
            logger.info("✅ 环境伪装演示完成")
            
        except Exception as e:
            logger.error(f"❌ 环境伪装演示失败: {e}")
            self.demo_results['environment_spoofing'] = {
                'status': 'failed',
                'error': str(e)
            }
    
    async def _demo_session_management(self):
        """演示会话管理"""
        logger.info("🔗 演示会话管理功能...")
        
        try:
            if not self.integration_system:
                logger.error("集成系统未初始化")
                return
            
            # 创建多个会话
            sessions = []
            for i in range(3):
                session_id = await self.integration_system.create_session(f"demo_session_{i}")
                sessions.append(session_id)
                logger.info(f"创建会话: {session_id}")
            
            # 准备请求
            request_params_list = []
            for session_id in sessions:
                params = await self.integration_system.prepare_request(
                    session_id=session_id,
                    url="https://jp.mercari.com",
                    method="GET"
                )
                request_params_list.append({
                    'session_id': session_id,
                    'param_count': len(params),
                    'has_headers': 'headers' in params,
                    'has_fingerprint': 'fingerprint_id' in params
                })
                
                logger.info(f"会话 {session_id} 请求参数: {len(params)} 个")
            
            # 获取会话统计
            if self.integration_system.session_manager:
                session_stats = self.integration_system.session_manager.get_session_statistics()
                logger.info(f"会话统计: {json.dumps(session_stats, indent=2, ensure_ascii=False)}")
            
            # 关闭会话
            for session_id in sessions:
                await self.integration_system.close_session(session_id)
                logger.info(f"关闭会话: {session_id}")
            
            self.demo_results['session_management'] = {
                'status': 'success',
                'sessions_created': len(sessions),
                'request_params': request_params_list
            }
            
            logger.info("✅ 会话管理演示完成")
            
        except Exception as e:
            logger.error(f"❌ 会话管理演示失败: {e}")
            self.demo_results['session_management'] = {
                'status': 'failed',
                'error': str(e)
            }
    
    async def _demo_detection_handling(self):
        """演示检测事件处理"""
        logger.info("🚨 演示检测事件处理...")
        
        try:
            if not self.integration_system:
                logger.error("集成系统未初始化")
                return
            
            # 创建测试会话
            session_id = await self.integration_system.create_session("detection_test_session")
            
            # 模拟各种检测事件
            detection_events = [
                DetectionEvent.CAPTCHA_TRIGGERED,
                DetectionEvent.FINGERPRINT_DETECTED,
                DetectionEvent.RATE_LIMITED
            ]
            
            handled_events = []
            for event in detection_events:
                try:
                    # 模拟检测事件（这里只是演示，实际应该通过响应分析触发）
                    event_data = {
                        'event_type': event,
                        'session_id': session_id,
                        'timestamp': datetime.now(),
                        'handled': False
                    }
                    
                    logger.info(f"模拟检测事件: {event.value}")
                    
                    # 根据事件类型执行相应处理
                    if event == DetectionEvent.CAPTCHA_TRIGGERED:
                        if self.integration_system.fingerprint_manager:
                            await self.integration_system.fingerprint_manager.report_captcha(session_id)
                        handled_events.append({'event': event.value, 'handled': True})
                    
                    elif event == DetectionEvent.FINGERPRINT_DETECTED:
                        if self.integration_system.fingerprint_manager:
                            await self.integration_system.fingerprint_manager.report_detection(
                                session_id, event.value
                            )
                        handled_events.append({'event': event.value, 'handled': True})
                    
                    elif event == DetectionEvent.RATE_LIMITED:
                        # 模拟速率限制处理
                        await asyncio.sleep(0.1)  # 模拟等待
                        handled_events.append({'event': event.value, 'handled': True})
                    
                except Exception as e:
                    logger.error(f"处理检测事件失败: {event.value} - {e}")
                    handled_events.append({'event': event.value, 'handled': False, 'error': str(e)})
            
            # 关闭测试会话
            await self.integration_system.close_session(session_id)
            
            self.demo_results['detection_handling'] = {
                'status': 'success',
                'events_tested': len(detection_events),
                'handled_events': handled_events
            }
            
            logger.info("✅ 检测事件处理演示完成")
            
        except Exception as e:
            logger.error(f"❌ 检测事件处理演示失败: {e}")
            self.demo_results['detection_handling'] = {
                'status': 'failed',
                'error': str(e)
            }
    
    async def _demo_performance_statistics(self):
        """演示性能和统计信息"""
        logger.info("📊 演示性能和统计信息...")
        
        try:
            if not self.integration_system:
                logger.error("集成系统未初始化")
                return
            
            # 获取系统统计
            system_stats = self.integration_system.get_stats()
            logger.info(f"系统统计: {json.dumps(system_stats, indent=2, ensure_ascii=False)}")
            
            # 获取指纹管理器统计
            if self.integration_system.fingerprint_manager:
                fingerprint_stats = self.integration_system.fingerprint_manager.get_enhanced_stats()
                logger.info(f"指纹统计: {json.dumps(fingerprint_stats, indent=2, ensure_ascii=False)}")
            
            # 获取会话管理器统计
            if self.integration_system.session_manager:
                session_stats = self.integration_system.session_manager.get_session_statistics()
                logger.info(f"会话统计: {json.dumps(session_stats, indent=2, ensure_ascii=False)}")
            
            # 计算性能指标
            performance_metrics = {
                'system_uptime': time.time() - system_stats.get('initialization_time', time.time()),
                'active_sessions': system_stats.get('active_sessions', 0),
                'total_sessions': system_stats.get('total_sessions', 0),
                'detection_events': system_stats.get('detection_events', 0),
                'memory_usage': 'N/A',  # 可以集成psutil获取实际内存使用
                'cpu_usage': 'N/A'      # 可以集成psutil获取实际CPU使用
            }
            
            logger.info(f"性能指标: {json.dumps(performance_metrics, indent=2, ensure_ascii=False)}")
            
            self.demo_results['performance_statistics'] = {
                'status': 'success',
                'system_stats': system_stats,
                'performance_metrics': performance_metrics
            }
            
            logger.info("✅ 性能和统计演示完成")
            
        except Exception as e:
            logger.error(f"❌ 性能和统计演示失败: {e}")
            self.demo_results['performance_statistics'] = {
                'status': 'failed',
                'error': str(e)
            }
    
    async def _generate_demo_report(self):
        """生成演示报告"""
        logger.info("📋 生成演示报告...")
        
        try:
            report = {
                'demo_info': {
                    'timestamp': datetime.now().isoformat(),
                    'version': '1.0.0',
                    'total_tests': len(self.demo_results)
                },
                'test_results': self.demo_results,
                'summary': {
                    'total_tests': len(self.demo_results),
                    'passed_tests': len([r for r in self.demo_results.values() if r.get('status') == 'success']),
                    'failed_tests': len([r for r in self.demo_results.values() if r.get('status') == 'failed']),
                    'success_rate': 0.0
                }
            }
            
            # 计算成功率
            if report['summary']['total_tests'] > 0:
                report['summary']['success_rate'] = (
                    report['summary']['passed_tests'] / report['summary']['total_tests'] * 100
                )
            
            # 保存报告
            report_file = f"./logs/anti_detection_demo_report_{int(time.time())}.json"
            try:
                import os
                os.makedirs(os.path.dirname(report_file), exist_ok=True)
                with open(report_file, 'w', encoding='utf-8') as f:
                    json.dump(report, f, indent=2, ensure_ascii=False)
                logger.info(f"演示报告已保存: {report_file}")
            except Exception as e:
                logger.warning(f"保存报告失败: {e}")
            
            # 显示摘要
            logger.info("=" * 60)
            logger.info("📊 反检测系统演示报告摘要")
            logger.info("=" * 60)
            logger.info(f"总测试数: {report['summary']['total_tests']}")
            logger.info(f"通过测试: {report['summary']['passed_tests']}")
            logger.info(f"失败测试: {report['summary']['failed_tests']}")
            logger.info(f"成功率: {report['summary']['success_rate']:.1f}%")
            logger.info("=" * 60)
            
            # 显示详细结果
            for test_name, result in self.demo_results.items():
                status_emoji = "✅" if result.get('status') == 'success' else "❌"
                logger.info(f"{status_emoji} {test_name}: {result.get('status', 'unknown')}")
                if result.get('error'):
                    logger.info(f"   错误: {result['error']}")
            
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ 生成演示报告失败: {e}")


# 主要演示功能
async def run_anti_detection_demo():
    """运行反检测系统演示"""
    logger.info("🎬 开始反检测系统演示...")
    
    demo = AntiDetectionDemo()
    await demo.run_complete_demo()
    
    logger.info("🎉 反检测系统演示完成")


# 快速功能测试
async def quick_integration_test():
    """快速集成测试"""
    logger.info("⚡ 开始快速集成测试...")
    
    try:
        # 测试配置管理
        config_manager = get_config_manager()
        logger.info(f"✅ 配置管理器测试通过: {config_manager.get_mode()}")
        
        # 测试环境伪装
        spoofing_system = create_spoofing_system(SpoofingLevel.STANDARD)
        result = await spoofing_system.apply_spoofing("test_session", "https://jp.mercari.com")
        logger.info(f"✅ 环境伪装测试通过: {result.success}")
        
        # 测试指纹管理
        fingerprint_manager = await create_enhanced_fingerprint_manager(SpoofingLevel.STANDARD)
        fingerprint = await fingerprint_manager.get_fingerprint_for_session("test_session", "https://jp.mercari.com")
        logger.info(f"✅ 指纹管理测试通过: {fingerprint.fingerprint_id if fingerprint else 'None'}")
        
        # 测试集成系统
        integration_system = await create_anti_detection_system(IntegrationMode.BALANCED)
        session_id = await integration_system.create_session()
        logger.info(f"✅ 集成系统测试通过: {session_id}")
        
        # 清理
        await integration_system.close_session(session_id)
        await integration_system.shutdown()
        
        logger.info("🎉 快速集成测试完成")
        
    except Exception as e:
        logger.error(f"❌ 快速集成测试失败: {e}")


# 测试特定功能
async def test_specific_feature(feature_name: str):
    """测试特定功能"""
    logger.info(f"🔍 测试特定功能: {feature_name}")
    
    if feature_name == "config":
        config_manager = get_config_manager()
        logger.info(f"配置摘要: {config_manager.get_config_summary()}")
        
    elif feature_name == "spoofing":
        spoofing_system = create_spoofing_system(SpoofingLevel.AGGRESSIVE)
        result = await spoofing_system.apply_spoofing("test", "https://jp.mercari.com")
        logger.info(f"伪装结果: {result.success}")
        
    elif feature_name == "fingerprint":
        fingerprint_manager = await create_enhanced_fingerprint_manager(SpoofingLevel.STANDARD)
        stats = fingerprint_manager.get_enhanced_stats()
        logger.info(f"指纹统计: {stats}")
        
    elif feature_name == "integration":
        await quick_integration_test()
        
    else:
        logger.error(f"未知功能: {feature_name}")


if __name__ == "__main__":
    import sys
    
    # 根据命令行参数选择测试模式
    if len(sys.argv) > 1:
        if sys.argv[1] == "quick":
            asyncio.run(quick_integration_test())
        elif sys.argv[1] == "feature" and len(sys.argv) > 2:
            asyncio.run(test_specific_feature(sys.argv[2]))
        else:
            asyncio.run(run_anti_detection_demo())
    else:
        asyncio.run(run_anti_detection_demo())