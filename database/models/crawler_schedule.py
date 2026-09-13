"""CrawlerSchedule model for dynamic crawl frequency adjustment."""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from ._generated import Base
from .agency_category import AgencyCategory


class CrawlerSchedule(Base):
    """Dynamic crawl schedule per category and priority level."""

    __tablename__ = "crawler_schedule"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey("agency_categories.id"), nullable=False, index=True)
    priority_level = Column(Integer, nullable=False, default=1)
    base_interval_seconds = Column(Integer, nullable=False, default=3600)
    current_interval_seconds = Column(Integer, nullable=False, default=3600)
    success_rate = Column(Float, nullable=False, default=1.0)
    last_updated = Column(DateTime, nullable=False)

    category = relationship("AgencyCategory")

    def __repr__(self):
        return (
            f"<CrawlerSchedule(category_id={self.category_id}, "
            f"priority={self.priority_level}, "
            f"interval={self.current_interval_seconds}s, "
            f"success_rate={self.success_rate:.2f})>"
        )