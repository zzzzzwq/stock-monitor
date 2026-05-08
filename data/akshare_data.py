"""akshare 数据封装（统一异常处理 + 降级）"""
import logging
from datetime import datetime, timedelta

import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)

# 交易日缓存
_TRADE_CALENDAR = None
_CALENDAR_DATE = None


def is_trading_day(dt: datetime = None) -> bool:
    """判断指定日期是否为交易日（缓存每日结果）"""
    global _TRADE_CALENDAR, _CALENDAR_DATE

    dt = dt or datetime.now()
    date_str = dt.strftime("%Y-%m-%d")

    if _TRADE_CALENDAR is not None and _CALENDAR_DATE == date_str:
        return True

    try:
        cal = ak.tool_trade_date_hist_sina()
        cal["trade_date"] = pd.to_datetime(cal["trade_date"])
        _TRADE_CALENDAR = set(cal["trade_date"].dt.strftime("%Y-%m-%d").tolist())
        _CALENDAR_DATE = date_str
        return date_str in _TRADE_CALENDAR
    except Exception as e:
        logger.warning(f"交易日历获取失败: {e}")
        return dt.weekday() < 5  # 降级: 仅跳过周末


def get_history(code: str, days: int = 180) -> pd.DataFrame:
    """获取日K线数据（前复权）"""
    end = datetime.now()
    start = end - timedelta(days=days + 30)  # 多取一些确保有足够数据
    try:
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust="qfq",
        )
        if df.empty:
            logger.warning(f"{code} 历史数据为空")
            return pd.DataFrame()
        return df
    except Exception as e:
        logger.error(f"获取 {code} 历史K线失败: {e}")
        return pd.DataFrame()


def _get_board_df(name_col: str = "板块名称") -> pd.DataFrame:
    """获取行业板块排行，兼容新版akshare"""
    try:
        df = ak.stock_board_industry_name_em()
        if not df.empty and "涨跌幅" in df.columns:
            df["涨跌幅"] = pd.to_numeric(df["涨跌幅"], errors="coerce")
        return df
    except Exception as e:
        logger.warning(f"行业板块获取失败: {e}")
        return pd.DataFrame()


def _lookup_in_df(df: pd.DataFrame, names: list[str], name_col: str = "板块名称") -> dict[str, float]:
    """在DataFrame中查找板块涨跌幅"""
    result = {}
    for name in names:
        row = df[df[name_col] == name]
        if not row.empty:
            result[name] = float(row["涨跌幅"].iloc[0])
        else:
            result[name] = None
    return result


def get_related_board_changes(board_names: list[str]) -> dict[str, float]:
    """获取相关板块涨跌幅（先查行业板块，没有再查概念板块）"""
    df = _get_board_df()
    if df.empty:
        return {}

    result = _lookup_in_df(df, board_names)

    # 对未找到的板块查概念板块
    missing = [n for n, v in result.items() if v is None]
    if missing:
        try:
            concept_df = ak.stock_board_concept_name_em()
            if not concept_df.empty and "涨跌幅" in concept_df.columns:
                concept_df["涨跌幅"] = pd.to_numeric(concept_df["涨跌幅"], errors="coerce")
            concept_result = _lookup_in_df(concept_df, missing)
            result.update(concept_result)
        except Exception as e:
            logger.warning(f"概念板块获取失败: {e}")

    return result


def get_market_sentiment() -> dict:
    """获取大盘情绪：涨跌家数、资金流向"""
    result = {}
    try:
        df = ak.stock_market_fund_flow()
        if df is not None and not df.empty:
            row = df.iloc[-1]
            result["fund_flow"] = {
                "date": str(row.iloc[0]),
                "main_net": round(float(row.iloc[5]) / 1e8, 2) if len(row) > 5 else 0,
                "main_pct": round(float(row.iloc[6]), 2) if len(row) > 6 else 0,
                "super_large_net": round(float(row.iloc[7]) / 1e8, 2) if len(row) > 7 else 0,
                "large_net": round(float(row.iloc[9]) / 1e8, 2) if len(row) > 9 else 0,
                "medium_net": round(float(row.iloc[11]) / 1e8, 2) if len(row) > 11 else 0,
                "small_net": round(float(row.iloc[13]) / 1e8, 2) if len(row) > 13 else 0,
            }
    except Exception as e:
        logger.warning(f"市场情绪获取失败: {e}")

    return result


def get_top_boards(top_n: int = 10) -> dict:
    """获取全市场最强/最弱板块"""
    result = {"top": [], "bottom": []}
    try:
        df = ak.stock_board_industry_name_em()
        if df is not None and not df.empty:
            df["涨跌幅"] = pd.to_numeric(df["涨跌幅"], errors="coerce")
            df = df.dropna(subset=["涨跌幅"])
            for _, row in df.nlargest(top_n, "涨跌幅").iterrows():
                result["top"].append({
                    "name": str(row.get("板块名称", "")),
                    "change_pct": round(float(row["涨跌幅"]), 2),
                })
            for _, row in df.nsmallest(top_n, "涨跌幅").iterrows():
                result["bottom"].append({
                    "name": str(row.get("板块名称", "")),
                    "change_pct": round(float(row["涨跌幅"]), 2),
                })
    except Exception as e:
        logger.warning(f"板块排行获取失败: {e}")

    return result


def get_index_tech(symbol: str = "sh000001") -> dict:
    """获取大盘指数的技术面简评（用于市场环境判断）"""
    try:
        # sh000001/SH000001 -> akshare 格式
        code = symbol.replace("sh", "SH").replace("sz", "SZ")
        df = ak.stock_zh_index_daily(symbol=f"s{code}")
        if df.empty:
            return {}
        df.columns = ["date", "open", "close", "high", "low", "volume"]
        close = df["close"]
        cur = float(close.iloc[-1])
        ma5 = float(close.rolling(5).mean().iloc[-1])
        ma10 = float(close.rolling(10).mean().iloc[-1])
        ma20 = float(close.rolling(20).mean().iloc[-1])
        ma_stat = "多头" if cur > ma5 > ma10 > ma20 else "空头" if cur < ma5 < ma10 < ma20 else "纠缠"
        return {
            "price": round(cur, 2),
            "ma5": round(ma5, 2),
            "ma10": round(ma10, 2),
            "ma20": round(ma20, 2),
            "ma_status": ma_stat,
        }
    except Exception as e:
        logger.warning(f"指数技术面获取失败: {e}")
        return {}


def get_news(code: str) -> list[dict]:
    """获取个股新闻"""
    try:
        news = ak.stock_news_em(symbol=code)
        if news is not None and not news.empty:
            items = []
            for _, row in news.head(10).iterrows():
                items.append({
                    "title": str(row.get("新闻标题", row.get("title", ""))),
                    "time": str(row.get("发布时间", row.get("datetime", ""))),
                })
            return items
    except Exception as e:
        logger.warning(f"获取 {code} 新闻失败: {e}")
    return []
