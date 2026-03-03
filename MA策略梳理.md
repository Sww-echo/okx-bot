# MA 策略逻辑梳理（代码实现版）

本文基于当前代码实现（`MAStrategy` + `MATrader` + `PositionTracker`）梳理实际运行逻辑。

## 1. 策略总体结构

- **信号层**：`src/strategies/ma.py` 的 `MAStrategy.analyze()` 负责识别市场状态并输出 `Signal`。
- **执行层**：`src/core/ma_trade.py` 的 `MATrader` 负责轮询、下单、风控、通知。
- **持仓层**：`src/core/position_tracker.py` 负责多策略持仓记录、止盈止损与移动止损。

> 当前实现允许策略 A/B 并行（按 `strategy_id` 区分），每个策略最多 1 个仓位，总仓位默认最多 2 个。

## 2. 数据与指标来源

每轮分析会读取 6 条均线 + K线字段：

- `MA20/60/120`
- `EMA20/60/120`
- `ATR`
- `volume` 与 `volume_ma`
- 当前 K 线的 `open/high/low/close`

指标计算在 `TrendIndicators` 中完成：

- `detect_squeeze()`：用 6 线的**变异系数**（`std / mean`）判断密集。
- `detect_alignment()`：
  - 多头：`EMA20 > EMA60 > EMA120` 且 `MA20 > MA60`
  - 空头：`EMA20 < EMA60 < EMA120` 且 `MA20 < MA60`

## 3. 市场状态机

状态枚举：

- `IDLE`：无序
- `SQUEEZE`：均线密集
- `TREND_LONG`：多头排列
- `TREND_SHORT`：空头排列

状态切换优先级：

1. 先判密集（是则进入 `SQUEEZE`）
2. 否则看排列（`long/short`）
3. 否则 `IDLE`

并维护两个关键记忆：

- `last_squeeze_high/low`：最近密集区 6 线最大/最小值
- `squeeze_cooldown`：密集结束后保留 20 根周期窗口，用于“密集突破”信号触发

## 4. 入场逻辑

### 4.1 策略 A：密集突破

触发前提：`squeeze_cooldown > 0` 且当前已进入趋势排列。

- **做多**：价格 > `last_squeeze_high * (1 + BREAKOUT_THRESHOLD)`
- **做空**：价格 < `last_squeeze_low * (1 - BREAKOUT_THRESHOLD)`

过滤与确认：

- 若开启量能确认，需 `current_volume >= 1.5 * volume_ma`
- 同方向连续突破计数 `breakout_bars_count`
- 达到 `BREAKOUT_BARS` 后发出开仓信号

止损设置：

- A 多单止损放在 `last_squeeze_low`
- A 空单止损放在 `last_squeeze_high`

### 4.2 策略 B：趋势回踩 MA20

先过过滤器：

- ADX 过滤开启时：`ADX >= 25`
- MACD 过滤开启时：
  - 多头回踩要求 `macd_hist >= 0`
  - 空头回弹要求 `macd_hist <= 0`

具体触发：

- **多头回踩买入**：`low <= MA20` 且 `close >= MA20`
- **空头受阻卖出**：`high >= MA20` 且 `close <= MA20`

止损设置：

- `sl_distance = ATR * ATR_MULTIPLIER`（无 ATR 时退化为 `MA20 * 2%`）
- 多单：`SL = MA20 - sl_distance`
- 空单：`SL = MA20 + sl_distance`

## 5. 止盈止损与移动止损

`_create_signal()` 中统一计算：

- 默认风险距离 = `|entry - stop_loss|`
- 止盈 = 风险距离 × `TP_RATIO`

`PositionTracker` 中持续跟踪：

- 命中 `SL` => `STOP_LOSS` 或 `TRAILING_STOP`
- 命中 `TP` => `TAKE_PROFIT`
- 若启用移动止损：
  - 盈利到 `1R`：推到保本
  - 盈利到 `2R+`：按 R 倍数继续抬升/下压止损

## 6. 实盘执行流程（MATrader）

循环流程：

1. 拉取最新价格
2. 先检查已有仓位是否触发退出
3. 调用 `MAStrategy.analyze()` 获取信号
4. 若 `OPEN_*` 且对应策略 ID 无持仓，则执行开仓
5. 休眠 `CHECK_INTERVAL`

开仓前风控：

- 仓位大小：`risk_amount / |entry - sl|`
- 最小交易额：`>= 10 USDT`
- 实际杠杆：不超过 `MAX_LEVERAGE`

## 7. 关键参数与默认值（MAConfig）

- `RISK_PER_TRADE = 0.02`
- `TP_RATIO = 3.0`
- `MAX_LEVERAGE = 3`
- `SQUEEZE_PERCENTILE = 20`（代码中会除以 1000）
- `BREAKOUT_BARS = 2`
- `BREAKOUT_THRESHOLD = 0.003`
- `ATR_MULTIPLIER = 1.5`
- ADX/Volume/MACD/TrailingStop 默认均开启

---

如果你希望，我可以下一步再给你一份「参数如何影响交易频率与胜率」的调参建议清单（按激进 / 均衡 / 保守三档）。
