"""Backtest orchestration use cases."""

import os
import pandas as pd

from ..backtest.backtester import Backtester
from ..config.settings import MAConfig
from .errors import ResourceNotFoundError


class BacktestService:
    """Runs backtests and caches the latest result."""

    def __init__(self, manager):
        self.manager = manager
        self.last_result = None

    async def run_backtest(self, data):
        symbol = data.get('symbol', 'ETH/USDT')
        start = data.get('start', '2025-01-01')
        end = data.get('end', '2025-12-31')

        config = MAConfig()
        trader = self.manager.trader
        if trader and hasattr(trader, 'ma_config'):
            for k in dir(trader.ma_config):
                if k.isupper():
                    setattr(config, k, getattr(trader.ma_config, k))

        config.SYMBOL = symbol

        path = f"data/{symbol.replace('/', '-')}_1H_{start}_{end}.csv"
        if not os.path.exists(path):
            raise ResourceNotFoundError(
                f'Data file not found: {path}. Run backtest script first to download data.'
            )

        df = pd.read_csv(path)
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df['timestamp'] = df['timestamp'].astype(int)
        df = df.dropna(subset=['close'])

        bt = Backtester(config, initial_balance=10000)
        await bt.run(df)
        report = bt.generate_report()

        result = {
            'total_return': report.total_return,
            'win_rate': report.win_rate,
            'max_drawdown': report.max_drawdown,
            'total_trades': report.total_trades,
            'trades': report.trades,
        }

        self.last_result = result
        return result

    def get_last_result(self):
        return self.last_result or {}
