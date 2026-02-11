# 极速部署指南 (傻瓜式)

既然您已准备好环境和代码，只需按照以下步骤操作即可在云服务器上一键跑起来。

我们为您准备了自动化脚本，无需手动折腾复杂配置。

## 📁 第一步：上传代码

确保您的项目文件夹完整上传到了服务器（如 `/root/okx-bot` 或 `/home/ubuntu/okx-bot`）。
进入项目目录：

```bash
cd okx-bot
```

## 🛠️ 第二步：一键初始化 (deploy.sh)

直接运行我们提供的部署脚本。它会自动为您：

1. 创建 Python 虚拟环境 (venv)
2. 安装所有依赖库 (pip)
3. 编译前端页面 (npm build)
4. 生成 `.env` 配置文件模板

```bash
bash deploy.sh
```

**运行完毕后：**
请务必编辑生成的 `.env` 文件，填入您的 API Key 和后台管理员密码：

```bash
nano .env
# Ctrl+O 保存，Ctrl+X 退出
```

## ▶️ 第三步：启动运行 (start.sh)

### 方式 A：临时运行 (测试用)

直接运行启动脚本，查看是否有报错：

```bash
bash start.sh
# 按 Ctrl+C 停止
```

如果看到 `Web服务已启动: http://0.0.0.0:58181`，说明一切正常。

### 方式 B：后台运行 (推荐 - Systemd自动管理)

为了让机器人开机自启、掉线自动重启，请使用我们生成的服务配置脚本：

1. **生成服务文件**:

   ```bash
   bash setup_service.sh
   ```

   它会在当前目录生成一个 `okx-bot.service` 文件，内容已自动填好了您的路径和用户。

2. **安装并启动服务** (需要 sudo 权限):

   ```bash
   # 移动服务文件到系统目录
   sudo mv okx-bot.service /etc/systemd/system/

   # 重载并启动
   sudo systemctl daemon-reload
   sudo systemctl enable --now okx-bot
   ```

3. **查看运行状态**:

   ```bash
   # 查看状态
   sudo systemctl status okx-bot

   # 查看实时日志
   journalctl -u okx-bot -f
   ```

### 方式 C：简单后台运行 (Screen/Nohup)

如果您嫌 Systemd 麻烦，或者是普通用户没有 sudo 权限，可以使用 screen：

```bash
screen -S bot
bash start.sh
# 按 Ctrl+A 然后按 D 退出（挂起）
# 重新进入查看: screen -r bot
```

---

## 常见问题

**Q: 脚本提示 `npm not found`?**
A: 说明服务器没装 Node.js。

- 如果您在本地电脑已经运行过 `npm run build`，那么只需要把生成的 `frontend/dist` 文件夹上传到服务器即可，服务器不需要安装 Node.js，脚本会自动跳过构建步骤。
- 如果必须在服务器构建，请运行: `curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash - && sudo apt install -y nodejs`

**Q: 端口访问不通?**
A: 请检查云服务器的安全组规则，放行 TCP 端口 **58181**。
