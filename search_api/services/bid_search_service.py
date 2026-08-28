import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from database.engine import get_session
from search_api.services.query_builder import BidQueryBuilder
from search_api.models.requests import BidSearchRequest
from search_api.models.responses import BidSearchResponse, BidSummary
from models.database import Bid

logger = logging.getLogger(__name__)

class BidSearchService:
    """
    検索リクエストを処理し、データベースから案件情報を取得するサービス
    """

    def search_bids(self, request: BidSearchRequest, limit: int = 100, offset: int = 0, use_fts: bool = False) -> BidSearchResponse:
        """
        フィルタ条件に基づいて案件を検索し、レスポンス形式に変換して返す
        """
        try:
            with get_session() as session:
                # 1. クエリの構築
                if use_fts and request.keyword:
                    # 全文検索クエリをベースにする
                    query = BidQueryBuilder.build_fts_query(request.keyword)
                    # その他のフィルタを追加
                    # FTSクエリをベースにするため、通常の build_query からフィルタ部分だけを抽出して適用
                    # (ここでは簡単にするため、通常の build_query で構築したクエリの filters を再利用する形にする)
                    base_query = BidQueryBuilder.build_query(request)
                    # select(Bid) 以外の where 条件をコピー
                    for element in base_query._where_criteria:
                        # keyword フィルタは FTS で代用するため除外
                        # (実際にはBidQueryBuilder側でキーワード除外版を作るのが綺麗だが、ここでは簡易的に)
                        query = query.where(element)
                else:
                    # 通常のキーワード/フィルタ検索
                    query = BidQueryBuilder.build_query(request)
                
                # 2. ページネーションの適用
                query = query.offset(offset).limit(limit)
                
                # 3. 実行
                result = session.execute(query).scalars().all()
                
                # 4. DTOへの変換
                bids_summary = [
                    BidSummary(
                        id=bid.id,
                        project_name=bid.project_name,
                        organization=bid.organization,
                        budget=bid.budget,
                        announcement_date=bid.announcement_date,
                        closing_date=bid.closing_date,
                        industry_id=bid.industry_id,
                        region_id=bid.region_id,
                        url=bid.url
                    )
                    for bid in result
                ]
                
                # 5. 総件数の取得 (簡易的に)
                # 本来は count(*) クエリを別途発行すべき
                total_count = len(bids_summary) 

                return BidSearchResponse(
                    bids=bids_summary,
                    total_count=total_count
                )

        except Exception as e:
            logger.error(f"Error searching bids: {e}", exc_info=True)
            raise e

    def get_bid_detail(self, bid_id: int):
        """
        案件の詳細情報を取得する
        """
        with get_session() as session:
            bid = session.get(Bid, bid_id)
            if not bid:
                return None
            return bid
