from sqlalchemy import Column, Integer, String, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class QualityThreshold(Base):
    __tablename__ = "quality_threshold"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_name = Column(String(100), nullable=False, unique=True)
    warn_at = Column(Float, nullable=False)
    alert_at = Column(Float, nullable=False)
    lower_is_worse = Column(Boolean, nullable=False, default=False)
