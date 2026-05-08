"""持仓盈亏计算"""
from typing import Any


def calc_holding_pnl(price: float, cost: float, shares: int) -> dict:
    """计算单只持仓盈亏"""
    pnl = (price - cost) * shares
    pnl_pct = (price / cost - 1) * 100
    unwind_req = ((cost / price) - 1) * 100 if price > 0 else 0
    market_value = price * shares
    return {
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "unwind_pct": round(unwind_req, 2),
        "market_value": round(market_value, 2),
    }


def calc_all_pnl(holdings: list[dict], prices: dict[str, float]) -> list[dict]:
    """计算全部持仓盈亏，返回 [{holding_info, pnl_info}]"""
    results = []
    total_pnl = 0
    for h in holdings:
        price = prices.get(h["code"], 0)
        if price == 0:
            continue
        pnl = calc_holding_pnl(price, h["cost_per_share"], h["shares"])
        pnl["code"] = h["code"]
        pnl["name"] = h["name"]
        pnl["price"] = price
        pnl["shares"] = h["shares"]
        pnl["cost"] = h["cost_per_share"]
        total_pnl += pnl["pnl"]
        results.append(pnl)
    return results
