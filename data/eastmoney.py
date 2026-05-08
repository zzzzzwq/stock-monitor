"""东方财富 push2 API（复用 daily_analysis.py 的 fetch() 逻辑）"""
import json
import urllib.request
import logging

logger = logging.getLogger(__name__)

EASTMONEY_URL = "https://push2.eastmoney.com/api/qt/stock/get"


def fetch(secid: str) -> dict | None:
    """获取东方财富个股/指数行情"""
    url = f"{EASTMONEY_URL}?secid={secid}&fields=f43,f44,f45,f46,f47,f48,f50,f57,f58,f170,f105,f106"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())["data"]
            return d
    except Exception as e:
        logger.error(f"东方财富获取失败 [{secid}]: {e}")
        return None


def parse_market_data(raw: dict) -> dict | None:
    """解析东方财富原始数据"""
    if not raw or not raw.get("f43"):
        return None
    p = raw["f43"] / 100
    prev_close = p - (raw.get("f170", 0) / 100)
    return {
        "price": p,
        "high": raw.get("f44", 0) / 100 or p,
        "low": raw.get("f45", 0) / 100 or p,
        "open": raw.get("f46", 0) / 100 or p,
        "volume": raw.get("f47", 0) or 0,
        "amount": raw.get("f48", 0) or 0,
        "change": raw.get("f170", 0) / 100,
        "change_pct": (raw.get("f170", 0) / 100) / prev_close * 100 if prev_close else 0,
    }


def _to_em_secid(code: str) -> str:
    """将 sh000001/sz399001 转为东方财富 secid 格式"""
    code = code.strip()
    if code.startswith("sh"):
        return f"1.{code[2:]}"
    elif code.startswith("sz"):
        return f"0.{code[2:]}"
    return code


def fetch_indices(indices_config: list[dict]) -> dict[str, dict]:
    """批量获取指数收盘数据"""
    result = {}
    for idx in indices_config:
        secid = _to_em_secid(idx.get("code", ""))
        raw = fetch(secid)
        parsed = parse_market_data(raw)
        if parsed:
            result[idx["name"]] = parsed
    return result


def fetch_holdings_close(holdings: list[dict]) -> dict[str, dict]:
    """获取持仓股收盘数据"""
    result = {}
    for h in holdings:
        secid = f"{'0' if h['market'] == 'sz' else '1'}.{h['code']}"
        raw = fetch(secid)
        parsed = parse_market_data(raw)
        if parsed:
            parsed["name"] = h["name"]
            result[h["code"]] = parsed
    return result


def fetch_board(bid: str) -> dict | None:
    """获取板块行情"""
    raw = fetch(f"90.{bid}")
    return parse_market_data(raw)
