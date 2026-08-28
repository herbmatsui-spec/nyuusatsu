"""
Award Pipeline
クローラから生データを受信→正規化→保存→競合紐付け→アラート判定 の一連処理。
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from database.engine import get_session
from database.models import AwardResult, Competitor, AwardHistory
from database.repositories.award_result_repository import AwardResultRepository
from database.repositories.competitor_repository import CompetitorRepository
from database.repositories.award_history_repository import AwardHistoryRepository
from services.award_calculator import calculate_award_rate, enrich_award_rate
from services.company_normalizer import build_competitor_payload, normalize_company_name

logger = logging.getLogger(__name__)


class AwardPipeline:
    """
    落札結果データの一貫した保存・処理パイプライン。
    """

    def run(self, award_data: Dict[str, Any]) -> Optional[AwardResult]:
        """
        単一の award_data を受信して保存・競合紐付けまで行う。
        戻り値: 保存された AwardResult、または None。
        """
        try:
            with get_session() as session:
                award_repo = AwardResultRepository(session)
                comp_repo = CompetitorRepository(session)
                history_repo = AwardHistoryRepository(session)

                # 既存チェック（source_url で重複排除）
                existing = None
                if award_data.get("source_url"):
                    existing = award_repo.get_by_source_url(award_data["source_url"])
                if existing:
                    logger.info(f"Award already exists: {award_data.get('source_url')}")
                    return existing

                # 落札率補完
                enriched = enrich_award_rate(dict(award_data))

                # 保存
                award_obj = award_repo.create(enriched)

                # 競合企業マスタ更新
                winner_name = enriched.get("winner_name")
                if winner_name:
                    normalized = normalize_company_name(winner_name)
                    payload = build_competitor_payload(winner_name)
                    competitor = comp_repo.upsert_by_name(winner_name, normalized)

                    # 落札履歴に追加
                    history_repo.create({
                        "competitor_id": competitor.id,
                        "award_result_id": award_obj.id,
                        "rank": 1,
                        "bid_amount": enriched.get("contract_amount"),
                        "is_winner": True,
                    })

                    # 業種カテゴリが未設定なら補完
                    if not competitor.industry_category and payload.get("industry_category"):
                        comp_repo.update(competitor, {"industry_category": payload["industry_category"]})

                logger.info(f"Saved award result: id={award_obj.id}, winner={winner_name}")
                return award_obj

        except Exception as e:
            logger.error(f"AwardPipeline failed: {e}")
            return None

    def run_batch(self, award_data_list: List[Dict[str, Any]]) -> List[AwardResult]:
        """複数の落札結果をバッチで保存する。"""
        results: List[AwardResult] = []
        for data in award_data_list:
            obj = self.run(data)
            if obj:
                results.append(obj)
        return results
