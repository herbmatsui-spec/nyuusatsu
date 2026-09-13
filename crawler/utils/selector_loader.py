"""GEPS セレクタの集約ロード + バージョン管理 (Step 17/18/21)。

`crawler/config/geps_selectors.yaml` を1度だけパースし、バージョン照合と
ページ／フィールド単位の候補セレクタ取得を提供する。クローラはこのモジュールを
経由してセレクタを取得することで、YAML構造の変更を1箇所に閉じ込める。

Step 21 のフォールバック: フィールド値はリスト（候補）形式を許容し、
`get_selectors()` が平坦化した優先順位付き候補リストを返す。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Optional, Union

import yaml

logger = logging.getLogger(__name__)

DEFAULT_SELECTOR_CONFIG = Path(__file__).resolve().parents[1] / "config" / "geps_selectors.yaml"


def get_version(config: dict) -> Optional[str]:
    """YAML から selectors_version を取得する。"""
    return config.get("selectors_version")


def load_selectors(
    path: Optional[Union[str, Path]] = None,
    expected_version: Optional[str] = None,
    page_type: Optional[str] = None,
) -> dict:
    """セレクタYAMLをロードし、バージョン照合を行う。

    Args:
        path: YAML ファイルパス。省略時は `crawler/config/geps_selectors.yaml`。
        expected_version: 期待するセレクタバージョン。不一致なら ValueError。
        page_type: 指定時は `pages[page_type]` サブ辞書を返す。

    Returns:
        フル設定 dict (page_type 指定なし) またはページサブ辞書。
    """
    selector_path = Path(path) if path else DEFAULT_SELECTOR_CONFIG
    with selector_path.open(encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}

    version = get_version(config)
    if not version:
        raise ValueError(f"Selector version is missing: {selector_path}")
    if expected_version and str(version) != str(expected_version):
        raise ValueError(
            f"Selector version mismatch: expected {expected_version}, got {version}"
        )
    logger.info("Loaded selector config v%s from %s", version, selector_path)

    if page_type:
        return config.get("pages", {}).get(page_type, {})
    return config


def _flatten(value: Any) -> List[str]:
    """セレクタ値（str / list / ネストリスト）を平坦化して候補リストを返す。"""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: List[str] = []
        for item in value:
            out.extend(_flatten(item))
        return out
    return []


def get_selectors(config: dict, page_type: str, field: str) -> List[str]:
    """ページ／フィールドの候補セレクタリストを優先順位付きで返す (Step 21)。"""
    value = config.get("pages", {}).get(page_type, {}).get(field, [])
    return _flatten(value)


def get_page_config(config: dict, page_type: str) -> dict:
    """指定ページのサブ辞書を安全に取得する。"""
    return config.get("pages", {}).get(page_type, {}) or {}
