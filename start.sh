#!/bin/bash
# 自动启动脚本
# 检查是否在 venv 环境中
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -d "venv" ]; then
        source venv/bin/activate
    else
        echo "⚠️ 未找到虚拟环境 venv，尝试直接运行 python3..."
    fi
fi

echo "🚀 Starting OKX Bot..."
exec python main.py
