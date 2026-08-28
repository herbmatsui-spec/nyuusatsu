# -*- coding: utf-8 -*-
"""TesseractによるOCR実装 (Step 13-18)"""
import os
import io
import tempfile
from typing import List, Optional
import logging

from .base import OCRProvider
from .ocr_result import OCRBlock, OCRResult
from .config import OCRConfig
from .logger import setup_ocr_logging

logger = setup_ocr_logging()


class TesseractOCRProvider(OCRProvider):
    """Tesseract OCRを使用したプロバイダー"""

    def __init__(self, config: Optional[OCRConfig] = None):
        self.config = config or OCRConfig.from_env()
        self._pytesseract = None
        self._pdf2image = None

    def _ensure_imports(self):
        """遅延インポート"""
        if self._pytesseract is None:
            import pytesseract
            self._pytesseract = pytesseract
            if self.config.tesseract_cmd:
                self._pytesseract.pytesseract.tesseract_cmd = self.config.tesseract_cmd
        if self._pdf2image is None:
            from pdf2image import convert_from_path, convert_from_bytes
            self._pdf2image = type("PDF2Image", (), {
                "convert_from_path": convert_from_path,
                "convert_from_bytes": convert_from_bytes,
            })

    def is_available(self) -> bool:
        """Tesseractが利用可能かチェック"""
        try:
            self._ensure_imports()
            self._pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def extract_text(self, file_path: str) -> OCRResult:
        """PDFファイルパスからテキストを抽出"""
        self._ensure_imports()
        logger.info("Tesseract OCR start: %s", file_path)

        try:
            images = self._pdf2image.convert_from_path(
                file_path,
                dpi=self.config.dpi,
                first_page=1,
                last_page=self.config.max_pages,
            )
        except Exception as e:
            logger.error("PDF to image error: %s", e)
            raise

        return self._process_images(images)

    def extract_text_from_bytes(self, file_data: bytes) -> OCRResult:
        """PDFバイトデータからテキストを抽出"""
        self._ensure_imports()
        logger.info("Tesseract OCR start (bytes)")

        try:
            images = self._pdf2image.convert_from_bytes(
                file_data,
                dpi=self.config.dpi,
                first_page=1,
                last_page=self.config.max_pages,
            )
        except Exception as e:
            logger.error("PDF to image error: %s", e)
            raise

        return self._process_images(images)

    def _process_images(self, images) -> OCRResult:
        """画像リストを処理してOCRResultを生成 (Step 15)"""
        blocks = []
        full_text_parts = []

        for page_idx, image in enumerate(images):
            logger.info("Processing page %d/%d", page_idx + 1, len(images))
            page_blocks, page_text = self._ocr_image(image, page_idx)
            blocks.extend(page_blocks)
            full_text_parts.append(page_text)

        full_text = "\n\n".join(full_text_parts)
        if blocks:
            avg_conf = sum(b.confidence for b in blocks) / len(blocks)
        else:
            avg_conf = 0.0

        result = OCRResult(
            blocks=blocks,
            total_pages=len(images),
            average_confidence=avg_conf,
            full_text=full_text,
            structured_data=None
        )

        logger.info(
            "Tesseract OCR done: %d blocks, avg confidence=%.3f",
            len(blocks), avg_conf
        )
        return result

    def _ocr_image(self, image, page_number: int):
        """単一画像に対してOCRを実行 (Step 14)"""
        custom_config = "--oem 3 --psm 6 -l " + self.config.tesseract_lang

        text = self._pytesseract.image_to_string(image, config=custom_config)

        data = self._pytesseract.image_to_data(
            image, config=custom_config, output_type=self._pytesseract.Output.DICT
        )

        blocks = []
        word_count = len(data.get("text", []))

        confidences = []
        for i in range(word_count):
            if data["text"][i].strip():
                conf_val = int(data["conf"][i])
                if conf_val >= 0:
                    confidences.append(conf_val)

        if confidences:
            avg_conf = sum(confidences) / 100.0
        else:
            avg_conf = 0.0

        text = self._postprocess_text(text)

        block = OCRBlock(
            text=text,
            confidence=avg_conf,
            page_number=page_number,
            block_type="text"
        )
        blocks.append(block)

        return blocks, text

    def _postprocess_text(self, text: str) -> str:
        """Step 17: Tesseract精度向上の後処理"""
        if not text:
            return text

        lines = []
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped:
                lines.append(stripped)

        result = "\n".join(lines)
        result = result.replace("\n\n\n", "\n\n")

        common_fixes = {
            "l|": "10",
            "|0": "10",
        }
        for wrong, correct in common_fixes.items():
            result = result.replace(wrong, correct)

        return result
