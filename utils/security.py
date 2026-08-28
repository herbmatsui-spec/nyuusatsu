import os
import re
import logging
from typing import Any, Dict, Optional
from config import AppConfig
from urllib.parse import urlparse

def validate_file_upload(uploaded_file: Any, max_size_mb: int = 20) -> Optional[str]:
    file_size = uploaded_file.getbuffer().nbytes
    if file_size > max_size_mb * 1024 * 1024:
        return f"ファイルサイズが大きすぎます。最大 {max_size_mb}MB までです。"
    if uploaded_file.type != "application/pdf":
        return "PDFファイルのみアップロード可能です。"
    return None

def validate_url(url: str, allowed_schemes: Optional[list] = None, allow_localhost: bool = False) -> Optional[str]:
    if not url or not url.strip():
        return "URLは空にできません。"
    allowed_schemes = allowed_schemes or ["http", "https"]
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme.lower() not in allowed_schemes:
            return f"URLスキームは{allowed_schemes}のいずれかにしてください。"
        if not parsed.netloc:
            return "有効なURLを入力してください。"
        # Optionally allow localhost
        if not allow_localhost:
            return None
        # If allow_localhost is True, only allow localhost, 127.0.0.1, ::1
        host = parsed.hostname
        if host is None:
            return "有効なURLを入力してください。"
        if host.lower() not in ("localhost", "127.0.0.1", "::1"):
            return "ローカルホストのみ許可されています。"
        return None
    except Exception:
        return "無効なURL形式です。"

def validate_api_key(api_key: str, provider: str) -> Optional[str]:
    patterns = {
        "openai": r"^sk-[a-zA-Z0-9]{48}$",
        "gemini": r"^AIza[0-9A-Za-z\\-]{35}$",
        "azure": r"^[0-9a-fA-F]{32}$",
        "deepseek": r"^sk-[a-zA-Z0-9]{48}$",
    }
    if provider not in patterns:
        return None
    if not re.match(patterns[provider], api_key):
        return f"無効な{provider} APIキー形式です。"
    return None

def sanitize_filename(filename: str, max_length: int = 255) -> str:
    # Remove or replace problematic characters for filenames
    # Includes path separators, control characters, and Windows illegal characters
    safe_name = re.sub(r'[\\/:*?"<>|\r\n\x00-\x1f]', '_', filename)
    # Remove leading/trailing underscores and dots
    safe_name = safe_name.strip('_.')
    # Ensure not empty
    if not safe_name:
        safe_name = "unnamed"
    # Apply length limit
    if len(safe_name) > max_length:
        # Keep extension if possible
        name, ext = os.path.splitext(safe_name)
        max_name_len = max_length - len(ext)
        if max_name_len < 1:
            # If extension too long, just truncate whole
            safe_name = safe_name[:max_length]
        else:
            safe_name = name[:max_name_len] + ext
    return safe_name

def mask_sensitive_data(data: Dict[str, Any], keys_to_mask: Optional[list] = None) -> Dict[str, Any]:
    default_keys = ["password", "secret", "api_key", "token", "authorization", "key", "credential"]
    keys_to_mask = keys_to_mask or default_keys
    def _mask(val):
        if isinstance(val, dict):
            return mask_sensitive_data(val, keys_to_mask)
        elif isinstance(val, list):
            return [_mask(item) for item in val]
        else:
            return val
    masked = {}
    for key, value in data.items():
        if any(k in key.lower() for k in keys_to_mask):
            masked[key] = "***"
        else:
            masked[key] = _mask(value)
    return masked