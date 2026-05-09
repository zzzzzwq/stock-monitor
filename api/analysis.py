"""分析数据查询 API"""
import json
import logging
import time

from flask import request, jsonify
from models import get_session
from models.holding import Holding
from auth.decorators import require_auth
from api import api_bp

from data.sina import get_indices_quotes, get_holdings_quotes
from data.eastmoney import fetch_indices, fetch_holdings_close, fetch_board
from data.akshare_data import (
    get_history, get_related_board_changes,
    get_market_sentiment, get_top_boards, get_index_tech, get_index_intraday,
)
from analysis.technicals import analyze_stock
from analysis.portfolio import calc_all_pnl
from analysis.insights import generate_insight
from analysis.portfolio_optimizer import analyze_portfolio
from notify.formatter import format_market_report
from scheduler.calendar import is_trading_day, next_trading_day

logger = logging.getLogger(__name__)
_DASHBOARD_CACHE = {}
_DASHBOARD_CACHE_TTL = 45


def _load_global_config() -> dict:
    """读取全局配置文件，失败时返回空字典。"""
    try:
        with open("config/config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _load_user_config(user_id: int) -> dict | None:
    """将数据库中的用户数据组装为兼容旧版 jobs 的 config 结构"""
    from models.user import User
    session = get_session()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return None

        holdings = session.query(Holding).filter_by(user_id=user_id, is_active=True).all()
        if not holdings:
            return None

        global_config = _load_global_config()

        holding_list = []
        all_boards = set()
        for h in holdings:
            boards = []
            try:
                boards = json.loads(h.related_boards) if h.related_boards else []
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
                "at_mobiles": json.loads(user.at_mobiles) if isinstance(user.at_mobiles, str) and user.at_mobiles else [],
                "at_all_on_error": user.at_all_on_error,
            },
            "general": global_config.get("general", {"timezone": "Asia/Shanghai"}),
        }
    finally:
        session.close()


def _build_indices_data(indices_config: list[dict]) -> dict:
    """构建指数实时行情数据。"""
    indices = get_indices_quotes(indices_config)
    indices_data = {}
    for idx in indices_config:
        sina_code = idx["sina_code"]
        d = indices.get(sina_code)
        if not d:
            continue
        prev = d.get("prev_close", 1) or 1
        chg_pct = (d["price"] - prev) / prev * 100
        indices_data[idx["name"]] = {
            "code": idx.get("code", sina_code),
            "sina_code": sina_code,
            "price": d["price"],
            "change_pct": round(chg_pct, 2),
            "high": d.get("high", 0),
            "low": d.get("low", 0),
            "open": d.get("open", 0),
            "prev_close": prev,
        }
    return indices_data


def _build_index_tech(index_symbols: list[str]) -> dict:
    """构建指数技术面概览。"""
    index_tech = {}
    for idx in index_symbols:
        tech = get_index_tech(idx)
        if tech:
            index_tech[idx] = tech
    return index_tech


def _build_index_intraday(indices_config: list[dict]) -> dict:
    """构建指数当日波动线。"""
    lines = {}
    for idx in indices_config:
        symbol = idx.get("code") or idx.get("sina_code")
        if not symbol:
            continue
        points = get_index_intraday(symbol)
        if points:
            lines[idx["name"]] = points
    return lines


def _build_holdings_report_payload(config: dict | None) -> dict:
    """构建持仓报告所需的实时数据、盈亏、技术面和总结。"""
    payload = {
        "holdings": [],
        "pnl": [],
        "insights": {},
        "tech_data": {},
        "boards": {},
        "fund_flow": None,
        "report": "",
        "summary": {
            "total_pnl": 0.0,
            "holdings_count": 0,
            "up_count": 0,
            "down_count": 0,
            "flat_count": 0,
        },
    }
    if not config:
        return payload

    holdings = config["holdings"]
    live_data = get_holdings_quotes(holdings)
    prices = {}

    for h in holdings:
        key = f"{h['market']}{h['code']}"
        d = live_data.get(key)
        if not d:
            continue
        prev = d.get("prev_close", 1) or 1
        chg_pct = (d["price"] - prev) / prev * 100
        prices[h["code"]] = d["price"]
        payload["holdings"].append({
            "code": h["code"],
            "name": h["name"],
            "market": h["market"],
            "price": d["price"],
            "change_pct": round(chg_pct, 2),
            "high": d.get("high", 0),
            "low": d.get("low", 0),
            "open": d.get("open", 0),
            "volume": d.get("volume", 0),
            "prev_close": prev,
            "shares": h["shares"],
            "cost": h["cost_per_share"],
            "related_boards": h.get("related_boards", []),
        })

    payload["pnl"] = calc_all_pnl(holdings, prices)
    for p in payload["pnl"]:
        live_holding = next((x for x in payload["holdings"] if x["code"] == p["code"]), None)
        if live_holding:
            p["high"] = live_holding["high"]
            p["low"] = live_holding["low"]
            p["prev_close"] = live_holding["prev_close"]
            p["change_pct"] = live_holding["change_pct"]

    for h in holdings:
        df = get_history(h["code"])
        if df.empty:
            continue
        payload["tech_data"][h["code"]] = analyze_stock(df)

    payload["boards"] = get_related_board_changes(config.get("related_boards", []))
    sentiment = get_market_sentiment()
    payload["fund_flow"] = sentiment.get("fund_flow")

    indices_data = _build_indices_data(config.get("indices", []))
    payload["report"] = format_market_report(
        indices_data,
        payload["holdings"],
        payload["pnl"],
        payload["boards"],
        payload["tech_data"],
        payload["fund_flow"],
    )

    for h in payload["holdings"]:
        payload["insights"][h["code"]] = generate_insight(h, payload["tech_data"].get(h["code"], {}))

    total_pnl = round(sum(p.get("pnl", 0) for p in payload["pnl"]), 2)
    up_count = sum(1 for h in payload["holdings"] if h.get("change_pct", 0) > 0.2)
    down_count = sum(1 for h in payload["holdings"] if h.get("change_pct", 0) < -0.2)
    flat_count = max(len(payload["holdings"]) - up_count - down_count, 0)
    payload["summary"] = {
        "total_pnl": total_pnl,
        "holdings_count": len(payload["holdings"]),
        "up_count": up_count,
        "down_count": down_count,
        "flat_count": flat_count,
    }
    return payload


@api_bp.route("/analysis/summary", methods=["GET"])
@require_auth
def analysis_summary():
    """今日概览：大盘 + 持仓盈亏 + 技术面"""
    config = _load_user_config(request.current_user_id)
    if not config:
        return jsonify({"error": "无持仓数据"}), 400

    indices_data = _build_indices_data(config.get("indices", []))

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
                "code": h["code"], "name": h["name"],
                "price": d["price"], "change_pct": round(chg_pct, 2),
                "high": d.get("high", 0), "low": d.get("low", 0),
                "open": d.get("open", 0), "volume": d.get("volume", 0),
            })

    pnl_list = calc_all_pnl(config["holdings"], prices) if prices else []
    total_pnl = round(sum(p.get("pnl", 0) for p in pnl_list), 2)

    tech_data = {}
    for h in config["holdings"]:
        df = get_history(h["code"])
        if not df.empty:
            full = analyze_stock(df)
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


@api_bp.route("/analysis/portfolio", methods=["GET"])
@require_auth
def portfolio_analysis():
    """持仓组合优化分析"""
    config = _load_user_config(request.current_user_id)
    if not config:
        return jsonify({"error": "无持仓数据"}), 400

    live_data = get_holdings_quotes(config["holdings"])
    prices = {}
    for h in config["holdings"]:
        key = f"{h['market']}{h['code']}"
        d = live_data.get(key)
        if d:
            prices[h["code"]] = d["price"]

    pnl_list = calc_all_pnl(config["holdings"], prices)
    enhanced = []
    for p in pnl_list:
        h = next((x for x in config["holdings"] if x["code"] == p["code"]), None)
        if h:
            p["related_boards"] = h.get("related_boards", [])
        enhanced.append(p)

    boards = get_related_board_changes(config.get("related_boards", []))
    result = analyze_portfolio(config["holdings"], enhanced, boards=boards)
    return jsonify(result)


@api_bp.route("/analysis/detail/<code>", methods=["GET"])
@require_auth
def analysis_detail(code: str):
    """单只股票详细技术分析 + 持仓总结"""
    df = get_history(code)
    if df.empty:
        return jsonify({"error": f"无法获取 {code} 的历史数据"}), 400

    result = analyze_stock(df)

    config = _load_user_config(request.current_user_id)
    if config:
        h = next((x for x in config.get("holdings", []) if x["code"] == code), None)
        if h:
            live_data = get_holdings_quotes([h])
            key = f"{h['market']}{h['code']}"
            ld = live_data.get(key, {})
            prev = ld.get("prev_close", 1) or 1
            h_enhanced = {
                **h, "cost": h.get("cost_per_share", 0),
                "price": ld.get("price", 0),
                "change_pct": round((ld.get("price", 0) - prev) / prev * 100, 2) if prev else 0,
                "high": ld.get("high", 0), "low": ld.get("low", 0),
            }
            result["insight"] = generate_insight(h_enhanced, result)

    return jsonify(result)


@api_bp.route("/analysis/market", methods=["GET"])
@require_auth
def market_environment():
    """大盘环境分析"""
    global_config = _load_global_config()
    sentiment = get_market_sentiment()
    top_boards = get_top_boards(8)
    index_symbols = [x.get("code", x.get("sina_code")) for x in global_config.get("indices", [])] or [
        "sh000001", "sz399001", "sz399006", "sh000688"
    ]
    index_tech = _build_index_tech(index_symbols)
    indices_data = _build_indices_data(global_config.get("indices", []))
    return jsonify({
        "sentiment": sentiment,
        "top_boards": top_boards,
        "index_tech": index_tech,
        "indices": indices_data,
        "is_trading_day": is_trading_day(),
    })


@api_bp.route("/analysis/dashboard", methods=["GET"])
@require_auth
def analysis_dashboard():
    """Dashboard 聚合数据：大盘、资金流、持仓快照与全文总结。"""
    refresh = request.args.get("refresh") == "1"
    include_lines = request.args.get("lines") == "1"
    cache_key = f"user:{request.current_user_id}:lines:{include_lines}"
    cached = _DASHBOARD_CACHE.get(cache_key)
    now_ts = time.time()
    if cached and not refresh and now_ts - cached["time"] < _DASHBOARD_CACHE_TTL:
        return jsonify(cached["data"])

    global_config = _load_global_config()
    config = _load_user_config(request.current_user_id)

    indices_config = global_config.get("indices", [])
    index_symbols = [x.get("code", x.get("sina_code")) for x in indices_config]
    indices_data = _build_indices_data(indices_config)
    index_tech = _build_index_tech(index_symbols)
    sentiment = get_market_sentiment()
    top_boards = get_top_boards(8)
    report_payload = _build_holdings_report_payload(config)

    data = {
        "is_trading_day": is_trading_day(),
        "indices": indices_data,
        "index_tech": index_tech,
        "index_intraday": _build_index_intraday(indices_config) if include_lines else {},
        "sentiment": sentiment,
        "top_boards": top_boards,
        "report": report_payload["report"],
        "holdings": report_payload["holdings"],
        "pnl": report_payload["pnl"],
        "insights": report_payload["insights"],
        "tech_data": report_payload["tech_data"],
        "boards": report_payload["boards"],
        "holdings_summary": report_payload["summary"],
        "cached_at": int(now_ts),
    }
    _DASHBOARD_CACHE[cache_key] = {"time": now_ts, "data": data}
    return jsonify(data)


@api_bp.route("/analysis/index-intraday", methods=["GET"])
@require_auth
def analysis_index_intraday():
    """指数当日分时波动线。"""
    global_config = _load_global_config()
    return jsonify({"index_intraday": _build_index_intraday(global_config.get("indices", []))})


@api_bp.route("/analysis/report", methods=["GET"])
@require_auth
def analysis_report():
    """生成分析报告 — 大盘→持仓→总结（无持仓也返回大盘）"""
    config = _load_user_config(request.current_user_id)
    global_config = _load_global_config()
    indices_data = _build_indices_data(global_config.get("indices", []))
    report_payload = _build_holdings_report_payload(config)
    return jsonify({
        "report": report_payload["report"],
        "summary": report_payload["summary"],
        "indices": indices_data,
        "holdings": report_payload["holdings"],
        "insights": report_payload["insights"],
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
