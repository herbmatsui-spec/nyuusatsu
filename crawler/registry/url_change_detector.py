"""URL Change Detector - compares current URLs with stored ones to detect changes."""

import json
import os
import hashlib
from typing import Optional
from dataclasses import dataclass, asdict
from crawler.registry import RegistryEntry


@dataclass
class StoredURLState:
    """Stored state of a URL for change detection."""
    municipality_code: str
    base_url: str
    bid_url_pattern: str
    base_url_hash: str
    bid_url_hash: str
    last_checked: str
    change_detected: bool = False


class URLChangeDetector:
    """Detects changes in URLs by comparing with stored states."""
    
    def __init__(self, state_file: str = "data/url_registry_state.json"):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.state_file = os.path.join(base_dir, state_file)
        self._states: dict[str, StoredURLState] = {}
        self._load_state()

    def _load_state(self) -> None:
        """Load stored URL states from file."""
        if os.path.exists(self.state_file):
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for code, state in data.items():
                    self._states[code] = StoredURLState(**state)

    def _save_state(self) -> None:
        """Save URL states to file."""
        data = {code: asdict(state) for code, state in self._states.items()}
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _compute_hash(self, url: str) -> str:
        """Compute SHA256 hash of a URL."""
        return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]

    def check_changes(self, entry: RegistryEntry) -> dict:
        """Check if URLs have changed for a registry entry.
        
        Returns:
            Dict with change detection results
        """
        from datetime import datetime
        
        current_base_hash = self._compute_hash(entry.base_url)
        current_bid_hash = self._compute_hash(entry.bid_url_pattern)
        
        stored = self._states.get(entry.municipality_code)
        
        if stored is None:
            # First time seeing this entry
            result = {
                "municipality_code": entry.municipality_code,
                "name": entry.name,
                "base_url_changed": False,
                "bid_url_changed": False,
                "is_new": True,
                "stored_base_url": None,
                "stored_bid_url": None,
                "current_base_url": entry.base_url,
                "current_bid_url": entry.bid_url_pattern,
            }
        else:
            base_changed = stored.base_url_hash != current_base_hash
            bid_changed = stored.bid_url_hash != current_bid_hash
            
            result = {
                "municipality_code": entry.municipality_code,
                "name": entry.name,
                "base_url_changed": base_changed,
                "bid_url_changed": bid_changed,
                "is_new": False,
                "stored_base_url": stored.base_url,
                "stored_bid_url": stored.bid_url_pattern,
                "current_base_url": entry.base_url,
                "current_bid_url": entry.bid_url_pattern,
            }
        
        return result

    def update_state(self, entry: RegistryEntry) -> None:
        """Update stored state for an entry after successful sync."""
        from datetime import datetime
        
        self._states[entry.municipality_code] = StoredURLState(
            municipality_code=entry.municipality_code,
            base_url=entry.base_url,
            bid_url_pattern=entry.bid_url_pattern,
            base_url_hash=self._compute_hash(entry.base_url),
            bid_url_hash=self._compute_hash(entry.bid_url_pattern),
            last_checked=datetime.now().isoformat(),
            change_detected=False,
        )
        self._save_state()

    def get_all_changes(self, entries: list[RegistryEntry]) -> list[dict]:
        """Check changes for all entries."""
        return [self.check_changes(entry) for entry in entries]

    def get_changed_entries(self, entries: list[RegistryEntry]) -> list[dict]:
        """Get only entries with detected changes."""
        all_changes = self.get_all_changes(entries)
        return [c for c in all_changes if c["base_url_changed"] or c["bid_url_changed"] or c["is_new"]]