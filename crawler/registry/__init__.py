"""URL registry package.

各レジストリは ``data/`` 以下のCSVまたはテンプレートから URL を読み込み、
共通の ``RegistryRecord`` で返す。基底クラス ``BaseRegistry`` は
``get_url(agency_code)`` 等の共通インターフェースを定義する。
"""
from __future__ import annotations

import csv
import os
import logging
from pathlib import Path
from typing import Dict, Iterator, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def registry_identity(municipality_code: str, name: str) -> str:
    code = (municipality_code or "").strip()
    return f"code:{code}" if code else f"name:{name.strip()}"


@dataclass
class RegistryRecord:
    """レジストリ1レコード（ agencies / url_registry 同期の単位）。"""

    municipality_code: str
    name: str
    base_url: str
    bid_url_pattern: str = ""
    bid_system: str = ""
    category: str = ""
    type: str = ""
    region: str = ""
    parser_type: str = "generic"
    parent_id: str = ""
    extra: Dict[str, str] = field(default_factory=dict)

    @property
    def identity(self) -> str:
        return registry_identity(self.municipality_code, self.name)

    def __post_init__(self) -> None:
        self.parent_id = (self.parent_id or "").strip()
        if self.region in ("", None):
            self.region = self.name
        if self.type in ("", None):
            self.type = "municipality"


class BaseRegistry:
    """レジストリ基底クラス。

    サブクラスは ``iter_records`` を実装し、CSV/テンプレート/ネットから
    ``RegistryRecord`` を生成する。共通ユーティリティとして ``_read_csv`` と
    ``get_url`` を提供する。
    """

    name: str = "base"

    def __init__(self, csv_path: Optional[str] = None) -> None:
        self.csv_path = csv_path

    @staticmethod
    def _resolve_path(path: Optional[str], default: str) -> str:
        if path:
            return path
        return str(PROJECT_ROOT / default)

    @staticmethod
    def _read_csv(path: str) -> List[Dict[str, str]]:
        if not os.path.exists(path):
            logger.warning("Registry CSV not found: %s", path)
            return []
        rows: List[Dict[str, str]] = []
        with open(path, encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                rows.append({k: (v.strip() if v is not None else "") for k, v in row.items()})
        logger.info("Loaded %d rows from %s", len(rows), path)
        return rows

    def iter_records(self) -> Iterator[RegistryRecord]:
        raise NotImplementedError

    def get_url(self, agency_code: str) -> Optional[str]:
        """agency_code (municipality_code) に紐付く base_url を返す。"""
        for rec in self.iter_records():
            if rec.municipality_code == agency_code:
                return rec.base_url
        return None

    def get_record(self, agency_code: str) -> Optional[RegistryRecord]:
        for rec in self.iter_records():
            if rec.municipality_code == agency_code:
                return rec
        return None

    def all_records(self) -> List[RegistryRecord]:
        return list(self.iter_records())
