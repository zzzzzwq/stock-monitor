"""交易日历"""
import logging
from datetime import datetime, timedelta

from data.akshare_data import is_trading_day as _is_trading_day

logger = logging.getLogger(__name__)


def is_trading_day(dt: datetime = None) -> bool:
    """判断是否为交易日"""
    return _is_trading_day(dt)


def next_trading_day(dt: datetime = None) -> str:
    """获取下一个交易日的日期字符串 YYYY-MM-DD"""
    dt = dt or datetime.now()
    for i in range(1, 8):
        candidate = dt + timedelta(days=i)
        if is_trading_day(candidate):
            return candidate.strftime("%Y-%m-%d")
    return ""


def last_trading_day(dt: datetime = None) -> str:
    """获取上一个交易日的日期字符串 YYYY-MM-DD"""
    dt = dt or datetime.now()
    for i in range(1, 8):
        candidate = dt - timedelta(days=i)
        if is_trading_day(candidate):
            return candidate.strftime("%Y-%m-%d")
    return ""
