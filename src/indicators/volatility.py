"""
波动率指标模块
处理价格波动率计算
"""
import logging
import traceback
import numpy as np
from typing import Optional, List, Dict, Any

from ..config.constants import VOLATILITY_WINDOW, SYMBOL


class VolatilityCalculator:
    """波动率计算器"""

    def __init__(self, exchange):
        self.exchange = exchange
        self.logger = logging.getLogger(self.__class__.__name__)
        self.window = VOLATILITY_WINDOW

    async def calculate_volatility(self) -> float:
        """
        计算价格波动率
        基于历史K线数据的对数收益率标准差
        """
        try:
            # 获取K线数据
            klines = await self.exchange.fetch_ohlcv(
                SYMBOL, 
                timeframe='1H',
                limit=self.window
            )
            
            if not klines:
                return 0.0
                
            # 提取收盘价
            prices = [float(k[4]) for k in klines]
            
            if len(prices) < 2:
                return 0.0
            
            # 计算对数收益率
            # ln(P_t / P_{t-1})
            returns = np.diff(np.log(prices))
            
            # 计算标准差并年化
            # 假设一年365天，每天24小时
            volatility = np.std(returns) * np.sqrt(24 * 365)
            
            self.logger.debug(f"计算出的波动率: {volatility:.5f}")
            return float(volatility)
            
        except Exception as e:
            self.logger.error(f"计算波动率失败: {str(e)} | 堆栈信息: {traceback.format_exc()}")
            return 0.0

    async def get_volatility_status(self) -> Dict[str, Any]:
        """获取波动率状态信息"""
        vol = await self.calculate_volatility()
        return {
            'value': vol,
            'level': self._get_volatility_level(vol),
            'timestamp': 0  # 调用方填充
        }

    def _get_volatility_level(self, volatility: float) -> str:
        """获取波动率等级"""
        if volatility < 0.2:
            return 'LOW'
        elif volatility < 0.6:
            return 'MEDIUM'
        elif volatility < 1.0:
            return 'HIGH'
        else:
            return 'EXTREME'


# 导出
__all__ = ['VolatilityCalculator']
