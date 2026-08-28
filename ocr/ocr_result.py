from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class OCRBlock:
    """OCRで抽出されたテキストブロック"""
    text: str
    confidence: float  # 0.0 ~ 1.0
    bbox: Optional[Tuple[int, int, int, int]] = None  # (x0, y0, x1, y1) ピクセル座標
    page_number: int = 0  # 0-indexed
    block_type: str = "text"  # "text", "table", "heading", "selection_mark"

@dataclass
class OCRResult:
    """OCR処理結果全体"""
    blocks: List[OCRBlock]
    total_pages: int
    average_confidence: float
    full_text: str
    structured_data: Optional[dict] = None  # Raw JSON for further analysis


    @property
    def is_high_confidence(self) -> bool:
        """全体の平均信頼度が高いかどうか"""
        return self.average_confidence >= 0.8
