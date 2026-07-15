# Mercari AI Agent - LLM集成与工具调用架构

## 概述

Mercari AI Agent是一个智能购物助手系统，专为日本Mercari平台设计。该系统集成了多个LLM提供商，并实现了强大的工具调用架构，能够执行复杂的商品搜索、分析和推荐任务。

## 核心特性

### 🤖 多LLM提供商支持
- **OpenAI GPT-o3/GPT-o4-mini**: 主要推理引擎
- **Anthropic Claude**: 备用推理引擎
- **Azure OpenAI**: 企业级支持
- **自动故障转移**: 提供商不可用时自动切换
- **成本跟踪**: 实时监控API调用成本
- **智能缓存**: 减少重复调用成本

### 🛠️ 强大的工具调用系统
- **模块化工具架构**: 易于扩展的工具系统
- **智能工具选择**: LLM自动选择最适合的工具
- **并行执行**: 支持多工具并发执行
- **错误处理**: 完善的错误恢复机制
- **中间件支持**: 可扩展的执行中间件

### 🎯 日语自然语言处理
- **查询理解**: 深度理解日语查询意图
- **查询扩展**: 自动扩展搜索关键词
- **类别建议**: 智能推荐商品类别
- **意图识别**: 准确识别用户购买意图

### 📊 智能分析引擎
- **商品评分**: 综合评估商品性价比
- **市场分析**: 分析市场趋势和价格波动
- **推荐系统**: 个性化商品推荐
- **竞争分析**: 对比类似商品

## 系统架构

```
mercari_ai_agent/
├── src/mercari_agent/
│   ├── core/                    # 核心组件
│   │   ├── tools/              # 工具系统
│   │   │   ├── base_tool.py    # 工具基类
│   │   │   ├── tool_registry.py # 工具注册表
│   │   │   ├── search_tools.py  # 搜索工具
│   │   │   ├── analysis_tools.py # 分析工具
│   │   │   └── formatting_tools.py # 格式化工具
│   │   ├── query_parser.py     # 查询解析器
│   │   ├── tool_orchestrator.py # 工具编排器
│   │   ├── recommendation_engine.py # 推荐引擎
│   │   └── output_formatter.py # 输出格式化
│   ├── services/               # 服务层
│   │   ├── llm_service.py     # LLM服务
│   │   ├── scraper_service.py # 爬虫服务
│   │   └── analysis_service.py # 分析服务
│   ├── prompts/               # 提示词管理
│   │   ├── system_prompts.py  # 系统提示词
│   │   ├── query_prompts.py   # 查询提示词
│   │   ├── analysis_prompts.py # 分析提示词
│   │   └── formatting_prompts.py # 格式化提示词
│   ├── config/                # 配置系统
│   │   └── settings.py        # 配置管理
│   ├── utils/                 # 工具函数
│   │   ├── japanese_processor.py # 日语处理
│   │   ├── price_normalizer.py # 价格标准化
│   │   └── logger.py          # 日志系统
│   └── main.py                # 主入口
├── tests/                     # 测试代码
│   ├── unit/                  # 单元测试
│   ├── integration/           # 集成测试
│   └── utils/                 # 测试工具
├── scripts/                   # 脚本文件
│   ├── run_tests.py          # 测试运行器
│   └── integration_test.py   # 集成测试
├── requirements.txt          # 依赖文件
├── requirements_test.txt     # 测试依赖
└── pytest.ini              # 测试配置
```

## 核心组件

### 1. LLM服务 (`services/llm_service.py`)

```python
# 多提供商支持
llm_service = LLMService(config)
response = await llm_service.generate_response(
    prompt="分析这个商品的性价比",
    provider="openai",  # 或 "anthropic", "azure"
    model="gpt-o4-mini"
)

# 自动故障转移
response = await llm_service.generate_response_with_fallback(
    prompt="查询处理",
    fallback_order=["openai", "anthropic", "azure"]
)

# 成本跟踪
cost_summary = llm_service.get_cost_summary()
```

### 2. 工具系统 (`core/tools/`)

```python
# 工具注册
registry = ToolRegistry()
registry.register_tool(ProductSearchTool())
registry.register_tool(ProductAnalysisTool())

# 工具执行
result = await registry.execute_tool(
    "search_products",
    query="iPhone 14",
    category="家電"
)
```

### 3. 查询解析器 (`core/query_parser.py`)

```python
# 查询理解
parser = QueryParser(llm_service)
query_result = await parser.parse_query("iPhone 14の中古を探している")

# 结果包含：
# - refined_query: "iPhone 14 中古"
# - category: "家電"
# - intent: "purchase"
# - price_range: {"min": 50000, "max": 120000}
```

### 4. 工具编排器 (`core/tool_orchestrator.py`)

```python
# 创建执行计划
plan = ToolExecutionPlan(steps=[
    {"tool": "search_products", "params": {"query": "iPhone"}},
    {"tool": "analyze_product", "params": {"product_data": None}},
    {"tool": "format_results", "params": {"results": None}}
])

# 执行计划
orchestrator = ToolOrchestrator(llm_service, tool_registry)
result = await orchestrator.execute_plan(plan, context)
```

## 工具类型

### 🔍 搜索工具
- **ProductSearchTool**: 商品搜索
- **MarketAnalysisTool**: 市场分析

### 📊 分析工具
- **ProductAnalysisTool**: 商品分析
- **PriceAnalysisTool**: 价格分析

### 📝 格式化工具
- **ResultsFormatterTool**: 结果格式化
- **ReportGeneratorTool**: 报告生成

## 配置系统

### 基本配置 (`config/settings.py`)

```python
# LLM配置
llm_config = LLMConfig(
    openai_api_key="your-openai-key",
    anthropic_api_key="your-anthropic-key",
    default_provider="openai",
    enable_fallback=True,
    enable_cost_tracking=True
)

# 工具配置
tool_config = ToolConfig(
    tool_timeout=30,
    max_tool_iterations=5,
    enable_tool_cache=True
)

# 成本跟踪配置
cost_config = CostTrackingConfig(
    daily_cost_limit=50.0,
    monthly_cost_limit=1000.0,
    enable_cost_optimization=True
)
```

## 使用方法

### 1. 基本使用

```python
from mercari_agent.main import MercariAIAgent

# 创建并初始化Agent
agent = MercariAIAgent()
await agent.initialize()

# 处理查询
result = await agent.process_query("iPhone 14 Pro の中古を探している")

# 查看结果
if result["success"]:
    print(f"找到 {result['total_products']} 个商品")
    print(f"分析了 {len(result['analyzed_products'])} 个商品")
    for product in result['analyzed_products']:
        print(f"- {product['product']['title']}: 评分 {product['analysis']['score']}")
```

### 2. 命令行使用

```bash
# 运行演示
python src/mercari_agent/main.py --demo

# 处理单个查询
python src/mercari_agent/main.py --query "iPhone 14 Pro"

# 系统健康检查
python src/mercari_agent/main.py --health

# 查看系统信息
python src/mercari_agent/main.py --info
```

### 3. 运行测试

```bash
# 安装测试依赖
pip install -r requirements_test.txt

# 运行单元测试
python scripts/run_tests.py --unit

# 运行集成测试
python scripts/run_tests.py --integration

# 运行所有测试
python scripts/run_tests.py --all

# 生成覆盖率报告
python scripts/run_tests.py --coverage

# 运行集成测试脚本
python scripts/integration_test.py
```

## 开发指南

### 1. 添加新工具

```python
from mercari_agent.core.tools.base_tool import BaseTool, ToolResult

class MyCustomTool(BaseTool):
    @property
    def name(self) -> str:
        return "my_custom_tool"
    
    @property
    def description(self) -> str:
        return "我的自定义工具"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "param1": {"type": "string", "required": True}
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        # 工具逻辑
        return ToolResult(
            success=True,
            data={"result": "执行成功"}
        )

# 注册工具
tool_registry.register_tool(MyCustomTool())
```

### 2. 添加新的LLM提供商

```python
# 在 llm_service.py 中添加新的提供商方法
async def _call_my_provider(self, prompt: str, **kwargs) -> LLMResponse:
    # 实现新提供商的调用逻辑
    pass

# 在 get_provider_config 中添加配置
def get_provider_config(self, provider: str) -> Dict:
    if provider == "my_provider":
        return {
            "api_key": self.my_provider_api_key,
            "model": self.my_provider_model
        }
```

### 3. 扩展提示词

```python
# 在 prompts/ 目录下创建新的提示词模块
class MyCustomPrompts:
    SYSTEM_PROMPT = """
    你是一个专业的助手...
    """
    
    QUERY_TEMPLATE = """
    请分析以下查询：{query}
    
    输出格式：
    {output_format}
    """
```

## 性能特性

### 📈 优化特性
- **智能缓存**: 减少重复LLM调用
- **并行执行**: 支持工具并发执行
- **批处理**: 批量处理多个查询
- **连接池**: 优化网络连接管理

### 💰 成本控制
- **实时成本跟踪**: 监控API调用成本
- **成本预警**: 超出预算时自动告警
- **智能选择**: 根据成本选择最优模型
- **缓存策略**: 减少不必要的API调用

### 🔒 安全特性
- **输入验证**: 严格的输入参数验证
- **错误处理**: 完善的异常处理机制
- **限流保护**: 防止API调用过频
- **数据脱敏**: 敏感信息处理

## 监控与日志

### 📊 监控指标
- **请求成功率**: 监控API调用成功率
- **响应时间**: 追踪系统响应性能
- **成本消耗**: 实时成本监控
- **工具使用**: 工具调用统计

### 📝 日志系统
- **结构化日志**: JSON格式日志输出
- **多级别日志**: DEBUG, INFO, WARNING, ERROR
- **性能日志**: 慢查询和性能瓶颈记录
- **错误追踪**: 详细的错误堆栈信息

## API文档

### 主要接口

#### 1. 处理查询
```python
async def process_query(query: str, user_id: str = "default") -> Dict[str, Any]
```

#### 2. 健康检查
```python
async def health_check() -> Dict[str, Any]
```

#### 3. 获取系统信息
```python
async def get_system_info() -> Dict[str, Any]
```

## 故障排除

### 常见问题

1. **LLM API调用失败**
   - 检查API密钥配置
   - 验证网络连接
   - 查看成本限制设置

2. **工具执行超时**
   - 调整工具超时设置
   - 检查网络连接
   - 优化工具逻辑

3. **配置加载失败**
   - 验证配置文件格式
   - 检查环境变量设置
   - 确认文件权限

### 调试技巧

1. **启用调试日志**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **使用集成测试**
   ```bash
   python scripts/integration_test.py
   ```

3. **查看详细错误**
   ```python
   try:
       result = await agent.process_query("test")
   except Exception as e:
       logger.error(f"错误详情: {e}", exc_info=True)
   ```

## 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 许可证

MIT License - 详见 LICENSE 文件

## 作者

Mercari AI Agent Team

---

**注意**: 这是一个演示项目，实际部署前请确保：
1. 配置真实的API密钥
2. 调整安全设置
3. 优化性能参数
4. 添加监控告警
5. 实施备份策略