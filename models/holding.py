"""持仓模型"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from models import Base


class Holding(Base):
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    code = Column(String(16), nullable=False)  # e.g. "002920"
    name = Column(String(32), nullable=False)
    market = Column(String(4), nullable=False)  # "sh" or "sz"
    shares = Column(Integer, nullable=False)
    cost_per_share = Column(Float, nullable=False)
    related_boards = Column(String(256), default="")  # JSON 数组
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "market": self.market,
            "shares": self.shares,
            "cost_per_share": self.cost_per_share,
            "related_boards": self.related_boards,
            "is_active": self.is_active,
        }
