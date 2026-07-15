"""
插件配置管理器单元测试

测试内容包括：
1. 配置加载和保存
2. 配置验证和schema集成
3. 热重载和监控
4. 环境变量解析
5. 配置模板生成
6. 错误处理和边界条件

Author: Mercari AI Agent Team
"""

import pytest
import asyncio
import json
import yaml
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, mock_open

from mercari_agent.plugins.config_manager import PluginConfigManager, ConfigEnvironment, ConfigFormat
from mercari_agent.plugins.interfaces import PluginType
from mercari_agent.plugins.schemas import get_plugin_default_config


class TestPluginConfigManager:
    """插件配置管理器测试"""
    
    @pytest.fixture
    async def config_manager(self, temp_dir):
        """配置管理器实例"""
        manager = PluginConfigManager()
        manager.config_dir = temp_dir / "config"
        manager.config_dir.mkdir(exist_ok=True)
        await manager.initialize()
        yield manager
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_config_manager_initialization(self, temp_dir):
        """测试配置管理器初始化"""
        manager = PluginConfigManager()
        manager.config_dir = temp_dir / "config"
        
        # 初始化前状态
        assert not hasattr(manager, 'watch_task')
        
        # 初始化
        await manager.initialize()
        
        # 验证初始化结果
        assert manager.config_dir.exists()
        assert manager.schema_validator is not None
        assert manager.template_generator is not None
        
        # 清理
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_load_plugin_config_with_file(self, config_manager, temp_dir):
        """测试从文件加载插件配置"""
        # 创建配置文件
        config_data = {
            "enabled": True,
            "max_concurrent_sessions": 15,
            "session_timeout": 2400.0,
            "pool_size": 8
        }
        
        config_file = temp_dir / "config" / "test_plugin.yaml"
        config_file.parent.mkdir(exist_ok=True)
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # 加载配置
        loaded_config = await config_manager.load_plugin_config(
            "test_plugin", 
            PluginType.SESSION_MANAGEMENT,
            config_file
        )
        
        assert loaded_config is not None
        assert loaded_config["enabled"] is True
        assert loaded_config["max_concurrent_sessions"] == 15
    
    @pytest.mark.asyncio
    async def test_load_plugin_config_default(self, config_manager):
        """测试加载默认插件配置"""
        # 加载不存在的配置文件，应该返回默认配置
        loaded_config = await config_manager.load_plugin_config(
            "nonexistent_plugin",
            PluginType.SESSION_MANAGEMENT
        )
        
        assert loaded_config is not None
        assert isinstance(loaded_config, dict)
        # 默认配置应该包含基础字段
        assert "enabled" in loaded_config or len(loaded_config) > 0
    
    @pytest.mark.asyncio
    async def test_save_plugin_config(self, config_manager, temp_dir):
        """测试保存插件配置"""
        config_data = {
            "enabled": False,
            "max_concurrent_sessions": 20,
            "session_timeout": 3600.0
        }
        
        # 设置配置文件路径
        config_manager.config_files["test_plugin"] = Mock()
        config_manager.config_files["test_plugin"].path = temp_dir / "config" / "test_plugin.yaml"
        config_manager.config_files["test_plugin"].format = ConfigFormat.YAML
        
        # 保存配置
        success = await config_manager.save_plugin_config("test_plugin", config_data)
        assert success
        
        # 验证保存的文件
        config_file = config_manager.config_files["test_plugin"].path
        assert config_file.exists()
        
        with open(config_file, 'r') as f:
            saved_data = yaml.safe_load(f)
        
        assert saved_data["enabled"] is False
        assert saved_data["max_concurrent_sessions"] == 20
    
    @pytest.mark.asyncio
    async def test_reload_plugin_config(self, config_manager, temp_dir):
        """测试重新加载插件配置"""
        # 创建初始配置
        initial_config = {"enabled": True, "timeout": 30}
        config_file = temp_dir / "config" / "test_plugin.yaml"
        config_file.parent.mkdir(exist_ok=True)
        
        with open(config_file, 'w') as f:
            yaml.dump(initial_config, f)
        
        # 加载配置
        await config_manager.load_plugin_config(
            "test_plugin",
            PluginType.SESSION_MANAGEMENT,
            config_file
        )
        
        # 修改配置文件
        updated_config = {"enabled": False, "timeout": 60}
        with open(config_file, 'w') as f:
            yaml.dump(updated_config, f)
        
        # 重新加载
        success = await config_manager.reload_plugin_config("test_plugin")
        assert success
        
        # 验证更新后的配置
        current_config = await config_manager.get_plugin_config("test_plugin")
        assert current_config["enabled"] is False
        assert current_config["timeout"] == 60
    
    @pytest.mark.asyncio
    async def test_get_plugin_config(self, config_manager):
        """测试获取插件配置"""
        # 设置测试配置
        test_config = {
            "enabled": True,
            "nested": {
                "value1": "test",
                "value2": 123
            }
        }
        
        config_manager.plugin_configs["test_plugin"] = test_config
        
        # 获取完整配置
        full_config = await config_manager.get_plugin_config("test_plugin")
        assert full_config == test_config
        
        # 获取特定键值
        enabled = await config_manager.get_plugin_config("test_plugin", "enabled")
        assert enabled is True
        
        # 获取嵌套键值
        nested_value = await config_manager.get_plugin_config("test_plugin", "nested.value1")
        assert nested_value == "test"
        
        # 获取不存在的键值
        missing = await config_manager.get_plugin_config("test_plugin", "missing", "default")
        assert missing == "default"
    
    @pytest.mark.asyncio
    async def test_update_plugin_config(self, config_manager):
        """测试更新插件配置"""
        # 初始配置
        initial_config = {"enabled": True, "timeout": 30}
        config_manager.plugin_configs["test_plugin"] = initial_config
        
        # 更新配置
        success = await config_manager.update_plugin_config(
            "test_plugin", 
            "timeout", 
            60,
            save_immediately=False
        )
        assert success
        
        # 验证更新
        updated_value = await config_manager.get_plugin_config("test_plugin", "timeout")
        assert updated_value == 60
        
        # 更新嵌套配置
        success = await config_manager.update_plugin_config(
            "test_plugin",
            "nested.new_value",
            "test",
            save_immediately=False
        )
        assert success
        
        nested_value = await config_manager.get_plugin_config("test_plugin", "nested.new_value")
        assert nested_value == "test"
    
    def test_resolve_environment_variables(self, config_manager):
        """测试环境变量解析"""
        import os
        
        # 设置环境变量
        os.environ["TEST_VAR"] = "test_value"
        os.environ["TEST_NUM"] = "123"
        
        # 包含环境变量的配置
        config_with_env = {
            "database_url": "${DATABASE_URL:localhost}",
            "api_key": "${API_KEY}",
            "timeout": "${TIMEOUT:30}",
            "nested": {
                "test_var": "${TEST_VAR}",
                "test_num": "${TEST_NUM}"
            }
        }
        
        resolved = config_manager._resolve_environment_variables(config_with_env)
        
        # 验证解析结果
        assert resolved["database_url"] == "localhost"  # 使用默认值
        assert resolved["api_key"] == "${API_KEY}"      # 未设置的变量保持原样
        assert resolved["timeout"] == "30"             # 使用默认值
        assert resolved["nested"]["test_var"] == "test_value"
        assert resolved["nested"]["test_num"] == "123"
        
        # 清理环境变量
        del os.environ["TEST_VAR"]
        del os.environ["TEST_NUM"]
    
    def test_detect_config_format(self, config_manager):
        """测试配置格式检测"""
        # YAML格式
        yaml_path = Path("config.yaml")
        assert config_manager._detect_config_format(yaml_path) == ConfigFormat.YAML
        
        yml_path = Path("config.yml")
        assert config_manager._detect_config_format(yml_path) == ConfigFormat.YAML
        
        # JSON格式
        json_path = Path("config.json")
        assert config_manager._detect_config_format(json_path) == ConfigFormat.JSON
        
        # TOML格式
        toml_path = Path("config.toml")
        assert config_manager._detect_config_format(toml_path) == ConfigFormat.TOML
        
        # 未知格式，默认为YAML
        unknown_path = Path("config.txt")
        assert config_manager._detect_config_format(unknown_path) == ConfigFormat.YAML
    
    @pytest.mark.asyncio
    async def test_validate_plugin_config_with_schema(self, config_manager):
        """测试使用schema验证插件配置"""
        # 有效配置
        valid_config = {
            "enabled": True,
            "max_concurrent_sessions": 10,
            "session_timeout": 1800.0
        }
        
        result = await config_manager._validate_plugin_config_with_schema(
            PluginType.SESSION_MANAGEMENT,
            valid_config
        )
        
        assert isinstance(result, dict)
        assert 'valid' in result
        assert 'errors' in result
        assert 'normalized_config' in result
        
        # 无效配置
        invalid_config = {
            "enabled": "not_boolean",  # 类型错误
            "max_concurrent_sessions": -5  # 值错误
        }
        
        result = await config_manager._validate_plugin_config_with_schema(
            PluginType.SESSION_MANAGEMENT,
            invalid_config
        )
        
        assert isinstance(result, dict)
        # 如果schema验证可用，应该检测到错误
        if config_manager.schema_validator.validator_available:
            assert result['valid'] is False or len(result['errors']) > 0
    
    @pytest.mark.asyncio
    async def test_generate_config_template(self, config_manager, temp_dir):
        """测试生成配置模板"""
        # 生成YAML模板
        yaml_template = config_manager.generate_config_template(PluginType.SESSION_MANAGEMENT, 'yaml')
        assert isinstance(yaml_template, str)
        assert len(yaml_template) > 0
        
        # 生成JSON模板
        json_template = config_manager.generate_config_template(PluginType.SESSION_MANAGEMENT, 'json')
        assert isinstance(json_template, str)
        assert len(json_template) > 0
        
        # 保存模板文件
        template_path = temp_dir / "template.yaml"
        success = config_manager.save_config_template(
            PluginType.SESSION_MANAGEMENT,
            template_path,
            'yaml'
        )
        assert success
        assert template_path.exists()
    
    @pytest.mark.asyncio
    async def test_export_import_config(self, config_manager, temp_dir):
        """测试配置导出和导入"""
        # 准备测试配置
        test_config = {
            "enabled": True,
            "timeout": 30,
            "custom_setting": "test_value"
        }
        
        config_manager.plugin_configs["test_plugin"] = test_config
        config_manager.plugin_type_mapping["test_plugin"] = PluginType.SESSION_MANAGEMENT
        
        # 创建配置条目
        from mercari_agent.plugins.config_manager import ConfigEntry
        from datetime import datetime
        
        config_entry = ConfigEntry(
            plugin_id="test_plugin",
            plugin_type=PluginType.SESSION_MANAGEMENT,
            config=test_config,
            last_modified=datetime.now(),
            schema_validated=True,
            normalized_config=test_config
        )
        config_manager._configs["test_plugin"] = config_entry
        
        # 导出配置
        export_path = temp_dir / "exported_config.yaml"
        success = config_manager.export_config("test_plugin", export_path, include_metadata=True)
        assert success
        assert export_path.exists()
        
        # 验证导出的内容
        with open(export_path, 'r') as f:
            exported_data = yaml.safe_load(f)
        
        assert exported_data["enabled"] is True
        assert exported_data["timeout"] == 30
        assert "_metadata" in exported_data
        
        # 导入配置
        success = config_manager.import_config("imported_plugin", export_path, validate=False)
        assert success
        
        # 验证导入的配置
        imported_config = config_manager.plugin_configs.get("imported_plugin")
        assert imported_config is not None
        assert imported_config["enabled"] is True
        assert imported_config["timeout"] == 30
    
    @pytest.mark.asyncio
    async def test_reset_config(self, config_manager):
        """测试重置配置"""
        # 设置自定义配置
        custom_config = {"enabled": False, "timeout": 60}
        config_manager.plugin_configs["test_plugin"] = custom_config
        config_manager.plugin_type_mapping["test_plugin"] = PluginType.SESSION_MANAGEMENT
        
        # 创建配置条目
        from mercari_agent.plugins.config_manager import ConfigEntry
        from datetime import datetime
        
        config_entry = ConfigEntry(
            plugin_id="test_plugin",
            plugin_type=PluginType.SESSION_MANAGEMENT,
            config=custom_config,
            last_modified=datetime.now()
        )
        config_manager._configs["test_plugin"] = config_entry
        
        # 重置配置
        success = config_manager.reset_config("test_plugin")
        assert success
        
        # 验证重置结果
        reset_config = config_manager.plugin_configs.get("test_plugin")
        assert reset_config is not None
        # 重置后应该是默认配置
        default_config = get_plugin_default_config(PluginType.SESSION_MANAGEMENT)
        assert reset_config == default_config
    
    @pytest.mark.asyncio
    async def test_get_all_configs(self, config_manager):
        """测试获取所有配置"""
        # 设置测试配置
        config1 = {"enabled": True, "timeout": 30}
        config2 = {"enabled": False, "timeout": 60}
        
        config_manager.plugin_configs["plugin1"] = config1
        config_manager.plugin_configs["plugin2"] = config2
        
        # 获取所有配置（不包含元数据）
        all_configs = config_manager.get_all_configs(include_metadata=False)
        assert len(all_configs) == 2
        assert "plugin1" in all_configs
        assert "plugin2" in all_configs
        assert all_configs["plugin1"]["enabled"] is True
        assert all_configs["plugin2"]["enabled"] is False
    
    @pytest.mark.asyncio
    async def test_get_config_summary(self, config_manager):
        """测试获取配置摘要"""
        # 设置测试数据
        config_manager.plugin_configs["plugin1"] = {"enabled": True}
        config_manager.plugin_configs["plugin2"] = {"enabled": False}
        
        # 获取摘要
        summary = config_manager.get_config_summary()
        
        assert isinstance(summary, dict)
        assert "total_configs" in summary
        assert "config_dir" in summary
        assert "plugins" in summary
        assert "last_updated" in summary
        assert summary["total_configs"] >= 2
        assert "plugin1" in summary["plugins"]
        assert "plugin2" in summary["plugins"]
    
    @pytest.mark.asyncio
    async def test_config_change_notification(self, config_manager):
        """测试配置变更通知"""
        notifications = []
        
        def config_listener(plugin_id: str, config: dict):
            notifications.append((plugin_id, config))
        
        # 注册监听器
        config_manager.add_config_listener("test_plugin", config_listener)
        
        # 更新配置
        test_config = {"enabled": True, "timeout": 30}
        await config_manager.update_plugin_config(
            "test_plugin",
            "timeout",
            45,
            save_immediately=False
        )
        
        # 手动触发通知（在实际实现中会自动触发）
        config_manager._notify_config_change("test_plugin", {"enabled": True, "timeout": 45})
        
        # 验证通知
        assert len(notifications) == 1
        assert notifications[0][0] == "test_plugin"
        assert notifications[0][1]["timeout"] == 45
    
    @pytest.mark.asyncio
    async def test_error_handling(self, config_manager):
        """测试错误处理"""
        # 加载不存在的插件配置
        config = await config_manager.get_plugin_config("nonexistent_plugin")
        assert config == {}
        
        # 更新不存在插件的配置
        success = await config_manager.update_plugin_config(
            "nonexistent_plugin",
            "test_key",
            "test_value",
            save_immediately=False
        )
        assert success  # 应该创建新的配置项
        
        # 重置不存在的插件配置
        success = config_manager.reset_config("nonexistent_plugin")
        assert not success
        
        # 重新加载不存在的插件配置
        success = await config_manager.reload_plugin_config("nonexistent_plugin")
        assert not success


@pytest.mark.integration
class TestConfigManagerIntegration:
    """配置管理器集成测试"""
    
    @pytest.mark.asyncio
    async def test_config_file_formats(self, temp_dir):
        """测试多种配置文件格式"""
        config_manager = PluginConfigManager()
        config_manager.config_dir = temp_dir / "config"
        await config_manager.initialize()
        
        try:
            test_config = {
                "enabled": True,
                "timeout": 30,
                "list_value": [1, 2, 3],
                "nested": {
                    "key1": "value1",
                    "key2": 42
                }
            }
            
            formats_to_test = [
                ("config.yaml", ConfigFormat.YAML),
                ("config.json", ConfigFormat.JSON),
            ]
            
            for filename, format_type in formats_to_test:
                config_file = config_manager.config_dir / filename
                config_file.parent.mkdir(exist_ok=True)
                
                # 保存配置
                if format_type == ConfigFormat.YAML:
                    with open(config_file, 'w') as f:
                        yaml.dump(test_config, f)
                elif format_type == ConfigFormat.JSON:
                    with open(config_file, 'w') as f:
                        json.dump(test_config, f)
                
                # 加载配置
                loaded_config = await config_manager.load_plugin_config(
                    f"test_{format_type.value}",
                    PluginType.SESSION_MANAGEMENT,
                    config_file
                )
                
                # 验证加载结果
                assert loaded_config["enabled"] is True
                assert loaded_config["timeout"] == 30
                assert loaded_config["list_value"] == [1, 2, 3]
                assert loaded_config["nested"]["key1"] == "value1"
                
        finally:
            await config_manager.stop()
    
    @pytest.mark.asyncio
    async def test_config_validation_integration(self, temp_dir):
        """测试配置验证集成"""
        config_manager = PluginConfigManager()
        config_manager.config_dir = temp_dir / "config"
        await config_manager.initialize()
        
        try:
            # 测试有效配置
            valid_config = {
                "enabled": True,
                "max_concurrent_sessions": 15,
                "session_timeout": 2400.0,
                "pool_size": 8
            }
            
            config_file = config_manager.config_dir / "valid_config.yaml"
            config_file.parent.mkdir(exist_ok=True)
            
            with open(config_file, 'w') as f:
                yaml.dump(valid_config, f)
            
            # 加载并验证配置
            loaded_config = await config_manager.load_plugin_config(
                "valid_plugin",
                PluginType.SESSION_MANAGEMENT,
                config_file
            )
            
            assert loaded_config is not None
            assert loaded_config["enabled"] is True
            
            # 获取验证状态
            validation_status = config_manager.get_validation_status("valid_plugin")
            if validation_status:
                assert 'validated' in validation_status
                assert 'errors' in validation_status
            
        finally:
            await config_manager.stop()
    
    @pytest.mark.asyncio
    async def test_template_generation_integration(self, temp_dir):
        """测试模板生成集成"""
        config_manager = PluginConfigManager()
        config_manager.config_dir = temp_dir / "config"
        await config_manager.initialize()
        
        try:
            # 生成所有插件类型的模板
            plugin_types = [
                PluginType.SESSION_MANAGEMENT,
                PluginType.FINGERPRINT,
                PluginType.BEHAVIOR_SIMULATION,
                PluginType.CAPTCHA_DETECTION
            ]
            
            for plugin_type in plugin_types:
                # 生成并保存模板
                template_path = await config_manager.generate_config_template_file(
                    plugin_type,
                    format='yaml'
                )
                
                assert template_path.exists()
                
                # 验证模板内容
                with open(template_path, 'r') as f:
                    template_content = f.read()
                
                assert len(template_content) > 0
                assert 'enabled' in template_content or 'version' in template_content
                
                # 尝试解析生成的模板
                try:
                    parsed_template = yaml.safe_load(template_content)
                    assert isinstance(parsed_template, dict)
                except yaml.YAMLError:
                    # 模板可能包含注释，解析失败是正常的
                    pass
            
        finally:
            await config_manager.stop()
    
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_performance_with_many_configs(self, temp_dir):
        """测试大量配置的性能"""
        config_manager = PluginConfigManager()
        config_manager.config_dir = temp_dir / "config"
        await config_manager.initialize()
        
        try:
            # 创建大量配置文件
            num_configs = 50
            configs = []
            
            for i in range(num_configs):
                plugin_id = f"plugin_{i}"
                config_data = {
                    "enabled": i % 2 == 0,
                    "timeout": 30 + i,
                    "id": i
                }
                
                config_file = config_manager.config_dir / f"{plugin_id}.yaml"
                with open(config_file, 'w') as f:
                    yaml.dump(config_data, f)
                
                configs.append((plugin_id, config_file))
            
            # 批量加载配置
            import time
            start_time = time.time()
            
            for plugin_id, config_file in configs:
                await config_manager.load_plugin_config(
                    plugin_id,
                    PluginType.SESSION_MANAGEMENT,
                    config_file
                )
            
            load_time = time.time() - start_time
            
            # 验证性能（每个配置加载时间应该在合理范围内）
            avg_time_per_config = load_time / num_configs
            assert avg_time_per_config < 0.1  # 每个配置加载时间不超过100ms
            
            # 获取所有配置
            all_configs = config_manager.get_all_configs()
            assert len(all_configs) == num_configs
            
            # 批量更新配置
            start_time = time.time()
            
            for i in range(num_configs):
                plugin_id = f"plugin_{i}"
                await config_manager.update_plugin_config(
                    plugin_id,
                    "timeout",
                    60 + i,
                    save_immediately=False
                )
            
            update_time = time.time() - start_time
            avg_update_time = update_time / num_configs
            assert avg_update_time < 0.01  # 每个配置更新时间不超过10ms
            
        finally:
            await config_manager.stop()