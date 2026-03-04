"""Configuration query/update use cases."""

from ..config.constants import STRATEGY_MODE
from ..config.settings import MAConfig


class ConfigService:
    """Handles strategy config shape and runtime update behavior."""

    def __init__(self, manager):
        self.manager = manager

    def get_config(self):
        mode = self.manager.active_mode or STRATEGY_MODE
        params = {}
        risk = {}

        if mode == 'ma':
            if not hasattr(self.manager.config, 'MA') or self.manager.config.MA is None:
                self.manager.config.MA = MAConfig()

            c = self.manager.config.MA
            params = {
                k: getattr(c, k)
                for k in dir(c)
                if k.isupper() and not k.startswith('_') and not callable(getattr(c, k, None))
            }
        else:
            c = self.manager.config
            params = {
                'INITIAL_GRID': getattr(c, 'INITIAL_GRID', 0.5),
                'GRID_MIN': c.GRID_PARAMS.get('min', 1.0) if hasattr(c, 'GRID_PARAMS') else 1.0,
                'GRID_MAX': c.GRID_PARAMS.get('max', 4.0) if hasattr(c, 'GRID_PARAMS') else 4.0,
                'BASE_AMOUNT': getattr(c, 'BASE_AMOUNT', 50.0),
                'MIN_TRADE_AMOUNT': getattr(c, 'MIN_TRADE_AMOUNT', 20.0),
                'MAX_POSITION_RATIO': getattr(c, 'MAX_POSITION_RATIO', 0.9),
                'POSITION_SCALE_FACTOR': getattr(c, 'POSITION_SCALE_FACTOR', 0.2),
                'COOLDOWN': getattr(c, 'COOLDOWN', 60),
                'VOLATILITY_WINDOW': getattr(c, 'VOLATILITY_WINDOW', 24),
            }

        if hasattr(self.manager.config, 'RISK_PARAMS'):
            rp = self.manager.config.RISK_PARAMS
            risk = {
                'MAX_DRAWDOWN': rp.get('max_drawdown', -0.15),
                'DAILY_LOSS_LIMIT': rp.get('daily_loss_limit', -0.05),
            }

        return {'mode': mode, 'params': params, 'risk': risk}

    async def update_config(self, data):
        mode = data.get('mode', STRATEGY_MODE)
        new_params = data.get('params', data.get('ma_config', {}))

        if mode == 'ma':
            if not hasattr(self.manager.config, 'MA') or self.manager.config.MA is None:
                self.manager.config.MA = MAConfig()

            c = self.manager.config.MA
            for k, v in new_params.items():
                if hasattr(c, k):
                    setattr(c, k, type(getattr(c, k))(v))
        else:
            c = self.manager.config
            grid_keys_map = {
                'GRID_MIN': lambda v: c.GRID_PARAMS.update({'min': v}),
                'GRID_MAX': lambda v: c.GRID_PARAMS.update({'max': v}),
            }
            for k, v in new_params.items():
                if k in grid_keys_map:
                    grid_keys_map[k](v)
                elif hasattr(c, k):
                    setattr(c, k, type(getattr(c, k))(v))

        trader = self.manager.trader
        if trader and hasattr(trader, 'reload_strategy'):
            await trader.reload_strategy()

        return {'status': 'updated', 'mode': mode, 'params': new_params}
