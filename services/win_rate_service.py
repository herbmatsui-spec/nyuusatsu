from __future__ import annotations

import statistics
from typing import List, Dict, Any


class WinRateService:
    def summarize(self, similar: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not similar:
            return {"count": 0, "median_award_rate": None, "expected_price_band": None}
        rates = [r["award_rate"] for r in similar if r.get("award_rate") is not None]
        prices = [r["contract_amount"] for r in similar if r.get("contract_amount") is not None]
        median_rate = statistics.median(rates) if rates else None
        return {
            "count": len(similar),
            "median_award_rate": round(median_rate, 4) if median_rate is not None else None,
            "expected_price_band": self._band(prices),
        }

    def _band(self, prices: List[int]) -> str:
        if not prices:
            return "データ不足"
        mn = min(prices)
        mx = max(prices)
        return f"{mn:,}円 ～ {mx:,}円"
