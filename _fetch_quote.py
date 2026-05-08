import sys, json
sys.path.insert(0, ".")

from data.eastmoney import fetch_indices
from data.sina import get_holdings_quotes

config = json.load(open("config/config.json", encoding="utf-8"))

print("=== 大盘指数 (收盘) ===")
indices = fetch_indices(config["indices"])
for name, d in indices.items():
    chg = d.get("change", 0)
    pct = d.get("change_pct", 0)
    print(f"{name}: {d['price']:.2f}  ({chg:+.2f}, {pct:+.2f}%)")

print()
print("=== 持仓股 (收盘) ===")
holdings_data = get_holdings_quotes(config["holdings"])
total_pnl = 0
for h in config["holdings"]:
    code = f"{h['market']}{h['code']}"
    d = holdings_data.get(code)
    if d and d.get("price"):
        pnl = (d["price"] - h["cost_per_share"]) * h["shares"]
        pnl_pct = (d["price"] / h["cost_per_share"] - 1) * 100
        mv = d["price"] * h["shares"]
        chg = d["price"] - d["prev_close"]
        day_pct = (chg / d["prev_close"]) * 100 if d["prev_close"] else 0
        total_pnl += pnl
        print(f'{h["name"]} ({h["code"]})')
        print(f"  收盘: {d['price']:.2f}  今开: {d['open']:.2f}  最高: {d['high']:.2f}  最低: {d['low']:.2f}")
        print(f"  日涨跌: {chg:+.2f} ({day_pct:+.2f}%)")
        print(f"  持仓市值: {mv:.2f}  总盈亏: {pnl:+.2f} ({pnl_pct:+.2f}%)")
        print()

print(f"总持仓盈亏: {total_pnl:+.2f}")
