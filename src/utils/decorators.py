"""
装饰器模块
提供通用的装饰器函数
"""
import logging
import time
import psutil
import asyncio
from functools import wraps
from tenacity import retry, stop_after_attempt, wait_exponential


def debug_watcher():
    """
    资源监控装饰器
    用于监控异步函数的执行时间和内存使用
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()
            mem_before = psutil.virtual_memory().used
            logging.debug(f"[DEBUG] 开始执行 {func.__name__}")
            
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                cost = time.time() - start
                mem_used = psutil.virtual_memory().used - mem_before
                logging.debug(
                    f"[DEBUG] {func.__name__} 执行完成 | "
                    f"耗时: {cost:.3f}s | "
                    f"内存变化: {mem_used/1024/1024:.2f}MB"
                )
        return wrapper
    return decorator


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def safe_fetch(method, *args, **kwargs):
    """
    带重试机制的安全请求函数
    
    Args:
        method: 要调用的异步方法
        *args: 位置参数
        **kwargs: 关键字参数
        
    Returns:
        方法返回值
        
    Raises:
        Exception: 重试3次后仍失败时抛出
    """
    try:
        return await method(*args, **kwargs)
    except Exception as e:
        logging.error(f"请求失败: {str(e)}")
        raise


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """
    通用重试装饰器
    
    Args:
        max_retries: 最大重试次数
        delay: 重试间隔（秒）
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries:
                        logging.warning(
                            f"{func.__name__} 执行失败，"
                            f"{delay}秒后进行第{attempt + 1}次重试: {str(e)}"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logging.error(
                            f"{func.__name__} 失败，"
                            f"达到最大重试次数({max_retries}次): {str(e)}"
                        )
            raise last_error
        return wrapper
    return decorator


# 导出
__all__ = ['debug_watcher', 'safe_fetch', 'retry_on_failure']
