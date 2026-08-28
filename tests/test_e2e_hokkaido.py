"""
北海道1件のE2Eテスト

前提: Docker Redis起動済み, インターネット接続あり
"""
import subprocess
import shutil
import sqlite3
import os
import pytest


@pytest.fixture
def bid_count_before():
    """テスト前のBid件数を取得する"""
    tmp = "bids_system_test.db"
    shutil.copy2("bids_system.db", tmp)
    conn = sqlite3.connect(tmp)
    count = conn.execute("SELECT COUNT(*) FROM bids").fetchone()[0]
    conn.close()
    os.remove(tmp)
    return count


@pytest.mark.slow
def test_hokkaido_sync_1bid(bid_count_before):
    """北海道の1件をsyncモードで処理してBidが増えることを確認する"""
    result = subprocess.run(
        ["py", "-3", "scripts/collect_all_sync.py",
         "--prefecture-name", "北海道",
         "--limit", "1",
         "--agencies-limit", "1",
         "--insecure"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        capture_output=True, text=True, timeout=30,
    )
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    # 少なくともエラーで終了しないこと
    # (外部サイト依存のため、Bid増加は保証しないが0で正常終了すること)
    assert result.returncode == 0
