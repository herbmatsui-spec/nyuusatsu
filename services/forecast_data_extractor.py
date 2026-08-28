import re
from typing import Dict, Any, Optional
from utils.forecast_logger import ForecastLogger


class ForecastDataExtractor:
    """LLMに頼らずルールベースで発注見通しの基本情報を抽出する（前処理）。"""

    def __init__(self):
        self.logger = ForecastLogger("DataExtractor")
        self.budget_patterns = [
            (r"(\d+[\d,.]*)\s*億円", lambda x: int(float(x.replace(",", "")) * 100000000)),
            (r"(\d+[\d,.]*)\s*万円", lambda x: int(float(x.replace(",", "")) * 10000)),
            (r"(\d+[\d,.]*)\s*円", lambda x: int(float(x.replace(",", "")))),
        ]

    def extract_structured_data(self, text: str) -> Dict[str, Any]:
        self.logger.info("Performing rule-based extraction")
        return {
            "title": self._extract_title(text),
            "estimated_budget": self._extract_budget_text(text),
            "estimated_budget_amount": self._extract_budget_amount(text),
            "expected_publish_date": self._extract_date(text, "publish"),
            "expected_bid_date": self._extract_date(text, "bid"),
            "category": self._extract_category(text),
            "raw_text": text,
        }

    def _extract_title(self, text: str) -> str:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if not lines:
            return "不明"
        match = re.search(r"(?:件名|事業名|名称)[:：]\s*(.*)", text)
        if match:
            return match.group(1).strip()
        return lines[0]

    def _extract_budget_text(self, text: str) -> Optional[str]:
        match = re.search(r"(?:予算|予定価格|概算額)[:：]\s*([^\n]+)", text)
        return match.group(1).strip() if match else None

    def _extract_budget_amount(self, text: str) -> Optional[int]:
        budget_text = self._extract_budget_text(text)
        if not budget_text:
            return None
        for pattern, converter in self.budget_patterns:
            match = re.search(pattern, budget_text)
            if match:
                try:
                    return converter(match.group(1))
                except (ValueError, TypeError):
                    continue
        return None

    def _extract_date(self, text: str, date_type: str) -> Optional[str]:
        keywords = {"publish": ["公示", "公告", "公開"], "bid": ["入札", "開札", "締切"]}
        for kw in keywords.get(date_type, []):
            match = re.search(rf"{kw}[:：]\s*(\d{{4}}[-/]\d{{1,2}}[-/]\d{{1,2}})", text)
            if match:
                return match.group(1).replace("/", "-")
        return None

    def _extract_category(self, text: str) -> Optional[str]:
        categories = ["土木", "建築", "電気", "通信", "システム", "清掃", "警備", "コンサル"]
        for cat in categories:
            if cat in text:
                return cat
        return None
