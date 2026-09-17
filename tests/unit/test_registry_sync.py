from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import MultipleResultsFound

from scripts import sync_registry_to_db as sync


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    for model in (sync.AgencyCategory, sync.Agency, sync.UrlRegistry):
        model.__table__.create(engine)
    with Session(engine) as session:
        session.add_all([
            sync.AgencyCategory(id=1, name="国", priority=1),
            sync.AgencyCategory(id=4, name="外郭団体", priority=2),
        ])
        session.commit()
        yield session
    engine.dispose()


def record(name="総務省", category="国", code=""):
    return sync.RegistryRecord(
        municipality_code=code, name=name, category=category,
        base_url="https://www.soumu.go.jp/", type="ministry",
    )


def add_agency(session, name="総務省", category=1, code=""):
    agency = sync.Agency(
        name=name, category_id=category, municipality_code=code,
        created_at=datetime.now(), updated_at=datetime.now(),
    )
    session.add(agency)
    session.flush()
    return agency


@pytest.mark.parametrize("category", ["国", "ministry", "manual_ministry"])
def test_category_aliases_preserve_existing_id(session, category):
    agency = add_agency(session)
    original_id = agency.id
    categories = sync.load_category_map(session)
    for _ in range(2):
        sync.upsert_agency(session, record(category=category), categories, False)
        sync.upsert_url_registry(session, record(category=category), categories)
        session.commit()
    assert session.query(sync.Agency).count() == 1
    assert session.query(sync.UrlRegistry).count() == 1
    assert session.get(sync.Agency, original_id).base_url == record().base_url
    assert agency.category_id == 1


def test_empty_codes_do_not_overwrite_other_names_or_categories(session):
    original = add_agency(session)
    categories = sync.load_category_map(session)
    sync.upsert_agency(session, record("法務省"), categories, False)
    sync.upsert_agency(session, record(category="quasi"), categories, False)
    assert original.name == "総務省"
    assert original.category_id == 1
    assert session.query(sync.Agency).count() == 3


def test_unknown_category_fails_without_writes(session):
    with pytest.raises(ValueError, match="category"):
        sync.upsert_agency(session, record(category="unknown"), sync.load_category_map(session), False)
    assert session.query(sync.Agency).count() == 0


def test_null_category_row_is_reused_only_without_canonical_match(session):
    orphan = add_agency(session, category=None)
    sync.upsert_agency(session, record(), sync.load_category_map(session), False)
    assert orphan.category_id == 1
    assert session.query(sync.Agency).count() == 1


def test_canonical_row_wins_without_deleting_legacy_duplicate(session):
    canonical = add_agency(session)
    duplicate = add_agency(session, category=None, code=None)
    sync.upsert_agency(session, record(), sync.load_category_map(session), False)
    assert canonical.base_url == record().base_url
    assert duplicate.category_id is None
    assert session.query(sync.Agency).count() == 2


def test_ambiguous_rows_fail_instead_of_arbitrary_overwrite(session):
    add_agency(session)
    add_agency(session)
    with pytest.raises(MultipleResultsFound):
        sync.upsert_agency(session, record(), sync.load_category_map(session), False)


def test_only_unset_can_fill_bid_url_without_overwriting_base(session):
    agency = add_agency(session)
    agency.base_url = "https://www.soumu.go.jp/existing/"
    incoming = record()
    incoming.bid_url_pattern = "https://www.soumu.go.jp/procurement/"
    sync.upsert_agency(session, incoming, sync.load_category_map(session), True)
    assert agency.base_url.endswith("/existing/")
    assert agency.bid_url_pattern == incoming.bid_url_pattern


def test_url_registry_separates_categories_with_empty_code(session):
    categories = sync.load_category_map(session)
    sync.upsert_url_registry(session, record(), categories)
    assert sync.upsert_url_registry(session, record(), categories) == "unchanged"
    sync.upsert_url_registry(session, record(category="quasi"), categories)
    assert session.query(sync.UrlRegistry).count() == 2


def test_batch_failure_rolls_back_all_new_records(session, monkeypatch):
    from contextlib import contextmanager

    @contextmanager
    def get_session():
        yield session

    records = [record("成功1"), record("失敗"), record("成功2")]
    original = sync.upsert_url_registry

    def failing_registry(session, rec, categories):
        if rec.name == "失敗":
            raise ValueError("forced registry failure")
        return original(session, rec, categories)

    monkeypatch.setattr(sync, "get_session", get_session)
    monkeypatch.setattr(sync, "collect_records", lambda *args: records)
    monkeypatch.setattr(sync, "upsert_url_registry", failing_registry)
    monkeypatch.setattr("sys.argv", ["sync_registry_to_db.py"])
    with pytest.raises(ValueError, match="forced registry failure"):
        sync.main()
    assert session.query(sync.Agency).count() == 0
    assert session.query(sync.UrlRegistry).count() == 0


def test_sync_preprocess_latest_alias_hierarchy_and_idempotence(session):
    from copy import deepcopy

    parent = record("旧親", code="001")
    child = record("　子局　", code="002")
    child.parent_id = "name:旧親"
    child.extra = {"updated_at": "2026-09-17T10:00:00Z"}
    older = deepcopy(child)
    older.extra["updated_at"] = "2026-09-16T10:00:00Z"
    older.base_url = "https://example.invalid/older"
    rows = [child, older, parent]
    before = deepcopy(rows)
    aliases = {"旧親": "新親"}
    assert len(sync.sync_records(session, rows, aliases=aliases)) == 2
    session.commit()
    assert rows == before
    for model in (sync.Agency, sync.UrlRegistry):
        saved = session.query(model).filter_by(municipality_code="002").one()
        assert saved.base_url == child.base_url
        assert saved.parent.municipality_code == "001"
    sync.sync_records(session, rows, aliases=aliases)
    session.commit()
    assert session.query(sync.Agency).count() == session.query(sync.UrlRegistry).count() == 2


def test_sync_preprocess_coded_same_name_towns_remain_distinct(session):
    rows = [record("中央町", code="001"), record("中央町", code="002")]
    rows[0].region, rows[1].region = "北", "南"
    sync.sync_records(session, rows)
    session.commit()
    assert session.query(sync.Agency).count() == session.query(sync.UrlRegistry).count() == 2
    assert {row.region for row in session.query(sync.Agency)} == {"北", "南"}


@pytest.mark.parametrize("batch", [True, False])
def test_sync_codeless_region_collision_rejected(session, batch):
    north, south = record("中央町"), record("中央町")
    north.region, south.region = "北", "南"
    if not batch:
        sync.sync_records(session, [north])
        session.commit()
    with pytest.raises(ValueError, match="regions"):
        sync.sync_records(session, [north, south] if batch else [south])
    session.commit()
    assert session.query(sync.Agency).count() == (0 if batch else 1)
    if not batch:
        assert session.query(sync.Agency).one().region == "北"


def test_sync_rejects_conflicting_code_before_touching_session():
    from unittest.mock import Mock

    session = Mock()
    with pytest.raises(ValueError, match="Conflicting records for code"):
        sync.sync_records(session, [record("A", code="001"), record("B", code="001")])
    assert session.mock_calls == []
