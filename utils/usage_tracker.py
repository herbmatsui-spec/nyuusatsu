import json
import os
from datetime import datetime
from typing import Dict, Any
import threading

_lock = threading.Lock()

def log_api_usage(provider: str, model: str, prompt_tokens: int, completion_tokens: int):
    """
    APIの使用量をログファイルに記録する。
    """
    usage_file = "logs/api_usage.json"
    
    with _lock:
        data = []
        if os.path.exists(usage_file):
            try:
                with open(usage_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = []
                
        entry = {
            "timestamp": datetime.now().isoformat(),
            "provider": provider,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens
        }
        data.append(entry)
        
        os.makedirs("logs", exist_ok=True)
        with open(usage_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
