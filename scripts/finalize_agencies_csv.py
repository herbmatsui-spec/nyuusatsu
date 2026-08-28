import csv
import os
import sys

# Reconfigure stdout for Japanese encoding on Windows console
sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "data", "agencies.csv")

def main():
    if not os.path.exists(CSV_PATH):
        print(f"Error: {CSV_PATH} not found.")
        sys.exit(1)

    print(f"Loading agencies from {CSV_PATH} for final checks...")
    
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Total rows: {len(rows)}")

    unique_names = {}
    cleaned_rows = []
    duplicates_removed = 0
    missing_fields_fixed = 0

    for i, row in enumerate(rows, 1):
        name = row.get("name")
        if not name:
            print(f"Row {i}: Missing name, skipping.")
            continue
            
        # Clean whitespaces
        name = name.strip()
        row["name"] = name
        
        # Deduplicate by name
        if name in unique_names:
            print(f"Duplicate found: {name} (Row {i} and Row {unique_names[name]}). Removing Row {i}.")
            duplicates_removed += 1
            continue
            
        unique_names[name] = i

        # Check is_active values (must be 'True' or 'False')
        is_active = row.get("is_active", "True").strip().capitalize()
        if is_active not in ["True", "False"]:
            print(f"Row {i} ({name}): Invalid is_active value '{is_active}'. Defaulting to 'True'.")
            is_active = "True"
            missing_fields_fixed += 1
        row["is_active"] = is_active

        # Ensure parser_type and frequency have default values if missing
        if not row.get("parser_type"):
            row["parser_type"] = "heuristic"
            missing_fields_fixed += 1
        if not row.get("frequency"):
            row["frequency"] = "weekly"
            missing_fields_fixed += 1

        cleaned_rows.append(row)

    # Write cleaned rows back to CSV
    print(f"Writing back cleaned agencies (Total: {len(cleaned_rows)}, Removed duplicates: {duplicates_removed}, Fixed fields: {missing_fields_fixed})")
    
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "name", "type", "region", "base_url", "target_url", 
            "parser_type", "frequency", "municipality_code", "category", "is_active"
        ])
        writer.writeheader()
        writer.writerows(cleaned_rows)

    print("agencies.csv finalized successfully.")

if __name__ == "__main__":
    main()
