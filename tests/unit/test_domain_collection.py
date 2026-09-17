import csv
from dataclasses import replace

import pytest

from crawler.utils.domain_collection import (
    CANDIDATE_FIELDS,
    Candidate,
    DomainCollectionError,
    extract_candidates,
    public_url,
    read_candidates,
    read_organizations,
    review_candidates,
    integrate_candidates,
    write_candidates,
)


def csv_file(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def candidate(**changes):
    return replace(Candidate("総務省", "国", "https://agency.go.jp/", "", "https://links.go.jp/list"), **changes)


@pytest.mark.parametrize("url", [
    "file:///tmp/a", "javascript:alert(1)", "http://localhost/", "http://x.local/",
    "http://127.0.0.1/", "http://[::1]/", "http://10.0.0.1/", "http://2130706433/",
    "http://0x7f000001/", "https://user:pass@agency.go.jp/", "https://a.go.jp:22/",
    "https://a.go.jp\\@localhost/", "https://a.go.jp/\nx", "https://a.internal/",
    "https://a.go.jp./", "https://-a.go.jp/", "https://agency.go.jp/%xx space",
])
def test_unsafe_urls_rejected(url):
    with pytest.raises(DomainCollectionError):
        public_url(url)


def test_extract_links_duplicates_fuzzy_and_pending(tmp_path):
    html = tmp_path / "links.html"
    html.write_text('<base href="http://localhost/"><a href="/home">総務省</a>'
                    '<a href="/home#top">総務省</a><a href="https://other.or.jp/">環境省庁</a>'
                    '<a href="http://127.0.0.1/">総務省</a><a href="javascript:x">総務省</a>', encoding="utf-8")
    result = extract_candidates(html, "https://links.go.jp/list", [("総務省", "国"), ("環境省", "国")])
    assert len(result) == 2
    assert result[0].base_url == "https://links.go.jp/"
    assert "match=exact" in result[0].note
    assert "match=suggested-fuzzy" in result[1].note
    assert all(item.status == "pending" for item in result)
    assert all(not item.bid_url_pattern for item in result)


def test_procurement_explicit_context_relative_links(tmp_path):
    html = tmp_path / "page.html"
    html.write_text('<a href="../bid/list">入札公告</a><a href="/about">概要</a>'
                    '<a href="//portal.or.jp/tender">調達</a>', encoding="utf-8")
    result = extract_candidates(html, "https://agency.go.jp/info/page", [("総務省", "国")], agency_name="総務省", category="国")
    assert {item.bid_url_pattern for item in result} == {"https://agency.go.jp/bid/list", "https://portal.or.jp/tender"}
    with pytest.raises(DomainCollectionError):
        extract_candidates(html, "https://agency.go.jp/", [("総務省", "国")], agency_name="別組織", category="国")


def test_candidate_csv_roundtrip_and_overwrite_guards(tmp_path):
    path = tmp_path / "candidates.csv"
    write_candidates(path, [candidate(note="証拠, reviewed\n次行")])
    assert read_candidates(path) == [candidate(note="証拠, reviewed\n次行")]
    original = path.read_bytes()
    with pytest.raises(DomainCollectionError):
        write_candidates(path, [], inputs=(path,))
    assert path.read_bytes() == original
    output = tmp_path / "dry.csv"
    write_candidates(output, [candidate()], dry_run=True)
    assert not output.exists()


@pytest.mark.parametrize("text", [
    "agency_name,agency_name\na,b\n", "agency_name\na,b\n", "agency_name,category\na\n",
    "agency_name,category\n,国\n",
])
def test_schema_rejected(tmp_path, text):
    path = tmp_path / "bad.csv"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(DomainCollectionError):
        read_organizations(path)


def test_invalid_status_unknown_columns_and_encoding(tmp_path):
    path = tmp_path / "bad.csv"
    csv_file(path, CANDIDATE_FIELDS, [dict(zip(CANDIDATE_FIELDS, ["総務省", "国", "https://agency.go.jp/", "", "https://links.go.jp/", "auto", ""]))])
    with pytest.raises(DomainCollectionError):
        read_candidates(path)
    path.write_bytes(b"\xff\xfe")
    with pytest.raises(DomainCollectionError, match="UTF-8"):
        read_candidates(path)


def test_bounded_input_and_no_guessing(tmp_path, monkeypatch):
    import crawler.utils.domain_collection as module

    html = tmp_path / "page.html"
    html.write_text("<p>総務省</p>", encoding="utf-8")
    assert extract_candidates(html, "https://links.go.jp/", [("総務省", "国")]) == []
    monkeypatch.setattr(module, "MAX_BYTES", 2)
    with pytest.raises(DomainCollectionError, match="exceeds"):
        extract_candidates(html, "https://links.go.jp/", [("総務省", "国")])


def test_review_updates_rows_writes_output_and_preserves_input(tmp_path):
    source = tmp_path / "candidates.csv"
    write_candidates(source, [candidate(), candidate(base_url="https://env.go.jp/", agency_name="環境省")])
    output = tmp_path / "reviewed.csv"
    result = review_candidates(source, output, [2], "approved", note="ok")
    assert [item.status for item in result] == ["pending", "approved"]
    assert "; review=ok" in result[1].note
    assert read_candidates(output) == result
    assert read_candidates(source) == [candidate(), candidate(base_url="https://env.go.jp/", agency_name="環境省")]
    with pytest.raises(DomainCollectionError):
        review_candidates(source, output, [3], "approved")
    with pytest.raises(DomainCollectionError):
        review_candidates(source, output, [1], "auto")


def test_review_dry_run_writes_nothing(tmp_path):
    source = tmp_path / "candidates.csv"
    write_candidates(source, [candidate()])
    assert review_candidates(source, tmp_path / "out.csv", [1], "approved", dry_run=True)
    assert not (tmp_path / "out.csv").exists()


def master_csv(tmp_path, rows):
    return csv_file(tmp_path / "master.csv", ["agency_name", "municipality_code", "category", "base_url"], rows)


def test_integrate_preserves_columns_and_ignores_unapproved(tmp_path):
    master = master_csv(tmp_path, [
        {"agency_name": "総務省", "municipality_code": "", "category": "国", "base_url": "https://old.go.jp/"},
        {"agency_name": "環境省", "municipality_code": "", "category": "国", "base_url": ""},
    ])
    approved = tmp_path / "approved.csv"
    write_candidates(approved, [
        candidate(base_url="https://old.go.jp/", bid_url_pattern="https://old.go.jp/bid/", status="approved"),
        candidate(agency_name="環境省", base_url="https://env.go.jp/", status="approved"),
        candidate(agency_name="外務省", base_url="https://mofa.go.jp/", status="pending"),
    ])
    output = tmp_path / "master_out.csv"
    stats = integrate_candidates(master, [approved], output)
    assert stats == {"master_rows": 2, "approved": 2, "ignored": 1, "updated": 2}
    with output.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["base_url"] == "https://old.go.jp/"
    assert rows[1]["base_url"] == "https://env.go.jp/"
    assert rows[0]["municipality_code"] == ""
    assert all("status" not in row for row in rows)


def test_integrate_conflicts_rejected_and_unapproved_ignored(tmp_path):
    master = master_csv(tmp_path, [{"agency_name": "総務省", "municipality_code": "", "category": "国", "base_url": "https://old.go.jp/"}])
    conflict = tmp_path / "conflict.csv"
    write_candidates(conflict, [candidate(base_url="https://other.go.jp/", status="approved")])
    with pytest.raises(DomainCollectionError, match="Conflict"):
        integrate_candidates(master, [conflict], tmp_path / "out.csv")
    unapproved = tmp_path / "unapproved.csv"
    write_candidates(unapproved, [candidate(base_url="https://other.go.jp/", status="rejected")])
    integrate_candidates(master, [unapproved], tmp_path / "out.csv")
    with (tmp_path / "out.csv").open(encoding="utf-8", newline="") as stream:
        assert list(csv.DictReader(stream))[0]["base_url"] == "https://old.go.jp/"


def test_integrate_explicit_category_and_idempotence(tmp_path):
    master = csv_file(tmp_path / "master.csv", ["agency_name", "base_url"], [{"agency_name": "総務省", "base_url": ""}])
    approved = tmp_path / "approved.csv"
    write_candidates(approved, [candidate(base_url="https://new.go.jp/", status="approved")])
    output = tmp_path / "out.csv"
    assert integrate_candidates(master, [approved], output, category="国")["updated"] == 1
    assert integrate_candidates(output, [approved], tmp_path / "again.csv", category="国")["updated"] == 0
    assert output.read_bytes() == (tmp_path / "again.csv").read_bytes()
    with output.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0] == {"agency_name": "総務省", "base_url": "https://new.go.jp/"}


def test_integrate_in_place_requires_output_master(tmp_path):
    master = master_csv(tmp_path, [{"agency_name": "総務省", "municipality_code": "", "category": "国", "base_url": ""}])
    approved = tmp_path / "approved.csv"
    write_candidates(approved, [candidate(base_url="https://new.go.jp/", status="approved")])
    with pytest.raises(DomainCollectionError, match="In-place"):
        integrate_candidates(master, [approved], tmp_path / "elsewhere.csv", in_place=True)
    assert integrate_candidates(master, [approved], master, in_place=True)["updated"] == 1
    with master.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["base_url"] == "https://new.go.jp/"
    assert rows[0]["agency_name"] == "総務省"


def test_approved_conflict_duplicates_and_category_isolation(tmp_path):
    master = master_csv(tmp_path, [{"agency_name": "総務省", "municipality_code": "001", "category": "国", "base_url": ""}])
    source = tmp_path / "candidates.csv"
    write_candidates(source, [candidate(status="approved"), candidate(status="approved", base_url="https://other.go.jp/")])
    with pytest.raises(DomainCollectionError, match="Conflicting approved"):
        integrate_candidates(master, [source], tmp_path / "out.csv")
    assert not (tmp_path / "out.csv").exists()
    other = tmp_path / "other.csv"
    write_candidates(other, [candidate(category="外郭団体", status="approved")])
    with pytest.raises(DomainCollectionError, match="exact master identity"):
        integrate_candidates(master, [other], tmp_path / "out.csv")
    duplicate = tmp_path / "duplicate.csv"
    write_candidates(duplicate, [candidate(status="approved"), candidate(status="approved")])
    assert integrate_candidates(master, [duplicate], tmp_path / "out.csv")["updated"] == 1


def test_atomic_failure_preserves_input_and_cleans_temp(tmp_path, monkeypatch):
    import crawler.utils.domain_collection as module

    master = master_csv(tmp_path, [{"agency_name": "総務省", "municipality_code": "001", "category": "国", "base_url": ""}])
    source = tmp_path / "candidates.csv"
    write_candidates(source, [candidate(status="approved")])
    original = master.read_bytes()
    before = set(tmp_path.iterdir())

    def fail(*args):
        raise OSError("simulated atomic failure")

    monkeypatch.setattr(module.os, "replace", fail)
    with pytest.raises(OSError):
        integrate_candidates(master, [source], master, in_place=True)
    assert master.read_bytes() == original
    assert set(tmp_path.iterdir()) == before


def test_cli_offline_workflow_and_report(tmp_path, capsys, monkeypatch):
    import json
    import socket
    from scripts.domain_collection import main

    def no_network(*args, **kwargs):
        raise AssertionError("network access forbidden")

    monkeypatch.setattr(socket, "socket", no_network)
    master = csv_file(tmp_path / "organizations.csv", ["agency_name", "priority_level"], [{"agency_name": "総務省", "priority_level": "001"}])
    html = tmp_path / "links.html"
    html.write_text('<a href="https://agency.go.jp/">総務省</a>', encoding="utf-8")
    candidates = tmp_path / "candidates.csv"
    extract_args = ["extract", "--html", str(html), "--source-url", "https://links.go.jp/list", "--organizations", str(master), "--category", "国", "--output", str(candidates)]
    assert main(extract_args + ["--dry-run"]) == 0
    assert not candidates.exists()
    assert main(extract_args) == 0
    capsys.readouterr()
    assert main(["report", "--input", str(candidates), "--dry-run"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["statuses"] == {"pending": 1, "approved": 0, "rejected": 0}
    assert report["candidates"][0]["row"] == 1
    reviewed = tmp_path / "reviewed.csv"
    review_args = ["review", "--input", str(candidates), "--output", str(reviewed), "--approve", "1"]
    assert main(review_args + ["--dry-run"]) == 0
    assert not reviewed.exists()
    assert main(review_args) == 0
    output = tmp_path / "integrated.csv"
    integrate_args = ["integrate", "--master", str(master), "--candidates", str(reviewed), "--category", "国", "--output", str(output)]
    assert main(integrate_args + ["--dry-run"]) == 0
    assert not output.exists()
    assert main(integrate_args) == 0
    with output.open(encoding="utf-8", newline="") as stream:
        assert list(csv.DictReader(stream)) == [{"agency_name": "総務省", "priority_level": "001", "base_url": "https://agency.go.jp/"}]
    rejected = tmp_path / "rejected.csv"
    assert main(["review", "--input", str(candidates), "--output", str(rejected), "--reject", "1"]) == 0
    assert read_candidates(rejected)[0].status == "rejected"


def test_cli_errors_and_dry_run_preserve_inputs(tmp_path, capsys):
    from scripts.domain_collection import main

    source = tmp_path / "candidates.csv"
    write_candidates(source, [candidate()])
    original = source.read_bytes()
    assert main(["review", "--input", str(source), "--output", str(source), "--approve", "1", "--dry-run"]) == 2
    assert "overwrite" in capsys.readouterr().err
    assert source.read_bytes() == original
    assert main(["report", "--input", str(tmp_path / "missing.csv")]) == 2


def test_hardlink_and_symlink_input_overwrite_rejected(tmp_path):
    source = tmp_path / "candidates.csv"
    write_candidates(source, [candidate()])
    hardlink = tmp_path / "hard.csv"
    hardlink.hardlink_to(source)
    symlink = tmp_path / "sym.csv"
    symlink.symlink_to(source)
    for output in (hardlink, symlink):
        with pytest.raises(DomainCollectionError):
            review_candidates(source, output, [1], "approved")
    assert read_candidates(source)[0].status == "pending"


def test_link_and_csv_limits(tmp_path, monkeypatch):
    import crawler.utils.domain_collection as module

    html = tmp_path / "links.html"
    html.write_text('<a href="/">総務省</a>' * 2, encoding="utf-8")
    monkeypatch.setattr(module, "MAX_LINKS", 1)
    with pytest.raises(DomainCollectionError, match="hyperlinks"):
        extract_candidates(html, "https://links.go.jp/", [("総務省", "国")])
    source = csv_file(tmp_path / "organizations.csv", ["agency_name", "category"], [{"agency_name": "総務省", "category": "国"}] * 2)
    monkeypatch.setattr(module, "MAX_ROWS", 1)
    with pytest.raises(DomainCollectionError, match="row limit"):
        read_organizations(source)

