import hashlib
import os
import json
from typing import Optional
from ocr.config import OCRConfig

def get_file_hash(file_data: bytes) -> str:
    """ファイルデータのSHA-256ハッシュを計算する。"""
    return hashlib.sha256(file_data).hexdigest()

def get_cached_ocr_text(file_data: bytes, config: OCRConfig) -> Optional[str]:
    """キャッシュからOCR結果を読み込む。"""
    file_hash = get_file_hash(file_data)
    cache_path = os.path.join(config.cache_dir, f"{file_hash}.json")
    
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("text")
        except Exception:
            return None
    return None

def save_ocr_cache(file_data: bytes, text: str, config: OCRConfig):
    """OCR結果をキャッシュに保存する。"""
    if not os.path.exists(config.cache_dir):
        os.makedirs(config.cache_dir, exist_ok=True)
        
    file_hash = get_file_hash(file_data)
    cache_path = os.path.join(config.cache_dir, f"{file_hash}.json")
    
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump({"text": text}, f, ensure_ascii=False, indent=2)
