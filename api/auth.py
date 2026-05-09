"""认证已移除 — 保留 stub 防止 import 报错"""
from flask import jsonify, request
from api import api_bp
from auth.decorators import require_auth
from models import get_session
from models.user import User


@api_bp.route("/auth/dev-login", methods=["POST"])
def dev_login():
    """自动使用默认用户（认证已移除）"""
    session = get_session()
    try:
        user = session.query(User).filter_by(id=1).first()
        if not user:
            from models.user import User as U
            user = U(nickname="默认用户")
            session.add(user)
            session.commit()
        return jsonify({"token": "", "user": user.to_dict()})
    finally:
        session.close()


@api_bp.route("/auth/me", methods=["GET"])
@require_auth
def get_me():
    """获取当前用户信息"""
    session = get_session()
    try:
        user = session.query(User).filter_by(id=request.current_user_id).first()
        if not user:
            return jsonify({"error": "用户不存在"}), 404
        return jsonify(user.to_dict())
    finally:
        session.close()
