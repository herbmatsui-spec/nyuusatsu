"""全市区町村レジストリ（テンプレートベース + マスタ補完）

``data/master/municipality_codes.csv`` が存在する場合はそれを優先して
(base_url 等の完全データ) 読み込み、存在しない市区町村については JIS
都道府県コードから URL を生成するテンプレートを適用する。

テンプレート生成ロジック:
  - 都道府県コード(上2桁)から都道府県ドメインの対応表を参照
  - GEPS 検索 URL ``https://search.geps.go.jp/search?q={name}&pref={code}``
    を bid_url_pattern として用いる（全国共通の調達ポータル）
"""
from __future__ import annotations

import urllib.parse
from pathlib import Path
from typing import Iterator, Optional

from crawler.registry import BaseRegistry, RegistryRecord

DEFAULT_MASTER = "data/master/municipality_codes.csv"

PREF_DOMAINS = {
    "01": "hokkaido", "02": "aomori", "03": "iwate", "04": "miyagi",
    "05": "akita", "06": "yamagata", "07": "fukushima", "08": "ibaraki",
    "09": "tochigi", "10": "gunma", "11": "saitama", "12": "chiba",
    "13": "tokyo", "14": "kanagawa", "15": "niigata", "16": "toyama",
    "17": "ishikawa", "18": "fukui", "19": "yamanashi", "20": "nagano",
    "21": "gifu", "22": "shizuoka", "23": "aichi", "24": "mie",
    "25": "shiga", "26": "kyoto", "27": "osaka", "28": "hyogo",
    "29": "nara", "30": "wakayama", "31": "tottori", "32": "shimane",
    "33": "okayama", "34": "hiroshima", "35": "yamaguchi", "36": "tokushima",
    "37": "kagawa", "38": "ehime", "39": "kochi", "40": "fukuoka",
    "41": "saga", "42": "nagasaki", "43": "kumamoto", "44": "oita",
    "45": "miyazaki", "46": "kagoshima", "47": "okinawa",
}


class MunicipalityRegistry(BaseRegistry):
    """テンプレートベースで URL を生成するレジストリ。

    マスタ CSV があればそれを使い、なければ JIS コードからテンプレート生成。
    """

    name = "municipality"

    def __init__(self, csv_path: Optional[str] = None) -> None:
        super().__init__(self._resolve_path(csv_path, DEFAULT_MASTER))

    @staticmethod
    def geps_url(municipality_code: str, name: str) -> str:
        encoded = urllib.parse.quote(name)
        pref = str(municipality_code)[:2]
        return f"https://search.geps.go.jp/search?q={encoded}&pref={pref}"

    @staticmethod
    def _prefecture_code(code: str) -> str:
        return str(code).zfill(2)[:2]

    @staticmethod
    def _default_base_url(pref_code: str, name: str) -> str:
        domain = PREF_DOMAINS.get(pref_code)
        if domain is None:
            return ""
        if name.startswith("東京都"):
            return "https://www.metro.tokyo.lg.jp/"
        return f"https://www.pref.{domain}.lg.jp/"

    def iter_records(self) -> Iterator[RegistryRecord]:
        rows = self._read_csv(self.csv_path)
        for row in rows:
            mcode = (row.get("municipality_code") or "").strip()
            name = (row.get("name") or "").strip()
            base_url = (row.get("base_url") or "").strip()
            if not base_url:
                base_url = self._default_base_url(self._prefecture_code(mcode), name)
            bid_url_pattern = (row.get("bid_url_pattern") or "").strip()
            if not bid_url_pattern:
                bid_url_pattern = self.geps_url(mcode, name)
            yield RegistryRecord(
                municipality_code=mcode,
                name=name,
                base_url=base_url,
                bid_url_pattern=bid_url_pattern,
                bid_system=(row.get("bid_system") or "GEPS").strip() or "GEPS",
                category=(row.get("category") or "municipality").strip(),
                type=(row.get("type") or "municipality").strip(),
                region=(row.get("region") or "").strip() or name,
                parser_type=(row.get("parser_type") or "generic").strip() or "generic",
            )
