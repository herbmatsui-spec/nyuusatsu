"""Tests for services/text_similarity_service.py"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models.bid import Bid
from services.text_similarity_service import TextSimilarityService


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


def _make_bid(session, bid_id, spec_text, org="テスト機関", budget=1000000):
    bid = Bid(
        id=bid_id,
        filename=f"bid_{bid_id}.pdf",
        current_status="入札済",
        analyzed_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        specification_text=spec_text,
        specification_text_clean=spec_text,
        organization_name=org,
        budget_amount=budget,
        announcement_date=datetime.utcnow() - timedelta(days=30),
    )
    session.add(bid)
    session.flush()
    return bid


SPEC_A = "本プロジェクトは東京都渋谷区にて行われるWebシステムの開発・構築に関するものである。"
SPEC_B = "東京都渋谷区でのWebシステム開発・構築プロジェクトである。"
SPEC_C = "大阪府のコンテンツ管理システムの導入及び運用保守サービス。"
SPEC_D = "北海道札幌市における道路舗装工事の施工を請負うものである。"


def test_build_vectors(db_session):
    svc = TextSimilarityService(db_session)
    _make_bid(db_session, 1, SPEC_A)
    _make_bid(db_session, 2, SPEC_B)
    _make_bid(db_session, 3, SPEC_C)
    count = svc.build(months=0)
    assert count == 3
    assert svc._is_built
    assert len(svc.doc_ids) == 3


def test_build_vectors_empty(db_session):
    svc = TextSimilarityService(db_session)
    count = svc.build(months=0)
    assert count == 0
    assert not svc._is_built


def test_get_similarity_found(db_session):
    svc = TextSimilarityService(db_session)
    _make_bid(db_session, 1, SPEC_A)
    _make_bid(db_session, 2, SPEC_B)
    _make_bid(db_session, 3, SPEC_C)
    svc.build(months=0)

    score = svc.get_similarity(1, 2)
    assert 0.0 < score <= 1.0

    score_ac = svc.get_similarity(1, 3)
    assert score_ac < score


def test_get_similarity_missing_docs(db_session):
    svc = TextSimilarityService(db_session)
    _make_bid(db_session, 1, SPEC_A)
    svc.build(months=0)

    assert svc.get_similarity(1, 999) == 0.0
    assert svc.get_similarity(999, 1) == 0.0


def test_get_similarity_not_built(db_session):
    svc = TextSimilarityService(db_session)
    assert svc.get_similarity(1, 2) == 0.0


def test_get_top_n_similar(db_session):
    svc = TextSimilarityService(db_session)
    _make_bid(db_session, 1, SPEC_A)
    _make_bid(db_session, 2, SPEC_B)
    _make_bid(db_session, 3, SPEC_C)
    _make_bid(db_session, 4, SPEC_D)
    svc.build(months=0)

    results = svc.get_top_n_similar(1, n=2, threshold=0.0)
    assert len(results) <= 2
    assert results[0]["bid_id"] == 2
    assert results[0]["similarity_score"] > 0
    assert results[0]["organization_name"] == "テスト機関"


def test_get_top_n_similar_threshold(db_session):
    svc = TextSimilarityService(db_session)
    _make_bid(db_session, 1, SPEC_A)
    _make_bid(db_session, 2, SPEC_B)
    _make_bid(db_session, 3, SPEC_C)
    svc.build(months=0)

    results = svc.get_top_n_similar(1, n=10, threshold=0.99)
    assert all(r["similarity_score"] >= 0.99 for r in results)


def test_get_top_n_similar_not_in_index(db_session):
    svc = TextSimilarityService(db_session)
    _make_bid(db_session, 1, SPEC_A)
    svc.build(months=0)
    results = svc.get_top_n_similar(999, n=10)
    assert results == []


def test_get_cached_top_n(db_session):
    svc = TextSimilarityService(db_session)
    _make_bid(db_session, 1, SPEC_A)
    _make_bid(db_session, 2, SPEC_B)
    svc.build(months=0)

    result1 = svc.get_cached_top_n(1, n=5)
    result2 = svc.get_cached_top_n(1, n=5)
    assert result1 == result2
    assert len(svc._similarity_cache) == 1


def test_save_and_load_vectors(db_session, tmp_path):
    svc = TextSimilarityService(db_session, cache_dir=str(tmp_path))
    _make_bid(db_session, 1, SPEC_A)
    _make_bid(db_session, 2, SPEC_B)
    svc.build(months=0)

    filepath = str(tmp_path / "test_vectors.pkl")
    svc.save_vectors(filepath)

    svc2 = TextSimilarityService(db_session, cache_dir=str(tmp_path))
    loaded = svc2.load_vectors(filepath)
    assert loaded
    assert svc2._is_built
    assert len(svc2.doc_ids) == 2
    score = svc2.get_similarity(1, 2)
    assert 0.0 <= score <= 1.0


def test_load_vectors_file_not_found(db_session, tmp_path):
    svc = TextSimilarityService(db_session, cache_dir=str(tmp_path))
    result = svc.load_vectors(str(tmp_path / "nonexistent.pkl"))
    assert result is False


def test_compute_similarity_between_texts(db_session):
    svc = TextSimilarityService(db_session)
    _make_bid(db_session, 1, SPEC_A)
    svc.build(months=0)

    score = svc.compute_similarity_between_texts(SPEC_A, SPEC_B)
    assert 0.0 < score <= 1.0

    score_d = svc.compute_similarity_between_texts(SPEC_A, SPEC_D)
    assert score_d < score


def test_compute_similarity_not_built(db_session):
    svc = TextSimilarityService(db_session)
    assert svc.compute_similarity_between_texts("text1", "text2") == 0.0


def test_tfidf_params_uses_japanese_stopwords(db_session):
    svc = TextSimilarityService(db_session)
    params = svc.tfidf_params
    assert params["max_features"] == 5000
    assert tuple(params["ngram_range"]) == (2, 5)
    assert params.get("stop_words") is None  # char_wb doesn't use stop_words


def test_config_defaults(db_session):
    svc = TextSimilarityService(db_session)
    assert svc.config.get("default_n") == 10
    assert svc.config.get("default_threshold") == 0.3


def test_unlimited_and_mixed_cleaned_corpus(db_session):
    old = _make_bid(db_session, 1, SPEC_A)
    old.announcement_date = datetime.utcnow() - timedelta(days=800)
    raw = _make_bid(db_session, 2, SPEC_B)
    raw.specification_text_clean = None
    fallback = _make_bid(db_session, 3, None)
    fallback.deliverables = SPEC_C
    db_session.flush()
    svc = TextSimilarityService(db_session)
    assert svc.build(months=0) == 3
    assert svc.doc_ids == [1, 2, 3]
    assert svc.build(months=6) == 2
    assert svc.doc_ids == [2, 3]


def test_sparse_cosine_never_densifies_rows(db_session, monkeypatch):
    from scipy.sparse import csr_matrix

    _make_bid(db_session, 1, SPEC_A)
    _make_bid(db_session, 2, SPEC_B)
    svc = TextSimilarityService(db_session)
    svc.build(months=0)

    def fail(*args, **kwargs):
        raise AssertionError("Sparse search must not densify vectors")

    monkeypatch.setattr(csr_matrix, "toarray", fail)
    score = svc.get_similarity(1, 2)
    assert score > 0
    assert svc.get_top_n_similar(1, threshold=0)[0]["similarity_score"] == score
    assert svc.compute_similarity_between_texts(SPEC_A, SPEC_B) == score


def test_filters_are_applied_before_ranking(db_session, monkeypatch):
    _make_bid(db_session, 1, SPEC_A)
    excluded_region = _make_bid(db_session, 2, SPEC_A)
    excluded_region.prefecture_code = "27"
    excluded_region.industry_category = "IT"
    excluded_industry = _make_bid(db_session, 3, SPEC_A)
    excluded_industry.prefecture_code = "13"
    excluded_industry.industry_category = "建設"
    old = _make_bid(db_session, 4, SPEC_A)
    old.prefecture_code = "13"
    old.industry_category = "IT"
    old.announcement_date = datetime.utcnow() - timedelta(days=400)
    match = _make_bid(db_session, 5, SPEC_B)
    match.prefecture_code = "13"
    match.industry_category = "IT"
    db_session.flush()
    svc = TextSimilarityService(db_session)
    svc.build(months=0)
    rank = svc._rank
    seen = []

    def spy(doc_id, n, threshold, candidates):
        seen.extend(svc.doc_ids[index] for index in candidates)
        return rank(doc_id, n, threshold, candidates)

    monkeypatch.setattr(svc, "_rank", spy)
    result = svc.get_top_n_similar(1, n=1, threshold=0, months=6,
                                   prefecture_code="13", industry_category="IT")
    assert seen == [5]
    assert [item["bid_id"] for item in result] == [5]
    result = svc.get_top_n_similar(1, n=1, threshold=0, months=0,
                                   prefecture_code="13", industry_category="IT")
    assert result[0]["bid_id"] == 4


def test_query_outside_corpus_transforms_without_expanding_window(db_session):
    old = _make_bid(db_session, 1, SPEC_A)
    old.announcement_date = datetime.utcnow() - timedelta(days=800)
    _make_bid(db_session, 2, SPEC_B)
    db_session.flush()
    svc = TextSimilarityService(db_session)
    assert svc.build(months=6) == 1
    results = svc.get_top_n_similar(1, months=6, threshold=0)
    assert results[0]["bid_id"] == 2
    assert results[0]["similarity_score"] > 0
    assert svc.doc_ids == [2]
    assert svc.get_similarity(1, 2) > 0


def test_lru_keys_all_parameters_and_promotes_hits(db_session, monkeypatch):
    _make_bid(db_session, 1, SPEC_A)
    _make_bid(db_session, 2, SPEC_B)
    svc = TextSimilarityService(db_session)
    svc.build(months=0)
    queries = [
        {}, {"n": 1}, {"threshold": 0.99}, {"months": 0},
        {"prefecture_code": "13"}, {"industry_category": "IT"},
    ]
    for query in queries:
        svc.get_cached_top_n(1, **query)
    assert len(svc._similarity_cache) == len(queries)
    for n in range(2, 96):
        svc.get_cached_top_n(1, n=n)
    assert len(svc._similarity_cache) == 99
    first = next(key for key in svc._similarity_cache if key[1:6] == (10, 0.3, 6, "", ""))
    svc.get_cached_top_n(1)
    assert next(reversed(svc._similarity_cache)) == first
    evicted = next(iter(svc._similarity_cache))
    svc.get_cached_top_n(1, n=96)
    svc.get_cached_top_n(1, n=97)
    assert len(svc._similarity_cache) == 100
    assert first in svc._similarity_cache
    assert evicted not in svc._similarity_cache

    def fail(*args):
        raise AssertionError("Cache hit should not rank again")

    monkeypatch.setattr(svc, "_rank", fail)
    result = svc.get_cached_top_n(1)
    if result:
        result[0]["title"] = "mutated"
        assert svc.get_cached_top_n(1)[0]["title"] != "mutated"
    assert svc.get_cached_top_n(1, industry_category="IT") == []


def test_cache_invalidation_on_rebuild_load_data_and_config(db_session, tmp_path, monkeypatch):
    import copy
    import services.text_similarity_service as module

    _make_bid(db_session, 1, SPEC_A)
    bid = _make_bid(db_session, 2, SPEC_B)
    svc = TextSimilarityService(db_session, cache_dir=str(tmp_path))
    svc.build(months=0)
    svc.get_cached_top_n(1, threshold=0)
    svc.build(months=0)
    assert not svc._similarity_cache
    path = svc.save_vectors()
    svc.get_cached_top_n(1, threshold=0)
    assert svc.load_vectors(path)
    assert not svc._similarity_cache
    original = svc.tfidf_matrix
    bid.specification_text_clean = SPEC_D
    bid.organization_name = "updated"
    db_session.flush()
    result = svc.get_cached_top_n(1, threshold=0)
    assert svc.tfidf_matrix is not original
    assert result[0]["organization_name"] == "updated"
    assert not svc.load_vectors(path)
    config = copy.deepcopy(module.get_config())
    config["tfidf"]["max_features"] = 250
    monkeypatch.setattr(module, "get_config", lambda: config)
    svc.get_cached_top_n(1, threshold=0)
    assert svc.vectorizer.max_features == 250
    assert len(svc._similarity_cache) == 1
    db_session.query(Bid).delete()
    db_session.flush()
    assert svc.build(months=0) == 0
    assert svc.tfidf_matrix is None
    assert not svc._similarity_cache


def test_session_free_bounded_artifacts_reused_across_reruns(db_session, monkeypatch):
    import services.text_similarity_service as module

    _make_bid(db_session, 1, SPEC_A)
    _make_bid(db_session, 2, SPEC_B)
    db_session.commit()
    svc = TextSimilarityService(db_session)
    expected = svc.get_cached_top_n(1, threshold=0)
    other_session = sessionmaker(bind=db_session.get_bind())()
    try:
        other = TextSimilarityService(other_session)

        def fail(*args):
            raise AssertionError("Rerun must reuse vectors and ranked results")

        monkeypatch.setattr(other, "_build", fail)
        monkeypatch.setattr(other, "_rank", fail)
        assert other.get_cached_top_n(1, threshold=0) == expected
        assert other.tfidf_matrix is svc.tfidf_matrix
        assert other._similarity_cache is svc._similarity_cache
        assert "session" not in other._artifact
        assert all(isinstance(row, dict) for row in other._artifact["records"])
        assert len(module._SHARED_ARTIFACTS) <= 4
    finally:
        other_session.close()


def test_default_search_loads_compatible_prebuilt_vectors(db_session, tmp_path, monkeypatch):
    import services.text_similarity_service as module

    _make_bid(db_session, 1, SPEC_A)
    _make_bid(db_session, 2, SPEC_B)
    svc = TextSimilarityService(db_session, cache_dir=str(tmp_path))
    svc.build(months=0)
    svc.save_vectors()
    module._SHARED_ARTIFACTS.clear()
    other = TextSimilarityService(db_session, cache_dir=str(tmp_path))

    def fail(*args):
        raise AssertionError("Compatible prebuilt vectors should avoid fitting")

    monkeypatch.setattr(other, "_build", fail)
    assert other.get_top_n_similar(1, threshold=0)[0]["bid_id"] == 2


def test_default_search_does_not_load_truncated_prebuilt(db_session, tmp_path):
    import services.text_similarity_service as module

    _make_bid(db_session, 1, SPEC_A)
    _make_bid(db_session, 2, SPEC_B)
    svc = TextSimilarityService(db_session, cache_dir=str(tmp_path))
    assert svc.build(months=0, max_docs=1) == 1
    svc.save_vectors()
    module._SHARED_ARTIFACTS.clear()
    other = TextSimilarityService(db_session, cache_dir=str(tmp_path))
    assert other.get_top_n_similar(1, threshold=0)[0]["bid_id"] == 2
    assert len(other.doc_ids) == 2
    explicit = TextSimilarityService(db_session, cache_dir=str(tmp_path))
    assert explicit.load_vectors()
    assert explicit.doc_ids == [1]


def test_different_memory_databases_do_not_share_vectors(db_session):
    _make_bid(db_session, 1, SPEC_A)
    svc = TextSimilarityService(db_session)
    svc.build(months=0)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as other_session:
        _make_bid(other_session, 1, SPEC_A)
        other = TextSimilarityService(other_session)
        other.build(months=0)
        assert other._artifact["fingerprint"][0] != svc._artifact["fingerprint"][0]
        assert other.tfidf_matrix is not svc.tfidf_matrix


def test_similarity_does_not_autoflush_pending_database_writes(db_session):
    _make_bid(db_session, 1, SPEC_A)
    _make_bid(db_session, 2, SPEC_B)
    db_session.commit()
    pending = Bid(filename="pending.pdf", current_status="未処理", specification_text=SPEC_A)
    db_session.add(pending)
    TextSimilarityService(db_session).get_cached_top_n(1, threshold=0)
    assert pending.id is None
    assert pending in db_session.new


def test_sparse_scores_match_sklearn_cosine(db_session):
    from sklearn.metrics.pairwise import cosine_similarity

    for bid_id, text in enumerate([SPEC_A, SPEC_B, SPEC_C, SPEC_D], 1):
        _make_bid(db_session, bid_id, text)
    svc = TextSimilarityService(db_session)
    svc.build(months=0)
    expected = cosine_similarity(svc.tfidf_matrix[0], svc.tfidf_matrix).ravel()
    results = svc.get_top_n_similar(1, threshold=0, months=0)
    assert len(results) == 3
    for result in results:
        assert result["similarity_score"] == round(float(expected[result["bid_id"] - 1]), 4)


def test_time_boundary_changes_cached_candidate_set(db_session, monkeypatch):
    import services.text_similarity_service as module

    now = datetime(2026, 9, 17, 12)
    clock = [now]

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            value = clock[0]
            return value.replace(tzinfo=tz) if tz else value

    _make_bid(db_session, 1, SPEC_A).announcement_date = now
    _make_bid(db_session, 2, SPEC_B).announcement_date = now - timedelta(days=30) + timedelta(seconds=1)
    db_session.flush()
    monkeypatch.setattr(module, "datetime", Clock)
    svc = TextSimilarityService(db_session)
    svc.build(months=0)
    assert len(svc.get_cached_top_n(1, threshold=0, months=1)) == 1
    clock[0] += timedelta(seconds=2)
    assert svc.get_cached_top_n(1, threshold=0, months=1) == []


def test_reject_legacy_corrupt_and_wrong_database_prebuilt(db_session, tmp_path):
    import pickle

    svc = TextSimilarityService(db_session, cache_dir=str(tmp_path))
    _make_bid(db_session, 1, SPEC_A)
    svc.build(months=0)
    path = tmp_path / "tfidf_vectors.pkl"
    path.write_bytes(pickle.dumps({"doc_ids": [1]}))
    assert not svc.load_vectors(str(path))
    path.write_bytes(b"not a pickle")
    assert not svc.load_vectors(str(path))
    svc.build(months=0)
    svc.save_vectors(str(path))
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as other_session:
        _make_bid(other_session, 1, SPEC_A)
        other = TextSimilarityService(other_session, cache_dir=str(tmp_path))
        assert not other.load_vectors(str(path))


def test_zero_max_docs_and_negative_months(db_session):
    _make_bid(db_session, 1, SPEC_A)
    svc = TextSimilarityService(db_session)
    assert svc.build(months=0, max_docs=0) == 0
    with pytest.raises(ValueError):
        svc.build(months=-1)
    with pytest.raises(ValueError):
        svc.get_top_n_similar(1, months=-1)


def test_10k_in_memory_similarity_benchmark(db_session, capsys):
    import json
    from statistics import median
    from time import perf_counter

    from sqlalchemy import insert

    now = datetime.utcnow()
    records = []
    for i in range(1, 10001):
        text = (
            f"公共調達案件{i} 地域{i % 47} 分類{i % 11} "
            "東京都の情報システム開発構築運用保守及びデータ移行と品質管理を実施する。"
            f"業務番号{i % 101} 対象施設{i % 233} 安全管理と検査を含む。"
        )
        records.append({
            "id": i, "filename": f"synthetic_{i}.pdf", "current_status": "入札済",
            "analyzed_at": now, "created_at": now, "updated_at": now,
            "specification_text": text,
            "specification_text_clean": text if i % 2 else None,
            "announcement_date": now - timedelta(days=i % 720),
            "prefecture_code": str(i % 47), "industry_category": str(i % 11),
        })
    db_session.execute(insert(Bid), records)
    db_session.commit()
    svc = TextSimilarityService(db_session)
    start = perf_counter()
    assert svc.build(months=0) == 10000
    build_seconds = perf_counter() - start
    start = perf_counter()
    assert len(svc.get_top_n_similar(1, months=0, threshold=0)) == 10
    cold_seconds = perf_counter() - start
    start = perf_counter()
    svc.get_cached_top_n(1, months=0, threshold=0)
    cache_fill_seconds = perf_counter() - start
    warm_times = []
    for _ in range(3):
        start = perf_counter()
        svc.get_cached_top_n(1, months=0, threshold=0)
        warm_times.append(perf_counter() - start)
    start = perf_counter()
    filtered = svc.get_cached_top_n(
        1, months=6, threshold=0, prefecture_code="1", industry_category="1",
    )
    filtered_seconds = perf_counter() - start
    candidates = svc._candidate_indices(1, 6, "1", "1")
    assert len(candidates) < 10000
    assert all(item["prefecture_code"] == "1" and item["industry_category"] == "1" for item in filtered)
    with sessionmaker(bind=db_session.get_bind())() as next_session:
        next_svc = TextSimilarityService(next_session)
        start = perf_counter()
        next_svc.get_cached_top_n(1, months=0, threshold=0)
        rerun_seconds = perf_counter() - start
        assert next_svc.tfidf_matrix is svc.tfidf_matrix
        assert next_svc._similarity_cache is svc._similarity_cache
    matrix = svc.tfidf_matrix
    assert max(cold_seconds, median(warm_times), filtered_seconds, rerun_seconds) < 5
    with capsys.disabled():
        print("\nSIMILARITY_BENCHMARK " + json.dumps({
            "documents": 10000, "build_seconds": build_seconds,
            "cold_search_seconds": cold_seconds, "cache_fill_seconds": cache_fill_seconds,
            "warm_search_median_seconds": median(warm_times),
            "filtered_search_seconds": filtered_seconds, "filtered_candidates": len(candidates),
            "fresh_service_rerun_seconds": rerun_seconds, "matrix_shape": matrix.shape,
            "matrix_nnz": matrix.nnz,
            "sparse_matrix_bytes": matrix.data.nbytes + matrix.indices.nbytes + matrix.indptr.nbytes,
        }, sort_keys=True))
