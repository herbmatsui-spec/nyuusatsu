"""Full Municipality Registry - combines prefecture and city registries,
and can generate URLs from templates for municipalities not in CSV."""

import os
from typing import Optional
from crawler.registry import BaseRegistry, RegistryEntry
from crawler.registry.prefecture_registry import PrefectureRegistry
from crawler.registry.city_registry import CityRegistry


class MunicipalityRegistry(BaseRegistry):
    """Unified registry for all municipalities (prefectures + cities).
    
    Loads from CSV files and can generate URLs from templates for
    municipalities not explicitly listed.
    """

    def __init__(
        self,
        prefecture_csv: str = "data/prefecture_urls.csv",
        city_csv: str = "data/city_urls.csv",
    ):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.prefecture_csv = os.path.join(base_dir, prefecture_csv)
        self.city_csv = os.path.join(base_dir, city_csv)
        self.prefecture_registry = PrefectureRegistry(prefecture_csv)
        self.city_registry = CityRegistry(city_csv)
        self._entries: dict[str, RegistryEntry] = {}
        self._loaded = False

    def load(self) -> None:
        """Load all registry data."""
        if self._loaded:
            return

        # Load prefecture registry
        self.prefecture_registry.load()
        for entry in self.prefecture_registry.get_all_entries():
            self._entries[entry.municipality_code] = entry

        # Load city registry
        self.city_registry.load()
        for entry in self.city_registry.get_all_entries():
            self._entries[entry.municipality_code] = entry

        self._loaded = True

    def get_entry(self, municipality_code: str) -> Optional[RegistryEntry]:
        """Get entry by municipality code."""
        if not self._loaded:
            self.load()
        return self._entries.get(municipality_code)

    def get_all_entries(self) -> list[RegistryEntry]:
        """Get all entries."""
        if not self._loaded:
            self.load()
        return list(self._entries.values())

    def get_entries_by_prefecture(self, prefecture: str) -> list[RegistryEntry]:
        """Get entries filtered by prefecture."""
        if not self._loaded:
            self.load()
        return [e for e in self._entries.values() if e.prefecture == prefecture]

    def get_entries_by_type(self, url_type: str) -> list[RegistryEntry]:
        """Get entries filtered by type (prefecture or city)."""
        if not self._loaded:
            self.load()
        return [e for e in self._entries.values() if e.url_type == url_type]

    def generate_template_url(self, municipality_code: str, prefecture: str, name: str) -> Optional[RegistryEntry]:
        """Generate a template-based entry for municipalities not in CSV.
        
        Uses GEPS search URLs as fallback.
        """
        pref_code = municipality_code[:2]
        # URL encode the municipality name for GEPS search
        from urllib.parse import quote
        encoded_name = quote(name)
        bid_url = f"https://search.geps.go.jp/search?q={encoded_name}&pref={pref_code}"
        
        # Estimate base_url from common patterns
        if municipality_code.endswith("000"):  # Prefecture level
            base_url = f"https://www.pref.{prefecture.lower().replace('県', '').replace('府', '').replace('道', '').replace('都', '')}.lg.jp/"
        else:
            base_url = f"https://www.city.{name.lower()}.{prefecture.lower().replace('県', '').replace('府', '').replace('道', '').replace('都', '')}.jp/"
        
        return RegistryEntry(
            municipality_code=municipality_code,
            name=name,
            prefecture=prefecture,
            base_url=base_url,
            bid_url_pattern=bid_url,
            bid_system="GEPS",
            parser_type="generic",
            url_type="generated",
        )