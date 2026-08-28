"""QAレビュー割当サービス

- `assign_reviewer(review_id, reviewer_name)` で特定レビューに担当者を設定
- `auto_balance()` は未割当のレビューを取得し、`User` テーブルの active ユーザーを順番に割り当てる（簡易ラウンドロビン）
- 本サービスは管理画面から呼び出すことを想定
"""

from typing import List

from sqlalchemy.orm import Session

from database.models.qa_review import QAReview, QAStatusEnum
from database.models.user import User


def assign_reviewer(session: Session, review_id: int, reviewer_name: str) -> QAReview:
    """レビューに担当者を設定しステータスを REVIEWING に更新"""
    review = session.query(QAReview).filter_by(id=review_id).first()
    if not review:
        raise ValueError(f"QAReview {review_id} not found")
    review.reviewer = reviewer_name
    review.status = QAStatusEnum.REVIEWING
    session.commit()
    return review


def auto_balance(session: Session) -> List[QAReview]:
    """未割当レビューに対してアクティブユーザーを順番に割り当てる。
    戻り値は割り当てが行われた QAReview オブジェクトのリスト。
    """
    pending_reviews = session.query(QAReview).filter(QAReview.status == QAStatusEnum.PENDING).all()
    if not pending_reviews:
        return []
    # アクティブユーザーを取得（簡易条件: is_active が True かつ username が設定）
    users = session.query(User).filter(User.is_active == True).all()
    if not users:
        raise RuntimeError("No active users available for QA assignment")
    assigned = []
    for i, review in enumerate(pending_reviews):
        reviewer = users[i % len(users)]
        review.reviewer = reviewer.username
        review.status = QAStatusEnum.REVIEWING
        assigned.append(review)
    session.commit()
    return assigned
