"""Unit tests for crawler.utils.selector_loader (Step 25 regression tests)."""
from __future__ import annotations

import pytest
from pathlib import Path

from crawler.utils.selector_loader import (
    load_selectors,
    get_selectors,
    get_page_config,
    get_version,
    DEFAULT_SELECTOR_CONFIG,
)


def test_load_default_config_has_version():
    config = load_selectors()
    assert get_version(config) == "2026.09"
    assert "pages" in config


def test_load_selectors_page_type_filters():
    form = load_selectors(page_type="search_form")
    assert "query" in form
    assert "start_date" in form


def test_load_selectors_rejects_missing_version(tmp_path):
    import yaml as _yaml
    bad = tmp_path / "bad.yaml"
    bad.write_text("pages: {}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="version is missing"):
        load_selectors(path=bad)


def test_load_selectors_rejects_version_mismatch():
    with pytest.raises(ValueError, match="version mismatch"):
        load_selectors(expected_version="1900.01")


def test_get_selectors_flattens_fallback_list():
    config = load_selectors()
    candidates = get_selectors(config, "search_form", "start_date")
    assert candidates == config["pages"]["search_form"]["start_date"]
    assert isinstance(candidates, list) and len(candidates) >= 3


def test_get_selectors_returns_empty_for_unknown_field():
    config = load_selectors()
    assert get_selectors(config, "search_form", "nonexistent") == []


def test_get_page_config_returns_empty_for_unknown_page():
    assert get_page_config({}, "unknown") == {}


def test_default_config_path_exists():
    assert DEFAULT_SELECTOR_CONFIG.exists()
