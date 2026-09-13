import csv
import re

# Read prefectures CSV
prefectures = []
with open('data/prefectures.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        prefectures.append({
            'id': int(row['id']),
            'name': row['name'],
            'code': row['code'],
            'kana': row['kana_name'],
            'region': row['region_code'],
        })

# Build PREFECTURES list of tuples (code, name, kana, region, priority, official_url)
# We'll set priority = 1, official_url = ''
# Prefix code with "JP-" to match seed script expectations
PREFECTURES_TUPLES = []
for p in prefectures:
    pref_code = "JP-" + p['code']
    PREFECTURES_TUPLES.append((
        pref_code,
        p['name'],
        p['kana'],
        p['region'],
        1,  # priority
        ''  # official_url
    ))

# HOKKAIDO_SOURCES from create_hokkaido_sources.py
# We'll extract source_type, url, parser_type, notes (ignore crawl_interval_hours)
HOKKAIDO_SOURCES_TUPLES = [
    ("web", "https://www.pref.hokkaido.lg.jp/", "heuristic", "Hokkaido official site"),
    ("geps", "https://search.geps.go.jp/search?q=%E5%8C%97%E6%B5%B7%E9%81%93&pref=01", "agency_specific", "GEPS Hokkaido"),
]

# GEPS source function
def geps_source_for(municipality_code: str, municipality_name: str) -> tuple:
    """Return the GEPS source tuple for a given municipality code and name.
    municipality_code is expected to be like "JP-01". We need to extract the numeric part.
    """
    import urllib.parse
    # Extract numeric code (remove "JP-" prefix if present)
    m = re.match(r'JP-(\d+)', municipality_code)
    if m:
        numeric_code = m.group(1)
    else:
        numeric_code = municipality_code
    # URL encode the prefecture name (Japanese)
    encoded_name = urllib.parse.quote(municipality_name)
    url = f"https://search.geps.go.jp/search?q={encoded_name}&pref={numeric_code}"
    return ("geps", url, "agency_specific", "GEPS")

# Now write the seeder file
output_path = 'database/seeders/prefecture_seeder.py'
with open(output_path, 'w', encoding='utf-8') as f:
    f.write('\"\"\"Prefecture / source seed data (reconstructed best-effort).\n')
    f.write('\n')
    f.write('The original constants are not available; provide reasonable placeholders so\n')
    f.write('imports resolve. Adjust the data to match production as needed.\n')
    f.write('\"\"\"\n')
    f.write('\n')
    f.write('from typing import Dict, List, Tuple\n')
    f.write('\n')
    f.write('PREFECTURES: List[Tuple[str, str, str, str, int, str]] = [\n')
    for tup in PREFECTURES_TUPLES:
        code, name, kana, region, priority, official_url = tup
        line = f'    ("{code}", "{name}", "{kana}", "{region}", {priority}, "{official_url}"),\n'
        f.write(line)
    f.write(']\n')
    f.write('\n')
    f.write('HOKKAIDO_SOURCES: List[Tuple[str, str, str, str]] = [\n')
    for tup in HOKKAIDO_SOURCES_TUPLES:
        source_type, url, parser_type, notes = tup
        line = f'    ("{source_type}", "{url}", "{parser_type}", "{notes}"),\n'
        f.write(line)
    f.write(']\n')
    f.write('\n')
    f.write('\n')
    f.write('def geps_source_for(municipality_code: str, municipality_name: str) -> Tuple[str, str, str, str]:\n')
    f.write('    \"\"\"Return the GEPS source URL for a given municipality code.\"\"\"\n')
    f.write('    import urllib.parse\n')
    f.write('    import re\n')
    f.write('    m = re.match(r\'JP-(\\d+)\', municipality_code)\n')
    f.write('    if m:\n')
    f.write('        numeric_code = m.group(1)\n')
    f.write('    else:\n')
    f.write('        numeric_code = municipality_code\n')
    f.write('    encoded_name = urllib.parse.quote(municipality_name)\n')
    f.write('    url = f"https://search.geps.go.jp/search?q={encoded_name}&pref={numeric_code}"\n')
    f.write('    return ("geps", url, "agency_specific", "GEPS")\n')

print(f'Written seeder to {output_path}')