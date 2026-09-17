from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models import Bid, CompanyProfile
from scripts import update_bid_difficulty_scores as difficulty
from scripts import update_win_predictions as market
from services.bid_difficulty_scorer import BidDifficultyScorer
from services.win_prediction_service import WinPredictionService

NOW = datetime(2026, 9, 17, 12)


@pytest.fixture
def sessions():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    yield factory
    engine.dispose()


@pytest.fixture(params=["difficulty", "market"])
def job(request):
    if request.param == "difficulty":
        return difficulty, difficulty.update_bid_difficulty_scores, "bid_difficulty_score", BidDifficultyScorer, "score", 62.5
    return market, market.update_win_predictions, "win_prediction_score", WinPredictionService, "predict", 0.375


def seed(sessions, dates):
    with sessions() as session:
        session.add_all([
            Bid(
                id=index, filename=f"bid_{index}.pdf", announcement_date=announced,
                analyzed_at=NOW, current_status="入札済", created_at=NOW, updated_at=NOW,
                qualifications="全省庁統一資格 A", budget_amount=1_000_000,
                bid_difficulty_score=99.0, win_prediction_score=0.99,
            )
            for index, announced in enumerate(dates, 1)
        ])
        session.commit()


def result(job, value=None):
    value = job[5] if value is None else value
    if job[4] == "score":
        return {"score": value}
    return {
        "win_rate": value, "score_kind": "uncalibrated_rule_based_score",
        "confidence": {"calibrated": False},
    }


def values(sessions, column):
    with sessions() as session:
        return dict(session.query(Bid.id, getattr(Bid, column)).order_by(Bid.id).all())


def test_default_window_batches_and_only_owned_column(sessions, job, monkeypatch):
    start = NOW.replace(year=2024)
    seed(sessions, [start - timedelta(microseconds=1), start, NOW, NOW + timedelta(microseconds=1), None, NOW - timedelta(days=1)])
    scored_ids = []

    def score(self, bid):
        scored_ids.append(bid.id)
        return result(job)

    monkeypatch.setattr(job[3], job[4], score)
    counts = job[1](sessions, batch_size=2, dry_run=False, now=NOW)
    assert counts == {"scanned": 3, "changed": 3, "updated": 3, "batches": 2}
    assert scored_ids == [2, 3, 6]
    old = 99.0 if job[2] == "bid_difficulty_score" else 0.99
    assert values(sessions, job[2]) == {1: old, 2: job[5], 3: job[5], 4: old, 5: old, 6: job[5]}
    other = "win_prediction_score" if job[2] == "bid_difficulty_score" else "bid_difficulty_score"
    assert set(values(sessions, other).values()) == {0.99 if other == "win_prediction_score" else 99.0}
    with sessions() as session:
        assert all(bid.updated_at == NOW for bid in session.query(Bid).all())
    assert job[1](sessions, dry_run=False, now=NOW)["updated"] == 0


@pytest.mark.parametrize("explicit", [False, True])
def test_dry_run_never_emits_writes_or_commits(sessions, job, monkeypatch, explicit):
    seed(sessions, [NOW] * 3)
    monkeypatch.setattr(job[3], job[4], Mock(return_value=result(job)))
    statements = []
    commits = []
    event.listen(sessions.kw["bind"], "before_cursor_execute", lambda conn, cursor, statement, parameters, context, many: statements.append(statement))
    event.listen(sessions.kw["bind"], "commit", lambda conn: commits.append(True))
    options = {"dry_run": True} if explicit else {}
    counts = job[1](sessions, batch_size=2, now=NOW, **options)
    assert counts == {"scanned": 3, "changed": 3, "updated": 0, "batches": 2}
    assert not commits
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in statements)
    assert set(values(sessions, job[2]).values()) == {99.0 if job[4] == "score" else 0.99}


def test_limit_and_calendar_month_end(sessions, job, monkeypatch):
    seed(sessions, [datetime(2024, 2, 28, 12), datetime(2024, 2, 29, 12), datetime(2024, 3, 1), datetime(2024, 3, 2)])
    scored_ids = []

    def score(self, bid):
        scored_ids.append(bid.id)
        return result(job)

    monkeypatch.setattr(job[3], job[4], score)
    counts = job[1](sessions, months=1, batch_size=1, limit=2, now=datetime(2024, 3, 31, 12, tzinfo=timezone.utc))
    assert counts["scanned"] == 2
    assert counts["batches"] == 2
    assert scored_ids == [2, 3]


def test_empty_database(sessions, job):
    assert job[1](sessions, now=NOW) == {"scanned": 0, "changed": 0, "updated": 0, "batches": 0}


@pytest.mark.parametrize("options", [
    {"months": 0}, {"months": -1}, {"months": 121}, {"months": 2.5},
    {"batch_size": 0}, {"batch_size": 1001}, {"batch_size": True},
    {"limit": 0}, {"limit": -1}, {"limit": 1.5},
])
def test_invalid_options_do_not_open_session(job, options):
    factory = Mock()
    with pytest.raises(ValueError):
        job[1](factory, **options)
    factory.assert_not_called()


@pytest.mark.parametrize("failure", ["scoring", "database", "commit"])
def test_failed_batch_rolls_back_but_preserves_previous_batch(sessions, job, monkeypatch, failure):
    seed(sessions, [NOW] * 4)

    def score(self, bid):
        if failure == "scoring" and bid.id == 4:
            raise RuntimeError("scoring failed")
        return result(job)

    monkeypatch.setattr(job[3], job[4], score)
    calls = []

    def fail_update(conn, cursor, statement, parameters, context, many):
        if statement.startswith("UPDATE"):
            calls.append(True)
            if len(calls) == 2:
                raise RuntimeError("database failed")

    def fail_commit(session):
        calls.append(True)
        if len(calls) == 2:
            raise RuntimeError("commit failed")

    if failure == "database":
        event.listen(sessions.kw["bind"], "before_cursor_execute", fail_update)
    elif failure == "commit":
        event.listen(sessions, "before_commit", fail_commit)
    with pytest.raises(RuntimeError, match="failed"):
        job[1](sessions, batch_size=2, dry_run=False, now=NOW)
    old = 99.0 if job[4] == "score" else 0.99
    assert values(sessions, job[2]) == {1: job[5], 2: job[5], 3: old, 4: old}


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -0.1, 101])
def test_invalid_scores_reject_whole_batch(sessions, job, monkeypatch, invalid):
    seed(sessions, [NOW] * 2)
    monkeypatch.setattr(job[3], job[4], Mock(side_effect=[result(job), result(job, invalid)]))
    with pytest.raises(ValueError, match="Invalid"):
        job[1](sessions, dry_run=False, now=NOW)
    assert set(values(sessions, job[2]).values()) == {99.0 if job[4] == "score" else 0.99}


def test_upper_id_snapshot_excludes_new_bids(sessions, job, monkeypatch):
    seed(sessions, [NOW] * 2)
    inserted = []

    def insert_bid(session):
        if not inserted:
            inserted.append(True)
            with sessions() as writer:
                writer.add(Bid(id=3, filename="new.pdf", announcement_date=NOW, analyzed_at=NOW, current_status="入札済", created_at=NOW, updated_at=NOW))
                writer.commit()

    event.listen(sessions, "after_commit", insert_bid)
    scorer = Mock(return_value=result(job))
    monkeypatch.setattr(job[3], job[4], scorer)
    counts = job[1](sessions, dry_run=False, batch_size=1, now=NOW)
    assert counts["scanned"] == 2
    assert values(sessions, job[2])[3] is None


def test_real_scoring_matches_identity_free_apis(sessions):
    seed(sessions, [NOW])
    with sessions() as session:
        session.add(CompanyProfile(name="自社", unified_qualification_grade="A", unified_qualification_expire=NOW + timedelta(days=365), created_at=NOW, updated_at=NOW))
        session.commit()
        bid = session.get(Bid, 1)
        expected_difficulty = BidDifficultyScorer(session).score(bid)["score"]
        generic = WinPredictionService(session, company_name=None, competitor_id=None).predict(bid)
        assert generic["confidence"]["qualification_status"] == "missing_profile"
        assert generic["confidence"]["calibrated"] is False
    difficulty.update_bid_difficulty_scores(sessions, dry_run=False, now=NOW)
    market.update_win_predictions(sessions, dry_run=False, now=NOW)
    assert values(sessions, "bid_difficulty_score")[1] == expected_difficulty
    assert values(sessions, "win_prediction_score")[1] == generic["win_rate"]
    with sessions() as session:
        profile = session.query(CompanyProfile).one()
        profile.unified_qualification_grade = "D"
        profile.unified_qualification_expire = NOW - timedelta(days=365)
        session.commit()
    assert market.update_win_predictions(sessions, dry_run=False, now=NOW)["updated"] == 0


@pytest.mark.parametrize("identity", ["company_name", "competitor_id"])
def test_market_rejects_personalized_predictor(sessions, monkeypatch, identity):
    seed(sessions, [NOW])
    predictor = Mock(company_name=None, competitor_id=None)
    setattr(predictor, identity, "company" if identity == "company_name" else 1)
    constructor = Mock(return_value=predictor)
    monkeypatch.setattr(market, "WinPredictionService", constructor)
    with pytest.raises(ValueError, match="non-personalized"):
        market.update_win_predictions(sessions, dry_run=False, now=NOW)
    assert constructor.call_args.kwargs == {"company_name": None, "competitor_id": None}
    predictor.predict.assert_not_called()
    assert values(sessions, "win_prediction_score")[1] == 0.99


@pytest.mark.parametrize("prediction", [
    {"win_rate": 0.2},
    {"win_rate": 0.2, "score_kind": "probability", "confidence": {"calibrated": False}},
    {"win_rate": 0.2, "score_kind": "uncalibrated_rule_based_score", "confidence": {"calibrated": True}},
    {"win_rate": 1.1, "score_kind": "uncalibrated_rule_based_score", "confidence": {"calibrated": False}},
])
def test_market_rejects_wrong_semantics_and_range(sessions, monkeypatch, prediction):
    seed(sessions, [NOW])
    monkeypatch.setattr(WinPredictionService, "predict", Mock(return_value=prediction))
    with pytest.raises(ValueError):
        market.update_win_predictions(sessions, dry_run=False, now=NOW)
    assert values(sessions, "win_prediction_score")[1] == 0.99


@pytest.mark.parametrize("args,expected", [([], True), (["--dry-run"], True), (["--apply"], False)])
def test_cli_modes(job, monkeypatch, args, expected):
    runner = Mock(return_value={"scanned": 0})
    monkeypatch.setattr(job[0], job[1].__name__, runner)
    assert job[0].main(args) == 0
    assert runner.call_args.kwargs == {"months": 24, "batch_size": 100, "limit": None, "dry_run": expected}


@pytest.mark.parametrize("args", [["--months", "0"], ["--batch-size", "0"], ["--limit", "0"], ["--apply", "--dry-run"], ["--company-name", "自社"], ["--competitor-id", "1"]])
def test_cli_invalid_options_do_not_run_job(job, monkeypatch, args):
    runner = Mock()
    monkeypatch.setattr(job[0], job[1].__name__, runner)
    with pytest.raises(SystemExit) as exc:
        job[0].main(args)
    assert exc.value.code == 2
    runner.assert_not_called()


def test_cli_failure_exit_status(job, monkeypatch):
    monkeypatch.setattr(job[0], job[1].__name__, Mock(side_effect=RuntimeError("failed")))
    assert job[0].main([]) == 1
