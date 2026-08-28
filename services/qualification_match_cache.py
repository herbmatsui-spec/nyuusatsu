"""
Qualification Match Cache
マッチング结果のRedis/SQLiteキャッシュ。
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from database.engine import get_session
from database.models import SystemSetting

logger = logging.getLogger(__name__)

CACHE_TTL_HOURS = 1


def _get_cache_key(company_profile_id: int, bid_id: int) -> str:
    return f"qual_match:{company_profile_id}:{bid_id}"


def get_cached_match(company_profile_id: int, bid_id: int) -> Optional[dict]:
    """キャッシュされたマッチ結果を返す。期限切れはNone。"""
    with get_session() as session:
        setting = session.query(SystemSetting).filter(
            SystemSetting.key == _get_cache_key(company_profile_id, bid_id)
        ).first()

        if not setting:
            return None

        try:
            data = json.loads(setting.value)
            updated_at = datetime.fromisoformat(data.get("updated_at", "2000-01-01"))
            if datetime.utcnow() - updated_at > timedelta(hours=CACHE_TTL_HOURS):
                return None
            return data
        except (json.JSONDecodeError, ValueError):
            return None


def set_cached_match(company_profile_id: int, bid_id: int, match_data: dict) -> None:
    """マッチ結果をキャッシュに保存（1時間TTL）。"""
    cache_key = _get_cache_key(company_profile_id, bid_id)
    data = {
        **match_data,
        "updated_at": datetime.utcnow().isoformat(),
    }

    with get_session() as session:
        setting = session.query(SystemSetting).filter(
            SystemSetting.key == cache_key
        ).first()

        if setting:
            setting.value = json.dumps(data, ensure_ascii=False, default=str)
        else:
            setting = SystemSetting(key=cache_key, value=json.dumps(data, ensure_ascii=False, default=str))
            session.add(setting)
        session.commit()


def clear_cache(company_profile_id: Optional[int] = None) -> int:
    """キャッシュをクリア。company_profile_id 指定なし時は全削除。"""
    with get_session() as session:
        q = session.query(SystemSetting).filter(
            SystemSetting.key.like("qual_match:%")
        )
        if company_profile_id is not None:
            q = q.filter(SystemSetting.key.like(f"qual_match:{company_profile_id}:%"))
        count = q.delete()
        session.commit()
    logger.info(f"Cleared {count} qualification match cache entries")
    return count