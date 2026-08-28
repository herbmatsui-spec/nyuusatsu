# -*- coding: utf-8 -*-
"""Azure Document IntelligenceによるOCR実装 (Step 19-24)"""
import logging
from typing import Optional, List

from .base import OCRProvider
from .ocr_result import OCRBlock, OCRResult
from .config import OCRConfig
from .logger import setup_ocr_logging

logger = setup_ocr_logging()


class AzureDocIntProvider(OCRProvider):
    """Azure Document Intelligenceを使用したプロバイダー"""

    def __init__(self, config: Optional[OCRConfig] = None):
        self.config = config or OCRConfig.from_env()
        self._client = None

    def _ensure_client(self):
        """遅延初期化でAzure SDKクライアントを作成"""
        if self._client is None:
            if not self.config.azure_endpoint or not self.config.azure_key:
                raise ValueError("Azure Document Intelligence configuration is missing")

            from azure.ai.documentintelligence import DocumentIntelligenceClient
            from azure.core.credentials import AzureKeyCredential

            self._client = DocumentIntelligenceClient(
                endpoint=self.config.azure_endpoint,
                credential=AzureKeyCredential(self.config.azure_key),
            )

    def is_available(self) -> bool:
        """Azure設定が利用可能かチェック"""
        return bool(
            self.config.azure_endpoint and self.config.azure_key
        )

    def extract_text(self, file_path: str) -> OCRResult:
        """PDFファイルパスからテキストを抽出"""
        self._ensure_client()
        logger.info("Azure Document Intelligence start: %s", file_path)

        with open(file_path, "rb") as f:
            poller = self._client.begin_analyze_document(
                "prebuilt-layout",
                body=f,
            )
            result = poller.result()

        return self._normalize_result(result)

    def extract_text_from_bytes(self, file_data: bytes) -> OCRResult:
        """PDFバイトデータからテキストを抽出"""
        self._ensure_client()
        logger.info("Azure Document Intelligence start (bytes)")

        from io import BytesIO
        poller = self._client.begin_analyze_document(
            "prebuilt-layout",
            body=BytesIO(file_data),
        )
        result = poller.result()

        return self._normalize_result(result)

    def _normalize_result(self, result) -> OCRResult:
        """Step 21: Azure結果を標準形式に変換 (構造化対応)"""
        blocks = []
        full_text_parts = []

        # Tables handling
        tables_content = []
        if hasattr(result, "tables"):
            for table in result.tables:
                # Convert table to Markdown
                md_table = self._table_to_markdown(table)
                tables_content.append(md_table)
                blocks.append(OCRBlock(
                    text=md_table,
                    confidence=0.9,
                    page_number=table.bounding_regions[0].page_number if table.bounding_regions else 0,
                    block_type="table"
                ))

        for page_idx, page in enumerate(result.pages):
            page_text_parts = []
            for line in page.lines:
                page_text_parts.append(line.content)
            
            page_text = "\n".join(page_text_parts)
            full_text_parts.append(page_text)

            block = OCRBlock(
                text=page_text,
                confidence=0.9,
                page_number=page_idx,
                block_type="text"
            )
            blocks.append(block)

        full_text = "\n\n".join(full_text_parts)
        # Append tables to full text if present
        if tables_content:
            full_text += "\n\n### Tables\n\n" + "\n\n".join(tables_content)

        avg_conf = sum(b.confidence for b in blocks) / len(blocks) if blocks else 0.0
        total_pages = len(result.pages) if result.pages else 0

        return OCRResult(
            blocks=blocks,
            total_pages=total_pages,
            average_confidence=avg_conf,
            full_text=full_text,
            structured_data={"tables": tables_content}
        )

    def _table_to_markdown(self, table) -> str:
        """Azure Table object to Markdown string"""
        rows = []
        for cell in table.cells:
            # This is a simplified representation. 
            # Azure tables can be complex; we'll need a more robust map in Step 3.
            rows.append(cell.content)
        return "\n".join(rows)
