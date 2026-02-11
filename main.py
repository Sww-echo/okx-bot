"""
OKX 交易系统主入口

使用方式:
  python main.py                     # 仅启动 Web 服务，等待前端控制
  python main.py --strategy grid     # 启动 Web 服务 + 自动运行网格策略
  python main.py --strategy ma       # 启动 Web 服务 + 自动运行 MA 策略
"""
import argparse
import asyncio
import logging
import traceback
import platform
import sys
import os
import ssl
import signal

# 忽略 SSL 证书验证（仅用于开发环境）
ssl._create_default_https_context = ssl._create_unverified_context

from src.config.settings import TradingConfig
from src.utils.logging import LogConfig
from src.web.server import WebServer
from src.core.bot_manager import BotManager


# 在Windows平台上设置SelectorEventLoop
if platform.system() == 'Windows':
    if sys.version_info[0] == 3 and sys.version_info[1] >= 8:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def parse_args():
    parser = argparse.ArgumentParser(description='OKX 交易系统')
    parser.add_argument(
        '--strategy', '-s',
        choices=['grid', 'ma'],
        default=None,
        help='启动时自动运行的策略 (grid=网格, ma=双均线)。不指定则仅启动 Web 服务。'
    )
    parser.add_argument(
        '--port', '-p',
        type=int,
        default=58181,
        help='Web 服务端口 (默认 58181)'
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    manager = None

    try:
        # 初始化日志
        LogConfig.setup_logger()
        logging.info("=" * 50)
        logging.info("OKX 交易系统启动")

        # 创建配置和策略管理器
        config = TradingConfig()
        manager = BotManager(config)

        # 注册信号处理器
        loop = asyncio.get_running_loop()

        def _signal_handler():
            logging.info("接收到退出信号，正在优雅关闭...")
            asyncio.ensure_future(manager.shutdown())

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _signal_handler)
            except NotImplementedError:
                signal.signal(sig, lambda s, f: _signal_handler())

        # 启动 Web 服务器
        server = WebServer(manager, port=args.port)
        await server.start()
        logging.info("=" * 50)

        # 如果 CLI 指定了策略，自动启动
        if args.strategy:
            logging.info(f"CLI 指定策略: {args.strategy}，自动启动...")
            await manager.start_strategy(args.strategy)
        else:
            logging.info("等待前端控制面板启动策略...")

        # 保持运行
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logging.info("接收到退出信号，正在停止...")
    except Exception as e:
        error_msg = f"启动失败: {str(e)}\n{traceback.format_exc()}"
        logging.error(error_msg)
    finally:
        if manager:
            await manager.shutdown()
        logging.info("系统已完全关闭")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
