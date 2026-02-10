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
        # 密集检测 (阈值: 20 -> 0.02)
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
                self.squeeze_cooldown = 20 # 密集状态结束后，保留20个周期的"前密集"记忆
        
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

        # ==================== 策略 A: 密集突破 ====================
        # 条件: 
        # 1. 最近曾处于密集状态 (squeeze_cooldown > 0)
        # 2. 当前趋势明确 (TREND_LONG/SHORT)
        # 3. 价格有效突破密集区高点/低点
        # 简化: 不做严格的回踩检测，只要突破且趋势确认即入场，止损设在密集区另一侧
        
        if self.squeeze_cooldown > 0:
            if self.current_state == MarketState.TREND_LONG:
                if current_price > self.last_squeeze_high * 1.001: # 略微突破
                    return self._create_signal(
                        'OPEN_LONG', current_price, 
                        f"策略A: 密集向上突破 (Range High: {self.last_squeeze_high:.2f})", 
                        'A', stop_loss_price=self.last_squeeze_low
                    )
            
            elif self.current_state == MarketState.TREND_SHORT:
                if current_price < self.last_squeeze_low * 0.999:
                    return self._create_signal(
                        'OPEN_SHORT', current_price, 
                        f"策略A: 密集向下突破 (Range Low: {self.last_squeeze_low:.2f})", 
                        'A', stop_loss_price=self.last_squeeze_high
                    )

        # ==================== 策略 B: MA20 回踩 (趋势中继) ====================
        # 条件:
        # 1. 处于多头/空头趋势
        # 2. 价格触及 MA20 (Low <= MA20 <= High)
        # 3. 收盘价确认 (多头 Close > MA20, 空头 Close < MA20) -> 证明支撑/压力有效
        # 4. MA20 方向需正确 (简单判断: MA20 > MA60)
        
        ma20 = lines['MA20']
        
        if self.current_state == MarketState.TREND_LONG:
            # 回踩支撑
            if low_price <= ma20 and current_price >= ma20:
                 # 可以增加过滤器: 如前一根K线也是多头排列
                 return self._create_signal(
                     'OPEN_LONG', current_price,
                     f"策略B: 上涨回踩MA20确认 (MA20: {ma20:.2f})",
                     'B', stop_loss_price=ma20 * 0.98 # 止损设在MA20下方2%? 或者使用ATR？
                     # 策略文档: "跌破MA20离场"
                     # 这里暂时设一个固定比例作为初始止损，后续由PositionTracker跟踪
                 )

        if self.current_state == MarketState.TREND_SHORT:
            # 反弹受阻
            if high_price >= ma20 and current_price <= ma20:
                return self._create_signal(
                    'OPEN_SHORT', current_price,
                    f"策略B: 下跌反弹MA20受阻 (MA20: {ma20:.2f})",
                    'B', stop_loss_price=ma20 * 1.02
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
            
        return Signal(type, price, reason, sl, tp, strategy_id)
