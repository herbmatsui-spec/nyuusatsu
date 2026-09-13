"""URL Registry base classes and common interfaces."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class RegistryEntry:
    """Represents a single entry in the URL registry."""
    municipality_code: str
    name: str
    prefecture: str
    base_url: str
    bid_url_pattern: str
    bid_system: str
    parser_type: str
    url_type: str  # "prefecture" or "city"


@dataclass
class RegistryRecord:
    """Record format expected by sync script."""
    municipality_code: str
    name: str
    region: str
    base_url: str
    bid_url_pattern: str
    category: str
    type: str
    bid_system: str
    parser_type: str


class BaseRegistry(ABC):
    """Abstract base class for URL registries."""

    @abstractmethod
    def load(self) -> None:
        """Load registry data from source (CSV, DB, etc.)."""
        pass

    @abstractmethod
    def get_entry(self, municipality_code: str) -> Optional[RegistryEntry]:
        """Get registry entry by municipality code."""
        pass

    @abstractmethod
    def get_all_entries(self) -> List[RegistryEntry]:
        """Get all registry entries."""
        pass

    @abstractmethod
    def get_entries_by_prefecture(self, prefecture: str) -> List[RegistryEntry]:
        """Get entries filtered by prefecture."""
        pass

    def all_records(self) -> List[RegistryRecord]:
        """Convert all entries to RegistryRecord format for sync script."""
        entries = self.get_all_entries()
        return [
            RegistryRecord(
                municipality_code=e.municipality_code,
                name=e.name,
                region=e.prefecture,
                base_url=e.base_url,
                bid_url_pattern=e.bid_url_pattern,
                category=e.url_type,
                type=e.url_type,
                bid_system=e.bid_system,
                parser_type=e.parser_type,
            )
            for e in entries
        ]