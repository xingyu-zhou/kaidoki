# 插件框架 API 参考

本文档提供了插件框架的完整API参考，包括所有接口、类和方法的详细说明。

## 目录

1. [核心接口](#核心接口)
2. [插件类型和枚举](#插件类型和枚举)
3. [插件框架](#插件框架)
4. [插件注册表](#插件注册表)
5. [插件加载器](#插件加载器)
6. [生命周期管理](#生命周期管理)
7. [配置管理](#配置管理)
8. [模式验证](#模式验证)
9. [版本控制](#版本控制)
10. [错误处理](#错误处理)

## 核心接口

### IPlugin

所有插件必须实现的基础接口。

```python
from mercari_agent.plugins.interfaces import IPlugin

class IPlugin(ABC):
    """插件基础接口"""
    
    # 必需属性
    plugin_id: str
    plugin_type: PluginType
    state: PluginState
    config: Dict[str, Any]
    metadata: PluginMetadata
    
    # 生命周期方法
    @abstractmethod
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """初始化插件"""
        pass
    
    @abstractmethod
    async def start(self) -> bool:
        """启动插件"""
        pass
    
    @abstractmethod
    async def stop(self) -> bool:
        """停止插件"""
        pass
    
    @abstractmethod
    async def cleanup(self) -> bool:
        """清理插件资源"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        pass
    
    @abstractmethod
    async def get_status(self) -> Dict[str, Any]:
        """获取插件状态"""
        pass
    
    # 可选方法
    async def reload_config(self, config: Dict[str, Any]) -> bool:
        """重新加载配置"""
        pass
```

#### 属性说明

- **plugin_id**: 插件的唯一标识符
- **plugin_type**: 插件类型（枚举值）
- **state**: 插件当前状态（枚举值）
- **config**: 插件配置字典
- **metadata**: 插件元数据

#### 方法说明

- **initialize()**: 插件初始化，设置配置和内部状态
- **start()**: 启动插件，开始提供服务
- **stop()**: 停止插件，暂停服务
- **cleanup()**: 清理插件资源，释放内存
- **health_check()**: 检查插件健康状态
- **get_status()**: 获取插件详细状态信息
- **reload_config()**: 热重载配置（可选）

### ISessionManagementPlugin

会话管理插件接口，继承自IPlugin。

```python
from mercari_agent.plugins.interfaces import ISessionManagementPlugin

class ISessionManagementPlugin(IPlugin):
    """会话管理插件接口"""
    
    @abstractmethod
    async def create_session(self, session_id: str, config: Dict[str, Any]) -> bool:
        """创建会话"""
        pass
    
    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话"""
        pass
    
    @abstractmethod
    async def update_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """更新会话"""
        pass
    
    @abstractmethod
    async def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        pass
    
    @abstractmethod
    async def list_sessions(self) -> List[Dict[str, Any]]:
        """列出所有会话"""
        pass
    
    @abstractmethod
    async def cleanup_sessions(self) -> int:
        """清理过期会话"""
        pass
```

### IFingerprintManagementPlugin

指纹管理插件接口，继承自IPlugin。

```python
from mercari_agent.plugins.interfaces import IFingerprintManagementPlugin

class IFingerprintManagementPlugin(IPlugin):
    """指纹管理插件接口"""
    
    @abstractmethod
    async def generate_fingerprint(self, user_agent: str, platform: str) -> str:
        """生成指纹"""
        pass
    
    @abstractmethod
    async def get_fingerprint(self, fingerprint_id: str) -> Optional[Dict[str, Any]]:
        """获取指纹"""
        pass
    
    @abstractmethod
    async def update_fingerprint(self, fingerprint_id: str, data: Dict[str, Any]) -> bool:
        """更新指纹"""
        pass
    
    @abstractmethod
    async def delete_fingerprint(self, fingerprint_id: str) -> bool:
        """删除指纹"""
        pass
    
    @abstractmethod
    async def list_fingerprints(self) -> List[Dict[str, Any]]:
        """列出所有指纹"""
        pass
    
    @abstractmethod
    async def rotate_fingerprints(self) -> int:
        """轮换指纹"""
        pass
```

### IBehaviorSimulationPlugin

行为模拟插件接口，继承自IPlugin。

```python
from mercari_agent.plugins.interfaces import IBehaviorSimulationPlugin

class IBehaviorSimulationPlugin(IPlugin):
    """行为模拟插件接口"""
    
    @abstractmethod
    async def simulate_mouse_movement(self, start_pos: tuple, end_pos: tuple, duration: float) -> Dict[str, Any]:
        """模拟鼠标移动"""
        pass
    
    @abstractmethod
    async def simulate_typing(self, text: str, speed: float) -> Dict[str, Any]:
        """模拟打字"""
        pass
    
    @abstractmethod
    async def simulate_page_scroll(self, direction: str, distance: int) -> Dict[str, Any]:
        """模拟页面滚动"""
        pass
    
    @abstractmethod
    async def get_behavior_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取行为历史"""
        pass
```

## 插件类型和枚举

### PluginType

插件类型枚举。

```python
from mercari_agent.plugins.interfaces import PluginType

class PluginType(Enum):
    """插件类型枚举"""
    UNKNOWN = "unknown"
    SESSION_MANAGEMENT = "session_management"
    FINGERPRINT_MANAGEMENT = "fingerprint_management"
    BEHAVIOR_SIMULATION = "behavior_simulation"
    CAPTCHA_SOLVER = "captcha_solver"
    PROXY_MANAGER = "proxy_manager"
    REQUEST_INTERCEPTOR = "request_interceptor"
    RESPONSE_PROCESSOR = "response_processor"
    ANTI_DETECTION = "anti_detection"
```

### PluginState

插件状态枚举。

```python
from mercari_agent.plugins.interfaces import PluginState

class PluginState(Enum):
    """插件状态枚举"""
    UNLOADED = "unloaded"
    LOADING = "loading"
    INACTIVE = "inactive"
    INITIALIZING = "initializing"
    READY = "ready"
    STARTING = "starting"
    ACTIVE = "active"
    STOPPING = "stopping"
    ERROR = "error"
    DISABLED = "disabled"
```

### PluginCapability

插件能力枚举。

```python
from mercari_agent.plugins.interfaces import PluginCapability

class PluginCapability(Enum):
    """插件能力枚举"""
    CONFIGURABLE = "configurable"
    MONITORABLE = "monitorable"
    HOT_RELOADABLE = "hot_reloadable"
    DEPENDENCY_INJECTION = "dependency_injection"
    EVENT_DRIVEN = "event_driven"
    RESOURCE_POOLING = "resource_pooling"
    CACHING = "caching"
    ASYNC_PROCESSING = "async_processing"
    BATCH_PROCESSING = "batch_processing"
    STREAM_PROCESSING = "stream_processing"
```

### PluginMetadata

插件元数据数据类。

```python
from mercari_agent.plugins.interfaces import PluginMetadata

@dataclass
class PluginMetadata:
    """插件元数据"""
    plugin_id: str
    name: str
    version: str
    description: str
    author: str
    homepage: Optional[str] = None
    license: Optional[str] = None
    plugin_type: PluginType = PluginType.UNKNOWN
    capabilities: List[PluginCapability] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    supported_platforms: List[str] = field(default_factory=list)
    min_framework_version: Optional[str] = None
    max_framework_version: Optional[str] = None
    config_schema: Optional[Dict[str, Any]] = None
    tags: List[str] = field(default_factory=list)
```

## 插件框架

### PluginFramework

插件框架的主要管理类，采用单例模式。

```python
from mercari_agent.plugins.framework import PluginFramework

class PluginFramework:
    """插件框架主管理器"""
    
    def __init__(self):
        """初始化框架"""
        
    @classmethod
    async def get_instance(cls) -> 'PluginFramework':
        """获取框架实例（单例）"""
        
    async def register_plugin(self, plugin: IPlugin) -> bool:
        """注册插件"""
        
    async def unregister_plugin(self, plugin_id: str) -> bool:
        """注销插件"""
        
    async def initialize_plugin(self, plugin_id: str, config: Optional[Dict[str, Any]] = None) -> bool:
        """初始化插件"""
        
    async def start_plugin(self, plugin_id: str) -> bool:
        """启动插件"""
        
    async def stop_plugin(self, plugin_id: str) -> bool:
        """停止插件"""
        
    async def cleanup_plugin(self, plugin_id: str) -> bool:
        """清理插件"""
        
    async def get_plugin(self, plugin_id: str) -> Optional[IPlugin]:
        """获取插件实例"""
        
    async def get_plugins_by_type(self, plugin_type: PluginType) -> List[IPlugin]:
        """根据类型获取插件列表"""
        
    async def get_plugins_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有插件状态"""
        
    async def reload_plugin_config(self, plugin_id: str, config: Dict[str, Any]) -> bool:
        """重新加载插件配置"""
        
    async def health_check_all(self) -> Dict[str, bool]:
        """检查所有插件健康状态"""
        
    async def start_all_plugins(self) -> Dict[str, bool]:
        """启动所有插件"""
        
    async def stop_all_plugins(self) -> Dict[str, bool]:
        """停止所有插件"""
        
    async def cleanup_all_plugins(self) -> Dict[str, bool]:
        """清理所有插件"""
```

#### 使用示例

```python
# 获取框架实例
framework = await PluginFramework.get_instance()

# 注册插件
plugin = MyPlugin()
await framework.register_plugin(plugin)

# 初始化并启动插件
config = {"enabled": True, "timeout": 30}
await framework.initialize_plugin("my_plugin", config)
await framework.start_plugin("my_plugin")

# 获取插件状态
status = await framework.get_plugins_status()
print(status)

# 停止并清理插件
await framework.stop_plugin("my_plugin")
await framework.cleanup_plugin("my_plugin")
```

## 插件注册表

### PluginRegistry

插件注册表管理插件的发现和注册。

```python
from mercari_agent.plugins.registry import PluginRegistry

class PluginRegistry:
    """插件注册表"""
    
    def __init__(self):
        """初始化注册表"""
        
    async def register_plugin(self, plugin: IPlugin) -> bool:
        """注册插件"""
        
    async def unregister_plugin(self, plugin_id: str) -> bool:
        """注销插件"""
        
    async def get_plugin(self, plugin_id: str) -> Optional[IPlugin]:
        """获取插件"""
        
    async def get_plugins_by_type(self, plugin_type: PluginType) -> List[IPlugin]:
        """根据类型获取插件"""
        
    async def list_plugins(self) -> List[IPlugin]:
        """列出所有插件"""
        
    async def discover_plugins(self, search_paths: List[str]) -> List[IPlugin]:
        """发现插件"""
        
    async def check_plugin_compatibility(self, plugin: IPlugin) -> bool:
        """检查插件兼容性"""
        
    async def validate_plugin_dependencies(self, plugin: IPlugin) -> bool:
        """验证插件依赖"""
```

## 插件加载器

### PluginLoader

插件动态加载器，支持热插拔。

```python
from mercari_agent.plugins.loader import PluginLoader

class PluginLoader:
    """插件加载器"""
    
    def __init__(self):
        """初始化加载器"""
        
    async def load_plugin(self, plugin_path: str) -> Optional[IPlugin]:
        """加载插件"""
        
    async def unload_plugin(self, plugin_id: str) -> bool:
        """卸载插件"""
        
    async def reload_plugin(self, plugin_id: str) -> bool:
        """重新加载插件"""
        
    async def load_plugins_from_directory(self, directory: str) -> List[IPlugin]:
        """从目录加载插件"""
        
    async def watch_plugin_directory(self, directory: str, callback: Callable):
        """监控插件目录变化"""
        
    async def get_loaded_plugins(self) -> List[IPlugin]:
        """获取已加载插件"""
        
    async def enable_hot_reload(self, plugin_id: str) -> bool:
        """启用热重载"""
        
    async def disable_hot_reload(self, plugin_id: str) -> bool:
        """禁用热重载"""
```

## 生命周期管理

### PluginLifecycleManager

插件生命周期管理器。

```python
from mercari_agent.plugins.lifecycle import PluginLifecycleManager

class PluginLifecycleManager:
    """插件生命周期管理器"""
    
    def __init__(self):
        """初始化生命周期管理器"""
        
    async def initialize_plugin(self, plugin: IPlugin, config: Optional[Dict[str, Any]] = None) -> bool:
        """初始化插件"""
        
    async def start_plugin(self, plugin: IPlugin) -> bool:
        """启动插件"""
        
    async def stop_plugin(self, plugin: IPlugin) -> bool:
        """停止插件"""
        
    async def cleanup_plugin(self, plugin: IPlugin) -> bool:
        """清理插件"""
        
    async def get_plugin_state(self, plugin: IPlugin) -> PluginState:
        """获取插件状态"""
        
    async def set_plugin_state(self, plugin: IPlugin, state: PluginState) -> bool:
        """设置插件状态"""
        
    async def transition_plugin_state(self, plugin: IPlugin, target_state: PluginState) -> bool:
        """转换插件状态"""
        
    async def resolve_dependencies(self, plugins: List[IPlugin]) -> List[IPlugin]:
        """解析依赖关系"""
        
    async def get_startup_order(self, plugins: List[IPlugin]) -> List[IPlugin]:
        """获取启动顺序"""
        
    async def get_shutdown_order(self, plugins: List[IPlugin]) -> List[IPlugin]:
        """获取关闭顺序"""
```

## 配置管理

### PluginConfigManager

插件配置管理器，支持热重载。

```python
from mercari_agent.plugins.config_manager import PluginConfigManager

class PluginConfigManager:
    """插件配置管理器"""
    
    def __init__(self):
        """初始化配置管理器"""
        
    async def load_config(self, plugin_id: str, config_path: Optional[str] = None) -> Dict[str, Any]:
        """加载配置"""
        
    async def save_config(self, plugin_id: str, config: Dict[str, Any], config_path: Optional[str] = None) -> bool:
        """保存配置"""
        
    async def reload_config(self, plugin_id: str) -> Dict[str, Any]:
        """重新加载配置"""
        
    async def get_config(self, plugin_id: str) -> Dict[str, Any]:
        """获取配置"""
        
    async def update_config(self, plugin_id: str, config: Dict[str, Any]) -> bool:
        """更新配置"""
        
    async def validate_config(self, plugin_id: str, config: Dict[str, Any]) -> bool:
        """验证配置"""
        
    async def get_config_schema(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """获取配置模式"""
        
    async def enable_hot_reload(self, plugin_id: str) -> bool:
        """启用热重载"""
        
    async def disable_hot_reload(self, plugin_id: str) -> bool:
        """禁用热重载"""
        
    async def watch_config_changes(self, plugin_id: str, callback: Callable):
        """监控配置变化"""
```

## 模式验证

### PluginSchemaValidator

插件配置模式验证器。

```python
from mercari_agent.plugins.schemas import PluginSchemaValidator

class PluginSchemaValidator:
    """插件配置模式验证器"""
    
    def __init__(self):
        """初始化验证器"""
        
    async def validate_config(self, config: Dict[str, Any], schema: Dict[str, Any]) -> bool:
        """验证配置"""
        
    async def get_validation_errors(self, config: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
        """获取验证错误"""
        
    async def generate_config_template(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """生成配置模板"""
        
    async def load_schema(self, schema_path: str) -> Dict[str, Any]:
        """加载模式"""
        
    async def register_schema(self, plugin_id: str, schema: Dict[str, Any]) -> bool:
        """注册模式"""
        
    async def get_schema(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """获取模式"""
        
    async def validate_plugin_config(self, plugin_id: str, config: Dict[str, Any]) -> bool:
        """验证插件配置"""
```

## 版本控制

### PluginVersionManager

插件版本控制管理器。

```python
from mercari_agent.plugins.version_control import PluginVersionManager

class PluginVersionManager:
    """插件版本控制管理器"""
    
    def __init__(self):
        """初始化版本管理器"""
        
    async def register_plugin_version(self, plugin_id: str, version: str, metadata: Dict[str, Any]) -> bool:
        """注册插件版本"""
        
    async def get_plugin_version(self, plugin_id: str) -> Optional[str]:
        """获取插件版本"""
        
    async def get_plugin_versions(self, plugin_id: str) -> List[str]:
        """获取插件所有版本"""
        
    async def check_compatibility(self, plugin_id: str, framework_version: str) -> bool:
        """检查兼容性"""
        
    async def resolve_dependencies(self, plugin_id: str, version: str) -> List[Dict[str, str]]:
        """解析依赖"""
        
    async def upgrade_plugin(self, plugin_id: str, target_version: str) -> bool:
        """升级插件"""
        
    async def downgrade_plugin(self, plugin_id: str, target_version: str) -> bool:
        """降级插件"""
        
    async def get_upgrade_path(self, plugin_id: str, from_version: str, to_version: str) -> List[str]:
        """获取升级路径"""
```

## 错误处理

### PluginException

插件异常基类。

```python
from mercari_agent.plugins.exceptions import PluginException

class PluginException(Exception):
    """插件异常基类"""
    
    def __init__(self, plugin_id: str, message: str, error_code: Optional[str] = None):
        self.plugin_id = plugin_id
        self.message = message
        self.error_code = error_code
        super().__init__(f"Plugin {plugin_id}: {message}")
```

### 具体异常类

```python
class PluginNotFoundError(PluginException):
    """插件未找到异常"""
    pass

class PluginLoadError(PluginException):
    """插件加载异常"""
    pass

class PluginInitializationError(PluginException):
    """插件初始化异常"""
    pass

class PluginConfigurationError(PluginException):
    """插件配置异常"""
    pass

class PluginDependencyError(PluginException):
    """插件依赖异常"""
    pass

class PluginVersionError(PluginException):
    """插件版本异常"""
    pass

class PluginStateError(PluginException):
    """插件状态异常"""
    pass
```

## 使用示例

### 基本使用

```python
from mercari_agent.plugins.framework import PluginFramework
from mercari_agent.plugins.interfaces import IPlugin, PluginType, PluginState

# 创建插件
class MyPlugin(IPlugin):
    def __init__(self):
        self.plugin_id = "my_plugin"
        self.plugin_type = PluginType.ANTI_DETECTION
        self.state = PluginState.INACTIVE
        self.config = {}
        self.metadata = PluginMetadata(...)
    
    async def initialize(self, config=None):
        # 初始化逻辑
        return True
    
    async def start(self):
        # 启动逻辑
        return True
    
    async def stop(self):
        # 停止逻辑
        return True
    
    async def cleanup(self):
        # 清理逻辑
        return True
    
    async def health_check(self):
        # 健康检查
        return True
    
    async def get_status(self):
        # 获取状态
        return {"plugin_id": self.plugin_id, "state": self.state.value}

# 使用插件
async def main():
    framework = await PluginFramework.get_instance()
    
    # 注册插件
    plugin = MyPlugin()
    await framework.register_plugin(plugin)
    
    # 初始化并启动
    config = {"enabled": True}
    await framework.initialize_plugin("my_plugin", config)
    await framework.start_plugin("my_plugin")
    
    # 获取状态
    status = await framework.get_plugins_status()
    print(status)
    
    # 清理
    await framework.stop_plugin("my_plugin")
    await framework.cleanup_plugin("my_plugin")

# 运行
import asyncio
asyncio.run(main())
```

### 高级使用

```python
from mercari_agent.plugins.framework import PluginFramework
from mercari_agent.plugins.loader import PluginLoader
from mercari_agent.plugins.config_manager import PluginConfigManager

async def advanced_usage():
    # 获取框架实例
    framework = await PluginFramework.get_instance()
    
    # 动态加载插件
    loader = PluginLoader()
    plugin = await loader.load_plugin("/path/to/plugin.py")
    
    if plugin:
        # 注册插件
        await framework.register_plugin(plugin)
        
        # 配置管理
        config_manager = PluginConfigManager()
        config = await config_manager.load_config(plugin.plugin_id)
        
        # 验证配置
        if await config_manager.validate_config(plugin.plugin_id, config):
            # 初始化和启动
            await framework.initialize_plugin(plugin.plugin_id, config)
            await framework.start_plugin(plugin.plugin_id)
            
            # 启用热重载
            await config_manager.enable_hot_reload(plugin.plugin_id)
            
            # 监控配置变化
            async def on_config_change(new_config):
                await framework.reload_plugin_config(plugin.plugin_id, new_config)
            
            await config_manager.watch_config_changes(plugin.plugin_id, on_config_change)
        
        # 健康检查
        health_status = await framework.health_check_all()
        print(f"Health Status: {health_status}")
        
        # 获取插件状态
        status = await framework.get_plugins_status()
        print(f"Plugin Status: {status}")

# 运行
asyncio.run(advanced_usage())
```

## 最佳实践

1. **插件设计原则**
   - 单一职责：每个插件应该只负责一个特定功能
   - 接口清晰：实现明确的接口，避免紧耦合
   - 异步优先：使用异步方法提高性能
   - 错误处理：妥善处理异常情况

2. **配置管理**
   - 使用JSON Schema验证配置
   - 支持配置热重载
   - 提供合理的默认值
   - 敏感信息加密存储

3. **生命周期管理**
   - 正确实现生命周期方法
   - 处理依赖关系
   - 优雅关闭和清理
   - 状态转换的原子性

4. **性能优化**
   - 使用资源池管理
   - 实现缓存机制
   - 异步并发处理
   - 监控和指标收集

5. **测试和调试**
   - 编写单元测试
   - 模拟依赖组件
   - 日志记录
   - 性能基准测试

这个API参考文档提供了插件框架的完整接口说明，可以帮助开发者快速理解和使用框架。