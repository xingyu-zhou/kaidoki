#!/bin/bash

# Mercari AI Agent 部署脚本
# 该脚本用于自动化部署Mercari AI Agent系统

set -e  # 遇到错误时退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

# 配置变量
DEPLOY_DIR="/opt/mercari-ai-agent"
SERVICE_NAME="mercari-ai-agent"
PYTHON_VERSION="3.8"
VENV_NAME="venv"

# 解析命令行参数
ENVIRONMENT="production"
CONFIG_FILE=""
SKIP_TESTS=false
SKIP_BACKUP=false
FORCE_DEPLOY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -c|--config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --skip-backup)
            SKIP_BACKUP=true
            shift
            ;;
        --force)
            FORCE_DEPLOY=true
            shift
            ;;
        -h|--help)
            echo "用法: $0 [选项]"
            echo "选项:"
            echo "  -e, --environment ENV  部署环境 (development/production)"
            echo "  -c, --config FILE      配置文件路径"
            echo "  --skip-tests           跳过测试"
            echo "  --skip-backup          跳过备份"
            echo "  --force                强制部署"
            echo "  -h, --help             显示帮助"
            exit 0
            ;;
        *)
            error "未知参数: $1"
            exit 1
            ;;
    esac
done

# 检查权限
check_permissions() {
    log "检查权限..."
    if [ "$EUID" -ne 0 ]; then
        error "请以root用户运行此脚本"
        exit 1
    fi
}

# 检查系统要求
check_requirements() {
    log "检查系统要求..."
    
    # 检查Python版本
    if ! command -v python3 &> /dev/null; then
        error "Python 3 未安装"
        exit 1
    fi
    
    # 检查pip
    if ! command -v pip3 &> /dev/null; then
        error "pip3 未安装"
        exit 1
    fi
    
    # 检查git
    if ! command -v git &> /dev/null; then
        error "git 未安装"
        exit 1
    fi
    
    # 检查systemd
    if ! command -v systemctl &> /dev/null; then
        error "systemd 未安装"
        exit 1
    fi
}

# 创建系统用户
create_user() {
    log "创建系统用户..."
    
    if ! id "$SERVICE_NAME" &>/dev/null; then
        useradd -r -s /bin/false -d "$DEPLOY_DIR" "$SERVICE_NAME"
        log "用户 $SERVICE_NAME 创建成功"
    else
        log "用户 $SERVICE_NAME 已存在"
    fi
}

# 创建目录结构
create_directories() {
    log "创建目录结构..."
    
    mkdir -p "$DEPLOY_DIR"
    mkdir -p "$DEPLOY_DIR/logs"
    mkdir -p "$DEPLOY_DIR/data"
    mkdir -p "$DEPLOY_DIR/cache"
    mkdir -p "$DEPLOY_DIR/config"
    mkdir -p /var/log/mercari-ai-agent
    
    chown -R "$SERVICE_NAME:$SERVICE_NAME" "$DEPLOY_DIR"
    chown -R "$SERVICE_NAME:$SERVICE_NAME" /var/log/mercari-ai-agent
}

# 备份现有部署
backup_existing() {
    if [ "$SKIP_BACKUP" = true ]; then
        log "跳过备份"
        return
    fi
    
    log "备份现有部署..."
    
    if [ -d "$DEPLOY_DIR/src" ]; then
        BACKUP_DIR="/opt/mercari-ai-agent-backup-$(date +%Y%m%d_%H%M%S)"
        cp -r "$DEPLOY_DIR" "$BACKUP_DIR"
        log "备份完成: $BACKUP_DIR"
    fi
}

# 停止现有服务
stop_service() {
    log "停止现有服务..."
    
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        systemctl stop "$SERVICE_NAME"
        log "服务 $SERVICE_NAME 已停止"
    else
        log "服务 $SERVICE_NAME 未运行"
    fi
}

# 部署代码
deploy_code() {
    log "部署代码..."
    
    # 复制代码到部署目录
    cp -r . "$DEPLOY_DIR/src/"
    
    # 设置权限
    chown -R "$SERVICE_NAME:$SERVICE_NAME" "$DEPLOY_DIR/src"
    
    # 创建虚拟环境
    cd "$DEPLOY_DIR"
    python3 -m venv "$VENV_NAME"
    chown -R "$SERVICE_NAME:$SERVICE_NAME" "$VENV_NAME"
    
    # 激活虚拟环境并安装依赖
    source "$VENV_NAME/bin/activate"
    pip install --upgrade pip
    pip install -r src/requirements.txt
    
    log "代码部署完成"
}

# 配置系统
configure_system() {
    log "配置系统..."
    
    # 复制配置文件
    if [ -n "$CONFIG_FILE" ]; then
        cp "$CONFIG_FILE" "$DEPLOY_DIR/config/config.yaml"
    else
        cp "config/${ENVIRONMENT}.yaml" "$DEPLOY_DIR/config/config.yaml"
    fi
    
    # 设置环境变量
    if [ -f "config/.env" ]; then
        cp "config/.env" "$DEPLOY_DIR/config/.env"
    fi
    
    # 创建systemd服务文件
    cat > /etc/systemd/system/"$SERVICE_NAME".service << EOF
[Unit]
Description=Mercari AI Agent
After=network.target

[Service]
Type=simple
User=$SERVICE_NAME
Group=$SERVICE_NAME
WorkingDirectory=$DEPLOY_DIR/src
Environment=PATH=$DEPLOY_DIR/$VENV_NAME/bin
ExecStart=$DEPLOY_DIR/$VENV_NAME/bin/python -m mercari_agent.main serve --config $DEPLOY_DIR/config/config.yaml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    # 重新加载systemd
    systemctl daemon-reload
    
    log "系统配置完成"
}

# 运行测试
run_tests() {
    if [ "$SKIP_TESTS" = true ]; then
        log "跳过测试"
        return
    fi
    
    log "运行测试..."
    
    cd "$DEPLOY_DIR/src"
    source "../$VENV_NAME/bin/activate"
    
    # 安装测试依赖
    pip install -r requirements-dev.txt
    
    # 运行单元测试
    python run_tests.py --unit
    
    if [ $? -ne 0 ]; then
        error "测试失败"
        exit 1
    fi
    
    log "测试通过"
}

# 启动服务
start_service() {
    log "启动服务..."
    
    systemctl enable "$SERVICE_NAME"
    systemctl start "$SERVICE_NAME"
    
    # 等待服务启动
    sleep 5
    
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log "服务 $SERVICE_NAME 启动成功"
    else
        error "服务 $SERVICE_NAME 启动失败"
        systemctl status "$SERVICE_NAME"
        exit 1
    fi
}

# 健康检查
health_check() {
    log "执行健康检查..."
    
    # 等待服务完全启动
    sleep 10
    
    # 检查服务状态
    if ! systemctl is-active --quiet "$SERVICE_NAME"; then
        error "服务未运行"
        exit 1
    fi
    
    # 检查API端点
    if command -v curl &> /dev/null; then
        if curl -f http://localhost:8000/health &> /dev/null; then
            log "健康检查通过"
        else
            error "健康检查失败"
            exit 1
        fi
    else
        warn "curl 未安装，跳过API健康检查"
    fi
}

# 安装nginx反向代理
install_nginx() {
    log "安装nginx反向代理..."
    
    # 安装nginx
    if ! command -v nginx &> /dev/null; then
        if command -v apt-get &> /dev/null; then
            apt-get update
            apt-get install -y nginx
        elif command -v yum &> /dev/null; then
            yum install -y nginx
        else
            warn "无法自动安装nginx，请手动安装"
            return
        fi
    fi
    
    # 创建nginx配置
    cat > /etc/nginx/sites-available/mercari-ai-agent << EOF
server {
    listen 80;
    server_name localhost;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
    
    # 启用配置
    ln -sf /etc/nginx/sites-available/mercari-ai-agent /etc/nginx/sites-enabled/
    
    # 重启nginx
    systemctl restart nginx
    systemctl enable nginx
    
    log "nginx配置完成"
}

# 清理函数
cleanup() {
    log "清理临时文件..."
    # 清理临时文件
}

# 主部署流程
main() {
    log "开始部署 Mercari AI Agent..."
    log "环境: $ENVIRONMENT"
    
    # 检查是否强制部署
    if [ "$FORCE_DEPLOY" = false ]; then
        read -p "确定要部署到 $ENVIRONMENT 环境吗？ (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log "部署取消"
            exit 0
        fi
    fi
    
    # 执行部署步骤
    check_permissions
    check_requirements
    create_user
    create_directories
    backup_existing
    stop_service
    deploy_code
    configure_system
    run_tests
    start_service
    health_check
    
    # 如果是生产环境，安装nginx
    if [ "$ENVIRONMENT" = "production" ]; then
        install_nginx
    fi
    
    log "部署完成！"
    log "服务状态: $(systemctl is-active $SERVICE_NAME)"
    log "访问地址: http://localhost"
    log "日志文件: /var/log/mercari-ai-agent/"
    
    # 显示服务信息
    echo
    echo "=== 服务信息 ==="
    systemctl status "$SERVICE_NAME" --no-pager
    
    echo
    echo "=== 常用命令 ==="
    echo "查看日志: journalctl -u $SERVICE_NAME -f"
    echo "重启服务: systemctl restart $SERVICE_NAME"
    echo "停止服务: systemctl stop $SERVICE_NAME"
    echo "启动服务: systemctl start $SERVICE_NAME"
}

# 设置陷阱函数
trap cleanup EXIT

# 运行主函数
main "$@"