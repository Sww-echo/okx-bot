"""
核心交易逻辑模块
整合策略、服务和执行
"""
import asyncio
import logging
import traceback
import time
from datetime import datetime
import httpx

from ..config.settings import TradingConfig
from ..config.constants import TRADE_MODE, SWAP_SYMBOL, SYMBOL
from ..services.exchange import ExchangeClient
from ..services.balance import BalanceService
from ..services.notification import get_notification_service
from ..services.persistence import PersistenceService
from ..strategies.grid import GridStrategy
from ..strategies.position import S1Strategy
from ..risk.manager import RiskManager
from ..utils.decorators import retry_on_failure, debug_watcher
from ..utils.formatters import format_trade_message, format_error_message

from .order import OrderManager, OrderThrottler


class GridTrader:
    """网格交易核心类"""

    def __init__(self, config: TradingConfig, initial_data: dict = None):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 服务初始化
        self.persistence = PersistenceService()
        self.exchange = ExchangeClient(flag=config.FLAG)
        self.order_manager = OrderManager(self.persistence)
        self.balance_service = BalanceService(self.exchange)
        self.notifier = get_notification_service()
        self.throttler = OrderThrottler(limit=10, interval=60)
        
        # 风险和策略初始化
        self.risk_manager = RiskManager(self.config, self.exchange, self.balance_service)
        self.grid_strategy = GridStrategy(self.config)
        self.s1_strategy = S1Strategy(self.config, self.risk_manager)
        
        # 将执行器注入到S1策略
        self.s1_strategy.set_executor(self.execute_s1_trade)
        
        # 状态变量
        self.initialized = False
        self.current_price = 0.0
        self.active_orders = {'buy': None, 'sell': None}
        self.buying_or_selling = False
        
        # 其他
        self.last_grid_adjust_time = time.time()
        self.symbol_info = {'base': config.BASE_SYMBOL} 

    def get_target_symbol(self):
        """获取目标交易对（现货或合约）"""
        return SWAP_SYMBOL if TRADE_MODE == 'swap' else self.config.SYMBOL

    async def initialize(self):
        """初始化交易环境"""
        if self.initialized:
            return
            
        self.logger.info("正在初始化交易系统...")
        try:
            # 加载市场数据
            await self.exchange.load_markets()
            
            # 同步时间
            await self.exchange.sync_time()
            
            # 初始余额检查和分配
            await self._check_initial_funds()
            
            # 设置合约杠杆（如果是合约模式）
            target_symbol = self.get_target_symbol()
            if TRADE_MODE == 'swap':
                await self.exchange.set_leverage(target_symbol)
            
            # 获取基准价格
            if self.config.INITIAL_BASE_PRICE > 0:
                self.grid_strategy.set_base_price(self.config.INITIAL_BASE_PRICE)
            else:
                ticker = await self.exchange.fetch_ticker(target_symbol)
                self.grid_strategy.set_base_price(float(ticker['last']))
            
            # S1策略初始化
            await self.s1_strategy.update_daily_levels(self.exchange, target_symbol)
            
            self.initialized = True
            
            # 发送启动通知
            threshold = self.config.FLIP_THRESHOLD(self.config.INITIAL_GRID)
            self.notifier.send_startup_notification(
                target_symbol,
                self.grid_strategy.base_price,
                self.grid_strategy.grid_size,
                threshold
            )
            
            self.logger.info("初始化完成")
            
        except Exception as e:
            self.logger.error(f"初始化失败: {str(e)}", exc_info=True)
            self.notifier.send_error_notification("初始化", self.config.SYMBOL, str(e))
            raise

    async def _check_initial_funds(self):
        """检查初始资金"""
        # 复用 BalanceService 的逻辑，或者在这里实现更高层的逻辑
        # 这里暂时简化处理，调用 BalanceService 的 helper 方法 (如果有)
        # 或者直接在这里写逻辑
        pass # 已经在 main_loop 或 strategy check 中包含动态检查

    async def start(self):
        """启动主循环"""
        while True:
            try:
                if not self.initialized:
                    await self.initialize()

                # 1. 获取最新价格
                target_symbol = self.get_target_symbol()
                ticker = await self.exchange.fetch_ticker(target_symbol)
                self.current_price = float(ticker['last'])
                
                # 2. 检查交易信号 (优先)
                await self._process_grid_signals()
                
                # 3. 如果没有正在进行的交易，执行其他维护任务
                if not self.buying_or_selling:
                    # 风险检查
                    if await self.risk_manager.multi_layer_check(self.current_price):
                        await asyncio.sleep(5)
                        continue
                    
                    # S1 策略检查
                    await self.s1_strategy.check_and_execute(self.current_price, self.balance_service, target_symbol)
                    
                    # 自动补足底仓（如果仓位低于最小值）
                    await self._ensure_min_position(target_symbol)
                    
                    # 网格大小调整
                    await self._adjust_grid_size_if_needed()

                await asyncio.sleep(5)

            except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
                self.logger.warning(f"网络连接波动 ({str(e)}), 5秒后重试...")
                await asyncio.sleep(5)
            except Exception as e:
                self.logger.error(f"主循环异常: {str(e)}", exc_info=True)
                await asyncio.sleep(30)

    async def _process_grid_signals(self):
        """处理网格交易信号"""
        signal, diff = self.grid_strategy.check_signal(self.current_price)
        
        if signal == 'sell':
             await self.execute_grid_trade('sell', self.current_price)
        elif signal == 'buy':
             await self.execute_grid_trade('buy', self.current_price)

    @retry_on_failure(max_retries=3)
    async def execute_grid_trade(self, side: str, price: float):
        """执行网格交易"""
        if self.buying_or_selling:
            return

        self.buying_or_selling = True
        try:
            # 1. 计算交易量
            amount = await self._calculate_trade_amount(side, price)
            
            # 2. 余额检查
            # 合约模式下，无论买卖都使用 USDT 保证金（全仓/逐仓），只需检查 USDT 余额是否足够开仓
            # 现货模式下，买入查 USDT，卖出查币
            has_balance = False
            msg = ""
            
            if TRADE_MODE == 'swap':
                # 简单估算：合约所需保证金 = (数量 * 价格) / 杠杆
                required_margin = (amount * price) / self.exchange.leverage
                has_balance, _ = await self.balance_service.check_buy_balance(required_margin, price)
                msg = f"保证金不足 ({required_margin:.2f} USDT)"
            else:
                # 现货模式
                if side == 'buy':
                    has_balance, _ = await self.balance_service.check_buy_balance(amount * price, price)
                    msg = "USDT 余额不足"
                else:
                    has_balance, _ = await self.balance_service.check_sell_balance(amount)
                    msg = f"{self.config.BASE_CURRENCY} 余额不足"
                
            if not has_balance:
                self.logger.warning(f"余额检查未通过: {msg} | 无法执行 {side}")
                return

            # 3. 下单
            order = await self.exchange.create_order(
                symbol=self.get_target_symbol(),
                type='limit', 
                side=side,
                amount=amount,
                price=price
            )
            
            # 4. 记录和通知
            total = amount * price
            self.order_manager.log_trade({
                'timestamp': time.time(),
                'side': side,
                'price': price,
                'amount': amount,
                'order_id': order.get('ordId', order.get('id', '')),
                'profit': 0 # 暂时无法计算
            })
            
            self.notifier.send_trade_notification(
                side, self.config.SYMBOL, price, amount, total, self.grid_strategy.grid_size
            )
            
            # 5. 更新网格基准价
            self.grid_strategy.set_base_price(price)
            self.logger.info(f"网格交易完成: {side} {amount} @ {price}, 基准价更新")
            
        except Exception as e:
            self.logger.error(f"网格交易执行失败: {str(e)}", exc_info=True)
            self.notifier.send_error_notification(f"{side} 交易", self.config.SYMBOL, str(e))
        finally:
            self.buying_or_selling = False

    async def execute_s1_trade(self, side: str, amount: float, price: float) -> bool:
        """S1策略交易执行回调"""
        try:
            # S1 是市价单调整仓位
            order = await self.exchange.create_order(
                symbol=self.config.SYMBOL,
                type='market',
                side=side.lower(),
                amount=amount,
                price=None # 市价单不需要价格
            )
            
            self.logger.info(f"S1 {side} 订单已提交: {order.get('ordId', order.get('id', 'unknown'))}")
            return True
        except Exception as e:
            self.logger.error(f"S1 交易失败: {str(e)}")
            return False

    async def _calculate_trade_amount(self, side: str, price: float) -> float:
        """计算交易数量"""
        # 这里可以使用原 trader.py 中的 calculate_trade_amount 逻辑
        # 简化版：固定金额或比例
        total_assets = await self.balance_service.get_total_assets(price)
        amount_usdt = max(
             self.config.MIN_TRADE_AMOUNT,
             total_assets * 0.05 # 默认每次交易5%
        )
        
        # 转换为币种数量
        # OKX 合约是"张"为单位，但 u本位永续下单可以是 "币" 为单位（需确认 sz 的单位）
        # 文档：sz string 委托数量
        # 币币/币币杠杆：委托数量
        # 交割/永续：张数 
        
        if TRADE_MODE == 'swap':
            # 假设 sz 是张数。OKX U本位合约通常 1张 = 1 OKB (需要查阅 specific instrument info)
            # 或者 1张 = 0.1 OKB
            # 为了简单，我们假设 1张 = 1 币 (如果是 OKB-USDT-SWAP, ctVal=1)
            # 需要通过 public_api 获取合约面值才准确。这里暂时简化处理：向上取整到整数张
            ct_val = 1.0 # TODO: 动态获取合约面值
            amount_coin = amount_usdt / price
            amount_contracts = max(1, int(amount_coin / ct_val))
            return float(amount_contracts)
        else:
            amount = amount_usdt / price
            return float(f"{amount:.3f}") # 简单精度处理

    async def _adjust_grid_size_if_needed(self):
        """调整网格大小"""
        # 简单的定期调整逻辑
        if time.time() - self.last_grid_adjust_time > 3600: # 每小时
             from ..indicators.volatility import VolatilityCalculator
             vc = VolatilityCalculator(self.exchange)
             vol = await vc.calculate_volatility()
             self.grid_strategy.update_grid_size(vol)
             self.last_grid_adjust_time = time.time()

    async def _ensure_min_position(self, target_symbol: str):
        """确保最小底仓"""
        if self.buying_or_selling:
            return
            
        try:
            position_ratio = await self.balance_service.get_position_ratio(self.current_price)
            min_ratio = self.config.MIN_POSITION_RATIO
            
            if position_ratio < min_ratio:
                # 计算需要买入的金额 (USDT)
                total_assets = await self.balance_service.get_total_assets(self.current_price)
                if total_assets <= 0:
                    return
                    
                deficit_ratio = min_ratio - position_ratio
                target_value_usdt = total_assets * deficit_ratio
                
                # 最小交易额检查 (10 USDT)
                if target_value_usdt < 10:
                    return

                self.logger.info(
                    f"底仓不足 | 当前: {position_ratio:.2%} | 目标: {min_ratio:.2%} | "
                    f"需买入: {target_value_usdt:.2f} USDT"
                )
                
                # 标记为交易中
                self.buying_or_selling = True
                try:
                    # 计算买入数量
                    if TRADE_MODE == 'swap':
                        # 合约模式：按张数计算
                        amount_coin = target_value_usdt / self.current_price
                        amount = max(1, int(amount_coin))
                    else:
                        # 现货模式
                        amount = target_value_usdt / self.current_price
                        amount = float(f"{amount:.3f}")

                    self.logger.info(f"开始自动建仓: 买入 {amount} {target_symbol}")
                    order = await self.exchange.create_order(
                        symbol=target_symbol,
                        type='market',
                        side='buy',
                        amount=amount,
                        price=None
                    )
                    
                    self.logger.info(f"成功补足底仓: {order.get('ordId', 'unknown')}")
                    
                    self.notifier.send(
                        f"已自动补足底仓\n数量: {amount}\n金额: {target_value_usdt:.2f} USDT", 
                        title="🚀 自动建仓完成"
                    )
                except Exception as e:
                    self.logger.error(f"自动建仓下单失败: {str(e)}")
                finally:
                    self.buying_or_selling = False
                    
        except Exception as e:
            self.logger.error(f"补底仓检查失败: {str(e)}")
            self.buying_or_selling = False

    async def shutdown(self):
        """关闭资源"""
        await self.exchange.close()
        self.logger.info("交易系统已关闭")


# 导出
__all__ = ['GridTrader']
