"""URL変更検知機能。

過去のレスポンス（ステータスコード / コンテンツのハッシュ）と比較し、
URLが変更・メンテナンス中・削除された場合にフラグを立てる。
スナップショットは ``data/url_snapshots.json`` に保持する。
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from crawler.registry import PROJECT_ROOT

logger = logging.getLogger(__name__)

DEFAULT_SNAPSHOT_PATH = str(PROJECT_ROOT / "data" / "url_snapshots.json")


@dataclass
class ChangeDetection:
    url: str
    changed: bool
    previous_status: Optional[int]
    current_status: Optional[int]
    previous_hash: Optional[str]
    current_hash: str
    reason: str = ""


class UrlChangeDetector:
    """レスポンスのステータスコードとヘッダ/テキストハッシュで変化を検知。"""

    def __init__(self, snapshot_path: str = DEFAULT_SNAPSHOT_PATH) -> None:
        self.snapshot_path = snapshot_path
        self._snapshots: dict = self._load_snapshots()

    def _load_snapshots(self) -> dict:
        if os.path.exists(self.snapshot_path):
            try:
                with open(self.snapshot_path, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load snapshots: %s", e)
        return {}

    def save_snapshots(self) -> None:
        Path(os.path.dirname(self.snapshot_path) or ".").mkdir(parents=True, exist_ok=True)
        with open(self.snapshot_path, "w", encoding="utf-8") as fh:
            json.dump(self._snapshots, fh, indent=2, ensure_ascii=False)
        logger.info("Saved %d URL snapshots to %s", len(self._snapshots), self.snapshot_path)

    @staticmethod
    def _hash_payload(content: str, status_code: Optional[int]) -> str:
        payload = f"{status_code}|{content or ''}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def detect(
        self,
        url: str,
        current_content: str,
        current_status: Optional[int],
    ) -> ChangeDetection:
        current_hash = self._hash_payload(current_content, current_status)
        prev = self._snapshots.get(url)

        changed = False
        reason = ""
        if prev is None:
            reason = "first_seen"
        elif prev.get("status") != current_status:
            changed = True
            reason = f"status_change:{prev.get('status')}->{current_status}"
        elif prev.get("hash") != current_hash:
            changed = True
            reason = "content_changed"

        self._snapshots[url] = {
            "status": current_status,
            "hash": current_hash,
        }
        return ChangeDetection(
            url=url,
            changed=changed,
            previous_status=prev.get("status") if prev else None,
            current_status=current_status,
            previous_hash=prev.get("hash") if prev else None,
            current_hash=current_hash,
            reason=reason,
        )
