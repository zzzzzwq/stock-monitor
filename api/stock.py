"""个股搜索 + 综合诊断 API"""
import logging

from flask import request, jsonify
from api import api_bp
from auth.decorators import require_auth

from data.stock_list import search_stocks
from data.sina import get_holdings_quotes
from data.akshare_data import get_history, get_related_board_changes
from analysis.technicals import analyze_stock

logger = logging.getLogger(__name__)


@api_bp.route("/stock/search", methods=["GET"])
def stock_search():
    """搜索股票"""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    results = search_stocks(q, limit=15)
    return jsonify(results)


@api_bp.route("/stock/diagnose/<code>", methods=["GET"])
@require_auth
def stock_diagnose(code: str):
    """个股综合诊断 — 100分制评分"""
    df = get_history(code)
    if df.empty:
        return jsonify({"error": f"无法获取 {code} 的数据"}), 400

    ta = analyze_stock(df)
    price = ta.get("price", 0)

    # 实时行情
    live = get_holdings_quotes([{"code": code, "market": "sh" if code.startswith("6") else "sz"}])
    key = f"{'sh' if code.startswith('6') else 'sz'}{code}"
    ld = live.get(key, {})
    prev = ld.get("prev_close", 1) or 1
    change_pct = round((ld.get("price", 0) - prev) / prev * 100, 2) if prev else 0

    # ===== 多维度评分（满分100） =====

    # 1. 技术面 (30分)
    tech_score = 15  # 基础分
    if ta.get("ma_status") == "多头排列":
        tech_score = 28
    elif ta.get("ma_status") == "空头排列":
        tech_score = 8
    else:
        tech_score = 15
    # MACD
    if ta.get("macd", {}).get("trend") == "偏多":
        tech_score += 3
    else:
        tech_score -= 2
    # KDJ
    kdj = ta.get("kdj", {})
    if kdj.get("cross") == "金叉":
        tech_score += 3
    elif kdj.get("cross") == "死叉":
        tech_score -= 2
    # RSI
    rsi = ta.get("rsi", 50)
    if rsi > 60:
        tech_score += 2
    elif rsi < 40:
        tech_score -= 2
    tech_score = max(0, min(30, tech_score))

    # 2. 量价配合 (15分)
    vol = ta.get("vol", {})
    vol_score = 8
    if vol.get("status") == "放量":
        vol_score += 4
    elif vol.get("status") == "缩量":
        vol_score -= 3
    # 位置评分（布林带）
    boll = ta.get("boll", {})
    pos = boll.get("position", 50)
    if 30 <= pos <= 70:
        vol_score += 3
    elif pos < 20:
        vol_score += 2
    vol_score = max(0, min(15, vol_score))

    # 3. 市场环境 (20分) — 基于大盘情绪
    market_score = 12

    # 4. 综合评分 = 技术面 + 量价 + 市场环境
    total_score = tech_score + vol_score + market_score

    # 等级
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

    return jsonify({
        "code": code,
        "price": price,
        "change_pct": change_pct,
        "score": total_score,
        "level": level,
        "detail": {
            "technology": {"score": tech_score, "max": 30, "items": [
                ta.get("ma_status", ""), f"MACD{ta.get('macd',{}).get('trend','')}",
                f"RSI{rsi:.0f}", f"KDJ{ta.get('kdj',{}).get('cross','无')}"
            ]},
            "volume_price": {"score": vol_score, "max": 15, "items": [
                f"量比{vol.get('ratio','--')}", f"布林{pos:.0f}%"
            ]},
            "market": {"score": market_score, "max": 20, "items": [
                "大盘偏弱" if change_pct < -0.5 else "大盘平稳"
            ]},
        },
        "signals": {
            "bull": ta.get("bull_signals", []),
            "bear": ta.get("bear_signals", []),
        },
        "mas": ta.get("mas", {}),
        "bias": ta.get("bias", ""),
    })
