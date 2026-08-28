import hashlib
import os
from typing import Optional

def get_file_hash(file_data: bytes) -> str:
    """ファイルデータのSHA-256ハッシュを計算する。"""
    return hashlib.sha256(file_data).hexdigest()

def is_file_cached(file_data: bytes, cache_dir: str) -> Optional[str]:
    """ファイルがキャッシュに存在するか確認し、パスを返す。"""
    file_hash = get_file_hash(file_data)
    cache_path = os.path.join(cache_dir, f"{file_hash}.pdf")
    if os.path.exists(cache_path):
        return cache_path
    return None

def save_to_cache(file_data: bytes, cache_dir: str) -> str:
    """ファイルをキャッシュに保存し、パスを返す。"""
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir, exist_ok=True)
    
    file_hash = get_file_hash(file_data)
    cache_path = os.path.join(cache_dir, f"{file_hash}.pdf")
    
    with open(cache_path, "wb") as f:
        f.write(file_data)
    return cache_path
