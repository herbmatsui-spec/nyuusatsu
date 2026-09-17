"""国政府庁レジストリ。

``data/master_ministries.csv`` から省庁の名前を読み込み、
base_url は空とし、bid_url_pattern は GEPS 検索 URL を生成して
``RegistryRecord`` として返す。CSV 列:
  agency_name, municipality_code, priority_level, parent_id
"""
from __future__ import annotations

import urllib.parse
from pathlib import Path
from typing import Iterator, Optional

from crawler.registry import BaseRegistry, PROJECT_ROOT, RegistryRecord

DEFAULT_CSV = "data/master_ministries.csv"


class MinistryRegistry(BaseRegistry):
    """国政府庁 URL レジストリ。"""

    name = "ministry"

    def __init__(self, csv_path: Optional[str] = None) -> None:
        super().__init__(self._resolve_path(csv_path, DEFAULT_CSV))

    @staticmethod
    def geps_url(agency_name: str) -> str:
        encoded = urllib.parse.quote(agency_name)
        return f"https://search.geps.go.jp/search?q={encoded}"

    def iter_records(self) -> Iterator[RegistryRecord]:
        rows = self._read_csv(self.csv_path)
        for row in rows:
            agency_name = (row.get("agency_name") or row.get("name") or "").strip()
            municipality_code = (row.get("municipality_code") or "").strip()
            bid_url_pattern = (row.get("bid_url_pattern") or "").strip()
            if not bid_url_pattern:
                bid_url_pattern = self.geps_url(agency_name) if agency_name else ""
            yield RegistryRecord(
                municipality_code=municipality_code,
                name=agency_name,
                base_url=(row.get("base_url") or "").strip(),
                bid_url_pattern=bid_url_pattern,
                bid_system=(row.get("bid_system") or "GEPS").strip(),
                category="ministry",
                type="ministry",
                region=(row.get("region") or "").strip(),
                parser_type=(row.get("parser_type") or "generic").strip(),
                parent_id=(row.get("parent_id") or "").strip(),
            )
