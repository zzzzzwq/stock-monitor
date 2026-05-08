"""技术指标计算（从现有3个脚本提取公共逻辑）"""
import pandas as pd
import numpy as np


def calc_mas(df: pd.DataFrame) -> dict:
    """计算均线，返回 {ma5, ma10, ma20, ma60}"""
    close = df["收盘"] if "收盘" in df.columns else df["close"]
    return {
        "ma5": close.rolling(5).mean().iloc[-1],
        "ma10": close.rolling(10).mean().iloc[-1],
        "ma20": close.rolling(20).mean().iloc[-1],
        "ma60": close.rolling(60).mean().iloc[-1] if len(close) >= 60 else None,
    }


def calc_macd(df: pd.DataFrame) -> dict:
    """计算MACD，返回 {dif, dea, bar, bar_prev, trend}"""
    close = df["收盘"] if "收盘" in df.columns else df["close"]
    exp12 = close.ewm(span=12).mean()
    exp26 = close.ewm(span=26).mean()
    dif = exp12 - exp26
    dea = dif.ewm(span=9).mean()
    bar = 2 * (dif - dea)
    return {
        "dif": dif.iloc[-1],
        "dea": dea.iloc[-1],
        "bar": bar.iloc[-1],
        "bar_prev": bar.iloc[-2] if len(bar) >= 2 else 0,
        "trend": "偏多" if bar.iloc[-1] > bar.iloc[-2] else "偏空",
    }


def calc_rsi(df: pd.DataFrame, period: int = 14) -> float:
    """计算RSI"""
    close = df["收盘"] if "收盘" in df.columns else df["close"]
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    avg_g = gain.rolling(period).mean()
    avg_l = loss.rolling(period).mean().replace(0, 0.001)
    rsi = 100 - 100 / (1 + avg_g / avg_l)
    return float(rsi.iloc[-1])


def calc_volume_ratio(df: pd.DataFrame) -> float:
    """量比 = 当日量 / MA20均量"""
    vol = df["成交量"] if "成交量" in df.columns else df["volume"]
    vol_ma20 = vol.rolling(20).mean().iloc[-1]
    return float(vol.iloc[-1] / vol_ma20) if vol_ma20 > 0 else 0


def get_support_resistance(df: pd.DataFrame) -> tuple:
    """计算压力支撑位"""
    low = df["最低"] if "最低" in df.columns else df["low"]
    high = df["最高"] if "最高" in df.columns else df["high"]
    close = df["收盘"] if "收盘" in df.columns else df["close"]
    cur = close.iloc[-1]
    support = min(low.tail(5).min(), cur * 0.985)
    resistance = max(high.tail(5).max(), close.rolling(20).mean().iloc[-1])
    return float(support), float(resistance)


def ma_status(cur: float, ma5: float, ma10: float, ma20: float) -> str:
    """判断均线状态"""
    if cur > ma5 > ma10 > ma20:
        return "多头排列"
    elif cur < ma5 < ma10 < ma20:
        return "空头排列"
    return "纠缠整理"


def analyze_stock(df: pd.DataFrame) -> dict:
    """对一只股票做完整技术分析"""
    if df.empty:
        return {}
    close = df["收盘"] if "收盘" in df.columns else df["close"]
    cur = float(close.iloc[-1])
    mas = calc_mas(df)
    macd = calc_macd(df)
    rsi = calc_rsi(df)
    vol_ratio = calc_volume_ratio(df)
    support, resistance = get_support_resistance(df)
    ma_stat = ma_status(cur, mas["ma5"], mas["ma10"], mas["ma20"])

    # 信号收集
    bull_signals = []
    bear_signals = []
    if cur > mas["ma5"]:
        bull_signals.append("站上MA5")
    if cur > mas["ma10"]:
        bull_signals.append("站上MA10")
    if cur > mas["ma20"]:
        bull_signals.append("突破MA20")
    if macd["trend"] == "偏多":
        bull_signals.append("MACD动量向上")
    if vol_ratio > 1.2:
        bull_signals.append("放量")
    if rsi > 50:
        bull_signals.append("RSI强势")
    if cur < mas["ma5"]:
        bear_signals.append("在MA5下")
    if cur < mas["ma20"]:
        bear_signals.append("在MA20下")
    if vol_ratio < 0.6:
        bear_signals.append("缩量")
    if rsi < 40:
        bear_signals.append("RSI偏弱")

    # 综合判断
    if len(bull_signals) >= 2:
        bias = "偏多"
    elif len(bear_signals) >= 2:
        bias = "偏空"
    else:
        bias = "中性"

    return {
        "price": cur,
        "mas": mas,
        "macd": macd,
        "rsi": rsi,
        "vol_ratio": vol_ratio,
        "support": support,
        "resistance": resistance,
        "ma_status": ma_stat,
        "bias": bias,
        "bull_signals": bull_signals,
        "bear_signals": bear_signals,
    }
