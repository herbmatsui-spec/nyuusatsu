"""
Generate Qualification Report
資格マッチの統計レポートを生成する。
"""
import sys
sys.path.insert(0, ".")

from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def generate_qualification_report() -> dict:
    try:
        from database.engine import get_session
        from database.models import Bid, BidQualificationTag, QualificationTag, CompanyProfile
        from sqlalchemy import func

        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "period": "daily",
        }

        with get_session() as session:
            total_bids = session.query(func.count(Bid.id)).scalar() or 0
            tagged_bids = (
                session.query(func.count(func.distinct(BidQualificationTag.bid_id)))
                .join(Bid, Bid.id == BidQualificationTag.bid_id)
                .scalar()
            ) or 0

            total_tags = session.query(QualificationTag).count()
            grade_a_tags = session.query(QualificationTag).filter(
                QualificationTag.grade_required.in_(["A", "B"])
            ).count()

            company_profiles = session.query(CompanyProfile).count()

            report["bids"] = {
                "total": total_bids,
                "tagged": tagged_bids,
                "untagged": total_bids - tagged_bids,
                "tag_rate": round(tagged_bids / total_bids * 100, 1) if total_bids > 0 else 0,
            }
            report["qualification_tags"] = {
                "total": total_tags,
                "grade_ab": grade_a_tags,
            }
            report["company_profiles"] = company_profiles

        logger.info(f"Qualification report generated: {report}")
        return report

    except Exception as e:
        logger.error(f"Failed to generate qualification report: {e}")
        return {"error": str(e)}


if __name__ == "__main__":
    result = generate_qualification_report()
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))