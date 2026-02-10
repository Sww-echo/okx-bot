"""
价格分析指标模块
处理价格位置分位、支撑阻力等分析
"""
import logging
import traceback
import numpy as np
from typing import Optional, List, Tuple

from ..config.constants import SYMBOL


class PriceAnalyzer:
    """价格分析器"""
    
    def __init__(self, exchange):
        self.exchange = exchange
        self.logger = logging.getLogger(self.__class__.__name__)
        
    async def get_price_percentile(self, period: str = '7d') -> float:
        """
        获取当前价格在历史中的分位位置
        (0.0 = 最低，1.0 = 最高)
        
        Args:
            period: 时间周期，默认为7天
            
        Returns:
            价格分位值 (0.0 - 1.0)
        """
        try:
            # 获取数据
            limit = 42  # 7天 * 6 (4小时K线)
            timeframe = '4h'
            
            ohlcv = await self.exchange.fetch_ohlcv(
                SYMBOL, 
                timeframe=timeframe, 
                limit=limit
            )
            
            if not ohlcv:
                return 0.5
                
            closes = [float(candle[4]) for candle in ohlcv]
            current_price = await self.exchange.fetch_ticker(SYMBOL)
            current_price = float(current_price['last'])
            
            # 排序价格
            sorted_prices = sorted(closes)
            
            # 数据不足时的处理
            if len(sorted_prices) < 10:
                self.logger.warning("历史数据不足，使用简化分位计算")
                mid_price = (sorted_prices[0] + sorted_prices[-1]) / 2
                return 0.5 if current_price >= mid_price else 0.0
            
            # 计算分位
            lower_quartile = sorted_prices[int(len(sorted_prices) * 0.25)]
            upper_quartile = sorted_prices[int(len(sorted_prices) * 0.75)]
            
            if current_price <= lower_quartile:
                return 0.0
            elif current_price >= upper_quartile:
                return 1.0
            else:
                # 线性插值
                return (current_price - lower_quartile) / (upper_quartile - lower_quartile)
                
        except Exception as e:
            self.logger.error(f"获取价格分位失败: {str(e)} | 堆栈信息: {traceback.format_exc()}")
            return 0.5
            
    async def get_support_resistance(self) -> Tuple[float, float]:
        """
        获取支撑位和阻力位
        基于近期高低点
        
        Returns:
            (支撑位, 阻力位)
        """
        try:
            ohlcv = await self.exchange.fetch_ohlcv(SYMBOL, '1d', limit=30)
            if not ohlcv:
                return 0, 0
                
            highs = [float(x[2]) for x in ohlcv]
            lows = [float(x[3]) for x in ohlcv]
            
            resistance = max(highs)
            support = min(lows)
            
            return support, resistance
            
        except Exception as e:
            self.logger.error(f"获取支撑阻力位失败: {str(e)}")
            return 0, 0


# 导出
__all__ = ['PriceAnalyzer']
