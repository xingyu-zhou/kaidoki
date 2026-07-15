# 配置文件目录

本目录包含 Mercari AI Agent 系统的配置文件和环境变量模板。

## 文件说明

### 配置文件

- `development.yaml` - 开发环境配置
- `production.yaml` - 生产环境配置
- `.env.template` - 环境变量模板文件

### 使用方法

1. **环境变量配置**
   ```bash
   # 复制模板文件
   cp config/.env.template config/.env
   
   # 编辑 .env 文件，填入实际的API密钥等敏感信息
   vim config/.env
   ```

2. **指定配置文件**
   ```bash
   # 使用开发环境配置
   python -m mercari_agent.main --config config/development.yaml
   
   # 使用生产环境配置
   python -m mercari_agent.main --config config/production.yaml
   ```

3. **环境变量优先级**
   - 环境变量的优先级高于配置文件
   - 可以通过环境变量覆盖配置文件中的设置

## 配置项说明

### 基础配置
- `environment`: 运行环境 (development/production/testing)
- `debug`: 调试模式开关
- `app_name`: 应用名称
- `app_version`: 应用版本

### LLM配置
- `openai_api_key`: OpenAI API密钥
- `anthropic_api_key`: Anthropic API密钥
- `azure_*`: Azure OpenAI配置
- `default_provider`: 默认LLM提供商
- `enable_fallback`: 是否启用备用提供商

### 爬虫配置
- `max_concurrent_requests`: 最大并发请求数
- `rate_limit_delay`: 请求间隔
- `enable_proxy`: 是否启用代理
- `headless`: 无头浏览器模式

### 缓存配置
- `enable_memory_cache`: 启用内存缓存
- `enable_disk_cache`: 启用磁盘缓存
- `enable_redis_cache`: 启用Redis缓存
- `cache_ttl`: 缓存过期时间

### 数据库配置
- `database_type`: 数据库类型 (sqlite/postgresql)
- `postgres_*`: PostgreSQL配置
- `sqlite_path`: SQLite文件路径

### API配置
- `host`: 服务器地址
- `port`: 服务器端口
- `enable_auth`: 是否启用认证
- `enable_cors`: 是否启用CORS

### 日志配置
- `level`: 日志级别 (DEBUG/INFO/WARNING/ERROR)
- `log_dir`: 日志目录
- `enable_json_logging`: 是否启用JSON格式日志

## 环境变量

### 必需的环境变量
- `OPENAI_API_KEY`: OpenAI API密钥
- `ANTHROPIC_API_KEY`: Anthropic API密钥（可选）
- `AZURE_OPENAI_ENDPOINT`: Azure OpenAI端点（可选）
- `AZURE_OPENAI_API_KEY`: Azure OpenAI API密钥（可选）

### 可选的环境变量
- `REDIS_HOST`: Redis服务器地址
- `REDIS_PASSWORD`: Redis密码
- `POSTGRES_HOST`: PostgreSQL服务器地址
- `POSTGRES_PASSWORD`: PostgreSQL密码
- `API_SECRET_KEY`: API密钥

## 安全注意事项

1. **敏感信息保护**
   - 不要将 `.env` 文件提交到版本控制
   - 使用环境变量存储API密钥等敏感信息
   - 定期更换密钥和密码

2. **生产环境配置**
   - 关闭调试模式
   - 使用强密码和密钥
   - 启用适当的安全头
   - 配置适当的日志级别

3. **网络安全**
   - 使用HTTPS
   - 配置适当的CORS策略
   - 启用请求限流
   - 使用防火墙和VPN

## 性能优化

1. **缓存策略**
   - 根据使用场景选择适当的缓存类型
   - 设置合理的缓存过期时间
   - 定期清理过期缓存

2. **并发控制**
   - 根据服务器性能调整并发数
   - 设置适当的请求间隔
   - 使用连接池优化数据库连接

3. **资源限制**
   - 设置内存使用限制
   - 限制文件大小
   - 配置适当的超时时间

## 监控和日志

1. **日志配置**
   - 选择适当的日志级别
   - 启用性能监控
   - 配置日志轮转

2. **健康检查**
   - 定期检查服务状态
   - 监控API响应时间
   - 跟踪错误率

3. **告警配置**
   - 设置错误阈值
   - 配置告警通知
   - 监控资源使用情况

## 故障排除

1. **常见问题**
   - API密钥无效：检查环境变量设置
   - 数据库连接失败：检查数据库配置和网络
   - 缓存连接失败：检查Redis配置
   - 爬虫被阻止：检查代理和请求频率

2. **调试模式**
   - 启用调试模式查看详细日志
   - 使用详细日志级别
   - 检查配置文件语法

3. **性能问题**
   - 检查缓存命中率
   - 监控内存使用情况
   - 优化数据库查询

## 部署指南

1. **开发环境**
   ```bash
   # 使用开发配置
   export ENVIRONMENT=development
   python -m mercari_agent.main serve --config config/development.yaml
   ```

2. **生产环境**
   ```bash
   # 使用生产配置
   export ENVIRONMENT=production
   python -m mercari_agent.main serve --config config/production.yaml
   ```

3. **Docker部署**
   ```bash
   # 构建镜像
   docker build -t mercari-ai-agent .
   
   # 运行容器
   docker run -d --name mercari-ai-agent \
     --env-file config/.env \
     -p 8000:8000 \
     mercari-ai-agent
   ```

## 配置验证

系统启动时会自动验证配置的有效性，包括：
- 必需配置项的存在性
- API密钥的有效性
- 数据库连接
- 缓存服务连接
- 文件权限检查

如果配置验证失败，系统将输出详细的错误信息并退出。

## 支持

如果在配置过程中遇到问题，请：
1. 检查日志文件获取详细错误信息
2. 验证环境变量设置
3. 确认网络连接和服务状态
4. 查看系统文档和FAQ