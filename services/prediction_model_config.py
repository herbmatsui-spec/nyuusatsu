import copy
import math
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_CONFIG_PATH = str(_PROJECT_ROOT / "config" / "prediction_model.yaml")
_CONFIG_CACHE: Dict[str, Any] | None = None
_CACHE_KEY = None
_CONFIG_LOCK = threading.RLock()


def _default_config() -> Dict[str, Any]:
    return {
        "tfidf": {"max_features": 5000, "analyzer": "char_wb", "ngram_range": [2, 5], "stop_words": None},
        "similarity": {"default_n": 10, "default_threshold": 0.3, "time_window_months": 6, "cache_size": 100},
        "difficulty_scorer": {
            "weights": {"budget": 0.30, "qualifications": 0.20, "deadline": 0.20, "competition_rate": 0.15, "spec_length": 0.15},
            "params": {"budget_log_base": 10, "spec_length_log_base": 10, "default_competition_rate": 3.0, "default_days_to_deadline": 30},
        },
        "win_predictor": {
            "weights": {"company_win_rate": 0.40, "difficulty_inverse": 0.30, "agency_award_trend": 0.20, "qualification_match": 0.10},
            "params": {"default_company_win_rate": 0.15, "default_agency_award_rate": 0.30, "default_qualification_match": 0.50},
        },
    }


def _number(value, low, high, name, integer=False):
    if type(value) not in ((int,) if integer else (int, float)):
        raise ValueError(f"{name} must be a number")
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}")


def _merge(data, defaults, name="config"):
    if not isinstance(data, dict) or data.keys() - defaults.keys():
        raise ValueError(f"Invalid keys or mapping in {name}")
    result = copy.deepcopy(defaults)
    for key, value in data.items():
        if isinstance(defaults[key], dict):
            if key == "weights" and (not isinstance(value, dict) or value.keys() != defaults[key].keys()):
                raise ValueError(f"{name}.weights must contain every factor")
            result[key] = _merge(value, defaults[key], f"{name}.{key}")
        else:
            result[key] = copy.deepcopy(value)
    return result


def validate_prediction_model_config(data: Dict[str, Any]) -> Dict[str, Any]:
    result = _merge(data, _default_config())
    tfidf = result["tfidf"]
    _number(tfidf["max_features"], 100, 50000, "max_features", integer=True)
    if tfidf["analyzer"] not in ("word", "char", "char_wb"):
        raise ValueError("Invalid analyzer")
    ngrams = tfidf["ngram_range"]
    if not isinstance(ngrams, (list, tuple)) or len(ngrams) != 2:
        raise ValueError("ngram_range must contain two integers")
    for value in ngrams:
        _number(value, 1, 5, "ngram_range", integer=True)
    if ngrams[0] > ngrams[1]:
        raise ValueError("ngram_range must be ordered")
    tfidf["ngram_range"] = list(ngrams)
    if tfidf["stop_words"] not in (None, "japanese", "english"):
        raise ValueError("Unsupported stop_words")
    similarity = result["similarity"]
    for key, high in (("default_n", 100), ("time_window_months", 24), ("cache_size", 1000)):
        _number(similarity[key], 1, high, key, integer=True)
    _number(similarity["default_threshold"], 0, 1, "default_threshold")
    for section in ("difficulty_scorer", "win_predictor"):
        weights = result[section]["weights"]
        for key, value in weights.items():
            _number(value, 0, 1, key)
        if not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9, rel_tol=0):
            raise ValueError(f"{section} weights must sum to 100%")
    params = result["difficulty_scorer"]["params"]
    for key in ("budget_log_base", "spec_length_log_base"):
        _number(params[key], 1.01, 100, key)
    _number(params["default_competition_rate"], 1, 1000, "default_competition_rate")
    _number(params["default_days_to_deadline"], 1, 3650, "default_days_to_deadline")
    for key, value in result["win_predictor"]["params"].items():
        _number(value, 0, 1, key)
    return result


def config_path(path=None) -> Path:
    return Path(path or os.getenv("PREDICTION_MODEL_CONFIG_PATH", _DEFAULT_CONFIG_PATH)).absolute()


def load_prediction_model_config(path: str | None = None) -> Dict[str, Any]:
    try:
        with config_path(path).open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except FileNotFoundError:
        return _default_config()
    except yaml.YAMLError as exc:
        raise ValueError("Invalid prediction model YAML") from exc
    return validate_prediction_model_config(data)


def _cache_key(path):
    try:
        stat = path.stat()
        return str(path), stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size, stat.st_ino
    except FileNotFoundError:
        return str(path), None


def get_config(path: str | None = None) -> Dict[str, Any]:
    global _CONFIG_CACHE, _CACHE_KEY
    target = config_path(path)
    with _CONFIG_LOCK:
        key = _cache_key(target)
        if _CONFIG_CACHE is None or key != _CACHE_KEY:
            data = load_prediction_model_config(str(target))
            _CONFIG_CACHE, _CACHE_KEY = data, key
        return copy.deepcopy(_CONFIG_CACHE)


def invalidate_config_cache() -> None:
    global _CONFIG_CACHE, _CACHE_KEY
    with _CONFIG_LOCK:
        _CONFIG_CACHE, _CACHE_KEY = None, None


def reload_config(path: str | None = None) -> Dict[str, Any]:
    invalidate_config_cache()
    return get_config(path)


def save_prediction_model_config(data: Dict[str, Any], path: str | None = None) -> Dict[str, Any]:
    validated = validate_prediction_model_config(data)
    target = config_path(path)
    with _CONFIG_LOCK:
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, prefix=f".{target.name}.", delete=False) as handle:
                temporary = handle.name
                yaml.safe_dump(validated, handle, allow_unicode=True, sort_keys=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
            temporary = None
            invalidate_config_cache()
        finally:
            if temporary is not None:
                os.unlink(temporary)
    return copy.deepcopy(validated)
