# 插件框架开发指南

欢迎使用Mercari AI Agent的统一模块化插件框架！这是一个功能强大、易于扩展的插件系统，专为反检测场景设计。

## 📚 目录

- [快速开始](#快速开始)
- [核心概念](#核心概念)
- [插件开发](#插件开发)
- [配置管理](#配置管理)
- [版本控制](#版本控制)
- [最佳实践](#最佳实践)
- [API参考](#api参考)
- [示例代码](#示例代码)

## 🚀 快速开始

### 安装依赖

```bash
# 基础依赖
pip install asyncio pathlib typing

# 推荐依赖（用于配置验证）
pip install jsonschema pyyaml

# 开发依赖（用于测试）
pip install pytest pytest-asyncio pytest-cov
```

### 创建第一个插件

```python
from mercari_agent.plugins import IPlugin, PluginType, PluginState

class MyFirstPlugin(IPlugin):
    """我的第一个插件"""
    
    def __init__(self):
        self.plugin_id = "my_first_plugin"
        self.plugin_type = PluginType.SESSION_MANAGEMENT
        self.state = PluginState.INACTIVE
        self.config = {}
    
    async def initialize(self, config: dict = None) -> bool:
        """初始化插件"""
        if config:
            self.config.update(config)
        self.state = PluginState.READY
        print(f"插件 {self.plugin_id} 初始化完成")
        return True
    
    async def start(self) -> bool:
        """启动插件"""
        self.state = PluginState.ACTIVE
        print(f"插件 {self.plugin_id} 已启动")
        return True
    
    async def stop(self) -> bool:
        """停止插件"""
        self.state = PluginState.INACTIVE
        print(f"插件 {self.plugin_id} 已停止")
        return True
    
    async def cleanup(self) -> bool:
        """清理插件"""
        self.state = PluginState.UNLOADED
        print(f"插件 {self.plugin_id} 已清理")
        return True
```

### 使用插件框架

```python
from mercari_agent.plugins import PluginFramework

async def main():
    # 初始化框架
    framework = PluginFramework.get_instance()
    await framework.initialize()
    
    # 创建并注册插件
    plugin = MyFirstPlugin()
    await framework.register_plugin(plugin)
    
    # 插件生命周期管理
    await framework.load_plugin("my_first_plugin")
    await framework.start_plugin("my_first_plugin")
    
    # 获取插件状态
    status = await framework.get_plugin_health("my_first_plugin")
    print(f"插件状态: {status}")
    
    # 停止和清理
    await framework.stop_plugin("my_first_plugin")
    await framework.unload_plugin("my_first_plugin")
    await framework.shutdown()

# 运行示例
import asyncio
asyncio.run(main())
```

## 💡 核心概念

### 插件接口层次结构

```
IPlugin (基础接口)
├── ISessionManagementPlugin (会话管理)
├── IFingerprintPlugin (指纹管理)
├── IBehaviorSimulationPlugin (行为模拟)
└── ICaptchaDetectionPlugin (CAPTCHA检测)
```

### 插件状态机

```
INACTIVE → READY → ACTIVE
    ↓        ↓       ↓
UNLOADED ← READY ← INACTIVE
```

### 框架组件

- **PluginFramework**: 核心框架管理器
- **PluginRegistry**: 插件注册表
- **PluginLoader**: 插件加载器
- **PluginLifecycleManager**: 生命周期管理
- **PluginConfigManager**: 配置管理
- **PluginVersionManager**: 版本控制

## 🔧 插件开发

### 1. 选择合适的插件基类

根据功能选择对应的专用接口：

```python
# 会话管理插件
class MySessionPlugin(ISessionManagementPlugin):
    async def create_session(self, config: dict) -> Any:
        """创建会话的具体实现"""
        pass

# 指纹管理插件  
class MyFingerprintPlugin(IFingerprintPlugin):
    async def generate_fingerprint(self, platform: str) -> dict:
        """生成指纹的具体实现"""
        pass
```

### 2. 实现必需方法

所有插件都必须实现这些基础方法：

```python
async def initialize(self, config: dict = None) -> bool:
    """插件初始化，设置必要的资源"""
    
async def start(self) -> bool:
    """启动插件，开始提供服务"""
    
async def stop(self) -> bool:
    """停止插件，暂停服务但保持资源"""
    
async def cleanup(self) -> bool:
    """清理插件，释放所有资源"""
    
async def health_check(self) -> bool:
    """健康检查，返回插件是否正常"""
    
async def get_status(self) -> dict:
    """获取插件详细状态信息"""
    
async def reload_config(self, config: dict) -> bool:
    """重新加载配置，支持热更新"""
```

### 3. 定义插件元数据

```python
from mercari_agent.plugins import PluginMetadata, PluginCapability

class MyAdvancedPlugin(IPlugin):
    def __init__(self):
        self.plugin_id = "advanced_plugin"
        self.plugin_type = PluginType.FINGERPRINT
        self.metadata = PluginMetadata(
            plugin_id=self.plugin_id,
            name="高级插件示例",
            version="1.2.0",
            description="展示高级功能的示例插件",
            author="开发团队",
            homepage="https://example.com",
            plugin_type=self.plugin_type,
            capabilities=[
                PluginCapability.CONFIGURABLE,
                PluginCapability.MONITORABLE,
                PluginCapability.HOT_RELOADABLE
            ],
            supported_platforms=["windows", "linux", "macos"],
            min_framework_version="1.0.0"
        )
```

## ⚙️ 配置管理

### 1. 使用Schema验证

```python
# 定义配置Schema
config_schema = {
    "type": "object",
    "properties": {
        "enabled": {"type": "boolean", "default": True},
        "timeout": {"type": "number", "minimum": 1, "default": 30},
        "max_retries": {"type": "integer", "minimum": 0, "default": 3}
    },
    "required": ["enabled"]
}

# 验证配置
from mercari_agent.plugins import validate_plugin_config, PluginType

result = validate_plugin_config(PluginType.SESSION_MANAGEMENT, user_config)
if result['valid']:
    validated_config = result['normalized_config']
else:
    print(f"配置验证失败: {result['errors']}")
```

### 2. 配置文件管理

创建配置文件 `config/plugins/my_plugin.yaml`:

```yaml
# 插件基础配置
enabled: true
priority: "NORMAL"
timeout: 30.0

# 插件特定配置
max_connections: 10
retry_count: 3

# 支持环境变量
database_url: ${DATABASE_URL:sqlite:///default.db}
api_key: ${API_KEY}

# 嵌套配置
advanced:
  feature_flags:
    - experimental_mode
    - debug_logging
  limits:
    memory_mb: 512
    cpu_percent: 80
```

### 3. 热重载配置

```python
# 配置变更监听
async def on_config_change(plugin_id: str, new_config: dict):
    print(f"插件 {plugin_id} 配置已更新: {new_config}")

# 注册监听器
config_manager = framework.config_manager
config_manager.add_config_listener("my_plugin", on_config_change)

# 手动重新加载配置
await config_manager.reload_plugin_config("my_plugin")
```

## 📋 版本控制

### 1. 定义插件版本信息

```python
from mercari_agent.plugins import PluginVersionInfo, SemanticVersion

version_info = PluginVersionInfo(
    plugin_id="my_plugin",
    plugin_type=PluginType.SESSION_MANAGEMENT,
    version=SemanticVersion.parse("1.2.3"),
    description="版本更新说明",
    author="开发者",
    stability="stable",  # stable, beta, alpha, experimental
    dependencies=[
        PluginDependency(
            plugin_id="dependency_plugin",
            plugin_type=PluginType.FINGERPRINT,
            version_constraint=VersionConstraint.parse(">=1.0.0,<2.0.0"),
            required=True
        )
    ],
    min_framework_version=SemanticVersion.parse("1.0.0"),
    supported_platforms=["windows", "linux", "macos"],
    changelog="修复了内存泄漏问题，提升了性能"
)

# 注册版本信息
version_manager = framework.version_manager
await version_manager.register_plugin_version(version_info)
```

### 2. 兼容性检查

```python
# 检查版本兼容性
result = await version_manager.check_compatibility(
    "my_plugin", 
    SemanticVersion.parse("1.2.3")
)

if result['compatible']:
    print("版本兼容")
else:
    print(f"兼容性问题: {result['issues']}")
    print(f"依赖冲突: {result['dependency_conflicts']}")
```

### 3. 插件升级和回退

```python
# 升级插件
upgrade_result = await version_manager.upgrade_plugin(
    "my_plugin", 
    target_version=SemanticVersion.parse("1.3.0")
)

if upgrade_result['success']:
    print(f"升级成功: {upgrade_result['old_version']} -> {upgrade_result['new_version']}")
else:
    print(f"升级失败: {upgrade_result['actions']}")

# 回退插件
rollback_result = await version_manager.rollback_plugin(
    "my_plugin", 
    target_version=SemanticVersion.parse("1.2.3")
)
```

## 🎯 最佳实践

### 1. 插件设计原则

- **单一职责**: 每个插件只负责一个特定功能
- **松耦合**: 插件间通过标准接口通信
- **可测试**: 设计时考虑单元测试的便利性
- **异常安全**: 妥善处理所有异常情况
- **资源管理**: 正确管理内存、文件等资源

### 2. 性能优化

```python
class OptimizedPlugin(IPlugin):
    def __init__(self):
        super().__init__()
        self._cache = {}
        self._connection_pool = None
    
    async def initialize(self, config: dict = None) -> bool:
        # 使用连接池
        self._connection_pool = await create_pool(config.get('pool_size', 10))
        
        # 预热缓存
        await self._warm_cache()
        return True
    
    async def _warm_cache(self):
        """预热缓存，提升性能"""
        pass
    
    async def cleanup(self) -> bool:
        # 清理连接池
        if self._connection_pool:
            await self._connection_pool.close()
        
        # 清理缓存
        self._cache.clear()
        return True
```

### 3. 错误处理

```python
import logging
from mercari_agent.plugins import PluginException

class RobustPlugin(IPlugin):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(f"plugin.{self.plugin_id}")
    
    async def start(self) -> bool:
        try:
            await self._do_start()
            self.state = PluginState.ACTIVE
            return True
        except Exception as e:
            self.logger.error(f"插件启动失败: {e}", exc_info=True)
            self.state = PluginState.INACTIVE
            return False
    
    async def _do_start(self):
        """实际的启动逻辑"""
        # 可能抛出异常的启动代码
        pass
    
    async def health_check(self) -> bool:
        """健康检查实现"""
        try:
            # 检查关键资源状态
            return await self._check_resources()
        except Exception as e:
            self.logger.warning(f"健康检查异常: {e}")
            return False
```

### 4. 测试友好设计

```python
class TestablePlugin(IPlugin):
    def __init__(self, external_service=None):
        super().__init__()
        # 依赖注入，便于测试
        self.external_service = external_service or RealExternalService()
    
    async def process_data(self, data):
        """可测试的数据处理方法"""
        # 业务逻辑与外部依赖分离
        processed = self._transform_data(data)
        result = await self.external_service.send(processed)
        return self._handle_response(result)
    
    def _transform_data(self, data):
        """纯函数，易于单元测试"""
        return {"processed": data}
    
    def _handle_response(self, response):
        """纯函数，易于单元测试"""
        return response.get('success', False)
```

## 📖 API参考

详细的API文档请参考：
- [插件接口API](api/interfaces.md)
- [框架核心API](api/framework.md)
- [配置管理API](api/config.md)
- [版本控制API](api/version.md)

## 🔗 相关链接

- [插件示例代码](examples/)
- [常见问题解答](FAQ.md)
- [开发环境设置](development.md)
- [部署指南](deployment.md)
- [贡献指南](contributing.md)

## 📞 获得帮助

如果您在使用插件框架时遇到问题：

1. 查看[常见问题解答](FAQ.md)
2. 阅读[API文档](api/)
3. 参考[示例代码](examples/)
4. 联系开发团队

---

**Mercari AI Agent 插件框架** - 让扩展变得简单而强大！