# -*- coding: utf-8 -*-
"""OCRフォールバック用メトリクス収集基盤 (Steps 32-33)"""
from dataclasses import dataclass, field


@dataclass
class OCRMetrics:
    """OCR処理の統計メトリクス"""
    fallback_count: int = 0
    normal_extract_count: int = 0
    ocr_failure_count: int = 0
    confidence_sum: float = 0.0
    confidence_count: int = 0

    @property
    def average_confidence(self) -> float:
        """OCRフォールバックの平均信頼度"""
        if self.confidence_count == 0:
            return 0.0
        return self.confidence_sum / self.confidence_count

    def to_dict(self) -> dict:
        """監視用辞書形式"""
        return {
            "ocr_fallback_count": self.fallback_count,
            "ocr_normal_extract_count": self.normal_extract_count,
            "ocr_failure_count": self.ocr_failure_count,
            "ocr_average_confidence": self.average_confidence,
        }


_ocr_metrics = OCRMetrics()


def get_metrics() -> OCRMetrics:
    """グローバルメトリクスインスタンス取得"""
    return _ocr_metrics


def reset_metrics() -> None:
    """開発/テスト用: メトリクスリセット"""
    global _ocr_metrics
    _ocr_metrics = OCRMetrics()


def record_fallback(provider: str, confidence: float) -> None:
    """OCRフォールバック発生時に記録"""
    _ocr_metrics.fallback_count += 1
    _ocr_metrics.confidence_sum += confidence
    _ocr_metrics.confidence_count += 1


def record_normal_extract() -> None:
    """通常pdfplumber抽出成功時に記録"""
    _ocr_metrics.normal_extract_count += 1


def record_ocr_failure() -> None:
    """OCR処理失敗時に記録"""
    _ocr_metrics.ocr_failure_count += 1