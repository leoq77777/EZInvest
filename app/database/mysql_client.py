"""
MySQL客户端封装
"""
from sqlalchemy import create_engine, MetaData, Table, Column, String, DateTime, Float, Text, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from typing import Optional
from app.config import settings
from datetime import datetime
from sqlalchemy.pool import StaticPool

# 创建数据库引擎
if settings.SQLITE_URL:
    # 支持 SQLite（文件或内存）。内存模式建议使用 StaticPool 来保持连接一致性。
    if settings.SQLITE_URL == "sqlite:///:memory:":
        engine = create_engine(
            settings.SQLITE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )
    else:
        engine = create_engine(
            settings.SQLITE_URL,
            connect_args={"check_same_thread": False},
            echo=False,
        )
else:
    DATABASE_URL = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
        "?charset=utf8mb4"
    )

    engine = create_engine(
        DATABASE_URL,
        poolclass=QueuePool,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        echo=False
    )

# 创建Session工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 声明基类
Base = declarative_base()


class FinancialData(Base):
    """金融数据表"""
    __tablename__ = "financial_data"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(50), index=True, nullable=False, comment="股票代码")
    market = Column(String(20), nullable=False, comment="市场")
    data_type = Column(String(50), nullable=False, comment="数据类型")
    date = Column(DateTime, index=True, nullable=False, comment="日期")
    data = Column(Text, nullable=False, comment="数据JSON")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")


class NewsData(Base):
    """新闻数据表"""
    __tablename__ = "news_data"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(50), index=True, nullable=False, comment="股票代码")
    title = Column(String(500), nullable=False, comment="标题")
    content = Column(Text, nullable=False, comment="内容")
    source = Column(String(200), nullable=False, comment="来源")
    url = Column(String(500), nullable=True, comment="链接")
    published_at = Column(DateTime, index=True, nullable=False, comment="发布时间")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    embedding_id = Column(Integer, nullable=True, comment="FAISS向量ID")


def get_db() -> Session:
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库表"""
    Base.metadata.create_all(bind=engine)


def close_db():
    """关闭数据库连接"""
    engine.dispose()


# 如果配置为使用 SQLite，则在导入时自动创建表，方便本地开发/测试
if settings.SQLITE_URL:
    try:
        init_db()
    except Exception:
        # 避免在导入时抛出异常
        pass

