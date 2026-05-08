"""持仓组合优化分析 — 行业集中度、风险等级、仓位合理性、调仓建议"""
import json
import logging
from collections import Counter
from data.akshare_data import get_related_board_changes

logger = logging.getLogger(__name__)


def analyze_portfolio(holdings: list[dict], pnl_list: list[dict],
                      tech_data: dict = None, boards: dict = None) -> dict:
    """对用户整个持仓做多维度组合分析"""
    if not holdings:
        return {"error": "无持仓数据"}

    # === 基础数据 ===
    total_value = sum(p.get("market_value", 0) for p in pnl_list)
    if total_value == 0:
        return {"error": "市值数据不足"}

    # 各维度分析
    sector = _analyze_sector(holdings, total_value)
    risk = _analyze_risk(pnl_list, sector)
    position = _analyze_position(holdings, total_value)
    correlation = _analyze_correlation(holdings, pnl_list)
    safety = _analyze_safety(pnl_list)
    suggestions = _generate_suggestions(sector, risk, position, correlation, safety, boards)

    return {
        "sector_concentration": sector,
        "risk_level": risk["level"],
        "risk_score": risk["score"],
        "total_value": round(total_value, 2),
        "diversification_score": _calc_diversification(sector, len(holdings)),
        "single_stock_weight": position,
        "correlation_analysis": correlation,
        "safety_assessment": safety,
        "rebalance_suggestions": suggestions,
    }


def _calc_diversification(sector: dict, holding_count: int) -> int:
    """分散度评分 0-100"""
    if not sector or holding_count <= 1:
        return 0
    num_vals = [v for v in sector.values() if isinstance(v, (int, float))]
    max_pct = max(num_vals) if num_vals else 100
    if max_pct > 80:
        return 20
    elif max_pct > 60:
        return 40
    elif max_pct > 40:
        return 60
    elif max_pct > 20:
        return 80
    return 100


def _analyze_sector(holdings: list[dict], total_value: float) -> dict:
    """行业集中度分析"""
    board_values = {}
    for h in holdings:
        boards = []
        try:
            boards = json.loads(h.get("related_boards", "[]"))
        except Exception:
            pass
        weight = (h.get("shares", 0) * h.get("cost_per_share", 0)) / total_value
        if not boards:
            # 无板块信息时，标记为"其他"
            boards = ["其他"]
        for b in boards:
            board_values[b] = board_values.get(b, 0) + weight

    # 转为百分比
    result = {k: round(v * 100, 1) for k, v in sorted(board_values.items(), key=lambda x: -x[1])}

    # 判断集中度（排除 _judgment）
    num_values = [v for k, v in result.items() if not k.startswith("_")]
    top_pct = max(num_values) if num_values else 0
    if len(result) <= 1 and top_pct > 80:
        result["_judgment"] = "高度集中"
    elif top_pct > 50:
        result["_judgment"] = "较为集中"
    elif top_pct > 30:
        result["_judgment"] = "适度分散"
    else:
        result["_judgment"] = "分散良好"

    return result


def _analyze_risk(pnl_list: list[dict], sector: dict) -> dict:
    """风险等级评估"""
    risk_score = 0
    max_pnl_pct = 0
    for p in pnl_list:
        pct = abs(p.get("pnl_pct", 0))
        max_pnl_pct = max(max_pnl_pct, pct)

    # 浮亏风险
    if max_pnl_pct > 15:
        risk_score += 40
    elif max_pnl_pct > 10:
        risk_score += 30
    elif max_pnl_pct > 5:
        risk_score += 20
    elif max_pnl_pct > 0:
        risk_score += 10

    # 行业集中风险
    sector_judgment = sector.get("_judgment", "适度分散")
    if "高度集中" in sector_judgment:
        risk_score += 30
    elif "较为集中" in sector_judgment:
        risk_score += 20

    # 市场环境风险 (默认中风险)
    risk_score += 15

    # 等级判定
    if risk_score >= 70:
        level = "高风险"
    elif risk_score >= 50:
        level = "中高风险"
    elif risk_score >= 30:
        level = "中风险"
    elif risk_score >= 15:
        level = "中低风险"
    else:
        level = "低风险"

    return {"score": risk_score, "level": level}


def _analyze_position(holdings: list[dict], total_value: float) -> list[dict]:
    """单只持仓权重合理性"""
    result = []
    for h in holdings:
        value = h.get("shares", 0) * h.get("cost_per_share", 0)
        weight = value / total_value * 100 if total_value > 0 else 0

        advice = ""
        if weight > 50:
            advice = "占比过高，建议控制在50%以内"
        elif weight > 30:
            advice = "仓位较重，注意集中风险"
        elif weight < 10:
            advice = "仓位偏轻"

        result.append({
            "name": h.get("name", ""),
            "code": h.get("code", ""),
            "weight": round(weight, 1),
            "advice": advice,
        })

    return result


def _analyze_correlation(holdings: list[dict], pnl_list: list[dict]) -> str:
    """持仓相关性分析"""
    if len(holdings) <= 1:
        return "仅有一只持仓，无法分析相关性"

    # 获取所有板块
    all_boards = set()
    for h in holdings:
        try:
            boards = json.loads(h.get("related_boards", "[]"))
            all_boards.update(boards)
        except Exception:
            pass

    # 检查板块重叠度
    overlap_count = len(holdings) - len(all_boards) if len(holdings) > len(all_boards) else 0

    same_sector = 0
    for i, h1 in enumerate(holdings):
        b1 = set()
        try:
            b1 = set(json.loads(h1.get("related_boards", "[]")))
        except Exception:
            pass
        for h2 in holdings[i + 1:]:
            b2 = set()
            try:
                b2 = set(json.loads(h2.get("related_boards", "[]")))
            except Exception:
                pass
            if b1 & b2:
                same_sector += 1

    total_pairs = len(holdings) * (len(holdings) - 1) // 2
    overlap_ratio = same_sector / total_pairs if total_pairs > 0 else 0

    if overlap_ratio > 0.7:
        return "持仓高度同质化，板块重叠严重，分散风险效果有限。建议增加不同板块的配置"
    elif overlap_ratio > 0.3:
        return f"部分持仓在同一板块，{same_sector}/{total_pairs}对组合存在板块重叠"
    elif overlap_ratio > 0:
        return "持仓有一定板块重叠，但整体分散尚可"
    return "持仓分散在不同板块，相关性较低"


def _analyze_safety(pnl_list: list[dict]) -> dict:
    """安全性评估"""
    if not pnl_list:
        return {}

    total_pnl = sum(p.get("pnl", 0) for p in pnl_list)
    avg_pnl_pct = sum(p.get("pnl_pct", 0) for p in pnl_list) / len(pnl_list)
    max_loss = min(p.get("pnl_pct", 0) for p in pnl_list)
    total_value = sum(p.get("market_value", 0) for p in pnl_list)

    if total_pnl < 0:
        if avg_pnl_pct < -10:
            assessment = "组合整体浮亏严重，需警惕进一步下跌风险"
        elif avg_pnl_pct < -5:
            assessment = "组合整体承压，多数持仓处于浮亏状态"
        else:
            assessment = "组合轻微浮亏，整体可控"
    elif total_pnl > 0:
        assessment = "组合整体盈利，当前持仓状况良好"
    else:
        assessment = "组合持平"

    return {
        "total_unrealized_pnl": round(total_pnl, 2),
        "avg_pnl_pct": round(avg_pnl_pct, 2),
        "max_drawdown": round(max_loss, 2),
        "total_value": round(total_value, 2),
        "assessment": assessment,
    }


def _generate_suggestions(sector: dict, risk: dict, position: list[dict],
                          correlation: str, safety: dict, boards: dict = None) -> list[str]:
    """生成调仓建议"""
    suggestions = []

    # 行业集中建议
    sector_judgment = sector.get("_judgment", "")
    if "高度集中" in sector_judgment:
        suggestions.append("行业过于集中，建议增加其他板块配置以分散风险")
    elif "较为集中" in sector_judgment:
        top_sector = [k for k in sector if not k.startswith("_")][:1]
        if top_sector:
            suggestions.append(f"{top_sector[0]}板块占比偏高，可适当配置不同板块对冲")

    # 仓位建议
    for p in position:
        if p.get("advice"):
            suggestions.append(f"{p['name']}：{p['advice']}")

    # 风险建议
    if risk["level"] in ("高风险", "中高风险"):
        suggestions.append("当前组合风险偏高，建议降低仓位或增加防御型资产")
    elif risk["level"] == "中风险":
        suggestions.append("组合风险适中，可维持当前配置")

    # 关联性建议
    if "高度同质化" in correlation or "重叠严重" in correlation:
        suggestions.append(correlation)

    # 安全性建议
    if safety.get("max_drawdown", 0) < -10:
        suggestions.append("部分持仓浮亏较深，需评估是否需要止损或补仓降低成本")
    elif safety.get("avg_pnl_pct", 0) < -5:
        suggestions.append("整体浮亏，建议关注大盘企稳信号后再做操作")

    # 板块环境建议
    if boards and any(v is not None for v in boards.values()):
        weak_boards = [n for n, c in boards.items() if c is not None and c < -1]
        if weak_boards:
            suggestions.append(f"持仓涉及{'、'.join(weak_boards[:2])}板块走弱，注意风险")

    return suggestions if suggestions else ["当前组合无明显问题，保持现有策略"]
