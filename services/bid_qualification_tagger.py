"""
Bid Qualification Tagger
案件の資格情報からBidQualificationTagを自動生成する。
"""
import logging
from typing import Any, Dict, List, Optional

from database.engine import get_session
from database.models import Bid, BidQualificationTag, QualificationTag
from database.repositories.bid_repository import BidRepository

logger = logging.getLogger(__name__)


class BidQualificationTagger:
    def __init__(self):
        pass

    def tag_bid_from_text(self, bid_id: int, qualification_text: str) -> int:
        """
        LLM抽出結果などの資格テキストから正規化tagsに変換し登録。
        戻り値: 生成されたBidQualificationTagの件数
        """
        normalized_tags = self._normalize_tags(qualification_text)
        count = 0

        with get_session() as session:
            for tag_code in normalized_tags:
                tag = session.query(QualificationTag).filter(
                    QualificationTag.tag_code == tag_code
                ).first()
                if tag:
                    existing = session.query(BidQualificationTag).filter(
                        BidQualificationTag.bid_id == bid_id,
                        BidQualificationTag.tag_id == tag.id,
                    ).first()
                    if existing:
                        continue
                    session.add(BidQualificationTag(
                        bid_id=bid_id,
                        tag_id=tag.id,
                        raw_text=qualification_text,
                    ))
                    count += 1
            session.flush()

        return count

    def _normalize_tags(self, text: str) -> List[str]:
        if not text:
            return []
        tags_found = []
        # Simple rule-based extraction
        import re
        # Look for patterns like "資格: 建設A", "等级: A"
        patterns = [
            r"資格[:\s]*([A-Za-z0-9]+)",
            r"等级[:\s]*([A-Za-z0-9]+)",
            r"(建設|IT|コンサル|物品|委託|医療|教育)",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for m in matches:
                if m.upper() in ["A", "B", "C", "D"]:
                    tags_found.append(f"QC-{m.upper()}")
                elif m in ["建設", "IT", "コンサル", "物品", "委託", "医療", "教育"]:
                    tags_found.append(f"CAT-{m}")
        return list(set(tags_found))

    def batch_tag_all(self, limit: int = 100) -> Dict[str, int]:
        """未タグ付きの案件を批量処理。"""
        with get_session() as session:
            bids = session.query(Bid).offset(0).limit(limit).all()
            stats = {"processed": 0, "tagged": 0, "skipped": 0}

            for bid in bids:
                if not bid.qualifications:
                    stats["skipped"] += 1
                    continue
                count = self.tag_bid_from_text(bid.id, bid.qualifications or "")
                stats["tagged"] += count
                stats["processed"] += 1

        return stats