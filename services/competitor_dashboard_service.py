"""
Competitor Dashboard Service
ダッシュボード向けの競合企業分析データを生成する。
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import (
    AwardHistory,
    AwardResult,
    Competitor,
)

logger = logging.getLogger(__name__)


class CompetitorDashboardService:
    def __init__(self, session: Session):
        self.session = session

    def get_competitor_summary(self) -> List[Dict[str, Any]]:
        """全競合のサマリー情報を返す。"""
        stmt = (
            select(
                Competitor.id,
                Competitor.normalized_name,
                Competitor.industry_category,
                Competitor.is_target_company,
                func.count(AwardHistory.id).label("total_bids"),
                func.sum(
                    func.case((AwardHistory.is_winner == True, 1), else_=0)
                ).label("wins"),
                func.avg(AwardResult.award_rate).label("avg_award_rate"),
                func.max(AwardResult.award_date).label("latest_award"),
                AwardResult.agency_name.label("agency_name"),
            )
            .select_from(Competitor)
            .outerjoin(AwardHistory, AwardHistory.competitor_id == Competitor.id)
            .outerjoin(AwardResult, AwardResult.id == AwardHistory.award_result_id)
            .group_by(
                Competitor.id,
                Competitor.normalized_name,
                Competitor.industry_category,
                Competitor.is_target_company,
                AwardResult.agency_name,
            )
            .order_by(func.count(AwardHistory.id).desc())
        )
        results = self.session.execute(stmt).all()
        summary = []
        for row in results:
            total = row.total_bids or 0
            wins = row.wins or 0
            win_rate = round(wins / total * 100, 1) if total > 0 else 0.0
            summary.append({
                "id": row.id,
                "name": row.normalized_name,
                "category": row.industry_category or "不明",
                "is_target": row.is_target_company,
                "total_bids": total,
                "wins": wins,
                "win_rate": win_rate,
                "avg_award_rate": round(float(row.avg_award_rate), 2) if row.avg_award_rate else None,
                "latest_award": row.latest_award,
            })
        return summary

    def get_competitor_detail(self, competitor_id: int) -> Optional[Dict[str, Any]]:
        """特定競合の詳細情報を返す。"""
        competitor = self.session.get(Competitor, competitor_id)
        if not competitor:
            return None

        wins_stmt = (
            select(AwardResult, AwardHistory)
            .join(AwardHistory, AwardResult.id == AwardHistory.award_result_id)
            .where(
                AwardHistory.competitor_id == competitor_id,
                AwardHistory.is_winner == True,
            )
            .order_by(AwardResult.award_date.desc())
        )
        wins = self.session.execute(wins_stmt).all()

        win_list = []
        for ar, ah in wins:
            win_list.append({
                "project_name": ar.project_name,
                "agency_name": ar.agency_name,
                "category": ar.category,
                "budget_amount": ar.budget_amount,
                "contract_amount": ar.contract_amount,
                "award_rate": ar.award_rate,
                "award_date": ar.award_date,
            })

        total_wins = len(win_list)
        avg_rate = (
            sum((w["award_rate"] or 0) for w in win_list) / total_wins
            if total_wins > 0 else None
        )

        return {
            "id": competitor.id,
            "name": competitor.normalized_name,
            "raw_names": competitor.raw_names,
            "industry": competitor.industry_category,
            "region": competitor.region,
            "is_target": competitor.is_target_company,
            "memo": competitor.memo,
            "total_wins": total_wins,
            "avg_award_rate": round(avg_rate, 2) if avg_rate else None,
            "wins": win_list[:50],
        }

    def get_win_rate_ranking(self, limit: int = 20) -> List[Dict[str, Any]]:
        """落札率ランキングを返す。"""
        summary = self.get_competitor_summary()
        ranked = [s for s in summary if s["wins"] > 0]
        ranked.sort(key=lambda s: (s["wins"], s["win_rate"]), reverse=True)
        return ranked[:limit]

    def get_competitor_trend(self, competitor_id: int, months: int = 6) -> List[Dict[str, Any]]:
        """指定競合の月別落札推移を返す。"""
        cutoff = datetime.utcnow() - timedelta(days=30 * months)
        stmt = (
            select(
                func.strftime("%Y-%m", AwardResult.award_date).label("month"),
                func.count(AwardResult.id).label("wins"),
                func.avg(AwardResult.award_rate).label("avg_rate"),
            )
            .select_from(AwardResult)
            .join(AwardHistory, AwardHistory.award_result_id == AwardResult.id)
            .where(
                AwardHistory.competitor_id == competitor_id,
                AwardHistory.is_winner == True,
                AwardResult.award_date >= cutoff,
            )
            .group_by(func.strftime("%Y-%m", AwardResult.award_date))
            .order_by(func.strftime("%Y-%m", AwardResult.award_date))
        )
        results = self.session.execute(stmt).all()
        return [
            {
                "month": r.month,
                "wins": r.wins or 0,
                "avg_rate": round(float(r.avg_rate), 2) if r.avg_rate else None,
            }
            for r in results
        ]
