"""通知配置 API"""
import json
import logging

from flask import request, jsonify
from models import get_session
from models.user import User
from auth.decorators import require_auth
from api import api_bp

logger = logging.getLogger(__name__)


@api_bp.route("/notify/config", methods=["GET"])
@require_auth
def get_notify_config():
    """获取通知配置"""
    session = get_session()
    try:
        user = session.query(User).filter_by(id=request.current_user_id).first()
        if not user:
            return jsonify({"error": "用户不存在"}), 404

        at_mobiles = []
        try:
            at_mobiles = json.loads(user.at_mobiles) if isinstance(user.at_mobiles, str) and user.at_mobiles else []
        except Exception:
            pass

        return jsonify({
            "wechat_webhook": user.wechat_webhook or "",
            "dingtalk_webhook": user.dingtalk_webhook or "",
            "error_webhook": user.error_webhook or "",
            "at_mobiles": at_mobiles,
            "at_all_on_error": user.at_all_on_error,
        })
    finally:
        session.close()


@api_bp.route("/notify/config", methods=["PUT"])
@require_auth
def update_notify_config():
    """更新通知配置"""
    data = request.get_json(force=True) or {}
    session = get_session()
    try:
        user = session.query(User).filter_by(id=request.current_user_id).first()
        if not user:
            return jsonify({"error": "用户不存在"}), 404

        if "wechat_webhook" in data:
            user.wechat_webhook = data["wechat_webhook"]
        if "dingtalk_webhook" in data:
            user.dingtalk_webhook = data["dingtalk_webhook"]
        if "error_webhook" in data:
            user.error_webhook = data["error_webhook"]
        if "at_mobiles" in data:
            user.at_mobiles = json.dumps(data["at_mobiles"], ensure_ascii=False)
        if "at_all_on_error" in data:
            user.at_all_on_error = bool(data["at_all_on_error"])

        session.commit()
        return jsonify({"message": "更新成功"})
    finally:
        session.close()
