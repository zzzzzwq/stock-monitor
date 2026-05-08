"""A股股票列表缓存 + 搜索"""
import os
import json
import logging
import pickle
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "stocks_cache.pkl")
CACHE_EXPIRY = timedelta(days=1)

_stocks = None  # [{code, name, market}]


def _fetch_stock_list() -> list[dict]:
    """从 akshare 获取全市场股票列表"""
    try:
        import akshare as ak
        df = ak.stock_info_a_code_name()
        if df.empty:
            return []
        stocks = []
        for _, row in df.iterrows():
            code = str(row.iloc[0]).strip().zfill(6)
            name = str(row.iloc[1]).strip()
            # 判断市场: 6开头=上交所, 0/3开头=深交所
            market = "sh" if code.startswith("6") else "sz"
            stocks.append({"code": code, "name": name, "market": market})
        logger.info(f"获取股票列表: {len(stocks)} 只")
        return stocks
    except Exception as e:
        logger.error(f"获取股票列表失败: {e}")
        return []


def _load_cached() -> list[dict] | None:
    """加载缓存的股票列表"""
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "rb") as f:
                data = pickle.load(f)
            if data.get("time") and datetime.now() - data["time"] < CACHE_EXPIRY:
                return data["stocks"]
    except Exception:
        pass
    return None


def _save_cache(stocks: list[dict]):
    """缓存股票列表"""
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "wb") as f:
            pickle.dump({"time": datetime.now(), "stocks": stocks}, f)
    except Exception as e:
        logger.warning(f"缓存股票列表失败: {e}")


def get_stock_list(force_refresh: bool = False) -> list[dict]:
    """获取全部股票列表（带缓存）"""
    global _stocks
    if _stocks is not None and not force_refresh:
        return _stocks
    stocks = _load_cached()
    if stocks is None or force_refresh:
        stocks = _fetch_stock_list()
        if stocks:
            _save_cache(stocks)
    _stocks = stocks or []
    return _stocks


def search_stocks(query: str, limit: int = 20) -> list[dict]:
    """搜索股票（支持代码或名称模糊匹配）"""
    if not query or len(query.strip()) < 1:
        return []
    q = query.strip().lower()
    stocks = get_stock_list()
    results = []
    for s in stocks:
        # 精确代码匹配、代码包含、名称包含
        if q == s["code"] or q in s["code"] or q in s["name"].lower():
            results.append(s)
            if len(results) >= limit:
                break
    # 排序：精确匹配 > 代码开头匹配 > 代码包含 > 名称匹配
    def sort_key(x):
        if q == x["code"]:
            return 0
        if x["code"].startswith(q):
            return 1
        if q in x["code"]:
            return 2
        return 3
    results.sort(key=lambda x: (sort_key(x), x["code"]))
    return results[:limit]
