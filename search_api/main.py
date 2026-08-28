from fastapi import FastAPI, HTTPException, Query, Depends
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import uvicorn
from database.repositories import BidRepository
from services.bid_service import BidService
from database.engine import SessionLocal

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

class BidSearchResponse(BaseModel):
    id: int
    project_name: str
    budget: str
    qualifications: str
    deadline: str
    deliverables: str

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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
