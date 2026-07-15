# 简化智能请求频率控制和会话管理架构设计

## 设计原则：大道至简

基于现实约束和核心需求，采用最简化但有效的解决方案：

### 核心问题
- authCode检测0.80置信度触发CAPTCHA
- 8-15秒间隔仍不足够
- 需支持3页×20产品=60次请求
- 必须在合规框架内运行

### 设计哲学
**专注核心，去除冗余，快速见效**

---

## 1. 核心架构（三层设计）

```
请求入口 → 智能间隔控制 → 会话管理 → HTTP请求
                ↓
            反馈调整机制
```

### 1.1 智能间隔控制器（核心组件）
```python
class SimpleRateController:
    def __init__(self):
        self.base_interval = 15.0  # 基础间隔15秒
        self.current_interval = 15.0
        self.success_count = 0
        self.captcha_count = 0
        self.last_request_time = 0
        
    async def wait_for_next_request(self):
        """核心方法：计算并等待下次请求"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        # 简单自适应算法
        if elapsed < self.current_interval:
            wait_time = self.current_interval - elapsed
            await asyncio.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    def on_success(self):
        """成功后微调"""
        self.success_count += 1
        if self.success_count > 10:  # 连续成功10次后稍微加快
            self.current_interval = max(12.0, self.current_interval * 0.95)
            self.success_count = 0
    
    def on_captcha(self):
        """触发CAPTCHA后调整"""
        self.captcha_count += 1
        self.current_interval = min(30.0, self.current_interval * 1.5)
        self.success_count = 0
```

### 1.2 会话管理器（简化版）
```python
class SimpleSessionManager:
    def __init__(self):
        self.sessions = {}
        self.current_session_id = None
        self.session_request_count = 0
        
    async def get_session(self):
        """获取可用会话"""
        if self.current_session_id is None or self.session_request_count > 50:
            await self._create_new_session()
        
        return self.sessions[self.current_session_id]
    
    async def _create_new_session(self):
        """创建新会话"""
        session_id = f"session_{int(time.time())}"
        
        # 简单的会话配置
        session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            connector=aiohttp.TCPConnector(limit=5, ssl=False),
            headers={
                'User-Agent': self._get_random_user_agent(),
                'Accept-Language': 'ja,ja-JP;q=0.9,en;q=0.8'
            }
        )
        
        self.sessions[session_id] = session
        self.current_session_id = session_id
        self.session_request_count = 0
```

---

## 2. 核心算法（数学模型简化）

### 2.1 动态间隔计算
```
interval = base_interval × adaptive_factor × random_factor

其中：
- base_interval = 15秒（基础安全间隔）
- adaptive_factor = 1.0 ~ 2.0（根据CAPTCHA历史调整）
- random_factor = 0.8 ~ 1.2（随机化避免规律性）
```

### 2.2 自适应调整规则
```python
def calculate_adaptive_factor(self):
    """计算自适应因子"""
    if self.captcha_count == 0:
        return 1.0  # 无CAPTCHA，保持基础间隔
    
    # 触发CAPTCHA后的保守策略
    recent_captcha_rate = self.captcha_count / max(1, self.total_requests)
    
    if recent_captcha_rate > 0.1:  # 10%以上CAPTCHA率
        return 2.0  # 双倍间隔
    elif recent_captcha_rate > 0.05:  # 5%以上CAPTCHA率
        return 1.5  # 1.5倍间隔
    else:
        return 1.0  # 正常间隔
```

---

## 3. 请求伪装（基础版）

### 3.1 简化的行为模拟
```python
class SimpleRequestDisguise:
    async def make_disguised_request(self, session, url):
        """伪装请求"""
        
        # 1. 随机延迟（模拟用户思考时间）
        await asyncio.sleep(random.uniform(1.0, 3.0))
        
        # 2. 添加随机Header
        headers = {
            'Referer': self._get_natural_referer(url),
            'X-Requested-With': 'XMLHttpRequest' if random.random() > 0.7 else None
        }
        
        # 3. 发送请求
        async with session.get(url, headers=headers) as response:
            return response
    
    def _get_natural_referer(self, current_url):
        """生成自然的Referer"""
        if 'search' in current_url:
            return 'https://jp.mercari.com/'
        elif 'item' in current_url:
            return 'https://jp.mercari.com/search'
        else:
            return 'https://jp.mercari.com/'
```

### 3.2 Cookie管理（简化版）
```python
class SimpleCookieManager:
    def __init__(self):
        self.critical_cookies = ['__cf_bm', '_cfuvid', 'session_id']
        
    def filter_cookies(self, cookies):
        """只保留关键Cookie"""
        filtered = {}
        for name, value in cookies.items():
            if any(critical in name.lower() for critical in self.critical_cookies):
                filtered[name] = value
        return filtered
```

---

## 4. 监控和配置（极简版）

### 4.1 基础监控
```python
class SimpleMonitor:
    def __init__(self):
        self.stats = {
            'total_requests': 0,
            'captcha_count': 0,
            'success_count': 0,
            'current_interval': 15.0
        }
    
    def log_request_result(self, success, captcha_triggered):
        """记录请求结果"""
        self.stats['total_requests'] += 1
        
        if success:
            self.stats['success_count'] += 1
        
        if captcha_triggered:
            self.stats['captcha_count'] += 1
            
        # 简单日志
        logger.info(f"请求统计: 成功率={self.get_success_rate():.2%}, CAPTCHA率={self.get_captcha_rate():.2%}")
    
    def get_success_rate(self):
        return self.stats['success_count'] / max(1, self.stats['total_requests'])
    
    def get_captcha_rate(self):
        return self.stats['captcha_count'] / max(1, self.stats['total_requests'])
```

### 4.2 配置管理
```yaml
# simple_config.yaml
rate_control:
  base_interval: 15.0
  max_interval: 30.0
  min_interval: 12.0
  
session_management:
  max_requests_per_session: 50
  session_timeout: 1800
  
monitoring:
  log_interval: 10  # 每10次请求记录一次
  alert_captcha_rate: 0.1  # CAPTCHA率超过10%告警
```

---

## 5. 集成方案

### 5.1 与现有系统集成
```python
class EnhancedSessionManagerV2(EnhancedSessionManager):
    """在现有基础上增强"""
    
    def __init__(self):
        super().__init__()
        self.rate_controller = SimpleRateController()
        self.disguise = SimpleRequestDisguise()
        self.monitor = SimpleMonitor()
    
    async def make_request(self, url, **kwargs):
        """重写请求方法"""
        # 1. 频率控制
        await self.rate_controller.wait_for_next_request()
        
        # 2. 获取会话
        session = await self.get_session_safe()
        
        # 3. 伪装请求
        try:
            response = await self.disguise.make_disguised_request(session, url)
            
            # 4. 检查结果
            captcha_triggered = self._check_captcha(response)
            
            # 5. 更新统计
            self.rate_controller.on_success() if not captcha_triggered else self.rate_controller.on_captcha()
            self.monitor.log_request_result(True, captcha_triggered)
            
            return response
            
        except Exception as e:
            self.monitor.log_request_result(False, False)
            raise
    
    def _check_captcha(self, response):
        """检查是否触发CAPTCHA"""
        # 简单检查
        if response.status == 403:
            return True
        
        # 检查响应内容
        if 'authCode' in response.url.query.get('', ''):
            return True
            
        return False
```

---

## 6. 部署和运维

### 6.1 快速部署
```python
# 一键启动脚本
async def deploy_simple_system():
    """部署简化系统"""
    
    # 1. 创建管理器
    manager = EnhancedSessionManagerV2()
    
    # 2. 初始化
    await manager.initialize()
    
    # 3. 运行测试
    test_urls = [
        'https://jp.mercari.com/search?keyword=test',
        'https://jp.mercari.com/item/m12345'
    ]
    
    for url in test_urls:
        try:
            response = await manager.make_request(url)
            print(f"✅ {url}: {response.status}")
        except Exception as e:
            print(f"❌ {url}: {e}")
    
    return manager
```

### 6.2 关键参数调优
```python
# 关键参数（可在运行时调整）
TUNING_PARAMS = {
    'base_interval': 15.0,      # 基础间隔（秒）
    'captcha_penalty': 1.5,     # CAPTCHA惩罚倍数
    'success_bonus': 0.95,      # 成功奖励因子
    'max_interval': 30.0,       # 最大间隔
    'min_interval': 12.0        # 最小间隔
}
```

---

## 7. 预期效果

### 7.1 性能指标
- **CAPTCHA触发率**: < 5%
- **平均请求间隔**: 15-20秒
- **完成60次请求时间**: 15-20分钟
- **成功率**: > 95%

### 7.2 风险控制
- **保守策略**: 宁可慢一点，也要避免被封
- **自适应调整**: 出现CAPTCHA立即增加间隔
- **简单可靠**: 减少复杂逻辑，降低出错概率

---

## 8. 总结

这个简化设计专注于解决核心问题：
1. **有效的频率控制**：15秒基础间隔+自适应调整
2. **简单的会话管理**：基础轮换机制
3. **基础的请求伪装**：必要的Header和行为模拟
4. **实用的监控**：关键指标跟踪

**核心优势**：
- 代码简洁，易于维护
- 专注核心问题，避免过度设计
- 快速部署，立即见效
- 易于调试和优化

**实施建议**：
1. 先部署基础版本
2. 根据实际效果调整参数
3. 必要时再增加复杂功能