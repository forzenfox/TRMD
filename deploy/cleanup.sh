#!/bin/bash
set -e

# ============================================================
# TRMD 一键清理脚本
# 用法:
#   ./cleanup.sh              # 默认清理（保留 sessions/downloads/数据库）
#   ./cleanup.sh --purge-data # 清理数据库
#   ./cleanup.sh --purge-all  # 清理所有数据
# ============================================================

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

PURGE_DATA=false
PURGE_ALL=false

for arg in "$@"; do
    case $arg in
        --purge-data) PURGE_DATA=true ;;
        --purge-all)  PURGE_ALL=true  ;;
        *)
            echo "未知参数: $arg"
            echo "用法: ./cleanup.sh [--purge-data|--purge-all]"
            exit 1
            ;;
    esac
done

# 确认提示
echo ""
warn "即将清理 TRMD 部署资源..."
echo "  默认清理: 容器实例 / temp/ / form/ / logs/"
if [ "$PURGE_DATA" = true ] || [ "$PURGE_ALL" = true ]; then
    echo "  数据库:    data/.trmd/（将被清理）"
fi
if [ "$PURGE_ALL" = true ]; then
    echo "  sessions/: 将被清理（需重新登录 Telegram）"
    echo "  downloads/: 将被清理"
fi
echo ""
read -p "是否继续？(y/N): " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    info "已取消"
    exit 0
fi

# 1. 停止并移除容器
info "停止并移除容器实例..."
docker compose down 2>/dev/null || true

# 2. 清理临时文件（默认清理）
info "清理 temp/..."
rm -rf temp/* temp/.* 2>/dev/null || true

info "清理 form/..."
rm -rf form/* form/.* 2>/dev/null || true

info "清理 logs/..."
rm -rf logs/* logs/.* 2>/dev/null || true

# 3. 清理数据库（可选）
if [ "$PURGE_DATA" = true ] || [ "$PURGE_ALL" = true ]; then
    info "清理 data/.trmd/（数据库）..."
    rm -rf data/.trmd/* data/.trmd/.* 2>/dev/null || true
fi

# 4. 清理所有数据（可选）
if [ "$PURGE_ALL" = true ]; then
    info "清理 sessions/（需重新登录 Telegram）..."
    rm -rf sessions/* sessions/.* 2>/dev/null || true
    info "清理 downloads/..."
    rm -rf downloads/* downloads/.* 2>/dev/null || true
fi

info "清理完成！"
echo "  如需重新部署，请执行: ./deploy.sh"