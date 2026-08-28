import json
import logging
from typing import Dict, Any
from config import AppConfig
from utils.rate_limiter import gemini_limiter
from utils.usage_tracker import log_api_usage
from tenacity import retry, stop_after_attempt, wait_exponential
from .base import LLMProvider

try:
    from google import genai
except ImportError:
    genai = None

logger = logging.getLogger(__name__)

class GeminiProvider(LLMProvider):
    def __init__(self, api_key: Optional[str], config: AppConfig):
        self.config = config
        self.api_key = api_key
        self.model = config.llm.gemini_model_name
        if api_key:
            if genai is None:
                raise ImportError("Gemini SDK not installed")
            self.client = genai.Client(api_key=api_key)
        else:
            self.client = None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def analyze(self, text: str, system_prompt: str) -> Dict[str, Any]:
        if not self.client:
            raise LLMConnectionError("Gemini API key not configured. Skipping this provider.")
        gemini_limiter.wait_and_consume(tokens=len(text)//4)
        
        response = self.client.models.generate_content(
            model=self.model,
            contents=f"{system_prompt}\n\nText to analyze:\n{text}",
            config={
                "response_mime_type": "application/json",
            }
        )
        
        content = response.text if hasattr(response, 'text') else str(response)
        
        log_api_usage("gemini", self.model, len(text)//4, 500) 
        
        return json.loads(content)
