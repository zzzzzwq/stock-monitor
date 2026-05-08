"""Sina 实时行情 API（复用现有 get_sina() 逻辑）"""
import urllib.request
import logging

logger = logging.getLogger(__name__)

SINA_URL = "https://hq.sinajs.cn/list="


def get_raw(codes: str) -> str:
    """获取Sina原始CSV数据"""
    url = SINA_URL + codes
    req = urllib.request.Request(url, headers={"Referer": "https://finance.sina.com.cn"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read().decode("gbk")
    except Exception as e:
        logger.error(f"Sina行情获取失败 [{codes}]: {e}")
        return ""


def parse_quote(line: str) -> dict | None:
    """解析单行Sina行情数据"""
    try:
        if not line or '"' not in line:
            return None
        p = line.split('"')[1].split(",")
        code_key = line.split("=")[0].split("_")[-1]
        return {
            "code": code_key,
            "name": p[0],
            "open": float(p[1]) if p[1] else 0,
            "prev_close": float(p[2]) if p[2] else 0,
            "price": float(p[3]) if p[3] else 0,
            "high": float(p[4]) if p[4] else 0,
            "low": float(p[5]) if p[5] else 0,
            "volume": int(float(p[8])) if p[8] else 0,  # 股
            "amount": float(p[9]) if len(p) > 9 and p[9] else 0,
        }
    except (IndexError, ValueError) as e:
        logger.warning(f"解析Sina行情失败: {e}")
        return None


def get_queries(codes: list[str]) -> dict[str, dict]:
    """批量获取行情，返回 {code: data}"""
    if not codes:
        return {}
    raw = get_raw(",".join(codes))
    result = {}
    for line in raw.strip().split("\n"):
        parsed = parse_quote(line)
        if parsed:
            result[parsed["code"]] = parsed
    return result


def get_indices_quotes(indices_config: list[dict]) -> dict[str, dict]:
    """获取大盘指数行情"""
    codes = [idx["sina_code"] for idx in indices_config]
    return get_queries(codes)


def get_holdings_quotes(holdings: list[dict]) -> dict[str, dict]:
    """获取持仓股行情，返回 {code: data}"""
    codes = []
    for h in holdings:
        codes.append(f"{h['market']}{h['code']}")
    return get_queries(codes)
