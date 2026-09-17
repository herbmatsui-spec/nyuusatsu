"""都道府県レジストリ。

``data/prefecture_urls.csv`` から都道府県の base_url / bid_url_pattern を
読み込み、``RegistryRecord`` として返す。CSV 列:
  municipality_code, name, base_url, bid_url_pattern, bid_system, parser_type, parent_id
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator, Optional

from crawler.registry import BaseRegistry, PROJECT_ROOT, RegistryRecord

DEFAULT_CSV = "data/prefecture_urls.csv"


class PrefectureRegistry(BaseRegistry):
    """都道府県 URL レジストリ。"""

    name = "prefecture"

    def __init__(self, csv_path: Optional[str] = None) -> None:
        super().__init__(self._resolve_path(csv_path, DEFAULT_CSV))


    def iter_records(self) -> Iterator[RegistryRecord]:
        rows = self._read_csv(self.csv_path)
        for row in rows:
            bid_url_pattern = (row.get("bid_url_pattern") or "").strip()
            yield RegistryRecord(
                municipality_code=(row.get("municipality_code") or "").strip(),
                name=(row.get("name") or "").strip(),
                base_url=(row.get("base_url") or "").strip(),
                bid_url_pattern=bid_url_pattern,
                bid_system=(row.get("bid_system") or "").strip(),
                category="prefecture",
                type="prefecture",
                region=(row.get("name") or "").strip(),
                parser_type=(row.get("parser_type") or "generic").strip() or "generic",
                parent_id=(row.get("parent_id") or "").strip(),
            )
