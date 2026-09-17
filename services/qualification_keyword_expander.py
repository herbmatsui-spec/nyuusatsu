"""資格要件キーワードの辞書ベース同義語展開。

config/qualification_keywords.yml をロードし、検索キーワードを
同義語・上位/下位概念へ拡張する軽量実装。
"""
from functools import lru_cache
from pathlib import Path

import yaml

_DEFAULT_PATH = Path(__file__).resolve().parents[1] / "config" / "qualification_keywords.yml"


@lru_cache(maxsize=8)
def _load_dictionary(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except (OSError, ValueError):
        return {}
    return data.get("qualifications") or {}


def expand_qualification_keywords(keyword: str, path: str | None = None) -> list[str]:
    """入力キーワードを辞書で照合し、同義語・関連語を含む展開語リストを返す。

    辞書に無い語はそのまま返す。重複は除去し、元の語を先頭に保持する。
    """
    keyword = keyword.strip()
    if not keyword:
        return []
    dictionary = _load_dictionary(path or str(_DEFAULT_PATH))
    terms = [keyword]
    entry = dictionary.get(keyword)
    if entry:
        for key in ("keywords", "broader", "narrower"):
            for term in entry.get(key) or []:
                if term and term not in terms:
                    terms.append(term)
    return terms


def expand_qualification_query(keywords: str, path: str | None = None) -> list[str]:
    """空白区切りの複数キーワードを順に展開する。"""
    expanded: list[str] = []
    for token in keywords.split():
        for term in expand_qualification_keywords(token, path):
            if term not in expanded:
                expanded.append(term)
    return expanded
