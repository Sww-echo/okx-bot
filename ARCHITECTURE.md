# OKX-Bot 系统架构文档

> 版本: 2.0.0 | 更新: 2026-03-22

---

## 一、系统总览

OKX-Bot 是一个基于 Python asyncio 的自动化加密货币交易系统，对接 OKX 交易所，支持**网格交易**和**双均线趋势**两种策略，同时提供 Web 控制面板和多渠道消息通知。

```
┌─────────────────────────────────────────────────────────────┐
│                        main.py                              │
│  (CLI 入口, asyncio 事件循环, 信号处理)                       │
└──────────┬──────────────────────────────┬───────────────────┘
           │                              │
     ┌─────▼─────┐                 ┌──────▼──────┐
     │ BotManager │                 │  WebServer  │
     │ (策略调度)  │◄───── API ────►│ (aiohttp)   │
     └─────┬──────┘                └─────────────┘
           │ 创建
     ┌─────┴──────────────┐
     │                    │
┌────▼─────┐       ┌─────▼─────┐
│GridTrader│       │ MATrader  │
│ (网格策略)│       │(双均线策略) │
└────┬─────┘       └─────┬─────┘
     │                    │
     ▼                    ▼
┌──────────────────────────────────────┐
│          共享服务层                    │
│  ExchangeClient | BalanceService     │
│  NotificationService | Persistence   │
│  RiskManager | OrderManager          │
└──────────────────────────────────────┘
```

---

## 二、启动流程

```
python main.py [--strategy grid|ma] [--port 58181]
```

```
1. 设置 Windows SelectorEventLoop (兼容性)
2. SSL 配置 (默认启用验证, DISABLE_SSL_VERIFY=1 可关闭)
3. 初始化日志 (TimedRotatingFileHandler, 保留2天)
4. 创建 TradingConfig → BotManager
5. 注册 SIGINT/SIGTERM 信号处理 → 优雅关闭
6. 启动 WebServer (aiohttp, 端口 58181)
7. 若 CLI 指定 --strategy → BotManager.start_strategy()
8. 主循环 while True: await asyncio.sleep(1)
```

---

## 三、BotManager — 策略生命周期管理

**文件**: `src/core/bot_manager.py`

统一管理 Grid / MA 两种策略的创建、初始化、启停。

| 状态 | 说明 |
|------|------|
| `idle` | 无策略运行 |
| `initializing` | 正在初始化（最多重试5次，间隔递增） |
| `running` | 策略主循环运行中 |
| `paused` | 策略暂停，主循环仍在但跳过交易 |

```
start_strategy(mode)
  ├── 若已有策略 → stop_strategy() 先停止
  ├── 创建 GridTrader 或 MATrader
  ├── trader.initialize() (重试5次, 3/6/9/12/15s)
  └── asyncio.create_task(trader.start())

stop_strategy()
  ├── trader.shutdown() (保存状态、通知、关闭连接)
  ├── task.cancel()
  └── 重置所有状态为 idle
```

---

## 四、策略一：网格交易 (GridTrader)

**文件**: `src/core/trade.py` + `src/strategies/grid.py`

### 4.1 核心原理

维护一个**基准价 (base_price)**，当市场价偏离基准价超过 **grid_size%** 时触发买/卖，成交后基准价更新为成交价。

```
基准价 1000, 网格 2%
  价格涨到 1020 (+2%) → 卖出 → 基准价更新为 1020
  价格跌到  998 (-2%) → 买入 → 基准价更新为 998
```

### 4.2 初始化

```
initialize()
  1. exchange.load_markets()         — 加载交易对信息
  2. exchange.sync_time()            — 同步服务器时间
  3. exchange.set_leverage()         — 合约模式设置杠杆
  4. 设置基准价:
     - INITIAL_BASE_PRICE > 0 → 使用配置值
     - 否则 → fetch_ticker() 获取当前价
  5. s1_strategy.update_daily_levels() — 获取52日高低点
  6. 发送启动通知
```

### 4.3 主循环 (每5秒一轮)

```
start() → while _running:
  │
  ├─ 1. 获取最新价格 fetch_ticker()
  │
  ├─ 2. 暂停检查: paused → sleep(5) 跳过
  │
  ├─ 3. 网格信号检查 _process_grid_signals()
  │     current_price vs base_price
  │     偏离 >= +grid_size% → 卖出信号
  │     偏离 <= -grid_size% → 买入信号
  │
  └─ 4. 无交易进行时的维护任务:
        a. 风控检查 → 触发则跳过本轮
        b. S1 Donchian 仓位调整
        c. 底仓不足自动补仓
        d. 每小时根据波动率调整网格大小
```

### 4.4 交易执行 (execute_grid_trade)

```
execute_grid_trade(side, price)     [带3次重试]
  │
  ├─ 1. 计算交易量
  │     amount_usdt = max(20, 总资产 × 5%)
  │     合约: amount_usdt / price → 张数
  │     现货: amount_usdt / price → 币数
  │
  ├─ 2. 余额检查
  │     合约: 保证金 = (数量×价格) / 杠杆
  │     现货买: 检查USDT (不足自动从理财赎回)
  │     现货卖: 检查币余额
  │
  ├─ 3. 限价下单 exchange.create_order()
  │
  ├─ 4. 记录 & 通知
  │     - 预估盈亏(卖出时) → risk_manager.record_trade_result()
  │     - order_manager.log_trade()
  │     - notifier.send_trade_notification()
  │
  └─ 5. 更新基准价 → base_price = 成交价
```

### 4.5 网格自适应

每小时根据波动率动态调整网格大小：

| 波动率区间 | 网格大小 |
|-----------|---------|
| 0% ~ 1% | 1.0% |
| 1% ~ 2% | 1.5% |
| 2% ~ 3% | 2.0% |
| 3% ~ 4% | 2.5% |
| 4% ~ 5% | 3.0% |
| 5% ~ 7% | 3.5% |
| 7%+ | 4.0% |

---

## 五、策略二：双均线趋势 (MATrader)

**文件**: `src/core/ma_trade.py` + `src/strategies/ma.py`

### 5.1 核心原理

基于 **6条均线** (MA20/60/120 + EMA20/60/120) 的状态机驱动策略，包含两个子策略。

### 5.2 状态机

```
          均线密集
IDLE ────────────► SQUEEZE
  ▲                   │
  │                   │ 排列确认
  │ 无序              ▼
  ├──────── TREND_LONG  (多头排列: 短>中>长)
  │
  └──────── TREND_SHORT (空头排列: 短<中<长)
```

### 5.3 子策略 A — 密集突破

触发条件：
1. 6线进入密集状态 (变异系数 < 阈值)
2. 记录密集区上沿 / 下沿
3. 价格突破密集区上沿 + BREAKOUT_THRESHOLD
4. 连续 N 根 K线确认 (BREAKOUT_BARS)
5. 成交量 > 均量 × 1.5 (可配置)

```
做多: 价格 > squeeze_high × (1 + threshold)
      止损 = squeeze_low (密集区下沿)

做空: 价格 < squeeze_low × (1 - threshold)
      止损 = squeeze_high (密集区上沿)
```

### 5.4 子策略 B — MA20 回踩

触发条件：
1. 趋势已确立 (TREND_LONG 或 TREND_SHORT)
2. 价格回踩 MA20 后收回
3. ADX > 25 (趋势强度过滤, 可配置)
4. MACD 方向一致 (可配置)

```
做多: low <= MA20 且 close >= MA20 (上涨回踩)
      止损 = MA20 - ATR × ATR_MULTIPLIER

做空: high >= MA20 且 close <= MA20 (下跌受阻)
      止损 = MA20 + ATR × ATR_MULTIPLIER
```

### 5.5 仓位计算

```
风险金额 = 总权益 × RISK_PER_TRADE (默认 2%)
数量 = 风险金额 / |开仓价 - 止损价|

杠杆检查: (数量 × 价格) / 总权益 <= MAX_LEVERAGE
```

### 5.6 持仓管理 (PositionTracker)

**文件**: `src/core/position_tracker.py`

- 按策略ID (A/B) 独立管理，最多同时持 2 个仓位
- 每轮检查止盈/止损/移动止损

**移动止损逻辑 (以多头为例):**

```
R = entry_price - initial_stop_loss  (1R = 初始风险距离)

盈利 >= 1R → 止损提到入场价 (保本)
盈利 >= 2R → 止损跟随推进:
  new_sl = entry + R × (profit_in_R - 1)
  上限: max_price - R × 0.5
```

### 5.7 主循环

```
start() → while _running:
  │
  ├─ 1. 获取最新价格
  │
  ├─ 2. 检查所有持仓退出条件
  │     position_tracker.update_price()
  │     触发 → exchange.close_position() → 通知
  │
  ├─ 3. 策略分析 strategy.analyze()
  │     产生信号 → 检查该策略是否已有持仓
  │     无持仓 → _execute_entry()
  │
  └─ 4. sleep(CHECK_INTERVAL)
```

---

## 六、S1 仓位控制策略

**文件**: `src/strategies/position.py`

辅助策略，基于 **52日 Donchian 通道**进行仓位再平衡：

```
价格突破 52日最高点 且 仓位 > 50% → 减仓到 50%
价格跌破 52日最低点 且 仓位 < 70% → 加仓到 70%
```

- 每 ~24小时更新一次高低点数据
- 通过回调函数 `executor` 执行市价单（由 GridTrader 注入）
- 仅在 GridTrader 中使用，MATrader 不使用

---

## 七、风控系统 (RiskManager)

**文件**: `src/risk/manager.py`

### 多层检查（每轮主循环执行）

```
multi_layer_check(current_price) → bool (True=触发风控,暂停交易)
  │
  ├─ 0. 连续亏损冷却检查
  │     连续 >= 5笔亏损 → 冷却 300秒
  │
  ├─ 1. 仓位比例检查
  │     < MIN_POSITION_RATIO (10%) → 底仓警告(不暂停)
  │     > MAX_POSITION_RATIO (90%) → 暂停交易
  │
  ├─ 2. 总资产回撤止损
  │     (peak - current) / peak >= 15% → 暂停交易
  │
  └─ 3. 每日亏损限制
        今日亏损 / 本金 >= 5% → 暂停交易
```

### 异常安全

风控检查异常时返回 `True`（保守立场，宁可暂停交易也不放过风险）。

---

## 八、服务层

### 8.1 ExchangeClient (OKX API 封装)

**文件**: `src/services/exchange.py`

- 封装 OKX SDK 全部操作：行情、下单、持仓、资金划转
- **所有 API 调用通过 `asyncio.to_thread()` 包装**，不阻塞事件循环
- 余额缓存 TTL: 0.2秒
- 自动区分模拟盘 / 实盘 API 密钥
- 合约信息自动加载（面值 ctVal、最小张数、步长）

### 8.2 BalanceService (余额管理)

**文件**: `src/services/balance.py`

| 方法 | 功能 |
|------|------|
| `get_available_balance(ccy)` | 获取可用余额 (× 0.95 安全边际) |
| `get_total_assets(price)` | 计算总资产 (USDT, 含理财和合约盈亏) |
| `get_position_ratio(price)` | 当前仓位 / 总资产 |
| `check_buy_balance(usdt)` | 检查USDT是否足够, 不足自动从理财赎回 |
| `check_sell_balance(amount)` | 检查币种余额, 不足自动赎回 |
| `transfer_excess_to_savings()` | 多余资金自动转入理财 |

### 8.3 NotificationService (通知推送)

**文件**: `src/services/notification.py`

- **全异步** (aiohttp ClientSession, 复用连接)
- 支持三个渠道并行推送：钉钉 / 企业微信 / Bark (iOS)
- 钉钉支持 HMAC-SHA256 签名鉴权
- 单例模式 `get_notification_service()`

### 8.4 PersistenceService (JSON 持久化)

**文件**: `src/services/persistence.py`

- 交易状态保存/恢复 (`data/state.json`)
- 交易历史保存 (`data/trade_history.json`)
- 历史归档（超过阈值自动归档旧记录）

### 8.5 OrderManager + OrderThrottler

**文件**: `src/core/order.py`

- `OrderThrottler`: 滑动窗口限流 (默认 60秒内最多10单)
- `OrderManager`: 交易记录、统计（胜率/盈亏比/连续胜负/盈亏因子）
- 内存保留最近100条，持久化存储

---

## 九、Web 服务

**文件**: `src/web/server.py`

aiohttp 服务，默认端口 58181，支持 Basic Auth。

### API 端点

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/login` | 登录 (返回 Basic Auth token) |
| GET | `/api/status` | 系统状态 (余额/持仓/盈亏/最近交易) |
| GET | `/api/config` | 获取当前策略参数 |
| POST | `/api/config` | 更新策略参数 (运行时生效) |
| GET | `/api/logs` | 最近200行日志 |
| POST | `/api/strategy/start` | 启动策略 `{mode: "grid"\|"ma"}` |
| POST | `/api/strategy/stop` | 停止策略 |
| POST | `/api/strategy/pause` | 暂停策略 |
| POST | `/api/strategy/resume` | 恢复策略 |
| POST | `/api/backtest` | 运行 MA 策略回测 |
| GET | `/api/backtest/results` | 获取回测结果 |

### 前端

React 19 SPA (Vite 构建), 页面:
- Dashboard (仪表盘)
- Parameters (参数配置)
- Logs (日志查看)
- Backtest (回测)
- Login (登录)

---

## 十、配置体系

### 10.1 环境变量 (.env)

```bash
# API 密钥
OKX_API_KEY=xxx                 # 实盘
OKX_SECRET_KEY=xxx
OKX_PASSPHRASE=xxx
OKX_DEMO_API_KEY=xxx            # 模拟盘 (FLAG=1 时优先使用)
OKX_DEMO_SECRET_KEY=xxx
OKX_DEMO_PASSPHRASE=xxx

# 交易配置
BASE_SYMBOL=ETH                 # 基础币种 (默认 OKB)
QUOTE_SYMBOL=USDT               # 计价币种
TRADE_MODE=swap                 # spot | swap
MARGIN_MODE=cross               # cross | isolated
POS_SIDE=net                    # net | long | short
LEVERAGE=5                      # 杠杆倍数

# 策略
STRATEGY_MODE=grid              # grid | ma
INITIAL_BASE_PRICE=0            # 网格初始基准价 (0=自动获取)
INITIAL_PRINCIPAL=0             # 初始本金 (用于风控计算)

# MA 策略专用
MA_TIMEFRAME=1H
MA_RISK_PER_TRADE=0.02
MA_TP_RATIO=3.0
MA_MAX_LEVERAGE=3

# 通知
DINGTALK_WEBHOOK=https://...
DINGTALK_SECRET=SEC...
WECHAT_WEBHOOK=https://...
BARK_KEY=xxx
BARK_SERVER=https://api.day.app

# Web
WEB_USER=admin
WEB_PASSWORD=                   # 空=不启用认证

# 其他
DISABLE_SSL_VERIFY=0            # 1=禁用SSL验证(仅开发)
HTTP_PROXY=                     # 代理
```

### 10.2 核心常量 (constants.py)

| 常量 | 默认值 | 说明 |
|------|-------|------|
| `FLAG` | `'1'` | 0=实盘, 1=模拟 |
| `INITIAL_GRID` | `0.5` | 初始网格大小 (%) |
| `MIN_TRADE_AMOUNT` | `20.0` | 最小交易额 (USDT) |
| `SAFETY_MARGIN` | `0.95` | 余额安全边际 (95%) |
| `MAX_POSITION_RATIO` | `0.9` | 最大仓位比例 |
| `MIN_POSITION_RATIO` | `0.1` | 最小底仓比例 |
| `MAX_DRAWDOWN` | `-0.15` | 最大回撤止损 (15%) |
| `DAILY_LOSS_LIMIT` | `-0.05` | 每日亏损限制 (5%) |
| `MAX_CONSECUTIVE_LOSSES` | `5` | 连续亏损保护阈值 |
| `LOSS_COOLDOWN` | `300` | 连续亏损冷却 (秒) |
| `COOLDOWN` | `60` | 交易冷却间隔 (秒) |

---

## 十一、回测系统

**文件**: `src/backtest/backtester.py`, `sim_exchange.py`, `report.py`

- `SimExchange` 模拟交易所（内存中的 K线回放 + 订单撮合）
- `Backtester` 逐根 K线驱动 MAStrategy.analyze()
- `BacktestReport` 计算: 总收益率、胜率、盈亏比、最大回撤
- `optimize.py` 576 种参数组合网格搜索
- `visualize.py` 生成 TradingView Lightweight Charts HTML 报告

运行：
```bash
python run_backtest.py         # 单次回测
python optimize.py             # 参数优化
python visualize.py            # 可视化
```

---

## 十二、目录结构

```
okx-bot/
├── main.py                     # 主入口
├── run_backtest.py             # 回测入口
├── optimize.py                 # 参数优化
├── visualize.py                # 回测可视化
├── analyze_trades.py           # 交易分析脚本
├── check_account_config.py     # 账户配置查询
├── check_swap.py               # 合约交易对查询
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env                        # 环境变量 (不入库)
│
├── src/
│   ├── __init__.py             # 版本号
│   ├── config/
│   │   ├── constants.py        # 全局常量
│   │   └── settings.py         # TradingConfig / MAConfig
│   ├── core/
│   │   ├── bot_manager.py      # 策略生命周期管理
│   │   ├── trade.py            # GridTrader (网格引擎)
│   │   ├── ma_trade.py         # MATrader (双均线引擎)
│   │   ├── order.py            # OrderManager + 限流器
│   │   └── position_tracker.py # 持仓跟踪 + 移动止损
│   ├── strategies/
│   │   ├── grid.py             # 网格信号逻辑
│   │   ├── position.py         # S1 Donchian 仓位调整
│   │   └── ma.py               # MA 状态机 + 双子策略
│   ├── indicators/
│   │   ├── volatility.py       # 波动率计算
│   │   ├── trend.py            # MA/EMA/MACD/ADX/ATR/布林带
│   │   └── price.py            # 价格分位/支撑阻力
│   ├── services/
│   │   ├── exchange.py         # OKX API 封装
│   │   ├── balance.py          # 余额/仓位管理
│   │   ├── notification.py     # 钉钉/企微/Bark 通知(异步)
│   │   └── persistence.py      # JSON 持久化
│   ├── risk/
│   │   └── manager.py          # 多层风控
│   ├── utils/
│   │   ├── logging.py          # 日志配置
│   │   ├── formatters.py       # 消息格式化
│   │   └── decorators.py       # 重试/调试装饰器
│   ├── web/
│   │   └── server.py           # aiohttp REST API
│   └── backtest/
│       ├── backtester.py       # 回测引擎
│       ├── sim_exchange.py     # 模拟交易所
│       └── report.py           # 回测报告
│
├── frontend/                   # React SPA (Vite + React 19)
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api.js
│   │   └── pages/
│   │       ├── Dashboard.jsx
│   │       ├── Parameters.jsx
│   │       ├── Logs.jsx
│   │       ├── Backtest.jsx
│   │       └── Login.jsx
│   └── dist/                   # 构建产物
│
└── data/                       # 运行时数据
    ├── state.json              # 交易状态
    ├── trade_history.json      # 交易历史
    └── *.csv                   # 回测数据
```

---

## 十三、关键数据流

### 网格交易一笔完整流程

```
fetch_ticker() → current_price
        │
        ▼
GridStrategy.check_signal()
  current vs base_price, 偏离 > grid_size%
        │ signal = 'buy'
        ▼
execute_grid_trade('buy', price)
        │
        ├─ _calculate_trade_amount() → amount
        ├─ balance_service.check_buy_balance() → OK
        │     └─ 不够? → exchange.transfer_to_spot() 从理财赎回
        ├─ exchange.create_order(limit, buy, amount, price)
        ├─ risk_manager.record_trade_result(profit)
        ├─ order_manager.log_trade(...)
        ├─ notifier.send_trade_notification(...)
        └─ grid_strategy.set_base_price(price)  ← 关键: 更新基准价
```

### MA策略一笔完整流程

```
fetch_ticker() → current_price
        │
        ▼
position_tracker.update_price()  ← 先检查已有持仓的退出
  触发? → exchange.close_position() → 通知
        │
        ▼
MAStrategy.analyze(indicators)
  ├─ get_six_line_data() → 6条均线 + OHLCV
  ├─ detect_squeeze() → 密集检测
  ├─ detect_alignment() → 排列检测
  ├─ 状态机更新 (IDLE/SQUEEZE/TREND)
  ├─ 策略A: 密集突破检查
  └─ 策略B: MA20回踩检查
        │ signal = OPEN_LONG
        ▼
_execute_entry(signal)
  ├─ risk_amount / |price - stop_loss| → amount
  ├─ 杠杆检查 <= MAX_LEVERAGE
  ├─ exchange.create_order(market, buy)
  ├─ position_tracker.open_position(sl, tp, trailing_stop)
  └─ notifier.send(...)
```

---

## 十四、部署

### Docker

```bash
docker-compose up -d
```

`docker-compose.yml` 挂载 `.env` 和 `data/` 目录。

### 手动

```bash
pip install -r requirements.txt
cp .env.example .env  # 编辑配置
python main.py --strategy grid
```

### 前端构建

```bash
cd frontend
npm install
npm run build
# 产物在 frontend/dist/, 由 WebServer 自动 serve
```
