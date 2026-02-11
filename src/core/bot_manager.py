"""
策略管理器
负责按需创建、初始化、启停交易策略
支持前端 API 和 CLI 两种控制方式
"""
import asyncio
import logging
from datetime import datetime

from ..config.settings import TradingConfig, MAConfig
from ..config.constants import STRATEGY_MODE
from ..core.trade import GridTrader
from ..core.ma_trade import MATrader


class BotManager:
    """统一管理 Grid / MA 策略的生命周期"""

    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

        # 当前运行的策略
        self.trader = None           # GridTrader | MATrader | None
        self.active_mode = None      # 'grid' | 'ma' | None
        self.status = 'idle'         # 'idle' | 'initializing' | 'running' | 'paused'
        self._task = None            # asyncio.Task for trader.start()
        self.start_time = None       # 策略启动时间

    # ── 策略生命周期 ─────────────────────────────────

    async def start_strategy(self, mode: str):
        """
        启动指定策略。如果已有策略在运行，先停止。

        Args:
            mode: 'grid' 或 'ma'
        """
        if mode not in ('grid', 'ma'):
            raise ValueError(f"未知策略模式: {mode}，仅支持 'grid' 或 'ma'")

        # 如果同一策略已在运行
        if self.active_mode == mode and self.status == 'running':
            self.logger.info(f"{mode} 策略已在运行中，跳过")
            return

        # 停止旧策略
        if self.trader is not None:
            self.logger.info(f"切换策略：停止 {self.active_mode}...")
            await self.stop_strategy()

        self.status = 'initializing'
        self.active_mode = mode

        try:
            if mode == 'ma':
                # 挂载 MA 配置到 TradingConfig
                if not hasattr(self.config, 'MA') or self.config.MA is None:
                    self.config.MA = MAConfig()
                self.logger.info("双均线趋势策略 (MA Strategy) 启动")
                self.trader = MATrader(self.config)
            else:
                self.logger.info("网格交易系统 (Grid Strategy) 启动")
                self.trader = GridTrader(self.config)

            # 初始化（带重试）
            max_retries = 5
            for attempt in range(1, max_retries + 1):
                try:
                    await self.trader.initialize()
                    break
                except Exception as e:
                    if attempt < max_retries:
                        wait = min(attempt * 3, 15)
                        self.logger.warning(f"初始化失败 (第{attempt}/{max_retries}次): {e}")
                        await asyncio.sleep(wait)
                    else:
                        self.logger.error(f"初始化失败，已达最大重试次数: {e}")
                        self.trader = None
                        self.active_mode = None
                        self.status = 'idle'
                        raise

            # 启动交易循环 (后台任务)
            self._task = asyncio.create_task(self._run_trader())
            self.status = 'running'
            self.start_time = datetime.now()
            self.logger.info(f"{mode} 策略已启动")

        except Exception as e:
            self.status = 'idle'
            self.active_mode = None
            self.trader = None
            raise

    async def _run_trader(self):
        """包装 trader.start()，捕获异常避免 Task 静默失败"""
        try:
            await self.trader.start()
        except asyncio.CancelledError:
            self.logger.info("交易任务已被取消")
        except Exception as e:
            self.logger.error(f"交易循环异常退出: {e}", exc_info=True)
            self.status = 'idle'
            self.trader = None
            self.active_mode = None
            self._task = None

    async def pause_strategy(self):
        """暂停当前策略"""
        if self.trader is None:
            raise RuntimeError("没有正在运行的策略")
        await self.trader.set_paused(True)
        self.status = 'paused'
        self.logger.info(f"{self.active_mode} 策略已暂停")

    async def resume_strategy(self):
        """恢复当前策略"""
        if self.trader is None:
            raise RuntimeError("没有正在运行的策略")
        await self.trader.set_paused(False)
        self.status = 'running'
        self.logger.info(f"{self.active_mode} 策略已恢复")

    async def stop_strategy(self):
        """停止当前策略并释放资源"""
        if self.trader is None:
            return

        mode = self.active_mode
        self.logger.info(f"正在停止 {mode} 策略...")

        try:
            await self.trader.shutdown()
        except Exception as e:
            self.logger.error(f"关闭策略时异常: {e}")

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        self.trader = None
        self._task = None
        self.active_mode = None
        self.status = 'idle'
        self.start_time = None
        self.logger.info(f"{mode} 策略已停止")

    # ── 状态查询 ─────────────────────────────────────

    def get_status(self):
        """返回当前策略管理器状态"""
        result = {
            'status': self.status,
            'active_mode': self.active_mode,
            'uptime': None,
        }

        if self.start_time:
            result['uptime'] = str(datetime.now() - self.start_time).split('.')[0]

        return result

    async def shutdown(self):
        """完全关闭（供 main.py 信号处理器调用）"""
        if self.trader:
            await self.stop_strategy()
        self.logger.info("BotManager 已关闭")


__all__ = ['BotManager']
