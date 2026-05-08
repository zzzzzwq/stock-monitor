"""数据库初始化 — 支持 SQLite / PostgreSQL 自动切换"""
import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

# 优先使用 DATABASE_URL 环境变量（Render PostgreSQL），否则使用本地 SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL:
    engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
else:
    db_path = os.getenv("DB_PATH", os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data", "stock_monitor.db"
    ))
    engine = create_engine(f"sqlite:///{db_path}", echo=False)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


def init_db():
    from models.user import User
    from models.holding import Holding
    Base.metadata.create_all(engine)

    # 处理新增字段的迁移（SQLite）
    inspector = inspect(engine)
    columns = [c["name"] for c in inspector.get_columns("users")]
    with engine.connect() as conn:
        if "phone" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR(16)"))
        if "password_hash" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(128) DEFAULT ''"))
        conn.commit()


def get_session():
    return SessionLocal()
