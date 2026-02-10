"""
网格交易系统主入口
"""
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

from src.core.trade import GridTrader
from src.config.settings import TradingConfig
from src.utils.logging import LogConfig
from src.services.notification import send_pushplus_message
from src.web.server import WebServer


# 在Windows平台上设置SelectorEventLoop
if platform.system() == 'Windows':
    # 在Windows平台上强制使用SelectorEventLoop
    if sys.version_info[0] == 3 and sys.version_info[1] >= 8:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def main():
    trader = None
    try:
        # 初始化统一日志配置
        LogConfig.setup_logger()
        logging.info("="*50)
        logging.info("网格交易系统 (Refactored) 启动")
        logging.info("="*50)
        
        # 创建配置和交易器实例
        config = TradingConfig()
        trader = GridTrader(config)
        
        # 注册信号处理器（优雅退出）
        loop = asyncio.get_running_loop()
        
        def _signal_handler():
            logging.info("接收到退出信号，正在优雅关闭...")
            if trader:
                asyncio.ensure_future(trader.shutdown())
        
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _signal_handler)
            except NotImplementedError:
                # Windows 不支持 add_signal_handler，使用备选方案
                signal.signal(sig, lambda s, f: _signal_handler())
        
        # 初始化交易器（带重试）
        max_init_retries = 10
        for attempt in range(1, max_init_retries + 1):
            try:
                await trader.initialize()
                break
            except Exception as e:
                if attempt < max_init_retries:
                    wait = min(attempt * 5, 30)
                    logging.warning(f"初始化失败 (第{attempt}/{max_init_retries}次): {str(e)}")
                    logging.info(f"{wait}秒后重试...")
                    await asyncio.sleep(wait)
                else:
                    logging.error(f"初始化失败，已达最大重试次数: {str(e)}")
                    raise
        
        # 启动Web服务器
        server = WebServer(trader)
        web_server_task = asyncio.create_task(server.start())
        
        # 启动交易循环
        trading_task = asyncio.create_task(trader.start())
        
        # 等待所有任务完成
        await asyncio.gather(web_server_task, trading_task)
        
    except KeyboardInterrupt:
        logging.info("接收到退出信号，正在停止...")
    except Exception as e:
        error_msg = f"启动失败: {str(e)}\n{traceback.format_exc()}"
        logging.error(error_msg)
    finally:
        if trader:
            await trader.shutdown()
        logging.info("系统已完全关闭")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
