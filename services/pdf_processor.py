from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import List, Optional

import pdfplumber

from config import AppConfig
from exceptions import OCRProcessingError, PDFExtractionError
from ocr import ocr_extract_text

logger = logging.getLogger(__name__)


class PDFProcessor:
    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig()
        self.logger = logger.getChild(self.__class__.__name__)
        self._ocr_available = True

    def extract_text(
        self,
        source: io.BytesIO | str,
        source_name: str = "uploaded.pdf",
    ) -> str:
        if isinstance(source, str):
            return self._extract_from_path(source, source_name)
        return self._extract_from_bytes(source, source_name)

    def _extract_from_path(self, pdf_path: str, source_name: str) -> str:
        texts: List[str] = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text(layout=True) or ""
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            for row in table:
                                row_text = " ".join(
                                    str(cell) for cell in row if cell is not None
                                )
                                page_text += "\n" + row_text
                    texts.append(page_text)
        except pdfplumber.PDFException as exc:
            raise PDFExtractionError(f"PDFの読み込みに失敗しました（pdfplumberエラー）: {exc}") from exc
        except PermissionError as exc:
            raise PDFExtractionError(f"PDFファイルにアクセス権限がありません: {exc}") from exc
        except Exception as exc:
            raise PDFExtractionError(f"予期しないエラー: {exc}") from exc

        full_text = "\n".join(texts).strip()
        return self._handle_extracted_text(full_text, pdf_path, source_name)

    def _extract_from_bytes(self, pdf_bytes: io.BytesIO, source_name: str) -> str:
        pdf_bytes.seek(0)
        texts: List[str] = []
        try:
            with pdfplumber.open(pdf_bytes) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text(layout=True) or ""
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            for row in table:
                                row_text = " ".join(
                                    str(cell) for cell in row if cell is not None
                                )
                                page_text += "\n" + row_text
                    texts.append(page_text)
        except pdfplumber.PDFException as exc:
            raise PDFExtractionError(f"PDFの読み込みに失敗しました（pdfplumberエラー）: {exc}") from exc
        except PermissionError as exc:
            raise PDFExtractionError(f"PDFファイルにアクセス権限がありません: {exc}") from exc
        except Exception as exc:
            raise PDFExtractionError(f"予期しないエラー: {exc}") from exc

        full_text = "\n".join(texts).strip()
        return self._handle_extracted_text(full_text, pdf_bytes, source_name)

    def _handle_extracted_text(self, full_text: str, source: io.BytesIO | str, source_name: str) -> str:
        if not full_text or len(full_text) < 20:
            if (
                hasattr(self, "_ocr_available")
                and self._ocr_available
            ):
                try:
                    ocr_text = self._run_ocr(source, source_name)
                    if ocr_text and ocr_text.strip():
                        self.logger.info(f"OCR fallback succeeded for {source_name}")
                        return ocr_text.strip()
                except OCRProcessingError:
                    self.logger.warning("OCR failed, returning empty text")
                except Exception as exc:
                    self.logger.warning(f"OCR error: {exc}, returning empty text")
        return full_text

    def _run_ocr(self, source: io.BytesIO | str, source_name: str) -> Optional[str]:
        file_data: Optional[bytes] = None
        if hasattr(source, "read"):
            if hasattr(source, "seek"):
                try:
                    source.seek(0)
                except Exception:
                    pass
            file_data = source.read()
        if not file_data and isinstance(source, str):
            with open(source, "rb") as f:
                file_data = f.read()
        if not file_data:
            return None
        return ocr_extract_text(file_data, source_name=source_name)
