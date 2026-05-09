"""认证已移除 — require_auth 直接放行，使用默认用户"""
import functools

from flask import request


def create_token(user_id: int, openid: str = "") -> str:
    return ""


def decode_token(token: str) -> dict | None:
    return None


def require_auth(f):
    """免认证，默认使用第一个用户"""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        request.current_user_id = 1
        request.current_openid = ""
        return f(*args, **kwargs)
    return wrapper


def optional_auth(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        request.current_user_id = 1
        request.current_openid = ""
        return f(*args, **kwargs)
    return wrapper
