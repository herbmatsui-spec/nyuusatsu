from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class QualityAlert(Base):
    __tablename__ = "quality_alert"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric = Column(String(100), nullable=False)
    level = Column(String(20), nullable=False)
    value = Column(Float, nullable=False)
    threshold = Column(Float, nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow)
