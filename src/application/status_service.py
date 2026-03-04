"""Status and log retrieval use cases."""

import os
import aiofiles

from ..utils.logging import LogConfig


class StatusService:
    """Builds API-facing status payloads from manager/trader state."""

    def __init__(self, manager):
        self.manager = manager

    async def read_log_content(self):
        log_path = os.path.join(LogConfig.LOG_DIR, LogConfig.LOG_FILE)
        if not os.path.exists(log_path):
            return 'No log file found.'

        async with aiofiles.open(log_path, mode='r', encoding='utf-8') as f:
            content = await f.read()

        lines = content.strip().split('\n')
        return '\n'.join(lines[-200:])

    async def get_status(self):
        mgr = self.manager
        trader = mgr.trader

        mgr_status = mgr.get_status()
        status = {
            'status': mgr_status['status'],
            'active_mode': mgr_status['active_mode'],
            'uptime': mgr_status['uptime'] or '—',
            'balance': 0,
            'total_pnl': 0,
            'positions': [],
            'recent_trades': [],
        }

        if trader is None:
            return status

        if hasattr(trader, 'balance_service'):
            try:
                avail = await trader.balance_service.get_available_balance('USDT')
                status['balance'] = avail
            except Exception:
                pass

        if hasattr(trader, 'position_tracker'):
            pos_list = []
            total_pnl = 0
            for symbol, pos in trader.position_tracker.positions.items():
                pnl = pos.get('unrealized_pnl', 0)
                total_pnl += pnl
                pos_list.append({
                    'symbol': symbol,
                    'side': pos.get('side'),
                    'amount': pos.get('amount'),
                    'entry_price': pos.get('entry_price'),
                    'pnl': pnl,
                })
            status['positions'] = pos_list
            status['total_pnl'] = total_pnl

        if hasattr(trader, 'trade_history'):
            status['recent_trades'] = trader.trade_history[-20:]
        elif hasattr(trader, 'order_manager'):
            try:
                history = trader.order_manager.get_trade_history()
                status['recent_trades'] = history[-20:] if history else []
            except Exception:
                pass

        return status
