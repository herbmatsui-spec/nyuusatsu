from __future__ import annotations

import hashlib
import io
import logging
import os
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from config import AppConfig
from database.models.document_archive import DocumentArchive

logger = logging.getLogger(__name__)


class ArchiveService:
    """PDF・HTML・添付資料の魚拓保存サービス"""

    def __init__(self, session: Session, config: Optional[AppConfig] = None):
        self.session = session
        self.config = config or AppConfig()
        self.archive_root = self.config.archive.archive_dir
        os.makedirs(self.archive_root, exist_ok=True)

    def _get_archive_path(self, bid_id: int, file_type: str, filename: str) -> str:
        safe_type = file_type.replace("/", "_")
        agency_dir = os.path.join(self.archive_root, str(bid_id), safe_type)
        os.makedirs(agency_dir, exist_ok=True)
        return os.path.join(agency_dir, filename)

    def _compute_sha256(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _is_duplicate(self, bid_id: int, file_type: str, sha256: str) -> bool:
        return (
            self.session.query(DocumentArchive)
            .filter(
                DocumentArchive.bid_id == bid_id,
                DocumentArchive.file_type == file_type,
                DocumentArchive.sha256 == sha256,
            )
            .first()
            is not None
        )

    def download_and_store(
        self,
        url: str,
        bid_id: int,
        file_type: str = "pdf",
        filename: Optional[str] = None,
    ) -> Optional[DocumentArchive]:
        if not filename:
            parsed = urlparse(url)
            filename = os.path.basename(parsed.path) or f"{int(time.time())}.bin"
            if not os.path.splitext(filename)[1]:
                filename = f"{filename}.{file_type}"

        local_path = self._get_archive_path(bid_id, file_type, filename)

        if os.path.exists(local_path):
            existing = (
                self.session.query(DocumentArchive)
                .filter(DocumentArchive.local_path == local_path)
                .first()
            )
            if existing:
                return existing

        data = self._download_with_retry(url)
        if data is None:
            logger.warning("Failed to download archive: %s", url)
            return None

        sha256 = self._compute_sha256(data)
        if self._is_duplicate(bid_id, file_type, sha256):
            logger.info("Duplicate archive skipped: %s", url)
            return None

        with open(local_path, "wb") as f:
            f.write(data)

        archive = DocumentArchive(
            bid_id=bid_id,
            file_type=file_type,
            original_url=url,
            local_path=local_path,
            sha256=sha256,
            file_size=len(data),
            is_deleted_external=False,
        )
        self.session.add(archive)
        self.session.flush()
        logger.info("Archived: %s -> %s", url, local_path)
        return archive

    def _download_with_retry(self, url: str, max_retries: int = 3) -> Optional[bytes]:
        last_error: Optional[Exception] = None
        for attempt in range(1, max_retries + 1):
            try:
                with httpx.Client(timeout=60) as client:
                    response = client.get(url, follow_redirects=True)
                    response.raise_for_status()
                    return response.content
            except Exception as exc:
                last_error = exc
                logger.warning("Download attempt %d/%d failed: %s", attempt, max_retries, exc)
                time.sleep(2 ** attempt)
        logger.error("All download attempts failed for %s: %s", url, last_error)
        return None

    def get_archives_by_bid(self, bid_id: int) -> list[DocumentArchive]:
        return (
            self.session.query(DocumentArchive)
            .filter(DocumentArchive.bid_id == bid_id)
            .order_by(DocumentArchive.archived_at.desc())
            .all()
        )

    def get_by_id(self, archive_id: int) -> Optional[DocumentArchive]:
        return self.session.get(DocumentArchive, archive_id)
