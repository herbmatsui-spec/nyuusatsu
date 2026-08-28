import logging
import os
import re
from dotenv import load_dotenv

REDACT_PATTERNS = [
    (r'(?i)(api[_-]?key\s*[:=]\s*)["\']?[A-Za-z0-9_\-]+["\']?', r"\1***"),
    (r'(?i)(secret[_-]?key\s*[:=]\s*)["\']?[A-Za-z0-9_\-]+["\']?', r"\1***"),
    (r'(?i)(password\s*[:=]\s*)["\']?[^"\'\s]+["\']?', r"\1***"),
]

class SecureFormatter(logging.Formatter):
    def format(self, record):
        message = super().format(record)
        for pattern, replacement in REDACT_PATTERNS:
            message = re.sub(pattern, replacement, message)
        return message

def setup_logging(log_name: str = "app"):
    """
    Sets up a common logging configuration for the application.
    Supports JSON structured logging and plain text logging depending on LOG_FORMAT env var.
    """
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_format = os.environ.get("LOG_FORMAT", "json").lower()

    if log_format == "json":
        from utils.structured_formatter import StructuredFormatter
        formatter = StructuredFormatter()
    else:
        formatter = SecureFormatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    logger = logging.getLogger(log_name)
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    # コンテキストフィルターの追加 (trace_id や pipeline_stage を自動伝搬)
    from utils.context_filter import ContextFilter
    ctx_filter = ContextFilter()
    
    # 既存のフィルターが重複して登録されないようにチェック
    has_ctx_filter = any(isinstance(f, ContextFilter) for f in logger.filters)
    if not has_ctx_filter:
        logger.addFilter(ctx_filter)

    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.addFilter(ctx_filter)
        logger.addHandler(console_handler)

        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, f"{log_name}.log"),
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(ctx_filter)
        logger.addHandler(file_handler)

    return logger

def get_logger(name: str):
    """
    Returns a logger instance for the given name.
    Automatically applies ContextFilter to the retrieved logger.
    """
    logger = logging.getLogger(name)
    from utils.context_filter import ContextFilter
    if not any(isinstance(f, ContextFilter) for f in logger.filters):
        logger.addFilter(ContextFilter())
    return logger

