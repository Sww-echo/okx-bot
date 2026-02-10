"""
配置文件兼容层
此文件保留是为了兼容旧代码，将请求转发到新的 src/config 模块
"""
from src.config.constants import *
from src.config.settings import TradingConfig, GridParams, RiskParams, DynamicIntervalParams

# 重新导出所有内容，确保旧代码引用 config.py 能正常工作
__all__ = [
    # 常量
    'BASE_SYMBOL', 'QUOTE_SYMBOL', 'SYMBOL', 'BASE_CURRENCY',
    'FLAG',
    'INITIAL_GRID', 'FLIP_THRESHOLD', 'POSITION_SCALE_FACTOR',
    'MIN_TRADE_AMOUNT', 'MIN_POSITION_PERCENT', 'MAX_POSITION_PERCENT',
    'COOLDOWN', 'SAFETY_MARGIN',
    'MAX_DRAWDOWN', 'DAILY_LOSS_LIMIT', 'MAX_POSITION_RATIO', 'MIN_POSITION_RATIO',
    'RISK_CHECK_INTERVAL', 'MAX_RETRIES', 'RISK_FACTOR', 'VOLATILITY_WINDOW',
    'PUSHPLUS_TOKEN',
    'LOG_LEVEL', 'DEBUG_MODE',
    'API_TIMEOUT', 'RECV_WINDOW',
    'INITIAL_BASE_PRICE', 'INITIAL_PRINCIPAL',
    
    # 类
    'TradingConfig', 'GridParams', 'RiskParams', 'DynamicIntervalParams'
]
