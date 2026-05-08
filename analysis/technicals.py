"""技术指标计算 — 均线 / MACD / RSI / KDJ / BOLL / 量价 / 综合评分"""
import pandas as pd
import numpy as np


def calc_mas(df: pd.DataFrame) -> dict:
    """计算均线"""
    close = df["收盘"] if "收盘" in df.columns else df["close"]
    return {
        "ma5": close.rolling(5).mean().iloc[-1],
        "ma10": close.rolling(10).mean().iloc[-1],
        "ma20": close.rolling(20).mean().iloc[-1],
        "ma60": close.rolling(60).mean().iloc[-1] if len(close) >= 60 else None,
    }


def calc_macd(df: pd.DataFrame) -> dict:
    """计算MACD"""
    close = df["收盘"] if "收盘" in df.columns else df["close"]
    exp12 = close.ewm(span=12).mean()
    exp26 = close.ewm(span=26).mean()
    dif = exp12 - exp26
    dea = dif.ewm(span=9).mean()
    bar = 2 * (dif - dea)
    return {
        "dif": float(dif.iloc[-1]),
        "dea": float(dea.iloc[-1]),
        "bar": float(bar.iloc[-1]),
        "bar_prev": float(bar.iloc[-2]) if len(bar) >= 2 else 0,
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


def calc_kdj(df: pd.DataFrame) -> dict:
    """计算KDJ随机指标"""
    low = df["最低"] if "最低" in df.columns else df["low"]
    high = df["最高"] if "最高" in df.columns else df["high"]
    close = df["收盘"] if "收盘" in df.columns else df["close"]

    low9 = low.rolling(9).min()
    high9 = high.rolling(9).max()
    rsv = (close - low9) / (high9 - low9 + 1e-10) * 100

    k = rsv.ewm(com=2).mean()
    d = k.ewm(com=2).mean()
    j = 3 * k - 2 * d

    k_val, d_val, j_val = float(k.iloc[-1]), float(d.iloc[-1]), float(j.iloc[-1])
    return {
        "k": round(k_val, 1),
        "d": round(d_val, 1),
        "j": round(j_val, 1),
        "cross": "金叉" if k_val > d_val and k.iloc[-2] <= d.iloc[-2] else
                  "死叉" if k_val < d_val and k.iloc[-2] >= d.iloc[-2] else "无",
        "status": "超买" if j_val > 100 else "超卖" if j_val < 0 else "正常",
    }


def calc_boll(df: pd.DataFrame) -> dict:
    """计算布林带"""
    close = df["收盘"] if "收盘" in df.columns else df["close"]
    mid = close.rolling(20).mean()
    std = close.rolling(20).std()
    upper = mid + 2 * std
    lower = mid - 2 * std

    cur = float(close.iloc[-1])
    u, m, l = float(upper.iloc[-1]), float(mid.iloc[-1]), float(lower.iloc[-1])
    position = (cur - l) / (u - l) * 100 if u > l else 50

    return {
        "upper": round(u, 2),
        "mid": round(m, 2),
        "lower": round(l, 2),
        "position": round(position, 1),
        "status": "上轨之上" if cur > u else "下轨之下" if cur < l else "区间内",
    }


def calc_volume_analysis(df: pd.DataFrame) -> dict:
    """成交量分析"""
    vol = df["成交量"] if "成交量" in df.columns else df["volume"]
    cur_vol = float(vol.iloc[-1])
    vol_ma5 = float(vol.rolling(5).mean().iloc[-1])
    vol_ma10 = float(vol.rolling(10).mean().iloc[-1])
    ratio = cur_vol / vol_ma5 if vol_ma5 > 0 else 0

    return {
        "vol": cur_vol,
        "vol_ma5": vol_ma5,
        "vol_ma10": vol_ma10,
        "ratio": round(ratio, 2),
        "status": "放量" if ratio > 1.3 else "缩量" if ratio < 0.7 else "正常",
    }


def ma_status(cur: float, ma5: float, ma10: float, ma20: float) -> str:
    """判断均线状态"""
    if cur > ma5 > ma10 > ma20:
        return "多头排列"
    elif cur < ma5 < ma10 < ma20:
        return "空头排列"
    return "纠缠整理"


def calc_score(bull: list, bear: list, rsi: float, kdj_status: str, ma_stat: str, boll_pos: float) -> dict:
    """综合评分 -5 ~ +5"""
    score = 0
    score += len(bull)  # 每个多头信号 +1
    score -= len(bear)  # 每个空头信号 -1

    if rsi > 60:
        score += 1
    elif rsi < 40:
        score -= 1

    if kdj_status == "超买":
        score -= 1
    elif kdj_status == "超卖":
        score += 1

    if "多头" in ma_stat:
        score += 1
    elif "空头" in ma_stat:
        score -= 1

    if boll_pos > 90:
        score -= 1  # 上轨附近，回调风险
    elif boll_pos < 10:
        score += 1  # 下轨附近，反弹机会

    score = max(-5, min(5, score))

    level = "强势" if score >= 3 else "偏多" if score >= 1 else \
            "偏空" if score <= -1 else "弱势" if score <= -3 else "中性"
    return {"score": score, "level": level}


def analyze_stock(df: pd.DataFrame) -> dict:
    """对一只股票做完整技术分析"""
    if df.empty:
        return {}
    close = df["收盘"] if "收盘" in df.columns else df["close"]
    cur = float(close.iloc[-1])

    mas = calc_mas(df)
    macd = calc_macd(df)
    rsi = calc_rsi(df)
    kdj = calc_kdj(df)
    boll = calc_boll(df)
    vol = calc_volume_analysis(df)
    ma_stat = ma_status(cur, mas["ma5"], mas["ma10"], mas["ma20"])

    # 信号收集
    bull_signals = []
    bear_signals = []

    # 均线信号
    if cur > mas["ma5"]:
        bull_signals.append("站上MA5")
    if cur > mas["ma10"]:
        bull_signals.append("站上MA10")
    if cur > mas["ma20"]:
        bull_signals.append("突破MA20")
    if cur < mas["ma5"]:
        bear_signals.append("在MA5下")
    if cur < mas["ma20"]:
        bear_signals.append("在MA20下")

    # MACD
    if macd["trend"] == "偏多":
        bull_signals.append("MACD向上")
    else:
        bear_signals.append("MACD向下")

    # KDJ
    if kdj["cross"] == "金叉":
        bull_signals.append("KDJ金叉")
    elif kdj["cross"] == "死叉":
        bear_signals.append("KDJ死叉")

    # BOLL
    if boll["status"] == "上轨之上":
        bear_signals.append("触及上轨")
    elif boll["status"] == "下轨之下":
        bull_signals.append("触及下轨")

    # 成交量
    if vol["status"] == "放量":
        bull_signals.append("放量")
    elif vol["status"] == "缩量":
        bear_signals.append("缩量")

    # RSI
    if rsi > 60:
        bull_signals.append(f"RSI{round(rsi)}强势")
    elif rsi < 40:
        bear_signals.append(f"RSI{round(rsi)}偏弱")

    # 综合评分
    score_info = calc_score(bull_signals, bear_signals, rsi, kdj["status"], ma_stat, boll["position"])

    return {
        "price": cur,
        "mas": {k: round(v, 2) if v else None for k, v in mas.items()},
        "macd": macd,
        "rsi": round(rsi, 1),
        "kdj": kdj,
        "boll": boll,
        "vol": vol,
        "ma_status": ma_stat,
        "bias": score_info["level"],
        "score": score_info["score"],
        "bull_signals": bull_signals,
        "bear_signals": bear_signals,
    }
