"""クローラ共通例外定義

- `CrawlError` : ネットワーク/取得エラー
- `ParseError` : HTML/データ解析エラー
- `RateLimitError` : 取得レート制限検出
"""

class CrawlError(Exception):
    pass

class ParseError(Exception):
    pass

class RateLimitError(Exception):
    pass
