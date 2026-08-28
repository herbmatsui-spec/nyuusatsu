"""クローラ基底クラス

- すべてのカスタムクローラはこのクラスを継承し、共通ロジック（リトライ付き取得等）を利用できる
- `parse_list` と `parse_detail` は子クラスで実装する抽象メソッド
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import List, Any

import requests

logger = logging.getLogger(__name__)

class BaseCrawler(ABC):
    def __init__(self, retry: int = 3, timeout: int = 15, backoff: float = 0.5):
        self.retry = retry
        self.timeout = timeout
        self.backoff = backoff

    def fetch(self, url: str) -> str:
        """HTTP GET with simple exponential backoff retry"""
        attempt = 0
        while attempt < self.retry:
            try:
                resp = requests.get(url, timeout=self.timeout)
                resp.raise_for_status()
                return resp.text
            except Exception as e:
                logger.warning(f"Fetch error {e} for {url}, attempt {attempt + 1}/{self.retry}")
                attempt += 1
                time.sleep(self.backoff * (2 ** attempt))
        raise RuntimeError(f"Failed to fetch {url} after {self.retry} attempts")

    @abstractmethod
    def parse_list(self, html: str) -> List[Any]:
        """一覧ページから対象リンクやオブジェクトのリストを抽出"""
        pass

    @abstractmethod
    def parse_detail(self, html: str) -> Any:
        """詳細ページから構造化データを抽出"""
        pass

    @abstractmethod
    def save(self, items: List[Any]):
        """抽出したアイテムを永続化（DB保存等）する"""
        pass
