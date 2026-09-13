"""参加資格タグSeeder の単体テスト"""
import pytest
from database.engine import SessionLocal
from database.models import QualificationTag
from database.seeders.qualification_tag_seeder import (
    seed_qualification_tags,
    load_master_csv,
)


@pytest.fixture
def session():
    """テスト用セッション"""
    s = SessionLocal()
    yield s
    s.close()


def test_load_master_csv():
    """マスターCSVが読み込めること"""
    rows = load_master_csv()
    assert len(rows) >= 23, f"Expected >= 23 tags, got {len(rows)}"
    # tag_code キーが存在すること
    assert "tag_code" in rows[0]


def test_seed_inserts_all(session):
    """seed 実行で全レコードが挿入されること"""
    # Clear existing tags
    session.query(QualificationTag).delete()
    session.commit()
    stats = seed_qualification_tags(session)
    assert stats["inserted"] >= 23


def test_seed_is_idempotent(session):
    """2回目実行で inserted=0 になること"""
    seed_qualification_tags(session)  # 1回目
    stats = seed_qualification_tags(session)  # 2回目
    assert stats["inserted"] == 0
