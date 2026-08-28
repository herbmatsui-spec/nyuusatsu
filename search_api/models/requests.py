from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date

class BidSearchRequest(BaseModel):
    """検索リクエストモデル"""
    keyword: Optional[str] = Field(None, description="キーワード検索（案件名・発注機関）")
    budget_min: Optional[int] = Field(None, description="予算下限（円）")
    budget_max: Optional[int] = Field(None, description="予算上限（円）")
    announcement_date_from: Optional[date] = Field(None, description="公告日（開始）")
    announcement_date_to: Optional[date] = Field(None, description="公告日（終了）")
    closing_date_from: Optional[date] = Field(None, description="締切日（開始）")
    closing_date_to: Optional[date] = Field(None, description="締切日（終了）")
    industry_ids: Optional[List[int]] = Field(None, description="業種IDリスト")
    region_ids: Optional[List[int]] = Field(None, description="地域IDリスト")
    page: int = Field(1, ge=1, description="ページ番号")
    page_size: int = Field(20, ge=1, le=100, description="1ページあたりの件数")
