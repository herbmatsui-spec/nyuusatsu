from fastapi import APIRouter, Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from database.engine import SessionLocal
from database.repositories import SavedSearchRepository, NotificationChannelRepository
from services.auth_service import AuthService
from search_api.schemas import (
    SavedSearchCreate,
    SavedSearchUpdate,
    SavedSearchResponse,
    AlertConfigCreate,
    AlertConfigResponse,
)

router = APIRouter(prefix="/me", tags=["user"])

security = HTTPBearer()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db),
):
    """JWT bearer トークンからユーザーを取得する依存関数。"""
    auth_service = AuthService(db)
    user = auth_service.get_current_user(credentials.credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# ---------------------------------------------------------------------------
# Saved searches
# ---------------------------------------------------------------------------

@router.get("/saved_searches", response_model=list[SavedSearchResponse])
async def list_saved_searches(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """ログインユーザーの保存検索一覧を取得する。"""
    repo = SavedSearchRepository(db)
    return repo.filter_by(user_id=current_user.id)


@router.post("/saved_searches", response_model=SavedSearchResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_search(
    request: SavedSearchCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """保存検索を新規作成する。"""
    repo = SavedSearchRepository(db)
    saved = repo.create(
        user_id=current_user.id,
        name=request.name,
        criteria_json=request.criteria_json,
        is_active=request.is_active,
    )
    return saved


@router.get("/saved_searches/{saved_search_id}", response_model=SavedSearchResponse)
async def read_saved_search(
    saved_search_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """保存検索の詳細を取得する。"""
    repo = SavedSearchRepository(db)
    saved = repo.get_by_id(saved_search_id)
    if not saved or saved.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Saved search not found")
    return saved


@router.put("/saved_searches/{saved_search_id}", response_model=SavedSearchResponse)
async def update_saved_search(
    saved_search_id: int,
    request: SavedSearchUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """保存検索を更新する。"""
    repo = SavedSearchRepository(db)
    saved = repo.get_by_id(saved_search_id)
    if not saved or saved.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Saved search not found")
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(saved, key, value)
    repo.save(saved)
    return saved


@router.delete("/saved_searches/{saved_search_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_search(
    saved_search_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """保存検索を削除する。"""
    repo = SavedSearchRepository(db)
    saved = repo.get_by_id(saved_search_id)
    if not saved or saved.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Saved search not found")
    repo.delete(saved)
    return None


# ---------------------------------------------------------------------------
# Alert settings
# ---------------------------------------------------------------------------

@router.get("/alerts", response_model=list[AlertConfigResponse])
async def list_alerts(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """ログインユーザーのアラート設定一覧を取得する。"""
    repo = NotificationChannelRepository(db)
    return repo.get_active_by_user(str(current_user.id))


@router.post("/alerts", response_model=AlertConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(
    request: AlertConfigCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """アラート設定を新規作成する。"""
    repo = NotificationChannelRepository(db)
    alert = repo.create(
        user_id=str(current_user.id),
        channel_type=request.channel_type,
        email_address=request.email_address,
        webhook_url=request.webhook_url,
        is_active=request.is_active,
    )
    return alert


@router.put("/alerts/{alert_id}", response_model=AlertConfigResponse)
async def update_alert(
    alert_id: int,
    request: AlertConfigCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """アラート設定を更新する。"""
    repo = NotificationChannelRepository(db)
    alert = repo.get_by_id(alert_id)
    if not alert or alert.user_id != str(current_user.id):
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.channel_type = request.channel_type
    alert.email_address = request.email_address
    alert.webhook_url = request.webhook_url
    alert.is_active = request.is_active
    repo.save(alert)
    return alert
