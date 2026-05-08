"""持仓多维总结 — 持仓分析、今日关注、明日预测/尾盘建议"""
from datetime import datetime, time as dtime


def is_market_open() -> bool:
    """判断当前是否在交易时段（周一至周五 9:30-15:00）"""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    open_time = dtime(9, 30)
    close_time = dtime(15, 0)
    return open_time <= now.time() <= close_time


def _holding_status(pnl_pct: float) -> str:
    """根据盈亏比例判断持仓状态"""
    if pnl_pct <= -15:
        return "深度套牢"
    elif pnl_pct <= -5:
        return "明显套牢"
    elif pnl_pct < 0:
        return "浅套"
    elif pnl_pct < 5:
        return "微利"
    elif pnl_pct < 15:
        return "盈利良好"
    return "大幅盈利"


def _position_assessment(shares: int, price: float, market_value: float) -> str:
    """仓位评估"""
    if shares <= 100:
        return "轻仓试探"
    elif shares <= 500:
        return "仓位适中"
    elif shares <= 2000:
        return "仓位较重"
    return "重仓持有"


def _intraday_strength(change_pct: float, high: float, low: float, price: float) -> str:
    """日内走势评价"""
    # 日内振幅
    amplitude = (high - low) / low * 100 if low > 0 else 0
    # 日内位置 (收盘/现价在高低点的位置)
    position = (price - low) / (high - low) * 100 if high > low else 50

    parts = []
    if change_pct > 2:
        parts.append("强势上涨")
    elif change_pct > 0.5:
        parts.append("震荡上行")
    elif change_pct > 0:
        parts.append("窄幅收红")
    elif change_pct > -0.5:
        parts.append("窄幅收跌")
    elif change_pct > -2:
        parts.append("明显走弱")
    else:
        parts.append("大幅下跌")

    if amplitude > 3:
        parts.append("，日内波动较大")
    elif amplitude > 1.5:
        parts.append("，日内有一定波动")
    else:
        parts.append("，日内窄幅震荡")

    if position > 80:
        parts.append("，价格处于日内高位")
    elif position < 20:
        parts.append("，价格处于日内低位")

    return "".join(parts)


def _tech_summary(ta: dict) -> str:
    """技术面一句话总结"""
    if not ta:
        return "暂无技术数据"
    parts = []
    ma = ta.get("ma_status", "")
    macd = ta.get("macd", {}).get("trend", "")
    score = ta.get("score", 0)
    signals = ta.get("bull_signals", []) + ta.get("bear_signals", [])

    if ma:
        parts.append(f"均线{ma}")
    if macd:
        parts.append(f"MACD{macd}")
    if signals:
        parts.append(f"信号: {' '.join(signals[:3])}")
    parts.append(f"综合评分{score}")

    return " | ".join(parts)


def _forward_advice(ta: dict, price: float, pnl_pct: float, is_open: bool) -> str:
    """给出方向建议（盘中→尾盘建议，盘后→明日预测）"""
    if not ta:
        return "数据不足，无法给出建议"

    support = ta.get("support", price * 0.98)
    resistance = ta.get("resistance", price * 1.02)
    score = ta.get("score", 0)
    mas = ta.get("mas", {})
    ma5 = mas.get("ma5", price)
    ma20 = mas.get("ma20", price)

    if is_open:
        # 盘中 — 尾盘方向建议
        parts = []
        if score >= 2:
            parts.append("技术面偏多")
            if price > ma5:
                parts.append(f"站稳MA5({ma5:.1f})，尾盘可持有")
            else:
                parts.append(f"关注MA5({ma5:.1f})能否收回")
        elif score <= -2:
            parts.append("技术面偏空")
            parts.append(f"若跌破{support:.1f}考虑减仓")
        else:
            parts.append("方向不明，观望为主")

        if pnl_pct < -5:
            parts.append(f"，已亏损{pnl_pct:.1f}%，不建议盲目加仓")
        elif pnl_pct > 5:
            parts.append(f"，已有盈利{pnl_pct:.1f}%，注意锁定利润")

        parts.append(f"，压力{resistance:.1f}")
        return "尾盘建议: " + "。".join(parts)

    # 盘后 — 明日预测
    parts = []
    if score >= 2:
        parts.append("技术面偏多")
        if price > ma5:
            parts.append(f"明日有望延续反弹")
        else:
            parts.append(f"明日需先站回MA5({ma5:.1f})")
        parts.append(f", 压力位{resistance:.1f}")
    elif score <= -2:
        parts.append("技术面偏弱")
        parts.append(f"明日关注{support:.1f}支撑")
        parts.append(f", 反弹压力{resistance:.1f}")
    else:
        parts.append("方向中性")
        parts.append(f"明日预计在{support:.1f}~{resistance:.1f}区间震荡")
        parts.append(", 等待方向选择")

    if pnl_pct < -5:
        parts.append(f"。已亏损{pnl_pct:.1f}%，不宜恐慌减仓，等待反弹")

    return "明日预测: " + "。".join(parts)


def generate_insight(h: dict, ta: dict) -> dict:
    """对一只持仓生成完整的多维总结"""
    price = h.get("price", 0)
    cost = h.get("cost", 0)
    shares = h.get("shares", 0)
    change_pct = h.get("change_pct", 0)
    high = h.get("high", price)
    low = h.get("low", price)
    market_value = price * shares
    cost_total = cost * shares
    pnl_val = market_value - cost_total
    pnl_pct = (price / cost - 1) * 100 if cost > 0 else 0
    market_open = is_market_open()

    status = _holding_status(pnl_pct)
    position = _position_assessment(shares, price, market_value)
    intraday = _intraday_strength(change_pct, high, low, price)
    tech_summary = _tech_summary(ta)
    forward = _forward_advice(ta, price, pnl_pct, market_open)

    # 今日关键观察点
    key_points = []
    if ta:
        ma5 = ta.get("mas", {}).get("ma5", 0)
        ma20 = ta.get("mas", {}).get("ma20", 0)
        if price < ma5:
            key_points.append(f"价格在MA5({ma5:.1f})之下")
        if price < ma20:
            key_points.append(f"未站上MA20({ma20:.1f})，中期趋势偏弱")
        if change_pct > 2:
            key_points.append("今日涨幅较大，关注明日持续性")
        elif change_pct < -2:
            key_points.append("今日跌幅较大，注意风险控制")

    if pnl_pct < -5:
        key_points.append(f"浮亏{pnl_pct:.1f}%，注意持仓风险")
    elif pnl_pct > 5:
        key_points.append(f"已盈利{pnl_pct:.1f}%，考虑分批止盈")

    if not key_points:
        key_points.append("今日走势平稳，无明显异常信号")

    return {
        "code": h.get("code", ""),
        "name": h.get("name", ""),
        "status": status,
        "position": position,
        "intraday_analysis": intraday,
        "tech_summary": tech_summary,
        "key_points": key_points,
        "forward_advice": forward,
        "is_market_open": market_open,
        "pnl_pct": round(pnl_pct, 2),
        "pnl_value": round(pnl_val, 2),
    }
