"""
订单管理模块
处理订单跟踪、限流和历史记录
"""
import time
import json
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import shutil

from ..services.persistence import PersistenceService


class OrderThrottler:
    """订单限流器"""
    
    def __init__(self, limit: int = 10, interval: int = 60):
        self.order_timestamps = []
        self.limit = limit
        self.interval = interval
    
    def check_rate(self) -> bool:
        """检查是否允许下单"""
        current_time = time.time()
        # 清理过期的必须时间戳
        self.order_timestamps = [t for t in self.order_timestamps if current_time - t < self.interval]
        
        if len(self.order_timestamps) >= self.limit:
            return False
            
        self.order_timestamps.append(current_time)
        return True


class OrderManager:
    """
    订单管理器
    负责订单的生命周期跟踪、历史记录和统计
    """
    
    def __init__(self, persistence_service: PersistenceService):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.persistence = persistence_service
        
        self.active_orders = {}  # order_id -> order_info
        self.trade_history = []
        
        # 加载历史记录
        self._load_history()
        
    def _load_history(self):
        """加载交易历史"""
        self.trade_history = self.persistence.load_trade_history()
        self.logger.info(f"加载了 {len(self.trade_history)} 条历史交易记录")

    def add_active_order(self, order: Dict):
        """添加活跃订单"""
        order_id = order.get('ordId', order.get('id', ''))
        self.active_orders[order_id] = {
            'order': order,
            'created_at': datetime.now(),
            'status': order.get('state', order.get('status', 'unknown')),
            'profit': 0
        }
        self.logger.debug(f"跟踪活跃订单: {order_id}")

    def remove_active_order(self, order_id: str):
        """移除活跃订单"""
        if order_id in self.active_orders:
            del self.active_orders[order_id]
            self.logger.debug(f"移除活跃订单: {order_id}")

    def log_trade(self, trade: Dict):
        """记录成交记录"""
        # 验证必要字段
        required_fields = ['timestamp', 'side', 'price', 'amount', 'order_id']
        for field in required_fields:
            if field not in trade:
                self.logger.error(f"交易记录缺少必要字段: {field}")
                return
        
        # 确保数据类型正确
        try:
            trade['timestamp'] = float(trade['timestamp'])
            trade['price'] = float(trade['price'])
            trade['amount'] = float(trade['amount'])
        except (ValueError, TypeError) as e:
            self.logger.error(f"交易记录数据类型错误: {str(e)}")
            return
            
        # 添加到历史
        self.trade_history.append(trade)
        
        # 保持内存中只保留最近100条
        if len(self.trade_history) > 100:
            # 这里的切片只是内存中的，保存时我们可能会保存更多或做归档
            # 但为了简单起见，且遵循原逻辑，我们只保留最新的
            self.trade_history = self.trade_history[-100:]
            
        # 保存到持久化存储
        self.persistence.save_trade_history(self.trade_history)
        self.logger.info(f"记录新交易: {trade['side']} {trade['amount']} @ {trade['price']}")

    def get_trade_history(self) -> List[Dict]:
        """获取交易历史"""
        return self.trade_history

    def get_statistics(self) -> Dict:
        """获取交易统计信息"""
        try:
            if not self.trade_history:
                return self._empty_stats()
            
            trades = self.trade_history
            total_trades = len(trades)
            winning_trades = len([t for t in trades if t.get('profit', 0) > 0])
            total_profit = sum(t.get('profit', 0) for t in trades)
            profits = [t.get('profit', 0) for t in trades]
            
            # 计算最大连续盈利和亏损
            current_streak = 1
            max_win_streak = 0
            max_loss_streak = 0
            
            if len(profits) > 0:
                for i in range(1, len(profits)):
                    prev = profits[i-1]
                    curr = profits[i]
                    if (curr > 0 and prev > 0) or (curr < 0 and prev < 0):
                        current_streak += 1
                    else:
                        if prev > 0:
                            max_win_streak = max(max_win_streak, current_streak)
                        elif prev < 0:
                            max_loss_streak = max(max_loss_streak, current_streak)
                        current_streak = 1
                
                # 处理最后一次 streaks
                if profits[-1] > 0:
                    max_win_streak = max(max_win_streak, current_streak)
                elif profits[-1] < 0:
                    max_loss_streak = max(max_loss_streak, current_streak)
            
            # 盈亏因子
            gross_profit = sum(p for p in profits if p > 0)
            gross_loss = abs(sum(p for p in profits if p < 0))
            profit_factor = gross_profit / gross_loss if gross_loss != 0 else float('inf')
            
            return {
                'total_trades': total_trades,
                'win_rate': winning_trades / total_trades if total_trades > 0 else 0,
                'total_profit': total_profit,
                'avg_profit': total_profit / total_trades if total_trades > 0 else 0,
                'max_profit': max(profits) if profits else 0,
                'max_loss': min(profits) if profits else 0,
                'profit_factor': profit_factor,
                'consecutive_wins': max_win_streak,
                'consecutive_losses': max_loss_streak
            }
            
        except Exception as e:
            self.logger.error(f"计算统计信息失败: {str(e)}")
            return self._empty_stats()

    def _empty_stats(self):
        return {
            'total_trades': 0, 'win_rate': 0, 'total_profit': 0,
            'avg_profit': 0, 'max_profit': 0, 'max_loss': 0,
            'profit_factor': 0, 'consecutive_wins': 0, 'consecutive_losses': 0
        }

    def archive_old_trades(self):
        """归档旧交易记录 (调用持久化服务)"""
        self.trade_history = self.persistence.archive_old_trades(self.trade_history)


# 导出
__all__ = ['OrderThrottler', 'OrderManager']
