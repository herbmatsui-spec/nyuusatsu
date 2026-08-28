"""コンテンツ形式判定ユーティリティ

- URL と HTTP Content-Type ヘッダーから 'html' / 'pdf' / 'mixed' を判定
- 拡張子が .pdf の場合は PDF、.html/.htm/.php/.aspx などは HTML、その他は unknown
"""

from urllib.parse import urlparse

def detect_format(url: str, content_type: str | None = None) -> str:
    path = urlparse(url).path.lower()
    if path.endswith('.pdf'):
        return 'pdf'
    if any(path.endswith(ext) for ext in ('.html', '.htm', '.php', '.aspx')):
        return 'html'
    if content_type:
        ct = content_type.lower()
        if 'pdf' in ct:
            return 'pdf'
        if 'html' in ct:
            return 'html'
    return 'unknown'
