"""発注機関リスト取得の基底クラス

- 省庁や自治体のトップページから入札情報ページへのリンクを抽出
- 取得ロジックは子クラスで上書き可能
"""

import requests
from bs4 import BeautifulSoup

class AgencyListFetcher:
    """基底クラス：トップページ取得と入札リンク抽出"""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    def fetch_top_page(self, url: str) -> str:
        """URL から HTML を取得し文字列で返す"""
        resp = requests.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return resp.text

    def find_bid_links(self, html: str) -> list[str]:
        """HTML から入札情報ページへのリンクリストを抽出（デフォルト実装は <a> の href を全取得）"""
        soup = BeautifulSoup(html, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "入札" in a.get_text() or "調達" in a.get_text():
                links.append(href)
        return links
