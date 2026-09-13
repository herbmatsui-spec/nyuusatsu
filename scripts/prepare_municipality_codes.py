import csv
import os

def prepare_municipalities_for_import():
    """
    fetch_municipality_codes.py の出力から、import_agencies.py 用の CSV を生成する。
    - 都道府県（category=prefecture）は除外
    - base_url は一旦空にする（後工程で設定）
    - category は「市区町村」カテゴリ名を出力（import 側で category_id に変換）
    - target_url, parser_type, frequency, is_active を追加
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    input_path = os.path.join(base_dir, "data", "master", "municipality_codes.csv")
    output_path = os.path.join(base_dir, "data", "municipalities.csv")

    if not os.path.exists(input_path):
        print(f"Input file not found: {input_path}")
        return

    with open(input_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Loaded {len(rows)} records from {input_path}")

    # Filter out prefectures
    municipalities = [r for r in rows if r.get("category") != "prefecture"]
    print(f"Filtered to {len(municipalities)} municipalities (excluded prefectures)")

    # Prepare output rows
    output_rows = []
    for row in municipalities:
        output_rows.append({
            "name": row["name"],
            "type": row["type"],
            "region": row["region"],
            "base_url": "",  # 一旦空（後工程で設定）
            "target_url": "",  # 後工程で設定
            "parser_type": "heuristic",
            "frequency": "daily",
            "municipality_code": row["municipality_code"],
            "category": "市区町村",  # import 側で category_id に変換
            "is_active": "True",
        })

    # Write output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fieldnames = ["name", "type", "region", "base_url", "target_url", "parser_type", "frequency", "municipality_code", "category", "is_active"]
    
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Successfully created {output_path} with {len(output_rows)} entries.")

if __name__ == "__main__":
    prepare_municipalities_for_import()
