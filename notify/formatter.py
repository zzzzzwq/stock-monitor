"""各时间点消息格式化"""
from datetime import datetime


WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _now_str() -> str:
    now = datetime.now()
    wd = WEEKDAY_NAMES[now.weekday()]
    return f"{now.strftime('%Y-%m-%d')} {wd}"


def _price_line(name: str, price: float, change_pct: float) -> str:
    return f"{name}: {price:.2f}  {change_pct:+.2f}%"


def _pnl_line(pnl: dict) -> str:
    return (f"  持仓{pnl['shares']}股 均价{pnl['cost']} "
            f"市值{pnl['market_value']:.0f} "
            f"浮亏{pnl['pnl']:.0f}({pnl['pnl_pct']:+.2f}%) "
            f"解套需涨+{pnl['unwind_pct']:.1f}%")


def _tech_line(ta: dict) -> str:
    if not ta:
        return "  技术分析: 数据不足"
    return (f"  MA5:{ta['mas']['ma5']:.1f} MA10:{ta['mas']['ma10']:.1f} MA20:{ta['mas']['ma20']:.1f}\n"
            f"  均线:{ta['ma_status']} MACD:{ta['macd']['trend']} RSI:{ta['rsi']:.1f}\n"
            f"  支撑{ta['support']:.1f} | 压力{ta['resistance']:.1f}")


def format_0830(indices: dict, holdings_pnl: list, tech_data: dict) -> tuple:
    """盘前 08:30 — 隔夜消息、大盘回顾、技术面、今日关注"""
    lines = [f"[盘前分析] {_now_str()}", "━━━━━━━━━━━━━━━━━━"]

    lines.append("【大盘回顾】")
    for name, d in indices.items():
        lines.append(f"  {_price_line(name, d['price'], d['change_pct'])}")

    lines.append("\n【持仓概览】")
    for pnl in holdings_pnl:
        lines.append(f"\n{pnl['name']}({pnl['code']}) {pnl['price']:.2f}")
        lines.append(_pnl_line(pnl))
        ta = tech_data.get(pnl["code"], {})
        lines.append(_tech_line(ta))

    lines.append(f"\n{'='*40}\n仅供参考，不构成投资建议")
    return "📊 盘前分析", "\n".join(lines)


def format_0925(open_data: dict, holdings_data: dict) -> tuple:
    """竞价 09:25 — 集合竞价结果"""
    lines = [f"[竞价分析] 09:25", "━━━━━━━━━━━━━━━━━━"]

    lines.append("【集合竞价】")
    for name, d in open_data.items():
        lines.append(f"  {_price_line(name, d.get('price', 0), d.get('change_pct', 0))}")

    lines.append("\n【持仓竞价】")
    for code, d in holdings_data.items():
        p = d.get("price", 0)
        op = d.get("open", p)
        chg = (p / d.get("prev_close", p) - 1) * 100 if d.get("prev_close") else 0
        lines.append(f"\n{d['name']}({code}): {p:.2f} 竞价量{d.get('volume', 0)/10000:.1f}万手")
        direction = "高开" if chg > 0.2 else ("低开" if chg < -0.2 else "平开")
        lines.append(f"  {direction} {chg:+.2f}%")

    return "🔔 竞价分析", "\n".join(lines)


def format_0935(indices: dict, holdings_data: dict) -> tuple:
    """开盘5分 09:35"""
    lines = [f"[开盘5分钟] 09:35", "━━━━━━━━━━━━━━━━━━"]
    lines.append("【大盘】")
    for name, d in indices.items():
        lines.append(f"  {_price_line(name, d.get('price', 0), d.get('change_pct', 0))}")

    lines.append("\n【持仓开盘】")
    for code, d in holdings_data.items():
        p = d.get("price", 0)
        op = d.get("open", p)
        intra = (p / op - 1) * 100 if op else 0
        lines.append(f"\n{d['name']}({code}): {p:.2f} 日内{intra:+.2f}%")
        if intra > 1:
            lines.append("  开盘走强 ✓")
        elif intra < -1:
            lines.append("  开盘走弱 ⚠")
        else:
            lines.append("  开盘整理 →")
    return "📈 开盘分析", "\n".join(lines)


def format_1130(indices: dict, holdings_data: dict, boards: dict, tech_data: dict) -> tuple:
    """午盘 11:30"""
    n = datetime.now()
    lines = [f"[午盘复盘] {n.strftime('%Y-%m-%d %H:%M')}", "━━━━━━━━━━━━━━━━━━"]

    lines.append("【大盘】")
    for name, d in indices.items():
        lines.append(f"  {_price_line(name, d.get('price', 0), d.get('change_pct', 0))}")

    lines.append("\n【持仓上午】")
    for code, d in holdings_data.items():
        p = d.get("price", 0)
        chg = d.get("change_pct", 0)
        op = d.get("open", p)
        intra = (p / op - 1) * 100 if op else 0
        lines.append(f"\n{d['name']}({code}): {p:.2f}  {chg:+.2f}% 日内{intra:+.2f}%")
        lines.append(f"  开{op:.2f} 高{d.get('high', 0):.2f} 低{d.get('low', 0):.2f}")
        ta = tech_data.get(code, {})
        if ta:
            lines.append(f"  {ta.get('bias', '')} | 信号: {', '.join(ta.get('bull_signals', []) + ta.get('bear_signals', []))}")

    lines.append("\n【板块】")
    for name, chg in boards.items():
        if chg is not None:
            lines.append(f"  {name}: {chg:+.2f}%")

    return "🏛 午盘复盘", "\n".join(lines)


def format_1305(indices: dict, holdings_data: dict) -> tuple:
    """下午开盘 13:05"""
    lines = [f"[下午开盘] 13:05", "━━━━━━━━━━━━━━━━━━"]
    lines.append("【大盘】")
    for name, d in indices.items():
        lines.append(f"  {_price_line(name, d.get('price', 0), d.get('change_pct', 0))}")

    lines.append("\n【持仓下午开盘】")
    for code, d in holdings_data.items():
        p = d.get("price", 0)
        chg = d.get("change_pct", 0)
        lines.append(f"\n{d['name']}({code}): {p:.2f}  {chg:+.2f}%")

    return "📉 下午开盘", "\n".join(lines)


def format_1500(indices: dict, holdings_pnl: list, boards: dict, tech_data: dict) -> tuple:
    """收盘 15:00"""
    n = datetime.now()
    lines = [f"[收盘总结] {n.strftime('%Y-%m-%d %H:%M')}", "━━━━━━━━━━━━━━━━━━"]

    lines.append("【大盘收盘】")
    for name, d in indices.items():
        lines.append(f"  {_price_line(name, d['price'], d['change_pct'])}"
                     f" 高{d['high']:.2f} 低{d['low']:.2f}")

    lines.append("\n【持仓】")
    for pnl in holdings_pnl:
        lines.append(f"\n{pnl['name']}({pnl['code']}) 收盘{pnl['price']:.2f}")
        lines.append(_pnl_line(pnl))
        ta = tech_data.get(pnl["code"], {})
        if ta:
            lines.append(f"  {ta.get('bias', '')} | "
                         f"支撑{ta['support']:.0f} 压力{ta['resistance']:.0f}")

    lines.append("\n【板块】")
    for name, chg in boards.items():
        if chg is not None:
            lines.append(f"  {name}: {chg:+.2f}%")

    return "📊 收盘总结", "\n".join(lines)


def format_2000(news_data: dict) -> tuple:
    """晚间 20:00 — 盘后消息"""
    lines = [f"[晚间消息] {_now_str()}", "━━━━━━━━━━━━━━━━━━"]
    lines.append("【盘后公告/新闻】")
    for code, news_list in news_data.items():
        if news_list:
            lines.append(f"\n{code}:")
            for item in news_list[:5]:
                lines.append(f"  · {item['title'][:40]}")
        else:
            lines.append(f"\n{code}: 暂无最新消息")

    return "🌙 晚间消息", "\n".join(lines)


def format_2200(next_day_preview: dict) -> tuple:
    """晚间 22:00 — 明日预览"""
    lines = [f"[明日预览] 明日{next_day_preview.get('next_date', '')}", "━━━━━━━━━━━━━━━━━━"]

    lines.append("【隔夜外盘参考】")
    lines.append("  (需等美股收盘后更新)")

    lines.append("\n【明日关键位】")
    for code, ta in next_day_preview.get("tech_data", {}).items():
        if ta:
            name = next_day_preview.get("names", {}).get(code, code)
            lines.append(f"\n{name}({code}):")
            lines.append(f"  支撑{ta['support']:.0f} / {ta['price']*0.98:.0f}(-2%)")
            lines.append(f"  压力{ta['resistance']:.0f} / {ta['price']*1.02:.0f}(+2%)")

    lines.append("\n【明日策略】")
    for code, suggestion in next_day_preview.get("suggestions", {}).items():
        lines.append(f"  {suggestion}")

    return "🌙 明日预览", "\n".join(lines)
