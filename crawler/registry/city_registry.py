"""市区町村（指定都市・中核市・市・町・村）レジストリ。

``data/city_urls.csv`` から市区町村の URL を読み込み、``RegistryRecord`` として返す。
CSV 列:
  municipality_code, prefecture, name, type, base_url, bid_url_pattern, bid_system, parser_type
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator, Optional

from crawler.registry import BaseRegistry, PROJECT_ROOT, RegistryRecord

DEFAULT_CSV = "data/city_urls.csv"


class CityRegistry(BaseRegistry):
    """市区町村 URL レジストリ。"""

    name = "city"

    def __init__(self, csv_path: Optional[str] = None) -> None:
        super().__init__(self._resolve_path(csv_path, DEFAULT_CSV))

    def iter_records(self) -> Iterator[RegistryRecord]:
        rows = self._read_csv(self.csv_path)
        for row in rows:
            mcode = (row.get("municipality_code") or "").strip()
            name = (row.get("name") or "").strip()
            prefecture = (row.get("prefecture") or "").strip()
            cat = (row.get("type") or "city").strip()
            bid_url_pattern = (row.get("bid_url_pattern") or "").strip()
            yield RegistryRecord(
                municipality_code=mcode,
                name=name,
                base_url=(row.get("base_url") or "").strip(),
                bid_url_pattern=bid_url_pattern,
                bid_system=(row.get("bid_system") or "").strip(),
                category=cat,
                type=cat,
                region=prefecture or name,
                parser_type=(row.get("parser_type") or "generic").strip() or "generic",
            )
