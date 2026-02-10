"""
S1 仓位控制策略模块
Based on PositionControllerS1 logic
"""
import time
import asyncio
import logging
import math
import traceback
from typing import Optional, Dict

from ..config.settings import TradingConfig


class S1Strategy:
    """S1 仓位控制策略"""
    
    def __init__(self, config: TradingConfig, risk_manager):
        """
        初始化S1仓位策略
        
        Args:
            config: 交易配置
            risk_manager: 风险管理器实例
        """
        self.config = config
        self.risk_manager = risk_manager
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 策略参数
        self.lookback = getattr(config, 'S1_LOOKBACK', 52)
        self.sell_target_pct = getattr(config, 'S1_SELL_TARGET_PCT', 0.50)
        self.buy_target_pct = getattr(config, 'S1_BUY_TARGET_PCT', 0.70)
        
        # 状态
        self.daily_high = None
        self.daily_low = None
        self.last_update_ts = 0
        self.update_interval = 23.9 * 60 * 60  # 接近24小时
        
        # 交易回调函数 (将由外部注入)
        self.executor = None
        
    def set_executor(self, executor):
        """设置执行器 (回调函数)"""
        self.executor = executor
        
    async def update_daily_levels(self, exchange, symbol: str):
        """更新每日高低点"""
        now = time.time()
        if now - self.last_update_ts >= self.update_interval:
            self.logger.info("S1: 更新每日高低点...")
            try:
                # 获取数据
                limit = self.lookback + 2
                klines = await exchange.fetch_ohlcv(symbol, '1d', limit)
                
                if not klines or len(klines) < self.lookback + 1:
                    self.logger.warning(f"S1: K线数据不足 ({len(klines)}), 无法更新.")
                    return
                
                # 使用倒数第2根向前推 (不含最新未完成K线)
                relevant_klines = klines[-(self.lookback + 1) : -1]
                
                if len(relevant_klines) < self.lookback:
                    self.logger.warning(f"S1: 有效K线不足 ({len(relevant_klines)}).")
                    return
                
                # 计算高低点 [timestamp, open, high, low, close, volume]
                self.daily_high = max(float(k[2]) for k in relevant_klines)
                self.daily_low = min(float(k[3]) for k in relevant_klines)
                self.last_update_ts = now
                
                self.logger.info(
                    f"S1 高低点更新 | "
                    f"High: {self.daily_high:.4f} | "
                    f"Low: {self.daily_low:.4f}"
                )
                
            except Exception as e:
                self.logger.error(f"S1: 更新每日高低点失败: {str(e)}", exc_info=True)

    async def check_and_execute(self, current_price: float, balance_service, symbol: str):
        """
        检查并执行仓位调整
        
        Args:
            current_price: 当前价格
            balance_service: 余额服务实例
            symbol: 交易对符号
        """
        # 确保数据已更新
        if self.daily_high is None or self.daily_low is None:
            return
            
        if not self.executor:
            self.logger.warning("S1: 未设置执行器，无法执行操作")
            return

        try:
            # 获取当前仓位信息
            position_pct = await balance_service.get_position_ratio(current_price)
            total_assets = await balance_service.get_total_assets(current_price)
            position_value = position_pct * total_assets # 近似计算
            
            # 获取基础币种余额
            base_currency = getattr(self.config, 'BASE_CURRENCY', 'OKB')
            coin_balance = await balance_service.get_available_balance(base_currency)

            action = 'NONE'
            trade_amount = 0.0
            
            # 高点检查 -> 卖出
            if current_price > self.daily_high and position_pct > self.sell_target_pct:
                action = 'SELL'
                target_value = total_assets * self.sell_target_pct
                sell_value = position_value - target_value
                
                if sell_value > 0:
                    trade_amount = min(sell_value / current_price, coin_balance)
                    self.logger.info(
                        f"S1: 触及高点 | 需要卖出 {trade_amount:.4f} {base_currency} "
                        f"以达到 {self.sell_target_pct:.0%} 目标"
                    )
            
            # 低点检查 -> 买入
            elif current_price < self.daily_low and position_pct < self.buy_target_pct:
                action = 'BUY'
                target_value = total_assets * self.buy_target_pct
                buy_value = target_value - position_value
                
                if buy_value > 0:
                    trade_amount = buy_value / current_price
                    self.logger.info(
                        f"S1: 触及低点 | 需要买入 {trade_amount:.4f} {base_currency} "
                        f"以达到 {self.buy_target_pct:.0%} 目标"
                    )

            # 执行操作
            if action != 'NONE' and trade_amount > 1e-6:
                success = await self.executor(action, trade_amount, current_price)
                if success:
                    self.logger.info(f"S1: {action} 调整执行成功")
                else:
                    self.logger.warning(f"S1: {action} 调整执行失败")
                    
        except Exception as e:
            self.logger.error(f"S1: 检查执行失败: {str(e)}", exc_info=True)


# 导出
__all__ = ['S1Strategy']
