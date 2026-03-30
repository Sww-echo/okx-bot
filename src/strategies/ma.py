"""
双均线趋势策略 (MA Strategy)
基于 6 条均线 (MA20/60/120 + EMA20/60/120) 的趋势跟随策略
"""
import logging
from enum import Enum
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass

from ..config.settings import MAConfig
from ..indicators.trend import TrendIndicators

class MarketState(Enum):
    IDLE = "IDLE"                       # 无特殊状态
    SQUEEZE = "SQUEEZE"                 # 均线密集
    TREND_LONG = "TREND_LONG"           # 多头趋势
    TREND_SHORT = "TREND_SHORT"         # 空头趋势

@dataclass
class Signal:
    """交易信号"""
    type: str           # 'OPEN_LONG', 'OPEN_SHORT', 'CLOSE_LONG', 'CLOSE_SHORT', 'NONE'
    price: float
    reason: str
    stop_loss: float = 0.0
    take_profit: float = 0.0
    strategy_id: str = "" # 'A': 密集突破, 'B': 回踩MA20
    trailing_stop: bool = True  # 是否启用移动止损

class MAStrategy:
    """双均线趋势策略核心逻辑"""
    
    def __init__(self, config: MAConfig):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 状态记录
        self.current_state = MarketState.IDLE
        self.last_squeeze_high = 0.0
        self.last_squeeze_low = 0.0
        self.squeeze_cooldown = 0
        self.breakout_bars_count = 0          # 连续突破K线计数
        self.breakout_direction = None        # 'long' or 'short'
        
    async def analyze(self, indicators: TrendIndicators) -> Signal:
        """
        分析市场并生成信号 (每K线收盘调用一次，或轮询调用)
        """
        # 1. 获取 6 线数据 ( + OHLC)
        # 需确保数据量足够计算最大周期均线 (默认120)
        required_limit = max(self.config.PERIODS) + 50
        lines = await indicators.get_six_line_data(
            timeframe=self.config.TIMEFRAME,
            limit=required_limit
        )
        
        if not lines:
            return Signal('NONE', 0.0, "数据不足")
            
        current_price = lines['close']
        high_price = lines['high']
        low_price = lines['low']
        
        # 2. 市场状态识别
        # 密集检测
        # SQUEEZE_PERCENTILE / 1000 = 变异系数阈值
        is_squeeze = indicators.detect_squeeze(lines, self.config.SQUEEZE_PERCENTILE / 1000)
        
        if is_squeeze:
            self.logger.info(f"Squeeze detected at {current_price:.2f}")

        # 排列检测
        alignment = indicators.detect_alignment(lines)
        
        # 状态机更新
        previous_state = self.current_state
        
        if is_squeeze:
            self.current_state = MarketState.SQUEEZE
            # 更新密集区范围 (取所有均线的最大最小值)
            ma_values = [v for k,v in lines.items() if k in ['MA20','MA60','MA120','EMA20','EMA60','EMA120']]
            if ma_values:
                self.last_squeeze_high = max(ma_values)
                self.last_squeeze_low = min(ma_values)
                self.squeeze_cooldown = 20 # 密集状态结束后，保留20个周期
        
        elif alignment == 'long':
            self.current_state = MarketState.TREND_LONG
            if self.squeeze_cooldown > 0: self.squeeze_cooldown -= 1
            
        elif alignment == 'short':
            self.current_state = MarketState.TREND_SHORT
            if self.squeeze_cooldown > 0: self.squeeze_cooldown -= 1
            
        else:
            # 既不密集也无序
            self.current_state = MarketState.IDLE
            if self.squeeze_cooldown > 0: self.squeeze_cooldown -= 1

        # 预测趋势与状态机... 
        
        # 获取额外指标 (根据开关)
        adx = None
        if self.config.ADX_FILTER_ENABLED:
            adx = await indicators.get_adx_data(period=14)
            
        macd_hist = None
        if self.config.MACD_FILTER_ENABLED:
            macd_line, signal_line = await indicators.get_macd_data()
            if macd_line is not None and signal_line is not None:
                macd_hist = macd_line - signal_line

        # ==================== 策略 A: 密集突破 ====================
        if self.squeeze_cooldown > 0:
            if self.current_state == MarketState.TREND_LONG:
                if current_price > self.last_squeeze_high * (1 + self.config.BREAKOUT_THRESHOLD):
                    
                    # 成交量过滤: 突破需爆量
                    vol_ok = True
                    if self.config.VOLUME_CONFIRM_ENABLED:
                        current_vol = lines.get('volume', 0)
                        vol_ma = lines.get('volume_ma', 0)
                        if vol_ma > 0 and current_vol < vol_ma * self.config.VOLUME_MULTIPLIER:
                            vol_ok = False
                            
                    if vol_ok:
                        if self.breakout_direction == 'long':
                            self.breakout_bars_count += 1
                        else:
                            self.breakout_direction = 'long'
                            self.breakout_bars_count = 1
                        
                        if self.breakout_bars_count >= self.config.BREAKOUT_BARS:
                            self.breakout_bars_count = 0
                            self.breakout_direction = None
                            return self._create_signal(
                                'OPEN_LONG', current_price, 
                                f"策略A: 密集突破确认 (量能OK, High: {self.last_squeeze_high:.2f})", 
                                'A', stop_loss_price=self.last_squeeze_low
                            )
                else:
                    if self.breakout_direction == 'long':
                        self.breakout_bars_count = 0
                        self.breakout_direction = None
            
            elif self.current_state == MarketState.TREND_SHORT:
                if current_price < self.last_squeeze_low * (1 - self.config.BREAKOUT_THRESHOLD):
                    
                    vol_ok = True
                    if self.config.VOLUME_CONFIRM_ENABLED:
                        current_vol = lines.get('volume', 0)
                        vol_ma = lines.get('volume_ma', 0)
                        if vol_ma > 0 and current_vol < vol_ma * self.config.VOLUME_MULTIPLIER:
                            vol_ok = False
                            
                    if vol_ok:
                        if self.breakout_direction == 'short':
                            self.breakout_bars_count += 1
                        else:
                            self.breakout_direction = 'short'
                            self.breakout_bars_count = 1
                        
                        if self.breakout_bars_count >= self.config.BREAKOUT_BARS:
                            self.breakout_bars_count = 0
                            self.breakout_direction = None
                            return self._create_signal(
                                'OPEN_SHORT', current_price, 
                                f"策略A: 密集跌破确认 (量能OK, Low: {self.last_squeeze_low:.2f})", 
                                'A', stop_loss_price=self.last_squeeze_high
                            )
                else:
                    if self.breakout_direction == 'short':
                        self.breakout_bars_count = 0
                        self.breakout_direction = None

        # ==================== 策略 B: MA20 回踩 ====================
        # 拦截过滤
        adx_ok = True
        if self.config.ADX_FILTER_ENABLED and adx is not None and adx < self.config.ADX_MIN:
            adx_ok = False
            
        macd_ok = True
        if self.config.MACD_FILTER_ENABLED and macd_hist is not None:
            if self.current_state == MarketState.TREND_LONG and macd_hist < 0:
                macd_ok = False  # 多头回踩但动能转空 -> 高危
            elif self.current_state == MarketState.TREND_SHORT and macd_hist > 0:
                macd_ok = False  # 空头回弹但动能转多 -> 高危
                
        if adx_ok and macd_ok:
            ma20 = lines['MA20']
            atr = lines.get('ATR', 0)
            
            touch_tol = ma20 * self.config.MA20_TOUCH_TOLERANCE

            if self.current_state == MarketState.TREND_LONG:
                if low_price <= (ma20 + touch_tol) and current_price >= (ma20 - touch_tol):
                     sl_distance = atr * self.config.ATR_MULTIPLIER if atr > 0 else ma20 * 0.02
                     filter_info = f"ADX:{adx:.1f}" if adx else ""
                     return self._create_signal(
                         'OPEN_LONG', current_price,
                         f"策略B: 上涨回踩 (MA20:{ma20:.2f}, tol:{self.config.MA20_TOUCH_TOLERANCE:.4f} {filter_info})",
                         'B', stop_loss_price=ma20 - sl_distance
                     )

            if self.current_state == MarketState.TREND_SHORT:
                if high_price >= (ma20 - touch_tol) and current_price <= (ma20 + touch_tol):
                    sl_distance = atr * self.config.ATR_MULTIPLIER if atr > 0 else ma20 * 0.02
                    filter_info = f"ADX:{adx:.1f}" if adx else ""
                    return self._create_signal(
                        'OPEN_SHORT', current_price,
                        f"策略B: 下跌受阻 (MA20:{ma20:.2f}, tol:{self.config.MA20_TOUCH_TOLERANCE:.4f} {filter_info})",
                        'B', stop_loss_price=ma20 + sl_distance
                    )
                
        return Signal('NONE', current_price, "观察中")

    def _create_signal(self, type: str, price: float, reason: str, strategy_id: str, stop_loss_price: float = 0.0) -> Signal:
        """生成交易信号"""
        sl = stop_loss_price
        tp = 0.0
        
        # 如果未指定止损价，使用默认百分比
        risk_pct = self.config.RISK_PER_TRADE
        
        if 'LONG' in type:
            if sl <= 0: sl = price * (1 - risk_pct)
            # 止盈 = 开仓 + (开仓-止损)*盈亏比
            risk_dist = price - sl
            tp = price + (risk_dist * self.config.TP_RATIO)
            
        elif 'SHORT' in type:
            if sl <= 0: sl = price * (1 + risk_pct)
            risk_dist = sl - price
            tp = price - (risk_dist * self.config.TP_RATIO)
            
        return Signal(type, price, reason, sl, tp, strategy_id, trailing_stop=self.config.TRAILING_STOP_ENABLED)

