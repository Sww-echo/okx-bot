"""
风险管理模块
包含多层风控检查逻辑
"""
import logging
import traceback
from typing import Optional, Dict

from ..config.settings import TradingConfig


class RiskManager:
    """高级风控管理器"""
    
    def __init__(self, config: TradingConfig, exchange, balance_service):
        self.config = config
        self.exchange = exchange
        self.balance_service = balance_service
        self.logger = logging.getLogger(self.__class__.__name__)
        self.last_position_ratio = 0.0
    
    async def multi_layer_check(self, current_price: float) -> bool:
        """
        执行多层风控检查
        
        Args:
            current_price: 当前价格
            
        Returns:
            如果触发风控（需要暂停交易或采取措施）返回 True，否则返回 False
        """
        try:
            # 1. 仓位比例检查
            position_ratio = await self.balance_service.get_position_ratio(current_price)
            
            # 只在仓位比例变化超过0.1%时打印日志
            if abs(position_ratio - self.last_position_ratio) > 0.001:
                self.logger.info(
                    f"风控检查 | "
                    f"当前仓位比例: {position_ratio:.2%} | "
                    f"最大允许比例: {self.config.MAX_POSITION_RATIO:.2%} | "
                    f"最小底仓比例: {self.config.MIN_POSITION_RATIO:.2%}"
                )
                self.last_position_ratio = position_ratio
            
            # 2. 底仓保护检查
            if position_ratio < self.config.MIN_POSITION_RATIO:
                self.logger.warning(f"底仓保护触发 | 当前: {position_ratio:.2%} < 最小: {self.config.MIN_POSITION_RATIO:.2%}")
                # 底仓不足不一定需要暂停交易，可能需要买入补充，但在风控层面我们标记为异常
                # 暂时放行，由策略层决定是否补仓
                return False
            
            # 3. 仓位超限检查
            if position_ratio > self.config.MAX_POSITION_RATIO:
                self.logger.warning(f"仓位超限 | 当前: {position_ratio:.2%} > 最大: {self.config.MAX_POSITION_RATIO:.2%}")
                return True
            
            # 4. 每日亏损限制检查 (TODO: 需要交易历史数据支持)
            # daily_loss = await self._calculate_daily_loss()
            # if daily_loss < self.config.DAILY_LOSS_LIMIT:
            #     self.logger.critical(f"触发每日亏损限制: {daily_loss:.2%}")
            #     return True

            return False
            
        except Exception as e:
            self.logger.error(f"风控检查失败: {str(e)} | 堆栈信息: {traceback.format_exc()}")
            # 发生异常时，为了安全起见，通常也应该视为风控不通过
            return True
    
    async def check_market_sentiment(self) -> None:
        """
        检查市场情绪指标并动态调整风险系数
        (此功能目前为预留接口)
        """
        pass
        # try:
        #     fear_greed = await self._get_fear_greed_index()
        #     if fear_greed < 20:  # 极度恐惧
        #         self.config.RISK_FACTOR *= 0.5  # 降低风险系数
        #     elif fear_greed > 80:  # 极度贪婪
        #         self.config.RISK_FACTOR *= 1.2  # 提高风险系数
        # except Exception as e:
        #     self.logger.error(f"获取市场情绪失败: {str(e)}")


# 导出
__all__ = ['RiskManager']
