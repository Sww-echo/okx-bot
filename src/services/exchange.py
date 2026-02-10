"""
交易所客户端模块
封装 OKX 交易所 API 操作
"""
import os
import logging
import traceback
import time
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any

import httpx
from okx import MarketData, Trade, Account, Funding, PublicData
from okx.Finance import Savings

from ..config.constants import (
    SYMBOL, SWAP_SYMBOL, DEBUG_MODE, API_TIMEOUT, RECV_WINDOW,
    BASE_CURRENCY, FLAG, TRADE_MODE, MARGIN_MODE, POS_SIDE, LEVERAGE
)


class ExchangeClient:
    """
    OKX 交易所客户端
    封装所有与交易所交互的操作
    """
    
    def __init__(self, flag: str = None):
        """
        初始化交易所客户端
        
        Args:
            flag: 交易模式，'0' 实盘，'1' 模拟。默认使用配置中的 FLAG
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 交易模式
        self.flag = flag or FLAG
        
        # 根据 FLAG 自动选择 API 密钥
        if self.flag == '1':
            # 模拟盘
            self.api_key = os.getenv('OKX_DEMO_API_KEY') or os.getenv('OKX_API_KEY')
            self.secret_key = os.getenv('OKX_DEMO_SECRET_KEY') or os.getenv('OKX_SECRET_KEY')
            self.passphrase = os.getenv('OKX_DEMO_PASSPHRASE') or os.getenv('OKX_PASSPHRASE')
            self.logger.info("使用模拟盘 API 密钥")
        else:
            # 实盘
            self.api_key = os.getenv('OKX_API_KEY')
            self.secret_key = os.getenv('OKX_SECRET_KEY')
            self.passphrase = os.getenv('OKX_PASSPHRASE')
            self.logger.info("使用实盘 API 密钥")
        
        self._verify_credentials()
        
        # 代理配置（可选）
        self.proxy = None
        
        # 初始化各个API模块
        self._init_api_clients()
        
        # 状态
        self.markets_loaded = False
        self.time_diff = 0
        
        # 缓存配置
        self.balance_cache = {'timestamp': 0, 'data': None}
        self.funding_balance_cache = {'timestamp': 0, 'data': {}}
        self.cache_ttl = 1/5  # 缓存有效期（秒）
        
        # 合约相关配置
        self.trade_mode = TRADE_MODE
        self.margin_mode = MARGIN_MODE
        self.pos_side = POS_SIDE
        self.leverage = LEVERAGE
        
        self.logger.setLevel(logging.INFO)
        mode_label = '模拟盘' if self.flag == '1' else '实盘'
        type_label = '永续合约' if self.trade_mode == 'swap' else '现货'
        self.logger.info(f"OKX交易所客户端初始化完成 | 模式: {mode_label} | 类型: {type_label}")
    
    def _init_api_clients(self):
        """初始化所有 API 客户端"""
        common_params = {
            'api_key': self.api_key,
            'api_secret_key': self.secret_key,
            'passphrase': self.passphrase,
            'flag': self.flag,
            'proxy': self.proxy
        }
        
        self.market_api = MarketData.MarketAPI(**common_params)
        self.trade_api = Trade.TradeAPI(**common_params)
        self.public_api = PublicData.PublicAPI(**common_params)
        self.account_api = Account.AccountAPI(**common_params)
        self.funding_api = Funding.FundingAPI(**common_params)
        self.savings_api = Savings.SavingsAPI(**common_params)
    
    def _verify_credentials(self):
        """验证API密钥是否存在"""
        required_env = ['OKX_API_KEY', 'OKX_SECRET_KEY', 'OKX_PASSPHRASE']
        missing = [var for var in required_env if not os.getenv(var)]
        if missing:
            error_msg = f"缺少环境变量: {', '.join(missing)}"
            self.logger.critical(error_msg)
            raise EnvironmentError(error_msg)

    # ==================== 市场数据 ====================
    
    async def load_markets(self) -> bool:
        """加载市场数据"""
        try:
            inst_type = 'SWAP' if self.trade_mode == 'swap' else 'SPOT'
            symbol = SWAP_SYMBOL if self.trade_mode == 'swap' else SYMBOL
            result = self.market_api.get_tickers(instType=inst_type)
            if result['code'] == '0':
                self.markets_loaded = True
                self.logger.info(f"市场数据加载成功 | 类型: {inst_type} | 交易对: {symbol}")
                return True
            else:
                error_msg = f"加载市场数据失败: {result['msg']} | 错误码: {result['code']}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
        except Exception as e:
            error_msg = f"加载市场数据失败: {str(e)} | 堆栈信息: {traceback.format_exc()}"
            self.logger.error(error_msg)
            self.markets_loaded = False
            raise Exception(error_msg)

    async def fetch_ticker(self, symbol: str) -> Dict:
        """获取行情数据"""
        self.logger.debug(f"获取行情数据 {symbol}...")
        start = datetime.now()
        try:
            result = self.market_api.get_ticker(instId=symbol.replace('/', '-'))
            if result['code'] == '0':
                ticker = result['data'][0]
                latency = (datetime.now() - start).total_seconds()
                self.logger.debug(f"获取行情成功 | 延迟: {latency:.3f}s | 最新价: {ticker['last']}")
                return ticker
            else:
                error_msg = f"获取行情失败: {result['msg']} | 错误码: {result['code']}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
        except Exception as e:
            error_msg = f"获取行情失败: {str(e)} | 堆栈信息: {traceback.format_exc()}"
            self.logger.error(error_msg)
            raise Exception(error_msg)

    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1H', limit: int = None) -> List:
        """获取K线数据"""
        try:
            # OKX 使用大写的时间周期格式
            bar_map = {
                '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
                '1h': '1H', '1H': '1H',
                '4h': '4H', '4H': '4H',
                '1d': '1D', '1D': '1D',
                '1w': '1W', '1W': '1W',
            }
            bar = bar_map.get(timeframe, timeframe.upper())
            
            result = self.market_api.get_candlesticks(
                instId=symbol.replace('/', '-'),
                bar=bar,
                limit=str(limit or 100)
            )
            if result['code'] == '0':
                return result['data']
            else:
                error_msg = f"获取K线数据失败: {result['msg']} | 错误码: {result['code']}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
        except Exception as e:
            error_msg = f"获取K线数据失败: {str(e)} | 堆栈信息: {traceback.format_exc()}"
            raise Exception(error_msg)

    async def fetch_order_book(self, symbol: str, limit: int = 5) -> Dict:
        """获取订单簿数据"""
        try:
            result = await asyncio.to_thread(
                self.market_api.get_orderbook,
                instId=symbol.replace('/', '-'),
                sz=str(limit)
            )
            if result['code'] == '0':
                return result['data'][0]
            else:
                error_msg = f"获取订单簿失败: {result['msg']} | 错误码: {result['code']}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
        except Exception as e:
            error_msg = f"获取订单簿失败: {str(e)} | 堆栈信息: {traceback.format_exc()}"
            self.logger.error(error_msg)
            raise Exception(error_msg)

    # ==================== 账户余额 ====================
    
    async def fetch_balance(self, params: Dict = None) -> Dict:
        """获取账户余额（含缓存机制）"""
        now = time.time()
        if now - self.balance_cache['timestamp'] < self.cache_ttl:
            return self.balance_cache['data']
        
        try:
            result = await asyncio.to_thread(self.account_api.get_account_balance)
            if result['code'] == '0':
                balance = {'free': {}, 'used': {}, 'total': {}}
                
                for item in result['data'][0]['details']:
                    asset = item['ccy']
                    free = float(item['availBal'])
                    total = float(item['eq'])
                    used = total - free
                    
                    balance['free'][asset] = free
                    balance['used'][asset] = used
                    balance['total'][asset] = total
                
                # 获取理财账户余额
                funding_balance = await self.fetch_funding_balance()
                # 合并现货和理财余额
                for asset, amount in funding_balance.items():
                    if asset not in balance['total']:
                        balance['total'][asset] = 0
                    if asset not in balance['free']:
                        balance['free'][asset] = 0
                    balance['total'][asset] += amount
                
                self.logger.debug(f"账户余额概要: {balance['total']}")
                # 更新缓存
                self.balance_cache = {
                    'timestamp': now,
                    'data': balance
                }
                return balance
            else:
                error_msg = f"获取余额失败: {result['msg']} | 错误码: {result['code']}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
        except Exception as e:
            error_msg = f"获取余额失败: {str(e)} | 堆栈信息: {traceback.format_exc()}"
            self.logger.error(error_msg)
            return {'free': {}, 'used': {}, 'total': {}}

    async def fetch_funding_balance(self) -> Dict:
        """获取理财账户余额（含缓存机制）"""
        now = time.time()
        if now - self.funding_balance_cache['timestamp'] < self.cache_ttl:
            return self.funding_balance_cache['data']
        
        try:
            result = self.funding_api.get_balances()
            if result['code'] == '0':
                balances = {"USDT": 0.0, BASE_CURRENCY: 0.0}
                for item in result['data']:
                    asset = item['ccy']
                    amount = float(item['availBal'])
                    balances[asset] = amount
                
                # 更新缓存
                self.funding_balance_cache = {
                    'timestamp': now,
                    'data': balances
                }
                return balances
            else:
                error_msg = f"获取理财账户余额失败: {result['msg']} | 错误码: {result['code']}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
        except Exception as e:
            error_msg = f"获取理财账户余额失败: {str(e)} | 堆栈信息: {traceback.format_exc()}"
            self.logger.error(error_msg)
            return self.funding_balance_cache['data'] if self.funding_balance_cache['data'] else {}

    # ==================== 订单操作 ====================
    
    async def create_order(
        self, 
        symbol: str, 
        type: str, 
        side: str, 
        amount: float, 
        price: float,
        pos_side: str = None
    ) -> Dict:
        """
        创建订单（自动适配现货/合约）
        
        Args:
            symbol: 交易对
            type: 订单类型 ('limit' / 'market')
            side: 交易方向 ('buy' / 'sell')
            amount: 数量
            price: 价格（市价单可为 None）
            pos_side: 持仓方向（合约双向持仓时必填：'long' / 'short'）
        """
        try:
            if self.trade_mode == 'swap':
                # 合约模式
                inst_id = SWAP_SYMBOL
                td_mode = self.margin_mode  # 'cross' 或 'isolated'
            else:
                # 现货模式
                inst_id = symbol.replace('/', '-')
                td_mode = 'cash'
            
            params = {
                'instId': inst_id,
                'tdMode': td_mode,
                'side': side.lower(),
                'ordType': type.lower(),
                'sz': str(amount)
            }
            
            # 合约双向持仓需要指定 posSide
            if self.trade_mode == 'swap' and self.pos_side != 'net':
                # 如果调用方指定了 pos_side 则使用，否则根据 side 推断
                if pos_side:
                    params['posSide'] = pos_side
                else:
                    params['posSide'] = 'long' if side.lower() == 'buy' else 'short'
            
            if type.lower() != 'market' and price is not None:
                params['px'] = str(price)
            
            self.logger.info(f"下单参数: {params}")
            result = await asyncio.to_thread(self.trade_api.place_order, **params)
            if result['code'] == '0':
                return result['data'][0]
            else:
                error_msg = f"下单失败: {result['msg']} | 错误码: {result['code']}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
        except Exception as e:
            error_msg = f"下单失败: {str(e)} | 堆栈信息: {traceback.format_exc()}"
            self.logger.error(error_msg)
            raise Exception(error_msg)

    async def fetch_order(self, order_id: str, symbol: str, params: Dict = None) -> Dict:
        """获取订单信息"""
        try:
            result = await asyncio.to_thread(
                self.trade_api.get_order,
                instId=symbol.replace('/', '-'),
                ordId=order_id
            )
            if result['code'] == '0':
                return result['data'][0]
            else:
                error_msg = f"获取订单失败: {result['msg']} | 错误码: {result['code']}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
        except Exception as e:
            error_msg = f"获取订单失败: {str(e)} | 堆栈信息: {traceback.format_exc()}"
            self.logger.error(error_msg)
            raise Exception(error_msg)

    async def fetch_open_orders(self, symbol: str) -> List:
        """获取当前未成交订单"""
        try:
            result = await asyncio.to_thread(
                self.trade_api.get_order_list,
                instId=symbol.replace('/', '-')
            )
            if result['code'] == '0':
                return result['data']
            else:
                error_msg = f"获取未成交订单失败: {result['msg']} | 错误码: {result['code']}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
        except Exception as e:
            error_msg = f"获取未成交订单失败: {str(e)} | 堆栈信息: {traceback.format_exc()}"
            self.logger.error(error_msg)
            raise Exception(error_msg)

    async def cancel_order(self, order_id: str, symbol: str, params: Dict = None) -> Dict:
        """取消指定订单"""
        try:
            result = await asyncio.to_thread(
                self.trade_api.cancel_order,
                instId=symbol.replace('/', '-'),
                ordId=order_id
            )
            if result['code'] == '0':
                return result['data'][0]
            else:
                error_msg = f"取消订单失败: {result['msg']} | 错误码: {result['code']}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
        except Exception as e:
            error_msg = f"取消订单失败: {str(e)} | 堆栈信息: {traceback.format_exc()}"
            self.logger.error(error_msg)
            raise Exception(error_msg)

    async def fetch_my_trades(self, symbol: str, limit: int = 10) -> List:
        """获取指定交易对的最近成交记录"""
        inst_type = 'SWAP' if self.trade_mode == 'swap' else 'SPOT'
        inst_id = SWAP_SYMBOL if self.trade_mode == 'swap' else symbol
        self.logger.debug(f"获取最近 {limit} 条成交记录 for {inst_id}...")
        if not self.markets_loaded:
            await self.load_markets()
        try:
            trades = await asyncio.to_thread(
                self.trade_api.get_orders_history,
                instType=inst_type,
                instId=inst_id,
                limit=limit
            )
            self.logger.info(f"成功获取 {len(trades)} 条最近成交记录 for {inst_id}")
            return trades
        except Exception as e:
            error_msg = f"获取成交记录失败: {str(e)} | 堆栈信息: {traceback.format_exc()}"
            self.logger.error(error_msg)
            return []

    # ==================== 资金划转 ====================
    
    async def transfer_to_spot(self, asset: str, amount: float) -> Dict:
        """从活期理财赎回到现货账户"""
        try:
            # 格式化金额
            if asset == 'USDT':
                formatted_amount = "{:.2f}".format(float(amount))
            elif asset == BASE_CURRENCY:
                formatted_amount = "{:.8f}".format(float(amount))
            else:
                formatted_amount = str(amount)
            
            params = {
                'ccy': asset,
                'amt': formatted_amount,
                'side': 'redempt',
                'rate': '0.03'
            }
            self.logger.info(f"开始赎回: {formatted_amount} {asset} 到现货")
            result = await asyncio.to_thread(
                self.savings_api.savings_purchase_redemption, 
                **params
            )
            self.logger.info(f"划转成功: {result}")
            
            # 清除缓存
            self._clear_balance_cache()
            
            return result
        except Exception as e:
            error_msg = f"赎回失败: {str(e)} | 堆栈信息: {traceback.format_exc()}"
            self.logger.error(error_msg)
            raise Exception(error_msg)

    async def transfer_to_savings(self, asset: str, amount: float) -> Dict:
        """从现货账户申购活期理财"""
        try:
            # 格式化金额
            if asset == 'USDT':
                formatted_amount = "{:.2f}".format(float(amount))
            elif asset == BASE_CURRENCY:
                formatted_amount = "{:.8f}".format(float(amount))
            else:
                formatted_amount = str(amount)
            
            params = {
                'ccy': asset,
                'amt': formatted_amount,
                'side': 'purchase',
            }
            self.logger.info(f"开始申购: {formatted_amount} {asset} 到活期理财")
            result = await asyncio.to_thread(
                self.savings_api.savings_purchase_redemption, 
                **params
            )
            self.logger.info(f"划转成功: {result}")
            
            # 清除缓存
            self._clear_balance_cache()
            
            return result
        except Exception as e:
            error_msg = f"申购失败: {str(e)} | 堆栈信息: {traceback.format_exc()}"
            self.logger.error(error_msg)
            raise Exception(error_msg)

    # ==================== 合约专用方法 ====================

    async def set_leverage(self, symbol: str = None, lever: int = None) -> Dict:
        """
        设置合约杠杆倍数
        
        Args:
            symbol: 合约交易对，默认使用 SWAP_SYMBOL
            lever: 杠杆倍数，默认使用配置中的 LEVERAGE
        """
        inst_id = symbol or SWAP_SYMBOL
        leverage = lever or self.leverage
        try:
            params = {
                'instId': inst_id,
                'lever': str(leverage),
                'mgnMode': self.margin_mode
            }
            result = await asyncio.to_thread(
                self.account_api.set_leverage, **params
            )
            if result['code'] == '0':
                self.logger.info(f"杠杆设置成功 | {inst_id} | {leverage}x | {self.margin_mode}")
                return result['data'][0]
            else:
                error_msg = f"设置杠杆失败: {result['msg']} | 错误码: {result['code']}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
        except Exception as e:
            error_msg = f"设置杠杆失败: {str(e)} | 堆栈信息: {traceback.format_exc()}"
            self.logger.error(error_msg)
            raise

    async def fetch_positions(self, symbol: str = None) -> List:
        """
        获取合约持仓信息
        
        Args:
            symbol: 合约交易对，默认使用 SWAP_SYMBOL
            
        Returns:
            持仓列表，每项包含 pos(数量)、avgPx(均价)、upl(未实现盈亏) 等
        """
        inst_id = symbol or SWAP_SYMBOL
        try:
            result = await asyncio.to_thread(
                self.account_api.get_positions,
                instType='SWAP',
                instId=inst_id
            )
            if result['code'] == '0':
                return result['data']
            else:
                error_msg = f"获取持仓失败: {result['msg']} | 错误码: {result['code']}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
        except Exception as e:
            error_msg = f"获取持仓失败: {str(e)} | 堆栈信息: {traceback.format_exc()}"
            self.logger.error(error_msg)
            return []

    async def close_position(self, symbol: str = None, pos_side: str = None) -> Dict:
        """
        市价全部平仓
        
        Args:
            symbol: 合约交易对
            pos_side: 持仓方向 ('long' / 'short' / 'net')
        """
        inst_id = symbol or SWAP_SYMBOL
        p_side = pos_side or self.pos_side
        try:
            params = {
                'instId': inst_id,
                'mgnMode': self.margin_mode,
            }
            if p_side != 'net':
                params['posSide'] = p_side
            
            result = await asyncio.to_thread(
                self.trade_api.close_positions, **params
            )
            if result['code'] == '0':
                self.logger.info(f"平仓成功 | {inst_id} | 方向: {p_side}")
                return result['data'][0]
            else:
                error_msg = f"平仓失败: {result['msg']} | 错误码: {result['code']}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
        except Exception as e:
            error_msg = f"平仓失败: {str(e)} | 堆栈信息: {traceback.format_exc()}"
            self.logger.error(error_msg)
            raise

    # ==================== 工具方法 ====================
    
    async def sync_time(self):
        """同步交易所服务器时间"""
        try:
            response = await asyncio.to_thread(self.public_api.get_system_time)
            if response['code'] == '0':
                server_time = int(response['data'][0]['ts'])
                local_time = int(time.time() * 1000)
                self.time_diff = server_time - local_time
                self.logger.info(f"时间同步完成 | 时差: {self.time_diff}ms")
            else:
                self.logger.error(f"获取系统时间失败: {response['msg']}")
        except Exception as e:
            error_msg = f"时间同步失败: {str(e)} | 堆栈信息: {traceback.format_exc()}"
            self.logger.error(error_msg)

    async def close(self):
        """关闭交易所连接"""
        try:
            self.logger.info("OKX交易所连接已安全关闭")
        except Exception as e:
            error_msg = f"关闭连接时发生错误: {str(e)} | 堆栈信息: {traceback.format_exc()}"
            self.logger.error(error_msg)

    def _clear_balance_cache(self):
        """清除余额缓存"""
        self.balance_cache = {'timestamp': 0, 'data': None}
        self.funding_balance_cache = {'timestamp': 0, 'data': {}}


# 导出
__all__ = ['ExchangeClient']
