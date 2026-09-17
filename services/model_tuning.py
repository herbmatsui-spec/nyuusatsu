from __future__ import annotations

import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Mapping

from database.models.user import User
from services.auth_service import AuthService
from services.prediction_model_config import (
    config_path,
    load_prediction_model_config,
    save_prediction_model_config,
    validate_prediction_model_config,
)
from utils.session_manager import get_session_manager

TUNING_RESOURCE = "prediction_model"
TUNING_ACTION = "write"
REBUILD_ACTION = "rebuild"
_PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TuningValidationError(ValueError):
    pass


class TuningPermissionError(PermissionError):
    pass


class ModelTuningHelper:
    def __init__(self, db_session, config_path: str | None = None):
        self.db_session = db_session
        self.config_path = config_path or str(_default_path())
        self._current_session_state = self._streamlit_state

    @staticmethod
    def _streamlit_state():
        import streamlit as st
        return st.session_state

    def load(self) -> Dict[str, Any]:
        return load_prediction_model_config(self.config_path)

    def can_access(self, action=TUNING_ACTION) -> bool:
        try:
            self._authorize(None, action)
            return True
        except TuningPermissionError:
            return False

    def save(self, config: Mapping[str, Any], user=None) -> Dict[str, Any]:
        self._authorize(user, TUNING_ACTION)
        return save_prediction_model_config(dict(config), self.config_path)

    def weights_from_sliders(self, section: str, values: Mapping[str, float]) -> Dict[str, float]:
        from services.prediction_model_config import _default_config
        defaults = _default_config()
        if section not in ("difficulty_scorer", "win_predictor") or set(values) != set(defaults[section]["weights"]):
            raise TuningValidationError("Sliders must cover every factor")
        for value in values.values():
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 100:
                raise TuningValidationError("Slider values must be finite percentages")
        if not math.isclose(sum(values.values()), 100, abs_tol=1e-9, rel_tol=0):
            raise TuningValidationError("Sliders must sum to 100%")
        return {key: value / 100 for key, value in values.items()}

    def vector_params(self, max_features, ngram_lo, ngram_hi, analyzer="char_wb", stop_words=None):
        return validate_prediction_model_config({"tfidf": {
            "max_features": max_features, "ngram_range": [ngram_lo, ngram_hi],
            "analyzer": analyzer, "stop_words": stop_words,
        }})["tfidf"]

    def trigger_vector_rebuild(self, user=None, months: int | None = None) -> int:
        self._authorize(user, REBUILD_ACTION)
        config = self.load()
        months = config["similarity"]["time_window_months"] if months is None else months
        validate_prediction_model_config({"similarity": {"time_window_months": months}})
        environment = dict(os.environ, PREDICTION_MODEL_CONFIG_PATH=str(config_path(self.config_path)))
        result = subprocess.run(
            [sys.executable, str(_PROJECT_ROOT / "scripts" / "build_specification_vectors.py"),
             "--months", str(months), "--max-docs", "10000"],
            cwd=str(_PROJECT_ROOT), env=environment, shell=False,
            capture_output=True, text=True, timeout=300, check=False,
        )
        if result.returncode != 0:
            raise RuntimeError("Vector rebuild failed; no successful rebuild reported")
        return result.returncode

    def _authorize(self, user, action: str) -> None:
        state = self._current_session_state()
        if not state or state.get("authenticated") is not True:
            raise TuningPermissionError("Authentication required")
        session_id = state.get("session_id")
        if not isinstance(session_id, str):
            raise TuningPermissionError("Active session required")
        username = get_session_manager().get_username(session_id)
        if not username or username != state.get("username"):
            raise TuningPermissionError("Session expired or user mismatch")
        with self.db_session.no_autoflush:
            current = self.db_session.query(User).populate_existing().filter(
                User.username == username, User.is_active.is_(True)
            ).first()
            if current is None or (user is not None and current.id != user.id):
                raise TuningPermissionError("Active session user required")
            if not AuthService(self.db_session).has_permission(current, action, TUNING_RESOURCE):
                raise TuningPermissionError(f"Missing permission {TUNING_RESOURCE}:{action}")


def _default_path():
    return config_path()


def render_model_tuning(db_session):
    import streamlit as st

    helper = ModelTuningHelper(db_session)
    if not helper.can_access():
        st.warning("予測モデル設定には認証済みの管理権限が必要です。")
        return
    st.subheader("予測モデルチューニング")
    try:
        config = helper.load()
    except (ValueError, OSError):
        st.error("モデル設定が不正です。設定ファイルを確認してください。")
        return
    with st.form("prediction_model_tuning"):
        slider_values = {}
        for section, title in (("difficulty_scorer", "難易度"), ("win_predictor", "勝率")):
            st.write(title)
            slider_values[section] = {
                key: st.slider(key, 0, 100, round(value * 100), key=f"tuning_{section}_{key}")
                for key, value in config[section]["weights"].items()
            }
            st.write(f"合計: {sum(slider_values[section].values())}% (100%必須)")
        default_n = st.number_input("類似案件件数", 1, 100, config["similarity"]["default_n"])
        threshold = st.slider("類似度しきい値", 0.0, 1.0, float(config["similarity"]["default_threshold"]))
        features = st.number_input("TF-IDF max_features", 100, 50000, config["tfidf"]["max_features"])
        ngrams = st.slider("TF-IDF ngram_range", 1, 5, tuple(config["tfidf"]["ngram_range"]))
        if st.form_submit_button("モデル設定を保存"):
            try:
                for section, values in slider_values.items():
                    config[section]["weights"] = helper.weights_from_sliders(section, values)
                config["similarity"].update(default_n=default_n, default_threshold=threshold)
                config["tfidf"].update(max_features=features, ngram_range=list(ngrams))
                helper.save(config)
                st.success("設定を保存しました。TF-IDF変更後は再構築を実行してください。")
            except (ValueError, PermissionError, OSError) as exc:
                st.error(str(exc))
    if helper.can_access(REBUILD_ACTION) and st.button("仕様書ベクトルを再構築 (最大10000件)"):
        try:
            with st.spinner("ベクトル再構築中"):
                helper.trigger_vector_rebuild()
            st.success("ベクトル再構築が完了しました。")
        except (ValueError, PermissionError, OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            st.error(str(exc))
