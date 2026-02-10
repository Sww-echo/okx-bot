"""
辅助函数兼容层
此文件保留是为了兼容旧代码，将请求转发到新的 src 模块
"""
from src.utils.logging import LogConfig
from src.utils.formatters import format_trade_message
from src.services.notification import send_pushplus_message
from src.utils.decorators import safe_fetch, debug_watcher

# 重新导出
__all__ = [
    'LogConfig',
    'format_trade_message',
    'send_pushplus_message',
    'safe_fetch',
    'debug_watcher'
]