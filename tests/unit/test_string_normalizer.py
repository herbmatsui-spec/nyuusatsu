from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import io
import json

import pytest

from crawler.registry import RegistryRecord
from crawler.utils.registry_scraper import RegistryScraper, ScrapedAgency
from utils.string_normalizer import StringNormalizer, main, normalize, normalize_records


@pytest.mark.parametrize("raw,expected", [
    ("　ＡＢＣ\t 支局\n", "ABC 支局"),
    ("ｶﾀｶﾅ\u00a0局", "カタカナ 局"),
    ("大阪かふ", "大阪かふ"),
    ("大阪府", "大阪府"),
    ("国交省", "国交省"),
    ("国土交通省", "国土交通省"),
    ("株式会社試験", "株式会社試験"),
    ("試験株式会社", "試験株式会社"),
    ("合同会社試験", "合同会社試験"),
    ("試験銀行", "試験銀行"),
    ("一般社団法人試験", "一般社団法人試験"),
    ("公益社団法人試験", "公益社団法人試験"),
])
def test_nfkc_whitespace_without_inferred_aliases(raw, expected):
    assert normalize(raw) == expected
    assert normalize(normalize(raw)) == expected


def test_explicit_alias_chains_are_exact_and_idempotent():
    aliases = {" 大阪かふ ": "大阪府", "Ａ": "Ｂ", "B": "C", "C": "C"}
    before = deepcopy(aliases)
    service = StringNormalizer(aliases)
    assert service.normalize("大阪かふ") == "大阪府"
    assert service.normalize("大阪かふ庁") == "大阪かふ庁"
    assert service.normalize("Ａ") == service.normalize(service.normalize("Ａ")) == "C"
    assert aliases == before


@pytest.mark.parametrize("aliases,match", [
    ({"Ａ": "県", "A": "市"}, "Conflicting aliases"),
    ({"A": "B", "B": "A"}, "Cyclic alias"),
    ({"A": "B", "B": "C", "C": "A"}, "Cyclic alias"),
    ({"": "A"}, "empty"),
    ({"A": "　"}, "empty"),
])
def test_bad_aliases_rejected(aliases, match):
    with pytest.raises(ValueError, match=match):
        StringNormalizer(aliases)


@pytest.mark.parametrize("factory", [
    lambda **kw: kw,
    lambda **kw: ScrapedAgency(**kw),
    lambda **kw: RegistryRecord(**kw),
])
def test_reverse_hierarchy_alias_remap_copy_and_idempotence(factory):
    records = [
        factory(municipality_code="001", name=" 子　局 ", base_url="child", parent_id="name:旧　親"),
        factory(municipality_code="", name="旧　親", base_url="parent", parent_id="name:旧根"),
        factory(municipality_code="０００", name="旧根", base_url="root", extra={"provenance": [{"raw": "旧根"}]}),
    ]
    before = deepcopy(records)
    aliases = {"旧 親": "新親", "旧根": "新根"}
    result = normalize_records(records, aliases)
    rows = [asdict(row) if not isinstance(row, dict) else row for row in result]
    assert [row["name"] for row in rows] == ["子 局", "新親", "新根"]
    assert [row["parent_id"] for row in rows] == ["name:新親", "code:０００", ""]
    assert rows[2]["municipality_code"] == "０００"
    assert normalize_records(result, aliases) == result
    assert records == before
    result_extra = result[2]["extra"] if isinstance(result[2], dict) else result[2].extra
    result_extra["provenance"][0]["raw"] = "changed"
    assert records == before


@pytest.mark.parametrize("field", ["region", "municipality_code", "parent_id", "category"])
def test_same_name_distinct_scope_never_merged(field):
    rows = [{"name": "中央町", field: "A"}, {"name": "中央町", field: "B"}]
    result = normalize_records(rows)
    assert len(result) == 2
    assert [row[field] for row in result] == ["A", "B"]


def test_canonical_parent_forms_deduplicate_and_last_row_wins():
    rows = [ScrapedAgency("01", " 親 "),
            ScrapedAgency("", "課", parent_id="name:親", base_url="old"),
            ScrapedAgency("", " 課 ", parent_id="01", base_url="new")]
    result = normalize_records(rows)
    assert len(result) == 2
    assert result[1].base_url == "new"
    assert result[1].parent_id == "code:01"


@pytest.mark.parametrize("stamps,expected", [
    ([None, None], "last"),
    (["2026-09-17T12:00:00Z", "2026-09-16T12:00:00Z"], "first"),
    (["2026-09-17T12:00:00+09:00", "2026-09-17T04:00:00Z"], "last"),
    (["2026-09-17T12:00:00Z", "2026-09-17T12:00:00+00:00"], "last"),
    (["2026-09-17", None], "first"),
    ([None, "2026-09-17"], "last"),
    ([datetime(2026, 9, 17), datetime(2026, 9, 17, tzinfo=timezone.utc)], "last"),
])
def test_timestamp_order(stamps, expected):
    rows = [ScrapedAgency("01", "親", base_url=label, extra={"updated_at": stamp})
            for label, stamp in zip(["first", "last"], stamps)]
    result = normalize_records(rows)
    assert result[0].base_url == expected
    assert normalize_records(result) == result


def test_custom_timestamp_field_and_stable_order():
    rows = [{"name": "Ａ", "observed_at": "2026-09-17", "value": 1},
            {"name": "B"}, {"name": "A", "observed_at": "2026-09-16", "value": 2}]
    result = normalize_records(rows, timestamp_field="observed_at")
    assert [row["name"] for row in result] == ["A", "B"]
    assert result[0]["value"] == 1


@pytest.mark.parametrize("timestamp", ["not-a-date", 123, True, "2026-13-17"])
def test_invalid_timestamp_rejected(timestamp):
    with pytest.raises(ValueError, match="Invalid timestamp"):
        normalize_records([{"name": "親", "updated_at": timestamp}])


@pytest.mark.parametrize("rows,match", [
    ([{"name": "親", "municipality_code": "01"}, {"name": "別親", "municipality_code": "01"}], "Conflicting records for code"),
    ([{"name": "親", "municipality_code": "01", "region": "A"},
      {"name": "親", "municipality_code": "01", "region": "B"}], "Conflicting records for code"),
    ([{"name": "親", "municipality_code": "01"}, {"name": "親"}], "Ambiguous conflicting codes"),
    ([{"name": "親", "municipality_code": "01"}, {"name": "親", "municipality_code": "02"},
      {"name": "子", "parent_id": "name:親"}], "Ambiguous parent"),
    ([{"name": "親", "region": "A"}, {"name": "親", "region": "B"},
      {"name": "子", "parent_id": "name:親"}], "Ambiguous parent"),
    ([{"name": "A", "parent_id": "name:B"}, {"name": "B", "parent_id": "name:A"}], "Cyclic parent"),
    ([{"name": "親", "parent_id": "name:親"}], "Cyclic parent"),
])
def test_conflicts_rejected_without_mutation(rows, match):
    before = deepcopy(rows)
    with pytest.raises(ValueError, match=match):
        normalize_records(rows)
    assert rows == before


def test_aliases_cannot_hide_code_conflicts():
    rows = [{"name": "旧親", "municipality_code": "01"},
            {"name": "新親", "municipality_code": "02"},
            {"name": "子", "parent_id": "name:旧親"}]
    with pytest.raises(ValueError, match="Ambiguous parent"):
        normalize_records(rows, {"旧親": "新親"})


def test_scraper_uses_same_service_and_retains_latest_whole_record():
    rows = [ScrapedAgency("01", " Ａ ", base_url="new", extra={"updated_at": "2026-09-17", "raw": "Ａ"}),
            ScrapedAgency("01", "A", base_url="old", extra={"updated_at": "2026-09-16"})]
    assert RegistryScraper().deduplicate_and_normalize(rows) == normalize_records(rows)
    assert RegistryScraper().deduplicate_and_normalize(rows)[0].extra["raw"] == "Ａ"


def test_standalone_cli_local_json_and_stdin(tmp_path, monkeypatch, capsys):
    path = tmp_path / "records.json"
    aliases = tmp_path / "aliases.json"
    path.write_text(json.dumps([{"name": " 大阪かふ "}, {"name": "大阪府"}]), encoding="utf-8")
    aliases.write_text(json.dumps({"大阪かふ": "大阪府"}), encoding="utf-8")
    main([str(path), "--aliases", str(aliases)])
    output = capsys.readouterr().out
    assert len(json.loads(output)) == 1
    monkeypatch.setattr("sys.stdin", io.StringIO(output))
    main([])
    assert capsys.readouterr().out == output
