from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.base import Base
from services.auth_service import AuthService
from database.models.role import Role, UserRole
from services.feedback_logger import FeedbackLogger
from services.model_tuning import (
    ModelTuningHelper,
    TuningPermissionError,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def admin_user(db_session):
    auth = AuthService(db_session)
    user = auth.create_user("tune-admin", "password")
    now = datetime.now(timezone.utc)
    role = Role(name="ml_admin", permissions_json='["prediction_model:write", "prediction_model:rebuild"]', created_at=now)
    db_session.add(role)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=role.id, created_at=now))
    db_session.commit()
    return user


@pytest.fixture
def plain_user(db_session):
    auth = AuthService(db_session)
    user = auth.create_user("plain", "password")
    now = datetime.now(timezone.utc)
    role = Role(name="viewer", permissions_json='["bid:read"]', created_at=now)
    db_session.add(role)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=role.id, created_at=now))
    db_session.commit()
    return user


@pytest.fixture
def helper(tmp_path, db_session):
    return ModelTuningHelper(
        db_session,
        config_path=str(tmp_path / "prediction_model.yaml"),
    )


@pytest.fixture
def feedback(tmp_path):
    return FeedbackLogger(str(tmp_path / "feedback.sqlite3"))


def _attach_session_state(monkeypatch, helper, authenticated=True, username="tune-admin", session_id="sid-1"):
    state = {"authenticated": authenticated, "username": username, "session_id": session_id}
    helper._current_session_state = lambda: state


def _grant_active_session(monkeypatch, helper, username="tune-admin"):
    from utils.session_manager import get_session_manager

    manager = get_session_manager()
    session_id = manager.create_session(username)
    _attach_session_state(monkeypatch, helper, authenticated=True, username=username, session_id=session_id)
    return session_id


def test_log_feedback_validates_input(feedback):
    with pytest.raises(ValueError):
        feedback.log_feedback("unknown", 1, 1)
    with pytest.raises(ValueError):
        feedback.log_feedback("difficulty", "x", 1)
    with pytest.raises(ValueError):
        feedback.log_feedback("difficulty", 1, 0)
    with pytest.raises(ValueError):
        feedback.log_feedback("difficulty", 1, 1, similar_bid_id="x")


def test_log_feedback_and_weekly_aggregation(feedback, monkeypatch):
    now = datetime.now(timezone.utc)
    monkeypatch.setattr("services.feedback_logger._utcnow", lambda: now)
    feedback.log_feedback("difficulty", 1, 1)
    feedback.log_feedback("difficulty", 2, -1)
    monkeypatch.setattr("services.feedback_logger._utcnow", lambda: now - timedelta(days=8))
    feedback.log_feedback("win_prediction", 3, 1)
    monkeypatch.setattr("services.feedback_logger._utcnow", lambda: now)
    buckets = feedback.aggregate_weekly()
    by_type = {b["feedback_type"]: b for b in buckets}
    assert by_type["difficulty"]["total"] == 2
    assert by_type["difficulty"]["positive_rate"] == pytest.approx(0.5)
    assert by_type["win_prediction"]["week_start"] < by_type["difficulty"]["week_start"]
    filtered = feedback.aggregate_weekly(feedback_type="win_prediction")
    assert [b["feedback_type"] for b in filtered] == ["win_prediction"]
    assert set(buckets[0]) == {"week_start", "feedback_type", "total", "positive", "negative", "positive_rate"}


def test_feedback_store_separate_from_bids(tmp_path, feedback):
    feedback.log_feedback("similarity", 7, 1, similar_bid_id=8)
    assert not any(p.name == "bids_system.db" for p in tmp_path.iterdir())
    assert (tmp_path / "feedback.sqlite3").exists()


def test_unauthorized_user_rejected_for_save(helper, admin_user, plain_user, monkeypatch):
    _grant_active_session(monkeypatch, helper, username="plain")
    config = helper.load()
    with pytest.raises(PermissionError):
        helper.save(config, user=plain_user)


def test_save_requires_authentication(helper, admin_user, monkeypatch):
    _attach_session_state(monkeypatch, helper, authenticated=False)
    config = helper.load()
    with pytest.raises(PermissionError):
        helper.save(config, user=admin_user)


def test_stale_session_rejected(helper, admin_user, monkeypatch):
    _attach_session_state(monkeypatch, helper, authenticated=True, session_id="expired")
    config = helper.load()
    with pytest.raises(PermissionError):
        helper.save(config, user=admin_user)


def test_authorized_save_roundtrip(helper, admin_user, monkeypatch):
    _grant_active_session(monkeypatch, helper)
    config = helper.load()
    config["similarity"]["default_n"] = 15
    saved = helper.save(config, user=admin_user)
    assert saved["similarity"]["default_n"] == 15
    assert helper.load()["similarity"]["default_n"] == 15


def test_save_rejects_invalid_config(helper, admin_user, monkeypatch):
    _grant_active_session(monkeypatch, helper)
    config = helper.load()
    config["difficulty_scorer"]["weights"]["budget"] = 0.9
    with pytest.raises(ValueError):
        helper.save(config, user=admin_user)


def test_slider_group_normalizes_to_sum_100(helper):
    values = {"budget": 30, "qualifications": 20, "deadline": 20, "competition_rate": 15, "spec_length": 15}
    weights = helper.weights_from_sliders("difficulty_scorer", values)
    assert sum(weights.values()) == pytest.approx(1.0)
    assert weights == {"budget": 0.30, "qualifications": 0.20, "deadline": 0.20, "competition_rate": 0.15, "spec_length": 0.15}
    with pytest.raises(ValueError):
        helper.weights_from_sliders("difficulty_scorer", {"budget": 30})
    with pytest.raises(ValueError):
        helper.weights_from_sliders("win_predictor", {"company_win_rate": 40, "difficulty_inverse": 30, "agency_award_trend": 20, "qualification_match": 20})


def test_bounded_vector_parameters(helper):
    with pytest.raises(ValueError):
        helper.vector_params(max_features=99, ngram_lo=2, ngram_hi=5)
    with pytest.raises(ValueError):
        helper.vector_params(max_features=50001, ngram_lo=2, ngram_hi=5)
    with pytest.raises(ValueError):
        helper.vector_params(max_features=5000, ngram_lo=4, ngram_hi=2)
    with pytest.raises(ValueError):
        helper.vector_params(max_features=5000, ngram_lo=0, ngram_hi=9)
    params = helper.vector_params(max_features=8000, ngram_lo=2, ngram_hi=5)
    assert params["max_features"] == 8000
    assert params["ngram_range"] == [2, 5]


def test_rebuild_requires_permission(helper, admin_user, plain_user, monkeypatch):
    _grant_active_session(monkeypatch, helper)
    with pytest.raises(PermissionError):
        helper.trigger_vector_rebuild(user=plain_user)


def test_rebuild_uses_fixed_argv(helper, admin_user, monkeypatch):
    _grant_active_session(monkeypatch, helper)
    rebuild = MagicMock(return_value=MagicMock(returncode=0))
    monkeypatch.setattr("services.model_tuning.subprocess.run", rebuild)
    assert helper.trigger_vector_rebuild(user=admin_user) == 0
    args, kwargs = rebuild.call_args
    assert args[0][-4:] == ["--months", "6", "--max-docs", "10000"]
    assert kwargs["shell"] is False
    assert kwargs["timeout"] == 300
    assert kwargs["env"]["PREDICTION_MODEL_CONFIG_PATH"] == helper.config_path
    rebuild.reset_mock()
    with pytest.raises(ValueError):
        helper.trigger_vector_rebuild(user=admin_user, months="6; touch /tmp/unsafe")
    rebuild.assert_not_called()


def test_rebuild_without_session_state(helper, admin_user, monkeypatch):
    helper._current_session_state = lambda: {"authenticated": True, "username": "tune-admin", "session_id": None}
    with pytest.raises(TuningPermissionError):
        helper.trigger_vector_rebuild(user=admin_user)


@pytest.mark.parametrize("rating", [True, False, 1.0, "1", None])
def test_feedback_rejects_noninteger_ratings(feedback, rating):
    with pytest.raises(ValueError):
        feedback.log_feedback("difficulty", 1, rating)


def test_feedback_append_only_and_no_pii(feedback):
    import sqlite3
    from contextlib import closing

    first = feedback.log_feedback("difficulty", 1, 1)
    second = feedback.log_feedback("difficulty", 1, -1)
    assert second > first
    with closing(sqlite3.connect(feedback.path)) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(prediction_feedback)")}
        assert columns == {"id", "feedback_type", "bid_id", "rating", "similar_bid_id", "created_at"}
        for statement in ("UPDATE prediction_feedback SET rating=1", "DELETE FROM prediction_feedback"):
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                connection.execute(statement)
    assert feedback.aggregate_weekly()[0]["total"] == 2


def test_missing_feedback_store_not_created(feedback):
    from pathlib import Path

    assert feedback.aggregate_weekly() == []
    assert not Path(feedback.path).exists()


@pytest.mark.parametrize("method", ["save", "trigger_vector_rebuild"])
def test_permissions_rechecked_after_revocation(helper, admin_user, monkeypatch, method):
    _grant_active_session(monkeypatch, helper)
    assert helper.can_access()
    role = helper.db_session.query(Role).filter_by(name="ml_admin").one()
    role.permissions_json = "[]"
    helper.db_session.commit()
    subprocess_mock = MagicMock()
    monkeypatch.setattr("services.model_tuning.subprocess.run", subprocess_mock)
    with pytest.raises(PermissionError):
        if method == "save":
            helper.save(helper.load())
        else:
            helper.trigger_vector_rebuild()
    subprocess_mock.assert_not_called()


def test_registered_session_identity_cannot_be_spoofed(helper, admin_user, plain_user, monkeypatch):
    session_id = _grant_active_session(monkeypatch, helper, username="plain")
    _attach_session_state(monkeypatch, helper, username="tune-admin", session_id=session_id)
    assert helper.can_access() is False
    with pytest.raises(PermissionError):
        helper.save(helper.load(), user=admin_user)


def test_inactive_user_rejected(helper, admin_user, monkeypatch):
    _grant_active_session(monkeypatch, helper)
    admin_user.is_active = False
    helper.db_session.commit()
    with pytest.raises(PermissionError):
        helper.save(helper.load())


def test_rebuild_failure_propagates(helper, admin_user, monkeypatch):
    _grant_active_session(monkeypatch, helper)
    monkeypatch.setattr("services.model_tuning.subprocess.run", MagicMock(return_value=MagicMock(returncode=1)))
    with pytest.raises(RuntimeError, match="rebuild failed"):
        helper.trigger_vector_rebuild()


def test_missing_session_state_preserves_original_config(helper, admin_user, monkeypatch):
    from pathlib import Path
    from services.prediction_model_config import save_prediction_model_config

    original = helper.load()
    save_prediction_model_config(original, helper.config_path)
    before = Path(helper.config_path).read_bytes()
    proposed = helper.load()
    proposed["similarity"]["default_n"] = 25
    helper._current_session_state = lambda: None
    with pytest.raises(TuningPermissionError, match="Authentication required"):
        helper.save(proposed, user=admin_user)
    assert Path(helper.config_path).read_bytes() == before
    assert helper.load() == original
    assert proposed["similarity"]["default_n"] == 25


def test_render_hides_controls_for_unauthenticated(helper, monkeypatch):
    from services.model_tuning import render_model_tuning

    fake_st = MagicMock()
    fake_st.session_state = {}
    monkeypatch.setitem(__import__("sys").modules, "streamlit", fake_st)
    render_model_tuning(helper.db_session)
    fake_st.form.assert_not_called()
    fake_st.button.assert_not_called()


def test_render_authorized_sliders_reject_bad_sum(helper, admin_user, monkeypatch):
    from pathlib import Path
    from services.model_tuning import render_model_tuning

    _grant_active_session(monkeypatch, helper)
    fake_st = MagicMock()
    fake_st.slider.side_effect = lambda label, low, high, value, **kwargs: value + 1 if label == "budget" else value
    fake_st.number_input.side_effect = lambda label, low, high, value: value
    fake_st.form_submit_button.return_value = True
    fake_st.button.return_value = False
    monkeypatch.setitem(__import__("sys").modules, "streamlit", fake_st)
    monkeypatch.setattr("services.model_tuning.ModelTuningHelper", lambda session: helper)
    render_model_tuning(helper.db_session)
    assert not Path(helper.config_path).exists()
    fake_st.error.assert_called_once()
    assert "100%" in fake_st.error.call_args.args[0]
