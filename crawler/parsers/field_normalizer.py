"""Field normalizer utilities."""

import re
from datetime import datetime, date

def normalize_amount(text: str) -> int:
    # Keep only digits (including full-width)
    text = text.translate(str.maketrans({chr(0xFF10 + i): str(i) for i in range(10)}))
    cleaned = re.sub(r"[^0-9]", "", text)
    return int(cleaned) if cleaned else 0

def normalize_date(text: str) -> date | None:
    # Try multiple date formats
    for fmt in ("%Y.%m.%d", "%Y/%m/%d", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except Exception:
            continue
    return None

def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())

def normalize_fullwidth_to_halfwidth(text: str) -> str:
    try:
        import mojimiji
        return mojimiji.zen_to_han(text, digit=True, ascii=True)
    except ImportError:
        # Fallback: manual conversion for common characters
        result = text
        # Full-width digits
        for i in range(10):
            result = result.replace(chr(0xFF10 + i), str(i))
        # Full-width uppercase letters
        for i in range(26):
            result = result.replace(chr(0xFF21 + i), chr(0x41 + i))
        # Full-width lowercase letters
        for i in range(26):
            result = result.replace(chr(0xFF41 + i), chr(0x61 + i))
        # Common symbols
        result = result.replace("＆", "&")
        return result

# Export transform map for ConfigDrivenCrawler
TRANSFORM_MAP = {
    "normalize_amount": normalize_amount,
    "normalize_date": normalize_date,
    "normalize_whitespace": normalize_whitespace,
    "normalize_fullwidth_to_halfwidth": normalize_fullwidth_to_halfwidth,
}