from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from database.engine import get_session
from database.models.document_archive import DocumentArchive
from services.archive_service import ArchiveService


@pytest.fixture
def db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    from database.base import Base
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


class TestArchiveService:
    def test_download_and_store_success(self, db_session):
        fake_content = b"%PDF-1.4 fake pdf content"
        with patch("services.archive_service.httpx.Client") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = fake_content
            mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_response

            service = ArchiveService(db_session)
            result = service.download_and_store(
                url="http://example.com/sample.pdf",
                bid_id=1,
                file_type="pdf",
                filename="sample.pdf",
            )

        assert result is not None
        assert result.sha256 is not None
        assert result.file_size == len(fake_content)
        assert os.path.exists(result.local_path)

        with open(result.local_path, "rb") as f:
            assert f.read() == fake_content

    def test_download_and_store_duplicate_skipped(self, db_session):
        fake_content = b"%PDF-1.4 fake pdf content"
        with patch("services.archive_service.httpx.Client") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = fake_content
            mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_response

            service = ArchiveService(db_session)
            result1 = service.download_and_store(
                url="http://example.com/sample.pdf",
                bid_id=1,
                file_type="pdf",
                filename="sample.pdf",
            )
            result2 = service.download_and_store(
                url="http://example.com/sample.pdf",
                bid_id=1,
                file_type="pdf",
                filename="sample_copy.pdf",
            )

        assert result1 is not None
        assert result2 is None

    def test_download_and_store_network_failure(self, db_session):
        with patch("services.archive_service.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value.get.side_effect = Exception("Network error")

            service = ArchiveService(db_session)
            result = service.download_and_store(
                url="http://example.com/missing.pdf",
                bid_id=1,
                file_type="pdf",
                filename="missing.pdf",
            )

        assert result is None

    def test_get_archives_by_bid(self, db_session):
        fake_content = b"%PDF-1.4 fake pdf content"
        with patch("services.archive_service.httpx.Client") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = fake_content
            mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_response

            service = ArchiveService(db_session)
            service.download_and_store(
                url="http://example.com/doc1.pdf",
                bid_id=10,
                file_type="pdf",
                filename="doc1.pdf",
            )
            service.download_and_store(
                url="http://example.com/doc2.html",
                bid_id=10,
                file_type="html",
                filename="doc2.html",
            )

        archives = service.get_archives_by_bid(10)
        assert len(archives) == 2
        assert {a.file_type for a in archives} == {"pdf", "html"}
