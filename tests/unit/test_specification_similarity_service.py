"""Tests for services/specification_similarity_service.py"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models.bid import Bid
from services.specification_similarity_service import SpecificationSimilarityService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def _make_bid(session, bid_id, spec, org="東京都渋谷区", budget=1000000, cat="IT", pref="13"):
    bid = Bid(
        id=bid_id,
        filename=f"bid_{bid_id}.pdf",
        current_status="入札済",
        analyzed_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        specification_text=spec,
        specification_text_clean=spec,
        organization_name=org,
        budget_amount=budget,
        industry_category=cat,
        prefecture_code=pref,
        announcement_date=datetime.utcnow() - timedelta(days=30),
    )
    session.add(bid)
    session.flush()
    return bid


SPEC_A = "東京都渋谷区にて行われるWebシステム開発・構築プロジェクト"
SPEC_B = "渋谷区のWebシステム開発・構築プロジェクトです"
SPEC_C = "大阪府のコンテンツ管理システム導入サービス"
SPEC_D = "北海道札幌市道路舗装工事施工請負"


def test_search_bids_by_keyword(db_session):
    svc = SpecificationSimilarityService(db_session)
    _make_bid(db_session, 1, SPEC_A)
    _make_bid(db_session, 2, SPEC_C)
    results = svc.search_bids(keyword="Web", limit=100)
    assert len(results) == 1
    assert results[0]["id"] == 1


def test_search_bids_by_organization(db_session):
    svc = SpecificationSimilarityService(db_session)
    _make_bid(db_session, 1, SPEC_A, org="東京都渋谷区")
    _make_bid(db_session, 2, SPEC_C, org="大阪府")
    results = svc.search_bids(organization="東京", limit=100)
    assert len(results) == 1
    assert results[0]["organization_name"] == "東京都渋谷区"


def test_search_bids_by_prefecture(db_session):
    svc = SpecificationSimilarityService(db_session)
    _make_bid(db_session, 1, SPEC_A, pref="13")
    _make_bid(db_session, 2, SPEC_C, pref="27")
    results = svc.search_bids(prefecture_code="13", limit=100)
    assert len(results) == 1
    assert results[0]["id"] == 1


def test_search_bids_by_industry(db_session):
    svc = SpecificationSimilarityService(db_session)
    _make_bid(db_session, 1, SPEC_A, cat="IT")
    _make_bid(db_session, 2, SPEC_C, cat="建設")
    results = svc.search_bids(industry_category="IT", limit=100)
    assert len(results) == 1


def test_search_bids_empty(db_session):
    svc = SpecificationSimilarityService(db_session)
    results = svc.search_bids(keyword="不存在", limit=100)
    assert results == []


def test_search_bids_limit(db_session):
    svc = SpecificationSimilarityService(db_session)
    for i in range(1, 6):
        _make_bid(db_session, i, SPEC_A)
    results = svc.search_bids(keyword="Web", limit=2)
    assert len(results) == 2


def test_get_all_prefectures(db_session):
    svc = SpecificationSimilarityService(db_session)
    _make_bid(db_session, 1, SPEC_A, pref="13")
    _make_bid(db_session, 2, SPEC_C, pref="27")
    prefectures = svc.get_all_prefectures()
    assert "13" in prefectures
    assert "27" in prefectures


def test_get_all_industries(db_session):
    svc = SpecificationSimilarityService(db_session)
    _make_bid(db_session, 1, SPEC_A, cat="IT")
    _make_bid(db_session, 2, SPEC_C, cat="建設")
    industries = svc.get_all_industries()
    assert "IT" in industries
    assert "建設" in industries


def test_get_bid_detail(db_session):
    svc = SpecificationSimilarityService(db_session)
    bid = _make_bid(db_session, 1, SPEC_A)
    detail = svc.get_bid_detail(1)
    assert detail is not None
    assert detail["id"] == 1
    assert detail["organization_name"] == "東京都渋谷区"
    assert detail["specification_text"] == SPEC_A


def test_get_bid_detail_not_found(db_session):
    svc = SpecificationSimilarityService(db_session)
    assert svc.get_bid_detail(999) is None


def test_find_similar_bids(db_session):
    svc = SpecificationSimilarityService(db_session)
    _make_bid(db_session, 1, SPEC_A)
    _make_bid(db_session, 2, SPEC_B)
    _make_bid(db_session, 3, SPEC_C)
    _make_bid(db_session, 4, SPEC_D)

    results = svc.find_similar_bids(1, n=10, threshold=0.0, use_cache=False)
    assert len(results) > 0
    # The most similar to SPEC_A should be SPEC_B (both Tokyo Web system)
    assert results[0]["bid_id"] == 2
    assert results[0]["similarity_score"] > 0


def test_find_similar_bids_not_found(db_session):
    svc = SpecificationSimilarityService(db_session)
    _make_bid(db_session, 1, SPEC_A)
    results = svc.find_similar_bids(999, n=10, threshold=0.0, use_cache=False)
    assert results == []


def test_bid_to_dict(db_session):
    svc = SpecificationSimilarityService(db_session)
    bid = _make_bid(db_session, 1, SPEC_A)
    result = svc._bid_to_dict(bid)
    assert result["id"] == 1
    assert result["title"] == "bid_1.pdf"  # deliverables is None, falls back to filename
    assert result["organization_name"] == "東京都渋谷区"
    assert result["budget_amount"] == 1000000
    assert result["industry_category"] == "IT"
    assert result["specification_text"] == SPEC_A


@pytest.mark.parametrize("use_cache", [True, False])
def test_similarity_forwards_all_filters_before_top_n(db_session, use_cache):
    svc = SpecificationSimilarityService(db_session)
    _make_bid(db_session, 1, SPEC_A)
    _make_bid(db_session, 2, SPEC_A, pref="27")
    _make_bid(db_session, 3, SPEC_A, cat="建設")
    old = _make_bid(db_session, 4, SPEC_A)
    old.announcement_date = datetime.utcnow() - timedelta(days=800)
    _make_bid(db_session, 5, SPEC_B)
    db_session.flush()
    results = svc.find_similar_bids(
        1, n=1, threshold=0, months=6, use_cache=use_cache,
        prefecture_code="13", industry_category="IT",
    )
    assert [item["bid_id"] for item in results] == [5]
    results = svc.find_similar_bids(
        1, n=1, threshold=0, months=0, use_cache=use_cache,
        prefecture_code="13", industry_category="IT",
    )
    assert [item["bid_id"] for item in results] == [4]
    assert svc.find_similar_bids(1, n=0, use_cache=use_cache) == []
    assert svc.find_similar_bids(1, threshold=1.1, use_cache=use_cache) == []


def test_empty_cached_results_do_not_trigger_uncached_fallback(db_session, monkeypatch):
    svc = SpecificationSimilarityService(db_session)
    _make_bid(db_session, 1, SPEC_A)
    _make_bid(db_session, 2, SPEC_B)
    text_service = svc._similarity_service()

    def fail(*args, **kwargs):
        raise AssertionError("Empty results are valid cached results")

    monkeypatch.setattr(text_service, "get_top_n_similar", fail)
    assert svc.find_similar_bids(1, threshold=1.1) == []
    assert svc.find_similar_bids(1, threshold=1.1) == []
