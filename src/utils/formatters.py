"""
格式化模块
提供消息格式化功能
"""
import time


def format_trade_message(
    side: str,
    symbol: str,
    price: float,
    amount: float,
    total: float,
    grid_size: float,
    retry_count: tuple = None
) -> str:
    """
    格式化交易消息为美观的文本格式
    
    Args:
        side: 交易方向 ('buy' 或 'sell')
        symbol: 交易对
        price: 交易价格
        amount: 交易数量
        total: 交易总额
        grid_size: 网格大小
        retry_count: 重试次数，格式为 (当前次数, 最大次数)
    
    Returns:
        格式化后的消息文本
    """
    # 使用emoji增加可读性
    direction_emoji = "🟢" if side == 'buy' else "🔴"
    direction_text = "买入" if side == 'buy' else "卖出"
    
    # 构建消息主体
    message = f"""
{direction_emoji} {direction_text} {symbol}
━━━━━━━━━━━━━━━━━━━━
💰 价格：{price:.2f} USDT
📊 数量：{amount:.4f} OKB
💵 金额：{total:.2f} USDT
📈 网格：{grid_size}%
"""
    
    # 如果有重试信息，添加重试次数
    if retry_count:
        current, max_retries = retry_count
        message += f"🔄 尝试：{current}/{max_retries}次\n"
    
    # 添加时间戳
    message += f"⏰ 时间：{time.strftime('%Y-%m-%d %H:%M:%S')}"
    
    return message


def format_error_message(
    error_type: str,
    symbol: str,
    error: str
) -> str:
    """
    格式化错误消息
    
    Args:
        error_type: 错误类型（如 'buy 失败'）
        symbol: 交易对
        error: 错误信息
        
    Returns:
        格式化后的错误消息
    """
    return f"""❌ 交易失败
━━━━━━━━━━━━━━━━━━━━
🔍 类型: {error_type}
📊 交易对: {symbol}
⚠️ 错误: {error}
⏰ 时间：{time.strftime('%Y-%m-%d %H:%M:%S')}
"""


def format_status_message(
    symbol: str,
    base_price: float,
    current_price: float,
    grid_size: float,
    position_ratio: float = None
) -> str:
    """
    格式化状态消息
    
    Args:
        symbol: 交易对
        base_price: 基准价格
        current_price: 当前价格
        grid_size: 网格大小
        position_ratio: 仓位比例
        
    Returns:
        格式化后的状态消息
    """
    price_diff = (current_price - base_price) / base_price * 100 if base_price > 0 else 0
    
    message = f"""📊 交易状态
━━━━━━━━━━━━━━━━━━━━
📈 交易对: {symbol}
💰 基准价: {base_price:.2f} USDT
📊 当前价: {current_price:.2f} USDT
📉 价差: {price_diff:+.2f}%
📏 网格: {grid_size}%
"""
    
    if position_ratio is not None:
        message += f"📦 仓位: {position_ratio:.2%}\n"
    
    message += f"⏰ 时间：{time.strftime('%Y-%m-%d %H:%M:%S')}"
    
    return message


# 导出
__all__ = ['format_trade_message', 'format_error_message', 'format_status_message']
