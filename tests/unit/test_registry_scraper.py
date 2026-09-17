import io
import json
from unittest.mock import MagicMock, patch

import pytest
import yaml

from crawler.registry import RegistryRecord
from crawler.utils.registry_scraper import RegistryScraper, ScrapedAgency


def test_csv_official_columns_encoding_and_no_invented_urls():
    content = "団体コード,団体名,都道府県名\n011002,札幌市,北海道\n".encode("cp932")
    records = RegistryScraper().parse_csv(content, "https://official.example/codes.csv", encoding="cp932")
    assert len(records) == 1
    record = records[0]
    assert record.identity == "code:011002"
    assert record.name == "札幌市"
    assert record.region == "北海道"
    assert record.base_url == record.bid_url_pattern == record.bid_system == ""
    assert record.extra["provenance"] == [{"source_url": "https://official.example/codes.csv",
                                          "format": "csv", "locator": "row:2"}]


def test_csv_mapping_links_parent_and_roundtrip(tmp_path):
    scraper = RegistryScraper()
    records = scraper.parse_csv(
        "id,label,base_url,bid_url_pattern,parent_id\n001,子,/org,/bids,code:00\n002,危険,javascript:bad,data:text/plain,x\n",
        "https://official.example/catalog/", {"municipality_code": "id", "name": "label"})
    assert records[0].base_url == "https://official.example/org"
    assert records[0].bid_url_pattern == "https://official.example/bids"
    assert records[0].parent_id == "code:00"
    assert records[1].base_url == records[1].bid_url_pattern == ""
    path = tmp_path / "registry.csv"
    scraper.to_csv(records, path)
    loaded = scraper._load_municipality_codes_from_csv(path)
    assert loaded[0].identity == records[0].identity
    assert loaded[0].parent_id == "code:00"
    assert loaded[0].extra["provenance"][0] == records[0].extra["provenance"][0]
    path = tmp_path / "registry.yaml"
    scraper.to_yaml(records, path)
    loaded_yaml = [RegistryRecord(**row) for row in yaml.safe_load(path.read_text())]
    assert loaded_yaml[0].parent_id == "code:00"
    assert loaded_yaml[0].extra == records[0].extra


def test_xml_namespaces_and_hierarchy():
    content = '<r xmlns="urn:official"><agency code="01" name="親"><agency code="0101" name="子"/></agency></r>'
    records = RegistryScraper().parse_xml(content, "https://official.example/codes.xml")
    assert [r.identity for r in records] == ["code:01", "code:0101"]
    assert [r.parent_id for r in records] == ["", "code:01"]
    assert all(not r.bid_url_pattern for r in records)


def test_xml_rejects_dtd_without_resolution():
    with pytest.raises(ValueError, match="DTD"):
        RegistryScraper().parse_xml('<!DOCTYPE r [<!ENTITY x SYSTEM "file:///missing">]><r name="x">&x;</r>')


@pytest.mark.parametrize("fmt", ["json", "xml"])
def test_estat_only_area_classes_and_five_digit_codes(fmt):
    if fmt == "json":
        content = json.dumps({"GET_META_INFO": {"CLASS_INF": {"CLASS_OBJ": [
            {"@id": "cat01", "CLASS": [{"@code": "99999", "@name": "統計分類"}]},
            {"@id": "area", "CLASS": [{"@code": "01100", "@name": "札幌市"}]},
        ]}}})
    else:
        content = '<GET_META_INFO><CLASS_INF><CLASS_OBJ id="cat01"><CLASS code="99999" name="統計分類"/></CLASS_OBJ><CLASS_OBJ id="area" name="地域"><CLASS code="01100" name="札幌市"/></CLASS_OBJ></CLASS_INF></GET_META_INFO>'
    records = RegistryScraper().parse_estat(content, "https://official.example/master")
    assert [(r.municipality_code, r.name) for r in records] == [("01100", "札幌市")]
    assert records[0].base_url == records[0].bid_url_pattern == ""


def test_html_heading_nested_list_and_table_hierarchy():
    html = '<h1>親省</h1><h2>第一局</h2><div><ul><li><a href="office">支局</a><ul><li><a href="/branch">出張所</a></li></ul></li></ul></div><h3>総務部</h3><table><tr><td><a href="/section">契約課</a></td></tr></table><h2>第二局</h2><a href="javascript:bad">相談室</a>'
    records = RegistryScraper().parse_html_org(html, "親省", "https://official.example/org/")
    by_name = {r.name: r for r in records}
    assert len(records) == 8
    assert by_name["第一局"].parent_id == "name:親省"
    assert by_name["支局"].parent_id == "name:第一局"
    assert by_name["出張所"].parent_id == "name:支局"
    assert by_name["契約課"].parent_id == "name:総務部"
    assert by_name["第二局"].parent_id == "name:親省"
    assert by_name["支局"].base_url == "https://official.example/org/office"
    assert by_name["相談室"].base_url == ""
    assert all(not r.bid_url_pattern for r in records)


def test_pdf_tables_and_text_provenance():
    table_page = MagicMock()
    table_page.extract_tables.return_value = [[['code', 'name', 'parent_id'], ['01', '第一局', 'name:親省']]]
    text_page = MagicMock()
    text_page.extract_tables.return_value = []
    text_page.extract_text.return_value = "親省\n第二局"
    with patch("pdfplumber.open") as open_pdf:
        open_pdf.return_value.__enter__.return_value.pages = [table_page, text_page]
        records = RegistryScraper().parse_pdf(b"pdf fixture", "https://official.example/org.pdf", "親省")
        assert isinstance(open_pdf.call_args.args[0], io.BytesIO)
    assert [r.name for r in records] == ["親省", "第一局", "第二局"]
    assert records[1].parent_id == records[2].parent_id == "name:親省"
    assert records[1].extra["provenance"][0]["locator"] == "page:1/table:1/row:2"
    assert records[2].extra["provenance"][0]["locator"] == "page:2/line:2"
    assert "review required" in records[2].extra["hierarchy_basis"]
    assert all(not r.bid_url_pattern for r in records)


def test_real_pdf_ingestion_empty_page():
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Resources << >> >>']
    data = b'%PDF-1.4\n'
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data += f'{index} 0 obj\n'.encode() + obj + b'\nendobj\n'
    start = len(data)
    data += b'xref\n0 4\n0000000000 65535 f \n'
    data += b''.join(f'{offset:010} 00000 n \n'.encode() for offset in offsets[1:])
    data += f'trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF'.encode()
    records = RegistryScraper().parse_pdf(data, "https://official.example/org.pdf", "親省")
    assert [r.name for r in records] == ["親省"]


def test_configured_sources_never_access_network(tmp_path):
    path = tmp_path / "official.csv"
    path.write_text("municipality_code,name,parent_id\n001,子,code:00\n", encoding="utf-8")
    scraper = RegistryScraper(sources={
        "municipalities": {"path": str(path), "source_url": "https://official.example/codes.csv"},
        "estat": {"format": "estat", "content": '{"CLASS_OBJ":{"@id":"area","CLASS":{"@code":"01","@name":"親"}}}'},
        "ministry_org_charts": {"format": "html", "content": "<h1>親省</h1><h2>局</h2>",
                                "ministry_name": "親省", "source_url": "https://official.example/org"},
    })
    with patch("requests.sessions.Session.request", side_effect=AssertionError("network forbidden")):
        result = scraper.scrape_all(tmp_path / "output")
        assert scraper._fetch("https://official.example/remote") is None
        assert RegistryScraper().scrape_estat_master() == []
        assert RegistryScraper()._get_ministry_org_urls() == {}
    assert result["municipalities"][0].parent_id == "code:00"
    assert result["estat"][0].identity == "code:01"
    assert result["ministry_org_charts"][1].parent_id == "name:親省"


def test_existing_deduplication_contract():
    records = [ScrapedAgency("01", " 札幌市 "), ScrapedAgency("01", "札幌市", base_url="https://official.example/bids"),
               ScrapedAgency("", "課", parent_id="name:県"), ScrapedAgency("", "課", parent_id="name:市")]
    result = RegistryScraper().deduplicate_and_normalize(records)
    assert len(result) == 3
    assert result[0].name == "札幌市"
    assert result[0].base_url == "https://official.example/bids"


def test_scraped_timestamp_column_selects_latest_without_mutation():
    from copy import deepcopy

    scraper = RegistryScraper()
    records = scraper.parse_csv(
        "code,name,base_url,updated_at\n"
        "001,Ａ,https://official.example/new,2026-09-17\n"
        "001,A,https://official.example/old,2026-09-16\n"
    )
    before = deepcopy(records)
    result = scraper.deduplicate_and_normalize(records)
    assert len(result) == 1
    assert result[0].name == "A"
    assert result[0].base_url == "https://official.example/new"
    assert records == before
