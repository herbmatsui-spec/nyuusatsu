from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
import yaml
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.orm import Session

from crawler.registry import PROJECT_ROOT, RegistryRecord
from crawler.utils.registry_scraper import RegistryScraper, ScrapedAgency
from scripts import sync_registry_to_db as sync


@pytest.fixture
def session(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'hierarchy.db'}")

    @sa.event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    for model in (sync.AgencyCategory, sync.Agency, sync.UrlRegistry):
        model.__table__.create(engine)
    with Session(engine) as session:
        session.add_all([
            sync.AgencyCategory(id=1, name="国", priority=1),
            sync.AgencyCategory(id=2, name="外郭団体", priority=2),
            sync.AgencyCategory(id=3, name="都道府県", priority=3),
            sync.AgencyCategory(id=4, name="市区町村", priority=4),
        ])
        session.commit()
        yield session
    engine.dispose()


def record(name, code="", parent="", category="ministry"):
    return RegistryRecord(code, name, "https://example.invalid/", category=category,
                          parent_id=parent)


def snapshot(session):
    return {
        model.__tablename__: [tuple(row) for row in session.execute(sa.select(model.__table__).order_by(model.id))]
        for model in (sync.Agency, sync.UrlRegistry)
    }


def test_reverse_order_three_levels_and_repeated_sync(session):
    root = record("県", "001", category="prefecture")
    city = record("市", "001001", root.identity, "city")
    ward = record("区役所", "001001-ward", city.identity, "city")
    sync.sync_records(session, [ward, city, root])
    session.commit()
    for model in (sync.Agency, sync.UrlRegistry):
        rows = {row.municipality_code: row for row in session.query(model)}
        assert rows[ward.municipality_code].parent is rows[city.municipality_code]
        assert rows[city.municipality_code].parent is rows[root.municipality_code]
        assert rows[root.municipality_code].parent_id is None
        assert rows[root.municipality_code].children == [rows[city.municipality_code]]
        assert isinstance(rows[ward.municipality_code].parent_id, int)
    ids = {model: [row.id for row in session.query(model)] for model in (sync.Agency, sync.UrlRegistry)}
    sync.sync_records(session, [root, city, ward])
    session.commit()
    assert ids == {model: [row.id for row in session.query(model)] for model in ids}


@pytest.mark.parametrize("reference", ["name:親省", "親省"])
def test_codeless_parent_from_previous_sync(session, reference):
    sync.sync_records(session, [record("親省")])
    session.commit()
    sync.sync_records(session, [record("地方局", parent=reference)])
    session.commit()
    for model in (sync.Agency, sync.UrlRegistry):
        assert session.query(model).order_by(model.id.desc()).first().parent_id is not None


@pytest.mark.parametrize("reference", ["code:0001", "0001", "name:親省"])
def test_coded_parent_references(session, reference):
    sync.sync_records(session, [record("地方局", parent=reference), record("親省", "0001")])
    session.commit()
    assert session.query(sync.Agency).filter_by(name="地方局").one().parent.name == "親省"


@pytest.mark.parametrize("reference", ["missing", "code:missing", "name:missing", "1"])
def test_missing_parent_rolls_back_entire_batch_and_preserves_data(session, reference):
    sync.sync_records(session, [record("既存")])
    session.commit()
    before = snapshot(session)
    changed = record("既存")
    changed.base_url = "https://example.invalid/changed"
    with pytest.raises(ValueError, match="Missing parent"):
        sync.sync_records(session, [changed, record("新規"), record("子", parent=reference)])
    session.commit()
    assert snapshot(session) == before


@pytest.mark.parametrize("parents,reference", [
    ([record("親", "a"), record("親", "b")], "name:親"),
    ([record("親"), record("親", category="quasi")], "name:親"),
    ([record("別名", "親"), record("親")], "親"),
])
def test_ambiguous_parent_rejected(session, parents, reference):
    with pytest.raises(ValueError, match="Ambiguous parent"):
        sync.sync_records(session, [record("子", parent=reference), *parents])
    session.commit()
    assert session.query(sync.Agency).count() == 0
    assert session.query(sync.UrlRegistry).count() == 0


@pytest.mark.parametrize("records", [
    [record("自分", parent="name:自分")],
    [record("A", parent="name:B"), record("B", parent="name:A")],
    [record("A", parent="name:B"), record("B", parent="name:C"), record("C", parent="name:A")],
])
def test_cycles_rejected(session, records):
    with pytest.raises(ValueError, match="Cyclic parent"):
        sync.sync_records(session, records)
    session.commit()
    assert session.query(sync.Agency).count() == 0
    assert session.query(sync.UrlRegistry).count() == 0


def test_cycle_through_existing_parent_rejected(session):
    sync.sync_records(session, [record("A"), record("B", parent="name:A")])
    session.commit()
    before = snapshot(session)
    with pytest.raises(ValueError, match="Cyclic parent"):
        sync.sync_records(session, [record("A", parent="name:B")])
    session.commit()
    assert snapshot(session) == before


def test_conflicting_duplicate_parents_rejected(session):
    with pytest.raises(ValueError, match="Conflicting parents"):
        sync.sync_records(session, [record("A"), record("B"),
                                    record("子", parent="name:A"), record("子", parent="name:B")])
    session.commit()
    assert session.query(sync.Agency).count() == 0


def test_ambiguous_url_parent_rejected_independently(session):
    sync.sync_records(session, [record("親")])
    session.add(sync.UrlRegistry(municipality_code="", agency_name="親", base_url="",
                                category_id=2, parser_type="generic", max_depth=2))
    session.commit()
    before = snapshot(session)
    with pytest.raises(ValueError, match="Ambiguous parent.*url_registry"):
        sync.sync_records(session, [record("子", parent="name:親")])
    session.commit()
    assert snapshot(session) == before


def test_flat_records_preserve_existing_ids_fields_and_hierarchy(session):
    sync.sync_records(session, [record("親"), record("子", parent="name:親"), record("平坦")])
    session.commit()
    agency = session.query(sync.Agency).filter_by(name="子").one()
    registry = session.query(sync.UrlRegistry).filter_by(agency_name="子").one()
    agency.priority_level = 9
    registry.last_crawled_at = "2026-09-01"
    registry.max_depth = 7
    session.commit()
    parent_ids = (agency.parent_id, registry.parent_id)
    ids = (agency.id, registry.id)
    incoming = record("子")
    incoming.base_url = ""
    sync.sync_records(session, [incoming, record("平坦")], only_unset=True)
    session.commit()
    assert (agency.parent_id, registry.parent_id) == parent_ids
    assert (agency.id, registry.id) == ids
    assert agency.priority_level == 9
    assert agency.base_url == registry.base_url == "https://example.invalid/"
    assert registry.last_crawled_at == "2026-09-01"
    assert registry.max_depth == 7
    assert session.query(sync.Agency).filter_by(name="平坦").one().parent_id is None


@pytest.mark.parametrize("registry_type", list(sync.REGISTRY_FACTORIES))
def test_scraper_csv_registry_parent_roundtrip(tmp_path, registry_type):
    scraper = RegistryScraper()
    parent = ScrapedAgency("0001", "親")
    child = ScrapedAgency("0001-1", "子", parent_id=parent.identity)
    path = tmp_path / f"{registry_type}.csv"
    scraper.to_csv([child, parent], str(path))
    loaded = sync.collect_records(registry_type, str(path))
    assert [row.identity for row in loaded] == [child.identity, parent.identity]
    assert [row.parent_id for row in loaded] == [parent.identity, ""]
    path.write_text("municipality_code,name,agency_name,base_url\n0002,平坦,平坦,\n", encoding="utf-8")
    assert sync.collect_records(registry_type, str(path))[0].parent_id == ""


def test_coded_rename_keeps_both_table_identities(session):
    sync.sync_records(session, [record("旧名", "001")])
    session.commit()
    ids = [session.query(model).one().id for model in (sync.Agency, sync.UrlRegistry)]
    sync.sync_records(session, [record("新名", "001"), record("子", parent="name:新名")])
    session.commit()
    agency = session.query(sync.Agency).filter_by(municipality_code="001").one()
    registry = session.query(sync.UrlRegistry).filter_by(municipality_code="001").one()
    assert [agency.id, registry.id] == ids
    assert agency.name == registry.agency_name == "新名"


def test_yaml_roundtrip_and_project_root(tmp_path):
    assert PROJECT_ROOT == Path(__file__).resolve().parents[2]
    scraped = [ScrapedAgency("", "親", category="ministry"),
               ScrapedAgency("", "子", category="ministry", parent_id="name:親")]
    path = tmp_path / "registry.yaml"
    RegistryScraper().to_yaml(scraped, str(path))
    loaded = [RegistryRecord(**row) for row in yaml.safe_load(path.read_text(encoding="utf-8"))]
    assert loaded[0].identity == loaded[1].parent_id == "name:親"
    assert loaded[0].parent_id == ""
    assert asdict(loaded[1])["parent_id"] == "name:親"


def test_municipality_scraper_preserves_parent(tmp_path):
    path = tmp_path / "municipalities.csv"
    path.write_text("municipality_code,name,parent_id\n0001,市,code:00\n0002,町,\n", encoding="utf-8")
    loaded = RegistryScraper()._load_municipality_codes_from_csv(str(path))
    assert [row.parent_id for row in loaded] == ["code:00", ""]


def test_org_chart_to_export_to_reverse_sync(tmp_path, monkeypatch, session):
    scraper = RegistryScraper()
    monkeypatch.setattr(scraper, "_fetch", lambda _: (
        "<h1>親省</h1><h2>第一局</h2><h3>支局</h3>"
        '<ul><li><a href="/office">出張所</a></li></ul>'
        "<h2>第二局</h2>"
    ))
    records = scraper.deduplicate_and_normalize(
        scraper.scrape_ministry_org_chart("親省", "https://example.invalid/org")
    )
    path = tmp_path / "org.csv"
    scraper.to_csv(records, str(path))
    loaded = sync.collect_records("ministry", str(path))
    sync.sync_records(session, list(reversed(loaded)))
    session.commit()
    rows = {row.name: row for row in session.query(sync.Agency)}
    assert rows["親省"].parent_id is None
    assert rows["第一局"].parent is rows["親省"]
    assert rows["第二局"].parent is rows["親省"]
    assert rows["支局"].parent is rows["第一局"]
    assert rows["出張所"].parent is rows["支局"]


def test_normalization_keeps_parent_reference_resolvable():
    scraper = RegistryScraper()
    records = [ScrapedAgency("", " 親省 "), ScrapedAgency("", "子", parent_id="name:親省")]
    normalized = scraper.deduplicate_and_normalize(records)
    assert normalized[0].identity == normalized[1].parent_id


def test_migration_upgrade_downgrade_preserves_sqlite_data(tmp_path, monkeypatch):
    path = tmp_path / "migration.db"
    url = f"sqlite:///{path}"
    monkeypatch.setenv("DATABASE_URL", url)
    engine = sa.create_engine(url)
    metadata = sa.MetaData()
    for model in (sync.AgencyCategory, sync.Agency, sync.UrlRegistry):
        table = model.__table__.to_metadata(metadata)
        if "parent_id" in table.c:
            column = table.c.parent_id
            for constraint in list(table.constraints):
                if isinstance(constraint, sa.ForeignKeyConstraint) and column.name in constraint.columns:
                    table.constraints.remove(constraint)
            table.indexes = {index for index in table.indexes if column not in list(index.columns)}
            table._columns.remove(column)
    metadata.create_all(engine)
    now = datetime(2026, 9, 17)
    with engine.begin() as connection:
        connection.execute(metadata.tables["agency_categories"].insert(), {"id": 1, "name": "国", "priority": 1})
        connection.execute(metadata.tables["agencies"].insert(), [
            {"id": 41, "name": "親", "created_at": now, "updated_at": now, "category_id": 1},
            {"id": 42, "name": "子", "created_at": now, "updated_at": now, "category_id": 1},
        ])
        connection.execute(metadata.tables["url_registry"].insert(), [
            {"id": 81, "municipality_code": "", "agency_name": "親", "base_url": "parent", "parser_type": "generic", "max_depth": 2},
            {"id": 82, "municipality_code": "", "agency_name": "子", "base_url": "child", "parser_type": "generic", "max_depth": 3},
        ])
        before = {name: connection.execute(table.select()).all() for name, table in metadata.tables.items()}
    config = Config()
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    scripts = ScriptDirectory.from_config(config)
    revision = scripts.get_revision("add_parent_id_hierarchical")
    assert revision.down_revision == "competitive_analysis_v1"
    assert scripts.get_revision(revision.down_revision) is not None
    command.stamp(config, revision.down_revision)
    command.upgrade(config, revision.revision)
    with engine.begin() as connection:
        for table, parent, child in (("agencies", 41, 42), ("url_registry", 81, 82)):
            inspector = sa.inspect(connection)
            column = next(c for c in inspector.get_columns(table) if c["name"] == "parent_id")
            assert isinstance(column["type"], sa.Integer)
            assert column["nullable"]
            assert any(fk["referred_table"] == table and fk["constrained_columns"] == ["parent_id"]
                       for fk in inspector.get_foreign_keys(table))
            assert f"ix_{table}_parent_id" in {index["name"] for index in inspector.get_indexes(table)}
            assert connection.execute(sa.text(f"SELECT parent_id FROM {table}")).all() == [(None,), (None,)]
            connection.execute(sa.text(f"UPDATE {table} SET parent_id=:parent WHERE id=:child"),
                               {"parent": parent, "child": child})
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        for table in ("agencies", "url_registry"):
            with pytest.raises(sa.exc.IntegrityError):
                connection.execute(sa.text(f"UPDATE {table} SET parent_id=999"))
            connection.rollback()
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
    command.downgrade(config, revision.down_revision)
    with engine.connect() as connection:
        for name, table in metadata.tables.items():
            assert connection.execute(table.select()).all() == before[name]
        for table in ("agencies", "url_registry"):
            inspector = sa.inspect(connection)
            assert "parent_id" not in {column["name"] for column in inspector.get_columns(table)}
            assert f"ix_{table}_parent_id" not in {index["name"] for index in inspector.get_indexes(table)}
            assert not any(fk["constrained_columns"] == ["parent_id"] for fk in inspector.get_foreign_keys(table))
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    engine.dispose()
