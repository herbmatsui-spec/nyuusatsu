import logging
from typing import Any, List, Optional
from sqlalchemy import select, and_, or_, text
from sqlalchemy.orm import Session
from models.database import Bid, Industry, Region
from search_api.models.requests import BidSearchRequest

logger = logging.getLogger(__name__)

class BidQueryBuilder:
    """
    BidSearchRequest のフィルタ条件を SQLAlchemy クエリに変換するクラス
    """

    @staticmethod
    def build_query(request: BidSearchRequest) -> Any:
        """
        検索リクエストに基づいた SQLAlchemy select 文を構築する
        """
        query = select(Bid)
        filters = []

        # 1. キーワード検索 (案件名, 発注機関)
        if request.keyword:
            keyword = f"%{request.keyword}%"
            filters.append(
                or_(
                    Bid.project_name.ilike(keyword),
                    Bid.organization.ilike(keyword)
                )
            )

        # 2. 金額範囲フィルタ
        if request.min_budget is not None:
            filters.append(Bid.budget >= request.min_budget)
        if request.max_budget is not None:
            filters.append(Bid.budget <= request.max_budget)

        # 3. 日付範囲フィルタ (公告日)
        if request.start_date:
            filters.append(Bid.announcement_date >= request.start_date)
        if request.end_date:
            filters.append(Bid.announcement_date <= request.end_date)

        # 4. 業種フィルタ (Industry ID)
        if request.industry_ids:
            filters.append(Bid.industry_id.in_(request.industry_ids))

        # 5. 地域フィルタ (Region ID)
        if request.region_ids:
            filters.append(Bid.region_id.in_(request.region_ids))

        if filters:
            query = query.where(and_(*filters))

        # デフォルトのソート (公告日の降順)
        query = query.order_by(Bid.announcement_date.desc())

        return query

    @staticmethod
    def build_fts_query(keyword: str) -> Any:
        """
        SQLite FTS5 を使用した全文検索クエリを構築する
        """
        # FTS5 の MATCH 演算子を使用して、bids_fts テーブルから ID を取得し、
        # それを Bid モデルのフィルタとして使用する
        # 注意: SQLite の MATCH 演算子は SQLAlchemy の標準関数にないため、text() を使用する
        
        # シンプルなキーワード検索。必要に応じてクエリの正規化（空白を OR に変換など）を行う
        fts_keyword = keyword.strip()
        
        # bids_fts から ID を取得するサブクエリ
        fts_subquery = select(text("rowid")).select_from(text("bids_fts")).where(text("bids_fts MATCH :k")).params(k=fts_keyword)
        
        return select(Bid).where(Bid.id.in_(fts_subquery))
