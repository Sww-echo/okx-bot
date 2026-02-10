# OKX 网格交易机器人

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![OKX](https://img.shields.io/badge/Exchange-OKX-green.svg)](https://okx.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

一个基于 OKX 交易所的自动化网格交易机器人，支持实盘和模拟盘交易。

## ✨ 功能特性

- 🔄 **自动网格交易** - 根据价格波动自动执行买卖操作
- 📊 **动态网格调整** - 根据市场波动率自动调整网格大小
- 🛡️ **多层风控机制** - 仓位限制、回撤保护、底仓保护
- 📈 **S1 仓位策略** - 基于每日高低点的仓位调整策略
- 🌐 **Web 监控界面** - 实时查看交易状态和系统日志
- 📱 **消息推送** - 支持 PushPlus 交易通知

## 📁 项目结构

```
okx-grid-bot/
├── main.py                 # 主入口文件
├── config.py               # 配置兼容层
├── helpers.py              # 辅助函数兼容层
├── requirements.txt        # 依赖列表
├── .env                    # 环境变量配置
├── data/                   # 数据存储目录
│   └── trade_history.json  # 交易历史记录
├── logs/                   # 日志目录
└── src/                    # 核心源码
    ├── config/             # 配置模块
    │   ├── settings.py     # 配置类定义
    │   └── constants.py    # 全局常量
    ├── core/               # 核心交易模块
    │   ├── trade.py        # 网格交易器主类
    │   └── order.py        # 订单管理器
    ├── services/           # 服务模块
    │   ├── exchange.py     # OKX 交易所客户端
    │   ├── balance.py      # 余额管理服务
    │   ├── notification.py # 消息通知服务
    │   └── persistence.py  # 数据持久化服务
    ├── strategies/         # 策略模块
    │   ├── grid.py         # 网格策略
    │   └── position.py     # S1 仓位策略
    ├── indicators/         # 技术指标
    │   ├── volatility.py   # 波动率指标
    │   ├── trend.py        # 趋势指标
    │   └── price.py        # 价格指标
    ├── risk/               # 风控模块
    │   └── manager.py      # 风险管理器
    ├── web/                # Web 服务
    │   └── server.py       # 监控页面服务器
    └── utils/              # 工具模块
        ├── logging.py      # 日志配置
        ├── decorators.py   # 装饰器
        └── formatters.py   # 格式化工具
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `env.example` 为 `.env` 并填写您的配置：

```bash
cp env.example .env
```

编辑 `.env` 文件：

```env
# 实盘 API (FLAG=0 时使用)
OKX_API_KEY=your_api_key
OKX_SECRET_KEY=your_secret_key
OKX_PASSPHRASE=your_passphrase

# 模拟盘 API (FLAG=1 时使用)
OKX_DEMO_API_KEY=your_demo_api_key
OKX_DEMO_SECRET_KEY=your_demo_secret_key
OKX_DEMO_PASSPHRASE=your_demo_passphrase

# 通知配置 (可选)
PUSHPLUS_TOKEN=your_pushplus_token

# 交易配置
INITIAL_BASE_PRICE=600.0
INITIAL_PRINCIPAL=1000.0
```

### 3. 运行机器人

```bash
python main.py
```

### 4. 访问监控页面

打开浏览器访问：http://localhost:58181

## ⚙️ 配置说明

### 交易模式切换

在 `src/config/constants.py` 中修改 `FLAG`：

```python
FLAG = '0'  # 实盘模式
FLAG = '1'  # 模拟盘模式
```

### 网格参数

在 `src/config/settings.py` 中的 `TradingConfig` 类：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `INITIAL_GRID` | 初始网格大小 (%) | 2.0 |
| `MIN_TRADE_AMOUNT` | 最小交易金额 (USDT) | 20.0 |
| `MAX_POSITION_PERCENT` | 最大仓位比例 | 90% |
| `MIN_POSITION_PERCENT` | 最小底仓比例 | 10% |

### 风控参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `MAX_DRAWDOWN` | 最大回撤限制 | 15% |
| `DAILY_LOSS_LIMIT` | 单日最大亏损 | 5% |

## 📊 网格交易逻辑

```
基准价 ──────────────────────────────────
         │
         │←── 网格大小 (例如 2%)
         │
卖出触发 ─┼───────────────────── 价格上涨 ≥ 网格大小 → 卖出
         │
基准价 ──┼──────────────────────────────
         │
买入触发 ─┼───────────────────── 价格下跌 ≥ 网格大小 → 买入
```

- **买入信号**: 当前价格相对基准价下跌超过网格大小时触发
- **卖出信号**: 当前价格相对基准价上涨超过网格大小时触发
- **基准价更新**: 每次交易后，基准价更新为成交价格

## 🛡️ 风控机制

1. **仓位限制** - 自动限制最大/最小仓位比例
2. **回撤保护** - 超过最大回撤时暂停交易
3. **底仓保护** - 确保维持最低持仓比例
4. **订单限流** - 防止短时间内频繁下单

## 📱 消息通知

支持通过 [PushPlus](https://www.pushplus.plus/) 发送交易通知：

1. 注册 PushPlus 账号获取 Token
2. 在 `.env` 文件中配置 `PUSHPLUS_TOKEN`
3. 系统会在交易执行、错误发生时自动推送通知

## 🔧 开发说明

### 添加新策略

1. 在 `src/strategies/` 目录下创建新的策略文件
2. 继承或参考 `GridStrategy` 类的接口
3. 在 `src/core/trade.py` 中集成新策略

### 添加新指标

1. 在 `src/indicators/` 目录下创建新的指标文件
2. 实现计算方法
3. 在需要的地方导入使用

## ⚠️ 风险提示

> **警告**: 加密货币交易存在高风险。使用本机器人前，请确保您：
> - 了解网格交易的原理和风险
> - 仅使用可承受损失的资金
> - 先在模拟盘充分测试
> - 持续监控机器人运行状态

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！
