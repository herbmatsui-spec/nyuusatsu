"""
Fallback selector module for trying alternative selectors.
"""
from bs4 import BeautifulSoup
from typing import List, Optional


class FallbackSelector:
    """Manages a list of selectors and tries them in order until one succeeds."""

    @staticmethod
    def select_with_fallback(soup: BeautifulSoup, selectors: List[str], min_results: int = 1) -> Optional[List]:
        """
        Try each selector in order and return the first result list that
        contains at least min_results elements.
        Returns None if no selector yields sufficient results.
        """
        for selector in selectors:
            try:
                elements = soup.select(selector)
                if elements is not None and len(elements) >= min_results:
                    return elements
            except Exception:
                # If selector syntax is invalid, skip
                continue
        return None

    @staticmethod
    def select_first_with_fallback(soup: BeautifulSoup, selectors: List[str]) -> Optional:
        """
        Try each selector and return the first element matched, or None.
        """
        for selector in selectors:
            try:
                element = soup.select_one(selector)
                if element is not None:
                    return element
            except Exception:
                continue
        return None
