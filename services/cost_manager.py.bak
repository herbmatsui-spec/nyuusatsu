# 改善点2 ステップ21-25: services/cost_manager.py
# LLM APIの消費トークンとリクエスト数を管理し、上限設定を設けます。

import json
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

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
        """利用ログファイルを読み込む"""
        try:
            with open(self.usage_log_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save_usage(self, data: List[Dict[str, Any]]):
        """利用ログファイルを保存する"""
        with open(self.usage_log_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def record_usage(self, provider: str, model: str, prompt_tokens: int, completion_tokens: int):
        """
        API利用実績を記録する。
        """
        usage = self._load_usage()
        
        new_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "provider": provider,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens
        }
        
        usage.append(new_entry)
        self._save_usage(usage)
        logger.info(f"Recorded usage for {provider}/{model}: {new_entry['total_tokens']} tokens")

    def get_daily_usage(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        """
        指定した日付（YYYY-MM-DD）の合計消費量を取得する。
        date_strがNoneの場合は今日。
        """
        if date_str is None:
            date_str = datetime.utcnow().strftime("%Y-%m-%d")
            
        usage = self._load_usage()
        total_tokens = 0
        total_requests = 0
        
        for entry in usage:
            if entry["timestamp"].startswith(date_str):
                total_tokens += entry.get("total_tokens", 0)
                total_requests += 1
                
        return {
            "date": date_str,
            "total_tokens": total_tokens,
            "total_requests": total_requests
        }

    def is_limit_exceeded(self) -> bool:
        """
        本日の消費量が上限を超えているか判定する。
        """
        today_usage = self.get_daily_usage()
        
        if today_usage["total_tokens"] > self.daily_token_limit:
            logger.warning(f"Daily token limit exceeded: {today_usage['total_tokens']} / {self.daily_token_limit}")
            return True
            
        if today_usage["total_requests"] > self.daily_request_limit:
            logger.warning(f"Daily request limit exceeded: {today_usage['total_requests']} / {self.daily_request_limit}")
            return True
            
        return False
