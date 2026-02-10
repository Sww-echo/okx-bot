"""
MA 策略回测引擎
"""
import asyncio
import logging
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime

from ..config.settings import MAConfig
from ..strategies.ma import MAStrategy, Signal
from ..indicators.trend import TrendIndicators
from .sim_exchange import SimExchange
from .report import BacktestReport # 稍后创建

class Backtester:
    """MA 策略回测器"""
    
    def __init__(self, config: MAConfig, initial_balance: float = 10000.0, fee_rate: float = 0.0005):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config
        
        # 初始化组件
        self.exchange = SimExchange(initial_balance, fee_rate)
        self.indicators = TrendIndicators(self.exchange)
        self.strategy = MAStrategy(config)
        
        # 回测状态
        self.trades: List[Dict] = []
        self.equity_curve: List[Dict] = [] # {time, equity}
        
    async def run(self, data: pd.DataFrame):
        """执行回测"""
        self.logger.info(f"开始回测... 数据量: {len(data)}")
        
        # 加载数据到模拟交易所
        self.exchange.load_data(data)
        
        # 预热: 跳过前面足够的K线以计算指标
        warmup_period = max(self.config.PERIODS) + self.config.SQUEEZE_LOOKBACK + 50
        if len(data) < warmup_period:
            self.logger.error("数据量不足以进行预热")
            return

        # 逐根K线回放
        for i in range(warmup_period, len(data)):
            # 1. 更新时间
            self.exchange.set_time(i)
            current_bar = data.iloc[i]
            timestamp = current_bar['timestamp']
            
            # 2. 策略分析
            signal = await self.strategy.analyze(self.indicators)
            
            # 3. 信号执行
            if signal.type.startswith('OPEN'):
                await self._execute_open(signal, timestamp)
            elif signal.type.startswith('CLOSE'):
                await self._execute_close(signal, timestamp)
                
            # 4. 检查止损止盈 (对现有持仓)
            # 需遍历所有持仓
            await self._check_exits(current_bar)
            
            # 5. 记录权益
            # 简化: 只记录余额 (暂不计算浮动盈亏，或需完善 SimExchange)
            # equity = self.exchange.get_equity(current_bar['close'])
            # self.equity_curve.append({'time': timestamp, 'value': equity})

        self.logger.info("回测完成")
        
    async def _execute_open(self, signal: Signal, timestamp):
        # 简单全仓或固定比例
        balance = self.exchange.balance
        risk_amt = balance * self.config.RISK_PER_TRADE
        dist = abs(signal.price - signal.stop_loss)
        if dist == 0: return
        
        amount = risk_amt / dist
        
        # DEBUG
        if not isinstance(amount, (int, float)) and not isinstance(amount, np.float64):
             self.logger.error(f"DEBUG: amount type {type(amount)} value {amount}")
             self.logger.error(f"DEBUG: risk_amt {risk_amt} dist {dist}")
        
        cost = amount * signal.price
        if cost > balance: amount = balance / signal.price * 0.95 # 资金不足则满仓
        
        side = 'buy' if 'LONG' in signal.type else 'sell'
        
        # 下单
        order = await self.exchange.create_order(
            symbol=self.config.SYMBOL,
            type='market',
            side=side,
            amount=amount,
            pos_side='long' if side=='buy' else 'short' # 简化单向
        )
        
        # 记录交易
        trade = {
            'entry_time': timestamp,
            'entry_price': order['avgPx'],
            'side': side,
            'amount': amount,
            'sl': signal.stop_loss,
            'tp': signal.take_profit,
            'reason': signal.reason,
            'status': 'OPEN',
            'strategy': signal.strategy_id
        }
        self.trades.append(trade)

    async def _check_exits(self, current_bar):
        current_price = current_bar['close']
        high = current_bar['high']
        low = current_bar['low']
        
        for trade in self.trades:
            if trade['status'] != 'OPEN': continue
            
            side = trade['side']
            exit_reason = None
            exit_price = current_price
            
            if side == 'buy':
                # 止损: Low <= SL
                if low <= trade['sl']:
                    exit_reason = 'STOP_LOSS'
                    exit_price = trade['sl'] # 假设刚好在SL成交
                # 止盈: High >= TP
                elif high >= trade['tp']:
                    exit_reason = 'TAKE_PROFIT'
                    exit_price = trade['tp']
            else: # sell
                if high >= trade['sl']:
                    exit_reason = 'STOP_LOSS'
                    exit_price = trade['sl']
                elif low <= trade['tp']:
                    exit_reason = 'TAKE_PROFIT'
                    exit_price = trade['tp']
            
            if exit_reason:
                await self._close_trade(trade, exit_price, exit_reason, current_bar['timestamp'])

    async def _close_trade(self, trade, price, reason, timestamp):
        # 模拟平仓交易
        close_side = 'sell' if trade['side'] == 'buy' else 'buy'
        await self.exchange.create_order(
            symbol=self.config.SYMBOL,
            type='market',
            side=close_side,
            amount=trade['amount'],
            price=price
        )
        
        # 更新记录
        trade['status'] = 'CLOSED'
        trade['exit_time'] = timestamp
        trade['exit_price'] = price
        trade['exit_reason'] = reason
        
        # 计算盈亏
        if trade['side'] == 'buy':
            pnl = (price - trade['entry_price']) * trade['amount']
        else:
            pnl = (trade['entry_price'] - price) * trade['amount']
            
        trade['pnl'] = pnl
        self.logger.info(f"平仓: {reason} PnL: {pnl:.2f}")

    def generate_report(self) -> BacktestReport:
        return BacktestReport(self.trades, self.exchange.initial_balance)
