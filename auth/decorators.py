"""JWT 认证装饰器"""
import functools
import os
import json
from datetime import datetime, timedelta, timezone

import jwt
from flask import request, jsonify

# JWT 密钥（生产环境建议通过环境变量配置）
JWT_SECRET = os.getenv("JWT_SECRET", "stock-monitor-dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 7


def create_token(user_id: int, openid: str = "") -> str:
    """签发 JWT token"""
    payload = {
        "user_id": user_id,
        "openid": openid,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    """解码 JWT token"""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def require_auth(f):
    """需要认证的装饰器"""

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "未提供认证令牌"}), 401

        token = auth_header[7:]
        payload = decode_token(token)
        if not payload:
            return jsonify({"error": "令牌无效或已过期"}), 401

        request.current_user_id = payload.get("user_id")
        request.current_openid = payload.get("openid", "")
        return f(*args, **kwargs)

    return wrapper


def optional_auth(f):
    """可选认证装饰器（有 token 则解析，无 token 也可访问）"""

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        request.current_user_id = None
        request.current_openid = ""

        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            payload = decode_token(token)
            if payload:
                request.current_user_id = payload.get("user_id")
                request.current_openid = payload.get("openid", "")

        return f(*args, **kwargs)

    return wrapper
