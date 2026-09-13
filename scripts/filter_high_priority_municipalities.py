"""Filter high-priority municipalities from population data.

Reads ``data/municipality_population.csv`` and filters for a minimum population
threshold (default: 100,000), producing ``data/high_priority_municipalities.csv``.

The output CSV includes all columns from the input (municipality_code, name,
population, prefecture, base_url) so it can be used directly by the config
generator script.
"""

import argparse
import csv
import os
import sys

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_PATH = os.path.join(BASE_DIR, "data", "municipality_population.csv")
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "high_priority_municipalities.csv")

DEFAULT_POPULATION_THRESHOLD = 100_000


def filter_with_pandas(input_path, output_path, threshold):
    df = pd.read_csv(input_path, encoding="utf-8-sig")
    high_pop = df[df["population"] >= threshold].copy()
    high_pop = high_pop.sort_values("population", ascending=False)
    high_pop.to_csv(output_path, index=False, encoding="utf-8-sig")
    return len(high_pop)


def filter_with_csv(input_path, output_path, threshold):
    with open(input_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    high_pop = [row for row in rows if int(row["population"]) >= threshold]
    high_pop.sort(key=lambda r: int(r["population"]), reverse=True)

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=reader.fieldnames)
        writer.writeheader()
        writer.writerows(high_pop)

    return len(high_pop)


def main():
    parser = argparse.ArgumentParser(description="Filter high-priority municipalities by population")
    parser.add_argument("--input", default=INPUT_PATH, help="Input CSV path")
    parser.add_argument("--output", default=OUTPUT_PATH, help="Output CSV path")
    parser.add_argument("--threshold", type=int, default=DEFAULT_POPULATION_THRESHOLD,
                        help=f"Minimum population threshold (default: {DEFAULT_POPULATION_THRESHOLD})")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file not found at {args.input}")
        print("Run scripts/fetch_municipality_population.py first.")
        sys.exit(1)

    if HAS_PANDAS:
        count = filter_with_pandas(args.input, args.output, args.threshold)
    else:
        count = filter_with_csv(args.input, args.output, args.threshold)

    print(f"Filtered {count} high-priority municipalities (population >= {args.threshold:,})")
    print(f"Output written to: {args.output}")

    with open(args.output, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print("\nTop 10 high-priority municipalities:")
    for row in rows[:10]:
        print(f"  {row['municipality_code']} {row['name']} ({row['prefecture']}) - {int(row['population']):,}")

    prefectures = {}
    for row in rows:
        pref = row["prefecture"]
        prefectures[pref] = prefectures.get(pref, 0) + 1
    print(f"\nDistribution by prefecture ({len(prefectures)} prefectures):")
    for pref in sorted(prefectures.keys()):
        print(f"  {pref}: {prefectures[pref]}")

    print(f"\nSuccessfully generated {args.output}")


if __name__ == "__main__":
    main()
