from __future__ import annotations

from typing import Dict, Any


class FeatureExtractionService:
    def extract(self, bid_id: int, full_text: str) -> Dict[str, Any]:
        return {
            "bid_id": bid_id,
            "business_category": self._guess_category(full_text),
            "scale_score": min(len(full_text) // 1000, 10),
            "required_qualifications": self._extract_qualifications(full_text),
            "region": self._extract_region(full_text),
        }

    def _guess_category(self, text: str) -> str:
        keywords = {
            "建設": ["工事", "建設", "土木"],
            "IT": ["システム", "開発", "運用"],
            "コンサル": ["コンサル", "調査", "計画"],
        }
        for category, words in keywords.items():
            if any(w in text for w in words):
                return category
        return "その他"

    def _extract_qualifications(self, text: str) -> list[str]:
        return [line.strip() for line in text.splitlines() if "資格" in line][:5]

    def _extract_region(self, text: str) -> str:
        for pref in ["北海道", "愛媛", "東京", "大阪"]:
            if pref in text:
                return pref
        return "全国"
