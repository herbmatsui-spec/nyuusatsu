# -*- coding: utf-8 -*-
"""Step 25-30: 信頼度スコア・品質管理"""
import re
import logging
from typing import Dict, Any, List
from .ocr_result import OCRResult, OCRBlock
from .logger import setup_ocr_logging

logger = setup_ocr_logging()


class ConfidenceScorer:
    """OCR結果の信頼度スコア計算と品質評価"""

    def __init__(self, config: Optional[Any] = None):
        self.min_confidence = getattr(config, "confidence_threshold", 0.6)

    def calculate_average_confidence(self, blocks: List[OCRBlock]) -> float:
        """Step 25: ブロックリストの平均信頼度を計算"""
        if not blocks:
            return 0.0
        confidence_sum = sum(b.confidence for b in blocks)
        return confidence_sum / len(blocks)

    def evaluate_text_quality(self, text: str) -> Dict[str, Any]:
        """Step 26: テキスト品質の評価指標を計算"""
        if not text or not text.strip():
            return {
                "score": 0.0,
                "char_count": 0,
                "has_garbled": True,
                "metrics": {},
            }

        char_count = len(text)
        japanese_chars = len(re.findall(r"[\u3040-\u30ff\u4e00-\u9fff]", text))
        alnum_chars = len(re.findall(r"[a-zA-Z0-9]", text))
        symbol_chars = len(re.findall(r"[!-/:-@\[-`{-~]", text))
        space_chars = text.count(" ") + text.count("\n") + text.count("\t")

        garbled_pattern = r"[\x00-\x08\x0b\x0c\x0e-\x1f]"
        garbled_chars = len(re.findall(garbled_pattern, text))

        total = max(char_count, 1)
        metrics = {
            "japanese_ratio": japanese_chars / total,
            "alnum_ratio": alnum_chars / total,
            "symbol_ratio": symbol_chars / total,
            "space_ratio": space_chars / total,
            "garbled_ratio": garbled_chars / total,
        }

        score = 1.0
        score -= metrics["garbled_ratio"] * 5.0
        if metrics["symbol_ratio"] > 0.3:
            score -= (metrics["symbol_ratio"] - 0.3) * 2.0
        if char_count < 20:
            score -= 0.2

        score = max(0.0, min(1.0, score))

        return {
            "score": score,
            "char_count": char_count,
            "has_garbled": garbled_chars > 0,
            "metrics": metrics,
        }

    def is_scanned_pdf(self, extracted_text: str, char_threshold: int = 50) -> bool:
        """Step 27: スキャンPDFかどうかを判定 (Deprecated: Use ocr.is_scanned_pdf)"""
        from ocr import is_scanned_pdf as check_is_scanned
        # Compatibility wrapper: old signature used text content
        return len(extracted_text.strip()) < char_threshold

    def generate_quality_report(self, result: OCRResult) -> Dict[str, Any]:
        """Step 28: UI表示用の品質レポートを生成"""
        quality = self.evaluate_text_quality(result.full_text)
        blocks_quality = [
            self.evaluate_text_quality(b.text) for b in result.blocks
        ]

        low_conf_blocks = [
            i for i, b in enumerate(result.blocks)
            if b.confidence < self.min_confidence
        ]

        return {
            "overall_confidence": result.average_confidence,
            "text_quality_score": quality["score"],
            "total_pages": result.total_pages,
            "total_blocks": len(result.blocks),
            "low_confidence_block_indices": low_conf_blocks,
            "needs_correction": (
                result.average_confidence < self.min_confidence
                or quality["score"] < 0.7
            ),
            "warning_message": self._generate_warning(
                result, quality, low_conf_blocks
            ),
            "block_details": blocks_quality,
        }

    def _generate_warning(
        self,
        result: OCRResult,
        quality: Dict[str, Any],
        low_conf_blocks: List[int],
    ) -> str:
        """Step 29: 精度が低い場合の警告メッセージを生成"""
        warnings = []

        if result.average_confidence < self.min_confidence:
            pct = result.average_confidence * 100
            warnings.append(
                "Average confidence is low ({:.1f}%). Manual correction recommended.".format(pct)
            )

        if quality.get("has_garbled"):
            warnings.append("Text contains garbled characters. Correction needed.")

        if low_conf_blocks:
            warnings.append(
                "Low confidence blocks: {} found".format(len(low_conf_blocks))
            )

        if quality["score"] < 0.7:
            warnings.append("Text quality score is low. Please verify content.")

        return " / ".join(warnings) if warnings else ""

    def log_quality_metrics(self, result: OCRResult, source: str = ""):
        """Step 30: 品質指標をログに記録"""
        report = self.generate_quality_report(result)
        logger.info(
            "OCR quality log | source=%s | confidence=%.3f | quality=%.3f | "
            "pages=%d | blocks=%d | needs_correction=%s",
            source,
            report["overall_confidence"],
            report["text_quality_score"],
            report["total_pages"],
            report["total_blocks"],
            report["needs_correction"],
        )
        if report["warning_message"]:
            logger.warning("Quality warning: %s", report["warning_message"])
