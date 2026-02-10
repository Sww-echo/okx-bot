"""
余额管理服务模块
处理账户余额检查、资金划转等操作
"""
import logging
import traceback
import asyncio
from typing import Dict, Optional, Tuple

from ..config.constants import SAFETY_MARGIN, BASE_CURRENCY, TRADE_MODE, SWAP_SYMBOL


class BalanceService:
    """
    余额管理服务
    负责检查余额、计算可用资金、执行资金划转
    """
    
    def __init__(self, exchange):
        """
        初始化余额服务
        
        Args:
            exchange: 交易所客户端实例
        """
        self.exchange = exchange
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 缓存配置
        self.funding_balance_cache = {
            'timestamp': 0,
            'data': {}
        }
        self.funding_cache_ttl = 60  # 理财余额缓存60秒
    
    async def get_available_balance(self, currency: str) -> float:
        """
        获取指定币种的可用余额
        
        Args:
            currency: 币种符号（如 'USDT', 'OKB'）
            
        Returns:
            可用余额（考虑安全边际）
        """
        balance = await self.exchange.fetch_balance({'type': 'spot'})
        return balance.get('free', {}).get(currency, 0) * SAFETY_MARGIN
    
    async def get_total_assets(self, current_price: float) -> float:
        """
        获取总资产价值（USDT）
        """
        try:
            balance = await self.exchange.fetch_balance()
            funding_balance = await self.exchange.fetch_funding_balance()
            
            # 计算USDT总额
            usdt_total = (
                float(balance.get('free', {}).get('USDT', 0)) +
                float(balance.get('used', {}).get('USDT', 0)) +
                float(funding_balance.get('USDT', 0))
            )

            if TRADE_MODE == 'swap':
                # 合约模式：总资产 = USDT余额 + 未实现盈亏
                positions = await self.exchange.fetch_positions(SWAP_SYMBOL)
                upl = sum(float(p.get('upl', 0)) for p in positions)
                return usdt_total + upl
            else:
                # 现货模式：总资产 = USDT + 币种价值
                base_total = (
                    float(balance.get('free', {}).get(BASE_CURRENCY, 0)) +
                    float(balance.get('used', {}).get(BASE_CURRENCY, 0)) +
                    float(funding_balance.get(BASE_CURRENCY, 0))
                )
                return usdt_total + (base_total * current_price)
            
        except Exception as e:
            self.logger.error(f"获取总资产失败: {str(e)} | 堆栈信息: {traceback.format_exc()}")
            return 0
    
    async def get_position_ratio(self, current_price: float) -> float:
        """
        获取当前仓位占总资产比例
        """
        try:
            total_assets = await self.get_total_assets(current_price)
            if total_assets == 0:
                return 0

            if TRADE_MODE == 'swap':
                # 合约模式：仓位价值 = 持仓数量(张) * 合约面值 * 价格 (假设每张1个币 ??? OKX通常是币本位或U本位)
                # OKX U本位永续：1张 = ctVal 币 (如 OKB-USDT-SWAP, ctVal=1 OKB? 需确认)
                # 简单起见，我们直接获取持仓名义价值 (notionalUsd)
                positions = await self.exchange.fetch_positions(SWAP_SYMBOL)
                position_value = sum(float(p.get('notionalUsd', 0)) for p in positions)
                # 注意：notionalUsd 是名义价值（带杠杆），这里我们要计算的是"仓位占用本金"还是"名义敞口"？
                # 按照网格策略习惯，通常控制的是"名义敞口比例"
                return position_value / total_assets
            else:
                # 现货模式
                balance = await self.exchange.fetch_balance()
                funding_balance = await self.exchange.fetch_funding_balance()
                
                base_amount = (
                    float(balance.get('free', {}).get(BASE_CURRENCY, 0)) +
                    float(balance.get('used', {}).get(BASE_CURRENCY, 0)) +
                    float(funding_balance.get(BASE_CURRENCY, 0))
                )
                position_value = base_amount * current_price
                return position_value / total_assets
            
        except Exception as e:
            self.logger.error(f"计算仓位比例失败: {str(e)} | 堆栈信息: {traceback.format_exc()}")
            return 0
    
    async def check_buy_balance(
        self, 
        required_usdt: float,
        current_price: float = None
    ) -> Tuple[bool, float]:
        """
        检查买入所需的USDT余额是否充足
        
        Args:
            required_usdt: 需要的USDT数量
            current_price: 当前价格（用于日志）
            
        Returns:
            (是否充足, 可用余额)
        """
        try:
            balance = await self.exchange.fetch_balance()
            available_usdt = float(balance.get('free', {}).get('USDT', 0))
            
            if available_usdt >= required_usdt:
                return True, available_usdt
            
            # 尝试从理财赎回
            funding_balance = await self.exchange.fetch_funding_balance()
            funding_usdt = float(funding_balance.get('USDT', 0))
            
            shortfall = required_usdt - available_usdt
            if funding_usdt >= shortfall:
                self.logger.info(f"现货USDT不足，从理财赎回 {shortfall:.2f} USDT")
                await self.exchange.transfer_to_spot('USDT', shortfall)
                await asyncio.sleep(2)  # 等待资金到账
                return True, available_usdt + shortfall
            
            self.logger.warning(
                f"USDT余额不足 | 需要: {required_usdt:.2f} | "
                f"现货: {available_usdt:.2f} | 理财: {funding_usdt:.2f}"
            )
            return False, available_usdt
            
        except Exception as e:
            self.logger.error(f"检查买入余额失败: {str(e)} | 堆栈信息: {traceback.format_exc()}")
            return False, 0
    
    async def check_sell_balance(
        self, 
        required_amount: float
    ) -> Tuple[bool, float]:
        """
        检查卖出所需的币种余额是否充足
        
        Args:
            required_amount: 需要的币种数量
            
        Returns:
            (是否充足, 可用余额)
        """
        try:
            balance = await self.exchange.fetch_balance()
            available = float(balance.get('free', {}).get(BASE_CURRENCY, 0))
            
            if available >= required_amount:
                return True, available
            
            # 尝试从理财赎回
            funding_balance = await self.exchange.fetch_funding_balance()
            funding_amount = float(funding_balance.get(BASE_CURRENCY, 0))
            
            shortfall = required_amount - available
            if funding_amount >= shortfall:
                self.logger.info(f"现货{BASE_CURRENCY}不足，从理财赎回 {shortfall:.8f}")
                await self.exchange.transfer_to_spot(BASE_CURRENCY, shortfall)
                await asyncio.sleep(2)
                return True, available + shortfall
            
            self.logger.warning(
                f"{BASE_CURRENCY}余额不足 | 需要: {required_amount:.8f} | "
                f"现货: {available:.8f} | 理财: {funding_amount:.8f}"
            )
            return False, available
            
        except Exception as e:
            self.logger.error(f"检查卖出余额失败: {str(e)} | 堆栈信息: {traceback.format_exc()}")
            return False, 0
    
    async def transfer_excess_to_savings(
        self, 
        target_ratio: float,
        current_price: float
    ) -> bool:
        """
        将超出目标比例的资金转入理财
        
        Args:
            target_ratio: 目标现货余额比例（如 0.16 表示 16%）
            current_price: 当前价格
            
        Returns:
            是否成功
        """
        try:
            total_assets = await self.get_total_assets(current_price)
            target_spot = total_assets * target_ratio
            
            balance = await self.exchange.fetch_balance()
            
            # 检查USDT
            spot_usdt = float(balance.get('free', {}).get('USDT', 0))
            excess_usdt = spot_usdt - (target_spot * 0.5)  # 保留一半目标为USDT
            
            if excess_usdt > 10:  # 最小转移金额
                self.logger.info(f"转移多余USDT到理财: {excess_usdt:.2f}")
                await self.exchange.transfer_to_savings('USDT', excess_usdt)
            
            # 检查基础币种
            spot_base = float(balance.get('free', {}).get(BASE_CURRENCY, 0))
            target_base = (target_spot * 0.5) / current_price
            excess_base = spot_base - target_base
            
            if excess_base > 0.01:
                self.logger.info(f"转移多余{BASE_CURRENCY}到理财: {excess_base:.8f}")
                await self.exchange.transfer_to_savings(BASE_CURRENCY, excess_base)
            
            return True
            
        except Exception as e:
            self.logger.error(f"转移资金到理财失败: {str(e)} | 堆栈信息: {traceback.format_exc()}")
            return False
    
    async def ensure_trading_funds(
        self,
        min_usdt: float,
        min_base: float,
        current_price: float
    ) -> bool:
        """
        确保现货账户有足够的交易资金
        
        Args:
            min_usdt: 最小USDT数量
            min_base: 最小基础币种数量
            current_price: 当前价格
            
        Returns:
            是否成功
        """
        try:
            balance = await self.exchange.fetch_balance()
            
            spot_usdt = float(balance['free'].get('USDT', 0))
            spot_base = float(balance['free'].get(BASE_CURRENCY, 0))
            
            transfers = []
            
            if spot_usdt < min_usdt:
                transfers.append({
                    'asset': 'USDT',
                    'amount': min_usdt - spot_usdt
                })
            
            if spot_base < min_base:
                transfers.append({
                    'asset': BASE_CURRENCY,
                    'amount': min_base - spot_base
                })
            
            if transfers:
                self.logger.info("开始资金赎回操作...")
                for transfer in transfers:
                    self.logger.info(f"从理财赎回 {transfer['amount']:.8f} {transfer['asset']}")
                    await self.exchange.transfer_to_spot(transfer['asset'], transfer['amount'])
                self.logger.info("资金赎回完成")
                await asyncio.sleep(2)
            
            return True
            
        except Exception as e:
            self.logger.error(f"资金检查和划转失败: {str(e)} | 堆栈信息: {traceback.format_exc()}")
            return False


# 导出
__all__ = ['BalanceService']
