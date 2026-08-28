from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from config import AppConfig
from exceptions import LLMAnalysisError, LLMConnectionError, LLMResponseParseError
from services.llm_provider import LLMService
from services.qualification_normalizer import QualificationNormalizer
from utils.logger import get_logger
from utils.result_merger import ResultMerger

logger = get_logger(__name__)


class AnalysisServiceCore:
    def __init__(self, config: AppConfig, deepseek_key: str, gemini_key: Optional[str] = None):
        self.config = config
        self.llm_service = LLMService(
            deepseek_key=deepseek_key,
            gemini_key=gemini_key,
            config=config,
        )
        self.normalizer = QualificationNormalizer(
            llm_service=self.llm_service,
            logger=logger.getChild("Normalizer")
        )
        self.logger = logger.getChild(self.__class__.__name__)

    def analyze(self, text: str) -> Dict[str, Any]:
        normalized_text = self._normalize_text(text)
        chunks = self._chunk_text(normalized_text)
        all_results: List[Dict[str, Any]] = []

        for i, chunk in enumerate(chunks):
            self.logger.info("Analyzing chunk %d/%d...", i + 1, len(chunks))
            try:
                result = self.llm_service.analyze_with_fallback(chunk)
                all_results.append(self._normalize(result))
            except LLMConnectionError as exc:
                self.logger.error("Chunk %d LLM接続エラー: %s", i + 1, exc)
                raise
            except LLMResponseParseError as exc:
                self.logger.error("Chunk %d レスポンス解析エラー: %s", i + 1, exc)
                continue
            except json.JSONDecodeError as exc:
                self.logger.error("Chunk %d JSONデコードエラー: %s", i + 1, exc)
                continue
            except Exception as exc:
                self.logger.error("Chunk %d 予期しないエラー: %s", i + 1, exc)
                raise LLMAnalysisError(f"チャンク{i+1}の分析中にエラー: {exc}") from exc

        if not all_results:
            raise LLMAnalysisError("全てのチャンクの分析に失敗しました。")

        merged = ResultMerger(self.config.required_keys).merge(all_results)
        
        # 参加資格の正規化
        if "qualifications" in merged and merged["qualifications"] != "記載なし":
            # 文字列をリストに変換（簡易的な分割）
            qual_text = merged["qualifications"]
            qual_list = [q.strip() for q in qual_text.split("、") if q.strip()]
            merged["normalized_qualifications"] = self.normalizer.normalize(qual_list)
            
        return merged

    def _normalize_text(self, text: str) -> str:
        from utils.text_processor import normalize_text
        return normalize_text(text)

    def _chunk_text(self, text: str) -> List[str]:
        from utils.text_processor import chunk_text
        return chunk_text(text, max_chars=self.config.chunking.max_text_chars)

    def _normalize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for key in self.config.required_keys:
            value = data.get(key)
            if value is None or (isinstance(value, str) and not value.strip()):
                result[key] = "記載なし"
            else:
                result[key] = str(value).strip()
        return result

    @staticmethod
    def parse_json(content: str) -> Dict[str, Any]:
        if not content or not content.strip():
            raise LLMAnalysisError("APIから空のレスポンスが返されました。")
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError as exc:
                    raise LLMAnalysisError(
                        f"JSONのパースに失敗しました: {exc}"
                    ) from exc
        raise LLMAnalysisError("レスポンスからJSONを抽出できませんでした。")

    def extract_pdf_metadata(self, text: str) -> Dict[str, Any]:
        return {
            "has_budget": "予算" in text or "budget" in text.lower(),
            "has_deadline": "期限" in text or "deadline" in text.lower(),
            "has_qualifications": "資格" in text or "qualification" in text.lower(),
            "char_count": len(text),
        }

    def check_compliance(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        required = self.config.required_keys
        missing = [k for k in required if not analysis.get(k) or analysis.get(k) == "記載なし"]
        return {
            "is_compliant": len(missing) == 0,
            "missing_fields": missing,
            "score": max(0, 100 - len(missing) * 10),
        }

    def generate_report(self, text: str, report_type: str = "pdf") -> Dict[str, Any]:
        summary = self.analyze(text)
        pdf_data = self.extract_pdf_metadata(text) if report_type == "pdf" else None
        return {
            **summary,
            "metadata": pdf_data or {},
            "compliance": self.check_compliance(summary),
        }
