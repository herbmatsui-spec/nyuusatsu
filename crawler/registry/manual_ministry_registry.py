"""国政府庁レジストリ（手動収集版）。

``data/manual_ministry_domains.csv`` から省庁の base_url を読み込み、
bid_url_pattern は GEPS 検索 URL をフォールバックとして生成して
``RegistryRecord`` として返す。CSV 列:
  agency_name, base_url, note
"""
from __future__ import annotations

import urllib.parse
from pathlib import Path
from typing import Iterator, Optional

from crawler.registry import BaseRegistry, PROJECT_ROOT, RegistryRecord

DEFAULT_CSV = "data/manual_ministry_domains.csv"


class ManualMinistryRegistry(BaseRegistry):
    """国政府庁 URL レジストリ（手動収集版）。"""

    name = "manual_ministry"

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
            base_url = (row.get("base_url") or "").strip()
            note = (row.get("note") or "").strip()
            bid_url_pattern = (row.get("bid_url_pattern") or "").strip()
            if not bid_url_pattern:
                bid_url_pattern = self.geps_url(agency_name)
            yield RegistryRecord(
                municipality_code="",  # ministries have no municipality code
                name=agency_name,
                base_url=base_url,
                bid_url_pattern=bid_url_pattern,
                bid_system="GEPS",
                category="国",
                type="ministry",
                region="",
                parser_type="generic",
                extra={"note": note} if note else {},
            )
