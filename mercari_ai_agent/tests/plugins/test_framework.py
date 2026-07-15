"""
插件框架核心功能单元测试

测试内容包括：
1. 插件框架初始化和生命周期
2. 插件注册和发现
3. 插件加载和卸载
4. 插件通信和事件处理
5. 错误处理和异常情况
6. 性能和稳定性测试

Author: Mercari AI Agent Team
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path

from mercari_agent.plugins.framework import PluginFramework
from mercari_agent.plugins.interfaces import (
    IPlugin, PluginType, PluginState, PluginCapability, 
    PluginConfiguration, PluginMetadata
)
from mercari_agent.plugins.registry import PluginRegistry
from mercari_agent.plugins.loader import PluginLoader
from mercari_agent.plugins.lifecycle import PluginLifecycleManager
from mercari_agent.plugins.config_manager import PluginConfigManager
from mercari_agent.plugins.version_control import PluginVersionManager


class TestPluginFramework:
    """插件框架测试"""
    
    @pytest.fixture
    async def framework(self):
        """插件框架实例"""
        framework = PluginFramework()
        await framework.initialize()
        yield framework
        await framework.shutdown()
    
    @pytest.mark.asyncio
    async def test_framework_singleton(self):
        """测试框架单例模式"""
        framework1 = PluginFramework.get_instance()
        framework2 = PluginFramework.get_instance()
        
        # 应该是同一个实例
        assert framework1 is framework2
    
    @pytest.mark.asyncio
    async def test_framework_initialization(self):
        """测试框架初始化"""
        framework = PluginFramework()
        
        # 初始化前状态
        assert not framework.is_initialized
        
        # 初始化
        success = await framework.initialize()
        assert success
        assert framework.is_initialized
        
        # 验证组件初始化
        assert framework.registry is not None
        assert framework.loader is not None
        assert framework.lifecycle_manager is not None
        assert framework.config_manager is not None
        assert framework.version_manager is not None
        
        # 清理
        await framework.shutdown()
    
    @pytest.mark.asyncio
    async def test_framework_shutdown(self, framework):
        """测试框架关闭"""
        assert framework.is_initialized
        
        # 关闭框架
        await framework.shutdown()
        assert not framework.is_initialized
    
    @pytest.mark.asyncio
    async def test_plugin_registration(self, framework, mock_plugin):
        """测试插件注册"""
        # 注册插件
        success = await framework.register_plugin(mock_plugin)
        assert success
        
        # 验证注册结果
        assert mock_plugin.plugin_id in framework.registry.plugins
        
        # 获取插件
        retrieved_plugin = await framework.get_plugin(mock_plugin.plugin_id)
        assert retrieved_plugin is mock_plugin
    
    @pytest.mark.asyncio
    async def test_plugin_duplicate_registration(self, framework, mock_plugin):
        """测试重复注册插件"""
        # 首次注册
        success1 = await framework.register_plugin(mock_plugin)
        assert success1
        
        # 重复注册
        success2 = await framework.register_plugin(mock_plugin)
        assert not success2  # 应该失败
    
    @pytest.mark.asyncio
    async def test_plugin_unregistration(self, framework, mock_plugin):
        """测试插件注销"""
        # 注册插件
        await framework.register_plugin(mock_plugin)
        
        # 注销插件
        success = await framework.unregister_plugin(mock_plugin.plugin_id)
        assert success
        
        # 验证注销结果
        assert mock_plugin.plugin_id not in framework.registry.plugins
        
        # 获取插件应该失败
        retrieved_plugin = await framework.get_plugin(mock_plugin.plugin_id)
        assert retrieved_plugin is None
    
    @pytest.mark.asyncio
    async def test_plugin_loading(self, framework, mock_plugin):
        """测试插件加载"""
        # 注册插件
        await framework.register_plugin(mock_plugin)
        
        # 加载插件
        success = await framework.load_plugin(mock_plugin.plugin_id)
        assert success
        
        # 验证加载结果
        assert mock_plugin.initialize_called
        assert mock_plugin.state == PluginState.READY
    
    @pytest.mark.asyncio
    async def test_plugin_starting(self, framework, mock_plugin):
        """测试插件启动"""
        # 注册和加载插件
        await framework.register_plugin(mock_plugin)
        await framework.load_plugin(mock_plugin.plugin_id)
        
        # 启动插件
        success = await framework.start_plugin(mock_plugin.plugin_id)
        assert success
        
        # 验证启动结果
        assert mock_plugin.start_called
        assert mock_plugin.state == PluginState.ACTIVE
    
    @pytest.mark.asyncio
    async def test_plugin_stopping(self, framework, mock_plugin):
        """测试插件停止"""
        # 注册、加载和启动插件
        await framework.register_plugin(mock_plugin)
        await framework.load_plugin(mock_plugin.plugin_id)
        await framework.start_plugin(mock_plugin.plugin_id)
        
        # 停止插件
        success = await framework.stop_plugin(mock_plugin.plugin_id)
        assert success
        
        # 验证停止结果
        assert mock_plugin.stop_called
        assert mock_plugin.state == PluginState.INACTIVE
    
    @pytest.mark.asyncio
    async def test_plugin_unloading(self, framework, mock_plugin):
        """测试插件卸载"""
        # 注册、加载和启动插件
        await framework.register_plugin(mock_plugin)
        await framework.load_plugin(mock_plugin.plugin_id)
        await framework.start_plugin(mock_plugin.plugin_id)
        
        # 卸载插件
        success = await framework.unload_plugin(mock_plugin.plugin_id)
        assert success
        
        # 验证卸载结果
        assert mock_plugin.stop_called
        assert mock_plugin.cleanup_called
        assert mock_plugin.state == PluginState.UNLOADED
    
    @pytest.mark.asyncio
    async def test_plugin_lifecycle_workflow(self, framework, mock_plugin):
        """测试完整的插件生命周期工作流"""
        # 1. 注册
        success = await framework.register_plugin(mock_plugin)
        assert success
        assert mock_plugin.state == PluginState.INACTIVE
        
        # 2. 加载
        success = await framework.load_plugin(mock_plugin.plugin_id)
        assert success
        assert mock_plugin.state == PluginState.READY
        assert mock_plugin.initialize_called
        
        # 3. 启动
        success = await framework.start_plugin(mock_plugin.plugin_id)
        assert success
        assert mock_plugin.state == PluginState.ACTIVE
        assert mock_plugin.start_called
        
        # 4. 停止
        success = await framework.stop_plugin(mock_plugin.plugin_id)
        assert success
        assert mock_plugin.state == PluginState.INACTIVE
        assert mock_plugin.stop_called
        
        # 5. 卸载
        success = await framework.unload_plugin(mock_plugin.plugin_id)
        assert success
        assert mock_plugin.state == PluginState.UNLOADED
        assert mock_plugin.cleanup_called
    
    @pytest.mark.asyncio
    async def test_get_all_plugins(self, framework, mock_plugin_factory):
        """测试获取所有插件"""
        # 注册多个插件
        plugins = mock_plugin_factory(3)
        for plugin in plugins:
            await framework.register_plugin(plugin)
        
        # 获取所有插件
        all_plugins = await framework.get_all_plugins()
        assert len(all_plugins) == 3
        
        # 验证插件ID
        plugin_ids = [p.plugin_id for p in all_plugins]
        for plugin in plugins:
            assert plugin.plugin_id in plugin_ids
    
    @pytest.mark.asyncio
    async def test_get_plugins_by_type(self, framework, mock_plugin_factory):
        """测试按类型获取插件"""
        # 创建不同类型的插件
        session_plugin = mock_plugin_factory(1, plugin_type=PluginType.SESSION_MANAGEMENT)
        fingerprint_plugin = mock_plugin_factory(1, plugin_type=PluginType.FINGERPRINT)
        behavior_plugin = mock_plugin_factory(1, plugin_type=PluginType.BEHAVIOR_SIMULATION)
        
        # 注册插件
        await framework.register_plugin(session_plugin)
        await framework.register_plugin(fingerprint_plugin)
        await framework.register_plugin(behavior_plugin)
        
        # 按类型获取插件
        session_plugins = await framework.get_plugins_by_type(PluginType.SESSION_MANAGEMENT)
        assert len(session_plugins) == 1
        assert session_plugins[0].plugin_type == PluginType.SESSION_MANAGEMENT
        
        fingerprint_plugins = await framework.get_plugins_by_type(PluginType.FINGERPRINT)
        assert len(fingerprint_plugins) == 1
        assert fingerprint_plugins[0].plugin_type == PluginType.FINGERPRINT
    
    @pytest.mark.asyncio
    async def test_get_plugins_by_state(self, framework, mock_plugin_factory):
        """测试按状态获取插件"""
        # 创建多个插件
        plugins = mock_plugin_factory(3)
        
        # 注册插件
        for plugin in plugins:
            await framework.register_plugin(plugin)
        
        # 加载第一个插件
        await framework.load_plugin(plugins[0].plugin_id)
        
        # 启动第二个插件
        await framework.load_plugin(plugins[1].plugin_id)
        await framework.start_plugin(plugins[1].plugin_id)
        
        # 按状态获取插件
        inactive_plugins = await framework.get_plugins_by_state(PluginState.INACTIVE)
        ready_plugins = await framework.get_plugins_by_state(PluginState.READY)
        active_plugins = await framework.get_plugins_by_state(PluginState.ACTIVE)
        
        assert len(inactive_plugins) == 1
        assert len(ready_plugins) == 1
        assert len(active_plugins) == 1
    
    @pytest.mark.asyncio
    async def test_plugin_configuration_reload(self, framework, mock_plugin):
        """测试插件配置重载"""
        # 注册和加载插件
        await framework.register_plugin(mock_plugin)
        await framework.load_plugin(mock_plugin.plugin_id)
        
        # 重载配置
        new_config = {"enabled": False, "timeout": 60}
        success = await framework.reload_plugin_config(mock_plugin.plugin_id, new_config)
        assert success
        
        # 验证配置重载
        assert mock_plugin.config_reloaded
        assert mock_plugin.config["enabled"] is False
        assert mock_plugin.config["timeout"] == 60
    
    @pytest.mark.asyncio
    async def test_plugin_health_check(self, framework, mock_plugin):
        """测试插件健康检查"""
        # 注册和启动插件
        await framework.register_plugin(mock_plugin)
        await framework.load_plugin(mock_plugin.plugin_id)
        await framework.start_plugin(mock_plugin.plugin_id)
        
        # 健康检查
        health_status = await framework.get_plugin_health(mock_plugin.plugin_id)
        assert health_status is not None
        assert health_status.get("healthy") is True
    
    @pytest.mark.asyncio
    async def test_framework_statistics(self, framework, mock_plugin_factory):
        """测试框架统计信息"""
        # 注册多个插件
        plugins = mock_plugin_factory(5)
        for plugin in plugins:
            await framework.register_plugin(plugin)
        
        # 启动部分插件
        await framework.load_plugin(plugins[0].plugin_id)
        await framework.start_plugin(plugins[0].plugin_id)
        
        await framework.load_plugin(plugins[1].plugin_id)
        await framework.start_plugin(plugins[1].plugin_id)
        
        # 获取统计信息
        stats = await framework.get_statistics()
        assert stats["total_plugins"] == 5
        assert stats["active_plugins"] == 2
        assert stats["inactive_plugins"] == 3
        assert "uptime" in stats
    
    @pytest.mark.asyncio
    async def test_error_handling_invalid_plugin(self, framework):
        """测试无效插件的错误处理"""
        # 尝试获取不存在的插件
        plugin = await framework.get_plugin("nonexistent_plugin")
        assert plugin is None
        
        # 尝试加载不存在的插件
        success = await framework.load_plugin("nonexistent_plugin")
        assert not success
        
        # 尝试启动不存在的插件
        success = await framework.start_plugin("nonexistent_plugin")
        assert not success
    
    @pytest.mark.asyncio
    async def test_error_handling_invalid_state_transition(self, framework, mock_plugin):
        """测试无效状态转换的错误处理"""
        # 注册插件
        await framework.register_plugin(mock_plugin)
        
        # 尝试启动未加载的插件
        success = await framework.start_plugin(mock_plugin.plugin_id)
        assert not success
        
        # 尝试停止未启动的插件
        await framework.load_plugin(mock_plugin.plugin_id)
        success = await framework.stop_plugin(mock_plugin.plugin_id)
        assert not success
    
    @pytest.mark.asyncio
    async def test_concurrent_plugin_operations(self, framework, mock_plugin_factory):
        """测试并发插件操作"""
        # 创建多个插件
        plugins = mock_plugin_factory(10)
        
        # 并发注册插件
        register_tasks = [framework.register_plugin(plugin) for plugin in plugins]
        results = await asyncio.gather(*register_tasks, return_exceptions=True)
        
        # 验证结果
        success_count = sum(1 for result in results if result is True)
        assert success_count == 10
        
        # 并发加载插件
        load_tasks = [framework.load_plugin(plugin.plugin_id) for plugin in plugins]
        results = await asyncio.gather(*load_tasks, return_exceptions=True)
        
        # 验证结果
        success_count = sum(1 for result in results if result is True)
        assert success_count == 10
    
    @pytest.mark.asyncio
    async def test_plugin_dependency_resolution(self, framework):
        """测试插件依赖解析"""
        # 创建有依赖关系的插件
        dependency_plugin = Mock(spec=IPlugin)
        dependency_plugin.plugin_id = "dependency_plugin"
        dependency_plugin.plugin_type = PluginType.SESSION_MANAGEMENT
        dependency_plugin.state = PluginState.INACTIVE
        dependency_plugin.initialize = AsyncMock(return_value=True)
        dependency_plugin.start = AsyncMock(return_value=True)
        dependency_plugin.stop = AsyncMock(return_value=True)
        dependency_plugin.cleanup = AsyncMock(return_value=True)
        
        main_plugin = Mock(spec=IPlugin)
        main_plugin.plugin_id = "main_plugin"
        main_plugin.plugin_type = PluginType.FINGERPRINT
        main_plugin.state = PluginState.INACTIVE
        main_plugin.initialize = AsyncMock(return_value=True)
        main_plugin.start = AsyncMock(return_value=True)
        main_plugin.stop = AsyncMock(return_value=True)
        main_plugin.cleanup = AsyncMock(return_value=True)
        
        # 注册插件
        await framework.register_plugin(dependency_plugin)
        await framework.register_plugin(main_plugin)
        
        # 测试依赖解析（这里简化处理，实际实现可能更复杂）
        success = await framework.load_plugin("main_plugin")
        assert success


@pytest.mark.integration
class TestPluginFrameworkIntegration:
    """插件框架集成测试"""
    
    @pytest.mark.asyncio
    async def test_complete_plugin_lifecycle(self, temp_dir):
        """测试完整插件生命周期"""
        # 创建框架实例
        framework = PluginFramework()
        await framework.initialize()
        
        try:
            # 创建测试插件
            plugin = Mock(spec=IPlugin)
            plugin.plugin_id = "integration_test_plugin"
            plugin.plugin_type = PluginType.SESSION_MANAGEMENT
            plugin.state = PluginState.INACTIVE
            plugin.metadata = Mock()
            plugin.metadata.name = "Integration Test Plugin"
            plugin.metadata.version = "1.0.0"
            
            # 设置插件行为
            plugin.initialize = AsyncMock(return_value=True)
            plugin.start = AsyncMock(return_value=True)
            plugin.stop = AsyncMock(return_value=True)
            plugin.cleanup = AsyncMock(return_value=True)
            plugin.health_check = AsyncMock(return_value=True)
            plugin.get_status = AsyncMock(return_value={"healthy": True})
            plugin.reload_config = AsyncMock(return_value=True)
            
            # 1. 注册插件
            success = await framework.register_plugin(plugin)
            assert success
            
            # 2. 加载插件
            success = await framework.load_plugin(plugin.plugin_id)
            assert success
            plugin.initialize.assert_called_once()
            
            # 3. 启动插件
            success = await framework.start_plugin(plugin.plugin_id)
            assert success
            plugin.start.assert_called_once()
            
            # 4. 健康检查
            health = await framework.get_plugin_health(plugin.plugin_id)
            assert health is not None
            
            # 5. 重载配置
            new_config = {"test": "value"}
            success = await framework.reload_plugin_config(plugin.plugin_id, new_config)
            assert success
            plugin.reload_config.assert_called_once_with(new_config)
            
            # 6. 停止插件
            success = await framework.stop_plugin(plugin.plugin_id)
            assert success
            plugin.stop.assert_called_once()
            
            # 7. 卸载插件
            success = await framework.unload_plugin(plugin.plugin_id)
            assert success
            plugin.cleanup.assert_called_once()
            
            # 8. 注销插件
            success = await framework.unregister_plugin(plugin.plugin_id)
            assert success
            
            # 验证插件已完全移除
            retrieved = await framework.get_plugin(plugin.plugin_id)
            assert retrieved is None
            
        finally:
            await framework.shutdown()
    
    @pytest.mark.asyncio
    async def test_multiple_plugins_interaction(self):
        """测试多插件交互"""
        framework = PluginFramework()
        await framework.initialize()
        
        try:
            # 创建多个插件
            plugins = []
            for i in range(3):
                plugin = Mock(spec=IPlugin)
                plugin.plugin_id = f"plugin_{i}"
                plugin.plugin_type = PluginType.SESSION_MANAGEMENT
                plugin.state = PluginState.INACTIVE
                plugin.initialize = AsyncMock(return_value=True)
                plugin.start = AsyncMock(return_value=True)
                plugin.stop = AsyncMock(return_value=True)
                plugin.cleanup = AsyncMock(return_value=True)
                plugin.health_check = AsyncMock(return_value=True)
                plugin.get_status = AsyncMock(return_value={"healthy": True})
                plugins.append(plugin)
            
            # 注册所有插件
            for plugin in plugins:
                await framework.register_plugin(plugin)
            
            # 启动所有插件
            for plugin in plugins:
                await framework.load_plugin(plugin.plugin_id)
                await framework.start_plugin(plugin.plugin_id)
            
            # 验证所有插件都在运行
            active_plugins = await framework.get_plugins_by_state(PluginState.ACTIVE)
            assert len(active_plugins) == 3
            
            # 获取统计信息
            stats = await framework.get_statistics()
            assert stats["total_plugins"] == 3
            assert stats["active_plugins"] == 3
            
            # 停止所有插件
            for plugin in plugins:
                await framework.stop_plugin(plugin.plugin_id)
                await framework.unload_plugin(plugin.plugin_id)
            
        finally:
            await framework.shutdown()
    
    @pytest.mark.asyncio
    async def test_framework_robustness(self):
        """测试框架健壮性"""
        framework = PluginFramework()
        await framework.initialize()
        
        try:
            # 创建一个会失败的插件
            failing_plugin = Mock(spec=IPlugin)
            failing_plugin.plugin_id = "failing_plugin"
            failing_plugin.plugin_type = PluginType.SESSION_MANAGEMENT
            failing_plugin.state = PluginState.INACTIVE
            failing_plugin.initialize = AsyncMock(side_effect=Exception("Initialize failed"))
            failing_plugin.start = AsyncMock(side_effect=Exception("Start failed"))
            failing_plugin.stop = AsyncMock(return_value=True)
            failing_plugin.cleanup = AsyncMock(return_value=True)
            
            # 注册失败的插件
            await framework.register_plugin(failing_plugin)
            
            # 尝试加载失败的插件
            success = await framework.load_plugin("failing_plugin")
            assert not success  # 应该失败
            
            # 框架应该仍然能够正常工作
            stats = await framework.get_statistics()
            assert stats["total_plugins"] == 1
            assert stats["active_plugins"] == 0
            
            # 创建一个正常的插件
            normal_plugin = Mock(spec=IPlugin)
            normal_plugin.plugin_id = "normal_plugin"
            normal_plugin.plugin_type = PluginType.FINGERPRINT
            normal_plugin.state = PluginState.INACTIVE
            normal_plugin.initialize = AsyncMock(return_value=True)
            normal_plugin.start = AsyncMock(return_value=True)
            normal_plugin.stop = AsyncMock(return_value=True)
            normal_plugin.cleanup = AsyncMock(return_value=True)
            
            # 正常插件应该能够正常工作
            await framework.register_plugin(normal_plugin)
            success = await framework.load_plugin("normal_plugin")
            assert success
            
            success = await framework.start_plugin("normal_plugin")
            assert success
            
        finally:
            await framework.shutdown()