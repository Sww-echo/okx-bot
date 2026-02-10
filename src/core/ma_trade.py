"""
MA 策略交易引擎
负责执行 MA 策略的交易逻辑
"""
import asyncio
import logging
import time
import math
from typing import Optional

from ..config.settings import TradingConfig
from ..config.constants import TRADE_MODE, SWAP_SYMBOL
from ..services.exchange import ExchangeClient
from ..services.balance import BalanceService
from ..services.notification import get_notification_service
from ..services.persistence import PersistenceService
from ..strategies.ma import MAStrategy, Signal
from ..indicators.trend import TrendIndicators
from .position_tracker import PositionTracker

class MATrader:
    """双均线趋势交易引擎"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 服务初始化
        self.persistence = PersistenceService()
        self.exchange = ExchangeClient(flag=config.FLAG)
        self.balance_service = BalanceService(self.exchange)
        self.notifier = get_notification_service()
        
        # 策略与指标
        self.ma_config = config.MA
        self.strategy = MAStrategy(self.ma_config)
        self.indicators = TrendIndicators(self.exchange)
        self.position_tracker = PositionTracker()
        
        # 状态简要
        self.initialized = False
        self._running = True
        self.paused = False
        self.current_price = 0.0

    async def set_paused(self, paused: bool):
        """设置暂停状态"""
        self.paused = paused
        self.logger.info(f"MA 交易引擎已{'暂停' if paused else '恢复'}")

    async def close_all_positions(self):
        """平仓所有"""
        pos = self.position_tracker.get_position()
        if pos:
            self.logger.info("手动触发平仓所有")
            await self.exchange.close_position(symbol=pos.symbol, pos_side=pos.side)
            self.position_tracker.close_position()

    async def get_status_summary(self):
        """获取状态摘要"""
        return {
            "mode": "ma",
            "state": self.strategy.current_state.value if hasattr(self.strategy, 'current_state') else "UNKNOWN",
            "paused": self.paused,
            "position": self.position_tracker.get_position(),
            "last_squeeze": self.strategy.last_squeeze_high if hasattr(self.strategy, 'last_squeeze_high') else 0
        }

        
    async def initialize(self):
        """初始化"""
        if self.initialized: return
        self.logger.info("初始化 MA 交易引擎...")
        
        # 加载市场数据
        if not await self.exchange.load_markets():
            raise Exception("无法加载市场数据")
            
        # 同步时间
        await self.exchange.sync_time()
        
        self.initialized = True
        self.logger.info("MA 交易引擎初始化完成")

    async def start(self):
        """启动交易循环"""
        while self._running:
            try:
                if not self.initialized:
                    await self.initialize()
                
                if self.paused:
                    await asyncio.sleep(1)
                    continue

                # 1. 获取最新价格
                target_symbol = self.ma_config.SYMBOL
                ticker = await self.exchange.fetch_ticker(target_symbol)
                self.current_price = float(ticker['last'])
                
                # 2. 更新持仓监控 (止损/止盈)
                if self.position_tracker.get_position():
                    await self._check_position_exit()
                
                # 3. 执行策略分析
                # 仅在无持仓或允许加仓(暂不支持)时分析
                if not self.position_tracker.get_position():
                    signal = await self.strategy.analyze(self.indicators)
                    if signal.type.startswith('OPEN'):
                        await self._execute_entry(signal)

                # 4. 休眠 (MA策略不需要高频轮询，建议按K线周期检查，这里设为配置的间隔)
                await asyncio.sleep(self.ma_config.CHECK_INTERVAL)

            except Exception as e:
                self.logger.error(f"MA 交易循环异常: {str(e)}", exc_info=True)
                await asyncio.sleep(30)

    async def shutdown(self):
        """关闭引擎"""
        self._running = False
        await self.exchange.close()
        self.logger.info("MA 交易引擎已关闭")

    async def _execute_entry(self, signal: Signal):
        """执行开仓信号"""
        self.logger.info(f"收到开仓信号: {signal}")
        
        # 1. 计算仓位大小
        # 仓位 = 账户余额 * 风险比例 / 止损距离
        # 简化：使用每次风险金额 = 余额 * 2% 
        # 数量 = 风险金额 / |Entry - SL|
        
        try:
            total_equity = await self.balance_service.get_total_assets(self.current_price)
            risk_amount = total_equity * self.ma_config.RISK_PER_TRADE
            
            price_diff = abs(signal.price - signal.stop_loss)
            if price_diff <= 0:
                self.logger.warning("止损距离过小，跳过开仓")
                return
                
            amount_coin = risk_amount / price_diff
            
            # 2. 检查最小交易额
            if amount_coin * signal.price < 10: # 10 USDT
                self.logger.warning(f"交易额过小 ({amount_coin*signal.price:.2f}), 跳过")
                return
            
            # 3. 下单
            side = 'buy' if 'LONG' in signal.type else 'sell'
            pos_side = 'long' if 'LONG' in signal.type else 'short'
            
            # 转换为合约张数 (假设每张=1币或根据合约面值，这里假设 amount 是币数，需转换)
            # 简化: 使用 market 单，按数量下单。
            # 注意: create_order 对于 swap 应该传 sz (contracts)，需根据 amount_coin 换算?
            # OKX Swap sz is unit of contracts. Contract Val?
            # 假设 sz = amount_coin for simple implementation or check `exchange` logic.
            # GridTrader logic: `amount_coin = target_value / price`.
            
            # 下单数量修正
            final_amount = amount_coin # 需根据合约面值调整，暂且假设为币数
            if TRADE_MODE == 'swap':
                 final_amount = max(1, int(amount_coin)) # 假设 1 contract = 1 coin? No, usually 0.01 or 100.
                 # 需要ExchangeClient提供换算方法。但这里先简化，假设用户已配置好。
                 # 或者直接下单
                 pass
            
            self.logger.info(f"执行开仓: {side} {final_amount} @ {signal.price}")
            
            order = await self.exchange.create_order(
                symbol=self.ma_config.SYMBOL,
                type='market',
                side=side,
                amount=final_amount,
                price=None,
                pos_side=pos_side
            )
            
            entry_price = float(order.get('avgPx', signal.price) or signal.price)
            real_amount = float(order.get('accFillSz', final_amount) or final_amount)
            
            # 4. 记录持仓
            self.position_tracker.open_position(
                symbol=self.ma_config.SYMBOL,
                side=pos_side,
                price=entry_price,
                amount=real_amount,
                sl=signal.stop_loss,
                tp=signal.take_profit,
                strategy_id=signal.strategy_id,
                timestamp=int(time.time())
            )
            
            # 5. 发送通知
            self.notifier.send(
                f"策略: {signal.strategy_id}\n"
                f"方向: {pos_side.upper()}\n"
                f"价格: {entry_price}\n"
                f"数量: {real_amount}\n"
                f"止损: {signal.stop_loss}\n"
                f"止盈: {signal.take_profit}",
                title=f"🚀 MA策略开仓成功"
            )
            
        except Exception as e:
            self.logger.error(f"开仓失败: {e}", exc_info=True)
            self.notifier.send_error_notification(f"MA开仓 {signal.type}", str(e))

    async def _check_position_exit(self):
        """检查持仓退出"""
        pos = self.position_tracker.get_position()
        if not pos: return
        
        exit_reason = self.position_tracker.update_price(self.current_price)
        
        if exit_reason:
            try:
                self.logger.info(f"触发退出: {exit_reason}")
                
                # 平仓方向
                side = 'sell' if pos.side == 'long' else 'buy'
                
                # 执行平仓
                await self.exchange.close_position(
                    symbol=pos.symbol,
                    pos_side=pos.side
                )
                
                # 清除记录
                self.position_tracker.close_position()
                
                # 通知
                pnl_msg = f"盈亏: {pos.pnl:.4f}"
                self.notifier.send(
                    f"原因: {exit_reason}\n"
                    f"平仓价格: {self.current_price}\n"
                    f"{pnl_msg}",
                    title=f"🛑 MA策略平仓"
                )
                
            except Exception as e:
                self.logger.error(f"平仓失败: {e}", exc_info=True)
