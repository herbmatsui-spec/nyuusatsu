"""品質メトリクスサービス

- 欠落フィールド、重複、カバレッジ率、日々の変化量を取得するユーティリティクラス
- メトリクスは `database.models.quality_metric` に保存され、`quality_alert_service` が評価します
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from database.models import Bid

class QualityMetricsService:
    def __init__(self, session: Session):
        self.session = session

    def count_missing_fields(self) -> dict:
        """必須フィールドが欠落している入札件数をカウントして返す。
        例: {'prefecture_code': 12, 'organization_name': 8, 'budget': 5}
        """
        total = self.session.query(Bid).count()
        missing = {}
        for field in ["prefecture_code", "organization_name", "budget"]:
            cnt = self.session.query(Bid).filter(getattr(Bid, field) == None).count()
            if cnt:
                missing[field] = cnt
        return missing

    def count_duplicates(self) -> int:
        """source_url が重複している件数を返す"""
        # SQLite では GROUP BY と HAVING を使う
        dup_sub = self.session.query(Bid.source_url).group_by(Bid.source_url).having(
            func.count(Bid.id) > 1
        ).subquery()
        dup_count = self.session.query(Bid).filter(Bid.source_url.in_(self.session.query(dup_sub.c.source_url))).count()
        return dup_count

    def coverage_rate(self) -> float:
        """インベントリに対するクロール済件数の比率 (0.0-100.0)"""
        from database.models import AgencyInventory
        total = self.session.query(AgencyInventory).count()
        if total == 0:
            return 0.0
        crawled = self.session.query(AgencyInventory).filter(AgencyInventory.is_crawled == True).count()
        return round((crawled / total) * 100, 2)

    def daily_delta(self, days: int = 1) -> dict:
        """過去 `days` 日間の新規・更新件数変化を返す。簡易実装として新規件数だけ返す。"""
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        new_cnt = self.session.query(Bid).filter(Bid.created_at >= cutoff).count()
        updated_cnt = self.session.query(Bid).filter(Bid.updated_at >= cutoff, Bid.updated_at != Bid.created_at).count()
        return {"new": new_cnt, "updated": updated_cnt}
