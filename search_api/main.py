from fastapi import FastAPI, HTTPException, Query, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from pydantic import ValidationError
from typing import Optional, List, Dict, Any
from datetime import date
import uvicorn
import logging

from database.engine import SessionLocal
from database.repositories import BidRepository
from database.models._generated import PricePrediction
from services.bid_service import BidService
from services.qualification_normalizer import QualificationNormalizer
from services.llm_service import LLMService
from config import AppConfig
from search_api.schemas import (
    BidDetail,
    PaginatedResponse,
    PricePredictionSchema,
    PaginationParams,
)
from search_api.forecast_api import router as forecast_router
from search_api.metrics_api import router as metrics_router
from search_api.award_api import router as award_router
from search_api.quality_api import router as quality_router
from search_api.user_api import router as user_router
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Dependency: DB session
def get_db_session() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Dependency: optional user from Bearer token (None when absent/invalid)
def get_optional_user(
    request: Request,
    db: Session = Depends(get_db_session),
):
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from services.auth_service import AuthService
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return None
    token = authorization[len("Bearer "):]
    user = AuthService(db).get_current_user(token)
    return user


# Dependency: prefecture scope from optional user
def get_prefecture_scope(user=Depends(get_optional_user)):
    from utils.plan_gate import get_search_prefecture_scope
    return get_search_prefecture_scope(user)


# Dependency: Bid service (legacy, used by /search endpoint)
def get_bid_service():
    db = SessionLocal()
    try:
        repo = BidRepository(db)
        yield BidService(repo)
    finally:
        db.close()


# Dependency: LLM Service
def get_llm_service():
    config = AppConfig()
    deepseek_key = None
    gemini_key = None
    try:
        from dotenv import load_dotenv
        load_dotenv()
        import os
        deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
        gemini_key = os.environ.get("GEMINI_API_KEY")
    except Exception:
        pass
    yield LLMService(
        deepseek_key=deepseek_key,
        gemini_key=gemini_key,
        config=config
    )


# Dependency: Qualification Normalizer Service
def get_qualification_normalizer_service(llm_service: LLMService = Depends(get_llm_service)):
    yield QualificationNormalizer(llm_service=llm_service)


class BidSearchResponse(BaseModel):
    id: int
    project_name: str
    budget: str
    qualifications: str
    deadline: str
    deliverables: str


class QualificationNormalizeRequest(BaseModel):
    texts: List[str]


class QualificationNormalizeResponse(BaseModel):
    results: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# FastAPI app with metadata
# ---------------------------------------------------------------------------

app = FastAPI(
    title="入札システム API",
    description=(
        "入札情報・落札結果・予測データ・品質メトリクスを提供する API。\n\n"
        "## エンドポイント\n"
        "- **Bids**: 入札案件の検索・詳細取得\n"
        "- **Awards**: 落札結果の検索・詳細取得\n"
        "- **Forecasts**: 発注見通しの検索・詳細取得\n"
        "- **Quality**: データ品質メトリクス取得\n"
        "- **Me**: 保存検索・アラート設定（認証必須）\n"
        "- **Metrics**: パイプラインメトリクス（Prometheus等）"
    ),
    version="1.0.0",
    contact={
        "name": "入札システム開発チーム",
    },
    license_info={"name": "MIT"},
)


# ---------------------------------------------------------------------------
# Error handlers — Steps 9
# ---------------------------------------------------------------------------

class ApiError(BaseModel):
    error: dict


def _error_response(code: str, message: str, details: Optional[dict] = None, status_code: int = 400) -> JSONResponse:
    body = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """統一フォーマットの HTTP エラーレスポンス"""
    body = {"error": {"code": f"HTTP_{exc.status_code}", "message": exc.detail}}
    if exc.headers:
        return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)
    return JSONResponse(status_code=exc.status_code, content=body)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """FastAPI リクエストバリデーションエラーを統一フォーマットで返す"""
    details = []
    for err in exc.errors():
        details.append({
            "loc": err.get("loc", []),
            "msg": err.get("msg", ""),
            "type": err.get("type", ""),
        })
    return _error_response(
        "VALIDATION_ERROR",
        "入力パラメータが無効です",
        details=details,
        status_code=422,
    )


@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
    """Pydantic バリデーションエラーを統一フォーマットで返す"""
    details = [
        {"loc": list(e.get("loc", [])), "msg": e.get("msg", ""), "type": e.get("type", "")}
        for e in exc.errors()
    ]
    return _error_response(
        "VALIDATION_ERROR",
        "入力パラメータが無効です",
        details=details,
        status_code=422,
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """予期しないサーバーエラーを統一フォーマットで返す"""
    logger.error(f"Unhandled exception: {type(exc).__name__}: {exc}", exc_info=True)
    body = {"error": {"code": "INTERNAL_ERROR", "message": "サーバー内部エラーが発生しました"}}
    return JSONResponse(status_code=500, content=body)


# ---------------------------------------------------------------------------
# Include routers — Steps 5, 6, 7
# ---------------------------------------------------------------------------

app.include_router(metrics_router)
app.include_router(forecast_router)
app.include_router(award_router)
app.include_router(quality_router)
app.include_router(user_router)


# ---------------------------------------------------------------------------
# Bid endpoints — Steps 3 & 4
# ---------------------------------------------------------------------------

@app.get("/bids/{bid_id}", response_model=BidDetail, responses={404: {"description": "Bid not found"}})
async def read_bid(
    bid_id: int,
    db: Session = Depends(get_db_session),
    prefecture_scope: Optional[List[str]] = Depends(get_prefecture_scope),
):
    """指定された ID の入札詳細を取得する。

    - **bid_id**: 入札ID
    """
    repo = BidRepository(db)
    bid = repo.get_by_id(bid_id)
    if not bid:
        raise HTTPException(status_code=404, detail="Bid not found")
    if prefecture_scope is not None and bid.prefecture_code not in prefecture_scope:
        raise HTTPException(status_code=404, detail="Bid not found")
    return bid


@app.get("/bids", response_model=PaginatedResponse[BidDetail])
async def search_bids(
    q: Optional[str] = Query(None, description="キーワード検索（案件名・発注機関）"),
    prefecture: Optional[List[str]] = Query(None, description="都道府県コード（複数指定可）"),
    organization: Optional[str] = Query(None, description="発注機関"),
    budget_min: Optional[int] = Query(None, ge=0, description="予算額下限（円）"),
    budget_max: Optional[int] = Query(None, ge=0, description="予算額上限（円）"),
    published_after: Optional[date] = Query(None, description="公告日（開始）"),
    published_before: Optional[date] = Query(None, description="公告日（終了）"),
    page: int = Query(PaginationParams.DEFAULT_PAGE, ge=1, description="ページ番号"),
    size: int = Query(PaginationParams.DEFAULT_SIZE, ge=1, le=PaginationParams.MAX_SIZE, description="ページサイズ"),
    db: Session = Depends(get_db_session),
    prefecture_scope: Optional[List[str]] = Depends(get_prefecture_scope),
):
    """入札案件を検索する。

    クエリパラメータでフィルタを指定でき、ページネーション付きの結果を返す。
    """
    repo = BidRepository(db)
    pref_filter = prefecture[0] if prefecture else None
    results, total = repo.search(
        keyword=q,
        prefecture=pref_filter,
        prefecture_codes=prefecture_scope,
        organization=organization,
        budget_min=budget_min,
        budget_max=budget_max,
        published_after=published_after,
        published_before=published_before,
        offset=(page - 1) * size,
        limit=size,
    )
    total_pages = (total + size - 1) // size if total > 0 else 0
    return PaginatedResponse(
        items=results,
        total=total,
        page=page,
        size=size,
        total_pages=total_pages,
    )


# ---------------------------------------------------------------------------
# Price prediction endpoint — Step 6
# ---------------------------------------------------------------------------

@app.get("/price_predictions/{bid_id}", response_model=List[PricePredictionSchema])
async def get_price_predictions(
    bid_id: int,
    db: Session = Depends(get_db_session),
):
    """指定された入札IDの価格予測データを取得する。"""
    predictions = db.query(PricePrediction).filter(PricePrediction.bid_id == bid_id).all()
    return predictions


# ---------------------------------------------------------------------------
# Existing endpoints (kept for backward compatibility)
# ---------------------------------------------------------------------------

@app.get("/search", response_model=List[BidSearchResponse])
async def search_bids_legacy(
    budget: Optional[str] = Query(None),
    qualification: Optional[str] = Query(None),
    deadline: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    service: BidService = Depends(get_bid_service),
    prefecture_scope: Optional[List[str]] = Depends(get_prefecture_scope),
):
    """[Deprecated] /bids を使用してください。"""
    filters = {}
    if budget: filters["budget"] = budget
    if qualification: filters["qualification"] = qualification
    if deadline: filters["deadline"] = deadline
    if q: filters["q"] = q

    try:
        results = service.get_all_bids(filters, allowed_prefectures=prefecture_scope)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/qualification/normalize", response_model=QualificationNormalizeResponse)
async def normalize_qualifications(
    request: QualificationNormalizeRequest,
    normalizer: QualificationNormalizer = Depends(get_qualification_normalizer_service)
):
    """
    参加資格テキストリストを正規化タグにマッピングする
    """
    try:
        results = normalizer.normalize(request.texts)
        return QualificationNormalizeResponse(results=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
