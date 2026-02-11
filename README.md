# OKX 自动化交易系统

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![OKX](https://img.shields.io/badge/Exchange-OKX-green.svg)](https://okx.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

一个基于 OKX 交易所的自动化交易系统，支持 **网格策略** 和 **MA 双均线趋势策略**，内置 Web 控制面板。

## ✨ 功能特性

- 🔄 **双策略支持** - 网格交易 + MA 双均线趋势策略，一键切换
- 🌐 **Web 控制面板** - 在浏览器中启动、暂停、停止策略，实时监控
- 🖥️ **终端 CLI 支持** - 也可直接通过命令行指定并启动策略
- 📊 **动态参数调节** - 通过前端实时修改策略参数，无需重启
- 🛡️ **多层风控机制** - 仓位限制、回撤保护、底仓保护
- 📈 **回测引擎** - 内置 MA 策略回测，验证参数效果
- 📱 **消息推送** - 支持 PushPlus / Bark 交易通知

---

## 📁 项目结构

```
okx-bot/
├── main.py                   # 主入口 (CLI + Web服务)
├── requirements.txt          # Python 依赖
├── .env                      # 环境变量配置
├── data/                     # 交易数据 & 回测数据
├── logs/                     # 日志目录
├── frontend/                 # React 前端控制面板
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx # 仪表盘 (策略启停控制)
│   │   │   ├── Parameters.jsx# 参数调节 (双策略 Tab)
│   │   │   ├── Backtest.jsx  # 回测页面
│   │   │   └── Logs.jsx      # 实时日志
│   │   ├── api.js            # API 封装
│   │   └── App.jsx           # 路由与布局
│   └── dist/                 # 构建产物 (Nginx 部署用)
└── src/                      # Python 后端
    ├── config/
    │   ├── settings.py       # 配置类 (TradingConfig, MAConfig)
    │   └── constants.py      # 全局常量
    ├── core/
    │   ├── bot_manager.py    # 策略管理器 (BotManager)
    │   ├── trade.py          # 网格交易器 (GridTrader)
    │   └── ma_trade.py       # MA 趋势交易器 (MATrader)
    ├── strategies/           # 策略逻辑
    ├── indicators/           # 技术指标
    ├── risk/                 # 风控模块
    ├── web/
    │   └── server.py         # Web API 服务器
    ├── backtest/             # 回测引擎
    └── services/             # 交易所、通知等服务
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
# 后端
pip install -r requirements.txt

# 前端 (如果需要修改 UI)
cd frontend && npm install
```

### 2. 配置环境变量

复制 `env.example` 为 `.env` 并填写：

```ini
# ── 交易所 API ──
OKX_API_KEY=your_api_key
OKX_SECRET_KEY=your_secret_key
OKX_PASSPHRASE=your_passphrase

# 模拟盘 API (FLAG=1 时使用)
OKX_DEMO_API_KEY=your_demo_api_key
OKX_DEMO_SECRET_KEY=your_demo_secret_key
OKX_DEMO_PASSPHRASE=your_demo_passphrase

# ── 交易配置 ──
SYMBOL=OKB/USDT
FLAG=1                    # 0=实盘, 1=模拟盘
STRATEGY_MODE=grid        # 默认策略 (grid / ma)

# ── 通知 (可选) ──
PUSHPLUS_TOKEN=your_token
BARK_KEY=your_key

# ── Web 面板认证 (可选) ──
WEB_USER=admin
WEB_PASSWORD=your_password
```

### 3. 启动系统

有两种使用方式：

#### 方式一：仅启动 Web 服务（推荐）

```bash
python main.py
```

启动后访问 http://localhost:58181，在前端 Dashboard 选择策略并启动。

#### 方式二：终端直接启动策略

```bash
# 启动网格策略
python main.py --strategy grid

# 启动 MA 趋势策略
python main.py --strategy ma

# 指定端口
python main.py --strategy grid --port 8080
```

> 终端模式下 Web 面板同样可用，可以在浏览器中暂停/停止策略。

### 4. 前端开发

```bash
cd frontend
npm run dev       # 开发模式 (热重载)
npm run build     # 构建生产版本到 dist/
```

---

## 📊 策略说明

### 网格策略 (Grid)

根据价格波动在预设价格网格内自动买卖，适合震荡行情。

| 参数           | 说明               | 可调范围      |
| -------------- | ------------------ | ------------- |
| 初始网格百分比 | 买卖触发的价格间距 | 0.1% – 4.0%   |
| 最小/最大网格  | 波动率自适应范围   | 0.5% – 8.0%   |
| 基础下单量     | 每格交易金额       | 10 – 500 USDT |
| 交易冷却时间   | 同向交易最小间隔   | 10 – 300 秒   |
| 波动率窗口     | 波动率回看周期     | 6 – 48 小时   |

### MA 双均线趋势策略

基于布林带挤压突破 + 多周期均线确认，适合趋势行情。

| 参数          | 说明            | 可调范围  |
| ------------- | --------------- | --------- |
| 挤压百分位    | 布林带挤压阈值  | 5 – 50    |
| 突破确认K线数 | K线连续突破确认 | 1 – 5 根  |
| ATR 倍数      | 止损距离乘数    | 0.5× – 4× |
| 盈亏比        | 止盈/止损比     | 1:1 – 8:1 |
| 最大杠杆      | 杠杆上限        | 1× – 100× |

---

## 🌐 Web 控制面板

访问地址：http://localhost:58181

### 功能页面

| 页面         | 功能                                   |
| ------------ | -------------------------------------- |
| **仪表盘**   | 选择策略、一键启停、实时余额/盈亏/持仓 |
| **参数调节** | 双策略 Tab 切换、滑块调参、预设方案    |
| **回测**     | MA 策略历史回测、收益/回撤/胜率分析    |
| **日志**     | 实时系统日志、按级别筛选               |

### API 端点

| 端点                   | 方法     | 说明                       |
| ---------------------- | -------- | -------------------------- |
| `/api/status`          | GET      | 获取系统状态               |
| `/api/config`          | GET/POST | 获取/修改策略参数          |
| `/api/strategy/start`  | POST     | 启动策略 `{"mode":"grid"}` |
| `/api/strategy/stop`   | POST     | 停止策略                   |
| `/api/strategy/pause`  | POST     | 暂停策略                   |
| `/api/strategy/resume` | POST     | 恢复策略                   |
| `/api/log`             | GET      | 获取日志                   |
| `/api/backtest`        | POST     | 运行回测                   |

---

## 🛡️ 风控机制

1. **仓位限制** - 自动限制最大/最小仓位比例
2. **回撤保护** - 超过最大回撤时暂停交易
3. **底仓保护** - 确保维持最低持仓比例
4. **订单限流** - 防止短时间内频繁下单
5. **日亏损限制** - 单日亏损超限自动停止

---

## 📱 消息通知

### PushPlus

在 `.env` 中配置 `PUSHPLUS_TOKEN`，系统会在交易执行、错误发生时自动推送。

### Bark (iOS)

1. App Store 下载 [Bark](https://apps.apple.com/app/id1403753865)
2. `.env` 中配置 `BARK_KEY`

---

## ⚠️ 风险提示

> **警告**: 加密货币交易存在高风险。使用本系统前，请确保您：
>
> - 了解网格交易和趋势交易的原理与风险
> - 仅使用可承受损失的资金
> - 先在模拟盘 (`FLAG=1`) 充分测试
> - 持续监控系统运行状态

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件
