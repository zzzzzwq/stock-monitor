"""分析数据查询 API"""
import json
import logging
from datetime import datetime

from flask import request, jsonify
from models import get_session
from models.holding import Holding
from auth.decorators import require_auth
from api import api_bp

from data.sina import get_indices_quotes, get_holdings_quotes
from data.eastmoney import fetch_indices, fetch_holdings_close, fetch_board
from data.akshare_data import (
    get_history, get_related_board_changes,
    get_market_sentiment, get_top_boards, get_index_tech,
)
from analysis.technicals import analyze_stock
from analysis.portfolio import calc_all_pnl
from analysis.insights import generate_insight
from notify.formatter import format_market_report
from scheduler.calendar import is_trading_day, next_trading_day

logger = logging.getLogger(__name__)


def _load_user_config(user_id: int) -> dict | None:
    """将数据库中的用户数据组装为兼容旧版 jobs 的 config 结构"""
    import json as _json
    from models.user import User
    session = get_session()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return None

        holdings = session.query(Holding).filter_by(user_id=user_id, is_active=True).all()
        if not holdings:
            return None

        # 从全局配置读取大盘指数和板块设置
        try:
            with open("config/config.json", "r", encoding="utf-8") as f:
                global_config = _json.load(f)
        except Exception:
            global_config = {}

        holding_list = []
        all_boards = set()
        for h in holdings:
            boards = []
            try:
                boards = _json.loads(h.related_boards) if h.related_boards else []
            except Exception:
                pass
            all_boards.update(boards)
            holding_list.append({
                "code": h.code,
                "name": h.name,
                "market": h.market,
                "shares": h.shares,
                "cost_per_share": h.cost_per_share,
                "related_boards": boards,
            })

        return {
            "holdings": holding_list,
            "indices": global_config.get("indices", []),
            "related_boards": list(all_boards) if all_boards else global_config.get("related_boards", []),
            "notify": {
                "wechat_webhook": user.wechat_webhook or "",
                "dingtalk_webhook": user.dingtalk_webhook or "",
                "error_webhook": user.error_webhook or "",
                "at_mobiles": _json.loads(user.at_mobiles) if isinstance(user.at_mobiles, str) and user.at_mobiles else [],
                "at_all_on_error": user.at_all_on_error,
            },
            "general": global_config.get("general", {"timezone": "Asia/Shanghai"}),
        }
    finally:
        session.close()


@api_bp.route("/analysis/summary", methods=["GET"])
@require_auth
def analysis_summary():
    """今日概览：大盘 + 持仓盈亏 + 技术面"""
    config = _load_user_config(request.current_user_id)
    if not config:
        return jsonify({"error": "无持仓数据"}), 400

    # 大盘数据
    indices = get_indices_quotes(config.get("indices", []))
    indices_data = {}
    for idx in config.get("indices", []):
        sina_code = idx["sina_code"]
        d = indices.get(sina_code)
        if d:
            prev = d.get("prev_close", 1) or 1
            chg_pct = (d["price"] - prev) / prev * 100
            indices_data[idx["name"]] = {
                "price": d["price"],
                "change_pct": round(chg_pct, 2),
                "high": d.get("high", 0),
                "low": d.get("low", 0),
            }

    # 持仓实时行情
    holdings_live = get_holdings_quotes(config["holdings"])
    prices = {}
    holdings_data = []
    for h in config["holdings"]:
        key = f"{h['market']}{h['code']}"
        d = holdings_live.get(key)
        if d:
            prev = d.get("prev_close", 1) or 1
            chg_pct = (d["price"] - prev) / prev * 100
            prices[h["code"]] = d["price"]
            holdings_data.append({
                "code": h["code"],
                "name": h["name"],
                "price": d["price"],
                "change_pct": round(chg_pct, 2),
                "high": d.get("high", 0),
                "low": d.get("low", 0),
                "open": d.get("open", 0),
                "volume": d.get("volume", 0),
            })

    # 盈亏计算
    pnl_list = calc_all_pnl(config["holdings"], prices) if prices else []
    total_pnl = round(sum(p.get("pnl", 0) for p in pnl_list), 2)

    # 技术面（完整数据）
    tech_data = {}
    for h in config["holdings"]:
        df = get_history(h["code"])
        if not df.empty:
            full = analyze_stock(df)
            # 前端展示精简版
            tech_data[h["code"]] = {
                "ma_status": full.get("ma_status", ""),
                "bias": full.get("bias", ""),
                "score": full.get("score", 0),
                "rsi": full.get("rsi", 0),
                "price": full.get("price", 0),
                "mas": full.get("mas", {}),
                "macd_trend": full.get("macd", {}).get("trend", ""),
                "kdj": full.get("kdj", {}),
                "boll": full.get("boll", {}),
                "vol": full.get("vol", {}),
                "bull_signals": full.get("bull_signals", []),
                "bear_signals": full.get("bear_signals", []),
            }

    return jsonify({
        "is_trading_day": is_trading_day(),
        "indices": indices_data,
        "holdings": holdings_data,
        "pnl": pnl_list,
        "total_pnl": total_pnl,
        "tech_data": tech_data,
    })


@api_bp.route("/analysis/detail/<code>", methods=["GET"])
@require_auth
def analysis_detail(code: str):
    """单只股票详细技术分析 + 持仓总结"""
    df = get_history(code)
    if df.empty:
        return jsonify({"error": f"无法获取 {code} 的历史数据"}), 400

    result = analyze_stock(df)

    # 如果有持仓数据，生成多维总结
    config = _load_user_config(request.current_user_id)
    if config:
        h = next((x for x in config.get("holdings", []) if x["code"] == code), None)
        if h:
            # 获取实时行情丰富数据
            live_data = get_holdings_quotes([h])
            key = f"{h['market']}{h['code']}"
            ld = live_data.get(key, {})
            prev = ld.get("prev_close", 1) or 1
            h_enhanced = {
                **h,
                "cost": h.get("cost_per_share", 0),
                "price": ld.get("price", 0),
                "change_pct": round((ld.get("price", 0) - prev) / prev * 100, 2) if prev else 0,
                "high": ld.get("high", 0),
                "low": ld.get("low", 0),
            }
            result["insight"] = generate_insight(h_enhanced, result)

    return jsonify(result)


@api_bp.route("/analysis/market", methods=["GET"])
@require_auth
def market_environment():
    """大盘环境分析"""
    sentiment = get_market_sentiment()
    top_boards = get_top_boards(8)

    # 指数技术面
    index_tech = {}
    for idx in ["sh000001", "sz399001", "sz399006", "sh000688"]:
        tech = get_index_tech(idx)
        if tech:
            index_tech[idx] = tech

    return jsonify({
        "sentiment": sentiment,
        "top_boards": top_boards,
        "index_tech": index_tech,
    })


@api_bp.route("/analysis/report", methods=["GET"])
@require_auth
def analysis_report():
    """"生成结构化分析报告 — 大盘→持仓→总结"""
    config = _load_user_config(request.current_user_id)
    if not config:
        return jsonify({"error": "无持仓数据"}), 400

    # 大盘数据
    indices = get_indices_quotes(config.get("indices", []))
    indices_data = {}
    for idx in config.get("indices", []):
        sina_code = idx["sina_code"]
        d = indices.get(sina_code)
        if d:
            prev = d.get("prev_close", 1) or 1
            chg_pct = (d["price"] - prev) / prev * 100
            indices_data[idx["name"]] = {
                "price": d["price"],
                "change_pct": round(chg_pct, 2),
                "high": d.get("high", 0),
                "low": d.get("low", 0),
            }

    # 持仓实时行情 + 盈亏
    holdings = config["holdings"]
    live_data = get_holdings_quotes(holdings)
    prices = {}
    holdings_enhanced = []
    for h in holdings:
        key = f"{h['market']}{h['code']}"
        d = live_data.get(key)
        if d:
            prev = d.get("prev_close", 1) or 1
            chg_pct = (d["price"] - prev) / prev * 100
            prices[h["code"]] = d["price"]
            holdings_enhanced.append({
                "code": h["code"],
                "name": h["name"],
                "price": d["price"],
                "change_pct": round(chg_pct, 2),
                "high": d.get("high", 0),
                "low": d.get("low", 0),
                "open": d.get("open", 0),
                "volume": d.get("volume", 0),
                "prev_close": prev,
                "shares": h["shares"],
                "cost": h["cost_per_share"],
            })

    # 盈亏
    pnl_list = calc_all_pnl(config["holdings"], prices)
    for p in pnl_list:
        h = next((x for x in holdings_enhanced if x["code"] == p["code"]), None)
        if h:
            p["high"] = h["high"]
            p["low"] = h["low"]
            p["prev_close"] = h["prev_close"]

    # 技术面
    tech_data = {}
    for h in holdings:
        df = get_history(h["code"])
        if not df.empty:
            tech_data[h["code"]] = analyze_stock(df)

    # 板块
    boards = get_related_board_changes(config.get("related_boards", []))

    # 资金流向
    sentiment = get_market_sentiment()
    fund_flow = sentiment.get("fund_flow")

    # 生成报告文本
    report_text = format_market_report(
        indices=indices_data,
        holdings_data=holdings_enhanced,
        pnl_list=pnl_list,
        boards=boards,
        tech_data=tech_data,
        fund_flow=fund_flow,
    )

    # 生成每只持仓的多维总结
    insights = {}
    for h in holdings_enhanced:
        ta = tech_data.get(h["code"], {})
        insights[h["code"]] = generate_insight(h, ta)

    total_pnl = sum(p.get("pnl", 0) for p in pnl_list)

    return jsonify({
        "report": report_text,
        "summary": {
            "total_pnl": round(total_pnl, 2),
            "holdings_count": len(holdings_enhanced),
        },
        "indices": indices_data,
        "holdings": holdings_enhanced,
        "insights": insights,
    })


@api_bp.route("/analysis/boards", methods=["GET"])
@require_auth
def analysis_boards():
    """相关板块涨跌幅"""
    config = _load_user_config(request.current_user_id)
    if not config:
        return jsonify({"error": "无持仓数据"}), 400
    boards = get_related_board_changes(config.get("related_boards", []))
    return jsonify(boards)


@api_bp.route("/analysis/next-trading-day", methods=["GET"])
def next_day():
    """下一个交易日"""
    return jsonify({"date": next_trading_day(), "is_trading_day": is_trading_day()})
