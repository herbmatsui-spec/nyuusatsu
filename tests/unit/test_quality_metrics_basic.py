"""品質メトリクスサービスの基本テスト"""
def test_import():
    """インポートできるかテスト"""
    from services.quality_metrics_service import QualityMetricsService
    assert QualityMetricsService is not None