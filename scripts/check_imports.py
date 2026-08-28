"""全ライブラリのインポート確認スクリプト

実行: python scripts/check_imports.py
"""
import sys

ROOT = "I:/入札システム"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, ".")

MODULES = [
    # サードパーティ
    "streamlit",
    "pdfplumber",
    "pydantic",
    "sqlalchemy",
    "requests",
    "dotenv",
    "plotly",
    # プロジェクト内
    "config",
    "exceptions",
    "utils.rate_limiter",
    "utils.session_manager",
    "utils.request_throttler",
    "database.base",
    "database.engine",
    "database.connection",
    "database.models.extraction_result",
    "database.repositories.extraction_result_repository",
]

failed = []
for mod in MODULES:
    try:
        __import__(mod)
        print(f"OK:   {mod}")
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {mod} - {exc}")
        failed.append(mod)

if failed:
    print(f"\n失敗: {len(failed)} 件 -> {failed}")
    sys.exit(1)
print("\n全インポート成功")
