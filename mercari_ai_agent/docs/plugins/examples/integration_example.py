"""
插件集成示例

该示例展示了如何将现有的反检测组件集成到插件框架中，包括：
1. 会话管理插件集成
2. 指纹管理插件集成
3. 行为模拟插件集成
4. 插件间通信
5. 配置共享
6. 统一生命周期管理

Author: Mercari AI Agent Team
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass
from abc import ABC, abstractmethod

from mercari_agent.plugins.interfaces import (
    IPlugin, ISessionManagementPlugin, IFingerprintManagementPlugin, 
    IBehaviorSimulationPlugin, PluginType, PluginState, PluginCapability, 
    PluginMetadata
)
from mercari_agent.plugins.framework import PluginFramework


# 模拟现有的反检测组件
class LegacySessionManager:
    """模拟现有的会话管理组件"""
    
    def __init__(self):
        self.sessions = {}
        self.active = False
    
    def create_session(self, session_id: str, config: Dict[str, Any]) -> bool:
        """创建会话"""
        if session_id in self.sessions:
            return False
        
        self.sessions[session_id] = {
            "id": session_id,
            "created_at": datetime.now(),
            "config": config.copy(),
            "active": True,
            "requests": 0
        }
        return True
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话"""
        return self.sessions.get(session_id)
    
    def update_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """更新会话"""
        if session_id not in self.sessions:
            return False
        
        self.sessions[session_id].update(data)
        return True
    
    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """列出所有会话"""
        return list(self.sessions.values())
    
    def cleanup_expired_sessions(self, max_age_seconds: int = 3600):
        """清理过期会话"""
        now = datetime.now()
        expired_sessions = []
        
        for session_id, session in self.sessions.items():
            age = (now - session["created_at"]).total_seconds()
            if age > max_age_seconds:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
        
        return len(expired_sessions)


class LegacyFingerprintManager:
    """模拟现有的指纹管理组件"""
    
    def __init__(self):
        self.fingerprints = {}
        self.active = False
    
    def generate_fingerprint(self, user_agent: str, platform: str) -> str:
        """生成指纹"""
        fingerprint_id = f"fp_{hash(user_agent + platform)}"
        self.fingerprints[fingerprint_id] = {
            "id": fingerprint_id,
            "user_agent": user_agent,
            "platform": platform,
            "created_at": datetime.now(),
            "used_count": 0
        }
        return fingerprint_id
    
    def get_fingerprint(self, fingerprint_id: str) -> Optional[Dict[str, Any]]:
        """获取指纹"""
        return self.fingerprints.get(fingerprint_id)
    
    def update_fingerprint(self, fingerprint_id: str, data: Dict[str, Any]) -> bool:
        """更新指纹"""
        if fingerprint_id not in self.fingerprints:
            return False
        
        self.fingerprints[fingerprint_id].update(data)
        return True
    
    def delete_fingerprint(self, fingerprint_id: str) -> bool:
        """删除指纹"""
        if fingerprint_id in self.fingerprints:
            del self.fingerprints[fingerprint_id]
            return True
        return False
    
    def list_fingerprints(self) -> List[Dict[str, Any]]:
        """列出所有指纹"""
        return list(self.fingerprints.values())
    
    def rotate_fingerprints(self, max_usage: int = 100):
        """轮换指纹"""
        rotated_count = 0
        for fingerprint_id, fingerprint in list(self.fingerprints.items()):
            if fingerprint["used_count"] >= max_usage:
                del self.fingerprints[fingerprint_id]
                rotated_count += 1
        return rotated_count


class LegacyBehaviorSimulator:
    """模拟现有的行为模拟组件"""
    
    def __init__(self):
        self.behaviors = {}
        self.active = False
    
    def simulate_human_behavior(self, behavior_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """模拟人类行为"""
        behavior_id = f"bhv_{int(time.time() * 1000)}"
        
        # 模拟不同类型的行为
        if behavior_type == "mouse_movement":
            result = {
                "type": "mouse_movement",
                "path": [(0, 0), (100, 50), (200, 100)],
                "duration": params.get("duration", 1.0),
                "smoothness": params.get("smoothness", 0.8)
            }
        elif behavior_type == "typing":
            result = {
                "type": "typing",
                "text": params.get("text", ""),
                "speed": params.get("speed", 0.1),
                "mistakes": params.get("mistakes", 0)
            }
        elif behavior_type == "page_scroll":
            result = {
                "type": "page_scroll",
                "direction": params.get("direction", "down"),
                "distance": params.get("distance", 500),
                "speed": params.get("speed", 0.5)
            }
        else:
            result = {"type": "unknown", "error": f"Unknown behavior type: {behavior_type}"}
        
        self.behaviors[behavior_id] = {
            "id": behavior_id,
            "type": behavior_type,
            "params": params.copy(),
            "result": result,
            "created_at": datetime.now()
        }
        
        return result
    
    def get_behavior_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取行为历史"""
        behaviors = list(self.behaviors.values())
        behaviors.sort(key=lambda x: x["created_at"], reverse=True)
        return behaviors[:limit]
    
    def clear_behavior_history(self):
        """清理行为历史"""
        self.behaviors.clear()


# 插件化适配器
class SessionManagementPluginAdapter(ISessionManagementPlugin):
    """会话管理插件适配器"""
    
    def __init__(self, legacy_manager: Optional[LegacySessionManager] = None):
        # 基础属性
        self.plugin_id = "session_management_adapter"
        self.plugin_type = PluginType.SESSION_MANAGEMENT
        self.state = PluginState.INACTIVE
        self.config = {}
        
        # 插件元数据
        self.metadata = PluginMetadata(
            plugin_id=self.plugin_id,
            name="会话管理适配器",
            version="1.0.0",
            description="将现有会话管理组件适配为插件",
            author="Mercari AI Agent Team",
            plugin_type=self.plugin_type,
            capabilities=[
                PluginCapability.CONFIGURABLE,
                PluginCapability.MONITORABLE,
                PluginCapability.HOT_RELOADABLE
            ]
        )
        
        # 适配的组件
        self.session_manager = legacy_manager or LegacySessionManager()
        
        # 日志
        self.logger = logging.getLogger(f"plugin.{self.plugin_id}")
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """初始化插件"""
        try:
            self.logger.info("初始化会话管理插件适配器")
            
            if config:
                self.config.update(config)
            
            # 设置默认配置
            if "session_timeout" not in self.config:
                self.config["session_timeout"] = 3600  # 1小时
            if "max_sessions" not in self.config:
                self.config["max_sessions"] = 1000
            if "cleanup_interval" not in self.config:
                self.config["cleanup_interval"] = 300  # 5分钟
            
            self.state = PluginState.READY
            return True
            
        except Exception as e:
            self.logger.error(f"初始化失败: {e}")
            self.state = PluginState.INACTIVE
            return False
    
    async def start(self) -> bool:
        """启动插件"""
        try:
            self.logger.info("启动会话管理插件适配器")
            self.session_manager.active = True
            self.state = PluginState.ACTIVE
            return True
        except Exception as e:
            self.logger.error(f"启动失败: {e}")
            return False
    
    async def stop(self) -> bool:
        """停止插件"""
        try:
            self.logger.info("停止会话管理插件适配器")
            self.session_manager.active = False
            self.state = PluginState.INACTIVE
            return True
        except Exception as e:
            self.logger.error(f"停止失败: {e}")
            return False
    
    async def cleanup(self) -> bool:
        """清理插件"""
        try:
            self.logger.info("清理会话管理插件适配器")
            self.session_manager.sessions.clear()
            self.state = PluginState.UNLOADED
            return True
        except Exception as e:
            self.logger.error(f"清理失败: {e}")
            return False
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            # 检查会话数量
            session_count = len(self.session_manager.sessions)
            max_sessions = self.config.get("max_sessions", 1000)
            
            if session_count > max_sessions:
                self.logger.warning(f"会话数量过多: {session_count}/{max_sessions}")
                return False
            
            return self.state == PluginState.ACTIVE
        except Exception as e:
            self.logger.error(f"健康检查失败: {e}")
            return False
    
    async def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "plugin_id": self.plugin_id,
            "state": self.state.value,
            "session_count": len(self.session_manager.sessions),
            "active_sessions": len([s for s in self.session_manager.sessions.values() if s.get("active", False)]),
            "config": self.config.copy()
        }
    
    # 会话管理接口实现
    async def create_session(self, session_id: str, config: Dict[str, Any]) -> bool:
        """创建会话"""
        return self.session_manager.create_session(session_id, config)
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话"""
        return self.session_manager.get_session(session_id)
    
    async def update_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """更新会话"""
        return self.session_manager.update_session(session_id, data)
    
    async def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        return self.session_manager.delete_session(session_id)
    
    async def list_sessions(self) -> List[Dict[str, Any]]:
        """列出所有会话"""
        return self.session_manager.list_sessions()
    
    async def cleanup_sessions(self) -> int:
        """清理过期会话"""
        timeout = self.config.get("session_timeout", 3600)
        return self.session_manager.cleanup_expired_sessions(timeout)


class FingerprintManagementPluginAdapter(IFingerprintManagementPlugin):
    """指纹管理插件适配器"""
    
    def __init__(self, legacy_manager: Optional[LegacyFingerprintManager] = None):
        # 基础属性
        self.plugin_id = "fingerprint_management_adapter"
        self.plugin_type = PluginType.FINGERPRINT_MANAGEMENT
        self.state = PluginState.INACTIVE
        self.config = {}
        
        # 插件元数据
        self.metadata = PluginMetadata(
            plugin_id=self.plugin_id,
            name="指纹管理适配器",
            version="1.0.0",
            description="将现有指纹管理组件适配为插件",
            author="Mercari AI Agent Team",
            plugin_type=self.plugin_type,
            capabilities=[
                PluginCapability.CONFIGURABLE,
                PluginCapability.MONITORABLE,
                PluginCapability.HOT_RELOADABLE
            ]
        )
        
        # 适配的组件
        self.fingerprint_manager = legacy_manager or LegacyFingerprintManager()
        
        # 日志
        self.logger = logging.getLogger(f"plugin.{self.plugin_id}")
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """初始化插件"""
        try:
            self.logger.info("初始化指纹管理插件适配器")
            
            if config:
                self.config.update(config)
            
            # 设置默认配置
            if "max_fingerprints" not in self.config:
                self.config["max_fingerprints"] = 500
            if "rotation_threshold" not in self.config:
                self.config["rotation_threshold"] = 100
            if "rotation_interval" not in self.config:
                self.config["rotation_interval"] = 3600  # 1小时
            
            self.state = PluginState.READY
            return True
            
        except Exception as e:
            self.logger.error(f"初始化失败: {e}")
            self.state = PluginState.INACTIVE
            return False
    
    async def start(self) -> bool:
        """启动插件"""
        try:
            self.logger.info("启动指纹管理插件适配器")
            self.fingerprint_manager.active = True
            self.state = PluginState.ACTIVE
            return True
        except Exception as e:
            self.logger.error(f"启动失败: {e}")
            return False
    
    async def stop(self) -> bool:
        """停止插件"""
        try:
            self.logger.info("停止指纹管理插件适配器")
            self.fingerprint_manager.active = False
            self.state = PluginState.INACTIVE
            return True
        except Exception as e:
            self.logger.error(f"停止失败: {e}")
            return False
    
    async def cleanup(self) -> bool:
        """清理插件"""
        try:
            self.logger.info("清理指纹管理插件适配器")
            self.fingerprint_manager.fingerprints.clear()
            self.state = PluginState.UNLOADED
            return True
        except Exception as e:
            self.logger.error(f"清理失败: {e}")
            return False
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            # 检查指纹数量
            fingerprint_count = len(self.fingerprint_manager.fingerprints)
            max_fingerprints = self.config.get("max_fingerprints", 500)
            
            if fingerprint_count > max_fingerprints:
                self.logger.warning(f"指纹数量过多: {fingerprint_count}/{max_fingerprints}")
                return False
            
            return self.state == PluginState.ACTIVE
        except Exception as e:
            self.logger.error(f"健康检查失败: {e}")
            return False
    
    async def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        fingerprints = self.fingerprint_manager.fingerprints
        return {
            "plugin_id": self.plugin_id,
            "state": self.state.value,
            "fingerprint_count": len(fingerprints),
            "avg_usage": sum(fp.get("used_count", 0) for fp in fingerprints.values()) / max(len(fingerprints), 1),
            "config": self.config.copy()
        }
    
    # 指纹管理接口实现
    async def generate_fingerprint(self, user_agent: str, platform: str) -> str:
        """生成指纹"""
        return self.fingerprint_manager.generate_fingerprint(user_agent, platform)
    
    async def get_fingerprint(self, fingerprint_id: str) -> Optional[Dict[str, Any]]:
        """获取指纹"""
        return self.fingerprint_manager.get_fingerprint(fingerprint_id)
    
    async def update_fingerprint(self, fingerprint_id: str, data: Dict[str, Any]) -> bool:
        """更新指纹"""
        return self.fingerprint_manager.update_fingerprint(fingerprint_id, data)
    
    async def delete_fingerprint(self, fingerprint_id: str) -> bool:
        """删除指纹"""
        return self.fingerprint_manager.delete_fingerprint(fingerprint_id)
    
    async def list_fingerprints(self) -> List[Dict[str, Any]]:
        """列出所有指纹"""
        return self.fingerprint_manager.list_fingerprints()
    
    async def rotate_fingerprints(self) -> int:
        """轮换指纹"""
        threshold = self.config.get("rotation_threshold", 100)
        return self.fingerprint_manager.rotate_fingerprints(threshold)


class BehaviorSimulationPluginAdapter(IBehaviorSimulationPlugin):
    """行为模拟插件适配器"""
    
    def __init__(self, legacy_simulator: Optional[LegacyBehaviorSimulator] = None):
        # 基础属性
        self.plugin_id = "behavior_simulation_adapter"
        self.plugin_type = PluginType.BEHAVIOR_SIMULATION
        self.state = PluginState.INACTIVE
        self.config = {}
        
        # 插件元数据
        self.metadata = PluginMetadata(
            plugin_id=self.plugin_id,
            name="行为模拟适配器",
            version="1.0.0",
            description="将现有行为模拟组件适配为插件",
            author="Mercari AI Agent Team",
            plugin_type=self.plugin_type,
            capabilities=[
                PluginCapability.CONFIGURABLE,
                PluginCapability.MONITORABLE,
                PluginCapability.HOT_RELOADABLE
            ]
        )
        
        # 适配的组件
        self.behavior_simulator = legacy_simulator or LegacyBehaviorSimulator()
        
        # 日志
        self.logger = logging.getLogger(f"plugin.{self.plugin_id}")
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """初始化插件"""
        try:
            self.logger.info("初始化行为模拟插件适配器")
            
            if config:
                self.config.update(config)
            
            # 设置默认配置
            if "max_history" not in self.config:
                self.config["max_history"] = 1000
            if "behavior_randomness" not in self.config:
                self.config["behavior_randomness"] = 0.1
            if "simulation_delay" not in self.config:
                self.config["simulation_delay"] = 0.1
            
            self.state = PluginState.READY
            return True
            
        except Exception as e:
            self.logger.error(f"初始化失败: {e}")
            self.state = PluginState.INACTIVE
            return False
    
    async def start(self) -> bool:
        """启动插件"""
        try:
            self.logger.info("启动行为模拟插件适配器")
            self.behavior_simulator.active = True
            self.state = PluginState.ACTIVE
            return True
        except Exception as e:
            self.logger.error(f"启动失败: {e}")
            return False
    
    async def stop(self) -> bool:
        """停止插件"""
        try:
            self.logger.info("停止行为模拟插件适配器")
            self.behavior_simulator.active = False
            self.state = PluginState.INACTIVE
            return True
        except Exception as e:
            self.logger.error(f"停止失败: {e}")
            return False
    
    async def cleanup(self) -> bool:
        """清理插件"""
        try:
            self.logger.info("清理行为模拟插件适配器")
            self.behavior_simulator.clear_behavior_history()
            self.state = PluginState.UNLOADED
            return True
        except Exception as e:
            self.logger.error(f"清理失败: {e}")
            return False
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            # 检查行为历史大小
            history_size = len(self.behavior_simulator.behaviors)
            max_history = self.config.get("max_history", 1000)
            
            if history_size > max_history:
                self.logger.warning(f"行为历史过多: {history_size}/{max_history}")
                return False
            
            return self.state == PluginState.ACTIVE
        except Exception as e:
            self.logger.error(f"健康检查失败: {e}")
            return False
    
    async def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "plugin_id": self.plugin_id,
            "state": self.state.value,
            "behavior_history_size": len(self.behavior_simulator.behaviors),
            "config": self.config.copy()
        }
    
    # 行为模拟接口实现
    async def simulate_mouse_movement(self, start_pos: tuple, end_pos: tuple, duration: float) -> Dict[str, Any]:
        """模拟鼠标移动"""
        params = {
            "start_pos": start_pos,
            "end_pos": end_pos,
            "duration": duration
        }
        return self.behavior_simulator.simulate_human_behavior("mouse_movement", params)
    
    async def simulate_typing(self, text: str, speed: float) -> Dict[str, Any]:
        """模拟打字"""
        params = {
            "text": text,
            "speed": speed
        }
        return self.behavior_simulator.simulate_human_behavior("typing", params)
    
    async def simulate_page_scroll(self, direction: str, distance: int) -> Dict[str, Any]:
        """模拟页面滚动"""
        params = {
            "direction": direction,
            "distance": distance
        }
        return self.behavior_simulator.simulate_human_behavior("page_scroll", params)
    
    async def get_behavior_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取行为历史"""
        return self.behavior_simulator.get_behavior_history(limit)


# 集成演示
class IntegratedAntiDetectionSystem:
    """集成的反检测系统"""
    
    def __init__(self):
        self.plugin_framework = PluginFramework()
        self.logger = logging.getLogger("integrated_system")
        
        # 插件适配器
        self.session_plugin = SessionManagementPluginAdapter()
        self.fingerprint_plugin = FingerprintManagementPluginAdapter()
        self.behavior_plugin = BehaviorSimulationPluginAdapter()
    
    async def initialize(self):
        """初始化系统"""
        try:
            self.logger.info("初始化集成反检测系统")
            
            # 注册插件
            await self.plugin_framework.register_plugin(self.session_plugin)
            await self.plugin_framework.register_plugin(self.fingerprint_plugin)
            await self.plugin_framework.register_plugin(self.behavior_plugin)
            
            # 配置插件
            session_config = {
                "session_timeout": 3600,
                "max_sessions": 500,
                "cleanup_interval": 300
            }
            
            fingerprint_config = {
                "max_fingerprints": 200,
                "rotation_threshold": 50,
                "rotation_interval": 1800
            }
            
            behavior_config = {
                "max_history": 500,
                "behavior_randomness": 0.2,
                "simulation_delay": 0.05
            }
            
            # 初始化插件
            await self.plugin_framework.initialize_plugin(self.session_plugin.plugin_id, session_config)
            await self.plugin_framework.initialize_plugin(self.fingerprint_plugin.plugin_id, fingerprint_config)
            await self.plugin_framework.initialize_plugin(self.behavior_plugin.plugin_id, behavior_config)
            
            # 启动插件
            await self.plugin_framework.start_plugin(self.session_plugin.plugin_id)
            await self.plugin_framework.start_plugin(self.fingerprint_plugin.plugin_id)
            await self.plugin_framework.start_plugin(self.behavior_plugin.plugin_id)
            
            self.logger.info("集成反检测系统初始化完成")
            return True
            
        except Exception as e:
            self.logger.error(f"系统初始化失败: {e}")
            return False
    
    async def process_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """处理请求"""
        try:
            # 获取或创建会话
            session_id = request_data.get("session_id", f"session_{int(time.time())}")
            session = await self.session_plugin.get_session(session_id)
            
            if not session:
                session_config = {
                    "user_agent": request_data.get("user_agent", "Mozilla/5.0..."),
                    "platform": request_data.get("platform", "Windows")
                }
                await self.session_plugin.create_session(session_id, session_config)
                session = await self.session_plugin.get_session(session_id)
            
            # 生成或获取指纹
            fingerprint_id = await self.fingerprint_plugin.generate_fingerprint(
                session["config"]["user_agent"],
                session["config"]["platform"]
            )
            
            # 模拟人类行为
            behavior_result = await self.behavior_plugin.simulate_mouse_movement(
                (0, 0), (100, 100), 1.0
            )
            
            # 更新会话
            await self.session_plugin.update_session(session_id, {
                "last_request": datetime.now(),
                "requests": session.get("requests", 0) + 1,
                "current_fingerprint": fingerprint_id
            })
            
            # 返回处理结果
            return {
                "session_id": session_id,
                "fingerprint_id": fingerprint_id,
                "behavior": behavior_result,
                "status": "success"
            }
            
        except Exception as e:
            self.logger.error(f"请求处理失败: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        try:
            plugins_status = await self.plugin_framework.get_plugins_status()
            
            return {
                "system": "integrated_anti_detection",
                "plugins": plugins_status,
                "active_plugins": len([p for p in plugins_status.values() if p.get("state") == "active"]),
                "total_plugins": len(plugins_status),
                "healthy": all(p.get("healthy", False) for p in plugins_status.values())
            }
            
        except Exception as e:
            self.logger.error(f"获取系统状态失败: {e}")
            return {
                "system": "integrated_anti_detection",
                "status": "error",
                "error": str(e)
            }
    
    async def cleanup(self):
        """清理系统"""
        try:
            self.logger.info("清理集成反检测系统")
            
            # 停止所有插件
            await self.plugin_framework.stop_plugin(self.session_plugin.plugin_id)
            await self.plugin_framework.stop_plugin(self.fingerprint_plugin.plugin_id)
            await self.plugin_framework.stop_plugin(self.behavior_plugin.plugin_id)
            
            # 清理插件
            await self.plugin_framework.cleanup_plugin(self.session_plugin.plugin_id)
            await self.plugin_framework.cleanup_plugin(self.fingerprint_plugin.plugin_id)
            await self.plugin_framework.cleanup_plugin(self.behavior_plugin.plugin_id)
            
            self.logger.info("集成反检测系统清理完成")
            
        except Exception as e:
            self.logger.error(f"系统清理失败: {e}")


# 演示使用
async def demo_integration():
    """演示集成使用"""
    print("=== 插件集成演示 ===")
    
    # 创建集成系统
    system = IntegratedAntiDetectionSystem()
    
    try:
        # 初始化系统
        print("\n1. 初始化集成系统...")
        success = await system.initialize()
        print(f"初始化结果: {success}")
        
        # 获取系统状态
        print("\n2. 获取系统状态...")
        status = await system.get_system_status()
        print(f"系统状态: {status}")
        
        # 处理请求
        print("\n3. 处理请求...")
        request_data = {
            "session_id": "test_session_001",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "platform": "Windows"
        }
        
        result = await system.process_request(request_data)
        print(f"处理结果: {result}")
        
        # 处理更多请求
        print("\n4. 处理更多请求...")
        for i in range(3):
            result = await system.process_request({
                "session_id": f"test_session_{i+2:03d}",
                "user_agent": f"Mozilla/5.0 (Test Browser {i+1})",
                "platform": "Linux"
            })
            print(f"请求 {i+1} 结果: {result['status']}")
        
        # 获取详细状态
        print("\n5. 获取详细状态...")
        status = await system.get_system_status()
        print(f"详细状态: {status}")
        
        # 获取各插件状态
        print("\n6. 获取各插件状态...")
        session_status = await system.session_plugin.get_status()
        fingerprint_status = await system.fingerprint_plugin.get_status()
        behavior_status = await system.behavior_plugin.get_status()
        
        print(f"会话插件状态: {session_status}")
        print(f"指纹插件状态: {fingerprint_status}")
        print(f"行为插件状态: {behavior_status}")
        
        # 清理系统
        print("\n7. 清理系统...")
        await system.cleanup()
        
    except Exception as e:
        print(f"演示过程中发生错误: {e}")
        await system.cleanup()
    
    print("\n=== 插件集成演示完成 ===")


if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 运行演示
    asyncio.run(demo_integration())