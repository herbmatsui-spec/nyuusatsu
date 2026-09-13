# High-Priority Municipal Config Generation

## Overview

This directory contains crawler config JSON files for high-priority Japanese municipalities
(population ≥ 100,000). Each file is named `{municipality_code}_{municipality_name}.json`
and follows the same format as `ehime.json`.

## Generation Procedure

Three scripts are involved in the pipeline:

### 1. Fetch Population Data

```bash
python scripts/fetch_municipality_population.py
```

Produces `data/municipality_population.csv` with columns:
`municipality_code, name, population, prefecture, base_url`

**Data sources:**
- Municipality codes and URLs: [Code4Fukui localgovjp](https://code4fukui.github.io/localgovjp/)
- Population data: [Wikipedia - List of cities in Japan](https://en.wikipedia.org/wiki/List_of_cities_in_Japan)

The script joins the two datasets on `(prefecture, city_name)`.

### 2. Filter High-Priority Municipalities

```bash
python scripts/filter_high_priority_municipalities.py
```

Produces `data/high_priority_municipalities.csv` — all rows with population ≥ 100,000,
sorted by population (descending).

The threshold can be overridden:
```bash
python scripts/filter_high_priority_municipalities.py --threshold 50000
```

### 3. Generate Config Files

```bash
python scripts/generate_high_priority_municipality_configs.py
```

Generates 286 individual JSON config files under:
`crawler/parsers/agency_config/municipalities/high_priority/`

## Config Loader Integration

`AgencyConfigLoader` (in `crawler/parsers/agency_config_loader.py`) searches
`crawler/parsers/agency_config/` and all subdirectories recursively for `.json`
files. This means:

1. **Hand-tuned configs** (e.g., `ehime.json`) take precedence for municipalities
   defined there.
2. **Generated configs** in `municipalities/high_priority/` serve as defaults
   for municipalities not yet hand-tuned.

```python
from crawler.parsers.agency_config_loader import AgencyConfigLoader

loader = AgencyConfigLoader()
config = loader.load("横浜市")  # Loads from high_priority/ directory
```

## Config Template

The template at `crawler/parsers/agency_config/municipality_template.json`
defines default fields. Fields that can be overridden per-municipality:

| Field | Default | Description |
|-------|---------|-------------|
| `entry_url` | `{}` | Base URL of the municipality website |
| `url_includes` | `["/"]` | URL path prefixes to match |
| `title_keywords` | `["入札", "公告", "調達", "競争"]` | Keywords for bid-related pages |
| `css_selectors` | `["a[href*='pdf']"]` | CSS selectors for content extraction |
| `municipality_code` | `""` | 6-digit lgcode |
| `population` | — | Population (metadata, for reference) |

## Regenerating All Configs

To regenerate from scratch:

```bash
python scripts/fetch_municipality_population.py
python scripts/filter_high_priority_municipalities.py
python scripts/generate_high_priority_municipality_configs.py
```
