from pydantic import BaseModel
from typing import Optional, List
from datetime import date

class IndustrySchema(BaseModel):
    id: int
    name: str

class RegionSchema(BaseModel):
    id: int
    name: str

class BidSummary(BaseModel):
    """検索結果一覧用サマリモデル"""
    id: int
    project_name: str
    organization: Optional[str]
    budget: Optional[str]
    budget_amount: Optional[int]
    announcement_date: Optional[date]
    closing_date: Optional[date]
    industry: Optional[IndustrySchema]
    region: Optional[RegionSchema]

class BidSearchResponse(BaseModel):
    """検索結果レスポンスモデル"""
    total: int
    page: int
    page_size: int
    total_pages: int
    results: List[BidSummary]
