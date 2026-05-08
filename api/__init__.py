"""API 蓝图"""
from flask import Blueprint

api_bp = Blueprint("api", __name__, url_prefix="/api")


from api import auth, holdings, analysis, notify, stock
