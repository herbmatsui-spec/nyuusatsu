"""Fetch Japanese municipality population data from Wikipedia and join with localgovjp codes.

Produces ``data/municipality_population.csv`` with columns:
municipality_code, name, population, prefecture, base_url

Sources:
- Local government codes + URLs: https://code4fukui.github.io/localgovjp/
- Population data: English Wikipedia "List of cities in Japan"
"""

import csv
import io
import os
import sys
import unicodedata
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
MASTER_DIR = os.path.join(DATA_DIR, "master")
OUTPUT_PATH = os.path.join(DATA_DIR, "municipality_population.csv")

LOCALGOVJP_PREF_URL = "https://code4fukui.github.io/localgovjp/prefjp-utf8.csv"
LOCALGOVJP_MUNI_URL = "https://code4fukui.github.io/localgovjp/localgovjp-utf8.csv"
WIKIPEDIA_URL = "https://en.wikipedia.org/api/rest_v1/page/html/List_of_cities_in_Japan"


def normalize_prefecture_name(name):
    """Normalize English prefecture names by stripping diacritics (e.g. Kōchi -> Kochi)."""
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_name


def normalize_city_name(name):
    """Normalize Japanese city names to handle common character variations.

    Replaces ヶ (U+30F6) with ケ (U+30B2) which appear in different datasets.
    """
    return name.replace("\u30f6", "\u30b2")


def lookup_prefecture(norm_name, pref_en_to_ja):
    """Look up a prefecture name, handling cases where multiple are concatenated."""
    if norm_name in pref_en_to_ja:
        return pref_en_to_ja[norm_name]
    # Handle concatenated names (e.g. "OitaOita" from section headers)
    for en, ja in pref_en_to_ja.items():
        if en in norm_name and len(en) >= 3:
            return ja
    return None


def build_prefecture_mapping():
    """Fetch prefecture codes from localgovjp to build English->Japanese name mapping."""
    print(f"Fetching prefecture mapping from: {LOCALGOVJP_PREF_URL}")
    req = urllib.request.Request(LOCALGOVJP_PREF_URL, headers={"User-Agent": "Mozilla/5.0"})
    content = urllib.request.urlopen(req, timeout=60).read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    mapping = {}
    for row in reader:
        pref_en = normalize_prefecture_name(row.get("pref_en", "").strip())
        pref_ja = row.get("pref", "").strip()
        if pref_en and pref_ja:
            mapping[pref_en] = pref_ja
    print(f"  Built mapping for {len(mapping)} prefectures")
    return mapping


def fetch_wikipedia_population(pref_en_to_ja):
    """Fetch population data from Wikipedia HTML and return dict keyed by (pref_ja, name_ja)."""
    print(f"Fetching population data from Wikipedia: {WIKIPEDIA_URL}")
    req = urllib.request.Request(WIKIPEDIA_URL, headers={"User-Agent": "Mozilla/5.0"})
    content = urllib.request.urlopen(req, timeout=60).read().decode("utf-8")

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("ERROR: beautifulsoup4 is required. Install with: pip install beautifulsoup4")
        sys.exit(1)

    soup = BeautifulSoup(content, "html.parser")
    tables = soup.find_all("table", class_="wikitable")
    if len(tables) < 2:
        print("ERROR: Could not find population table on Wikipedia page")
        sys.exit(1)

    table = tables[1]
    rows = table.find_all("tr")
    population_map = {}
    unmapped_prefs = set()

    for row in rows[1:]:
        cells = row.find_all(["th", "td"])
        if len(cells) < 8:
            continue
        name_ja = normalize_city_name(cells[1].get_text(strip=True))
        pref_en = cells[2].get_text(strip=True)
        pop_text = cells[3].get_text(strip=True)

        if not name_ja or not pref_en or not pop_text:
            continue

        pref_ja = lookup_prefecture(normalize_prefecture_name(pref_en), pref_en_to_ja)
        if not pref_ja:
            unmapped_prefs.add(pref_en)
            continue

        pop_text_clean = pop_text.replace(",", "")
        if not pop_text_clean.isdigit():
            continue

        population = int(pop_text_clean)
        key = (pref_ja, name_ja)
        population_map[key] = population

    print(f"Parsed {len(population_map)} population entries from Wikipedia")
    if unmapped_prefs:
        print(f"Unmapped prefectures: {sorted(unmapped_prefs)}")
    return population_map


def fetch_localgovjp_municipalities():
    """Fetch the localgovjp municipality codes CSV and return list of dicts."""
    print(f"Fetching municipality codes from: {LOCALGOVJP_MUNI_URL}")
    req = urllib.request.Request(LOCALGOVJP_MUNI_URL, headers={"User-Agent": "Mozilla/5.0"})
    content = urllib.request.urlopen(req, timeout=60).read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)

    municipalities = []
    for row in rows:
        city = row.get("city", "").strip()
        pref = row.get("pref", "").strip()
        url = row.get("url", "").strip()
        lgcode = row.get("lgcode", "").strip().zfill(6)

        if not city or not pref or not lgcode:
            continue
        if " " in city:
            continue

        is_town_or_village = city.endswith("町") or city.endswith("村")
        name = f"{pref}{city}" if is_town_or_village else city

        municipalities.append({
            "municipality_code": lgcode,
            "name": name,
            "city": city,
            "prefecture": pref,
            "base_url": url,
        })

    print(f"Parsed {len(municipalities)} municipalities from localgovjp")
    return municipalities


def main():
    os.makedirs(MASTER_DIR, exist_ok=True)

    pref_en_to_ja = build_prefecture_mapping()
    population_map = fetch_wikipedia_population(pref_en_to_ja)
    municipalities = fetch_localgovjp_municipalities()

    results = []
    not_found = []

    for muni in municipalities:
        city_normalized = normalize_city_name(muni["city"])
        key = (muni["prefecture"], city_normalized)
        pop = population_map.get(key)

        if pop is not None:
            results.append({
                "municipality_code": muni["municipality_code"],
                "name": muni["name"],
                "population": pop,
                "prefecture": muni["prefecture"],
                "base_url": muni["base_url"],
            })
        else:
            not_found.append(muni)

    results.sort(key=lambda x: x["population"], reverse=True)

    print(f"\nResults:")
    print(f"  Joined: {len(results)} municipalities with population data")
    print(f"  No population match: {len(not_found)} municipalities")

    fieldnames = ["municipality_code", "name", "population", "prefecture", "base_url"]
    with open(OUTPUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"  Written to: {OUTPUT_PATH}")

    print("\nTop 10 municipalities by population:")
    for r in results[:10]:
        print(f"  {r['municipality_code']} {r['name']} ({r['prefecture']}) - {r['population']:,}")

    high_pop = [r for r in results if r["population"] >= 100000]
    print(f"\nMunicipalities with population >= 100,000: {len(high_pop)}")

    high_pop_missing = [m for m in not_found if "市" in m["city"] or "区" in m["city"]]
    if high_pop_missing:
        print(f"\nNOTE: {len(high_pop_missing)} cities/wards without population match:")
        for m in high_pop_missing[:10]:
            print(f"  {m['municipality_code']} {m['name']} ({m['prefecture']})")

    print(f"\nSuccessfully generated {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
