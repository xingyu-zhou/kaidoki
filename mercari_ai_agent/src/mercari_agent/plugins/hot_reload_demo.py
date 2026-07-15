"""
插件配置热加载演示

该文件演示了插件框架的配置热加载和schema验证功能：
1. 配置schema自动验证
2. 配置文件热加载监控
3. 配置模板自动生成
4. 配置变更实时通知
5. 配置验证状态查询

使用方法：
python hot_reload_demo.py

Author: Mercari AI Agent Team
"""

import asyncio
import json
import yaml
import time
from pathlib import Path
from typing import Dict, Any

from .config_manager import PluginConfigManager
from .schemas import PluginType, generate_plugin_template, validate_plugin_config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class HotReloadDemo:
    """热加载演示类"""
    
    def __init__(self):
        self.config_manager = PluginConfigManager()
        self.demo_dir = Path("demo_configs")
        self.demo_dir.mkdir(exist_ok=True)
        
        # 演示插件
        self.demo_plugins = {
            "session_demo": PluginType.SESSION_MANAGEMENT,
            "fingerprint_demo": PluginType.FINGERPRINT,
            "behavior_demo": PluginType.BEHAVIOR_SIMULATION,
            "captcha_demo": PluginType.CAPTCHA_DETECTION
        }
    
    async def run_demo(self):
        """运行完整演示"""
        logger.info("🚀 开始插件配置热加载演示")
        
        try:
            # 初始化配置管理器
            await self.config_manager.initialize()
            
            # 1. 演示配置模板生成
            await self.demo_template_generation()
            
            # 2. 演示schema验证
            await self.demo_schema_validation()
            
            # 3. 演示配置热加载
            await self.demo_hot_reload()
            
            # 4. 演示配置状态查询
            await self.demo_config_status()
            
            logger.info("✅ 热加载演示完成")
            
        except Exception as e:
            logger.error(f"❌ 演示运行失败: {e}")
        finally:
            await self.config_manager.stop()
    
    async def demo_template_generation(self):
        """演示配置模板生成"""
        logger.info("📝 演示1: 配置模板生成")
        
        try:
            for plugin_id, plugin_type in self.demo_plugins.items():
                # 生成YAML模板
                yaml_template = generate_plugin_template(plugin_type, format='yaml')
                yaml_path = self.demo_dir / f"{plugin_id}_template.yaml"
                
                with open(yaml_path, 'w', encoding='utf-8') as f:
                    f.write(yaml_template)
                
                logger.info(f"  ✓ 生成 {plugin_type.value} 模板: {yaml_path}")
                
                # 生成JSON模板
                json_template = generate_plugin_template(plugin_type, format='json')
                json_path = self.demo_dir / f"{plugin_id}_template.json"
                
                with open(json_path, 'w', encoding='utf-8') as f:
                    f.write(json_template)
                
                logger.info(f"  ✓ 生成 {plugin_type.value} JSON模板: {json_path}")
            
            logger.info("📝 模板生成演示完成\n")
            
        except Exception as e:
            logger.error(f"模板生成失败: {e}")
    
    async def demo_schema_validation(self):
        """演示schema验证"""
        logger.info("🔍 演示2: Schema配置验证")
        
        # 测试有效配置
        await self._test_valid_configs()
        
        # 测试无效配置
        await self._test_invalid_configs()
        
        logger.info("🔍 Schema验证演示完成\n")
    
    async def _test_valid_configs(self):
        """测试有效配置"""
        logger.info("  测试有效配置...")
        
        valid_session_config = {
            "enabled": True,
            "max_concurrent_sessions": 15,
            "session_timeout": 2400.0,
            "pool_size": 8,
            "enable_connection_pooling": True
        }
        
        result = validate_plugin_config(PluginType.SESSION_MANAGEMENT, valid_session_config)
        if result['valid']:
            logger.info("  ✓ 会话管理配置验证通过")
        else:
            logger.error(f"  ❌ 会话管理配置验证失败: {result['errors']}")
        
        valid_fingerprint_config = {
            "enabled": True,
            "max_fingerprints": 50,
            "rotation_interval": 3600.0,
            "enable_canvas_fingerprinting": True,
            "supported_platforms": ["windows", "macos", "linux"]
        }
        
        result = validate_plugin_config(PluginType.FINGERPRINT, valid_fingerprint_config)
        if result['valid']:
            logger.info("  ✓ 指纹管理配置验证通过")
        else:
            logger.error(f"  ❌ 指纹管理配置验证失败: {result['errors']}")
    
    async def _test_invalid_configs(self):
        """测试无效配置"""
        logger.info("  测试无效配置...")
        
        # 无效的会话管理配置（负数值）
        invalid_session_config = {
            "enabled": True,
            "max_concurrent_sessions": -5,  # 无效值
            "session_timeout": "invalid",   # 类型错误
            "pool_size": 0                  # 超出最小值
        }
        
        result = validate_plugin_config(PluginType.SESSION_MANAGEMENT, invalid_session_config)
        if not result['valid']:
            logger.info(f"  ✓ 检测到无效会话配置: {len(result['errors'])} 个错误")
            for error in result['errors'][:2]:  # 只显示前2个错误
                logger.info(f"    - {error['message']}")
        
        # 无效的指纹配置（缺少必需字段）
        invalid_fingerprint_config = {
            "enabled": True
            # 缺少必需的字段
        }
        
        result = validate_plugin_config(PluginType.FINGERPRINT, invalid_fingerprint_config)
        if not result['valid']:
            logger.info(f"  ✓ 检测到无效指纹配置: {len(result['errors'])} 个错误")
            for error in result['errors'][:2]:
                logger.info(f"    - {error['message']}")
    
    async def demo_hot_reload(self):
        """演示热加载功能"""
        logger.info("🔄 演示3: 配置热加载")
        
        try:
            # 创建演示配置文件
            demo_config_path = self.demo_dir / "session_demo.yaml"
            
            # 初始配置
            initial_config = {
                "enabled": True,
                "max_concurrent_sessions": 10,
                "session_timeout": 1800.0,
                "pool_size": 5
            }
            
            with open(demo_config_path, 'w', encoding='utf-8') as f:
                yaml.dump(initial_config, f, default_flow_style=False, indent=2)
            
            # 加载配置
            config = await self.config_manager.load_plugin_config(
                "session_demo", 
                PluginType.SESSION_MANAGEMENT,
                demo_config_path
            )
            logger.info(f"  ✓ 初始配置加载: max_sessions={config.get('max_concurrent_sessions')}")
            
            # 等待一秒
            await asyncio.sleep(1)
            
            # 修改配置文件
            updated_config = initial_config.copy()
            updated_config['max_concurrent_sessions'] = 20
            updated_config['session_timeout'] = 3600.0
            
            with open(demo_config_path, 'w', encoding='utf-8') as f:
                yaml.dump(updated_config, f, default_flow_style=False, indent=2)
            
            logger.info("  📝 修改了配置文件...")
            
            # 手动触发重新加载
            success = await self.config_manager.reload_plugin_config("session_demo")
            if success:
                new_config = await self.config_manager.get_plugin_config("session_demo")
                logger.info(f"  ✓ 配置热加载成功: max_sessions={new_config.get('max_concurrent_sessions')}")
            else:
                logger.error("  ❌ 配置热加载失败")
            
            logger.info("🔄 热加载演示完成\n")
            
        except Exception as e:
            logger.error(f"热加载演示失败: {e}")
    
    async def demo_config_status(self):
        """演示配置状态查询"""
        logger.info("📊 演示4: 配置状态查询")
        
        try:
            # 获取配置统计信息
            stats = self.config_manager.get_config_stats()
            logger.info("  配置管理器统计:")
            logger.info(f"    - 总配置数: {stats['total_configs']}")
            logger.info(f"    - 已加载配置: {stats['loaded_configs']}")
            logger.info(f"    - 验证错误: {stats['validation_errors']}")
            logger.info(f"    - Schema验证次数: {stats['schema_validations']}")
            logger.info(f"    - 平均加载时间: {stats['average_load_time']:.3f}s")
            
            # 获取插件验证状态
            if hasattr(self.config_manager, 'get_plugin_validation_status'):
                status = self.config_manager.get_plugin_validation_status("session_demo")
                if status:
                    logger.info("  会话插件验证状态:")
                    logger.info(f"    - 插件类型: {status['plugin_type']}")
                    logger.info(f"    - 验证有效: {status['valid']}")
                    logger.info(f"    - 错误数量: {len(status['errors'])}")
                    logger.info(f"    - 警告数量: {len(status['warnings'])}")
            
            # 验证所有配置
            if hasattr(self.config_manager, 'validate_all_configs'):
                all_results = await self.config_manager.validate_all_configs()
                logger.info(f"  全量验证结果: {len(all_results)} 个插件配置")
                
                for plugin_id, result in all_results.items():
                    status_icon = "✅" if result['valid'] else "❌"
                    logger.info(f"    {status_icon} {plugin_id} ({result['plugin_type']})")
            
            logger.info("📊 配置状态查询演示完成\n")
            
        except Exception as e:
            logger.error(f"配置状态查询失败: {e}")
    
    def cleanup(self):
        """清理演示文件"""
        try:
            import shutil
            if self.demo_dir.exists():
                shutil.rmtree(self.demo_dir)
            logger.info("🧹 清理演示文件完成")
        except Exception as e:
            logger.warning(f"清理文件失败: {e}")


async def main():
    """主函数"""
    demo = HotReloadDemo()
    
    try:
        await demo.run_demo()
    finally:
        # 可选择是否清理演示文件
        # demo.cleanup()
        pass


if __name__ == "__main__":
    asyncio.run(main())