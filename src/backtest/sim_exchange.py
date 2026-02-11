"""
回测用模拟交易所
"""
import logging
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np

class SimExchange:
    """模拟交易所"""
    
    def __init__(self, initial_balance: float = 10000.0, fee_rate: float = 0.0005):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.fee_rate = fee_rate
        
        # 历史数据 (DataFrame)
        self.data: Optional[pd.DataFrame] = None
        self.current_index = 0
        
        # 持仓
        self.positions: Dict[str, Dict] = {} # symbol -> {side, amount, entry_price}
        self.orders: List[Dict] = []
        
    def load_data(self, df: pd.DataFrame):
        """加载历史数据"""
        self.data = df
        self.current_index = 0
        
    def set_time(self, index: int):
        """设置当前模拟时间点"""
        self.current_index = index
        
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1H', limit: int = 200) -> List[List[float]]:
        """模拟获取K线数据 (返回当前时间点之前的数据)"""
        # 假设 self.data 已经是对应 timeframe 的数据
        if self.data is None:
            return []
            
        end_idx = self.current_index + 1
        start_idx = max(0, end_idx - limit)
        
        # 截取数据
        slice_df = self.data.iloc[start_idx:end_idx]
        
        # 转换为 list 格式: [timestamp, open, high, low, close, volume]
        # 假设 df columns: timestamp, open, high, low, close, volume
        result = slice_df.values.tolist()
        return result
        
    async def create_order(self, symbol: str, type: str, side: str, amount: float, price: float = None, pos_side: str = None) -> Dict:
        """模拟下单"""
        if self.data is None:
            raise Exception("No data loaded")
            
        # 获取当前价格 (收盘价作为成交价)
        current_candle = self.data.iloc[self.current_index]
        current_price = float(current_candle['close'])
        amount = float(amount)
        
        # 扣除手续费
        value = amount * current_price
        fee = value * self.fee_rate
        self.balance -= fee
        
        # 记录成交
        order = {
            'symbol': symbol,
            'side': side,
            'amount': amount,
            'price': current_price,
            'avgPx': current_price,
            'accFillSz': amount,
            'fee': fee,
            'timestamp': current_candle['timestamp']
        }
        self.orders.append(order)
        self.logger.info(f"模拟成交: {side} {amount} @ {current_price} (Fee: {fee:.4f})")
        
        return order
        
    async def close_position(self, symbol: str, pos_side: str):
        """模拟平仓"""
        # 简化: 直接按当前价格平仓
        # 在 Backtester 中主要通过 create_order 反向操作来平仓
        # 这里仅作兼容接口
        pass
        
    async def fetch_ticker(self, symbol: str) -> Dict:
        """模拟Ticker"""
        if self.data is None: return {}
        price = float(self.data.iloc[self.current_index]['close'])
        return {'last': price}
