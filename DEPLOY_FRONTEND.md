# 前端部署指南

你的前端控制面板已经开发完成。由于你的 Bot 运行在云服务器上，需要执行以下步骤来启用。

## 1. 编译前端 (在云服务器上)

假设你的项目路径是 `/www/wwwroot/trading/okx-bot`：

```bash
# 1. 进入前端目录
cd /www/wwwroot/trading/okx-bot/frontend

# 2. 安装依赖 (如果还没装)
npm install

# 3. 构建生产环境代码
npm run build
```

构建完成后，会生成 `dist` 目录：`/www/wwwroot/trading/okx-bot/frontend/dist`。

---

## 2. 配置 Nginx

修改 Nginx 配置，让它同时代理前端页面和后端 API。

**推荐配置：**

```nginx
server {
    listen 80;
    server_name your_server_ip_or_domain;

    # 1. 前端页面 (访问 /)
    location / {
        root /www/wwwroot/trading/okx-bot/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # 2. 后端 API (访问 /api/)
    location /api/ {
        proxy_pass http://127.0.0.1:58181;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # 增加超时时间以支持回测
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }
}
```

修改后记得重载 Nginx：`nginx -s reload`

---

## 3. 重启 Bot

为了让 API 生效，需要重启 Bot 服务（使用 python3）：

1.  找到正在运行的进程：`ps -ef | grep python`
2.  杀掉进程：`kill -9 <PID>`
3.  重新启动:
    ```bash
    cd /www/wwwroot/trading/okx-bot
    nohup python3 main.py > trading_system.log 2>&1 &
    ```

---

## 4. 访问控制面板

直接访问服务器 IP：`http://your_server_ip/`

默认用户名密码由环境变量 `WEB_USER` 和 `WEB_PASSWORD` 控制。
如果没设置，可能不需要密码。
可以在 `.env` 文件中添加：

```ini
WEB_USER=admin
WEB_PASSWORD=your_secure_password
```
