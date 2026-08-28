"""統合テストスクリプト

実行: python scripts/integration_test.py
"""
import os
import sys

ROOT = "I:/入札システム"
for p in (ROOT, "."):
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_integration.db")
os.environ.setdefault("ENABLE_AUTH", "false")
os.environ.setdefault("ENABLE_RATE_LIMIT", "false")


def test_imports() -> bool:
    mods = [
        "streamlit",
        "pdfplumber",
        "pydantic",
        "sqlalchemy",
        "dotenv",
        "config",
        "exceptions",
        "utils.rate_limiter",
        "utils.request_throttler",
        "utils.session_manager",
        "utils.auth_decorator",
        "database.base",
        "database.engine",
        "database.models.extraction_result",
        "database.repositories.extraction_result_repository",
        "app",
        "app_history",
    ]
    ok = True
    for m in mods:
        try:
            __import__(m)
            print(f"OK:   {m}")
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL: {m} - {exc}")
            ok = False
    return ok


def test_config() -> bool:
    from config import AppConfig
    cfg = AppConfig()
    assert hasattr(cfg, "auth"), "AuthConfig が不足"
    assert hasattr(cfg, "rate_limit"), "RateLimitConfig が不足"
    print("OK: config")
    return True


def test_request_throttler() -> bool:
    from utils.request_throttler import RequestThrottler
    t = RequestThrottler(max_requests=2, window_seconds=60)
    assert t.is_allowed("k"), "1回目は許可されるべき"
    assert t.is_allowed("k"), "2回目は許可されるべき"
    assert not t.is_allowed("k"), "3回目は制限されるべき"
    assert t.get_remaining("k") == 0
    print("OK: request_throttler")
    return True


def test_session_manager() -> bool:
    from utils.session_manager import SessionManager
    sm = SessionManager(timeout_minutes=60)
    sid = sm.create_session("alice")
    assert sm.validate_session(sid)
    assert sm.get_username(sid) == "alice"
    sm.logout(sid)
    assert not sm.validate_session(sid)
    print("OK: session_manager")
    return True


def test_db() -> bool:
    from database.base import Base
    from database.engine import engine
    from database.models.extraction_result import ExtractionResult
    Base.metadata.create_all(bind=engine)
    from database.repositories.extraction_result_repository import ExtractionResultRepository
    repo = ExtractionResultRepository()
    rid = repo.save({
        "filename": "test.pdf",
        "budget": "1,000,000 JPY",
        "qualifications": "記載なし",
        "deadline": "2026-12-31",
        "deliverables": "テスト成果物",
        "raw_text_length": 6,
        "created_by": "tester",
    })
    fetched = repo.find_by_id(rid)
    assert fetched is not None and fetched["id"] == rid
    all_rows = repo.find_all(limit=10)
    assert any(r["id"] == rid for r in all_rows)
    assert repo.delete(rid)
    assert repo.find_by_id(rid) is None
    print("OK: db (extraction_results)")
    return True


def main() -> int:
    results = [
        ("imports", test_imports()),
        ("config", test_config()),
        ("request_throttler", test_request_throttler()),
        ("session_manager", test_session_manager()),
        ("db", test_db()),
    ]
    print("\n--- 結果 ---")
    failed = [name for name, ok in results if not ok]
    for name, ok in results:
        print(f"{'PASS' if ok else 'FAIL'}: {name}")
    if failed:
        print(f"\n失敗: {failed}")
        return 1
    print("\n全テスト合格")
    return 0


if __name__ == "__main__":
    sys.exit(main())
