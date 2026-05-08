#!/bin/bash
# ==============================================
# 盯盘助手 — Oracle Cloud 一键部署脚本
# 用法: sudo bash deploy.sh <你的域名>
# 例如: sudo bash deploy.sh stock.example.tk
# ==============================================
set -e

DOMAIN="${1:-}"
if [ -z "$DOMAIN" ]; then
    echo "❌ 请提供域名！"
    echo "用法: sudo bash deploy.sh <你的域名>"
    echo "例如: sudo bash deploy.sh stock.example.tk"
    exit 1
fi

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; }

# 检查 root
if [ "$EUID" -ne 0 ]; then
    err "请以 root 身份运行: sudo bash deploy.sh <域名>"
    exit 1
fi

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo ""
echo "========================================"
echo "  盯盘助手 — Oracle Cloud 部署"
echo "  域名: $DOMAIN"
echo "========================================"
echo ""

# --------------------------------------------------
# 步骤 1: 系统更新 + 基础依赖
# --------------------------------------------------
echo ""
warn "步骤 1/6: 安装系统依赖..."
apt-get update -qq
apt-get install -y -qq \
    curl wget git \
    nginx \
    certbot python3-certbot-nginx \
    ca-certificates gnupg lsb-release \
    ufw
log "系统依赖安装完成"

# --------------------------------------------------
# 步骤 2: 安装 Docker
# --------------------------------------------------
echo ""
warn "步骤 2/6: 安装 Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | bash
    systemctl enable docker
    systemctl start docker
    log "Docker 安装完成"
else
    log "Docker 已安装，跳过"
fi

# 安装 docker-compose 插件
if ! docker compose version &> /dev/null; then
    DOCKER_CONFIG=${DOCKER_CONFIG:-/usr/local/lib/docker/cli-plugins}
    mkdir -p "$DOCKER_CONFIG"
    curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
         -o "$DOCKER_CONFIG/docker-compose"
    chmod +x "$DOCKER_CONFIG/docker-compose"
    log "docker-compose 安装完成"
else
    log "docker-compose 已安装，跳过"
fi

# --------------------------------------------------
# 步骤 3: 配置防火墙
# --------------------------------------------------
echo ""
warn "步骤 3/6: 配置防火墙..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
log "防火墙配置完成（22/80/443 已开放）"

# --------------------------------------------------
# 步骤 4: 生成 JWT_SECRET + 配置环境变量
# --------------------------------------------------
echo ""
warn "步骤 4/6: 生成配置..."

# 生成随机 JWT_SECRET
JWT_SECRET=$(openssl rand -hex 32)
log "JWT_SECRET 已生成"

# 创建 .env 文件（供 docker-compose 读取）
cat > .env << EOF
JWT_SECRET=$JWT_SECRET
WECHAT_APPID=
WECHAT_SECRET=
EOF
chmod 600 .env
log ".env 文件已创建（请补充 WECHAT_APPID 和 WECHAT_SECRET）"

# --------------------------------------------------
# 步骤 5: 配置 Nginx + SSL
# --------------------------------------------------
echo ""
warn "步骤 5/6: 配置 Nginx + SSL 证书..."

# 生成 Nginx 配置
sed "s/DOMAIN_NAME/$DOMAIN/g" nginx/stock-monitor.conf > /etc/nginx/sites-available/stock-monitor
ln -sf /etc/nginx/sites-available/stock-monitor /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx
log "Nginx 配置完成"

# 获取 SSL 证书
echo ""
warn "正在申请 Let's Encrypt SSL 证书..."
warn "请确保域名 $DOMAIN 已解析到本机 IP！"
echo "按回车键继续..."
read -r

certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email || \
    certbot --nginx -d "$DOMAIN"

log "SSL 证书获取完成"

# 设置证书自动续期
(crontab -l 2>/dev/null; echo "0 3 * * * /usr/bin/certbot renew --quiet") | crontab -
log "SSL 自动续期已设置（每天凌晨 3 点检查）"

# --------------------------------------------------
# 步骤 6: 构建并启动 Docker
# --------------------------------------------------
echo ""
warn "步骤 6/6: 构建并启动 Docker 容器..."

# 停止旧容器
docker compose down 2>/dev/null || true

# 构建并启动
docker compose up -d --build
log "Docker 容器已启动"

# --------------------------------------------------
# 完成
# --------------------------------------------------
echo ""
echo "========================================"
echo -e "${GREEN}  部署完成！${NC}"
echo "========================================"
echo ""
echo "  服务地址: https://$DOMAIN"
echo "  健康检查: curl https://$DOMAIN/health"
echo "  查看日志: docker compose logs -f"
echo ""
echo "  ⚠ 还需完成以下配置:"
echo "  1. 编辑 .env 文件，填入微信小程序 appid/secret"
echo "     nano $PROJECT_DIR/.env"
echo "     然后重启: docker compose restart"
echo ""
echo "  2. 在 config/config.json 中配置大盘指数和调度时间"
echo ""
echo "  3. 在微信小程序后台设置 request 合法域名:"
echo "     https://$DOMAIN"
echo ""
