import re
from bs4 import BeautifulSoup
from typing import Dict, Optional

class BidDetailExtractor:
    """入札詳細ページから情報を抽出するクラス"""

    def extract(self, html: str) -> Dict[str, str]:
        """HTMLから詳細情報を抽出する"""
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text()
        
        # 予算額の抽出（例: 1,000,000円, 100万円）
        budget = self._extract_budget(text)
        
        # 期限の抽出（例: 2026年7月31日）
        deadline = self._extract_deadline(text)
        
        # 資格要件の抽出（例: 〇〇等級）
        qualification = self._extract_qualification(text)
        
        return {
            "budget": budget,
            "deadline": deadline,
            "qualifications": qualification,
        }

    def _extract_budget(self, text: str) -> str:
        # 予算額のパターンマッチング
        patterns = [
            r"予算額[:：]\s*([\d,]+円)",
            r"予定価格[:：]\s*([\d,]+円)",
            r"([\d,]+万円)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return ""

    def _extract_deadline(self, text: str) -> str:
        # 期限のパターンマッチング
        patterns = [
            r"入札期限[:：]\s*(\d{4}年\d{1,2}月\d{1,2}日)",
            r"提出期限[:：]\s*(\d{4}年\d{1,2}月\d{1,2}日)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return ""

    def _extract_qualification(self, text: str) -> str:
        # 資格要件のパターンマッチング
        match = re.search(r"資格要件[:：]\s*(.+)", text)
        if match:
            return match.group(1).strip()
        return ""
