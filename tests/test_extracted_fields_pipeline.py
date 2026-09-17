from datetime import date, datetime, timezone
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Bid, BidStatus, Customer, Partner, CustomerBidLink, PartnerBidLink
from services.bid_analysis_service import BidAnalysisService
from services.bid_storage_service import BidStorageService
from services.extracted_fields_normalizer import normalize_budget, normalize_delivery_deadline, normalize_extracted_fields
from scripts.backfill_extracted_fields import backfill_extracted_fields


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    yield


@pytest.fixture
def sessions(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'pipeline.db'}")
    for model in (Bid, BidStatus, Customer, Partner, CustomerBidLink, PartnerBidLink):
        model.__table__.create(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


def test_analysis_persists_representative_payload(sessions, monkeypatch):
    now = datetime.now(timezone.utc)
    with sessions() as session:
        session.add(Customer(name="customer", memo="ISO", created_at=now, updated_at=now))
        session.add(Partner(name="partner", category="報告書", created_at=now, updated_at=now))
        session.commit()
        llm = Mock()
        llm.analyze_with_fallback.return_value = {
            "budget": "1,500万円（税抜）",
            "qualifications": ["ISO 9001", "全省庁統一資格"],
            "deadline": "履行期間：2026年4月1日から2027年3月31日まで",
            "deliverables": ["報告書", "データ"],
            "key_risks": ["短納期"],
            "organization_name": "テスト機関",
            "industry_category": "調査",
        }
        service = BidAnalysisService(session, llm_service=llm)
        monkeypatch.setattr(service, "extract_text_from_pdf", lambda path: "仕様書テキスト")
        bid = service.analyze_and_save("test.pdf", "https://example.invalid/bid")
        bid_id = bid.id
    with sessions() as session:
        bid = session.get(Bid, bid_id)
        assert bid.budget_amount == 15_000_000
        assert bid.delivery_deadline == date(2027, 3, 31)
        assert bid.qualifications == "ISO 9001\n全省庁統一資格"
        assert bid.deliverables == "報告書\nデータ"
        assert bid.specification_text == "仕様書テキスト"
        assert bid.current_status == "未確認"
        assert session.query(BidStatus).count() == 1
        assert session.query(CustomerBidLink).count() == 1
        assert session.query(PartnerBidLink).count() == 1


@pytest.mark.parametrize("value, expected", [
    (None, None), ("記載なし", None), (True, None), ({"amount": 100}, None),
    (1000000, 1000000), ("１，５００万円", 15000000), ("2億円", 200000000),
    ("1.5千円", 1500), ("100円（税抜）", 100), ("税抜 100円", 100),
    ("110万円（税込）", None), ("税込:110万円", None),
    ("110万円（税込）、100万円（税抜）", 1000000),
    ("税込:110万円、税抜:100万円", 1000000),
    ("税込:220万円、税抜:100万円～200万円", None),
    ("税込:220万円、1億200万円（税抜）", None),
    ("1億2千万円", None), ("100万円～200万円", None),
    ("-100円", None), ("0.1円", None), (float("nan"), None),
    ("9223372036854775808円", None), ("令和8年度 100万円", None),
])
def test_budget_normalization(value, expected):
    assert normalize_budget(value) == expected


@pytest.mark.parametrize("value, expected", [
    (None, None), ("不明", None), ({"end": "2027-03-31"}, None),
    ("2027-03-31", date(2027, 3, 31)), ("２０２７／３／３１", date(2027, 3, 31)),
    ("令和9年3月31日", date(2027, 3, 31)), ("H31.4.1", date(2019, 4, 1)),
    ("令和元年5月1日", date(2019, 5, 1)), ("令和元年4月1日", None),
    ("納期：2027年3月31日（水）まで", date(2027, 3, 31)),
    ("2026-04-01 ～ 2027-03-31", date(2027, 3, 31)),
    ("契約締結日から令和9年3月31日まで", date(2027, 3, 31)),
    ("2026-04-01 - 2027-03-31", date(2027, 3, 31)),
    ("2027-04-01から2027-03-31まで", None),
    ("2026年4月1日から3月31日まで", None),
    ("3月31日", None), ("契約から90日", None), ("2027年3月末", None),
    ("2027-02-30", None), ("2026-04-01から未定", None),
    ("2026-04-01 または 2027-03-31", None),
    ("入札期限：2027年3月31日", None),
    ("開始日：2026-04-01、終了日：未定", None),
    (date(2027, 3, 31), date(2027, 3, 31)),
])
def test_delivery_normalization(value, expected):
    assert normalize_delivery_deadline(value) == expected


@pytest.mark.parametrize("payload", [None, [], "bad", {}, {"success": False, "budget": "100万円"},
                                         {"error": "failed"}, {"status": "failed"},
                                         {"budget": None, "qualifications": [], "deliverables": "None", "deadline": "未定"}])
def test_missing_failed_extraction(payload, caplog):
    assert all(value is None for value in normalize_extracted_fields(payload).values())


@pytest.mark.parametrize("value, expected", [
    ([" ISO 9001 ", None, "記載なし", "全省庁資格", "ISO 9001"], "ISO 9001\n全省庁資格"),
    ('["ISO 9001", "報告書"]', "ISO 9001\n報告書"),
    ("['ISO 9001', '報告書']", "ISO 9001\n報告書"),
    ({"name": "資格"}, None), ([{"name": "資格"}], None), (12, None),
    (" null ", None), ("[broken", None),
])
def test_text_normalization(value, expected):
    fields = normalize_extracted_fields({"qualifications": value, "deliverables": value})
    assert fields["qualifications"] == expected
    assert fields["deliverables"] == expected


def make_service(session, monkeypatch, payload):
    llm = Mock()
    llm.analyze_with_fallback.return_value = payload
    service = BidAnalysisService(session, llm_service=llm)
    monkeypatch.setattr(service, "extract_text_from_pdf", lambda path: "仕様書")
    return service


def test_repeat_update_preserves_status_and_replaces_links(sessions, monkeypatch):
    with sessions() as session:
        now = datetime.now(timezone.utc)
        session.add(Customer(name="customer", memo="ISO", created_at=now, updated_at=now))
        session.commit()
        service = make_service(session, monkeypatch, {"budget": "100万円", "qualifications": ["ISO 9001"]})
        bid = service.analyze_and_save("first.pdf", "https://example.invalid/repeat")
        bid_id = bid.id
        created = bid.created_at
        bid.current_status = "確認済"
        bid.notes = "keep"
        session.commit()
        service.llm_service.analyze_with_fallback.return_value = {"budget": "200万円", "qualifications": ["ISO 9001"]}
        updated = service.analyze_and_save("second.pdf", "https://example.invalid/repeat")
        assert updated.id == bid_id
        assert updated.created_at == created
    with sessions() as session:
        bid = session.get(Bid, bid_id)
        assert bid.budget_amount == 2000000
        assert bid.current_status == "確認済"
        assert bid.notes == "keep"
        assert session.query(Bid).count() == 1
        assert session.query(BidStatus).count() == 1
        assert session.query(CustomerBidLink).count() == 1


@pytest.mark.parametrize("failure", [None, [], {"success": False, "budget": "100万円"}, RuntimeError("LLM failed")])
def test_analysis_failure_clears_previous_fields(sessions, monkeypatch, failure, caplog):
    with sessions() as session:
        service = make_service(session, monkeypatch, {"budget": "100万円", "deadline": "2027-03-31", "qualifications": "ISO", "deliverables": "報告書"})
        bid_id = service.analyze_and_save("test.pdf", "url").id
        if isinstance(failure, Exception):
            service.llm_service.analyze_with_fallback.side_effect = failure
        else:
            service.llm_service.analyze_with_fallback.return_value = failure
        service.analyze_and_save("test.pdf", "url")
    with sessions() as session:
        bid = session.get(Bid, bid_id)
        for key in ("budget_amount", "qualifications", "deliverables", "delivery_deadline"):
            assert getattr(bid, key) is None
        assert session.query(BidStatus).count() == 1
    assert "NULL" in caplog.text


@pytest.mark.parametrize("existing", [True, False])
@pytest.mark.parametrize("failure_stage", ["matching", "flush", "commit"])
def test_analysis_rolls_back_entire_transaction(sessions, monkeypatch, existing, failure_stage):
    from sqlalchemy import event
    from sqlalchemy.exc import IntegrityError

    with sessions() as session:
        now = datetime.now(timezone.utc)
        session.add(Customer(name="customer", memo="ISO", created_at=now, updated_at=now))
        session.commit()
        service = make_service(session, monkeypatch, {"budget": "100万円", "qualifications": "ISO"})
        if existing:
            service.analyze_and_save("test.pdf", "url")
        service.llm_service.analyze_with_fallback.return_value = {"budget": "200万円", "qualifications": "other"}
        if failure_stage == "matching":
            original = service.match_customers_and_partners

            def fail(bid):
                original(bid)
                session.flush()
                raise RuntimeError("matching failed")

            monkeypatch.setattr(service, "match_customers_and_partners", fail)
        elif failure_stage == "flush":
            def fail_flush(session, context, instances):
                raise IntegrityError("injected", {}, RuntimeError("flush failed"))

            event.listen(session, "before_flush", fail_flush, once=True)
        else:
            def fail_commit(session):
                raise RuntimeError("commit failed")

            event.listen(session, "before_commit", fail_commit, once=True)
        with pytest.raises((RuntimeError, IntegrityError)):
            service.analyze_and_save("test.pdf", "url")
        assert not session.in_transaction()
    with sessions() as session:
        assert session.query(Bid).count() == int(existing)
        assert session.query(BidStatus).count() == int(existing)
        assert session.query(CustomerBidLink).count() == int(existing)
        if existing:
            assert session.query(Bid).one().budget_amount == 1000000


def test_storage_normalizes_commits_and_clears_explicit_nulls(sessions):
    service = BidStorageService(sessions)
    bid = service.save_bid({"title": "test", "source_url": "url", "budget": "1,500万円", "qualifications": ["ISO"], "deliverables": ["報告書"], "deadline": "2027-03-31"})
    assert bid.budget_amount == 15000000
    bid_id = bid.id
    service.save_bid({"title": "updated", "source_url": "url"})
    with sessions() as session:
        assert session.get(Bid, bid_id).budget_amount == 15000000
    service.save_bid({"title": "updated", "source_url": "url", "budget": "110万円（税込）", "qualifications": None, "deliverables": {}, "deadline": "未定"})
    with sessions() as session:
        bid = session.get(Bid, bid_id)
        assert bid.budget_amount is None
        assert bid.qualifications is None
        assert bid.deliverables is None
        assert bid.delivery_deadline is None
        assert session.query(Bid).count() == 1


def test_storage_rollback(sessions):
    from sqlalchemy import event

    service = BidStorageService(sessions)
    bid_id = service.save_bid({"title": "test", "source_url": "url", "budget": "100万円"}).id
    session = sessions()

    def fail(session):
        raise RuntimeError("commit failed")

    event.listen(session, "before_commit", fail, once=True)
    service = BidStorageService(lambda: session)
    with pytest.raises(RuntimeError):
        service.save_bid({"title": "changed", "source_url": "url", "budget": "200万円"})
    with sessions() as session:
        assert session.get(Bid, bid_id).budget_amount == 1000000
        assert session.get(Bid, bid_id).filename == "test"


def test_backfill_bounded_idempotent_and_dry_run(sessions):
    from sqlalchemy import event

    with sessions() as session:
        now = datetime.now(timezone.utc)
        for index in range(5):
            session.add(Bid(filename=f"{index}.pdf", current_status="未確認", analyzed_at=now, created_at=now, updated_at=now,
                            budget="1,500万円", budget_amount=1, qualifications='["ISO", "資格"]', deliverables="['報告書']",
                            deadline="2026-04-01から2027-03-31まで"))
        session.commit()
    assert backfill_extracted_fields(sessions, batch_size=2) == {"scanned": 5, "changed": 5}
    with sessions() as session:
        assert session.query(Bid).first().budget_amount == 1
    commits = []
    event.listen(sessions, "after_commit", lambda session: commits.append(True))
    assert backfill_extracted_fields(sessions, batch_size=2, dry_run=False) == {"scanned": 5, "changed": 5}
    assert len(commits) == 3
    assert backfill_extracted_fields(sessions, batch_size=2, dry_run=False) == {"scanned": 5, "changed": 0}
    with sessions() as session:
        for bid in session.query(Bid).all():
            assert bid.budget_amount == 15000000
            assert bid.delivery_deadline == date(2027, 3, 31)
            assert bid.qualifications == "ISO\n資格"
            assert bid.deliverables == "報告書"
    with pytest.raises(ValueError):
        backfill_extracted_fields(sessions, batch_size=0)


def test_backfill_batch_rollback(sessions):
    from sqlalchemy import event

    with sessions() as session:
        now = datetime.now(timezone.utc)
        for index in range(2):
            session.add(Bid(filename=f"{index}.pdf", current_status="未確認", analyzed_at=now, created_at=now, updated_at=now, budget="100万円", budget_amount=1))
        session.commit()

    def fail(session):
        session.flush()
        raise RuntimeError("commit failed")

    event.listen(sessions, "before_commit", fail, once=True)
    with pytest.raises(RuntimeError):
        backfill_extracted_fields(sessions, batch_size=2, dry_run=False)
    with sessions() as session:
        assert [bid.budget_amount for bid in session.query(Bid).all()] == [1, 1]
