"""
常量定义模块
包含所有全局常量，保持与原 config.py 兼容
"""
import os
from dotenv import load_dotenv
import logging

load_dotenv()

# ==================== 交易对配置 ====================
# ==================== 交易对配置 ====================
BASE_SYMBOL = os.getenv('BASE_SYMBOL', 'OKB')  # 基础币种
QUOTE_SYMBOL = os.getenv('QUOTE_SYMBOL', 'USDT')  # 计价币种
SYMBOL = f"{BASE_SYMBOL}-{QUOTE_SYMBOL}"  # OKX使用-而不是/作为分隔符
BASE_CURRENCY = BASE_SYMBOL

# ==================== 运行模式 ====================
FLAG = '1'  # 0为实盘，1为模拟

# ==================== 交易类型配置 ====================
# 'spot' = 现货交易, 'swap' = 永续合约
TRADE_MODE = os.getenv('TRADE_MODE', 'spot').lower()

# 合约专用交易对（永续合约格式）
SWAP_SYMBOL = f"{BASE_SYMBOL}-{QUOTE_SYMBOL}-SWAP"

# 保证金模式：'cross' = 全仓, 'isolated' = 逐仓
MARGIN_MODE = os.getenv('MARGIN_MODE', 'cross').lower()

# 持仓方向：'long' = 只做多, 'short' = 只做空, 'net' = 单向持仓, 'both' = 双向持仓
POS_SIDE = os.getenv('POS_SIDE', 'net').lower()

# 杠杆倍数
LEVERAGE = int(os.getenv('LEVERAGE', '5'))

# ==================== 网格参数 ====================
INITIAL_GRID = 0.5
FLIP_THRESHOLD = lambda grid_size: (grid_size / 5) / 100  # 网格大小的1/5的1%
POSITION_SCALE_FACTOR = 0.2  # 仓位调整系数（20%）

# ==================== 交易限制 ====================
MIN_TRADE_AMOUNT = 20.0  # 新下限
MIN_POSITION_PERCENT = 0.05  # 最小交易比例（总资产的5%）
MAX_POSITION_PERCENT = 0.15  # 最大交易比例（总资产的15%）
COOLDOWN = 60
SAFETY_MARGIN = 0.95

# ==================== 风控参数 ====================
MAX_DRAWDOWN = -0.15
DAILY_LOSS_LIMIT = -0.05
MAX_POSITION_RATIO = 0.9  # 最大仓位比例 (90%)，保留10%底仓
MIN_POSITION_RATIO = 0.1  # 最小仓位比例 (10%)，底仓
RISK_CHECK_INTERVAL = 300  # 5分钟检查一次风控
MAX_RETRIES = 5  # 最大重试次数
RISK_FACTOR = 0.1  # 风险系数（10%）
VOLATILITY_WINDOW = 24  # 波动率计算周期（小时）
MAX_CONSECUTIVE_LOSSES = 5  # 连续亏损保护阈值
LOSS_COOLDOWN = 300  # 连续亏损触发后冷却时间（秒）

# ==================== 通知配置 ====================
DINGTALK_WEBHOOK = os.getenv('DINGTALK_WEBHOOK')
DINGTALK_SECRET = os.getenv('DINGTALK_SECRET')
WECHAT_WEBHOOK = os.getenv('WECHAT_WEBHOOK')
BARK_KEY = os.getenv('BARK_KEY')
BARK_SERVER = os.getenv('BARK_SERVER', 'https://api.day.app')

# ==================== 日志配置 ====================
LOG_LEVEL = logging.DEBUG  # 设置为DEBUG显示详细日志
DEBUG_MODE = True  # 设置为True时显示详细日志

# ==================== API配置 ====================
API_TIMEOUT = 10000  # API超时时间（毫秒）
RECV_WINDOW = 5000  # 接收窗口时间（毫秒）

# ==================== 环境变量配置 ====================
try:
    INITIAL_BASE_PRICE = float(os.getenv('INITIAL_BASE_PRICE', 0))
except ValueError:
    INITIAL_BASE_PRICE = 0
    logging.warning("无效的INITIAL_BASE_PRICE配置，已重置为0")

try:
    INITIAL_PRINCIPAL = float(os.getenv('INITIAL_PRINCIPAL', 0))
    if INITIAL_PRINCIPAL <= 0:
        logging.warning("INITIAL_PRINCIPAL 必须为正数，已重置为0")
        INITIAL_PRINCIPAL = 0
except ValueError:
    INITIAL_PRINCIPAL = 0
    logging.warning("无效的INITIAL_PRINCIPAL配置，已重置为0")

# ==================== 策略模式 ====================
# 'grid' = 网格合约策略, 'ma' = 双均线趋势策略
STRATEGY_MODE = os.getenv('STRATEGY_MODE', 'grid').lower()

# ==================== MA 策略参数 ====================
MA_TIMEFRAME = os.getenv('MA_TIMEFRAME', '1H')           # K线周期
MA_PERIODS = [20, 60, 120]                                # 均线周期
MA_RISK_PER_TRADE = float(os.getenv('MA_RISK_PER_TRADE', '0.02'))  # 单笔最大亏损比例
MA_TP_RATIO = float(os.getenv('MA_TP_RATIO', '3.0'))      # 止盈盈亏比
MA_MAX_LEVERAGE = int(os.getenv('MA_MAX_LEVERAGE', '3'))   # 最大实际杠杆
MA_SQUEEZE_LOOKBACK = int(os.getenv('MA_SQUEEZE_LOOKBACK', '20'))  # 密集检测回看周期

# ==================== 导出所有常量 ====================
__all__ = [
    'BASE_SYMBOL', 'QUOTE_SYMBOL', 'SYMBOL', 'BASE_CURRENCY',
    'FLAG',
    'TRADE_MODE', 'SWAP_SYMBOL', 'MARGIN_MODE', 'POS_SIDE', 'LEVERAGE',
    'INITIAL_GRID', 'FLIP_THRESHOLD', 'POSITION_SCALE_FACTOR',
    'MIN_TRADE_AMOUNT', 'MIN_POSITION_PERCENT', 'MAX_POSITION_PERCENT',
    'COOLDOWN', 'SAFETY_MARGIN',
    'MAX_DRAWDOWN', 'DAILY_LOSS_LIMIT', 'MAX_POSITION_RATIO', 'MIN_POSITION_RATIO',
    'RISK_CHECK_INTERVAL', 'MAX_RETRIES', 'RISK_FACTOR', 'VOLATILITY_WINDOW',
    'MAX_CONSECUTIVE_LOSSES', 'LOSS_COOLDOWN',
    'DINGTALK_WEBHOOK', 'DINGTALK_SECRET', 'WECHAT_WEBHOOK',
    'BARK_KEY', 'BARK_SERVER',
    'LOG_LEVEL', 'DEBUG_MODE',
    'API_TIMEOUT', 'RECV_WINDOW',
    'INITIAL_BASE_PRICE', 'INITIAL_PRINCIPAL',
    'STRATEGY_MODE',
    'MA_TIMEFRAME', 'MA_PERIODS', 'MA_RISK_PER_TRADE', 'MA_TP_RATIO',
    'MA_MAX_LEVERAGE', 'MA_SQUEEZE_LOOKBACK',
]
