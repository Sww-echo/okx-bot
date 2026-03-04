"""Strategy lifecycle use cases."""

from ..config.constants import STRATEGY_MODE
from .errors import InvalidActionError, InvalidModeError


class StrategyService:
    """Encapsulates strategy start/stop/pause/resume operations."""

    def __init__(self, manager):
        self.manager = manager

    async def start(self, mode='grid'):
        try:
            await self.manager.start_strategy(mode)
        except ValueError as exc:
            raise InvalidModeError(str(exc)) from exc

        return {
            'status': 'ok',
            'message': f'{mode} 策略已启动',
            'active_mode': self.manager.active_mode,
        }

    async def stop(self):
        await self.manager.stop_strategy()
        return {'status': 'ok', 'message': '策略已停止'}

    async def pause(self):
        await self.manager.pause_strategy()
        return {'status': 'ok', 'message': '策略已暂停'}

    async def resume(self):
        await self.manager.resume_strategy()
        return {'status': 'ok', 'message': '策略已恢复'}

    async def execute_action(self, action):
        """Legacy action endpoint compatibility."""
        if action == 'pause':
            await self.manager.pause_strategy()
        elif action in ('start', 'resume'):
            if self.manager.trader is None:
                await self.manager.start_strategy(STRATEGY_MODE)
            else:
                await self.manager.resume_strategy()
        elif action == 'stop':
            await self.manager.stop_strategy()
        else:
            raise InvalidActionError(f'Unknown action: {action}')

        return {'status': 'ok', 'action': action}
