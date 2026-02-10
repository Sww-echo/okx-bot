"""
持仓跟踪模块
负责 MA 策略的持仓管理、止盈止损跟踪
"""
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict

@dataclass
class Position:
    """持仓数据结构"""
    symbol: str
    side: str           # 'long', 'short'
    entry_price: float
    amount: float
    stop_loss: float
    take_profit: float
    strategy_id: str    # 'A', 'B'
    entry_time: int
    pnl: float = 0.0
    max_price: float = 0.0 # 持仓期间最高价 (用于移动止损)
    min_price: float = 0.0 # 持仓期间最低价

class PositionTracker:
    """MA 策略持仓跟踪器"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.position: Optional[Position] = None
        
    def open_position(self, symbol: str, side: str, price: float, amount: float, 
                     sl: float, tp: float, strategy_id: str, timestamp: int):
        """记录开仓"""
        if self.position:
            self.logger.warning("已有持仓，无法开新仓")
            return
            
        self.position = Position(
            symbol=symbol,
            side=side,
            entry_price=price,
            amount=amount,
            stop_loss=sl,
            take_profit=tp,
            strategy_id=strategy_id,
            entry_time=timestamp,
            max_price=price,
            min_price=price
        )
        self.logger.info(f"持仓已建立: {side} {amount} @ {price} | SL: {sl} | TP: {tp}")

    def close_position(self):
        """清空持仓记录"""
        self.position = None
        self.logger.info("持仓记录已清除")

    def update_price(self, current_price: float) -> Optional[str]:
        """
        更新当前价格，检查是否触发止盈止损
        
        Returns:
            触发原因 ('STOP_LOSS', 'TAKE_PROFIT', None)
        """
        if not self.position:
            return None
            
        pos = self.position
        
        # 更新最高/最低价
        pos.max_price = max(pos.max_price, current_price)
        pos.min_price = min(pos.min_price, current_price) if pos.min_price > 0 else current_price
        
        # 计算浮动盈亏 (用于日志)
        if pos.side == 'long':
            pos.pnl = (current_price - pos.entry_price) * pos.amount
            
            # 止损检查
            if current_price <= pos.stop_loss:
                self.logger.info(f"触发止损: 当前 {current_price} <= SL {pos.stop_loss}")
                return 'STOP_LOSS'
            
            # 止盈检查
            if current_price >= pos.take_profit:
                self.logger.info(f"触发止盈: 当前 {current_price} >= TP {pos.take_profit}")
                return 'TAKE_PROFIT'
                
        elif pos.side == 'short':
            pos.pnl = (pos.entry_price - current_price) * pos.amount
            
            # 止损检查
            if current_price >= pos.stop_loss:
                self.logger.info(f"触发止损: 当前 {current_price} >= SL {pos.stop_loss}")
                return 'STOP_LOSS'
                
            # 止盈检查
            if current_price <= pos.take_profit:
                self.logger.info(f"触发止盈: 当前 {current_price} <= TP {pos.take_profit}")
                return 'TAKE_PROFIT'
                
        return None

    def get_position(self) -> Optional[Position]:
        return self.position
