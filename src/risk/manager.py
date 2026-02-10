"""
风险管理模块
包含多层风控检查逻辑：仓位限制、回撤止损、每日亏损限制、连续亏损保护
"""
import logging
import time
import traceback
from typing import Optional, Dict, List

from ..config.settings import TradingConfig
from ..config.constants import MAX_CONSECUTIVE_LOSSES, LOSS_COOLDOWN


class RiskManager:
    """高级风控管理器"""
    
    def __init__(self, config: TradingConfig, exchange, balance_service):
        self.config = config
        self.exchange = exchange
        self.balance_service = balance_service
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 仓位监控
        self.last_position_ratio = 0.0
        
        # 回撤止损
        self.peak_assets = 0.0              # 资产峰值
        self.drawdown_triggered = False      # 回撤是否已触发
        
        # 连续亏损保护
        self.consecutive_losses = 0          # 连续亏损计数
        self.loss_cooldown_until = 0.0       # 冷却截止时间
        
        # 每日亏损追踪
        self._daily_trades: List[Dict] = []  # 今日交易记录
        self._daily_reset_ts = 0.0           # 今日重置时间戳
    
    async def multi_layer_check(self, current_price: float) -> bool:
        """
        执行多层风控检查
        
        Args:
            current_price: 当前价格
            
        Returns:
            如果触发风控（需要暂停交易或采取措施）返回 True，否则返回 False
        """
        try:
            # ========== 0. 连续亏损冷却检查 ==========
            if time.time() < self.loss_cooldown_until:
                remaining = int(self.loss_cooldown_until - time.time())
                self.logger.warning(f"连续亏损冷却中 | 剩余 {remaining}s")
                return True
            
            # ========== 1. 仓位比例检查 ==========
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
                # 底仓不足不暂停交易，由策略层决定是否补仓
                return False
            
            # 3. 仓位超限检查
            if position_ratio > self.config.MAX_POSITION_RATIO:
                self.logger.warning(f"仓位超限 | 当前: {position_ratio:.2%} > 最大: {self.config.MAX_POSITION_RATIO:.2%}")
                return True
            
            # ========== 4. 总资产回撤止损 ==========
            total_assets = await self.balance_service.get_total_assets(current_price)
            
            if total_assets > self.peak_assets:
                self.peak_assets = total_assets
                self.drawdown_triggered = False  # 创新高时重置
            
            if self.peak_assets > 0:
                drawdown = (self.peak_assets - total_assets) / self.peak_assets
                max_drawdown = abs(self.config.RISK_PARAMS.get('max_drawdown', -0.15))
                
                if drawdown >= max_drawdown:
                    if not self.drawdown_triggered:
                        self.drawdown_triggered = True
                        self.logger.critical(
                            f"⚠️ 回撤止损触发 | "
                            f"峰值: {self.peak_assets:.2f} | "
                            f"当前: {total_assets:.2f} | "
                            f"回撤: {drawdown:.2%} >= {max_drawdown:.2%}"
                        )
                    return True
            
            # ========== 5. 每日亏损限制 ==========
            daily_pnl = self._get_daily_pnl()
            if daily_pnl is not None:
                daily_limit = abs(self.config.RISK_PARAMS.get('daily_loss_limit', -0.05))
                initial = self.config.INITIAL_PRINCIPAL if self.config.INITIAL_PRINCIPAL > 0 else self.peak_assets
                
                if initial > 0:
                    daily_loss_ratio = abs(daily_pnl) / initial if daily_pnl < 0 else 0
                    if daily_loss_ratio >= daily_limit:
                        self.logger.critical(
                            f"⚠️ 每日亏损限制触发 | "
                            f"今日亏损: {daily_pnl:.2f} USDT ({daily_loss_ratio:.2%}) | "
                            f"限制: {daily_limit:.2%}"
                        )
                        return True

            return False
            
        except Exception as e:
            self.logger.error(f"风控检查失败: {str(e)} | 堆栈信息: {traceback.format_exc()}")
            # 发生异常时，为了安全起见，视为风控不通过
            return True
    
    # ==================== 连续亏损保护 ====================
    
    def record_trade_result(self, profit: float):
        """
        记录交易结果，用于连续亏损保护和每日亏损追踪
        
        Args:
            profit: 本次交易盈亏（正数=盈利，负数=亏损）
        """
        # 连续亏损计数
        if profit < 0:
            self.consecutive_losses += 1
            self.logger.info(f"连续亏损计数: {self.consecutive_losses}/{MAX_CONSECUTIVE_LOSSES}")
            
            if self.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
                self.loss_cooldown_until = time.time() + LOSS_COOLDOWN
                self.logger.warning(
                    f"⚠️ 连续亏损保护触发 | "
                    f"连续 {self.consecutive_losses} 笔亏损 | "
                    f"冷却 {LOSS_COOLDOWN}s"
                )
                self.consecutive_losses = 0  # 重置，冷却结束后重新计数
        else:
            # 盈利则重置计数
            if self.consecutive_losses > 0:
                self.logger.info(f"连续亏损计数已重置（盈利 {profit:.2f}）")
            self.consecutive_losses = 0
        
        # 每日盈亏追踪
        self._ensure_daily_reset()
        self._daily_trades.append({
            'timestamp': time.time(),
            'profit': profit
        })
    
    # ==================== 每日亏损计算 ====================
    
    def _ensure_daily_reset(self):
        """确保每日数据在新的一天自动重置"""
        now = time.time()
        # 每天 UTC 0点重置（可根据需求调整为本地时区）
        current_day = int(now // 86400)
        last_day = int(self._daily_reset_ts // 86400) if self._daily_reset_ts > 0 else -1
        
        if current_day != last_day:
            if self._daily_trades:
                self.logger.info(f"每日亏损追踪重置 | 昨日交易 {len(self._daily_trades)} 笔")
            self._daily_trades = []
            self._daily_reset_ts = now
    
    def _get_daily_pnl(self) -> Optional[float]:
        """
        获取今日总盈亏
        
        Returns:
            今日总盈亏（USDT），无数据时返回 None
        """
        self._ensure_daily_reset()
        if not self._daily_trades:
            return None
        return sum(t['profit'] for t in self._daily_trades)
    
    # ==================== 预留接口 ====================
    
    async def check_market_sentiment(self) -> None:
        """
        检查市场情绪指标并动态调整风险系数
        (此功能目前为预留接口)
        """
        pass

    def get_risk_status(self) -> Dict:
        """获取当前风控状态概览"""
        daily_pnl = self._get_daily_pnl()
        return {
            'peak_assets': self.peak_assets,
            'drawdown_triggered': self.drawdown_triggered,
            'consecutive_losses': self.consecutive_losses,
            'loss_cooldown_remaining': max(0, int(self.loss_cooldown_until - time.time())),
            'daily_pnl': daily_pnl if daily_pnl is not None else 0,
            'daily_trade_count': len(self._daily_trades),
        }


# 导出
__all__ = ['RiskManager']
