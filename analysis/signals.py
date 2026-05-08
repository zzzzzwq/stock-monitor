"""信号聚合和多空判断"""
import logging

logger = logging.getLogger(__name__)


def format_signals(analysis_result: dict) -> str:
    """将技术分析结果格式化为可读信号"""
    if not analysis_result:
        return "数据不足"
    parts = []
    if analysis_result.get("bull_signals"):
        parts.extend(analysis_result["bull_signals"])
    if analysis_result.get("bear_signals"):
        parts.extend(analysis_result["bear_signals"])
    return " ".join(parts[:6]) if parts else "无明显信号"


def quick_judge(analysis_result: dict) -> str:
    """快速判断 """
    if not analysis_result:
        return "数据不足"
    if analysis_result.get("bias") == "偏多":
        return "偏多 ✓"
    elif analysis_result.get("bias") == "偏空":
        return "偏空 ⚠"
    return "中性 →"
