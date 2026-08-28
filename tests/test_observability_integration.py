import json
import pytest
from fastapi.testclient import TestClient

from database.session import get_db
from database.models.pipeline_metric import PipelineMetric
from services.health_checker import HealthChecker, HealthStatus
from services.metrics_query_service import MetricsQueryService
from services.prometheus_exporter import generate_prometheus_metrics
from search_api.main import app

client = TestClient(app)

def test_integration_structured_logging():
    # 構造化ログフォーマッターの動作テスト
    from utils.structured_formatter import StructuredFormatter
    import logging
    
    formatter = StructuredFormatter()
    
    class MockRecord:
        def __init__(self):
            self.created = 1770000000.0
            self.levelname = "ERROR"
            self.name = "integration_test"
            self.msg = "DB connection error occurred. api_key=dummy_secret_key"
            self.module = "integration"
            self.funcName = "run_test"
            self.lineno = 100
            self.exc_info = None
            
        def getMessage(self):
            return self.msg

    output = formatter.format(MockRecord())
    data = json.loads(output)
    
    assert data["level"] == "ERROR"
    assert "dummy_secret_key" not in data["message"]
    assert "***" in data["message"]
    assert data["module"] == "integration"

def test_integration_metrics_query_service():
    from services.metrics_collector import MetricsCollector
    
    trace_id = "integration_trace_query"
    # ダミーデータをインサート
    MetricsCollector.record("crawl", "success", 1.0, labels={"agency_id": 10}, trace_id=trace_id)
    MetricsCollector.record("crawl", "duration_ms", 120.5, labels={"agency_id": 10}, trace_id=trace_id)
    MetricsCollector.record("analysis", "success", 0.0, labels={"agency_id": 10, "error": "LLMTimeout"}, trace_id=trace_id)
    
    service = MetricsQueryService()
    summary = service.get_pipeline_summary(hours=1)
    
    assert summary["crawl"]["success"] >= 1
    assert summary["analysis"]["failed"] >= 1
    assert summary["crawl"]["duration_avg_ms"] > 0
    
    errors = service.get_error_distribution(hours=1)
    assert len(errors) >= 1
    assert any(e["error_type"] == "LLMTimeout" for e in errors)

def test_integration_health_checker():
    checker = HealthChecker()
    res = checker.check_all()
    
    assert "overall_status" in res
    assert "components" in res
    assert "Database" in res["components"]
    assert res["components"]["Database"]["status"] == "healthy"

def test_integration_prometheus_exporter():
    metrics_str = generate_prometheus_metrics(hours=1)
    
    assert "pipeline_stage_success_total" in metrics_str
    assert 'stage="crawl"' in metrics_str
    assert 'status="success"' in metrics_str

def test_integration_api_endpoints():
    # FastAPIの /metrics 関連エンドポイントが稼働しているか
    response_summary = client.get("/metrics/summary?hours=1")
    assert response_summary.status_code == 200
    data = response_summary.json()
    assert "crawl" in data
    
    response_health = client.get("/metrics/health")
    assert response_health.status_code == 200
    
    response_prometheus = client.get("/metrics?hours=1")
    assert response_prometheus.status_code == 200
    assert "pipeline_stage_success" in response_prometheus.text
