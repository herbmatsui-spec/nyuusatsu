# 改善点2 ステップ21-25: services/cost_manager.py
# LLM APIの消費トークンとリクエスト数を管理し、上限設定を設けます。

import json
import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger("CostManager")

class CostManager:
    """
    LLM APIの利用コスト（トークン数・リクエスト数）を監視・制限クラス。
    """
    def __init__(self, usage_log_path: str = "logs/api_usage.json"):
        self.usage_log_path = Path(usage_log_path)
        # 環境変数から上限設定を読み込み（デフォルト値あり）
        self.daily_token_limit = int(os.getenv("LLM_DAILY_TOKEN_LIMIT", 1000000))
        self.daily_request_limit = int(os.getenv("LLM_DAILY_REQUEST_LIMIT", 1000))

        # ログディレクトリの作成
        self.usage_log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.usage_log_path.exists():
            self._save_usage([])

    def _load_usage(self) -> List[Dict[str, Any]]:
        if self.usage_log_path.exists():
            try:
                with open(self.usage_log_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return []
        return []

    def _save_usage(self, usage_data: List[Dict[str, Any]]) -> None:
        with open(self.usage_log_path, 'w') as f:
            json.dump(usage_data, f, indent=2, ensure_ascii=False)

    def record_usage(self, provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> None:
        usage_data = self._load_usage()
        today = datetime.now(timezone.utc).date().isoformat()
        
        # 今日のエントリーを見つけるか、新しく作る
        today_entry = None
        for entry in usage_data:
            if entry.get("date") == today:
                today_entry = entry
                break
        
        if today_entry is None:
            today_entry = {
                "date": today,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_requests": 0,
                "providers": {}
            }
            usage_data.append(today_entry)
        
        # トークン数を更新
        today_entry["total_prompt_tokens"] += prompt_tokens
        today_entry["total_completion_tokens"] += completion_tokens
        today_entry["total_requests"] += 1
        
        # プロバイダー別の使用状況を更新
        if provider not in today_entry["providers"]:
            today_entry["providers"][provider] = {
                "model": model,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "requests": 0
            }
        
        provider_data = today_entry["providers"][provider]
        provider_data["prompt_tokens"] += prompt_tokens
        provider_data["completion_tokens"] += completion_tokens
        provider_data["requests"] += 1
        
        # 使用状況を保存
        self._save_usage(usage_data)

    def get_usage(self, date: Optional[str] = None) -> List[Dict[str, Any]]:
        usage_data = self._load_usage()
        if date is None:
            return usage_data
        return [entry for entry in usage_data if entry.get("date") == date]

    def check_limit(self) -> bool:
        usage_data = self._load_usage()
        today = datetime.now(timezone.utc).date().isoformat()
        
        for entry in usage_data:
            if entry.get("date") == today:
                total_tokens = entry.get("total_prompt_tokens", 0) + entry.get("total_completion_tokens", 0)
                return total_tokens < self.daily_token_limit
        return True  # 今日の使用記録がない場合は制限内とみなす