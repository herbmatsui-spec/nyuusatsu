"""PDF パーサー実装（OCR 連携）

- 現在はスタブ実装です。実際の PDF テキスト抽出は OCR プロバイダー（例: TesseractOCR）を利用して実装してください。
- `extract_fields` は PDF ファイルパスまたはバイト列からテキスト抽出し、`HtmlParser` と同様の辞書形式で返すことを想定
"""

from .base_parser import BaseParser
# OCR provider のインタフェースは ocr.base.OCRProvider
# ここでは簡易スタブを提供し、実装者が適切に拡張できるようにする

class PdfParser(BaseParser):
    def __init__(self, ocr_provider=None):
        # ocr_provider は OCRProvider の実装インスタンス（例: TesseractOCR）
        self.ocr = ocr_provider

    def extract_fields(self, raw_text: str) -> dict:
        # raw_text には PDF ファイルのパスが渡される想定（実装に合わせて変更）
        if self.ocr is None:
            raise RuntimeError("OCR provider not configured for PdfParser")
        # OCR でテキスト抽出（実装例）:
        # result = self.ocr.extract_text(raw_text)
        # text = result.full_text
        # ここではプレースホルダーとして空辞書を返す
        return {}
