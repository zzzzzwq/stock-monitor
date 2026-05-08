"""持仓管理 API"""
import json
import logging

from flask import request, jsonify
from models import get_session
from models.holding import Holding
from auth.decorators import require_auth
from api import api_bp

logger = logging.getLogger(__name__)


@api_bp.route("/holdings", methods=["GET"])
@require_auth
def list_holdings():
    """获取当前用户持仓列表"""
    session = get_session()
    try:
        holdings = session.query(Holding).filter_by(
            user_id=request.current_user_id, is_active=True
        ).all()
        return jsonify([h.to_dict() for h in holdings])
    finally:
        session.close()


@api_bp.route("/holdings", methods=["POST"])
@require_auth
def add_holding():
    """添加持仓"""
    data = request.get_json(force=True) or {}
    required = ["code", "name", "market", "shares", "cost_per_share"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"缺少必填字段: {field}"}), 400

    session = get_session()
    try:
        holding = Holding(
            user_id=request.current_user_id,
            code=data["code"],
            name=data["name"],
            market=data["market"],
            shares=int(data["shares"]),
            cost_per_share=float(data["cost_per_share"]),
            related_boards=json.dumps(data.get("related_boards", []), ensure_ascii=False),
        )
        session.add(holding)
        session.commit()
        return jsonify(holding.to_dict()), 201
    finally:
        session.close()


@api_bp.route("/holdings/<int:holding_id>", methods=["PUT"])
@require_auth
def update_holding(holding_id: int):
    """修改持仓"""
    data = request.get_json(force=True) or {}
    session = get_session()
    try:
        holding = session.query(Holding).filter_by(
            id=holding_id, user_id=request.current_user_id
        ).first()
        if not holding:
            return jsonify({"error": "持仓不存在"}), 404

        if "shares" in data:
            holding.shares = int(data["shares"])
        if "cost_per_share" in data:
            holding.cost_per_share = float(data["cost_per_share"])
        if "name" in data:
            holding.name = data["name"]
        if "market" in data:
            holding.market = data["market"]
        if "code" in data:
            holding.code = data["code"]
        if "related_boards" in data:
            holding.related_boards = json.dumps(data["related_boards"], ensure_ascii=False)
        if "is_active" in data:
            holding.is_active = bool(data["is_active"])

        session.commit()
        return jsonify(holding.to_dict())
    finally:
        session.close()


@api_bp.route("/holdings/<int:holding_id>", methods=["DELETE"])
@require_auth
def delete_holding(holding_id: int):
    """删除持仓（软删除）"""
    session = get_session()
    try:
        holding = session.query(Holding).filter_by(
            id=holding_id, user_id=request.current_user_id
        ).first()
        if not holding:
            return jsonify({"error": "持仓不存在"}), 404
        holding.is_active = False
        session.commit()
        return jsonify({"message": "删除成功"})
    finally:
        session.close()
