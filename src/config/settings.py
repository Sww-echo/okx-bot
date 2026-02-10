"""
配置类定义模块
提供结构化的配置管理
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any
import os
from dotenv import load_dotenv

from .constants import (
    BASE_SYMBOL, QUOTE_SYMBOL, SYMBOL, BASE_CURRENCY,
    FLAG,
    INITIAL_GRID, POSITION_SCALE_FACTOR,
    MIN_TRADE_AMOUNT, MIN_POSITION_PERCENT, MAX_POSITION_PERCENT,
    COOLDOWN, SAFETY_MARGIN,
    MAX_DRAWDOWN, DAILY_LOSS_LIMIT, MAX_POSITION_RATIO, MIN_POSITION_RATIO,
    RISK_CHECK_INTERVAL, MAX_RETRIES, RISK_FACTOR, VOLATILITY_WINDOW,
    API_TIMEOUT, RECV_WINDOW,
    INITIAL_BASE_PRICE, INITIAL_PRINCIPAL
)

load_dotenv()


@dataclass
class GridParams:
    """网格参数配置"""
    initial: float = INITIAL_GRID
    min: float = 1.0
    max: float = 4.0
    volatility_threshold: Dict[str, Any] = field(default_factory=lambda: {
        'ranges': [
            {'range': [0, 0.20], 'grid': 1.0},     # 波动率 0-20%，网格1.0%
            {'range': [0.20, 0.40], 'grid': 1.5},  # 波动率 20-40%，网格1.5%
            {'range': [0.40, 0.60], 'grid': 2.0},  # 波动率 40-60%，网格2.0%
            {'range': [0.60, 0.80], 'grid': 2.5},  # 波动率 60-80%，网格2.5%
            {'range': [0.80, 1.00], 'grid': 3.0},  # 波动率 80-100%，网格3.0%
            {'range': [1.00, 1.20], 'grid': 3.5},  # 波动率 100-120%，网格3.5%
            {'range': [1.20, 999], 'grid': 4.0}    # 波动率 >120%，网格4.0%
        ]
    })


@dataclass
class RiskParams:
    """风控参数配置"""
    max_drawdown: float = MAX_DRAWDOWN
    daily_loss_limit: float = DAILY_LOSS_LIMIT
    position_limit: float = MAX_POSITION_RATIO


@dataclass
class DynamicIntervalParams:
    """动态时间间隔参数"""
    volatility_to_interval_hours: List[Dict] = field(default_factory=lambda: [
        {'range': [0, 0.20], 'interval_hours': 1.0},
        {'range': [0.20, 0.40], 'interval_hours': 0.5},
        {'range': [0.40, 0.80], 'interval_hours': 0.25},
        {'range': [0.80, 999], 'interval_hours': 0.125},
    ])
    default_interval_hours: float = 1.0


class TradingConfig:
    """
    交易配置类
    保持与原 config.py 中 TradingConfig 完全兼容
    """
    
    # 风控参数
    RISK_PARAMS = {
        'max_drawdown': MAX_DRAWDOWN,
        'daily_loss_limit': DAILY_LOSS_LIMIT,
        'position_limit': MAX_POSITION_RATIO
    }
    
    # 网格参数
    GRID_PARAMS = {
        'initial': INITIAL_GRID,
        'min': 1.0,
        'max': 4.0,
        'volatility_threshold': {
            'ranges': [
                {'range': [0, 0.20], 'grid': 1.0},
                {'range': [0.20, 0.40], 'grid': 1.5},
                {'range': [0.40, 0.60], 'grid': 2.0},
                {'range': [0.60, 0.80], 'grid': 2.5},
                {'range': [0.80, 1.00], 'grid': 3.0},
                {'range': [1.00, 1.20], 'grid': 3.5},
                {'range': [1.20, 999], 'grid': 4.0}
            ]
        }
    }
    
    # 动态时间间隔参数
    DYNAMIC_INTERVAL_PARAMS = {
        'volatility_to_interval_hours': [
            {'range': [0, 0.20], 'interval_hours': 1.0},
            {'range': [0.20, 0.40], 'interval_hours': 0.5},
            {'range': [0.40, 0.80], 'interval_hours': 0.25},
            {'range': [0.80, 999], 'interval_hours': 0.125},
        ],
        'default_interval_hours': 1.0
    }
    
    # 交易对配置
    SYMBOL = SYMBOL
    BASE_SYMBOL = BASE_SYMBOL
    BASE_CURRENCY = BASE_CURRENCY
    
    # 运行模式
    FLAG = FLAG  # 0为实盘，1为模拟
    
    # 网格阈值函数
    @staticmethod
    def FLIP_THRESHOLD(grid_size):
        return (grid_size / 5) / 100  # 网格大小的1/5的1%
    
    # 价格配置
    INITIAL_BASE_PRICE = INITIAL_BASE_PRICE
    
    # 风控配置
    RISK_CHECK_INTERVAL = RISK_CHECK_INTERVAL
    MAX_RETRIES = MAX_RETRIES
    RISK_FACTOR = RISK_FACTOR
    
    # 交易限制
    BASE_AMOUNT = 50.0
    MIN_TRADE_AMOUNT = MIN_TRADE_AMOUNT
    MAX_POSITION_RATIO = MAX_POSITION_RATIO
    MIN_POSITION_RATIO = MIN_POSITION_RATIO
    
    # 波动率配置
    VOLATILITY_WINDOW = VOLATILITY_WINDOW
    INITIAL_GRID = INITIAL_GRID
    POSITION_SCALE_FACTOR = POSITION_SCALE_FACTOR
    
    # 交易参数
    COOLDOWN = COOLDOWN
    SAFETY_MARGIN = SAFETY_MARGIN
    
    # API配置
    API_TIMEOUT = API_TIMEOUT
    RECV_WINDOW = RECV_WINDOW
    
    # 仓位配置
    MIN_POSITION_PERCENT = MIN_POSITION_PERCENT
    MAX_POSITION_PERCENT = MAX_POSITION_PERCENT
    
    # 初始本金
    INITIAL_PRINCIPAL = INITIAL_PRINCIPAL
    
    def __init__(self):
        """初始化并验证配置"""
        self._validate()
    
    def _validate(self):
        """验证配置合法性"""
        if self.MIN_POSITION_RATIO >= self.MAX_POSITION_RATIO:
            raise ValueError("底仓比例不能大于或等于最大仓位比例")
        
        if self.GRID_PARAMS['min'] > self.GRID_PARAMS['max']:
            raise ValueError("网格最小值不能大于最大值")


class Settings:
    """
    现代化配置类 (可选使用)
    提供更清晰的配置接口
    """
    
    def __init__(self):
        load_dotenv()
        
        # 交易对配置
        self.base_symbol = BASE_SYMBOL
        self.quote_symbol = QUOTE_SYMBOL
        self.symbol = SYMBOL
        
        # API凭证
        self.api_key = os.getenv('OKX_API_KEY', '')
        self.secret_key = os.getenv('OKX_SECRET_KEY', '')
        self.passphrase = os.getenv('OKX_PASSPHRASE', '')
        
        # 参数对象
        self.grid = GridParams()
        self.risk = RiskParams()
        self.intervals = DynamicIntervalParams()
        
        # 初始值
        self.initial_base_price = INITIAL_BASE_PRICE
        self.initial_principal = INITIAL_PRINCIPAL
    
    @classmethod
    def load(cls) -> "Settings":
        """加载配置"""
        return cls()
    
    def to_trading_config(self) -> TradingConfig:
        """转换为 TradingConfig 对象以保持兼容"""
        return TradingConfig()


# 导出
__all__ = ['TradingConfig', 'Settings', 'GridParams', 'RiskParams', 'DynamicIntervalParams']
