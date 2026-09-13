"""外郭団体レジストリ。

``data/master_quasi_agencies.csv`` から外郭団体の名前を読み込み、
base_url は空とし、bid_url_pattern は GEPS 検索 URL を生成して
``RegistryRecord`` として返す。CSV 列:
  agency_name, municipality_code, priority_level
"""
from __future__ import annotations

import urllib.parse
from pathlib import Path
from typing import Iterator, Optional

from crawler.registry import BaseRegistry, PROJECT_ROOT, RegistryRecord

DEFAULT_CSV = "data/master_quasi_agencies.csv"


class QuasiAgencyRegistry(BaseRegistry):
    """外郭団体 URL レジストリ。"""

    name = "quasi"

    def __init__(self, csv_path: Optional[str] = None) -> None:
        super().__init__(self._resolve_path(csv_path, DEFAULT_CSV))

    @staticmethod
    def geps_url(agency_name: str) -> str:
        encoded = urllib.parse.quote(agency_name)
        return f"https://search.geps.go.jp/search?q={encoded}"

    def iter_records(self) -> Iterator[RegistryRecord]:
        rows = self._read_csv(self.csv_path)
        for row in rows:
            agency_name = (row.get("agency_name") or "").strip()
            municipality_code = (row.get("municipality_code") or "").strip()
            priority_level = (row.get("priority_level") or "").strip()
            bid_url_pattern = self.geps_url(agency_name) if agency_name else ""
            yield RegistryRecord(
                municipality_code=municipality_code,
                name=agency_name,
                base_url="",  # quasi agencies have diverse domains; leave empty
                bid_url_pattern=bid_url_pattern,
                bid_system="GEPS",
                category="quasi",
                type="quasi",
                region="",
                parser_type="generic",
            )
