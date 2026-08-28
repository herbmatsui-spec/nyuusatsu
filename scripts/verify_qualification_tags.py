"""
Verify Qualification Tags
Bid.qualificationsは非NULLだがBidQualificationTagが0件のBidを検出するスクリプト。
"""
import sys
sys.path.insert(0, ".")

from database.engine import get_session
from database.models import Bid, BidQualificationTag


def verify_qualification_tags() -> dict:
    with get_session() as session:
        all_bids = session.query(Bid).all()
        results = {
            "total": len(all_bids),
            "qual_null": 0,
            "tags_zero": 0,
            "problematic_bids": [],
        }

        for bid in all_bids:
            if not bid.qualifications:
                results["qual_null"] += 1
                continue

            tagged_count = (
                session.query(BidQualificationTag)
                .filter(BidQualificationTag.bid_id == bid.id)
                .count()
            )
            if tagged_count == 0:
                results["tags_zero"] += 1
                results["problematic_bids"].append({
                    "id": bid.id,
                    "filename": bid.filename,
                    "qualifications": bid.qualifications[:100],
                })

        return results


if __name__ == "__main__":
    result = verify_qualification_tags()
    print(f"Total bids: {result['total']}")
    print(f"Qualifications null: {result['qual_null']}")
    print(f"Tags zero (should be tagged): {result['tags_zero']}")
    print(f"First 5 problematic:")
    for p in result["problematic_bids"][:5]:
        print(f"  - [{p['id']}] {p['filename']}: {p['qualifications']}")