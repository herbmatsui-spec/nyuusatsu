from abc import ABC, abstractmethod
from typing import List, Optional
from .ocr_result import OCRResult, OCRBlock


class OCRProvider(ABC):
    """OCRプロバイダーの抽象基底クラス"""

    @abstractmethod
    def extract_text(self, file_path: str) -> OCRResult:
        """ファイルパスからテキストを抽出"""
        pass

    @abstractmethod
    def extract_text_from_bytes(self, file_data: bytes) -> OCRResult:
        """バイトデータからテキストを抽出"""
        pass

    def is_available(self) -> bool:
        """プロバイダーが利用可能かどうかをチェック"""
        return True
