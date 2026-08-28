"""発注機関インベントリ初期投入スクリプト

- すべての都道府県コードに対して `PrefectureFetcher` を実行し、`agency_inventory` テーブルにレコード登録
- 市区町村データが `MUNICIPALITY_SOURCES` に存在すれば `MunicipalityFetcher` も実行
"""

import sys
from typing import List

from config.prefectures import PREFECTURES
from crawler.agency_lists.prefecture_fetcher import PrefectureFetcher
from crawler.agency_lists.municipality_fetcher import MunicipalityFetcher


def main(pref_codes: List[str] | None = None):
    if pref_codes is None:
        pref_codes = list(PREFECTURES.keys())
    # Prefecture level
    pref_fetcher = PrefectureFetcher()
    for code in pref_codes:
        try:
            pref_fetcher.fetch_and_store(code)
            print(f"[Prefecture] {code} ({PREFECTURES.get(code)}) processed")
        except Exception as e:
            print(f"Error processing prefecture {code}: {e}", file=sys.stderr)
    # Municipality level (if any data present)
    muni_fetcher = MunicipalityFetcher()
    for code in pref_codes:
        try:
            muni_fetcher.fetch_and_store(code)
            print(f"[Municipality] {code} processed")
        except Exception as e:
            # Might be missing data – skip silently
            pass

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Seed script failed: {e}", file=sys.stderr)
        sys.exit(1)
