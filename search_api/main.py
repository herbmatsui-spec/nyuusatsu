from fastapi import FastAPI, HTTPException, Query, Depends
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import uvicorn
from database.repositories import BidRepository
from services.bid_service import BidService
from database.engine import SessionLocal
from services.qualification_normalizer import QualificationNormalizer
from services.llm_service import LLMService
from config import AppConfig

app = FastAPI(title="Bid Search API")

from search_api.metrics_api import router as metrics_router
app.include_router(metrics_router)

# Dependency injection for DB and Service
def get_bid_service():
    db = SessionLocal()
    try:
        repo = BidRepository(db)
        yield BidService(repo)
    finally:
        db.close()

# Dependency injection for LLM Service
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

# Dependency injection for Qualification Normalizer Service
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

@app.get("/search", response_model=List[BidSearchResponse])
async def search_bids(
    budget: Optional[str] = Query(None),
    qualification: Optional[str] = Query(None),
    deadline: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    service: BidService = Depends(get_bid_service)
):
    filters = {}
    if budget: filters["budget"] = budget
    if qualification: filters["qualification"] = qualification
    if deadline: filters["deadline"] = deadline
    if q: filters["q"] = q # Full-text search
    
    try:
        results = service.get_all_bids(filters)
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