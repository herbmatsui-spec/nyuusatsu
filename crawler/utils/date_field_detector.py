"""日付入力フィールド自動検出ユーティリティ (Step 22)。

Playwright ``page`` に対し、設定済みセレクタを優先して検出し、
見つからなければ CSS ヒューリスティックでフォールバックする。
start_date には候補の最初を、end_date には最後を返す。
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, List, Optional, Sequence

logger = logging.getLogger(__name__)

DEFAULT_DATE_HEURISTIC: List[str] = [
    'input.datepicker',
    'input[class*="datepicker"]',
    'input[id*="date" i]',
    'input[name*="date" i]',
    'input[placeholder*="日付" i]',
    'input[type="date"]',
]


async def detect_date_field(
    page: Any,
    configured: Any,
    purpose: str,
    heuristic: Optional[Sequence[str]] = None,
) -> Any:
    """検索フォーム上の日付入力フィールドを検出する。

    Args:
        page: Playwright ``Page`` (または互換のモック)。
        configured: YAML から取得した候補セレクタ（str または str のリスト）。
        purpose: ``"start_date"`` または ``"end_date"``。
        heuristic: フォールバック用セレクタリスト。省略時は ``DEFAULT_DATE_HEURISTIC``。

    Returns:
        ヒットした要素、または ``None``。
    """
    candidates: List[str] = [configured] if isinstance(configured, str) else list(configured or [])
    for selector in candidates:
        try:
            element = await page.query_selector(selector)
        except Exception:
            continue
        if element:
            return element

    ordered = list(heuristic) if heuristic else DEFAULT_DATE_HEURISTIC
    elements: List[Any] = []
    for selector in ordered:
        try:
            elements = await page.query_selector_all(selector)
        except Exception:
            continue
        if elements:
            break

    if not elements:
        return None
    return elements[-1] if purpose == "end_date" else elements[0]
