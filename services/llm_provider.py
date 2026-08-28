from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from openai import OpenAI
from openai import APIConnectionError, RateLimitError, APIStatusError
from config import AppConfig
from exceptions import LLMConnectionError, LLMResponseParseError, RateLimitExceededError
from utils.rate_limiter import deepseek_limiter, gemini_limiter
from utils.usage_tracker import log_api_usage
from tenacity import retry, stop_after_attempt, wait_exponential
import logging
import json

# Handle optional google genai import
try:
    from google import genai
except ImportError:
    genai = None

logger = logging.getLogger(__name__)

class LLMProvider(ABC):
    @abstractmethod
    def analyze(self, text: str, system_prompt: str) -> Dict[str, Any]:
        pass

class DeepSeekProvider(LLMProvider):
    def __init__(self, api_key: str, config: AppConfig):
        self.client = OpenAI(base_url=config.llm.deepseek_base_url, api_key=api_key)
        self.model = config.llm.deepseek_model
        self.config = config

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def analyze(self, text: str, system_prompt: str) -> Dict[str, Any]:
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
            # Token usage tracking
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
            # Treat as connection error or maybe parse? We'll treat as connection error for simplicity.
            raise LLMConnectionError(f"APIステータスエラー: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise LLMResponseParseError(f"JSONパースエラー: {exc}") from exc
        except Exception as exc:
            # Catch-all for unexpected errors
            raise LLMConnectionError(f"予期しないエラー: {exc}") from exc

class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, config: AppConfig):
        self.client = genai.Client(api_key=api_key)
        self.model = config.llm.gemini_model_name
        self.config = config

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def analyze(self, text: str, system_prompt: str) -> Dict[str, Any]:
        try:
            gemini_limiter.wait_and_consume(tokens=len(text)//4)
            
            # Note: System prompt is handled differently in Gemini SDK
            response = self.client.models.generate_content(
                model=self.model,
                contents=f"{system_prompt}\n\nText to analyze:\n{text}",
                config={
                    "response_mime_type": "application/json",
                }
            )
            
            # Gemini returns parsed object or string
            content = response.text if hasattr(response, 'text') else str(response)
            
            # Approximation for tokens since SDK varies
            log_api_usage("gemini", self.model, len(text)//4, 500) 
            
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMResponseParseError(f"JSONパースエラー: {exc}") from exc
        except Exception as exc:
            # For any other error, treat as connection error (could be more specific)
            raise LLMConnectionError(f"Gemini APIエラー: {exc}") from exc

class LLMService:
    """
    LLM呼び出しをプライマリ/セカンダリフォールバックでオーケストレーションする。
    """
    def __init__(self, deepseek_key: Optional[str], gemini_key: Optional[str], config: AppConfig):
        self.config = config
        self.providers = []
        
        if deepseek_key:
            self.providers.append(DeepSeekProvider(deepseek_key, config))
        if gemini_key:
            self.providers.append(GeminiProvider(gemini_key, config))
        
        if not self.providers:
            raise RuntimeError("有効なLLM APIキーが提供されていません。")

    def analyze_with_fallback(self, text: str) -> Dict[str, Any]:
        last_exception = None
        for provider in self.providers:
            try:
                return provider.analyze(text, self.config.llm.system_prompt)
            except Exception as e:
                logger.warning(f"Provider {provider.__class__.__name__} failed: {e}")
                last_exception = e
                continue
        
        raise RuntimeError(f"すべてのLLMプロバイダーが失敗しました。最後のエラー: {last_exception}")
