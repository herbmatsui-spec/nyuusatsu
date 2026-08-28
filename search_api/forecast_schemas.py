from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ForecastResponse(BaseModel):
    id: int
    agency_id: int
    fiscal_year: int
    quarter: Optional[int] = None
    title: str
    description: Optional[str] = None
    estimated_budget: Optional[str] = None
    estimated_budget_amount: Optional[int] = None
    expected_publish_date: Optional[datetime] = None
    expected_bid_date: Optional[datetime] = None
    category: Optional[str] = None
    industry_category: Optional[str] = None
    source_url: Optional[str] = None
    pdf_url: Optional[str] = None
    status: str
    priority_level: Optional[str] = None
    related_bid_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ForecastListResponse(BaseModel):
    items: List[ForecastResponse]
    total: int
    page: int
    per_page: int


class ForecastSearchQuery(BaseModel):
    keyword: Optional[str] = None
    agency_id: Optional[int] = None
    category: Optional[str] = None
    fiscal_year: Optional[int] = None
    status: Optional[str] = None
    page: int = 1
    per_page: int = 20
