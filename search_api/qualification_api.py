from fastapi import FastAPI, HTTPException
from typing import List, Dict, Any
from pydantic import BaseModel
import uvicorn
from services.qualification_normalizer import QualificationNormalizer
from services.llm_service import LLMService
from config import AppConfig

app = FastAPI(title="Qualification Normalizer API")

class QualificationNormalizeRequest(BaseModel):
    texts: List[str]

class QualificationNormalizeResponse(BaseModel):
    results: List[Dict[str, Any]]

@app.post("/qualification/normalize", response_model=QualificationNormalizeResponse)
async def normalize_qualifications(request: QualificationNormalizeRequest):
    """
    参加資格テキストリストを正規化タグにマッピングする
    """
    try:
        # Get API keys from environment
        import os
        from dotenv import load_dotenv
        load_dotenv()
        deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
        gemini_key = os.environ.get("GEMINI_API_KEY")
        
        # Initialize config and LLM service
        config = AppConfig()
        llm_service = LLMService(
            deepseek_key=deepseek_key,
            gemini_key=gemini_key,
            config=config
        )
        
        # Initialize qualification normalizer
        normalizer = QualificationNormalizer(llm_service=llm_service)
        
        # Normalize the qualifications
        results = normalizer.normalize(request.texts)
        return QualificationNormalizeResponse(results=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)