import re
from typing import Optional
from urllib.parse import urlparse
from crawler.patterns.forecast_patterns import FORECAST_URL_PATTERNS, get_all_keywords


def is_forecast_url(url: str) -> bool:
    if not url:
        return False

    url_lower = url.lower()
    keywords = get_all_keywords()

    for keyword in keywords:
        if keyword.lower() in url_lower:
            return True

    return False


def detect_forecast_in_text(text: str) -> bool:
    if not text:
        return False

    keywords = get_all_keywords()
    text_lower = text.lower()

    for keyword in keywords:
        if keyword.lower() in text_lower:
            return True

    return False


def extract_forecast_indicators(text: str) -> list:
    indicators = []
    if not text:
        return indicators

    text_lower = text.lower()
    keyword_hits = []

    for group in FORECAST_URL_PATTERNS:
        for keyword in group["keywords"]:
            if keyword.lower() in text_lower:
                keyword_hits.append({
                    "keyword": keyword,
                    "group": group["name"],
                    "priority": group["priority"]
                })

    return keyword_hits


def normalize_forecast_url(url: str) -> Optional[str]:
    if not url:
        return None

    parsed = urlparse(url)
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    if parsed.query:
        normalized += f"?{parsed.query}"

    return normalized.rstrip('/')


def extract_agency_code_from_url(url: str) -> Optional[str]:
    if not url:
        return None

    patterns = [
        r'/(\d{6})/',
        r'muni=(\d{6})',
        r'code=(\d{6})',
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None


def is_pdf_url(url: str) -> bool:
    if not url:
        return False
    return url.lower().endswith('.pdf') or '.pdf?' in url.lower()


def match_forecast_pattern(url: str) -> Optional[dict]:
    if not url:
        return None

    url_lower = url.lower()

    for group in FORECAST_URL_PATTERNS:
        for keyword in group["keywords"]:
            if keyword.lower() in url_lower:
                return {
                    "name": group["name"],
                    "matched_keyword": keyword,
                    "priority": group["priority"]
                }

    return None