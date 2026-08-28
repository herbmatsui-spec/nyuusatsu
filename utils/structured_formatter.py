import json
import logging
import traceback
from datetime import datetime, timezone
import re

REDACT_PATTERNS = [
    (r'(?i)(api[_-]?key\s*[:=]\s*)["\']?[A-Za-z0-9_\-]+["\']?', r"\1***"),
    (r'(?i)(secret[_-]?key\s*[:=]\s*)["\']?[A-Za-z0-9_\-]+["\']?', r"\1***"),
    (r'(?i)(password\s*[:=]\s*)["\']?[^"\'\s]+["\']?', r"\1***"),
]

class StructuredFormatter(logging.Formatter):
    """
    JSON形式で構造化されたログを出力するためのフォーマッター。
    個人情報やAPIキーなどの機密情報を自動でマスクする機能も含む。
    """
    def __init__(self, fmt=None, datefmt=None, style='%', validate=True):
        super().__init__(fmt, datefmt, style, validate)

    def format(self, record):
        # タイムスタンプはISO 8601形式 (UTC)
        timestamp = datetime.fromtimestamp(record.created, timezone.utc).isoformat()
        
        log_entry = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # ログコンテキスト (trace_id, pipeline_stage) があれば取り込む
        for key in ["trace_id", "pipeline_stage", "agency_id", "duration_ms", "error_type", "bid_count"]:
            if hasattr(record, key):
                val = getattr(record, key)
                if val is not None and val != "":
                    log_entry[key] = val

        # 例外情報の追記
        if record.exc_info:
            log_entry["exception"] = "".join(traceback.format_exception(*record.exc_info))

        # JSONシリアライズ
        serialized = json.dumps(log_entry, ensure_ascii=False)

        # 機密情報のマスク処理
        for pattern, replacement in REDACT_PATTERNS:
            serialized = re.sub(pattern, replacement, serialized)

        return serialized
