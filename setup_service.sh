#!/bin/bash

# 获取当前用户名和目录
USER=$(whoami)
DIR=$(pwd)
SERVICE_FILE="okx-bot.service"

# 生成 systemd 配置文件
cat > $SERVICE_FILE << EOL
[Unit]
Description=OKX Trading Bot (Auto-Generated Service)
After=network.target

[Service]
User=$USER
WorkingDirectory=$DIR
ExecStart=$DIR/venv/bin/python main.py
Restart=always
RestartSec=5
# 确保日志实时输出
Environment=PYTHONUNBUFFERED=1
# 加载 .env 环境变量
EnvironmentFile=$DIR/.env

[Install]
WantedBy=multi-user.target
EOL

echo "✅ === 自动生成服务文件: $SERVICE_FILE ==="
echo "   运行账户: $USER"
echo "   工作目录: $DIR"
echo "   启动命令: $DIR/venv/bin/python main.py"
echo ""

# 使用说明
echo "👉 后续步骤 (需要 sudo 权限):"
echo "   1. 移动文件:  sudo mv $SERVICE_FILE /etc/systemd/system/"
echo "   2. 重载配置:  sudo systemctl daemon-reload"
echo "   3. 启动服务:  sudo systemctl enable --now okx-bot"
echo "   4. 查看日志:  journalctl -u okx-bot -f"
echo ""
echo "⚠️  注意: 如果无法移动文件，请手动复制上述 $SERVICE_FILE 内容到 /etc/systemd/system/okx-bot.service"
