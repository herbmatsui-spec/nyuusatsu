"""Prefecture URL Registry - loads prefecture URLs from CSV."""

import csv
import os
from typing import Optional
from crawler.registry import BaseRegistry, RegistryEntry


class PrefectureRegistry(BaseRegistry):
    """Registry for prefecture-level URLs."""

    def __init__(self, csv_path: str = "data/prefecture_urls.csv"):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.csv_path = os.path.join(base_dir, csv_path)
        self._entries: dict[str, RegistryEntry] = {}
        self._loaded = False

    def load(self) -> None:
        """Load prefecture data from CSV."""
        if self._loaded:
            return

        with open(self.csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                entry = RegistryEntry(
                    municipality_code=row["municipality_code"],
                    name=row["name"],
                    prefecture=row["name"],
                    base_url=row["base_url"],
                    bid_url_pattern=row["bid_url_pattern"],
                    bid_system=row["bid_system"],
                    parser_type=row["parser_type"],
                    url_type="prefecture",
                )
                self._entries[row["municipality_code"]] = entry

        self._loaded = True

    def get_entry(self, municipality_code: str) -> Optional[RegistryEntry]:
        """Get prefecture entry by code."""
        if not self._loaded:
            self.load()
        return self._entries.get(municipality_code)

    def get_all_entries(self) -> list[RegistryEntry]:
        """Get all prefecture entries."""
        if not self._loaded:
            self.load()
        return list(self._entries.values())

    def get_entries_by_prefecture(self, prefecture: str) -> list[RegistryEntry]:
        """Get prefecture entry by prefecture name."""
        if not self._loaded:
            self.load()
        return [e for e in self._entries.values() if e.prefecture == prefecture]