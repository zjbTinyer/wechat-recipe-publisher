"""
日志配置模块
统一的日志格式和级别控制，方便在 GitHub Actions 中查看运行状态
"""
import logging
import sys


def setup_logger(level: str = "INFO") -> logging.Logger:
    """配置并返回根 logger

    Args:
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR)

    Returns:
        配置好的 root logger
    """
    logger = logging.getLogger("recipe_publisher")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 控制台输出（GitHub Actions 会捕获 stdout）
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)

    # 格式：时间 | 级别 | 消息
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
