"""
Competitor CRUD Service
競合企業の作成・更新・削除・一覧取得を提供する。
"""
import logging
from typing import Any, Dict, List, Optional

from database.engine import get_session
from database.models import Competitor
from database.repositories.competitor_repository import CompetitorRepository

logger = logging.getLogger(__name__)


class CompetitorCrudService:
    def __init__(self):
        pass

    def _get_repo(self, session):
        return CompetitorRepository(session)

    def create_competitor(self, data: Dict[str, Any]) -> Optional[Competitor]:
        with get_session() as session:
            repo = self._get_repo(session)
            try:
                obj = repo.create(data)
                logger.info(f"Created competitor: {obj.normalized_name}")
                return obj
            except Exception as e:
                logger.error(f"Failed to create competitor: {e}")
                return None

    def update_competitor(self, competitor_id: int, data: Dict[str, Any]) -> Optional[Competitor]:
        with get_session() as session:
            repo = self._get_repo(session)
            obj = repo.get_by_id(competitor_id)
            if not obj:
                logger.warning(f"Competitor not found: id={competitor_id}")
                return None
            updated = repo.update(obj, data)
            logger.info(f"Updated competitor: {updated.normalized_name}")
            return updated

    def delete_competitor(self, competitor_id: int) -> bool:
        with get_session() as session:
            repo = self._get_repo(session)
            obj = repo.get_by_id(competitor_id)
            if not obj:
                return False
            repo.delete(obj)
            logger.info(f"Deleted competitor: id={competitor_id}")
            return True

    def list_competitors(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        with get_session() as session:
            repo = self._get_repo(session)
            items = repo.list_all()
            results = []
            for item in items:
                d = {
                    "id": item.id,
                    "normalized_name": item.normalized_name,
                    "raw_names": item.raw_names,
                    "industry_category": item.industry_category,
                    "region": item.region,
                    "is_target_company": item.is_target_company,
                    "memo": item.memo,
                }
                results.append(d)
            return results

    def set_target(self, competitor_id: int, is_target: bool) -> bool:
        with get_session() as session:
            repo = self._get_repo(session)
            obj = repo.get_by_id(competitor_id)
            if not obj:
                return False
            repo.update(obj, {"is_target_company": is_target})
            return True

    def export_to_csv(self, filepath: str) -> int:
        import csv
        items = self.list_competitors()
        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "normalized_name", "industry_category", "region", "is_target_company"])
            writer.writeheader()
            for item in items:
                writer.writerow(item)
        return len(items)

    def export_to_json(self, filepath: str) -> int:
        import json
        items = self.list_competitors()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        return len(items)
