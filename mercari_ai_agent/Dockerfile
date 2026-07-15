# Mercari AI Agent Dockerfile
# 用于构建Mercari AI Agent的Docker镜像

FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libc6-dev \
    libffi-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 创建非root用户
RUN useradd -r -s /bin/false -m -d /app mercari_agent

# 复制依赖文件
COPY requirements.txt requirements-dev.txt ./

# 安装Python依赖
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 复制源代码
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/

# 创建必要的目录
RUN mkdir -p /app/data /app/logs /app/cache /app/temp && \
    chown -R mercari_agent:mercari_agent /app

# 设置权限
RUN chmod +x scripts/*.sh

# 切换到非root用户
USER mercari_agent

# 健康检查
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 暴露端口
EXPOSE 8000

# 默认命令
CMD ["python", "-m", "mercari_agent.main", "serve", "--config", "config/production.yaml"]