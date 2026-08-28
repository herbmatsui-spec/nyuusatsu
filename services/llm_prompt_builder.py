from __future__ import annotations

from typing import Dict, Any, List


class LLMPromptBuilder:
    def build(self, bid_summary: str, similar_stats: Dict[str, Any], competitors: List[str]) -> str:
        return (
            "以下の入札案件について、過去の類似落札データと競合情報をもとに、"
            "適正入札価格帯と予測勝率を推定してください。\n\n"
            f"【案件サマリ】\n{bid_summary}\n\n"
            f"【類似案件統計】\n{similar_stats}\n\n"
            f"【参加予想競合】\n{', '.join(competitors)}\n\n"
            "出力はJSONで: {\"expected_price\": 金額, \"win_probability\": 0.0-1.0, \"rationale\": \"理由\"}"
        )
