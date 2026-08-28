"""ページネーションユーティリティ

- `find_next_page` は HTML から "次へ" リンクを抽出
- `crawl_all_pages` は開始 URL からページネーションを辿り、`parse_fn` で処理した結果を全ページ分収集
"""

from typing import Callable, List, Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

def find_next_page(html: str, base_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    # 一般的な "次へ" リンクのパターンを検索
    for selector in ["a.next", "a[rel='next']", "a:contains('次')", "a:contains('Next')"]:
        el = soup.select_one(selector)
        if el and el.get('href'):
            return urljoin(base_url, el['href'])
    return None

def crawl_all_pages(start_url: str, fetch_fn: Callable[[str], str], parse_fn: Callable[[str], List[Any]]) -> List[Any]:
    """開始ページから全ページを巡回し、`parse_fn` が返すリストを結合して返す"""
    results: List[Any] = []
    url = start_url
    while url:
        html = fetch_fn(url)
        results.extend(parse_fn(html))
        next_url = find_next_page(html, url)
        if not next_url or next_url == url:
            break
        url = next_url
    return results
