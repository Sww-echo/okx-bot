"""
趋势指标模块
包含 MA, MACD, ADX 等指标
"""
import logging
import traceback
import numpy as np
import pandas as pd
from typing import Optional, Tuple, List, Dict

from ..config.constants import SYMBOL


class TrendIndicators:
    """趋势指标计算器"""

    def __init__(self, exchange):
        self.exchange = exchange
        self.logger = logging.getLogger(self.__class__.__name__)

    async def get_ma_data(self, short_period: int = 20, long_period: int = 50) -> Tuple[Optional[float], Optional[float]]:
        """
        获取移动平均线 (MA) 数据
        
        Args:
            short_period: 短期周期
            long_period: 长期周期
            
        Returns:
            (短期MA, 长期MA)
        """
        try:
            # 获取K线数据
            klines = await self.exchange.fetch_ohlcv(
                SYMBOL, 
                timeframe='1H',
                limit=long_period + 10  # 多获取一些数据以确保计算准确
            )
            
            if not klines or len(klines) < long_period:
                return None, None
            
            # 提取收盘价
            closes = [float(x[4]) for x in klines]
            
            # 计算短期和长期MA
            short_ma = np.mean(closes[-short_period:])
            long_ma = np.mean(closes[-long_period:])
            
            return float(short_ma), float(long_ma)
            
        except Exception as e:
            self.logger.error(f"获取MA数据失败: {str(e)} | 堆栈信息: {traceback.format_exc()}")
            return None, None

    async def get_macd_data(self) -> Tuple[Optional[float], Optional[float]]:
        """
        获取 MACD 数据
        
        Returns:
            (MACD线, 信号线)
        """
        try:
            # 获取K线数据
            klines = await self.exchange.fetch_ohlcv(
                SYMBOL,
                timeframe='1H',
                limit=100  # MACD需要更多数据来计算
            )
            
            if not klines or len(klines) < 26:
                return None, None
            
            # 提取收盘价
            closes = pd.Series([float(x[4]) for x in klines])
            
            # 计算EMA12和EMA26
            ema12 = closes.ewm(span=12, adjust=False).mean()
            ema26 = closes.ewm(span=26, adjust=False).mean()
            
            # 计算MACD线
            macd_line = ema12 - ema26
            
            # 计算信号线（MACD的9日EMA）
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            
            return float(macd_line.iloc[-1]), float(signal_line.iloc[-1])
            
        except Exception as e:
            self.logger.error(f"获取MACD数据失败: {str(e)} | 堆栈信息: {traceback.format_exc()}")
            return None, None

    async def get_adx_data(self, period: int = 14) -> Optional[float]:
        """
        获取 ADX 数据
        
        Args:
            period: 周期
            
        Returns:
            ADX值
        """
        try:
            # 获取K线数据
            klines = await self.exchange.fetch_ohlcv(
                SYMBOL,
                timeframe='1H',
                limit=period * 2
            )
            
            if not klines or len(klines) < period + 1:
                return None
            
            highs = np.array([float(x[2]) for x in klines])
            lows = np.array([float(x[3]) for x in klines])
            closes = np.array([float(x[4]) for x in klines])
            
            # 计算TR
            tr1 = highs[1:] - lows[1:]
            tr2 = np.abs(highs[1:] - closes[:-1])
            tr3 = np.abs(lows[1:] - closes[:-1])
            tr = np.maximum(np.maximum(tr1, tr2), tr3)
            
            # 计算DM
            up_move = highs[1:] - highs[:-1]
            down_move = lows[:-1] - lows[1:]
            
            plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
            minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
            
            # 平滑处理
            def smooth(data, period):
                res = np.zeros_like(data)
                res[period-1] = np.mean(data[:period])
                for i in range(period, len(data)):
                    res[i] = (res[i-1] * (period-1) + data[i]) / period
                return res
            
            atr = smooth(tr, period)
            plus_di = 100 * smooth(plus_dm, period) / atr
            minus_di = 100 * smooth(minus_dm, period) / atr
            
            # 计算DX和ADX
            dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
            adx = smooth(dx, period)
            
            # 防止除以零
            if np.isnan(adx[-1]):
                return 0.0
                
            return float(adx[-1])
            
        except Exception as e:
            self.logger.error(f"获取ADX数据失败: {str(e)} | 堆栈信息: {traceback.format_exc()}")
            return None

    def calculate_bollinger_bands(self, closes: List[float], window: int = 20, num_std: float = 2.0) -> Dict[str, float]:
        """
        计算布林带
        
        Args:
            closes: 收盘价列表
            window: 窗口大小
            num_std: 标准差倍数
            
        Returns:
            {'upper': 上轨, 'middle': 中轨, 'lower': 下轨}
        """
        if len(closes) < window:
            return {'upper': 0, 'middle': 0, 'lower': 0}
            
        prices = pd.Series(closes)
        middle = prices.rolling(window=window).mean().iloc[-1]
        std = prices.rolling(window=window).std().iloc[-1]
        
        upper = middle + (std * num_std)
        lower = middle - (std * num_std)
        
        return {
            'upper': float(upper),
            'middle': float(middle),
            'lower': float(lower)
        }



    def calculate_ema(self, closes: List[float], period: int) -> float:
        """计算EMA"""
        if len(closes) < period:
            return 0.0
        return float(pd.Series(closes).ewm(span=period, adjust=False).mean().iloc[-1])

    async def get_six_line_data(self, timeframe: str = '1H', limit: int = 200) -> Dict[str, float]:
        """获取6条均线数据 (MA20/60/120 + EMA20/60/120)"""
        try:
            klines = await self.exchange.fetch_ohlcv(SYMBOL, timeframe=timeframe, limit=limit)
            if not klines or len(klines) < 120:
                return {}
            
            closes = [float(x[4]) for x in klines]
            
            # MA (Simple)
            ma20 = float(np.mean(closes[-20:]))
            ma60 = float(np.mean(closes[-60:]))
            ma120 = float(np.mean(closes[-120:]))
            
            # EMA (Exponential)
            ema20 = self.calculate_ema(closes, 20)
            ema60 = self.calculate_ema(closes, 60)
            ema120 = self.calculate_ema(closes, 120)
            
            last_kline = klines[-1]
            return {
                'MA20': ma20, 'MA60': ma60, 'MA120': ma120,
                'EMA20': ema20, 'EMA60': ema60, 'EMA120': ema120,
                'open': float(last_kline[1]),
                'high': float(last_kline[2]),
                'low': float(last_kline[3]),
                'close': float(last_kline[4]),
                'volume': float(last_kline[5])
            }
        except Exception as e:
            self.logger.error(f"获取6线数据失败: {e}")
            return {}

    def detect_squeeze(self, lines: Dict[str, float], threshold_pct: float = 0.01) -> bool:
        """
        检测均线密集 (基于标准差/均值)
        
        Args:
            lines: get_six_line_data 返回的字典
            threshold_pct: 密集阈值 (默认1%)
        """
        if not lines: return False
        # 只看均线 (MA/EMA)
        target_keys = ['MA20', 'MA60', 'MA120', 'EMA20', 'EMA60', 'EMA120']
        values = [v for k, v in lines.items() if k in target_keys]
        if not values: return False
        
        std = np.std(values)
        mean = np.mean(values)
        
        # 变异系数 < 阈值
        is_squeeze = (std / mean) < threshold_pct
        return bool(is_squeeze)

    def detect_alignment(self, lines: Dict[str, float]) -> str:
        """
        检测均线排列状态
        
        Returns:
            'long' (多头排列), 'short' (空头排列), 'none' (无序)
        """
        if not lines: return 'none'
        
        # 多头排列: 短 > 中 > 长
        # 严格模式：所有短周期 > 所有中周期 > 所有长周期
        # 宽松模式 (这里采用)：EMA20 > EMA60 > EMA120 且 MA20 > MA60 > MA120
        
        long_cond = (lines['EMA20'] > lines['EMA60'] > lines['EMA120']) or \
                    (lines['MA20'] > lines['MA60'] > lines['MA120'])
                    
        short_cond = (lines['EMA20'] < lines['EMA60'] < lines['EMA120']) or \
                     (lines['MA20'] < lines['MA60'] < lines['MA120'])
                     
        if long_cond: return 'long'
        if short_cond: return 'short'
        return 'none'


# 导出
__all__ = ['TrendIndicators']
