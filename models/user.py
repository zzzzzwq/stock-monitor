"""用户模型"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from models import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    openid = Column(String(128), unique=True, nullable=True, index=True)  # 微信 openid
    phone = Column(String(16), unique=True, nullable=True, index=True)    # 手机号
    password_hash = Column(String(128), default="")                       # 密码哈希
    nickname = Column(String(64), default="")
    avatar_url = Column(String(256), default="")
    wechat_webhook = Column(String(512), default="")
    dingtalk_webhook = Column(String(512), default="")
    error_webhook = Column(String(512), default="")
    at_mobiles = Column(String(256), default="")  # JSON 数组
    at_all_on_error = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            "id": self.id,
            "openid": self.openid,
            "phone": self.phone,
            "nickname": self.nickname,
            "avatar_url": self.avatar_url,
            "wechat_webhook": bool(self.wechat_webhook),
            "dingtalk_webhook": bool(self.dingtalk_webhook),
            "at_mobiles": self.at_mobiles,
            "at_all_on_error": self.at_all_on_error,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else "",
        }
