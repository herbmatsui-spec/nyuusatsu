"""
Generate Award Report
日次の落札結果運用レポートを生成する。
"""
import logging
import json
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger(__name__)


def generate_daily_award_report() -> Dict[str, Any]:
    """
    日次の落札結果レポートをdictで返す。
    スケジューラから日次実行することを想定。
    """
    try:
        from database.engine import get_session
        from services.award_quality_checker import get_quality_report
        from services.competitor_dashboard_service import CompetitorDashboardService
        from database.repositories.award_result_repository import AwardResultRepository
        from database.models import AwardResult
        from sqlalchemy import func, select

        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "period": "daily",
        }

        with get_session() as session:
            quality = get_quality_report(session)
            report["data_quality"] = quality

            dash = CompetitorDashboardService(session)
            summary = dash.get_competitor_summary()
            report["competitor_summary"] = {
                "total_competitors": len(summary),
                "total_bids": sum(s["total_bids"] for s in summary),
                "target_companies": sum(1 for s in summary if s["is_target"]),
            }

            award_repo = AwardResultRepository(session)
            new_count = award_repo.count_all()
            report["award_count"] = new_count

            avg_stmt = select(func.avg(AwardResult.award_rate)).where(AwardResult.award_rate.is_not(None))
            avg_result = session.execute(avg_stmt).scalar()
            report["avg_award_rate"] = round(float(avg_result), 2) if avg_result else None

        logger.info(f"Daily award report generated: {json.dumps(report, ensure_ascii=False, default=str)}")
        return report
    except Exception as e:
        logger.error(f"Failed to generate award report: {e}")
        return {"error": str(e)}


if __name__ == "__main__":
    report = generate_daily_award_report()
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
