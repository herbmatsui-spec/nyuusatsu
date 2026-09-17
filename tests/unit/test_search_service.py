from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.models import Bid
from services import search_service


@pytest.fixture
def search_db(monkeypatch):
    engine = create_engine(
        "sqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Bid.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    now = datetime(2026, 9, 17)
    with factory() as session:
        for bid_id, title, notes, pref, org in [
            (1, "道路 舗装 工事", None, "13", "東京都建設局"),
            (2, "道路 点検", "調査", "27", "大阪府"),
            (3, "庁舎 清掃", None, "13", "東京都財務局"),
            (4, "100%_調査", "工事", None, None),
        ]:
            session.add(Bid(
                id=bid_id, filename=title, notes=notes, prefecture_code=pref,
                organization_name=org, analyzed_at=now, created_at=now,
                updated_at=now, current_status="新規", announcement_date=now,
            ))
        session.commit()
    monkeypatch.setattr(search_service, "get_session", factory)
    yield factory
    engine.dispose()


@pytest.mark.parametrize("conditions,expected", [
    ({"keyword": "道路 工事"}, [1]),
    ({"keyword": "道路 清掃", "use_or": True}, [1, 2, 3]),
    ({"keyword": "道路", "use_not": True}, [3, 4]),
    ({"prefecture": ["13"]}, [1, 3]),
    ({"organization": "建設"}, [1]),
    ({"keyword": "道路", "prefecture": ["13"], "organization": "建設"}, [1]),
])
def test_search_conditions(search_db, conditions, expected):
    result = search_service.search_bids(**conditions)
    assert [row["id"] for row in result["results"]] == expected
    assert result["total"] == len(expected)


@pytest.mark.parametrize("conditions,expected", [
    ({"keyword": " \t　"}, [1, 2, 3, 4]),
    ({"keyword": "%_"}, [4]),
    ({"keyword": "工事"}, [1, 4]),
    ({"keyword": "不存在"}, []),
    ({"keyword": "道路 清掃", "use_not": True, "use_or": True}, [4]),
    ({"prefecture": ["13", "27"]}, [1, 2, 3]),
    ({"prefecture": []}, [1, 2, 3, 4]),
])
def test_search_edge_cases(search_db, conditions, expected):
    assert [r["id"] for r in search_service.search_bids(**conditions)["results"]] == expected


def test_bid_type_exact_match(search_db):
    with search_db() as session:
        session.get(Bid, 1).bid_type = "一般競争入札"
        session.get(Bid, 2).bid_type = "一般競争入札（条件付）"
        session.commit()
    result = search_service.search_bids(bid_type="一般競争入札")
    assert [r["id"] for r in result["results"]] == [1]
    assert result["total"] == 1
    assert search_service.search_bids(bid_type="随意契約")["total"] == 0
    assert search_service.search_bids()["total"] == 4


def test_options_and_pagination(search_db):
    assert search_service.get_prefectures() == ["13", "27"]
    first = search_service.search_bids(limit=2)
    second = search_service.search_bids(offset=2, limit=2)
    assert first["total"] == second["total"] == 4
    assert [r["id"] for r in first["results"]] == [1, 2]
    assert [r["id"] for r in second["results"]] == [3, 4]
    assert search_service.search_bids(offset=4)["results"] == []
    assert set(first["results"][0]) == {
        "id", "title", "organization", "announcement_date",
        "budget_amount", "qualification_requirements", "delivery_deadline", "deliverables",
    }


@pytest.mark.parametrize("arguments", [{"offset": -1}, {"limit": 0}, {"limit": -1}])
def test_invalid_pagination(arguments):
    with pytest.raises(ValueError):
        search_service.search_bids(**arguments)


def test_bid_type_migration_preserves_records():
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect, text
    from migrations.versions import unified_search_bid_type as migration

    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE bids (id INTEGER PRIMARY KEY, filename TEXT)"))
        connection.execute(text("INSERT INTO bids VALUES (1, 'existing')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            assert "bid_type" in {c["name"] for c in inspect(connection).get_columns("bids")}
            assert connection.execute(text("SELECT bid_type FROM bids")).scalar() is None
            migration.downgrade()
            assert "bid_type" not in {c["name"] for c in inspect(connection).get_columns("bids")}
            assert connection.execute(text("SELECT filename FROM bids")).scalar() == "existing"
    engine.dispose()


@pytest.fixture
def extracted_db(search_db):
    with search_db() as session:
        rows = [
            (1, 1_500_000, "全省庁統一資格 A等級 建設業許可", date(2026, 3, 31), "舗装工事一式"),
            (2, 5_000_000, "ISO 9001 認証", date(2026, 6, 30), "システム開発"),
            (3, 20_000_000, None, None, "調査報告書作成"),
            (4, None, "電気工事業 届出", None, None),
        ]
        for bid_id, amount, quals, deadline, deliv in rows:
            bid = session.get(Bid, bid_id)
            bid.budget_amount = amount
            bid.qualifications = quals
            bid.delivery_deadline = deadline
            bid.deliverables = deliv
        session.commit()
    yield search_db


@pytest.mark.parametrize("conditions,expected", [
    ({"budget_min": 1_000_000}, [1, 2, 3]),
    ({"budget_max": 5_000_000}, [1, 2]),
    ({"budget_min": 1_000_000, "budget_max": 5_000_000}, [1, 2]),
    ({"budget_min": 1_500_000, "budget_max": 1_500_000}, [1]),
    ({"qualification_keywords": "ISO"}, [2]),
    ({"qualification_keywords": "統一資格 A等級"}, [1]),
    ({"qualification_keywords": "ISO 電気"}, []),
    ({"deadline_from": date(2026, 4, 1)}, [2]),
    ({"deadline_to": date(2026, 3, 31)}, [1]),
    ({"deadline_from": date(2026, 1, 1), "deadline_to": date(2026, 12, 31)}, [1, 2]),
    ({"deliverables_keyword": "報告書"}, [3]),
    ({"deliverables_keyword": "開発"}, [2]),
])
def test_extracted_field_filters(extracted_db, conditions, expected):
    result = search_service.search_bids(**conditions)
    assert [r["id"] for r in result["results"]] == expected
    assert result["total"] == len(expected)


def test_extracted_fields_combined_with_existing_conditions(extracted_db):
    result = search_service.search_bids(
        keyword="点検", prefecture=["27"], budget_min=1_000_000,
    )
    assert [r["id"] for r in result["results"]] == [2]
    result = search_service.search_bids(
        organization="建設局", qualification_keywords="建設業許可",
    )
    assert [r["id"] for r in result["results"]] == [1]


def test_null_fields_excluded_from_range_filters(extracted_db):
    assert search_service.search_bids(budget_min=0)["total"] == 3
    assert search_service.search_bids(deadline_from=date(2000, 1, 1))["total"] == 2


@pytest.mark.parametrize("conditions,expected", [
    ({"sort_column": "budget_amount", "sort_direction": "asc"}, [1, 2, 3, 4]),
    ({"sort_column": "budget_amount", "sort_direction": "desc"}, [3, 2, 1, 4]),
    ({"sort_column": "delivery_deadline", "sort_direction": "asc"}, [1, 2, 3, 4]),
    ({"sort_column": "delivery_deadline", "sort_direction": "desc"}, [2, 1, 4, 3]),
    ({"sort_column": "announcement_date", "sort_direction": "desc"}, [4, 3, 2, 1]),
    ({"sort_column": "unknown_column"}, [1, 2, 3, 4]),
    ({"sort_direction": "desc"}, [4, 3, 2, 1]),
])
def test_sort_by_extracted_fields(extracted_db, conditions, expected):
    result = search_service.search_bids(**conditions)
    assert [r["id"] for r in result["results"]] == expected


def test_extracted_field_escaping(extracted_db):
    result = search_service.search_bids(qualification_keywords="%")
    assert result["results"] == []
    result = search_service.search_bids(qualification_keywords="_")
    assert result["results"] == []
