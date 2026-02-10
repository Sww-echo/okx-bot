"""
网格策略模块
实现核心网格交易逻辑
"""
import logging
import traceback
from typing import Dict, Optional, Tuple, Any

from ..config.settings import TradingConfig


class GridStrategy:
    """网格交易策略"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 状态
        self.grid_size = config.INITIAL_GRID
        self.base_price = 0.0
        
    def set_base_price(self, price: float):
        """设置基准价格"""
        self.base_price = price
        self.logger.info(f"基准价格更新为: {price:.4f}")

    def update_grid_size(self, volatility: float) -> float:
        """
        根据波动率调整网格大小
        
        Args:
            volatility: 当前波动率
            
        Returns:
            调整后的网格大小
        """
        try:
            # 根据波动率获取基础网格大小
            base_grid = None
            for range_config in self.config.GRID_PARAMS['volatility_threshold']['ranges']:
                if range_config['range'][0] <= volatility < range_config['range'][1]:
                    base_grid = range_config['grid']
                    break
            
            # 如果没有匹配到波动率范围，使用默认网格
            if base_grid is None:
                base_grid = self.config.INITIAL_GRID
            
            # 确保网格在允许范围内
            new_grid = max(
                min(base_grid, self.config.GRID_PARAMS['max']),
                self.config.GRID_PARAMS['min']
            )
            
            if new_grid != self.grid_size:
                self.logger.info(
                    f"调整网格大小 | "
                    f"波动率: {volatility:.2%} | "
                    f"原网格: {self.grid_size:.2f}% | "
                    f"新网格: {new_grid:.2f}%"
                )
                self.grid_size = new_grid
                
            return self.grid_size
            
        except Exception as e:
            self.logger.error(f"调整网格大小失败: {str(e)}")
            return self.grid_size

    def check_signal(self, current_price: float) -> Tuple[str, float]:
        """
        检查交易信号
        
        Args:
            current_price: 当前价格
            
        Returns:
            (信号类型 'buy'/'sell'/None, 触发价格差百分比)
        """
        if self.base_price <= 0:
            return None, 0.0
            
        price_diff_pct = (current_price - self.base_price) / self.base_price
        
        # 卖出信号: 价格上涨超过网格大小
        if price_diff_pct >= (self.grid_size / 100):
            return 'sell', price_diff_pct
            
        # 买入信号: 价格下跌超过网格大小
        elif price_diff_pct <= -(self.grid_size / 100):
            return 'buy', price_diff_pct
            
        return None, price_diff_pct

    def check_flip_signal(self, current_price: float, flip_threshold_func) -> bool:
        """
        检查是否需要翻转 (大幅偏离)
        
        Args:
            current_price: 当前价格
            flip_threshold_func: 计算翻转阈值的函数
            
        Returns:
            是否触发翻转信号
        """
        if self.base_price <= 0:
            return False
            
        price_diff = abs(current_price - self.base_price)
        threshold = self.base_price * flip_threshold_func(self.grid_size)
        
        return price_diff >= threshold


# 导出
__all__ = ['GridStrategy']
