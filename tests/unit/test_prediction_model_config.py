import copy
from unittest.mock import patch

import pytest
import yaml

from services import prediction_model_config as config


@pytest.fixture(autouse=True)
def clear_cache():
    config.invalidate_config_cache()
    yield
    config.invalidate_config_cache()


@pytest.mark.parametrize("section,key,value", [
    ("tfidf", "max_features", 99),
    ("tfidf", "max_features", 50001),
    ("tfidf", "max_features", True),
    ("tfidf", "max_features", 1000.5),
    ("tfidf", "ngram_range", [3, 2]),
    ("tfidf", "ngram_range", [1, 6]),
    ("tfidf", "ngram_range", [True, 2]),
    ("tfidf", "ngram_range", "1,2"),
    ("tfidf", "analyzer", "exec"),
    ("tfidf", "stop_words", ["name@example.invalid"]),
    ("similarity", "default_threshold", float("nan")),
    ("similarity", "default_threshold", float("inf")),
    ("similarity", "default_threshold", 1.1),
    ("similarity", "default_n", 0),
    ("similarity", "cache_size", 1001),
    ("similarity", "time_window_months", -1),
])
def test_invalid_parameters_rejected(section, key, value):
    with pytest.raises(ValueError):
        config.validate_prediction_model_config({section: {key: value}})


@pytest.mark.parametrize("value", [-1, 2, float("nan"), float("inf"), True, "0.3"])
def test_invalid_weights_rejected(value):
    data = config._default_config()
    data["difficulty_scorer"]["weights"]["budget"] = value
    with pytest.raises(ValueError):
        config.validate_prediction_model_config(data)


@pytest.mark.parametrize("data", [None, [], "abc", {"unknown": {}}, {"tfidf": {"unknown": 1}},
                                      {"difficulty_scorer": {"weights": {"budget": 1}}}])
def test_invalid_schema_rejected(data):
    with pytest.raises(ValueError):
        config.validate_prediction_model_config(data)


def test_partial_config_normalized_without_mutation():
    data = {"tfidf": {"max_features": 8000}}
    original = copy.deepcopy(data)
    validated = config.validate_prediction_model_config(data)
    assert validated["tfidf"]["max_features"] == 8000
    assert validated["tfidf"]["ngram_range"] == [2, 5]
    assert data == original


def test_missing_file_uses_defaults(tmp_path):
    assert config.load_prediction_model_config(str(tmp_path / "missing.yaml")) == config._default_config()


@pytest.mark.parametrize("text", ["", "tfidf: [", "!!python/object:os.system {}", "tfidf: {max_features: 1}"])
def test_invalid_file_does_not_silently_use_defaults(tmp_path, text):
    path = tmp_path / "config.yaml"
    path.write_text(text)
    with pytest.raises(ValueError):
        config.load_prediction_model_config(str(path))


def test_atomic_save_refreshes_cache_and_returns_copies(tmp_path, monkeypatch):
    path = tmp_path / "config.yaml"
    monkeypatch.setenv("PREDICTION_MODEL_CONFIG_PATH", str(path))
    original = config.get_config()
    original["similarity"]["default_n"] = 44
    assert config.get_config()["similarity"]["default_n"] == 10
    config.save_prediction_model_config(original)
    assert yaml.safe_load(path.read_text())["similarity"]["default_n"] == 44
    assert config.get_config()["similarity"]["default_n"] == 44
    replacement = config._default_config()
    replacement["similarity"]["default_n"] = 25
    path.write_text(yaml.safe_dump(replacement))
    assert config.get_config()["similarity"]["default_n"] == 25
    assert config.reload_config()["similarity"]["default_n"] == 25


def test_failed_save_preserves_original_and_cleans_temp(tmp_path):
    path = tmp_path / "config.yaml"
    config.save_prediction_model_config({}, str(path))
    original = path.read_bytes()
    with patch.object(config.os, "replace", side_effect=OSError("disk error")):
        with pytest.raises(OSError):
            config.save_prediction_model_config({"similarity": {"default_n": 30}}, str(path))
    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [path]
    with pytest.raises(ValueError):
        config.save_prediction_model_config({"similarity": {"default_n": -1}}, str(path))
    assert path.read_bytes() == original


def test_cache_tracks_path_switches(tmp_path, monkeypatch):
    one, two = tmp_path / "one.yaml", tmp_path / "two.yaml"
    config.save_prediction_model_config({"similarity": {"default_n": 21}}, str(one))
    config.save_prediction_model_config({"similarity": {"default_n": 22}}, str(two))
    monkeypatch.setenv("PREDICTION_MODEL_CONFIG_PATH", str(one))
    assert config.get_config()["similarity"]["default_n"] == 21
    monkeypatch.setenv("PREDICTION_MODEL_CONFIG_PATH", str(two))
    assert config.get_config()["similarity"]["default_n"] == 22
