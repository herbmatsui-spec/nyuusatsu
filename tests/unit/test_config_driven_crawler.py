import pytest
from datetime import date
from crawler.config_driven_crawler import ConfigDrivenCrawler


def detail_crawler():
    return ConfigDrivenCrawler(config={"detail_fields": {
        "field1": {"selector": ".price", "attr": "text", "transform": "normalize_amount", "required": True},
        "field2": {"selector": ".date", "attr": "text", "transform": "normalize_date", "multiple": False},
        "field3": {"selector": ".title", "attr": "text", "transform": "normalize_whitespace", "multiple": True},
    }})

def test_parse_detail_no_fields():
    # Test fallback to raw text when no detail_fields are defined
    crawler = detail_crawler()
    # Manually clear detail_fields to test fallback behavior
    crawler.config["detail_fields"] = {}
    html = "<div>Hello World</div>"
    result = crawler.parse_detail(html)
    # Should fallback to raw text extraction
    assert result == "Hello World"

def test_parse_detail_with_fields():
    # Test parsing with detail_fields
    crawler = detail_crawler()
    html = """
    <div class="price">1,234,567円</div>
    <div class="date">2026.08.27</div>
    <div class="title">   平成元年   </div>
    """
    result = crawler.parse_detail(html)
    # Check that we get the expected fields
    assert "field1" in result  # price field
    assert "field2" in result  # date field
    assert "field3" in result  # title field
    # Check values - transform functions should be applied
    assert result["field1"] == 1234567  # normalize_amount removes non-digits and converts to int
    assert result["field2"] == date(2026, 8, 27)  # normalize_date converts to date object
    # field3 has multiple: true, so it returns a list
    assert isinstance(result["field3"], list)
    assert result["field3"][0] == "平成元年"  # normalize_whitespace should clean up spaces

def test_parse_detail_multiple_elements():
    # Test multiple element handling
    crawler = detail_crawler()
    html = """
    <div class="price">1,234,567円</div>
    <div class="date">2026.08.27</div>
    <div class="title">First Title</div>
    <div class="title">Second Title</div>
    """
    result = crawler.parse_detail(html)
    # field3 has multiple: true, so it should be a list
    assert isinstance(result["field3"], list)
    assert len(result["field3"]) == 2
    assert "First Title" in result["field3"]
    assert "Second Title" in result["field3"]


def test_parse_detail_missing_selector():
    # Test behavior when selector doesn't match
    crawler = detail_crawler()
    html = """
    <div class="price">1,234,567円</div>
    <div class="date">2026.08.27</div>
    <div>No matching selector for title</div>
    """
    result = crawler.parse_detail(html)
    # field1 should have value since selector ".price" matches
    assert result["field1"] == 1234567
    # field3 should be empty list since selector ".title" doesn't match and multiple: true
    assert result["field3"] == []

def test_parse_detail_required_field_missing():
    # Test that required fields raise an error when missing
    crawler = detail_crawler()
    html = "<div>No matching selector for required field</div>"
    with pytest.raises(ValueError, match="Required field field1 not found in HTML"):
        crawler.parse_detail(html)


def configured(**overrides):
    from scripts.gen_crawler import generate_config_dict
    config = generate_config_dict("テスト市", "https://official.example/notices/index", list_item_selector="a.bid")
    config.update(overrides)
    return ConfigDrivenCrawler(config=config, delay=0)


def test_static_links_pdf_queries_hints_and_unsafe_schemes():
    crawler = configured()
    html = '''<a class="bid" href="detail">案件</a>
    <a href="/docs/NOTICE.PDF?download=1#page=2">資料</a>
    <a href="/download?id=42">仕様書</a>
    <button data-url="../relative">案件</button>
    <div data-href="/data">案件</div>
    <a class="bid" href="javascript:bad" data-url="/safe">案件</a>
    <a class="bid" href="data:text/html,bad">入札</a>
    <a class="bid" href="file:///etc/passwd">入札</a>
    <a class="bid" href="//user:password@official.example/x">入札</a>
    <a class="bid" href="#fragment">案件</a>
    <button data-url="/data">重複</button>'''
    assert crawler.parse_list(html) == [
        "https://official.example/notices/detail", "https://official.example/safe",
        "https://official.example/docs/NOTICE.PDF?download=1", "https://official.example/download?id=42",
        "https://official.example/relative", "https://official.example/data",
    ]


def test_bounded_pagination_fallback_relative_origin_and_visited(monkeypatch):
    crawler = configured(pagination={"next_button_selectors": ["a.next", "a[rel=next]"], "max_pages": 5})
    pages = {
        crawler.list_url: '<a class="bid" href="one">1</a><a class="next" href="https://other.example/next">next</a><a rel="next" href="?page=2">next</a>',
        'https://official.example/notices/index?page=2': '<a class="bid" href="two">2</a><a rel="next" href="index">loop</a>',
    }
    calls = []
    monkeypatch.setattr(crawler, "fetch", lambda url: calls.append(url) or pages[url])
    assert crawler.crawl_range() == ['https://official.example/notices/one', 'https://official.example/notices/two']
    assert calls == list(pages)
    assert crawler._current_url is None
    crawler.max_pages = 1
    calls.clear()
    assert crawler.crawl_range() == ['https://official.example/notices/one']
    assert calls == [crawler.list_url]
    crawler.max_depth = 0
    calls.clear()
    assert crawler.crawl_range() == []
    assert calls == []


def test_date_state_restored_on_fetch_error(monkeypatch):
    crawler = configured()
    original = date(2026, 1, 1)
    crawler.start_date = original
    def fail(url):
        raise RuntimeError("fixture")
    monkeypatch.setattr(crawler, "fetch", fail)
    with pytest.raises(RuntimeError, match="fixture"):
        crawler.crawl_range(start_date=date(2026, 2, 1))
    assert crawler.start_date == original
    assert crawler.end_date is None


def response(content, content_type="text/html", status=200, location=None):
    import requests
    result = requests.Response()
    result.status_code = status
    result._content = content
    result._content_consumed = True
    result.headers["Content-Type"] = content_type
    if location:
        result.headers["Location"] = location
    return result


@pytest.mark.parametrize("encoding,metadata", [
    ("cp932", '<meta charset="cp932">'),
    ("euc_jp", '<meta http-equiv="Content-Type" content="text/html; charset=euc-jp">'),
    ("utf-8", '<meta charset="utf-8">'),
])
def test_fetch_metadata_decodes_japanese(monkeypatch, encoding, metadata):
    import requests
    text = metadata + '<h1>入札公告と仕様書</h1>'
    result = response(text.encode(encoding), "text/html")
    result.encoding = "ISO-8859-1"
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: result)
    assert configured().fetch("https://official.example/bids") == text


def test_response_header_and_apparent_encoding(monkeypatch):
    import requests
    crawler = configured()
    text = '<h1>入札公告</h1>'
    monkeypatch.setattr(requests.Response, "apparent_encoding", property(lambda self: "euc-jp"))
    assert crawler._decode_response(response(text.encode("euc-jp"))) == text
    declared = '<meta charset="utf-8">' + text
    assert crawler._decode_response(response(declared.encode("cp932"), "text/html; charset=cp932")) == declared
    crawler.config["encoding"] = {"preferred": "cp932", "auto_detect": False}
    assert crawler._decode_response(response(text.encode("cp932"))) == text


def test_agency_settings_used_in_requests_retries_delay_proxy(monkeypatch):
    import requests
    from unittest.mock import Mock
    from scripts.gen_crawler import generate_config_dict
    config = generate_config_dict("親省", "https://official.example/bids", agency_type="ministry")
    crawler = ConfigDrivenCrawler(config=config, proxy="http://proxy.example:8080", backoff=0)
    assert (crawler.delay, crawler.retry, crawler.timeout, crawler.max_depth) == (10, 5, 30, 3)
    request = Mock(side_effect=[requests.Timeout("fixture"), response(b"ok")])
    sleep = Mock()
    monkeypatch.setattr(requests, "get", request)
    monkeypatch.setattr("crawler.config_driven_crawler.time.sleep", sleep)
    assert crawler.fetch(config["list_url"]) == "ok"
    assert request.call_count == 2
    assert request.call_args.kwargs == {
        "timeout": 30, "headers": {"User-Agent": "ConfigDrivenCrawler/1.0"},
        "proxies": {"http": "http://proxy.example:8080", "https": "http://proxy.example:8080"},
        "allow_redirects": False,
    }
    assert [call.args[0] for call in sleep.call_args_list] == [10, 0, 10]


def test_redirect_and_retry_bounds(monkeypatch):
    import requests
    from unittest.mock import Mock
    crawler = configured()
    request = Mock(return_value=response(b"", status=302, location="https://other.example/page"))
    monkeypatch.setattr(requests, "get", request)
    with pytest.raises(ValueError, match="cross-origin"):
        crawler.fetch(crawler.list_url)
    assert request.call_count == 1
    request.reset_mock()
    with pytest.raises(ValueError, match="HTTP"):
        crawler.fetch("file:///missing")
    assert request.call_count == 0
    crawler.retry = 2
    crawler.backoff = 0
    request.side_effect = requests.Timeout("fixture")
    monkeypatch.setattr("crawler.config_driven_crawler.time.sleep", lambda _: None)
    with pytest.raises(requests.Timeout):
        crawler.fetch(crawler.list_url)
    assert request.call_count == 2


def test_pdf_response_ingestion(monkeypatch):
    import requests
    from unittest.mock import MagicMock, patch
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: response(b"pdf", "application/pdf"))
    with patch("pdfplumber.open") as open_pdf:
        page = MagicMock()
        page.extract_text.return_value = "入札公告"
        open_pdf.return_value.__enter__.return_value.pages = [page]
        assert configured().fetch("https://official.example/download?id=1") == "入札公告"


def test_save_uses_existing_repository_interface():
    from unittest.mock import Mock
    repository = Mock(spec=["upsert_bid"])
    items = [{"title": "案件"}]
    configured().save(items, repository)
    repository.upsert_bid.assert_called_once_with(items[0])


@pytest.mark.parametrize("source", ["mapping", "yaml", "loader"])
def test_startup_normalizes_without_changing_loader_or_input(tmp_path, monkeypatch, source):
    from copy import deepcopy
    import yaml

    config = {"agency_name": "　大阪かふ　", "agency_name_aliases": {"大阪かふ": "大阪府"},
              "municipality_code": "００１", "parent_id": "name: 大阪かふ ",
              "crawl_settings": {"retry": 2}, "detail_fields": {}}
    before = deepcopy(config)
    if source == "mapping":
        crawler = ConfigDrivenCrawler(config=config)
    elif source == "yaml":
        path = tmp_path / "crawler.yaml"
        content = yaml.safe_dump(config, allow_unicode=True)
        path.write_text(content, encoding="utf-8")
        crawler = ConfigDrivenCrawler(config_path=path)
        assert path.read_text(encoding="utf-8") == content
    else:
        monkeypatch.setattr(ConfigDrivenCrawler, "_load_config", lambda self, path: config)
        crawler = ConfigDrivenCrawler(config_path="unused")
    assert crawler.config["agency_name"] == "大阪府"
    assert crawler.config["parent_id"] == "name:大阪府"
    assert crawler.config["municipality_code"] == "００１"
    assert crawler.retry == 2
    assert config == before
    assert ConfigDrivenCrawler(config=crawler.config).config == crawler.config


def test_startup_no_implicit_typo_or_abbreviation_alias():
    crawler = ConfigDrivenCrawler(config={"agency_name": " 大阪かふ ", "parent_id": "code:００１"})
    assert crawler.config["agency_name"] == "大阪かふ"
    assert crawler.config["parent_id"] == "code:００１"
