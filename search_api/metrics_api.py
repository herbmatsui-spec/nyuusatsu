from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, List

from services.metrics_query_service import MetricsQueryService
from services.health_checker import HealthChecker

router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.get("/summary")
def get_metrics_summary(hours: int = Query(24, ge=1, le=168)):
    """直近N時間におけるパイプラインの処理統計サマリーを取得する"""
    service = MetricsQueryService()
    try:
        return service.get_pipeline_summary(hours=hours)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/timeseries/{stage}")
def get_stage_timeseries(stage: str, metric_name: str = "success", hours: int = Query(24, ge=1, le=168)):
    """特定のステージの時系列メトリクスデータを取得する"""
    if stage not in ["crawl", "download", "analysis", "task_queue"]:
        raise HTTPException(status_code=400, detail="Invalid stage name")
        
    service = MetricsQueryService()
    try:
        return service.get_stage_timeseries(stage=stage, metric_name=metric_name, hours=hours)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/errors")
def get_error_distribution(hours: int = Query(24, ge=1, le=168)):
    """直近N時間におけるエラーの分布状況を取得する"""
    service = MetricsQueryService()
    try:
        return service.get_error_distribution(hours=hours)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
def get_system_health():
    """システムの各コンポーネントのヘルス状態を取得する"""
    checker = HealthChecker()
    try:
        return checker.check_all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from fastapi import Response
from services.prometheus_exporter import generate_prometheus_metrics

@router.get("")
def get_prometheus_metrics(hours: int = Query(24, ge=1, le=168)):
    """Prometheus形式でメトリクスを取得する"""
    try:
        metrics_data = generate_prometheus_metrics(hours=hours)
        return Response(content=metrics_data, media_type="text/plain")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
