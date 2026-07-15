"""
基础插件示例

该示例展示了如何创建一个最基本的插件，包括：
1. 基础插件结构
2. 生命周期方法实现
3. 配置管理
4. 错误处理
5. 状态管理

Author: Mercari AI Agent Team
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from mercari_agent.plugins.interfaces import (
    IPlugin, PluginType, PluginState, PluginCapability, PluginMetadata
)


class BasicExamplePlugin(IPlugin):
    """基础示例插件
    
    这是一个最基本的插件实现，展示了所有必需的方法
    和推荐的编程模式。
    """
    
    def __init__(self):
        """初始化插件基本属性"""
        # 必需属性
        self.plugin_id = "basic_example_plugin"
        self.plugin_type = PluginType.SESSION_MANAGEMENT
        self.state = PluginState.INACTIVE
        self.config = {}
        
        # 插件元数据
        self.metadata = PluginMetadata(
            plugin_id=self.plugin_id,
            name="基础示例插件",
            version="1.0.0",
            description="演示基本插件开发模式的示例插件",
            author="Mercari AI Agent Team",
            homepage="https://example.com/plugins/basic",
            plugin_type=self.plugin_type,
            capabilities=[
                PluginCapability.CONFIGURABLE,
                PluginCapability.MONITORABLE,
                PluginCapability.HOT_RELOADABLE
            ],
            supported_platforms=["windows", "linux", "macos"],
            min_framework_version="1.0.0"
        )
        
        # 内部状态
        self._initialized = False
        self._running = False
        self._last_activity = None
        self._error_count = 0
        
        # 日志记录
        self.logger = logging.getLogger(f"plugin.{self.plugin_id}")
        self.logger.info(f"插件 {self.plugin_id} 创建完成")
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """初始化插件
        
        Args:
            config: 插件配置字典
            
        Returns:
            bool: 初始化是否成功
        """
        try:
            self.logger.info(f"正在初始化插件 {self.plugin_id}")
            
            # 更新配置
            if config:
                self.config.update(config)
                self.logger.info(f"已加载配置: {list(config.keys())}")
            
            # 验证必需的配置项
            required_configs = ['enabled', 'timeout']
            for key in required_configs:
                if key not in self.config:
                    # 设置默认值
                    defaults = {'enabled': True, 'timeout': 30.0}
                    self.config[key] = defaults.get(key)
                    self.logger.warning(f"配置项 {key} 不存在，使用默认值: {defaults.get(key)}")
            
            # 执行初始化逻辑
            await self._perform_initialization()
            
            # 更新状态
            self._initialized = True
            self.state = PluginState.READY
            self.logger.info(f"插件 {self.plugin_id} 初始化成功")
            
            return True
            
        except Exception as e:
            self.logger.error(f"插件初始化失败: {e}", exc_info=True)
            self._error_count += 1
            self.state = PluginState.INACTIVE
            return False
    
    async def start(self) -> bool:
        """启动插件
        
        Returns:
            bool: 启动是否成功
        """
        try:
            if not self._initialized:
                self.logger.error("插件未初始化，无法启动")
                return False
            
            if not self.config.get('enabled', True):
                self.logger.info("插件已禁用，跳过启动")
                return True
            
            self.logger.info(f"正在启动插件 {self.plugin_id}")
            
            # 执行启动逻辑
            await self._perform_startup()
            
            # 更新状态
            self._running = True
            self._last_activity = datetime.now()
            self.state = PluginState.ACTIVE
            self.logger.info(f"插件 {self.plugin_id} 启动成功")
            
            return True
            
        except Exception as e:
            self.logger.error(f"插件启动失败: {e}", exc_info=True)
            self._error_count += 1
            self.state = PluginState.INACTIVE
            return False
    
    async def stop(self) -> bool:
        """停止插件
        
        Returns:
            bool: 停止是否成功
        """
        try:
            if not self._running:
                self.logger.info("插件未运行，无需停止")
                return True
            
            self.logger.info(f"正在停止插件 {self.plugin_id}")
            
            # 执行停止逻辑
            await self._perform_shutdown()
            
            # 更新状态
            self._running = False
            self.state = PluginState.INACTIVE
            self.logger.info(f"插件 {self.plugin_id} 停止成功")
            
            return True
            
        except Exception as e:
            self.logger.error(f"插件停止失败: {e}", exc_info=True)
            self._error_count += 1
            return False
    
    async def cleanup(self) -> bool:
        """清理插件资源
        
        Returns:
            bool: 清理是否成功
        """
        try:
            self.logger.info(f"正在清理插件 {self.plugin_id}")
            
            # 确保插件已停止
            if self._running:
                await self.stop()
            
            # 执行清理逻辑
            await self._perform_cleanup()
            
            # 重置状态
            self._initialized = False
            self._running = False
            self._last_activity = None
            self.state = PluginState.UNLOADED
            self.logger.info(f"插件 {self.plugin_id} 清理完成")
            
            return True
            
        except Exception as e:
            self.logger.error(f"插件清理失败: {e}", exc_info=True)
            self._error_count += 1
            return False
    
    async def health_check(self) -> bool:
        """健康检查
        
        Returns:
            bool: 插件是否健康
        """
        try:
            # 基础状态检查
            if not self._initialized:
                return False
            
            # 检查配置有效性
            if not self.config.get('enabled', True):
                return True  # 禁用状态也是健康的
            
            # 检查运行状态
            if self.state == PluginState.ACTIVE and not self._running:
                return False
            
            # 检查错误计数
            max_errors = self.config.get('max_errors', 10)
            if self._error_count >= max_errors:
                return False
            
            # 检查最后活动时间
            if self._last_activity:
                timeout = self.config.get('timeout', 30.0)
                elapsed = (datetime.now() - self._last_activity).total_seconds()
                if elapsed > timeout * 2:  # 超时的2倍认为不健康
                    self.logger.warning(f"插件长时间无活动: {elapsed}秒")
                    return False
            
            # 执行自定义健康检查
            return await self._perform_health_check()
            
        except Exception as e:
            self.logger.error(f"健康检查异常: {e}", exc_info=True)
            return False
    
    async def get_status(self) -> Dict[str, Any]:
        """获取插件状态信息
        
        Returns:
            Dict[str, Any]: 状态信息字典
        """
        try:
            status = {
                "plugin_id": self.plugin_id,
                "plugin_type": self.plugin_type.value,
                "state": self.state.value,
                "initialized": self._initialized,
                "running": self._running,
                "healthy": await self.health_check(),
                "error_count": self._error_count,
                "last_activity": self._last_activity.isoformat() if self._last_activity else None,
                "config": self.config.copy(),
                "metadata": {
                    "name": self.metadata.name,
                    "version": self.metadata.version,
                    "description": self.metadata.description,
                    "author": self.metadata.author
                }
            }
            
            # 添加自定义状态信息
            custom_status = await self._get_custom_status()
            if custom_status:
                status.update(custom_status)
            
            return status
            
        except Exception as e:
            self.logger.error(f"获取状态失败: {e}", exc_info=True)
            return {
                "plugin_id": self.plugin_id,
                "state": "error",
                "error": str(e)
            }
    
    async def reload_config(self, config: Dict[str, Any]) -> bool:
        """重新加载配置
        
        Args:
            config: 新的配置字典
            
        Returns:
            bool: 重新加载是否成功
        """
        try:
            self.logger.info(f"正在重新加载插件 {self.plugin_id} 的配置")
            
            # 保存旧配置用于回滚
            old_config = self.config.copy()
            
            # 更新配置
            self.config.update(config)
            
            # 验证新配置
            if not await self._validate_config(self.config):
                self.logger.error("新配置验证失败，回滚到旧配置")
                self.config = old_config
                return False
            
            # 应用配置变更
            await self._apply_config_changes(old_config, self.config)
            
            self.logger.info("配置重新加载成功")
            return True
            
        except Exception as e:
            self.logger.error(f"配置重新加载失败: {e}", exc_info=True)
            return False
    
    # 内部辅助方法
    
    async def _perform_initialization(self):
        """执行具体的初始化逻辑"""
        # 在子类中重写此方法实现特定的初始化逻辑
        await asyncio.sleep(0.1)  # 模拟初始化时间
        self.logger.debug("执行基础初始化逻辑")
    
    async def _perform_startup(self):
        """执行具体的启动逻辑"""
        # 在子类中重写此方法实现特定的启动逻辑
        await asyncio.sleep(0.1)  # 模拟启动时间
        self.logger.debug("执行基础启动逻辑")
    
    async def _perform_shutdown(self):
        """执行具体的停止逻辑"""
        # 在子类中重写此方法实现特定的停止逻辑
        await asyncio.sleep(0.1)  # 模拟停止时间
        self.logger.debug("执行基础停止逻辑")
    
    async def _perform_cleanup(self):
        """执行具体的清理逻辑"""
        # 在子类中重写此方法实现特定的清理逻辑
        await asyncio.sleep(0.1)  # 模拟清理时间
        self.logger.debug("执行基础清理逻辑")
    
    async def _perform_health_check(self) -> bool:
        """执行自定义健康检查"""
        # 在子类中重写此方法实现特定的健康检查
        return True
    
    async def _get_custom_status(self) -> Optional[Dict[str, Any]]:
        """获取自定义状态信息"""
        # 在子类中重写此方法添加特定的状态信息
        return None
    
    async def _validate_config(self, config: Dict[str, Any]) -> bool:
        """验证配置有效性"""
        try:
            # 基础验证
            if not isinstance(config, dict):
                return False
            
            # 检查必需配置项
            required_keys = ['enabled', 'timeout']
            for key in required_keys:
                if key not in config:
                    return False
            
            # 类型检查
            if not isinstance(config['enabled'], bool):
                return False
            
            if not isinstance(config['timeout'], (int, float)) or config['timeout'] <= 0:
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"配置验证异常: {e}")
            return False
    
    async def _apply_config_changes(self, old_config: Dict[str, Any], new_config: Dict[str, Any]):
        """应用配置变更"""
        # 比较配置差异并应用相应的变更
        for key, new_value in new_config.items():
            old_value = old_config.get(key)
            if old_value != new_value:
                self.logger.info(f"配置项 {key} 从 {old_value} 变更为 {new_value}")
                # 在子类中重写此方法处理特定配置的变更


# 示例：如何使用这个基础插件
async def demo_basic_plugin():
    """演示基础插件的使用"""
    print("=== 基础插件演示 ===")
    
    # 创建插件实例
    plugin = BasicExamplePlugin()
    print(f"创建插件: {plugin.plugin_id}")
    
    # 配置插件
    config = {
        "enabled": True,
        "timeout": 60.0,
        "max_errors": 5,
        "debug": True
    }
    
    try:
        # 初始化
        print("\n1. 初始化插件...")
        success = await plugin.initialize(config)
        print(f"初始化结果: {success}")
        
        # 获取状态
        status = await plugin.get_status()
        print(f"插件状态: {status['state']}")
        
        # 启动
        print("\n2. 启动插件...")
        success = await plugin.start()
        print(f"启动结果: {success}")
        
        # 健康检查
        print("\n3. 健康检查...")
        healthy = await plugin.health_check()
        print(f"健康状态: {healthy}")
        
        # 获取详细状态
        print("\n4. 获取详细状态...")
        status = await plugin.get_status()
        print(f"详细状态: {status}")
        
        # 重新加载配置
        print("\n5. 重新加载配置...")
        new_config = {"timeout": 120.0, "debug": False}
        success = await plugin.reload_config(new_config)
        print(f"配置重新加载结果: {success}")
        
        # 停止
        print("\n6. 停止插件...")
        success = await plugin.stop()
        print(f"停止结果: {success}")
        
        # 清理
        print("\n7. 清理插件...")
        success = await plugin.cleanup()
        print(f"清理结果: {success}")
        
    except Exception as e:
        print(f"演示过程中发生错误: {e}")
        # 确保清理
        await plugin.cleanup()
    
    print("\n=== 演示完成 ===")


if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 运行演示
    asyncio.run(demo_basic_plugin())