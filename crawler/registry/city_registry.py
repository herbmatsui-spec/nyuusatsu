"""Municipality/City URL Registry - loads city URLs from CSV."""

import csv
import os
from typing import Optional
from crawler.registry import BaseRegistry, RegistryEntry


class CityRegistry(BaseRegistry):
    """Registry for city/municipality-level URLs."""

    def __init__(self, csv_path: str = "data/city_urls.csv"):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.csv_path = os.path.join(base_dir, csv_path)
        self._entries: dict[str, RegistryEntry] = {}
        self._loaded = False

    def load(self) -> None:
        """Load city data from CSV."""
        if self._loaded:
            return

        with open(self.csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                entry = RegistryEntry(
                    municipality_code=row["municipality_code"],
                    name=row["name"],
                    prefecture=row["prefecture"],
                    base_url=row["base_url"],
                    bid_url_pattern=row["bid_url_pattern"],
                    bid_system=row["bid_system"],
                    parser_type=row["parser_type"],
                    url_type="city",
                )
                self._entries[row["municipality_code"]] = entry

        self._loaded = True

    def get_entry(self, municipality_code: str) -> Optional[RegistryEntry]:
        """Get city entry by code."""
        if not self._loaded:
            self.load()
        return self._entries.get(municipality_code)

    def get_all_entries(self) -> list[RegistryEntry]:
        """Get all city entries."""
        if not self._loaded:
            self.load()
        return list(self._entries.values())

    def get_entries_by_prefecture(self, prefecture: str) -> list[RegistryEntry]:
        """Get city entries filtered by prefecture."""
        if not self._loaded:
            self.load()
        return [e for e in self._entries.values() if e.prefecture == prefecture]