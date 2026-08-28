import re
from typing import List, Dict, Any, Optional
from pathlib import Path

from utils.forecast_logger import ForecastLogger


class ForecastTextExtractor:
    """PDFからテキストを抽出する。発注見通しは表形式が多いため pdfplumber を使用。"""

    def __init__(self):
        self.logger = ForecastLogger("TextExtractor")

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        self.logger.info(f"Extracting text from PDF", path=pdf_path)
        full_text: List[str] = []
        try:
            import pdfplumber

            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        full_text.append(f"--- Page {i + 1} ---\n{page_text}")
                    tables = page.extract_tables()
                    for j, table in enumerate(tables):
                        table_text = "\n".join(
                            [" | ".join([str(cell) if cell else "" for cell in row]) for row in table]
                        )
                        full_text.append(f"[Table {j + 1}]\n{table_text}")
            return "\n".join(full_text)
        except Exception as e:
            self.logger.error(f"PDF extraction failed", path=pdf_path, error=str(e))
            return ""

    def clean_text(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"\s+", " ", text)
        return text.strip()
