from sqlalchemy import Column, Integer, String, Float, DateTime, Enum
from sqlalchemy.ext.declarative import declarative_base
import enum
from datetime import datetime

Base = declarative_base()

class CrawlStatusEnum(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    DONE = "done"

class CrawlPriority(Base):
    __tablename__ = "crawl_priority"

    id = Column(Integer, primary_key=True, autoincrement=True)
    prefecture_code = Column(String(2), nullable=False, index=True)
    prefecture_name = Column(String(32), nullable=False)
    agency_count = Column(Integer, nullable=False, default=0)  # 推定発注機関数
    target_industry_match = Column(Float, nullable=False, default=0.0)  # 業種一致度 (0.0-1.0)
    score = Column(Float, nullable=False, default=0.0)  # 優先度スコア (0-100)
    status = Column(Enum(CrawlStatusEnum), nullable=False, default=CrawlStatusEnum.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
