# Mercari反检测系统 - 快速使用指南

## 🚀 快速开始

### 1. 紧急修复部署
```bash
# 一键部署紧急修复
python emergency_captcha_fix_deployment.py --mode=emergency

# 仅验证不执行
python emergency_captcha_fix_deployment.py --verify-only

# 运行健康检查
python emergency_captcha_fix_deployment.py --health-check
```

### 2. 基础使用示例
```python
import asyncio
from mercari_agent.scrapers.anti_detection_integration import (
    create_anti_detection_system, IntegrationMode
)

async def main():
    # 创建反检测系统（隐身模式）
    system = await create_anti_detection_system(IntegrationMode.STEALTH)
    
    # 创建会话
    session_id = await system.create_session()
    
    # 执行请求（自动应用所有反检测措施）
    response = await system.execute_request(
        session_id=session_id,
        url="https://jp.mercari.com/search?keyword=iPhone"
    )
    
    print(f"响应状态: {response.status}")
    content = await response.text()
    print(f"内容长度: {len(content)}")
    
    # 关闭会话
    await system.close_session(session_id)

# 运行示例
asyncio.run(main())
```

## ⚙️ 配置模式

### 1. 预设模式选择
```python
from mercari_agent.scrapers.anti_detection_integration import IntegrationMode

# 隐身模式 - 最大程度避免检测（推荐）
system = await create_anti_detection_system(IntegrationMode.STEALTH)

# 平衡模式 - 性能与安全平衡
system = await create_anti_detection_system(IntegrationMode.BALANCED)

# 性能模式 - 优先考虑性能
system = await create_anti_detection_system(IntegrationMode.PERFORMANCE)

# 调试模式 - 用于问题排查
system = await create_anti_detection_system(IntegrationMode.DEBUGGING)
```

### 2. 自定义配置
```python
from mercari_agent.config.unified_config_manager import get_config_manager

# 获取配置管理器
config = get_config_manager()

# 切换到隐身模式
await config.switch_mode(ConfigMode.STEALTH)

# 动态调整参数
await config.set_config("session_management.request_intervals.min_interval", 20.0)
await config.set_config("detector.confidence_threshold", 0.5)

# 应用Mercari特定优化
await config.set_config("mercari_specific.enabled", True)
```

## 🛠️ 与现有系统集成

### 1. 替换现有会话管理器
```python
# 原始代码
from mercari_agent.scrapers.enhanced_session_manager import EnhancedSessionManager

class MercariScraper:
    def __init__(self):
        self.session_manager = EnhancedSessionManager()

# 升级后代码
from mercari_agent.scrapers.anti_detection_integration import AntiDetectionIntegration

class MercariScraper:
    def __init__(self):
        self.anti_detection = AntiDetectionIntegration()
    
    async def initialize(self):
        await self.anti_detection.initialize()
        self.session_id = await self.anti_detection.create_session()
    
    async def make_request(self, url):
        return await self.anti_detection.execute_request(self.session_id, url)
```

### 2. 在搜索工具中集成
```python
# 修改 src/mercari_agent/core/tools/search_tools.py
from mercari_agent.scrapers.anti_detection_integration import create_anti_detection_system, IntegrationMode

class SearchTools:
    def __init__(self):
        self.anti_detection_system = None
        self.session_id = None
    
    async def initialize(self):
        # 初始化反检测系统
        self.anti_detection_system = await create_anti_detection_system(IntegrationMode.STEALTH)
        self.session_id = await self.anti_detection_system.create_session()
    
    async def search_mercari(self, keyword: str, max_pages: int = 3):
        """使用反检测系统进行搜索"""
        if not self.anti_detection_system:
            await self.initialize()
        
        url = f"https://jp.mercari.com/search?keyword={keyword}"
        
        # 使用反检测系统执行请求
        response = await self.anti_detection_system.execute_request(
            session_id=self.session_id,
            url=url
        )
        
        return await response.text()
```

## 📊 监控和调试

### 1. 获取系统统计
```python
# 获取运行统计
stats = system.get_stats()
print(f"活跃会话数: {stats['active_sessions']}")
print(f"检测事件数: {stats['detection_events']}")
print(f"成功绕过数: {stats['successful_bypasses']}")
```

### 2. 注册事件处理器
```python
from mercari_agent.scrapers.anti_detection_integration import DetectionEvent

async def my_captcha_handler(event_data):
    print(f"检测到CAPTCHA: {event_data.url}")
    # 自定义处理逻辑
    return True

# 注册处理器
system.register_event_handler(DetectionEvent.CAPTCHA_TRIGGERED, my_captcha_handler)
```

### 3. 配置回调监控
```python
from mercari_agent.config.unified_config_manager import get_config_manager

config = get_config_manager()

def on_config_change(path, old_value, new_value):
    print(f"配置更改: {path} = {old_value} -> {new_value}")

# 注册配置变更回调
config.register_callback("detector.confidence_threshold", on_config_change)
```

## 🚨 故障排除

### 1. 常见问题

**Q: CAPTCHA仍然被触发**
```python
# A: 降低置信度阈值
await config.set_config("detector.confidence_threshold", 0.4)

# 增加请求间隔
await config.set_config("session_management.request_intervals.min_interval", 25.0)
```

**Q: 系统性能较慢**
```python
# A: 切换到性能模式
await config.switch_mode(ConfigMode.PERFORMANCE)

# 或者调整并发数
await config.set_config("session_management.concurrency.max_concurrent_sessions", 5)
```

**Q: 内存使用过高**
```python
# A: 减少指纹池大小
await config.set_config("fingerprint_management.pool.max_fingerprints", 50)

# 增加轮换频率
await config.set_config("fingerprint_management.pool.rotation_interval", 900)
```

### 2. 调试模式
```python
# 启用调试模式
await config.set_config("global.debug_mode", True)
await config.set_config("global.log_level", "DEBUG")

# 启用检测事件导出
await config.set_config("development.export.export_samples", True)
```

### 3. 健康检查
```python
# 运行完整健康检查
python emergency_captcha_fix_deployment.py --health-check

# 或在代码中检查
from mercari_agent.scrapers.anti_detection_integration import HealthChecker

checker = HealthChecker()
results = await checker.run_health_check()
print(f"系统状态: {results['overall_status']}")
```

## 📈 性能优化建议

### 1. 针对Mercari的优化
```python
# 启用Mercari特定优化
await config.set_config("mercari_specific.enabled", True)
await config.set_config("mercari_specific.detection_points.auth_code_handling", True)

# 设置日语环境
await config.set_config("mercari_specific.headers.accept_language", "ja,ja-JP;q=0.9")
```

### 2. 批量操作优化
```python
# 对于大批量搜索，使用会话复用
async def batch_search(keywords):
    system = await create_anti_detection_system(IntegrationMode.STEALTH)
    session_id = await system.create_session()
    
    results = []
    for keyword in keywords:
        url = f"https://jp.mercari.com/search?keyword={keyword}"
        response = await system.execute_request(session_id, url)
        results.append(await response.text())
        
        # 智能延迟
        await asyncio.sleep(1)  # 系统会自动调整间隔
    
    await system.close_session(session_id)
    return results
```

### 3. 资源管理
```python
# 正确的资源清理
async def clean_shutdown():
    await system.shutdown()  # 清理所有资源
```

## 📝 最佳实践

1. **总是使用STEALTH模式**进行生产环境爬取
2. **定期监控CAPTCHA触发率**，目标<5%
3. **合理设置请求间隔**，不要过于激进
4. **及时更新配置**，根据反馈调整参数
5. **使用健康检查**确保系统正常运行
6. **正确处理异常**，避免系统崩溃
7. **定期备份配置**，便于问题恢复

## 🔄 升级和迁移

从旧版本升级：
```bash
# 1. 备份现有配置
cp -r config config_backup

# 2. 运行升级脚本
python emergency_captcha_fix_deployment.py --mode=emergency

# 3. 验证升级
python emergency_captcha_fix_deployment.py --health-check
```

---

## 📞 技术支持

如果遇到问题，请：
1. 查看日志文件 `logs/mercari_agent.log`
2. 运行健康检查
3. 检查配置文件语法
4. 参考故障排除指南

**紧急情况下使用回滚**：
```bash
# 自动回滚到上一个备份
python emergency_captcha_fix_deployment.py --rollback