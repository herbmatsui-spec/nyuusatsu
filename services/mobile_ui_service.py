import json
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import and_, or_

from database.engine import get_session
from database.models import Bid, NotificationChannel, SavedSearch, User
from services.auth_service import AuthService
from utils.session_manager import get_session_manager
from database.repositories.bid_repository import BidRepository


PAGE_SIZE = 20


def authenticated_user(session, session_id: str):
    username = get_session_manager().get_username(session_id)
    if not username:
        raise PermissionError("ログインが必要です")
    user = session.query(User).filter_by(username=username, is_active=True).first()
    if user is None:
        raise PermissionError("ログインが必要です")
    return user


def login(username: str, password: str) -> str | None:
    with get_session() as session:
        user = AuthService(session).authenticate(username, password)
        if user is None:
            return None
        return get_session_manager().create_session(user.username)


def saved_searches(session_id: str) -> list[dict]:
    with get_session() as session:
        user = authenticated_user(session, session_id)
        rows = session.query(SavedSearch).filter_by(user_id=user.id).order_by(SavedSearch.updated_at.desc()).all()
        return [{"id": row.id, "name": row.name, "criteria_json": row.criteria_json} for row in rows]


def save_search(session_id: str, name: str, criteria: dict, saved_id: int | None = None) -> int:
    if not name.strip() or len(name.strip()) > 100:
        raise ValueError("検索名は1〜100文字で入力してください")
    payload = json.dumps({"mobile_ui": criteria}, default=str, ensure_ascii=False)
    with get_session() as session:
        user = authenticated_user(session, session_id)
        if saved_id is None:
            row = SavedSearch(user_id=user.id, created_at=now_utc(), is_active=False)
            session.add(row)
        else:
            row = session.query(SavedSearch).filter_by(id=saved_id, user_id=user.id).first()
            if row is None:
                raise PermissionError("保存検索が見つかりません")
        row.name = name.strip()
        row.criteria_json = payload
        row.updated_at = now_utc()
        session.commit()
        return row.id


def delete_search(session_id: str, saved_id: int) -> None:
    with get_session() as session:
        user = authenticated_user(session, session_id)
        row = session.query(SavedSearch).filter_by(id=saved_id, user_id=user.id).first()
        if row is None:
            raise PermissionError("保存検索が見つかりません")
        session.delete(row)
        session.commit()


def search(criteria: dict, offset: int = 0) -> dict:
    start = criteria["start"]
    end = criteria["end"]
    if not isinstance(start, date) or not isinstance(end, date) or start > end:
        raise ValueError("公開日の範囲が不正です")
    if offset < 0:
        raise ValueError("取得位置が不正です")
    with get_session() as session:
        query = session.query(
            Bid.id, Bid.filename, Bid.organization_name,
            Bid.announcement_date, Bid.prefecture_code,
        )
        for term in criteria.get("keyword", "").split():
            query = query.filter(or_(
                Bid.filename.contains(term, autoescape=True),
                Bid.notes.contains(term, autoescape=True),
            ))
        codes = criteria.get("prefectures", [])
        if codes:
            query = query.filter(Bid.prefecture_code.in_([f"{int(code):02d}" for code in codes]))
        organization = criteria.get("organization", "").strip()
        if organization:
            query = query.filter(Bid.organization_name.contains(organization, autoescape=True))
        query = query.filter(and_(
            Bid.announcement_date >= datetime.combine(start, time.min),
            Bid.announcement_date < datetime.combine(end, time.min) + timedelta(days=1),
        ))
        total = query.count()
        rows = query.order_by(Bid.announcement_date.desc(), Bid.id.desc()).offset(offset).limit(PAGE_SIZE).all()
        return {
            "results": [dict(row._mapping) for row in rows],
            "total": total,
            "offset": offset,
        }


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def account_summary(session_id: str) -> dict:
    with get_session() as session:
        user = authenticated_user(session, session_id)
        from config import PlanConfig
        from services.billing_service import get_effective_plan, is_trial_active

        trial = is_trial_active(user)
        effective = get_effective_plan(user)
        plans = PlanConfig()
        return {
            "username": user.username,
            "plan_display": plans.DISPLAY_NAMES.get(effective, effective),
            "plan_code": user.plan,
            "trial_active": trial,
            "trial_ends_at": user.trial_ends_at,
            "subscription_status": user.subscription_status or "inactive",
            "current_period_end": user.current_period_end,
            "next_billing_note": "次回請求日はStripeポータルで確認してください（APIから取得できません）。",
        }


def notification_channels(session_id: str) -> list[dict]:
    with get_session() as session:
        user = authenticated_user(session, session_id)
        rows = session.query(NotificationChannel).filter_by(user_id=str(user.id)).all()
        return [{
            "id": row.id, "channel_type": row.channel_type, "is_active": bool(row.is_active),
            "email_address": row.email_address, "webhook_url": row.webhook_url,
        } for row in rows]


def set_notification_channel(session_id: str, channel_type: str, is_active: bool, destination: str = "") -> dict:
    if channel_type not in {"email", "slack", "teams", "line"}:
        raise ValueError("対応していない通知先です")
    if channel_type == "email":
        if not destination or "@" not in destination:
            raise ValueError("有効なメールアドレスを入力してください")
    with get_session() as session:
        user = authenticated_user(session, session_id)
        row = session.query(NotificationChannel).filter_by(user_id=str(user.id), channel_type=channel_type).first()
        now = now_utc()
        if row is None:
            row = NotificationChannel(user_id=str(user.id), channel_type=channel_type, created_at=now, updated_at=now)
            session.add(row)
        row.is_active = is_active
        if channel_type == "email":
            row.email_address = destination
        elif destination:
            row.webhook_url = destination
        row.updated_at = now
        session.commit()
        return {"id": row.id, "channel_type": row.channel_type, "is_active": bool(row.is_active)}


def enqueue_latest_refresh(session_id: str) -> int:
    """既存のバックフィルジョブを作成して投入し、ジョブIDを返す（実行はワーカー次第）。"""
    with get_session() as session:
        authenticated_user(session, session_id)
        from database.models import Agency
        from services.backfill_service import BackfillService

        agency = session.query(Agency).first()
        if agency is None:
            raise LookupError("再取得対象の機関が未登録です。管理者に問い合わせてください。")
        job = BackfillService().create_job(
            agency_id=agency.id,
            start_date=date.today() - timedelta(days=7),
            end_date=date.today(),
        )
        return int(job.id)


def job_status(job_id: int) -> dict:
    from database.models import BackfillJob
    from database.session import get_db

    db = next(get_db())
    try:
        job = db.get(BackfillJob, job_id)
        if job is None:
            return {"status": "unknown", "message": "ジョブが見つかりません"}
        return {
            "status": job.status.value if hasattr(job.status, "value") else str(job.status),
            "fetched_count": job.fetched_count or 0,
            "new_count": job.new_count or 0,
            "error_count": job.error_count or 0,
        }
    finally:
        db.close()


def detail(bid_id: int) -> dict | None:
    with get_session() as session:
        bid = BidRepository(session).get_by_id(bid_id)
        if bid is None:
            return None
        return {column.name: getattr(bid, column.name) for column in Bid.__table__.columns}
