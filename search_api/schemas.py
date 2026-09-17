"""Pydantic schemas for the Search API.

These models define the public API contract. They are decoupled from the
internal SQLAlchemy ORM models so that internal fields can be excluded and
the structure can be optimized for API clients (web / mobile / third-party).
"""
from datetime import datetime
from typing import Optional, List, Generic, TypeVar, Dict

from pydantic import BaseModel, Field

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class PaginationParams:
    """Query-parameter defaults shared across list endpoints."""
    DEFAULT_PAGE = 1
    DEFAULT_SIZE = 20
    MAX_SIZE = 100


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""
    items: List[T]
    total: int = Field(..., description="Total number of matching records")
    page: int = Field(..., ge=1, description="Current page number (1-based)")
    size: int = Field(..., ge=1, description="Number of items per page")
    total_pages: int = Field(..., description="Total number of pages")


# ---------------------------------------------------------------------------
# Bid schemas
# ---------------------------------------------------------------------------

class BidBase(BaseModel):
    """入札の基本情報"""
    id: int
    filename: str
    organization_name: Optional[str] = Field(None, description="発注機関名")
    prefecture_code: Optional[str] = Field(None, description="都道府県コード")
    announcement_date: Optional[datetime] = Field(None, description="公告日")
    source_url: Optional[str] = Field(None, description="元URL")


class BidDetail(BidBase):
    """入札詳細情報 — BidBase に抽出・分析フィールドを追加"""
    budget: Optional[str] = Field(None, description="予算額（文字列）")
    budget_amount: Optional[int] = Field(None, description="予算額（数値）")
    qualifications: Optional[str] = Field(None, description="参加資格")
    deadline: Optional[str] = Field(None, description="締切日")
    deliverables: Optional[str] = Field(None, description="納品物")
    key_risks: Optional[str] = Field(None, description="主要リスク")
    notes: Optional[str] = Field(None, description="備考")
    current_status: str = Field(..., description="現在ステータス")
    industry_category: Optional[str] = Field(None, description="業種カテゴリ")
    actual_bid_amount: Optional[int] = Field(None, description="実際の入札金額")
    win_loss_reason: Optional[str] = Field(None, description="落選理由等")
    awarded_company: Optional[str] = Field(None, description="落札会社")
    awarded_date: Optional[datetime] = Field(None, description="落札日")
    award_rate: Optional[float] = Field(None, description="入札率")
    analyzed_at: Optional[datetime] = Field(None, description="分析日時")
    updated_date: Optional[datetime] = Field(None, description="更新日")
    created_at: Optional[datetime] = Field(None, description="作成日時")
    updated_at: Optional[datetime] = Field(None, description="更新日時")

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Award result schemas
# ---------------------------------------------------------------------------

class AwardResultBase(BaseModel):
    """落札結果の基本情報"""
    id: int
    tender_id: Optional[int] = Field(None, description="入札ID")
    project_name: Optional[str] = Field(None, description="案件名")
    source_url: Optional[str] = Field(None, description="元URL")
    agency_name: Optional[str] = Field(None, description="機関名")
    category: Optional[str] = Field(None, description="カテゴリ")
    budget_amount: Optional[int] = Field(None, description="予算額")
    contract_amount: Optional[int] = Field(None, description="契約金額")
    award_rate: Optional[float] = Field(None, description="落札率")
    winner_name: Optional[str] = Field(None, description="落札者")
    winner_count: Optional[int] = Field(None, description="落札者数")
    announcement_date: Optional[datetime] = Field(None, description="公告日")
    award_date: Optional[datetime] = Field(None, description="落札日")


class AwardResultDetail(AwardResultBase):
    """落札結果詳細 — AwardResultBase に追加フィールド"""
    winner_normalized: Optional[str] = Field(None, description="正規化落札者名")
    fiscal_year: Optional[int] = Field(None, description="会計年度")
    is_rebidding: bool = Field(False, description="再入札かどうか")
    created_at: Optional[datetime] = Field(None, description="作成日時")
    updated_at: Optional[datetime] = Field(None, description="更新日時")

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Forecast schemas
# ---------------------------------------------------------------------------

class ForecastItem(BaseModel):
    """予測データアイテム"""
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
    notes: Optional[str] = None
    related_bid_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Quality metrics schemas
# ---------------------------------------------------------------------------

class QualityMetrics(BaseModel):
    """品質メトリクスレスポンス"""
    date: Optional[datetime] = Field(None, description="メトリクス対象日")
    missing_field_rate: float = Field(..., description="必須フィールド欠損率（%）")
    duplicate_rate: float = Field(..., description="重複率（%）")
    acquisition_delay_median: float = Field(..., description="取得遅延中央値（分）")
    coverage_rate: float = Field(..., description="インベントリカバレッジ率（%）")
    coverage_municipality_rate: float = Field(..., description="自治体カバレッジ率（%）")
    geps_crawler_success_rate: float = Field(..., description="GEPSクロール成功率（%）")
    geps_selector_match_rate: float = Field(..., description="GEPSセレクタマッチ率（%）")
    duplicate_count: int = Field(..., description="重複件数")
    missing_fields: Optional[Dict[str, int]] = Field(None, description="フィールド別欠損件数")
    daily_new: Optional[int] = Field(None, description="過去24時間新規件数")
    daily_updated: Optional[int] = Field(None, description="過去24時間更新件数")


class PricePredictionSchema(BaseModel):
    """価格予測データ"""
    id: int
    bid_id: Optional[int] = None
    bid_amount: Optional[int] = None
    expected_price: Optional[int] = None
    win_probability: Optional[float] = None
    rationale: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Saved search & alert schemas (auth required)
# ---------------------------------------------------------------------------

class SavedSearchBase(BaseModel):
    """保存検索の基本情報"""
    name: str = Field(..., max_length=255, description="検索名")
    criteria_json: str = Field(..., description="検索条件（JSON文字列）")
    is_active: bool = Field(True, description="アクティブかどうか")


class SavedSearchCreate(SavedSearchBase):
    """保存検索作成リクエスト"""


class SavedSearchUpdate(BaseModel):
    """保存検索更新リクエスト"""
    name: Optional[str] = Field(None, max_length=255, description="検索名")
    criteria_json: Optional[str] = Field(None, description="検索条件（JSON文字列）")
    is_active: Optional[bool] = Field(None, description="アクティブかどうか")


class SavedSearchResponse(SavedSearchBase):
    """保存検索レスポンス"""
    id: int
    user_id: int
    last_notified_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AlertConfigBase(BaseModel):
    """アラート設定の基本情報"""
    channel_type: str = Field(..., description="通知チャンネルタイプ (email, webhook)")
    email_address: Optional[str] = None
    webhook_url: Optional[str] = None
    is_active: bool = Field(True, description="アクティブかどうか")


class AlertConfigCreate(AlertConfigBase):
    """アラート設定作成リクエスト"""


class AlertConfigResponse(AlertConfigBase):
    """アラート設定レスポンス"""
    id: int
    user_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
