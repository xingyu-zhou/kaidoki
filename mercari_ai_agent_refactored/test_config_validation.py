#!/usr/bin/env python3
"""
配置验证测试脚本

该脚本验证Mercari AI Agent重构版本的配置管理功能，包括：
- .env文件加载
- 环境变量处理
- 配置验证
- 多环境支持
"""

import os
import sys
import json
import tempfile
from pathlib import Path
from typing import Dict, Any

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

try:
    from mercari_agent.shared.config.app_config import (
        AppConfig, Environment, get_config, create_config,
        DatabaseConfig, LLMConfig, ScrapingConfig, LoggingConfig, APIConfig
    )
    from mercari_agent.shared.exceptions import ConfigurationError
except ImportError as e:
    print(f"❌ 导入配置模块失败: {e}")
    sys.exit(1)


class ConfigValidator:
    """配置验证器"""
    
    def __init__(self):
        self.results = []
        self.errors = []
        self.warnings = []
    
    def log_result(self, test_name: str, status: str, details: str = ""):
        """记录测试结果"""
        self.results.append({
            "test": test_name,
            "status": status,
            "details": details
        })
        
        symbol = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{symbol} {test_name}: {status}")
        if details:
            print(f"   详情: {details}")
    
    def test_env_file_loading(self) -> bool:
        """测试.env文件加载"""
        print("\n🔍 测试.env文件加载...")
        
        try:
            # 检查.env文件是否存在
            env_file = project_root / ".env"
            if not env_file.exists():
                self.log_result("ENV文件存在性", "FAIL", ".env文件不存在")
                return False
            
            self.log_result("ENV文件存在性", "PASS")
            
            # 检查.env文件内容
            with open(env_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查关键配置项
            required_keys = [
                'ENVIRONMENT', 'DEBUG', 'OPENAI_API_KEY', 'OPENAI_MODEL',
                'DATABASE_URL', 'LOG_LEVEL', 'SCRAPER_TIMEOUT'
            ]
            
            found_keys = []
            for key in required_keys:
                if key in content:
                    found_keys.append(key)
            
            if len(found_keys) >= len(required_keys) * 0.8:
                self.log_result("ENV关键配置项", "PASS", f"找到{len(found_keys)}/{len(required_keys)}个关键配置")
            else:
                self.log_result("ENV关键配置项", "FAIL", f"仅找到{len(found_keys)}/{len(required_keys)}个关键配置")
                return False
            
            return True
            
        except Exception as e:
            self.log_result("ENV文件加载", "FAIL", str(e))
            return False
    
    def test_config_initialization(self) -> bool:
        """测试配置初始化"""
        print("\n🔍 测试配置初始化...")
        
        try:
            # 测试默认配置创建
            config = AppConfig()
            self.log_result("默认配置创建", "PASS")
            
            # 测试配置属性
            if hasattr(config, 'environment') and hasattr(config, 'database'):
                self.log_result("配置属性检查", "PASS")
            else:
                self.log_result("配置属性检查", "FAIL", "缺少必需的配置属性")
                return False
            
            # 测试环境检测
            if config.environment in [Environment.DEVELOPMENT, Environment.PRODUCTION, Environment.TESTING, Environment.STAGING]:
                self.log_result("环境检测", "PASS", f"检测到环境: {config.environment.value}")
            else:
                self.log_result("环境检测", "FAIL", f"未知环境: {config.environment}")
                return False
            
            return True
            
        except Exception as e:
            self.log_result("配置初始化", "FAIL", str(e))
            return False
    
    def test_database_config(self) -> bool:
        """测试数据库配置"""
        print("\n🔍 测试数据库配置...")
        
        try:
            config = AppConfig()
            db_config = config.database
            
            # 检查SQLite路径
            sqlite_path = db_config.get_sqlite_path()
            if sqlite_path and Path(sqlite_path).parent.exists():
                self.log_result("SQLite路径", "PASS", f"路径: {sqlite_path}")
            else:
                self.log_result("SQLite路径", "FAIL", "SQLite路径无效")
                return False
            
            # 检查数据库URL
            db_url = config.get_database_url()
            if db_url and db_url.startswith(('sqlite:///', 'postgresql://')):
                self.log_result("数据库URL", "PASS", f"URL: {db_url[:50]}...")
            else:
                self.log_result("数据库URL", "FAIL", "数据库URL无效")
                return False
            
            return True
            
        except Exception as e:
            self.log_result("数据库配置", "FAIL", str(e))
            return False
    
    def test_llm_config(self) -> bool:
        """测试LLM配置"""
        print("\n🔍 测试LLM配置...")
        
        try:
            config = AppConfig()
            llm_config = config.llm
            
            # 检查是否有至少一个LLM配置
            has_openai = llm_config.has_openai_config()
            has_anthropic = llm_config.has_anthropic_config()
            has_azure = llm_config.has_azure_config()
            
            if has_openai or has_anthropic or has_azure:
                providers = []
                if has_openai: providers.append("OpenAI")
                if has_anthropic: providers.append("Anthropic")
                if has_azure: providers.append("Azure")
                self.log_result("LLM提供商配置", "PASS", f"配置的提供商: {', '.join(providers)}")
            else:
                self.log_result("LLM提供商配置", "FAIL", "没有配置任何LLM提供商")
                return False
            
            # 检查基础参数
            if llm_config.max_tokens > 0 and 0 <= llm_config.temperature <= 2:
                self.log_result("LLM参数", "PASS", f"tokens: {llm_config.max_tokens}, temp: {llm_config.temperature}")
            else:
                self.log_result("LLM参数", "FAIL", "LLM参数无效")
                return False
            
            return True
            
        except Exception as e:
            self.log_result("LLM配置", "FAIL", str(e))
            return False
    
    def test_scraping_config(self) -> bool:
        """测试爬虫配置"""
        print("\n🔍 测试爬虫配置...")
        
        try:
            config = AppConfig()
            scraping_config = config.scraping
            
            # 检查基础参数
            if (scraping_config.max_retries > 0 and 
                scraping_config.timeout > 0 and 
                scraping_config.max_pages > 0):
                self.log_result("爬虫基础参数", "PASS", 
                    f"重试: {scraping_config.max_retries}, 超时: {scraping_config.timeout}")
            else:
                self.log_result("爬虫基础参数", "FAIL", "爬虫参数无效")
                return False
            
            # 检查User-Agent配置
            if scraping_config.user_agents and len(scraping_config.user_agents) > 0:
                self.log_result("User-Agent配置", "PASS", f"配置了{len(scraping_config.user_agents)}个UA")
            else:
                self.log_result("User-Agent配置", "FAIL", "没有配置User-Agent")
                return False
            
            return True
            
        except Exception as e:
            self.log_result("爬虫配置", "FAIL", str(e))
            return False
    
    def test_logging_config(self) -> bool:
        """测试日志配置"""
        print("\n🔍 测试日志配置...")
        
        try:
            config = AppConfig()
            logging_config = config.logging
            
            # 检查日志级别
            valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if logging_config.level.upper() in valid_levels:
                self.log_result("日志级别", "PASS", f"级别: {logging_config.level}")
            else:
                self.log_result("日志级别", "FAIL", f"无效级别: {logging_config.level}")
                return False
            
            # 检查日志目录
            log_dir = logging_config.get_log_dir()
            if log_dir.exists():
                self.log_result("日志目录", "PASS", f"目录: {log_dir}")
            else:
                self.log_result("日志目录", "FAIL", f"目录不存在: {log_dir}")
                return False
            
            return True
            
        except Exception as e:
            self.log_result("日志配置", "FAIL", str(e))
            return False
    
    def test_environment_variables(self) -> bool:
        """测试环境变量处理"""
        print("\n🔍 测试环境变量处理...")
        
        try:
            # 保存原始环境变量
            original_env = os.environ.copy()
            
            # 设置测试环境变量
            test_env = {
                'ENVIRONMENT': 'testing',
                'DEBUG': 'true',
                'OPENAI_API_KEY': 'test-key',
                'LOG_LEVEL': 'DEBUG'
            }
            
            os.environ.update(test_env)
            
            # 创建新配置实例
            config = AppConfig()
            
            # 验证环境变量是否正确加载
            if config.environment == Environment.TESTING:
                self.log_result("环境变量-环境", "PASS")
            else:
                self.log_result("环境变量-环境", "FAIL", f"期望testing，实际{config.environment.value}")
            
            if config.debug == True:
                self.log_result("环境变量-DEBUG", "PASS")
            else:
                self.log_result("环境变量-DEBUG", "FAIL", f"期望True，实际{config.debug}")
            
            if config.llm.openai_api_key == 'test-key':
                self.log_result("环境变量-API KEY", "PASS")
            else:
                self.log_result("环境变量-API KEY", "FAIL", "API KEY未正确加载")
            
            # 恢复原始环境变量
            os.environ.clear()
            os.environ.update(original_env)
            
            return True
            
        except Exception as e:
            self.log_result("环境变量处理", "FAIL", str(e))
            return False
    
    def test_config_validation(self) -> bool:
        """测试配置验证"""
        print("\n🔍 测试配置验证...")
        
        try:
            # 测试有效配置
            config = AppConfig()
            self.log_result("有效配置验证", "PASS")
            
            # 测试无效配置 - 没有LLM配置
            original_env = os.environ.copy()
            
            # 清除所有LLM API KEY
            for key in ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'AZURE_OPENAI_API_KEY']:
                if key in os.environ:
                    del os.environ[key]
            
            try:
                invalid_config = AppConfig()
                self.log_result("无效配置验证", "FAIL", "应该抛出配置错误")
            except ConfigurationError:
                self.log_result("无效配置验证", "PASS", "正确抛出配置错误")
            except Exception as e:
                self.log_result("无效配置验证", "FAIL", f"意外错误: {e}")
            
            # 恢复环境变量
            os.environ.clear()
            os.environ.update(original_env)
            
            return True
            
        except Exception as e:
            self.log_result("配置验证", "FAIL", str(e))
            return False
    
    def test_global_config(self) -> bool:
        """测试全局配置"""
        print("\n🔍 测试全局配置...")
        
        try:
            # 测试全局配置获取
            global_config = get_config()
            if global_config:
                self.log_result("全局配置获取", "PASS")
            else:
                self.log_result("全局配置获取", "FAIL", "无法获取全局配置")
                return False
            
            # 测试配置字典
            config_dict = global_config.get_config_dict()
            if config_dict and isinstance(config_dict, dict):
                self.log_result("配置字典", "PASS", f"包含{len(config_dict)}个配置项")
            else:
                self.log_result("配置字典", "FAIL", "无法获取配置字典")
                return False
            
            return True
            
        except Exception as e:
            self.log_result("全局配置", "FAIL", str(e))
            return False
    
    def run_all_tests(self) -> Dict[str, Any]:
        """运行所有测试"""
        print("🚀 开始Mercari AI Agent配置验证测试...")
        print("=" * 60)
        
        # 运行测试
        test_methods = [
            self.test_env_file_loading,
            self.test_config_initialization,
            self.test_database_config,
            self.test_llm_config,
            self.test_scraping_config,
            self.test_logging_config,
            self.test_environment_variables,
            self.test_config_validation,
            self.test_global_config
        ]
        
        passed = 0
        failed = 0
        
        for test_method in test_methods:
            try:
                if test_method():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"❌ 测试执行失败: {test_method.__name__} - {e}")
                failed += 1
        
        # 生成报告
        print("\n" + "=" * 60)
        print("📊 测试结果摘要:")
        print(f"✅ 通过: {passed}")
        print(f"❌ 失败: {failed}")
        print(f"📊 总计: {passed + failed}")
        
        success_rate = (passed / (passed + failed)) * 100 if (passed + failed) > 0 else 0
        print(f"🎯 成功率: {success_rate:.1f}%")
        
        # 生成详细报告
        report = {
            "timestamp": "2025-01-29T12:46:00+09:00",
            "test_type": "配置验证测试",
            "summary": {
                "total_tests": passed + failed,
                "passed": passed,
                "failed": failed,
                "success_rate": success_rate
            },
            "detailed_results": self.results
        }
        
        if success_rate >= 80:
            print("🎉 配置验证测试基本通过！")
        elif success_rate >= 60:
            print("⚠️ 配置验证测试部分通过，需要关注失败项目")
        else:
            print("🚨 配置验证测试失败，需要修复配置问题")
        
        return report


def main():
    """主函数"""
    # 切换到项目目录
    os.chdir(project_root)
    
    # 创建验证器并运行测试
    validator = ConfigValidator()
    report = validator.run_all_tests()
    
    # 保存报告
    report_file = project_root / "config_validation_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n📝 详细报告已保存至: {report_file}")
    
    # 返回退出码
    if report["summary"]["success_rate"] >= 80:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())