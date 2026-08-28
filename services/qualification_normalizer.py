from typing import List, Dict, Any, Optional
import logging
from database.seeders.qualification_tag_seeder import load_master_csv

class QualificationNormalizer:
    NORMALIZE_PROMPT = """
以下の入札仕様書から抽出された参加資格テキストを、
マスタータグリストの中から最も近いものに紐付けてください。
該当なしの場合は "UNMATCHED" を返してください。

マスタータグ:
{tag_list}

入力テキスト:
{qualification_text}

出力JSON: {{"tag_code": "...", "confidence": 0.0-1.0}}
"""

    def __init__(self, llm_service: Any, logger: Optional[logging.Logger] = None):
        self.llm_service = llm_service
        self.logger = logger or logging.getLogger(__name__)
        self.master_tags = self._load_tags()

    def _load_tags(self) -> List[Dict[str, str]]:
        try:
            return load_master_csv()
        except Exception as e:
            self.logger.error(f"Failed to load master tags: {e}")
            return []

    def normalize(self, text_list: List[str]) -> List[Dict[str, Any]]:
        """
        参加資格テキストリストを正規化タグにマッピングする
        """
        results = []
        for text in text_list:
            # ルールベースマッチング（簡易）
            match = self._match_rule_based(text)
            if match:
                results.append({
                    "original_text": text,
                    "tag_code": match["tag_code"],
                    "display_name": match["display_name"],
                    "confidence": 1.0
                })
            else:
                # LLMマッチングの実装
                match = self._match_llm(text)
                # 信頼度閾値チェック（0.5以上を有効とする）
                if match and match.get("confidence", 0.0) >= 0.5:
                    results.append({
                        "original_text": text,
                        "tag_code": match.get("tag_code", "UNMATCHED"),
                        "confidence": match.get("confidence", 0.0)
                    })
                else:
                    results.append({
                        "original_text": text,
                        "tag_code": "UNMATCHED",
                        "confidence": 0.0
                    })
        return results

    def _match_llm(self, text: str) -> Optional[Dict[str, Any]]:
        tag_list_str = "\n".join([f"{t['tag_code']}: {t['display_name']}" for t in self.master_tags])
        prompt = self.NORMALIZE_PROMPT.format(tag_list=tag_list_str, qualification_text=text)

        try:
            response = self.llm_service.analyze_with_fallback(prompt)
            # analyze_with_fallback は解析済みの dict を返す（プロバイダが JSON をパース済み）
            if isinstance(response, dict):
                return response
            # 文字列が返される古い実装との互換性のためのフォールバック
            import json
            import re
            match = re.search(r"\{.*\}", response, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception as e:
            self.logger.error(f"LLM matching failed: {e}")
        return None

    def _match_rule_based(self, text: str) -> Optional[Dict[str, str]]:
        for tag in self.master_tags:
            if tag["display_name"] in text or tag["tag_code"] in text:
                return tag
        return None
