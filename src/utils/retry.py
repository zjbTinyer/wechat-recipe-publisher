"""
重试工具模块
提供指数退避 + 随机抖动的重试装饰器，适用于网络请求和 API 调用
"""
import time
import functools
import random
import logging

logger = logging.getLogger("recipe_publisher")


def retry(max_attempts: int = 3, base_delay: float = 2.0, backoff: float = 2.0,
          exceptions: tuple = (Exception,)):
    """重试装饰器

    Args:
        max_attempts: 最大尝试次数（包含第一次）
        base_delay: 基础延迟秒数
        backoff: 退避倍数
        exceptions: 捕获的异常类型元组

    延迟公式: base_delay * (backoff ^ (attempt - 1)) * random_jitter
    其中 random_jitter 在 [0.5, 1.5] 之间
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt < max_attempts:
                        delay = base_delay * (backoff ** (attempt - 1))
                        delay *= 0.5 + random.random()  # [0.5, 1.5] 抖动
                        logger.warning(
                            f"第 {attempt}/{max_attempts} 次尝试失败: {e}. "
                            f"{delay:.1f}s 后重试..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"已重试 {max_attempts} 次，全部失败: {e}"
                        )
            raise last_exc  # type: ignore
        return wrapper
    return decorator
