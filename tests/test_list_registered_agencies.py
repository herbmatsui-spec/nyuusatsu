"""Tests for scripts/list_registered_agencies.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.list_registered_agencies import (
    summarize,
    analyze_missing_types,
    _group_by_subcategory,
    TARGETS,
    REGISTRY_FACTORIES,
)


def test_targets_match_plan():
    """目標値が計画通り設定されていること。"""
    assert TARGETS["prefecture"] == 47
    assert TARGETS["municipality"] == 1800
    assert TARGETS["ministry"] == 2000
    assert TARGETS["quasi"] == 500


def test_registry_factories():
    """すべてのレジストリファクトリーが登録されていること。"""
    for key in ["prefecture", "city", "municipality", "ministry", "quasi",
                "manual_ministry", "manual_quasi"]:
        assert key in REGISTRY_FACTORIES


def test_summarize_returns_all_types():
    """サマリにすべてのレジストリタイプが含まれること。"""
    summary = summarize()
    for rtype in REGISTRY_FACTORIES:
        assert rtype in summary
        assert "count" in summary[rtype]
        assert "target" in summary[rtype]
        assert "shortfall" in summary[rtype]
        assert "missing_types" in summary[rtype]
        assert "categories" in summary[rtype]
        assert "sample_names" in summary[rtype]


def test_summarize_has_totals():
    """サマリに合計値が含まれること。"""
    summary = summarize()
    assert "_totals" in summary
    totals = summary["_totals"]
    assert totals["count"] > 0
    assert totals["target"] == 4347
    assert "shortfall" in totals


def test_group_by_subcategory():
    """サブカテゴリ分類が正しく動作すること。"""
    from crawler.registry import RegistryRecord
    records = [
        RegistryRecord(municipality_code="01", name="札幌市", base_url="https://example.com"),
        RegistryRecord(municipality_code="02", name="函館市", base_url="https://example.com"),
        RegistryRecord(municipality_code="03", name="京都府", base_url="https://example.com"),
    ]
    groups = _group_by_subcategory(records)
    assert "市" in groups
    assert len(groups["市"]) == 2


def test_analyze_missing_types_returns_list():
    """不足タイプ分析がリストを返すこと。"""
    from crawler.registry import RegistryRecord
    records = [
        RegistryRecord(municipality_code="01", name="国立広島市", base_url="https://example.com"),
    ]
    missing = analyze_missing_types(records, "quasi")
    assert isinstance(missing, list)
    assert "土地改良区" in missing
    assert "田んぼ管理組合" not in missing


def test_unique_inventory_and_coverage(monkeypatch):
    import scripts.list_registered_agencies as inventory
    from crawler.registry import RegistryRecord

    def rec(code, name, url="", **kwargs):
        return RegistryRecord(code, name, "https://official.example/", url, **kwargs)

    data = {
        "prefecture": [rec("010006", "北海道")],
        "city": [rec("011002", "札幌市", "https://official.example/bids")],
        "municipality": [rec("010006", "北海道"), rec("011002", "札幌市"),
                         rec("012025", "函館市", "https://search.geps.go.jp/search?q=x")],
        "ministry": [rec("M1", "総務省")],
        "manual_ministry": [rec("", "総務省", "https://official.example/notices",
                                extra={"verified_bid_url": "https://official.example/notices",
                                       "verified_at": "2026-09-01", "url_status": "reachable"})],
    }
    monkeypatch.setattr(inventory, "_load_records", lambda kind: data.get(kind, []))
    summary = inventory.summarize()
    assert summary["_totals"]["count"] == 4
    assert summary["_totals"]["raw_count"] == 7
    assert summary["_categories"]["municipality"]["count"] == 2
    assert summary["_totals"]["coverage"] == {
        "reachable_verified": 1, "unverified_url": 1,
        "placeholder_only": 1, "missing_url": 1,
    }
    assert summary["_totals"]["target_is_approximate"] is True


def test_identity_ambiguity_and_hierarchy():
    from scripts.list_registered_agencies import _unique_groups
    from crawler.registry import RegistryRecord
    records = [RegistryRecord("01", "同名町", ""), RegistryRecord("02", "同名町", ""),
               RegistryRecord("", "同名町", ""),
               RegistryRecord("", "事務所", "", parent_id="code:01"),
               RegistryRecord("", "事務所", "", parent_id="code:02")]
    assert len(_unique_groups(records)) == 5


def test_missing_types_detect_real_subtypes():
    from crawler.registry import RegistryRecord
    records = [RegistryRecord("", "東部水道企業団", ""),
               RegistryRecord("", "北部広域連合", "")]
    missing = analyze_missing_types(records, "manual_quasi")
    assert "水道企業団" not in missing
    assert "広域連合" not in missing
    assert "土地改良区" in missing
