from openai import OpenAI
from openai import APIConnectionError, RateLimitError, APIStatusError
from config import AppConfig
from exceptions import LLMConnectionError, LLMResponseParseError, RateLimitExceededError
from utils.rate_limiter import deepseek_limiter
from utils.usage_tracker import log_api_usage
from tenacity import retry, stop_after_attempt, wait_exponential
import logging
import json
from .base import LLMProvider
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class DeepSeekProvider(LLMProvider):
    def __init__(self, api_key: Optional[str], config: AppConfig):
        self.config = config
        self.api_key = api_key
        self.model = config.llm.deepseek_model
        if api_key:
            self.client = OpenAI(base_url=config.llm.deepseek_base_url, api_key=api_key)
        else:
            self.client = None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def analyze(self, text: str, system_prompt: str) -> Dict[str, Any]:
        if not self.client:
            raise LLMConnectionError("DeepSeek API key not configured. Skipping this provider.")
        try:
            deepseek_limiter.wait_and_consume(tokens=len(text)//4)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            
            content = response.choices[0].message.content or "{}"
            log_api_usage(
                "deepseek", 
                self.model, 
                response.usage.prompt_tokens, 
                response.usage.completion_tokens
            )
            return json.loads(content)
        except APIConnectionError as exc:
            raise LLMConnectionError(f"API接続エラー: {exc}") from exc
        except RateLimitError as exc:
            raise RateLimitExceededError(f"レート制限超過: {exc}") from exc
        except APIStatusError as exc:
            raise LLMConnectionError(f"APIステータスエラー: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise LLMResponseParseError(f"JSONパースエラー: {exc}") from exc
        except Exception as exc:
            raise LLMConnectionError(f"予期しないエラー: {exc}") from exc