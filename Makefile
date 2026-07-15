# Mercari AI Agent - 重构版 Makefile
# 提供项目管理和开发任务的便捷命令

.PHONY: help install install-dev clean test test-unit test-integration test-e2e lint format type-check security-check build run run-api docker-build docker-run docker-compose-up docker-compose-down docs docs-serve backup restore deploy validate-env setup-dev

# 默认目标
help: ## 显示帮助信息
	@echo "Mercari AI Agent - 重构版"
	@echo "=========================="
	@echo ""
	@echo "可用命令:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# =============================================================================
# 环境设置
# =============================================================================

setup-dev: ## 设置开发环境
	@echo "🔧 设置开发环境..."
	uv sync --locked
	uv run playwright install chromium

validate-env: ## 验证环境变量
	@echo "🔍 验证环境变量..."
	@if [ ! -f .env ]; then \
		echo "❌ .env 文件不存在，请从 .env.template 复制并配置"; \
		exit 1; \
	fi
	@echo "✅ 环境变量文件存在"

install: ## 安装生产依赖
	@echo "📦 安装生产依赖..."
	uv sync --locked --no-dev

install-dev: ## 安装开发依赖
	@echo "📦 安装开发依赖..."
	uv sync --locked

# =============================================================================
# 代码质量
# =============================================================================

clean: ## 清理临时文件
	@echo "🧹 清理临时文件..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	rm -rf build/ dist/ htmlcov/ .coverage .coverage.*

format: ## 格式化代码
	@echo "🎨 格式化代码..."
	black src/ tests/
	isort src/ tests/

lint: ## 代码检查
	@echo "🔍 代码检查..."
	flake8 src/ tests/
	black --check src/ tests/
	isort --check-only src/ tests/

type-check: ## 类型检查
	@echo "🔍 类型检查..."
	mypy src/

security-check: ## 安全检查
	@echo "🔒 安全检查..."
	bandit -r src/
	safety check

# =============================================================================
# 测试
# =============================================================================

test: ## 运行所有测试
	@echo "🧪 运行所有测试..."
	uv run pytest

test-unit: ## 运行单元测试
	@echo "🧪 运行单元测试..."
	pytest tests/unit/ -v

test-integration: ## 运行集成测试
	@echo "🧪 运行集成测试..."
	pytest tests/integration/ -v

test-e2e: ## 运行端到端测试
	@echo "🧪 运行端到端测试..."
	pytest tests/e2e/ -v

test-coverage: ## 运行测试并生成覆盖率报告
	@echo "🧪 运行测试覆盖率..."
	pytest --cov=src/mercari_agent --cov-report=html --cov-report=term

test-watch: ## 监视文件变化并自动运行测试
	@echo "👀 监视测试..."
	pytest-watch

# =============================================================================
# 构建和运行
# =============================================================================

build: ## 构建项目
	@echo "🔨 构建项目..."
	uv build

run: validate-env ## 运行主程序
	@echo "🚀 运行主程序..."
	uv run mercari-agent

run-api: validate-env ## 运行API服务器
	@echo "🚀 运行API服务器..."
	uv run mercari-api

# =============================================================================
# Docker
# =============================================================================

docker-build: ## 构建Docker镜像
	@echo "🐳 构建Docker镜像..."
	docker build -t mercari-ai-agent:latest .

docker-run: ## 运行Docker容器
	@echo "🐳 运行Docker容器..."
	docker run -p 8000:8000 --env-file .env mercari-ai-agent:latest

docker-compose-up: ## 启动Docker Compose服务
	@echo "🐳 启动Docker Compose服务..."
	docker-compose up -d

docker-compose-down: ## 停止Docker Compose服务
	@echo "🐳 停止Docker Compose服务..."
	docker-compose down

docker-compose-logs: ## 查看Docker Compose日志
	@echo "🐳 查看Docker Compose日志..."
	docker-compose logs -f

# =============================================================================
# 文档
# =============================================================================

docs: ## 生成文档
	@echo "📚 生成文档..."
	cd docs && make html

docs-serve: ## 启动文档服务器
	@echo "📚 启动文档服务器..."
	cd docs/_build/html && python -m http.server 8080

docs-clean: ## 清理文档
	@echo "📚 清理文档..."
	cd docs && make clean

# =============================================================================
# 数据库
# =============================================================================

db-init: ## 初始化数据库
	@echo "🗄️ 初始化数据库..."
	python -m src.mercari_agent.infrastructure.database.init

db-migrate: ## 运行数据库迁移
	@echo "🗄️ 运行数据库迁移..."
	alembic upgrade head

db-migration: ## 创建新的数据库迁移
	@echo "🗄️ 创建数据库迁移..."
	@read -p "迁移名称: " name; \
	alembic revision --autogenerate -m "$$name"

db-reset: ## 重置数据库
	@echo "🗄️ 重置数据库..."
	@echo "⚠️ 这将删除所有数据！"
	@read -p "确认重置数据库? (y/N): " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		python -m src.mercari_agent.infrastructure.database.reset; \
	fi

# =============================================================================
# 部署
# =============================================================================

deploy-staging: ## 部署到测试环境
	@echo "🚀 部署到测试环境..."
	./scripts/deploy.sh staging

deploy-production: ## 部署到生产环境
	@echo "🚀 部署到生产环境..."
	@echo "⚠️ 部署到生产环境！"
	@read -p "确认部署到生产环境? (y/N): " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		./scripts/deploy.sh production; \
	fi

# =============================================================================
# 备份和恢复
# =============================================================================

backup: ## 备份数据
	@echo "💾 备份数据..."
	python -m src.mercari_agent.scripts.backup

restore: ## 恢复数据
	@echo "📥 恢复数据..."
	@read -p "备份文件路径: " backup_file; \
	python -m src.mercari_agent.scripts.restore "$$backup_file"

# =============================================================================
# 监控和日志
# =============================================================================

logs: ## 查看日志
	@echo "📋 查看日志..."
	tail -f data/logs/mercari_agent.log

logs-error: ## 查看错误日志
	@echo "📋 查看错误日志..."
	tail -f data/logs/errors.log

monitor: ## 启动监控
	@echo "📊 启动监控..."
	python -m src.mercari_agent.monitoring.dashboard

# =============================================================================
# 开发工具
# =============================================================================

shell: ## 启动Python shell
	@echo "🐍 启动Python shell..."
	python -c "from src.mercari_agent import *; print('Mercari AI Agent shell ready!')"

jupyter: ## 启动Jupyter notebook
	@echo "📓 启动Jupyter notebook..."
	jupyter notebook

profile: ## 性能分析
	@echo "⚡ 性能分析..."
	python -m cProfile -o profile.stats -m src.mercari_agent.main
	python -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumulative').print_stats(20)"

benchmark: ## 运行基准测试
	@echo "⚡ 运行基准测试..."
	python -m src.mercari_agent.benchmarks.runner

# =============================================================================
# 插件管理
# =============================================================================

plugin-list: ## 列出已安装的插件
	@echo "🔌 列出插件..."
	python -m src.mercari_agent.plugins.cli list

plugin-install: ## 安装插件
	@echo "🔌 安装插件..."
	@read -p "插件名称或路径: " plugin; \
	python -m src.mercari_agent.plugins.cli install "$$plugin"

plugin-uninstall: ## 卸载插件
	@echo "🔌 卸载插件..."
	@read -p "插件名称: " plugin; \
	python -m src.mercari_agent.plugins.cli uninstall "$$plugin"

# =============================================================================
# 工具
# =============================================================================

tool-list: ## 列出可用工具
	@echo "🛠️ 列出工具..."
	python -m src.mercari_agent.tools.cli list

tool-test: ## 测试工具
	@echo "🛠️ 测试工具..."
	@read -p "工具名称: " tool; \
	python -m src.mercari_agent.tools.cli test "$$tool"

# =============================================================================
# 配置管理
# =============================================================================

config-validate: ## 验证配置
	@echo "⚙️ 验证配置..."
	python -m src.mercari_agent.config.validator

config-generate: ## 生成配置模板
	@echo "⚙️ 生成配置模板..."
	python -m src.mercari_agent.config.generator

# =============================================================================
# 版本管理
# =============================================================================

version: ## 显示版本信息
	@echo "📋 版本信息..."
	python -c "from src.mercari_agent import get_version_info; import json; print(json.dumps(get_version_info(), indent=2))"

release: ## 创建发布版本
	@echo "🏷️ 创建发布版本..."
	@read -p "版本号 (例如: 2.1.0): " version; \
	python -m src.mercari_agent.scripts.release "$$version"

# =============================================================================
# 全面检查
# =============================================================================

check-all: clean lint type-check security-check test ## 运行所有检查
	@echo "✅ 所有检查完成！"

ci: check-all ## CI/CD 流水线
	@echo "🔄 CI/CD 流水线完成！"

# =============================================================================
# 快速开始
# =============================================================================

quickstart: ## 快速开始（首次使用）
	@echo "🚀 Mercari AI Agent 快速开始..."
	@echo "1. 设置开发环境..."
	make setup-dev
	@echo "2. 请激活虚拟环境后运行: make install-dev"
	@echo "3. 复制环境变量模板: cp .env.template .env"
	@echo "4. 编辑 .env 文件，填入必要的配置"
	@echo "5. 运行测试: make test"
	@echo "6. 启动应用: make run"

# =============================================================================
# 项目信息
# =============================================================================

info: ## 显示项目信息
	@echo "📋 项目信息"
	@echo "============"
	@echo "项目名称: Mercari AI Agent - 重构版"
	@echo "版本: 2.0.0"
	@echo "Python版本: $(shell python --version)"
	@echo "项目路径: $(shell pwd)"
	@echo "虚拟环境: $(shell which python)"
	@echo ""
	@echo "📊 项目统计"
	@echo "============"
	@echo "Python文件数: $(shell find src/ -name '*.py' | wc -l)"
	@echo "测试文件数: $(shell find tests/ -name '*.py' | wc -l)"
	@echo "代码行数: $(shell find src/ -name '*.py' -exec wc -l {} + | tail -1 | awk '{print $$1}')"
