"""フィールド正規化ユーティリティ

- 金額文字列（例: "1,234,567円"） → int
- 日付文字列（例: "2026.08.27"、"2026/08/27"） → datetime.date
- 文字列全体の空白・全角半角統一
"""

import re
from datetime import datetime, date


def normalize_amount(text: str) -> int:
    # 数字とカンマだけ残す
    cleaned = re.sub(r"[^0-9]", "", text)
    return int(cleaned) if cleaned else 0


def normalize_date(text: str) -> date | None:
    # 複数フォーマットをサポート
    for fmt in ("%Y.%m.%d", "%Y/%m/%d", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except Exception:
            continue
    return None


def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def normalize_fullwidth_to_halfwidth(text: str) -> str:
    # 簡易変換: 全角数字・記号 → 半角
    # 実装は python-jp文字列 utils が必要になるため、ここでは placeholder
    return text
