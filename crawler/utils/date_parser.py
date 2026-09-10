"""日付パースユーティリティ

様々な形式の日付文字列を date オブジェクトに変換する共通関数
"""
import re
from datetime import date, datetime
from typing import Optional


# 和暦変換用ベース年
WAREKI_BASE = {
    "令和": 2018,  # 令和元年 = 2019年
    "平成": 1988,  # 平成元年 = 1989年
    "昭和": 1925,  # 昭和元年 = 1926年
    "大正": 1911,  # 大正元年 = 1912年
    "明治": 1867,  # 明治元年 = 1868年
}


def _parse_wareki(match) -> Optional[date]:
    """和暦日付パース"""
    era = match.group(1)
    year_str = match.group(2)
    month = int(match.group(3))
    day = int(match.group(4))

    base_year = WAREKI_BASE.get(era)
    if base_year is None:
        return None

    if year_str == "元":
        year = base_year + 1
    else:
        year = base_year + int(year_str)

    try:
        return date(year, month, day)
    except ValueError:
        return None


def _parse_wareki_short(match) -> Optional[date]:
    """和暦短縮形式パース (R5.10.1 等)"""
    era_char = match.group(1).upper()
    era_map = {"R": "令和", "H": "平成", "S": "昭和", "T": "大正", "M": "明治", "E": "明治"}
    era = era_map.get(era_char)
    if not era:
        return None

    year = int(match.group(2))
    month = int(match.group(3))
    day = int(match.group(4))

    base_year = WAREKI_BASE.get(era)
    if base_year is None:
        return None

    full_year = base_year + year
    try:
        return date(full_year, month, day)
    except ValueError:
        return None


# よくある日付パターン（優先度順）
DATE_PATTERNS = [
    # YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD
    (r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$", lambda m: date(int(m[1]), int(m[2]), int(m[3]))),
    # YYYY年MM月DD日
    (r"^(\d{4})年(\d{1,2})月(\d{1,2})日$", lambda m: date(int(m[1]), int(m[2]), int(m[3]))),
    # 和暦: 令和X年MM月DD日, 平成X年MM月DD日, 昭和X年MM月DD日
    (r"^(令和|平成|昭和|大正|明治)(\d{1,2}|元)年(\d{1,2})月(\d{1,2})日$", _parse_wareki),
    # 和暦短縮: R5.10.1, H31.3.31, S63.1.1
    (r"^([RHSTMe])(\d{1,2})[./](\d{1,2})[./](\d{1,2})$", _parse_wareki_short),
    # YYYYMMDD (数字のみ)
    (r"^(\d{4})(\d{2})(\d{2})$", lambda m: date(int(m[1]), int(m[2]), int(m[3]))),
    # MM/DD, MM-DD (年なし -> 当年とみなす)
    (r"^(\d{1,2})[/-](\d{1,2})$", lambda m: date(datetime.now().year, int(m[1]), int(m[2]))),
]


def parse_date_string(text: str) -> Optional[date]:
    """日付文字列を date オブジェクトに変換

    対応形式:
    - 2024-01-15, 2024/01/15, 2024.01.15
    - 2024年1月15日
    - 令和6年1月15日, 平成31年3月31日, 昭和63年1月1日
    - R6.1.15, H31.3.31, S63.1.1
    - 20240115
    - 01/15 (当年とみなす)

    Args:
        text: 日付文字列

    Returns:
        date オブジェクト、パース失敗時は None
    """
    if not text:
        return None

    # 前後の空白除去
    text = text.strip()

    # よくあるプレフィックス除去
    for prefix in ["公告日:", "公告日：", "掲載日:", "掲載日：", "発表日:", "発表日：", "日付:"]:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()

    for pattern, parser in DATE_PATTERNS:
        match = re.match(pattern, text)
        if match:
            try:
                return parser(match)
            except Exception:
                continue

    # datetime.fromisoformat で試行 (Python 3.7+)
    try:
        return datetime.fromisoformat(text.replace("/", "-")).date()
    except Exception:
        pass

    return None


def extract_date_from_text(text: str) -> Optional[date]:
    """長いテキストから日付らしい部分を抽出してパース

    Args:
        text: 任意のテキスト

    Returns:
        最初に見つかった有効な日付、見つからなければ None
    """
    if not text:
        return None

    # 日付らしいパターンを検索（finditer で全文マッチを取得）
    patterns = [
        r"\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}日?",  # 2024-01-15, 2024年1月15日
        r"(?:令和|平成|昭和|大正|明治)(?:\d{1,2}|元)年\d{1,2}月\d{1,2}日",  # 和暦
        r"[RHSTMe]\d{1,2}[./]\d{1,2}[./]\d{1,2}",  # 短縮和暦
        r"\d{8}",  # 20240115
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, text):
            result = parse_date_string(match.group(0))
            if result:
                return result

    # より緩いパターンで再試行（日以降の文字も許容）
    loose_patterns = [
        r"(?:令和|平成|昭和|大正|明治)(?:\d{1,2}|元)年\d{1,2}月\d{1,2}日\S*",  # 和暦+任意文字
        r"\d{4}年\d{1,2}月\d{1,2}日\S*",  # 西暦+任意文字
    ]
    for pattern in loose_patterns:
        match = re.search(pattern, text)
        if match:
            result = parse_date_string(match.group(0))
            if result:
                return result

    return None


def parse_datetime_string(text: str) -> Optional[datetime]:
    """日時文字列を datetime オブジェクトに変換"""
    if not text:
        return None

    text = text.strip()

    # ISO format
    try:
        return datetime.fromisoformat(text.replace("/", "-"))
    except Exception:
        pass

    # よくある形式
    patterns = [
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M",
        "%Y年%m月%d日 %H時%M分",
    ]

    for fmt in patterns:
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            continue

    # 日付のみの場合
    d = parse_date_string(text)
    if d:
        return datetime.combine(d, datetime.min.time())

    return None