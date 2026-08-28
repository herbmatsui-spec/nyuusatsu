"""QA 修正パイプライン

- `apply_fix` : QA で承認されたレビューの内容を `bids` テーブルへ反映し、レビュー状態を APPROVED に更新
- `reject` : レビューを REJECTED にし、理由を `note` に保存

このモジュールは管理画面やバッチから呼び出されます。
"""

from sqlalchemy.orm import Session
from datetime import datetime

from database.models import Bid
from database.models.qa_review import QAReview, QAStatusEnum


def apply_fix(session: Session, review_id: int, corrected_fields: dict) -> Bid:
    """QA レビュー ID と修正フィールドを受け取り、Bid を更新しレビューを APPROVED にする。"""
    review = session.query(QAReview).filter_by(id=review_id).first()
    if not review:
        raise ValueError(f"QAReview {review_id} not found")
    bid = session.query(Bid).filter_by(id=review.bid_id).first()
    if not bid:
        raise ValueError(f"Bid {review.bid_id} not found for review {review_id}")
    # フィールド更新（存在するカラムのみ更新）
    for key, value in corrected_fields.items():
        if hasattr(bid, key):
            setattr(bid, key, value)
    bid.updated_at = datetime.utcnow()
    # レビュー状態更新
    review.status = QAStatusEnum.APPROVED
    review.reviewed_at = datetime.utcnow()
    session.commit()
    return bid


def reject(session: Session, review_id: int, reason: str) -> QAReview:
    """レビューを REJECTED とし、理由を note に保存。"""
    review = session.query(QAReview).filter_by(id=review_id).first()
    if not review:
        raise ValueError(f"QAReview {review_id} not found")
    review.status = QAStatusEnum.REJECTED
    review.note = (review.note or "") + f"\nReject reason: {reason}"
    review.reviewed_at = datetime.utcnow()
    session.commit()
    return review
