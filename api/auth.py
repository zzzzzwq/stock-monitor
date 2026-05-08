"""用户认证 API — 手机号注册登录 + 微信登录 + 开发测试"""
import json
import os
import logging
import urllib.request
import urllib.error

import bcrypt
from flask import request, jsonify
from models import get_session
from models.user import User
from auth.decorators import create_token, require_auth
from api import api_bp

logger = logging.getLogger(__name__)


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _check_password(password: str, hash: str) -> bool:
    if not hash:
        return False
    return bcrypt.checkpw(password.encode("utf-8"), hash.encode("utf-8"))

# 微信小程序配置（从环境变量读取）
WECHAT_APPID = os.getenv("WECHAT_APPID", "")
WECHAT_SECRET = os.getenv("WECHAT_SECRET", "")


def _wx_code_to_session(code: str) -> dict | None:
    """通过微信 API 换取 openid"""
    url = (
        f"https://api.weixin.qq.com/sns/jscode2session"
        f"?appid={WECHAT_APPID}&secret={WECHAT_SECRET}&js_code={code}&grant_type=authorization_code"
    )
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        logger.error(f"微信登录失败: {e}")
        return None


@api_bp.route("/auth/wx-login", methods=["POST"])
def wx_login():
    """微信一键登录"""
    data = request.get_json(force=True) or {}
    code = data.get("code", "")
    if not code:
        return jsonify({"error": "缺少 code 参数"}), 400

    if not WECHAT_APPID or not WECHAT_SECRET:
        return jsonify({"error": "服务端未配置微信登录"}), 500

    session_data = _wx_code_to_session(code)
    if not session_data or "openid" not in session_data:
        return jsonify({"error": "微信登录失败"}), 401

    openid = session_data["openid"]

    session = get_session()
    try:
        user = session.query(User).filter_by(openid=openid).first()
        if not user:
            user = User(openid=openid, nickname=data.get("nickname", ""), avatar_url=data.get("avatarUrl", ""))
            session.add(user)
            session.commit()

        token = create_token(user.id, openid)
        return jsonify({"token": token, "user": user.to_dict()})
    finally:
        session.close()


@api_bp.route("/auth/register", methods=["POST"])
def register():
    """手机号注册"""
    data = request.get_json(force=True) or {}
    phone = data.get("phone", "").strip()
    password = data.get("password", "").strip()
    nickname = data.get("nickname", "").strip() or f"用户{phone[-4:]}"

    if not phone or len(phone) < 11:
        return jsonify({"error": "请输入正确的手机号"}), 400
    if not password or len(password) < 6:
        return jsonify({"error": "密码至少6位"}), 400

    session = get_session()
    try:
        existing = session.query(User).filter_by(phone=phone).first()
        if existing:
            return jsonify({"error": "该手机号已注册"}), 409

        user = User(
            phone=phone,
            password_hash=_hash_password(password),
            nickname=nickname,
        )
        session.add(user)
        session.commit()

        token = create_token(user.id)
        return jsonify({"token": token, "user": user.to_dict()}), 201
    finally:
        session.close()


@api_bp.route("/auth/login", methods=["POST"])
def phone_login():
    """手机号密码登录"""
    data = request.get_json(force=True) or {}
    phone = data.get("phone", "").strip()
    password = data.get("password", "").strip()

    if not phone or not password:
        return jsonify({"error": "请输入手机号和密码"}), 400

    session = get_session()
    try:
        user = session.query(User).filter_by(phone=phone).first()
        if not user or not _check_password(password, user.password_hash):
            return jsonify({"error": "手机号或密码错误"}), 401

        token = create_token(user.id)
        return jsonify({"token": token, "user": user.to_dict()})
    finally:
        session.close()


@api_bp.route("/auth/dev-login", methods=["POST"])
def dev_login():
    """开发测试登录（无需微信环境）"""
    data = request.get_json(force=True) or {}
    nickname = data.get("nickname", f"dev_user_{data.get('id', '1')}")

    session = get_session()
    try:
        user = session.query(User).filter_by(nickname=nickname).first()
        if not user:
            user = User(nickname=nickname)
            session.add(user)
            session.commit()

        token = create_token(user.id, user.openid or "")
        return jsonify({"token": token, "user": user.to_dict()})
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


@api_bp.route("/auth/update-profile", methods=["PUT"])
@require_auth
def update_profile():
    """更新用户信息"""
    data = request.get_json(force=True) or {}
    session = get_session()
    try:
        user = session.query(User).filter_by(id=request.current_user_id).first()
        if not user:
            return jsonify({"error": "用户不存在"}), 404
        if "nickname" in data:
            user.nickname = data["nickname"]
        if "avatar_url" in data:
            user.avatar_url = data["avatar_url"]
        session.commit()
        return jsonify(user.to_dict())
    finally:
        session.close()
