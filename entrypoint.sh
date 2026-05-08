#!/bin/bash
set -e

# 首次启动时初始化数据库并迁移旧配置
python main.py --migrate-config || true

# 启动服务
exec python main.py
