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


def _build_summary(indices: dict, holdings_data: list, pnl_list: list, boards: dict = None) -> str:
    """根据数据生成总结文本"""
    parts = []

    # 大盘判断
    weak_indices = [n for n, d in indices.items() if d.get("change_pct", 0) < -0.5]
    strong_indices = [n for n, d in indices.items() if d.get("change_pct", 0) > 0.5]

    if weak_indices and not strong_indices:
        parts.append(f"今天大盘整体偏弱，{'、'.join(weak_indices)}下跌，市场情绪不佳。")
    elif strong_indices and not weak_indices:
        parts.append(f"今天市场表现较好，{'、'.join(strong_indices)}上涨。")
    elif strong_indices and weak_indices:
        parts.append(f"今天市场分化，{'、'.join(strong_indices)}上涨但{'、'.join(weak_indices)}走弱。")
    else:
        parts.append("今天大盘窄幅震荡，各指数变动不大。")

    # 持仓判断
    up_stocks = []
    down_stocks = []
    deep_down = []
    for h in holdings_data:
        chg = h.get("change_pct", 0)
        name = h.get("name", "")
        if chg > 0.2:
            up_stocks.append(name)
        elif chg < -0.5:
            down_stocks.append(name)
        if chg < -2:
            deep_down.append(name)

    if up_stocks:
        parts.append(f"{'、'.join(up_stocks)}勉强翻红但力度有限，" if len(up_stocks) < len(holdings_data) else f"{'、'.join(up_stocks)}表现较好。")
    if down_stocks:
        parts.append(f"{'、'.join(down_stocks)}持续走弱，")

    # 盈亏情况
    total_pnl = sum(p.get("pnl", 0) for p in pnl_list)
    if total_pnl < 0:
        parts.append(f"两个持仓都处于浮亏状态，合计亏损{abs(total_pnl):.0f}元。")
    else:
        parts.append(f"目前持仓整体盈利{total_pnl:.0f}元。")

    return "".join(parts)


def format_market_report(indices: dict, holdings_data: list, pnl_list: list,
                         boards: dict = None, tech_data: dict = None, fund_flow: dict = None) -> str:
    """生成完整的市场分析报告 — 大盘→持仓→总结"""
    now = datetime.now()
    wd = WEEKDAY_NAMES[now.weekday()]
    date_str = now.strftime("%Y-%m-%d")
    lines = [f"盘前分析 {date_str} {wd}", "━━━━━━━━━━━━━━━━━━"]

    # 大盘指数
    lines.append("\n【大盘指数】")
    lines.append(f"{'指数':<10}{'点位':>10}{'涨跌幅':>10}")
    for name, d in indices.items():
        chg = d.get("change_pct", 0)
        arrow = "↑" if chg > 0 else "↓"
        lines.append(f"{name:<10}{d.get('price', 0):>10.2f}{arrow}{chg:>+8.2f}%")

    # 持仓股
    lines.append("\n【持仓股】")
    total_pnl = 0
    for pnl in pnl_list:
        code = pnl.get("code", "")
        name = pnl.get("name", "")
        price = pnl.get("price", 0)
        chg = pnl.get("change_pct", 0)
        shares = pnl.get("shares", 0)
        cost = pnl.get("cost", 0)
        pnl_val = pnl.get("pnl", 0)
        pnl_pct = pnl.get("pnl_pct", 0)
        market_value = pnl.get("market_value", 0)
        high = pnl.get("high", price)
        low = pnl.get("low", price)
        total_pnl += pnl_val

        # 行情描述
        if chg > 0.5:
            trend_desc = f"上涨{chg:+.2f}%"
        elif chg > 0:
            trend_desc = f"微涨{chg:+.2f}%"
        elif chg > -0.5:
            trend_desc = f"微跌{chg:+.2f}%"
        else:
            trend_desc = f"跌{chg:+.2f}%"

        level_info = ""
        if price < 100 and pnl.get("prev_close", 0) >= 100:
            level_info = "，已跌破百元关口"
        elif price < 50 and pnl.get("prev_close", 0) >= 50:
            level_info = "，已跌破五十元关口"

        cost_info = f"浮亏{abs(pnl_val):.0f}(亏损{pnl_pct:+.2f}%)" if pnl_val < 0 else f"盈利{pnl_val:.0f}(盈利{pnl_pct:+.2f}%)"
        lines.append(f"\n{name}({code}) — 现价 {price:.2f}，今天{trend_desc}{level_info}，日内波幅 {low:.2f}~{high:.2f}")
        lines.append(f"  持仓{shares}股 均价{cost} 市值{market_value:.0f} {cost_info}")

        # 技术面简评
        ta = tech_data.get(code, {}) if tech_data else {}
        if ta:
            mas = ta.get("mas", {})
            macd_trend = ta.get("macd", {}).get("trend", "")
            rsi = ta.get("rsi", 0)
            score = ta.get("score", 0)
            signals = ta.get("bull_signals", []) + ta.get("bear_signals", [])
            lines.append(f"  技术: 均线{ta.get('ma_status','--')} MACD{macd_trend} RSI{rsi} 评分{score}")
            if signals:
                lines.append(f"  信号: {' '.join(signals[:5])}")

    # 总盈亏
    lines.append(f"\n总持仓盈亏：{total_pnl:+.0f} 元")

    # 板块
    if boards and any(v is not None for v in boards.values()):
        lines.append("\n【板块】")
        for name, chg in boards.items():
            if chg is not None:
                arrow = "↑" if chg > 0 else "↓"
                lines.append(f"  {name}: {arrow}{chg:+.2f}%")

    # 资金流向
    if fund_flow:
        main_net = fund_flow.get("main_net", 0)
        lines.append(f"\n【资金流向】")
        lines.append(f"  主力净流: {'+' if main_net >= 0 else ''}{main_net}亿")

    # 总结
    summary = _build_summary(indices, holdings_data, pnl_list, boards)
    lines.append(f"\n【总结】\n{summary}")

    lines.append(f"\n{'='*40}\n仅供参考，不构成投资建议")
    return "\n".join(lines)
