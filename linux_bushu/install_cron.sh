#!/bin/bash

# Cron 定时任务安装脚本
# 设置每天早上8点自动执行小说下载任务

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置变量
PROJECT_DIR="/opt/feishu"
VENV_DIR="$PROJECT_DIR/venv"
PYTHON_BIN="$VENV_DIR/bin/python"
SCRIPT_NAME="cron_deployment.py"
LOG_DIR="/var/log/feishu"
CRON_LOG="$LOG_DIR/cron.log"

# 函数定义
print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}   飞书小说下载系统 - Cron 部署${NC}"
    echo -e "${BLUE}================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# 检查是否为 root 用户
check_root() {
    if [ "$EUID" -eq 0 ]; then
        print_warning "检测到 root 用户，建议使用普通用户运行此脚本"
        read -p "是否继续？(y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# 检查系统环境
check_system() {
    print_info "检查系统环境..."
    
    # 检查操作系统
    if [[ "$OSTYPE" != "linux-gnu"* ]]; then
        print_error "此脚本仅支持 Linux 系统"
        exit 1
    fi
    
    # 检查 Python3
    if ! command -v python3 &> /dev/null; then
        print_error "Python3 未安装，请先安装 Python3"
        exit 1
    fi
    
    # 检查 cron
    if ! command -v crontab &> /dev/null; then
        print_error "cron 未安装，请先安装 cron"
        exit 1
    fi
    
    print_success "系统环境检查通过"
}

# 创建项目目录和虚拟环境
setup_project() {
    print_info "设置项目环境..."
    
    # 创建项目目录
    if [ ! -d "$PROJECT_DIR" ]; then
        sudo mkdir -p "$PROJECT_DIR"
        sudo chown $USER:$USER "$PROJECT_DIR"
    fi
    
    # 复制文件到项目目录
    print_info "复制项目文件..."
    cp cron_deployment.py "$PROJECT_DIR/"
    cp database.py "$PROJECT_DIR/"
    cp feishu_api.py "$PROJECT_DIR/"
    cp config.py "$PROJECT_DIR/"
    cp requirements.txt "$PROJECT_DIR/"
    cp env_example.txt "$PROJECT_DIR/"
    
    print_success "已复制核心文件: cron_deployment.py, database.py, feishu_api.py, config.py"
    
    # 创建虚拟环境
    if [ ! -d "$VENV_DIR" ]; then
        print_info "创建 Python 虚拟环境..."
        cd "$PROJECT_DIR"
        python3 -m venv venv
    fi
    
    # 安装依赖
    print_info "安装 Python 依赖..."
    cd "$PROJECT_DIR"
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    
    print_success "项目环境设置完成"
}

# 创建必要目录
create_directories() {
    print_info "创建必要目录..."
    
    # 创建数据存储目录
    sudo mkdir -p /home/xiaoshuo
    sudo chmod 755 /home/xiaoshuo
    sudo chown $USER:$USER /home/xiaoshuo
    
    # 创建日志目录
    sudo mkdir -p "$LOG_DIR"
    sudo chmod 755 "$LOG_DIR"
    sudo chown $USER:$USER "$LOG_DIR"
    
    print_success "目录创建完成"
}

# 配置环境变量
setup_config() {
    print_info "配置环境变量..."
    
    cd "$PROJECT_DIR"
    
    if [ ! -f ".env" ]; then
        cp env_example.txt .env
        print_warning "已创建 .env 配置文件，请根据实际情况修改配置"
        print_info "配置文件位置: $PROJECT_DIR/.env"
        
        # 如果是本地 MySQL，自动设置为 localhost
        if systemctl is-active --quiet mysql || systemctl is-active --quiet mysqld; then
            sed -i 's/DB_HOST=115.190.39.113/DB_HOST=localhost/' .env
            print_info "检测到本地 MySQL，已自动设置 DB_HOST=localhost"
        fi
        
        print_warning "请编辑 .env 文件设置正确的数据库和API配置"
        echo ""
        echo "主要配置项："
        echo "  DB_HOST=your_mysql_host"
        echo "  DB_USER=your_mysql_user"
        echo "  DB_PASSWORD=your_mysql_password"
        echo "  FEISHU_APP_ID=your_feishu_app_id"
        echo "  FEISHU_APP_SECRET=your_feishu_app_secret"
        echo ""
        read -p "配置完成后按回车继续..."
    fi
    
    print_success "配置设置完成"
}

# 创建 Cron 任务
setup_cron() {
    print_info "设置 Cron 定时任务..."
    
    # 创建 cron 脚本
    CRON_SCRIPT="$PROJECT_DIR/run_daily.sh"
    
    cat > "$CRON_SCRIPT" << EOF
#!/bin/bash
# 每日定时执行脚本

# 设置环境变量
export PATH="/usr/local/bin:/usr/bin:/bin"
export LANG="en_US.UTF-8"

# 切换到项目目录
cd "$PROJECT_DIR"

# 激活虚拟环境并执行任务
source venv/bin/activate
python3 cron_deployment.py daily >> "$CRON_LOG" 2>&1

# 记录执行时间
echo "===========================================" >> "$CRON_LOG"
echo "Task completed at: \$(date)" >> "$CRON_LOG"
echo "===========================================" >> "$CRON_LOG"
EOF

    chmod +x "$CRON_SCRIPT"
    
    # 添加到 crontab
    print_info "添加到 crontab..."
    
    # 检查是否已存在相同的任务
    if crontab -l 2>/dev/null | grep -q "$CRON_SCRIPT"; then
        print_warning "Cron 任务已存在，跳过添加"
    else
        # 备份现有的 crontab
        crontab -l 2>/dev/null > /tmp/crontab_backup
        
        # 添加新任务（每天早上8点执行）
        echo "0 8 * * * $CRON_SCRIPT" >> /tmp/crontab_backup
        
        # 安装新的 crontab
        crontab /tmp/crontab_backup
        
        print_success "Cron 任务添加成功"
        print_info "任务将在每天早上8:00执行"
    fi
    
    # 显示当前的 crontab
    print_info "当前的 Cron 任务："
    crontab -l | grep -E "(feishu|$CRON_SCRIPT)" || print_warning "未找到相关任务"
}

# 测试运行
test_run() {
    print_info "执行测试运行..."
    
    cd "$PROJECT_DIR"
    source venv/bin/activate
    
    # 测试飞书数据拉取
    print_info "测试飞书数据拉取..."
    python3 cron_deployment.py fetch
    
    if [ $? -eq 0 ]; then
        print_success "飞书数据拉取测试通过"
    else
        print_warning "飞书数据拉取测试失败（将使用测试数据）"
    fi
    
    # 测试数据同步
    print_info "测试数据同步..."
    python3 cron_deployment.py sync
    
    if [ $? -eq 0 ]; then
        print_success "数据同步测试通过"
    else
        print_error "数据同步测试失败"
        return 1
    fi
    
    # 测试文件下载
    print_info "测试文件下载..."
    python3 cron_deployment.py download
    
    if [ $? -eq 0 ]; then
        print_success "文件下载测试通过"
    else
        print_warning "文件下载测试失败（可能是没有待下载文件）"
    fi
    
    print_success "测试运行完成"
}

# 显示部署信息
show_deployment_info() {
    print_success "部署完成！"
    echo ""
    echo "项目信息："
    echo "  项目目录: $PROJECT_DIR"
    echo "  下载目录: /home/xiaoshuo"
    echo "  日志目录: $LOG_DIR"
    echo "  配置文件: $PROJECT_DIR/.env"
    echo ""
    echo "定时任务："
    echo "  执行时间: 每天早上 8:00"
    echo "  执行脚本: $PROJECT_DIR/run_daily.sh"
    echo "  日志文件: $CRON_LOG"
    echo ""
    echo "手动操作："
    echo "  查看日志: tail -f $CRON_LOG"
    echo "  手动执行: cd $PROJECT_DIR && source venv/bin/activate && python3 cron_deployment.py daily"
    echo "  查看任务: crontab -l"
    echo "  编辑任务: crontab -e"
    echo ""
    echo "监控命令："
    echo "  查看下载文件: ls -la /home/xiaoshuo/"
    echo "  查看今日日志: grep \"\$(date +%Y-%m-%d)\" $CRON_LOG"
    echo "  查看错误日志: grep -i error $CRON_LOG"
}

# 主函数
main() {
    print_header
    
    # 检查环境
    check_root
    check_system
    
    # 设置项目
    setup_project
    create_directories
    setup_config
    
    # 设置定时任务
    setup_cron
    
    # 测试运行
    if [ "$1" != "--skip-test" ]; then
        test_run
    fi
    
    # 显示部署信息
    show_deployment_info
}

# 运行主函数
main "$@" 