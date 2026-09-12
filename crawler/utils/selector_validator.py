"""
Selector validation utility for GEPS selectors.
"""
from typing import List, Tuple
from bs4 import BeautifulSoup


def validate_selector(html: str, selector: str) -> Tuple[bool, int]:
    """
    Validate a CSS selector against HTML.
    
    Args:
        html: HTML string to validate against
        selector: CSS selector string
        
    Returns:
        Tuple of (is_valid, match_count) where is_valid is True if selector matches at least one element
    """
    try:
        soup = BeautifulSoup(html, 'html.parser')
        matches = soup.select(selector)
        return len(matches) > 0, len(matches)
    except Exception:
        # If selector syntax is invalid, return False
        return False, 0


def validate_selectors(html: str, selectors: List[str]) -> List[Tuple[str, bool, int]]:
    """
    Validate a list of selectors against HTML.
    
    Args:
        html: HTML string to validate against
        selectors: List of CSS selector strings
        
    Returns:
        List of tuples (selector, is_valid, match_count)
    """
    results = []
    for selector in selectors:
        is_valid, count = validate_selector(html, selector)
        results.append((selector, is_valid, count))
    return results


def find_first_valid_selector(html: str, selectors: List[str]) -> Tuple[str, int]:
    """
    Find the first valid selector from a list (ordered by priority).
    
    Args:
        html: HTML string to validate against
        selectors: List of CSS selector strings in priority order
        
    Returns:
        Tuple of (first_valid_selector, match_count) or ("", 0) if none valid
    """
    for selector in selectors:
        is_valid, count = validate_selector(html, selector)
        if is_valid:
            return selector, count
    return "", 0