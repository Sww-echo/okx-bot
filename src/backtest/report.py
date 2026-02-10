"""
回测报告生成器
"""
from dataclasses import dataclass
from typing import List, Dict
import pandas as pd
import numpy as np

@dataclass
class BacktestReport:
    """回测报告"""
    trades: List[Dict]
    initial_balance: float
    final_balance: float = 0.0
    total_return: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    total_trades: int = 0
    
    def __init__(self, trades: List[Dict], initial_balance: float):
        self.trades = trades
        self.initial_balance = initial_balance
        self._calculate_metrics()
        
    def _calculate_metrics(self):
        if not self.trades:
            self.final_balance = self.initial_balance
            return
            
        # 提取盈亏
        pnls = [t['pnl'] for t in self.trades if 'pnl' in t]
        self.total_trades = len(pnls)
        
        self.final_balance = self.initial_balance + sum(pnls)
        self.total_return = (self.final_balance - self.initial_balance) / self.initial_balance * 100
        
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        
        self.win_rate = len(wins) / len(pnls) * 100 if pnls else 0
        
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        self.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # 最大回撤 (简化: 基于每笔交易后的余额)
        balance_curve = [self.initial_balance]
        current_bal = self.initial_balance
        for p in pnls:
            current_bal += p
            balance_curve.append(current_bal)
            
        peak = balance_curve[0]
        max_dd = 0
        for val in balance_curve:
            if val > peak:
                peak = val
            dd = (peak - val) / peak
            max_dd = max(max_dd, dd)
        self.max_drawdown = max_dd * 100

    def print_summary(self):
        """打印摘要"""
        print("="*50)
        print("MA 策略回测报告")
        print("="*50)
        print(f"初始资金: {self.initial_balance:.2f} USDT")
        print(f"最终资金: {self.final_balance:.2f} USDT")
        print(f"总收益率: {self.total_return:.2f}%")
        print("-" * 30)
        print(f"总交易数: {self.total_trades}")
        print(f"胜率: {self.win_rate:.2f}%")
        print(f"盈亏比: {self.profit_factor:.2f}")
        print(f"最大回撤: {self.max_drawdown:.2f}%")
        print("="*50)
        
    def save_csv(self, filename: str):
        """保存交易记录"""
        if not self.trades: return
        df = pd.DataFrame(self.trades)
        df.to_csv(filename, index=False)
        print(f"交易记录已保存至 {filename}")
