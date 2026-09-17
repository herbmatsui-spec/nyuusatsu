from datetime import datetime
from unittest.mock import MagicMock

from database.models import Bid
from services.prediction_dashboard_service import PredictionDashboardService


def test_personalized_prediction_ignores_shared_market_cache():
    session = MagicMock()
    session.get.return_value = Bid(
        id=1,
        filename="sample.pdf",
        announcement_date=datetime(2026, 9, 1),
        bid_difficulty_score=99.0,
        win_prediction_score=0.99,
    )
    service = PredictionDashboardService(session, company_name="テスト株式会社")
    service.difficulty_scorer = MagicMock()
    service.difficulty_scorer.score.return_value = {
        "score": 40.0,
        "breakdown": {"budget": 0.5},
        "weights": {"budget": 1.0},
    }
    service.win_predictor = MagicMock()
    service.win_predictor.predict.return_value = {
        "win_rate": 0.2,
        "breakdown": {"company_win_rate": 0.2},
        "weights": {"company_win_rate": 1.0},
        "difficulty_score": 40.0,
    }

    result = service.get_bid_prediction(1)

    assert result["win_prediction"]["win_rate"] == 0.2
    assert result["win_prediction"]["breakdown"] == {"company_win_rate": 0.2}
    assert result["difficulty"]["score"] == 40.0
    assert result["from_cache"] is False
    service.win_predictor.predict.assert_called_once()
