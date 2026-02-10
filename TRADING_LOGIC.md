# 交易逻辑详解

本文档详细说明 OKX 网格交易机器人的核心交易逻辑。

## 目录

- [网格交易原理](#网格交易原理)
- [信号检测逻辑](#信号检测逻辑)
- [交易执行流程](#交易执行流程)
- [S1 仓位策略](#s1-仓位策略)
- [动态网格调整](#动态网格调整)
- [风控机制](#风控机制)

---

## 网格交易原理

网格交易是一种量化交易策略，通过在固定价格区间内设置多个买卖点位，利用价格的上下波动来赚取差价利润。

### 核心概念

| 概念 | 说明 |
|------|------|
| **基准价** | 交易的参考价格，每次成交后更新 |
| **网格大小** | 触发交易的价格变化百分比 (例如 2%) |
| **买入触发** | 价格相对基准价下跌超过网格大小 |
| **卖出触发** | 价格相对基准价上涨超过网格大小 |

### 图示

```
价格
  ↑
  │    ┌─────────────────────────────── 卖出触发线 (+2%)
  │    │
  │    │←── 网格大小
  │    │
  ├────┼─────────────────────────────── 基准价 (75 USDT)
  │    │
  │    │←── 网格大小
  │    │
  │    └─────────────────────────────── 买入触发线 (-2%)
  │
时间 →
```

### 交易示例

假设初始设置：
- 基准价 = **75.00 USDT**
- 网格大小 = **2%**

| 时间 | 当前价格 | 价差 | 触发信号 | 操作 | 新基准价 |
|------|---------|------|---------|------|---------|
| T1 | 75.00 | 0% | 无 | 等待 | 75.00 |
| T2 | 74.80 | -0.27% | 无 | 等待 | 75.00 |
| T3 | **73.50** | **-2%** | **买入** | 买入 OKB | **73.50** |
| T4 | 73.80 | +0.41% | 无 | 等待 | 73.50 |
| T5 | **74.97** | **+2%** | **卖出** | 卖出 OKB | **74.97** |
| T6 | 75.20 | +0.31% | 无 | 等待 | 74.97 |

---

## 信号检测逻辑

### 代码实现

```python
# 文件: src/strategies/grid.py

def check_signal(self, current_price: float) -> Tuple[str, float]:
    """检查交易信号"""
    if self.base_price <= 0:
        return None, 0.0
    
    # 计算价格变化百分比
    price_diff_pct = (current_price - self.base_price) / self.base_price
    
    # 卖出信号: 价格上涨超过网格大小
    if price_diff_pct >= (self.grid_size / 100):
        return 'sell', price_diff_pct
    
    # 买入信号: 价格下跌超过网格大小
    elif price_diff_pct <= -(self.grid_size / 100):
        return 'buy', price_diff_pct
    
    return None, price_diff_pct
```

### 信号判断流程图

```
                    ┌──────────────────┐
                    │   获取当前价格    │
                    └────────┬─────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │  计算价差 = (当前价-基准价)   │
              │            / 基准价          │
              └──────────────┬───────────────┘
                             │
                             ▼
                    ┌────────────────┐
           ┌──────◀│  价差 >= +2%?  │
           │  是    └───────┬────────┘
           │                │ 否
           ▼                ▼
    ┌────────────┐   ┌────────────────┐
    │  卖出信号  │   │  价差 <= -2%?  │▶──────┐
    └────────────┘   └───────┬────────┘  是   │
                             │ 否             ▼
                             ▼         ┌────────────┐
                      ┌──────────┐     │  买入信号  │
                      │  无信号  │     └────────────┘
                      └──────────┘
```

---

## 交易执行流程

### 主循环

```python
# 文件: src/core/trade.py

async def start(self):
    """主循环"""
    while True:
        # 1. 获取最新价格
        ticker = await self.exchange.fetch_ticker(self.config.SYMBOL)
        self.current_price = float(ticker['last'])
        
        # 2. 检查网格交易信号
        await self._process_grid_signals()
        
        # 3. 风险检查
        if await self.risk_manager.multi_layer_check(self.current_price):
            await asyncio.sleep(5)
            continue
        
        # 4. S1 策略检查
        await self.s1_strategy.check_and_execute(...)
        
        # 5. 网格大小调整
        await self._adjust_grid_size_if_needed()
        
        await asyncio.sleep(5)  # 5秒轮询间隔
```

### 交易执行

```python
async def execute_grid_trade(self, side: str, price: float):
    """执行网格交易"""
    
    # 1. 计算交易量 (总资产的5%)
    amount = await self._calculate_trade_amount(side, price)
    
    # 2. 余额检查
    if side == 'buy':
        sufficient, _ = await self.balance_service.check_buy_balance(...)
    else:
        sufficient, _ = await self.balance_service.check_sell_balance(...)
    
    if not sufficient:
        return  # 余额不足，取消交易
    
    # 3. 下单
    order = await self.exchange.create_order(
        symbol=self.config.SYMBOL,
        type='limit',
        side=side,
        amount=amount,
        price=price
    )
    
    # 4. 记录交易
    self.order_manager.log_trade({...})
    
    # 5. 发送通知
    self.notifier.send_trade_notification(...)
    
    # 6. 更新基准价
    self.grid_strategy.set_base_price(price)
```

### 交易量计算

```python
async def _calculate_trade_amount(self, side: str, price: float) -> float:
    """计算交易数量"""
    
    # 获取总资产
    total_assets = await self.balance_service.get_total_assets(price)
    
    # 每次交易金额 = 总资产 * 5% (最低 20 USDT)
    amount_usdt = max(
        self.config.MIN_TRADE_AMOUNT,  # 20 USDT
        total_assets * 0.05
    )
    
    # 转换为币种数量
    amount = amount_usdt / price
    
    return float(f"{amount:.3f}")
```

---

## S1 仓位策略

S1 策略是一种基于每日高低点的仓位调整策略。

### 原理

- **高位减仓**: 当价格接近 54 日高点时，逐步减少仓位
- **低位加仓**: 当价格接近 54 日低点时，逐步增加仓位

### 仓位调整逻辑

```python
# 文件: src/strategies/position.py

async def check_and_execute(self, current_price, balance_service, symbol):
    """检查并执行S1仓位调整"""
    
    # 计算价格在高低点区间的位置
    if self.daily_high <= self.daily_low:
        return
    
    position_in_range = (
        (current_price - self.daily_low) / 
        (self.daily_high - self.daily_low)
    )
    
    # 获取当前仓位
    current_position = await balance_service.get_position_ratio(current_price)
    
    # 计算目标仓位 (价格越高，目标仓位越低)
    target_position = 1.0 - position_in_range  # 简化逻辑
    
    # 调整仓位
    if current_position > target_position + 0.1:
        # 需要减仓
        await self._execute_reduce(...)
    elif current_position < target_position - 0.1:
        # 需要加仓
        await self._execute_add(...)
```

### 图示

```
仓位比例
100% ├──●──────────────────────────────
     │   \
 80% │    \
     │     \
 60% │      \
     │       \
 40% │        \
     │         \
 20% │          \
     │           \
  0% ├────────────●──────────────────────
     │            │
     低点        高点
           ← 价格区间 →
```

---

## 动态网格调整

网格大小会根据市场波动率自动调整。

### 调整逻辑

```python
# 文件: src/strategies/grid.py

def update_grid_size(self, volatility: float) -> float:
    """根据波动率调整网格大小"""
    
    # 波动率区间配置
    volatility_ranges = [
        {'range': [0.00, 0.02], 'grid': 1.5},  # 低波动 → 小网格
        {'range': [0.02, 0.04], 'grid': 2.0},  # 中波动 → 中网格
        {'range': [0.04, 0.08], 'grid': 3.0},  # 高波动 → 大网格
        {'range': [0.08, 1.00], 'grid': 4.0},  # 极高波动 → 更大网格
    ]
    
    # 根据当前波动率选择网格大小
    for config in volatility_ranges:
        if config['range'][0] <= volatility < config['range'][1]:
            return config['grid']
    
    return self.config.INITIAL_GRID  # 默认
```

### 波动率计算

```python
# 文件: src/indicators/volatility.py

async def calculate_volatility(self, period: int = 24) -> float:
    """计算波动率 (基于过去N小时的价格标准差)"""
    
    # 获取历史K线
    klines = await self.exchange.fetch_ohlcv(symbol, '1H', limit=period)
    
    # 计算收益率
    closes = [float(k[4]) for k in klines]
    returns = [(closes[i] - closes[i-1]) / closes[i-1] 
               for i in range(1, len(closes))]
    
    # 计算标准差作为波动率
    volatility = np.std(returns)
    
    return volatility
```

---

## 风控机制

### 多层风控检查

```python
# 文件: src/risk/manager.py

async def multi_layer_check(self, current_price: float) -> bool:
    """
    多层风控检查
    返回 True 表示触发风控，应暂停交易
    """
    
    # 1. 仓位检查
    position_ratio = await self.balance_service.get_position_ratio(current_price)
    
    if position_ratio > self.config.MAX_POSITION_PERCENT / 100:
        self.logger.warning(f"仓位超限 | 当前: {position_ratio:.2%}")
        return True
    
    if position_ratio < self.config.MIN_POSITION_PERCENT / 100:
        self.logger.warning(f"底仓不足 | 当前: {position_ratio:.2%}")
        # 触发加仓逻辑
    
    # 2. 回撤检查
    total_assets = await self.balance_service.get_total_assets(current_price)
    drawdown = (self.peak_assets - total_assets) / self.peak_assets
    
    if drawdown > self.config.MAX_DRAWDOWN / 100:
        self.logger.error(f"回撤超限 | 当前: {drawdown:.2%}")
        return True
    
    return False
```

### 风控参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `MAX_POSITION_PERCENT` | 最大仓位比例 | 90% |
| `MIN_POSITION_PERCENT` | 最小底仓比例 | 10% |
| `MAX_DRAWDOWN` | 最大回撤限制 | 15% |
| `DAILY_LOSS_LIMIT` | 单日最大亏损 | 5% |

### 风控触发后的行为

```
风控检查
    │
    ├─▶ 仓位超限 (>90%)
    │       └─▶ 暂停买入，等待卖出
    │
    ├─▶ 底仓不足 (<10%)
    │       └─▶ 暂停卖出，触发加仓
    │
    └─▶ 回撤超限 (>15%)
            └─▶ 暂停所有交易，发送告警
```

---

## 订单限流

为防止短时间内频繁下单，系统实现了订单限流机制。

```python
# 文件: src/core/order.py

class OrderThrottler:
    def __init__(self, limit: int = 10, interval: int = 60):
        self.order_timestamps = []
        self.limit = limit      # 60秒内最多10笔订单
        self.interval = interval
    
    def check_rate(self) -> bool:
        """检查是否允许下单"""
        current_time = time.time()
        
        # 清理过期时间戳
        self.order_timestamps = [
            t for t in self.order_timestamps 
            if current_time - t < self.interval
        ]
        
        if len(self.order_timestamps) >= self.limit:
            return False  # 超过限制
        
        self.order_timestamps.append(current_time)
        return True
```

---

## 总结

本机器人通过以下机制实现自动化网格交易：

1. **持续监控** - 每 5 秒获取最新价格
2. **信号检测** - 根据价格变化判断买卖信号
3. **风险控制** - 多层风控确保资金安全
4. **动态调整** - 根据市场状态自动调整参数
5. **完整记录** - 所有交易详细记录和通知

> ⚠️ **风险提示**: 量化交易存在风险，请在充分理解策略逻辑后谨慎使用。
