from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class AgencyInventory(Base):
    __tablename__ = "agency_inventory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agency_name = Column(String(255), nullable=False, index=True)
    prefecture_code = Column(String(2), nullable=False, index=True)
    municipality = Column(String(128), nullable=True)
    top_page_url = Column(String(1024), nullable=True)
    bid_page_url = Column(String(1024), nullable=True)
    page_format = Column(String(16), nullable=False, default="unknown")  # html/pdf/mixed/unknown
    is_crawled = Column(Boolean, default=False)
    crawler_config_id = Column(Integer, ForeignKey("crawl_configs.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
