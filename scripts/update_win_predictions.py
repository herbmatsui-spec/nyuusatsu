import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

from sqlalchemy.orm import Session

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from database.models import Bid
from scripts.update_bid_difficulty_scores import _run_cli, _update_scores
from services.win_prediction_service import WinPredictionService


def update_win_predictions(
    session_factory: Callable[[], Session],
    *,
    months: int = 24,
    batch_size: int = 100,
    limit: int | None = None,
    dry_run: bool = True,
    now: datetime | None = None,
) -> dict[str, int]:
    def score_factory(session: Session) -> Callable[[Bid], float]:
        predictor = WinPredictionService(session, company_name=None, competitor_id=None)

        def score(bid: Bid) -> float:
            if predictor.company_name is not None or predictor.competitor_id is not None:
                raise ValueError("Shared win_prediction_score requires a non-personalized predictor")
            result = predictor.predict(bid)
            if (
                result.get("score_kind") != "uncalibrated_rule_based_score"
                or result.get("confidence", {}).get("calibrated") is not False
            ):
                raise ValueError("Shared win_prediction_score requires an uncalibrated market score")
            return result["win_rate"]

        return score

    return _update_scores(
        session_factory, score_factory, "win_prediction_score", 1.0,
        months=months, batch_size=batch_size, limit=limit, dry_run=dry_run, now=now,
    )


def main(argv: list[str] | None = None) -> int:
    return _run_cli(
        update_win_predictions,
        "Precompute generic non-personalized market scores (0-1), not calibrated win probabilities",
        argv,
    )


if __name__ == "__main__":
    sys.exit(main())
