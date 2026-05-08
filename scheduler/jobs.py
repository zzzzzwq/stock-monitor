"""8个定时分析任务 — 多用户版"""
import json
import logging
from datetime import datetime

from data.sina import get_indices_quotes, get_holdings_quotes
from data.eastmoney import fetch_indices, fetch_holdings_close, fetch_board
from data.akshare_data import get_history, get_related_board_changes, get_news
from analysis.technicals import analyze_stock
from analysis.portfolio import calc_all_pnl
from notify.formatter import (
    format_0830, format_0925, format_0935,
    format_1130, format_1305, format_1500,
    format_2000, format_2200,
)
from notify.pusher import push
from scheduler.calendar import is_trading_day, next_trading_day

logger = logging.getLogger(__name__)


def _build_user_config(user, holdings, global_config: dict) -> dict:
    """将数据库中的用户数据组装为兼容旧版分析函数的 config 结构"""
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

    if not holding_list:
        return {}

    at_mobiles = []
    try:
        at_mobiles = json.loads(user.at_mobiles) if isinstance(user.at_mobiles, str) and user.at_mobiles else []
    except Exception:
        pass

    return {
        "holdings": holding_list,
        "indices": global_config.get("indices", []),
        "related_boards": list(all_boards) if all_boards else global_config.get("related_boards", []),
        "notify": {
            "wechat_webhook": user.wechat_webhook or "",
            "dingtalk_webhook": user.dingtalk_webhook or "",
            "error_webhook": user.error_webhook or "",
            "at_mobiles": at_mobiles,
            "at_all_on_error": user.at_all_on_error,
        },
        "general": global_config.get("general", {"timezone": "Asia/Shanghai"}),
    }


def _load_global_config() -> dict:
    """加载全局配置"""
    try:
        with open("config/config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _get_active_users():
    """获取所有活跃用户及其持仓"""
    from models import get_session
    from models.user import User
    from models.holding import Holding

    session = get_session()
    try:
        users = session.query(User).filter_by(is_active=True).all()
        global_config = _load_global_config()
        result = []
        for user in users:
            holdings = session.query(Holding).filter_by(user_id=user.id, is_active=True).all()
            config = _build_user_config(user, holdings, global_config)
            if config:
                result.append((user, config))
        return result
    finally:
        session.close()


def _should_skip() -> bool:
    """检查是否应跳过（非交易日直接跳过）"""
    if not is_trading_day():
        logger.info("非交易日，跳过")
        return True
    return False


def _get_indices_close(config: dict) -> dict:
    """获取大盘指数数据（盘后收盘用东方财富）"""
    return fetch_indices(config.get("indices", []))


def _get_indices_live(config: dict) -> dict:
    """获取大盘指数实时数据（盘中用Sina）"""
    raw = get_indices_quotes(config.get("indices", []))
    result = {}
    for idx in config.get("indices", []):
        sina_code = idx["sina_code"]
        d = raw.get(sina_code)
        if d:
            prev = d.get("prev_close", 1) or 1
            chg_pct = (d["price"] - prev) / prev * 100
            result[idx["name"]] = {
                "price": d["price"],
                "change_pct": chg_pct,
                "high": d.get("high", 0),
                "low": d.get("low", 0),
                "open": d.get("open", 0),
            }
    return result


def _get_holdings_live(config: dict) -> dict:
    """获取持仓实时数据"""
    holdings = config.get("holdings", [])
    raw = get_holdings_quotes(holdings)
    result = {}
    for h in holdings:
        key = f"{h['market']}{h['code']}"
        d = raw.get(key)
        if d:
            prev = d.get("prev_close", 1) or 1
            chg_pct = (d["price"] - prev) / prev * 100
            result[h["code"]] = {
                "name": h["name"],
                "price": d["price"],
                "prev_close": prev,
                "change_pct": chg_pct,
                "open": d.get("open", 0),
                "high": d.get("high", 0),
                "low": d.get("low", 0),
                "volume": d.get("volume", 0),
                "amount": d.get("amount", 0),
            }
    return result


def _get_tech_data(config: dict) -> dict:
    """获取全部持仓技术分析数据"""
    result = {}
    for h in config.get("holdings", []):
        df = get_history(h["code"])
        if not df.empty:
            result[h["code"]] = analyze_stock(df)
    return result


def _get_board_data(config: dict) -> dict:
    """获取相关板块数据"""
    return get_related_board_changes(config.get("related_boards", []))


def _get_holdings_pnl(config: dict) -> list:
    """获取持仓盈亏（收盘价）"""
    holdings = config.get("holdings", [])
    close_data = fetch_holdings_close(holdings)
    prices = {code: d["price"] for code, d in close_data.items()}
    return calc_all_pnl(holdings, prices)


def _run_for_all(job_fn):
    """对每个活跃用户执行一次 job 函数"""
    users = _get_active_users()
    if not users:
        logger.info("无活跃用户，跳过")
        return
    logger.info(f"共 {len(users)} 个活跃用户")
    for user, config in users:
        try:
            user_label = user.nickname or f"用户#{user.id}"
            logger.info(f"执行 [{job_fn.__name__}] 用户: {user_label}")
            job_fn(config)
        except Exception as e:
            logger.error(f"用户 {user.id} 执行失败: {e}", exc_info=True)


def job_0830(config: dict = None):
    """08:30 盘前 - 隔夜消息、大盘回顾、持仓技术面"""
    if config is None:
        return _run_for_all(job_0830)
    if _should_skip():
        return
    try:
        indices = _get_indices_live(config)
        holdings_live = _get_holdings_live(config)
        prices = {code: d["price"] for code, d in holdings_live.items()}
        holdings_pnl = calc_all_pnl(config.get("holdings", []), prices)
        tech_data = _get_tech_data(config)
        title, content = format_0830(indices, holdings_pnl, tech_data)
        push(config, title, content)
    except Exception as e:
        logger.error(f"盘前分析失败: {e}", exc_info=True)


def job_0925(config: dict = None):
    """09:25 竞价 - 集合竞价结果"""
    if config is None:
        return _run_for_all(job_0925)
    if _should_skip():
        return
    try:
        indices = _get_indices_live(config)
        holdings_live = _get_holdings_live(config)
        title, content = format_0925(indices, holdings_live)
        push(config, title, content)
    except Exception as e:
        logger.error(f"竞价分析失败: {e}", exc_info=True)


def job_0935(config: dict = None):
    """09:35 开盘5分"""
    if config is None:
        return _run_for_all(job_0935)
    if _should_skip():
        return
    try:
        indices = _get_indices_live(config)
        holdings_live = _get_holdings_live(config)
        title, content = format_0935(indices, holdings_live)
        push(config, title, content)
    except Exception as e:
        logger.error(f"开盘分析失败: {e}", exc_info=True)


def job_1130(config: dict = None):
    """11:30 午盘复盘"""
    if config is None:
        return _run_for_all(job_1130)
    if _should_skip():
        return
    try:
        indices = _get_indices_live(config)
        holdings_live = _get_holdings_live(config)
        boards = _get_board_data(config)
        tech_data = _get_tech_data(config)
        title, content = format_1130(indices, holdings_live, boards, tech_data)
        push(config, title, content)
    except Exception as e:
        logger.error(f"午盘复盘失败: {e}", exc_info=True)


def job_1305(config: dict = None):
    """13:05 下午开盘"""
    if config is None:
        return _run_for_all(job_1305)
    if _should_skip():
        return
    try:
        indices = _get_indices_live(config)
        holdings_live = _get_holdings_live(config)
        title, content = format_1305(indices, holdings_live)
        push(config, title, content)
    except Exception as e:
        logger.error(f"下午开盘分析失败: {e}", exc_info=True)


def job_1500(config: dict = None):
    """15:00 收盘复盘"""
    if config is None:
        return _run_for_all(job_1500)
    if _should_skip():
        return
    try:
        indices = _get_indices_close(config)
        holdings_pnl = _get_holdings_pnl(config)
        boards = _get_board_data(config)
        tech_data = _get_tech_data(config)
        title, content = format_1500(indices, holdings_pnl, boards, tech_data)
        push(config, title, content)
    except Exception as e:
        logger.error(f"收盘复盘失败: {e}", exc_info=True)


def job_2000(config: dict = None):
    """20:00 晚间消息"""
    if config is None:
        return _run_for_all(job_2000)
    if _should_skip():
        return
    try:
        news_data = {}
        for h in config.get("holdings", []):
            news = get_news(h["code"])
            news_data[f"{h['name']}({h['code']})"] = news
        title, content = format_2000(news_data)
        push(config, title, content)
    except Exception as e:
        logger.error(f"晚间消息失败: {e}", exc_info=True)


def job_2200(config: dict = None):
    """22:00 明日预览"""
    if config is None:
        return _run_for_all(job_2200)
    if _should_skip():
        return
    try:
        tech_data = _get_tech_data(config)
        next_date = next_trading_day()
        names = {h["code"]: h["name"] for h in config.get("holdings", [])}

        suggestions = {}
        for h in config.get("holdings", []):
            ta = tech_data.get(h["code"])
            if ta:
                if ta["bias"] == "偏多":
                    suggestions[h["code"]] = f"{h['name']}: 偏多持仓观察"
                elif ta["bias"] == "偏空":
                    suggestions[h["code"]] = f"{h['name']}: 偏空注意风险"
                else:
                    suggestions[h["code"]] = f"{h['name']}: 中性等待方向"

        preview = {
            "next_date": next_date,
            "tech_data": tech_data,
            "names": names,
            "suggestions": suggestions,
        }
        title, content = format_2200(preview)
        push(config, title, content)
    except Exception as e:
        logger.error(f"明日预览失败: {e}", exc_info=True)


# job函数注册表
JOB_REGISTRY = {
    "0830": job_0830,
    "0925": job_0925,
    "0935": job_0935,
    "1130": job_1130,
    "1305": job_1305,
    "1500": job_1500,
    "2000": job_2000,
    "2200": job_2200,
}
