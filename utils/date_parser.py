import re
import logging
from datetime import datetime, date
from typing import Optional

logger = logging.getLogger(__name__)

def parse_date(date_str: str) -> Optional[date]:
    """
    多様な形式の日本語日付文字列を python date オブジェクトに変換する。
    例: '令和6年4月1日', '2024/04/01', 'H31.4.1'
    """
    if not date_str or date_str in ["不明", "記載なし", "None"]:
        return None

    date_str = date_str.strip()

    # Try standard YYYY-MM-DD or YYYY/MM/DD regex first
    match = re.match(r'^(\d{4})[-/](\d{1,2})[-/](\d{1,2})', date_str)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            pass

    # Try YYYY年MM月DD日 regex
    match_ja = re.match(r'^(\d{4})年(\d{1,2})月(\d{1,2})日', date_str)
    if match_ja:
        try:
            return date(int(match_ja.group(1)), int(match_ja.group(2)), int(match_ja.group(3)))
        except ValueError:
            pass

    try:
        # dateparser を使用して柔軟にパース（インストールされている場合）
        import dateparser
        parsed_dt = dateparser.parse(
            date_str, 
            languages=['ja'], 
            settings={'RELATIVE_BASE': datetime(2000, 1, 1)}
        )
        if parsed_dt:
            return parsed_dt.date()
        return None
    except ImportError:
        logger.warning(f"dateparser is not installed; advanced date parsing skipped for '{date_str}'")
        return None
    except Exception as e:
        logger.warning(f"Failed to parse date string '{date_str}': {e}")
        return None
