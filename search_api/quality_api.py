from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import date, datetime
from typing import Optional
from sqlalchemy.orm import Session

from database.engine import SessionLocal
from services.quality_metrics_service import QualityMetricsService
from search_api.schemas import QualityMetrics

router = APIRouter(prefix="/quality", tags=["quality"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/metrics", response_model=QualityMetrics)
async def get_quality_metrics(
    date: Optional[date] = Query(None, description="メトリクス対象日（指定しない場合最新）"),
    db: Session = Depends(get_db),
):
    """指定日または最新の品質メトリクスを取得する。

    メトリクスには以下が含まれる：

    - **missing_field_rate**: 必須フィールド欠損率（%）
    - **duplicate_rate**: 重複率（%）
    - **acquisition_delay_median**: 取得遅延中央値（分）
    - **coverage_rate**: インベントリカバレッジ率（%）
    - **coverage_municipality_rate**: 自治体カバレッジ率（%）
    - **geps_crawler_success_rate**: GEPSクロール成功率（%）
    - **geps_selector_match_rate**: GEPSセレクタマッチ率（%）
    - **duplicate_count**: 重複件数
    - **missing_fields**: フィールド別欠損件数
    - **daily_new**: 過去24時間新規件数
    - **daily_updated**: 過去24時間更新件数
    """
    date_start = None
    date_end = None
    if date is not None:
        date_start = datetime(date.year, date.month, date.day)
        date_end = datetime(date.year, date.month, date.day, 23, 59, 59)

    service = QualityMetricsService(db, date_start=date_start, date_end=date_end)
    metrics = service.collect_all_metrics()

    if not metrics:
        raise HTTPException(status_code=404, detail="No quality metrics available")

    missing_fields = {
        k.replace("missing_", ""): v
        for k, v in metrics.items()
        if k.startswith("missing_") and k != "missing_field_rate"
    }

    return QualityMetrics(
        date=date_end,
        missing_field_rate=metrics.get("missing_field_rate", 0.0),
        duplicate_rate=metrics.get("duplicate_rate", 0.0),
        acquisition_delay_median=metrics.get("acquisition_delay_median", 0.0),
        coverage_rate=metrics.get("coverage_rate", 0.0),
        coverage_municipality_rate=metrics.get("coverage_municipality_rate", 0.0),
        geps_crawler_success_rate=metrics.get("geps_crawler_success_rate", 0.0),
        geps_selector_match_rate=metrics.get("geps_selector_match_rate", 0.0),
        duplicate_count=metrics.get("duplicate_count", 0),
        missing_fields=missing_fields if missing_fields else None,
        daily_new=metrics.get("daily_new"),
        daily_updated=metrics.get("daily_updated"),
    )
