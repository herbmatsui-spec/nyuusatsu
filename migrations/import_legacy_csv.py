from migrations.csv_to_db import migrate_csv_to_db

def run_import():
    """
    レガシーCSVデータをインポートするメインエントリポイント。
    """
    print("Starting legacy CSV import...")
    migrate_csv_to_db("./bid_ledger.csv")
    print("Import completed.")

if __name__ == "__main__":
    run_import()
