"""个股搜索 + 综合诊断 API"""
import logging

from flask import request, jsonify
from api import api_bp
from auth.decorators import require_auth

from data.stock_list import search_stocks
from data.sina import get_holdings_quotes
from data.akshare_data import (
    get_history,
    get_related_board_changes,
    get_stock_boards,
    get_market_sentiment,
)
from data.stock_list import get_stock_list
from analysis.technicals import analyze_stock

logger = logging.getLogger(__name__)


def _infer_market(code: str) -> str:
    if code.startswith(("6", "9")):
        return "sh"
    if code.startswith(("0", "3", "2")):
        return "sz"
    if code.startswith(("4", "8")):
        return "bj"
    return "sz"


def _find_stock_meta(code: str) -> dict:
    stock = next((s for s in get_stock_list() if s["code"] == code), None)
    market = stock["market"] if stock else _infer_market(code)
    name = stock["name"] if stock else code
    return {"name": name, "market": market}


@api_bp.route("/stock/info", methods=["GET"])
def stock_info():
    """获取个股完整信息（代码+名称+市场+板块），用于添加持仓自动填充"""
    code = request.args.get("code", "").strip()
    if not code:
        return jsonify({"error": "缺少code参数"}), 400

    stocks = get_stock_list()
    stock = None
    for s in stocks:
        if s["code"] == code:
            stock = dict(s)
            break
    if not stock:
        return jsonify({"error": f"未找到代码 {code}"}), 404

    stock["boards"] = get_stock_boards(code)
    return jsonify(stock)


@api_bp.route("/stock/search", methods=["GET"])
def stock_search():
    """搜索股票（支持模糊匹配，输入1显示所有1开头的股票）"""
    q = request.args.get("q", "").strip()
    if not q or len(q) < 1:
        return jsonify([])
    results = search_stocks(q, limit=20)
    return jsonify(results)


@api_bp.route("/stock/diagnose/<code>", methods=["GET"])
@require_auth
def stock_diagnose(code: str):
    """个股综合诊断 — 100分制评分"""
    meta = _find_stock_meta(code)
    market = meta["market"]
    live = get_holdings_quotes([{"code": code, "market": market}])
    key = f"{market}{code}"
    ld = live.get(key, {})
    price = ld.get("price", 0)
    prev = ld.get("prev_close", 1) or 1
    change_pct = round((price - prev) / prev * 100, 2) if prev else 0
    boards = get_stock_boards(code)
    board_changes = get_related_board_changes(boards)
    sentiment = get_market_sentiment()

    # 获取历史数据（失败时不阻断，降级）
    ta = {}
    df = get_history(code)
    if not df.empty:
        ta = analyze_stock(df)

    # 实时行情取不到时的处理
    if price == 0 and not ta:
        return jsonify({
            "code": code,
            "name": meta["name"],
            "market": market,
            "price": 0,
            "change_pct": 0,
            "score": 0,
            "max_score": 100,
            "level": "无数据",
            "detail": {
                "technology": {"score": 0, "max": 30, "items": ["暂无数据"]},
                "volume_price": {"score": 0, "max": 15, "items": ["暂无数据"]},
                "market": {"score": 0, "max": 20, "items": ["暂无数据"]},
                "trend": {"score": 0, "max": 15, "items": ["暂无数据"]},
                "volatility": {"score": 0, "max": 10, "items": ["暂无数据"]},
                "boards": {"score": 0, "max": 10, "items": ["暂无数据"]},
            },
            "signals": {"bull": [], "bear": []},
            "related_boards": boards,
            "board_changes": [],
            "note": "行情数据暂时无法获取，请稍后再试"
        })

    # ===== 多维度评分（满分100） =====

    # 1. 技术面 (30分) - 有数据才评分
    tech_score = 10
    tech_items = ["数据不足"]

    if ta:
        tech_score = 15
        if ta.get("ma_status") == "多头排列":
            tech_score = 28
        elif ta.get("ma_status") == "空头排列":
            tech_score = 8
        else:
            tech_score = 15
        if ta.get("macd", {}).get("trend") == "偏多":
            tech_score += 3
        else:
            tech_score -= 2
        kdj = ta.get("kdj", {})
        if kdj.get("cross") == "金叉":
            tech_score += 3
        elif kdj.get("cross") == "死叉":
            tech_score -= 2
        rsi = ta.get("rsi", 50)
        if rsi > 60:
            tech_score += 2
        elif rsi < 40:
            tech_score -= 2
        tech_score = max(0, min(30, tech_score))
        tech_items = [
            ta.get("ma_status", ""),
            f"MACD{ta.get('macd',{}).get('trend','')}",
            f"RSI{rsi:.0f}",
            f"KDJ{ta.get('kdj',{}).get('cross','无')}"
        ]

    # 2. 量价配合 (15分)
    vol_score = 8
    vol_items = ["数据不足"]
    if ta:
        vol = ta.get("vol", {})
        vol_score = 8
        if vol.get("status") == "放量":
            vol_score += 4
        elif vol.get("status") == "缩量":
            vol_score -= 3
        boll = ta.get("boll", {})
        pos = boll.get("position", 50)
        if 30 <= pos <= 70:
            vol_score += 3
        elif pos < 20:
            vol_score += 2
        vol_score = max(0, min(15, vol_score))
        vol_items = [f"量比{vol.get('ratio','--')}", f"布林{pos:.0f}%"]

    # 3. 市场环境 (20分)
    fund_flow = sentiment.get("fund_flow") or {}
    market_score = 10
    market_items = ["市场情绪中性"]
    main_net = fund_flow.get("main_net", 0)
    if main_net > 80:
        market_score = 18
        market_items = [f"主力净流入{main_net}亿", "市场风险偏好较强"]
    elif main_net > 20:
        market_score = 15
        market_items = [f"主力净流入{main_net}亿", "市场环境偏暖"]
    elif main_net < -80:
        market_score = 4
        market_items = [f"主力净流出{abs(main_net)}亿", "整体资金面承压"]
    elif main_net < -20:
        market_score = 7
        market_items = [f"主力净流出{abs(main_net)}亿", "短线资金偏谨慎"]

    # 4. 趋势结构 (15分)
    trend_score = 8
    trend_items = ["趋势等待进一步确认"]
    if ta:
        trend_score = 8
        mas = ta.get("mas", {})
        support = ta.get("support", price or 0)
        resistance = ta.get("resistance", price or 0)
        if ta.get("bias") in ("强势", "偏多"):
            trend_score += 4
        elif ta.get("bias") in ("弱势", "偏空"):
            trend_score -= 3
        if price and support and price > support:
            trend_score += 2
        if resistance and price and price >= resistance * 0.98:
            trend_items = [f"接近压力位{resistance:.2f}", "追高需谨慎"]
        else:
            trend_items = [f"支撑位{support:.2f}", f"压力位{resistance:.2f}"]
        ma20 = mas.get("ma20")
        if ma20 and price > ma20:
            trend_score += 1
        elif ma20 and price < ma20:
            trend_score -= 1
        trend_score = max(0, min(15, trend_score))

    # 5. 波动风险 (10分)
    volatility_score = 6
    volatility_items = ["波动水平正常"]
    if ta:
        boll = ta.get("boll", {})
        position = boll.get("position", 50)
        kdj = ta.get("kdj", {})
        if 25 <= position <= 75:
            volatility_score = 8
            volatility_items = [f"布林位置{position:.1f}%", "波动仍在可控区间"]
        elif position < 15 or position > 85:
            volatility_score = 4
            volatility_items = [f"布林位置{position:.1f}%", "已接近极端区间"]
        if kdj.get("status") == "超买":
            volatility_score -= 1
            volatility_items.append("短线偏超买")
        elif kdj.get("status") == "超卖":
            volatility_score += 1
            volatility_items.append("短线偏超卖")
        volatility_score = max(0, min(10, volatility_score))

    # 6. 板块热度 (10分)
    board_score = 5
    board_items = ["暂无板块数据"]
    board_change_items = []
    valid_board_changes = [(name, chg) for name, chg in board_changes.items() if chg is not None]
    if valid_board_changes:
        avg_board_chg = sum(chg for _, chg in valid_board_changes) / len(valid_board_changes)
        board_change_items = [f"{name}{chg:+.2f}%" for name, chg in valid_board_changes[:3]]
        if avg_board_chg > 2:
            board_score = 9
            board_items = ["所属板块整体强势"] + board_change_items
        elif avg_board_chg > 0.5:
            board_score = 7
            board_items = ["所属板块偏强"] + board_change_items
        elif avg_board_chg < -2:
            board_score = 2
            board_items = ["所属板块整体走弱"] + board_change_items
        elif avg_board_chg < -0.5:
            board_score = 4
            board_items = ["所属板块偏弱"] + board_change_items
        else:
            board_score = 5
            board_items = ["所属板块分化"] + board_change_items

    total_score = tech_score + vol_score + market_score + trend_score + volatility_score + board_score
    if total_score >= 85:
        level = "优秀"
    elif total_score >= 70:
        level = "良好"
    elif total_score >= 55:
        level = "一般"
    elif total_score >= 40:
        level = "较差"
    else:
        level = "危险"

    result = {
        "code": code,
        "name": meta["name"],
        "market": market,
        "price": price,
        "change_pct": change_pct,
        "score": total_score,
        "max_score": 100,
        "level": level,
        "quote": {
            "open": ld.get("open", 0),
            "high": ld.get("high", 0),
            "low": ld.get("low", 0),
            "prev_close": prev,
            "volume": ld.get("volume", 0),
        },
        "detail": {
            "technology": {"score": tech_score, "max": 30, "items": tech_items},
            "volume_price": {"score": vol_score, "max": 15, "items": vol_items},
            "market": {"score": market_score, "max": 20, "items": market_items},
            "trend": {"score": trend_score, "max": 15, "items": trend_items},
            "volatility": {"score": volatility_score, "max": 10, "items": volatility_items},
            "boards": {"score": board_score, "max": 10, "items": board_items},
        },
        "signals": {
            "bull": ta.get("bull_signals", []) if ta else [],
            "bear": ta.get("bear_signals", []) if ta else [],
        },
        "technicals": ta,
        "related_boards": boards,
        "board_changes": [
            {"name": name, "change_pct": chg}
            for name, chg in valid_board_changes
        ],
    }

    if not ta:
        result["note"] = "技术面数据暂缺，评分为实时行情估算"

    return jsonify(result)
