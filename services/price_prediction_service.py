from __future__ import annotations

import json
import os
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session
from config import AppConfig
from services.llm_provider import LLMService
from services.llm_prompt_builder import LLMPromptBuilder
from services.win_rate_service import WinRateService
from services.similar_bid_service import SimilarBidService
from services.feature_extraction_service import FeatureExtractionService
from database.models.bid import Bid


class PricePredictionService:
    def __init__(self, session: Session, config: Optional[AppConfig] = None):
        self.session = session
        self.config = config or AppConfig()
        self.llm = LLMService(
            deepseek_key=os.getenv("DEEPSEEK_API_KEY"),
            gemini_key=os.getenv("GEMINI_API_KEY"),
            config=self.config,
        )
        self.builder = LLMPromptBuilder()
        self.win_rate = WinRateService()
        self.similar = SimilarBidService(session)
        self.feature = FeatureExtractionService()

    def predict(self, bid_id: int, competitor_ids: List[int], bid_amount: int) -> Dict[str, Any]:
        bid = self.session.query(Bid).get(bid_id)
        if not bid:
            return {"error": "bid_not_found"}
        text = getattr(bid, "full_text", "") or ""
        features = self.feature.extract(bid_id, text)
        similar = self.similar.find_similar(bid_id)
        stats = self.win_rate.summarize(similar)
        competitors = [str(cid) for cid in competitor_ids]
        prompt = self.builder.build(bid.filename or "", stats, competitors)
        try:
            result = self.llm.analyze_with_fallback(prompt, system_prompt="")
            return {
                "expected_price": result.get("expected_price", bid_amount),
                "win_probability": float(result.get("win_probability", 0.0)),
                "rationale": result.get("rationale", ""),
            }
        except Exception as exc:
            return {"error": str(exc)}
