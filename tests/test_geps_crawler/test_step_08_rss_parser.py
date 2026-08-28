from crawler.parsers.rss_parser import RSSParser
import pytest

def test_rss_parser_init():
    """RSSParserが正常に初期化されるか"""
    parser = RSSParser()
    assert parser.logger is not None

def test_rss_parser_parse_rss20(sample_rss_xml):
    """RSS 2.0 XMLを正しくパースできるか"""
    parser = RSSParser()
    results = parser.parse(sample_rss_xml, "https://example.gov.jp", "テスト省")
    assert len(results) == 2
    assert results[0].title == "入札公告: サーバ調達"
    assert results[0].url == "https://example.gov.jp/bid/001.pdf"

def test_rss_parser_parse_date_format(sample_rss_xml):
    """RSS 2.0の日付がYYYY-MM-DD形式に変換されるか"""
    parser = RSSParser()
    results = parser.parse(sample_rss_xml, "https://example.gov.jp", "テスト省")
    assert results[0].publish_date == "2026-07-01"

def test_rss_parser_parse_atom(sample_atom_xml):
    """Atom XMLを正しくパースできるか"""
    parser = RSSParser()
    results = parser.parse(sample_atom_xml, "https://example.gov.jp", "テスト省")
    assert len(results) == 2
    assert results[0].title == "入札案件A"

def test_rss_parser_atom_date(sample_atom_xml):
    """Atomの日付がYYYY-MM-DD形式に変換されるか"""
    parser = RSSParser()
    results = parser.parse(sample_atom_xml, "https://example.gov.jp", "テスト省")
    assert results[0].publish_date == "2026-07-01"

def test_rss_parser_empty_xml():
    """空XMLで空リストを返すか"""
    parser = RSSParser()
    results = parser.parse("", "https://example.com", "テスト省")
    assert results == []

def test_rss_parser_invalid_xml():
    """不正XMLでエラーにならず空リストを返すか"""
    parser = RSSParser()
    results = parser.parse("<not>valid</xml>broken", "https://example.com", "テスト省")
    assert isinstance(results, list)

def test_rss_parser_no_link_items():
    """linkが空のアイテムはスキップされるか"""
    parser = RSSParser()
    xml = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item><title>タイトルのみ</title></item>
    </channel></rss>"""
    results = parser.parse(xml, "https://example.com", "テスト省")
    assert len(results) == 0

def test_rss_parser_agency_name(sample_rss_xml):
    """agency_nameが結果に正しくセットされるか"""
    parser = RSSParser()
    results = parser.parse(sample_rss_xml, "https://example.gov.jp", "国交省")
    for r in results:
        assert r.agency_name == "国交省"

def test_rss_parser_relative_url():
    """相対URLが正しく解決されるか"""
    parser = RSSParser()
    xml = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item>
        <title>相対URLテスト</title>
        <link>/relative/path.pdf</link>
        <pubDate>Mon, 01 Jul 2026 00:00:00 GMT</pubDate>
      </item>
    </channel></rss>"""
    results = parser.parse(xml, "https://example.com", "テスト省")
    assert len(results) == 1
    assert results[0].url == "https://example.com/relative/path.pdf"
