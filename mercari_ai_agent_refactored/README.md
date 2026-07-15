# Mercari AI Agent - 重构版本

这是Mercari AI Agent系统的重构版本，采用了Clean Architecture架构模式，提供了更清晰的代码结构和更好的可维护性。

## 🚀 主要特性

- **Clean Architecture**: 遵循Clean Architecture原则，实现了良好的分层设计
- **多模块设计**: 清晰的模块划分，每个模块职责单一
- **多提供商LLM支持**: 支持OpenAI、Anthropic、Azure OpenAI等多个LLM提供商
- **REST API**: 基于FastAPI的高性能API接口
- **CLI工具**: 便于测试和调试的命令行接口
- **配置管理**: 灵活的环境配置管理
- **异步支持**: 全面的异步编程支持

## 📁 项目结构

```
mercari_ai_agent_refactored/
├── src/mercari_agent/
│   ├── domain/                 # 领域层
│   │   ├── entities/          # 实体对象
│   │   ├── repositories/      # 仓储接口
│   │   └── services/          # 领域服务
│   ├── application/           # 应用层
│   │   └── services/          # 应用服务
│   ├── infrastructure/        # 基础设施层
│   │   ├── llm/              # LLM服务
│   │   └── scraping/         # 爬虫服务
│   ├── interfaces/           # 接口层
│   │   ├── api/              # REST API
│   │   └── cli/              # CLI接口
│   └── shared/               # 共享模块
│       ├── config/           # 配置管理
│       ├── utils/            # 工具函数
│       └── exceptions/       # 异常定义
├── tests/                    # 测试文件
├── configs/                  # 配置文件
└── requirements.txt          # 项目依赖
```

## 🛠️ 安装和设置

### 1. 安装依赖

```bash
cd mercari_ai_agent_refactored
pip install -r requirements.txt
```

### 2. 配置环境

创建 `.env` 文件：

```bash
# 环境设置
MERCARI_ENVIRONMENT=development
MERCARI_DEBUG=true

# API配置
MERCARI_API_HOST=localhost
MERCARI_API_PORT=8000
MERCARI_API_RATE_LIMIT=60

# LLM配置
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
AZURE_OPENAI_ENDPOINT=your_azure_endpoint_here

# 日志配置
MERCARI_LOG_LEVEL=INFO
MERCARI_LOG_DIR=logs
```

### 3. 目录结构初始化

```bash
# 创建日志目录
mkdir -p logs

# 创建数据目录（如果需要）
mkdir -p data
```

## 🚀 使用方法

### CLI工具

```bash
# 查看帮助
python cli.py --help

# 解析查询
python cli.py parse "iPhone 13 Pro 128GB"

# 搜索商品
python cli.py search "iPhone 13" --limit 10

# 生成推荐
python cli.py recommend --query "スマートフォン" --limit 5

# 格式化输出
python cli.py format --data '{"keywords": ["iPhone"]}' --format markdown
```

### REST API

启动API服务器：

```bash
# 默认配置启动
python src/mercari_agent/interfaces/api/server.py

# 自定义配置启动
python src/mercari_agent/interfaces/api/server.py --host 0.0.0.0 --port 8080 --reload
```

API端点：

- `GET /health` - 健康检查
- `POST /api/v1/search` - 商品搜索
- `POST /api/v1/recommend` - 获取推荐
- `POST /api/v1/query/parse` - 解析查询
- `GET /api/v1/system/status` - 系统状态

API文档访问：`http://localhost:8000/docs`

### API使用示例

#### 搜索商品

```bash
curl -X POST "http://localhost:8000/api/v1/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "iPhone 13 Pro",
    "min_price": 50000,
    "max_price": 100000,
    "limit": 10
  }'
```

#### 解析查询

```bash
curl -X POST "http://localhost:8000/api/v1/query/parse" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "iPhone 13 Pro 128GB 5万円以下",
    "language": "ja"
  }'
```

## 🧪 测试

### 运行集成测试

```bash
cd mercari_ai_agent_refactored
python tests/integration_test.py
```

### 测试覆盖的功能

- 配置加载测试
- 服务初始化测试
- 查询解析服务测试
- 推荐服务测试
- 输出格式化服务测试
- 爬虫服务测试
- CLI接口测试
- API接口测试
- 端到端工作流测试

## 🔧 配置选项

### 环境配置

系统支持多环境配置：

- `development` - 开发环境
- `staging` - 测试环境
- `production` - 生产环境

### LLM提供商配置

支持的LLM提供商：

- **OpenAI**: GPT-3.5, GPT-4
- **Anthropic**: Claude系列
- **Azure OpenAI**: Azure托管的OpenAI服务

### API配置选项

- `host`: 服务器主机地址
- `port`: 服务器端口
- `rate_limit`: 速率限制（每分钟请求数）
- `cors_origins`: 允许的CORS源

## 📊 监控和日志

### 系统监控

访问 `GET /api/v1/system/status` 获取：

- 系统资源使用情况
- 服务运行状态
- 性能指标
- 错误统计

### 日志配置

支持的日志级别：

- `DEBUG` - 调试信息
- `INFO` - 一般信息
- `WARNING` - 警告信息
- `ERROR` - 错误信息
- `CRITICAL` - 严重错误

## 🔄 架构说明

### Clean Architecture层级

1. **Domain层**: 核心业务逻辑，不依赖外部框架
2. **Application层**: 应用服务，协调Domain和Infrastructure
3. **Infrastructure层**: 外部服务接口，如LLM、爬虫等
4. **Interface层**: 用户接口，如REST API、CLI等

### 主要设计模式

- **依赖注入**: 服务间依赖通过注入管理
- **仓储模式**: 数据访问抽象
- **策略模式**: LLM提供商切换
- **中介者模式**: 服务间通信协调

## 🚦 性能优化

### 异步处理

- 全面使用async/await模式
- 并发处理多个请求
- 异步I/O操作优化

### 缓存策略

- LLM响应缓存
- 搜索结果缓存
- 配置缓存

### 速率限制

- API调用频率控制
- 令牌桶算法
- 用户级别限制

## 🛡️ 安全性

### API安全

- 速率限制防止滥用
- CORS配置
- 请求验证

### 数据安全

- 敏感配置脱敏
- 日志信息过滤
- 错误信息清理

## 🤝 贡献指南

1. Fork项目
2. 创建功能分支
3. 提交代码
4. 运行测试
5. 创建Pull Request

## 📝 更新日志

### v2.0.0 (重构版本)

- 完全重构架构，采用Clean Architecture
- 添加REST API支持
- 改进配置管理
- 增强错误处理
- 完善测试覆盖

## 📄 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 💬 支持

如有问题或建议，请：

1. 查看文档
2. 运行集成测试
3. 检查日志文件
4. 提交Issue

---

**Mercari AI Agent Team**  
*重构版本 v2.0.0*
