import logging
from typing import Any, Optional
from sqlalchemy.orm import Session
from database.engine import get_session
from models.database import SearchQuery
from search_api.models.requests import BidSearchRequest
import json

logger = logging.getLogger(__name__)

class SearchHistoryService:
    """
    検索履歴をデータベースに保存・管理するサービス
    """

    def save_search_history(self, user_id: Optional[int], request: BidSearchRequest, result_count: int):
        """
        実行された検索クエリと結果件数を保存する
        """
        try:
            with get_session() as session:
                # 検索条件をJSON文字列に変換
                query_params = request.model_dump_json()
                
                search_record = SearchQuery(
                    user_id=user_id,
                    query_text=query_params,
                    result_count=result_count
                )
                
                session.add(search_record)
                session.commit()
                logger.info(f"Saved search history: {query_params} with {result_count} results")
        except Exception as e:
            logger.error(f"Error saving search history: {e}", exc_info=True)

    def get_recent_searches(self, user_id: Optional[int] = None, limit: int = 10):
        """
        最近の検索履歴を取得する
        """
        from sqlalchemy import select, desc
        
        try:
            with get_session() as session:
                query = select(SearchQuery).order_by(desc(SearchQuery.created_at))
                if user_id:
                    query = query.where(SearchQuery.user_id == user_id)
                
                query = query.limit(limit)
                return session.execute(query).scalars().all()
        except Exception as e:
            logger.error(f"Error retrieving search history: {e}", exc_info=True)
            return []
