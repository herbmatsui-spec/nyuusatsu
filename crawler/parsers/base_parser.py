"""パーサー基底インターフェース

- `BaseParser` は `extract_fields` の抽象メソッドを提供
- 各具体パーサーは HTML/PDF テキストから必要フィールドを dict で返す
"""

from abc import ABC, abstractmethod

class BaseParser(ABC):
    @abstractmethod
    def extract_fields(self, raw_text: str) -> dict:
        """生テキスト/HTML から構造化データを抽出し dict を返す"""
        pass
