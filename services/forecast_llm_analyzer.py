import json
import os
from typing import Dict, Any, Optional

from config import AppConfig
from services.llm_service import LLMService
from utils.forecast_logger import ForecastLogger


class ForecastLlmAnalyzer:
    """低性能LLM（gemini-flash-lite等）でも動作するよう、簡易プロンプトで解析する。"""

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig()
        self.logger = ForecastLogger("LlmAnalyzer")
        self.prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts", "forecast_analysis_prompt.txt")

    def _load_prompt(self) -> str:
        try:
            with open(self.prompt_path, encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return "以下の発注見通しテキストからJSON形式で情報を抽出してください。"

    def analyze(self, text: str) -> Dict[str, Any]:
        prompt = self._load_prompt().replace("{{text}}", text[: self.config.forecast_crawl.forecast_max_text_chars])
        try:
            result = self._call_llm(prompt)
            return self._parse_json(result)
        except Exception as e:
            self.logger.error(f"LLM analysis failed", error=str(e))
            return {"raw_text": text, "error": str(e)}

    def _call_llm(self, prompt: str) -> str:
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        gemini_key = os.getenv("GEMINI_API_KEY")
        service = LLMService(deepseek_key, gemini_key, self.config)
        result = service.analyze_with_fallback(prompt)
        if isinstance(result, dict):
            return result.get("content", "") or json.dumps(result)
        return str(result)

    def _parse_json(self, text: str) -> Dict[str, Any]:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[-2] if "```" in text[3:] else text
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 最初の { から最後の } を抽出して再挑戦
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    pass
            return {}
