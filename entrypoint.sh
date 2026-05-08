#!/bin/bash
set -e

# 首次启动时初始化数据库并迁移旧配置
python main.py --migrate-config || true

# 判断是否生产环境（Render 会设置 PORT 环境变量）
if [ -n "$PORT" ]; then
    echo "生产模式: 使用 gunicorn"
    exec gunicorn web.app:app \
        --bind 0.0.0.0:$PORT \
        --workers 2 \
        --threads 2 \
        --timeout 120 \
        --access-logfile - \
        --error-logfile -
else
    echo "开发模式: 使用 Flask dev server"
    exec python main.py
fi
