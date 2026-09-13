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
        numeric_code = municipality_code  # fallback
    # URL encode the prefecture name (Japanese)
    encoded_name = urllib.parse.quote(municipality_name)
    url = f"https://search.geps.go.jp/search?q={encoded_name}&pref={numeric_code}"
    return ("geps", url, "agency_specific", "GEPS")

# Now generate the seeder file content
output_lines = []
output_lines.append('\"\"\"Prefecture / source seed data (reconstructed best-effort).')
output_lines.append('')
output_lines.append('The original constants are not available; provide reasonable placeholders so')
output_lines.append('imports resolve. Adjust the data to match production as needed.')
output_lines.append('\"\"\"')
output_lines.append('')
output_lines.append('from typing import Dict, List, Tuple')
output_lines.append('')
output_lines.append('PREFECTURES: List[Tuple[str, str, str, str, int, str]] = [')

for tup in PREFECTURES_TUPLES:
    # Format each tuple as a string
    # Need to quote strings properly
    code, name, kana, region, priority, official_url = tup
    # Escape quotes inside strings if any (should not be)
    line = f'    ("{code}", "{name}", "{kana}", "{region}", {priority}, "{official_url}"),'
    output_lines.append(line)

output_lines.append(']')
output_lines.append('')
output_lines.append('HOKKAIDO_SOURCES: List[Tuple[str, str, str, str]] = [')

for tup in HOKKAIDO_SOURCES_TUPLES:
    source_type, url, parser_type, notes = tup
    line = f'    ("{source_type}", "{url}", "{parser_type}", "{notes}"),'
    output_lines.append(line)

output_lines.append(']')
output_lines.append('')
output_lines.append('')
output_lines.append('def geps_source_for(municipality_code: str, municipality_name: str) -> Tuple[str, str, str, str]:')
output_lines.append('    \"\"\"Return the GEPS source URL for a given municipality code.\"\"\"')
output_lines.append('    import urllib.parse')
output_lines.append('    import re')
output_lines.append('    m = re.match(r\'JP-(\\d+)\', municipality_code)')
output_lines.append('    if m:')
output_lines.append('        numeric_code = m.group(1)')
output_lines.append('    else:')
output_lines.append('        numeric_code = municipality_code')
output_lines.append('    encoded_name = urllib.parse.quote(municipality_name)')
output_lines.append('    url = f"https://search.geps.go.jp/search?q={encoded_name}&pref={numeric_code}"')
output_lines.append('    return ("geps", url, "agency_specific", "GEPS")')

output = '\n'.join(output_lines)
print(output)