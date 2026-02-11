"""
持仓跟踪模块
负责 MA 策略的持仓管理、止盈止损跟踪
支持按策略ID (A/B) 管理多个独立持仓
"""
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple

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
    _initial_stop_loss: float = 0.0  # 记录初始止损 (用于判断是否为移动止损触发)

class PositionTracker:
    """MA 策略持仓跟踪器 (支持多策略独立持仓)"""
    
    def __init__(self, max_positions: int = 2):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.positions: Dict[str, Position] = {}  # strategy_id -> Position
        self.max_positions = max_positions  # 最大同时持仓数
        
    def open_position(self, symbol: str, side: str, price: float, amount: float, 
                     sl: float, tp: float, strategy_id: str, timestamp: int):
        """记录开仓 (按策略ID独立管理)"""
        # 检查该策略是否已有持仓
        if strategy_id in self.positions:
            self.logger.warning(f"策略{strategy_id} 已有持仓，无法开新仓")
            return
        
        # 检查总持仓数
        if len(self.positions) >= self.max_positions:
            self.logger.warning(f"已达最大持仓数 {self.max_positions}，无法开新仓")
            return
            
        pos = Position(
            symbol=symbol,
            side=side,
            entry_price=price,
            amount=amount,
            stop_loss=sl,
            take_profit=tp,
            strategy_id=strategy_id,
            entry_time=timestamp,
            max_price=price,
            min_price=price,
            _initial_stop_loss=sl
        )
        self.positions[strategy_id] = pos
        self.logger.info(f"持仓建立 [策略{strategy_id}]: {side} {amount} @ {price} | SL: {sl} | TP: {tp}")

    def close_position(self, strategy_id: str = None):
        """
        清空持仓记录
        
        Args:
            strategy_id: 指定策略ID，None则清空所有
        """
        if strategy_id:
            if strategy_id in self.positions:
                del self.positions[strategy_id]
                self.logger.info(f"持仓记录已清除 [策略{strategy_id}]")
        else:
            self.positions.clear()
            self.logger.info("所有持仓记录已清除")

    def update_price(self, current_price: float) -> List[Tuple[str, str]]:
        """
        更新当前价格，检查所有持仓是否触发止盈止损（含移动止损）
        
        Returns:
            触发列表: [(strategy_id, reason), ...] 
            reason: 'STOP_LOSS', 'TAKE_PROFIT', 'TRAILING_STOP'
        """
        triggered = []
        
        for strategy_id, pos in list(self.positions.items()):
            reason = self._check_single_position(pos, current_price)
            if reason:
                triggered.append((strategy_id, reason))
                
        return triggered
    
    def _check_single_position(self, pos: Position, current_price: float) -> Optional[str]:
        """检查单个持仓的止盈止损"""
        # 更新最高/最低价
        pos.max_price = max(pos.max_price, current_price)
        pos.min_price = min(pos.min_price, current_price) if pos.min_price > 0 else current_price
        
        if pos.side == 'long':
            pos.pnl = (current_price - pos.entry_price) * pos.amount
            
            # === 移动止损逻辑 ===
            risk_distance = pos.entry_price - pos._initial_stop_loss
            if risk_distance > 0:
                profit_in_r = (pos.max_price - pos.entry_price) / risk_distance
                
                # 盈利 >= 2R: 止损跟随推进
                if profit_in_r >= 2.0:
                    new_sl = pos.entry_price + risk_distance * (profit_in_r - 1.0)
                    new_sl = min(new_sl, pos.max_price - risk_distance * 0.5)
                    if new_sl > pos.stop_loss:
                        self.logger.info(f"移动止损 [策略{pos.strategy_id}]: SL {pos.stop_loss:.2f} -> {new_sl:.2f} ({profit_in_r:.1f}R)")
                        pos.stop_loss = new_sl
                # 盈利 >= 1R: 保本止损
                elif profit_in_r >= 1.0:
                    new_sl = pos.entry_price
                    if new_sl > pos.stop_loss:
                        self.logger.info(f"保本止损 [策略{pos.strategy_id}]: SL {pos.stop_loss:.2f} -> {new_sl:.2f}")
                        pos.stop_loss = new_sl
            
            # 止损检查
            if current_price <= pos.stop_loss:
                reason = 'TRAILING_STOP' if pos.stop_loss > pos._initial_stop_loss else 'STOP_LOSS'
                self.logger.info(f"触发{reason} [策略{pos.strategy_id}]: {current_price} <= SL {pos.stop_loss}")
                return reason
            
            # 止盈检查
            if current_price >= pos.take_profit:
                self.logger.info(f"触发止盈 [策略{pos.strategy_id}]: {current_price} >= TP {pos.take_profit}")
                return 'TAKE_PROFIT'
                
        elif pos.side == 'short':
            pos.pnl = (pos.entry_price - current_price) * pos.amount
            
            # === 移动止损逻辑 (空头) ===
            risk_distance = pos._initial_stop_loss - pos.entry_price
            if risk_distance > 0:
                profit_in_r = (pos.entry_price - pos.min_price) / risk_distance
                
                if profit_in_r >= 2.0:
                    new_sl = pos.entry_price - risk_distance * (profit_in_r - 1.0)
                    new_sl = max(new_sl, pos.min_price + risk_distance * 0.5)
                    if new_sl < pos.stop_loss:
                        self.logger.info(f"移动止损 [策略{pos.strategy_id}]: SL {pos.stop_loss:.2f} -> {new_sl:.2f} ({profit_in_r:.1f}R)")
                        pos.stop_loss = new_sl
                elif profit_in_r >= 1.0:
                    new_sl = pos.entry_price
                    if new_sl < pos.stop_loss:
                        self.logger.info(f"保本止损 [策略{pos.strategy_id}]: SL {pos.stop_loss:.2f} -> {new_sl:.2f}")
                        pos.stop_loss = new_sl
            
            # 止损检查
            if current_price >= pos.stop_loss:
                reason = 'TRAILING_STOP' if pos.stop_loss < pos._initial_stop_loss else 'STOP_LOSS'
                self.logger.info(f"触发{reason} [策略{pos.strategy_id}]: {current_price} >= SL {pos.stop_loss}")
                return reason
                
            # 止盈检查
            if current_price <= pos.take_profit:
                self.logger.info(f"触发止盈 [策略{pos.strategy_id}]: {current_price} <= TP {pos.take_profit}")
                return 'TAKE_PROFIT'
                
        return None

    def get_position(self, strategy_id: str = None) -> Optional[Position]:
        """
        获取持仓
        
        Args:
            strategy_id: 指定策略ID。None 返回第一个持仓（向后兼容）
        """
        if strategy_id:
            return self.positions.get(strategy_id)
        # 向后兼容: 返回第一个持仓
        if self.positions:
            return next(iter(self.positions.values()))
        return None
    
    def get_all_positions(self) -> Dict[str, Position]:
        """获取所有持仓"""
        return self.positions.copy()
    
    def has_position(self, strategy_id: str = None) -> bool:
        """
        检查是否有持仓
        
        Args:
            strategy_id: 指定策略ID。None 检查是否有任何持仓
        """
        if strategy_id:
            return strategy_id in self.positions
        return len(self.positions) > 0
