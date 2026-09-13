"""
Structure change detection module for detecting when site structure changes.
"""
import hashlib
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup


class StructureChangeDetector:
    """
    Detects structural changes by monitoring the number of elements selected
    by a previously successful selector.
    """

    def __init__(self):
        # Store last known good state per selector hash
        self._state: Dict[str, Dict[str, Any]] = {}

    def _selector_hash(self, selector: str) -> str:
        """Generate a hash for the selector string."""
        return hashlib.md5(selector.encode('utf-8')).hexdigest()

    def record_success(self, selector: str, soup: BeautifulSoup) -> None:
        """
        Record a successful extraction: store the selector and the count of elements
        it selected, along with a hash of the selected elements' text for change detection.
        """
        try:
            elements = soup.select(selector)
            count = len(elements) if elements else 0
            # Compute a simple hash of the concatenated text of first few elements
            sample_text = ''
            if elements:
                # Take up to 5 elements for hashing
                for el in elements[:5]:
                    sample_text += el.get_text(strip=True)[:100]
            text_hash = hashlib.md5(sample_text.encode('utf-8')).hexdigest() if sample_text else ''
            state = {
                'count': count,
                'text_hash': text_hash,
                'selector': selector,
            }
            self._state[self._selector_hash(selector)] = state
        except Exception:
            # If selection fails, do not record
            pass

    def has_changed(self, selector: str, soup: BeautifulSoup, threshold: float = 0.5) -> bool:
        """
        Returns True if the current selection result deviates significantly
        from the last recorded success.
        threshold: fraction of original count below which we consider changed (e.g., 0.5 means <50%).
        Also considers text hash change as indicator.
        """
        state = self._state.get(self._selector_hash(selector))
        if not state:
            # No prior success recorded
            return False
        try:
            elements = soup.select(selector)
            count = len(elements) if elements else 0
            # Significant drop in count
            if state['count'] > 0 and count < state['count'] * threshold:
                return True
            # Check text hash change (optional)
            sample_text = ''
            if elements:
                for el in elements[:5]:
                    sample_text += el.get_text(strip=True)[:100]
            current_hash = hashlib.md5(sample_text.encode('utf-8')).hexdigest() if sample_text else ''
            if state['text_hash'] and current_hash and state['text_hash'] != current_hash:
                # Text changed significantly
                return True
        except Exception:
            # If selection fails, treat as change
            return True
        return False
