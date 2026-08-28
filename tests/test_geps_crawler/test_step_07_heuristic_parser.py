from crawler.parsers.heuristic_parser import HeuristicParser
from crawler.models.crawl_result import CrawlResult
import pytest

def test_heuristic_parser_init():
    """パーサーが正常に初期化されるか"""
    parser = HeuristicParser()
    assert parser.keywords is not None
    assert len(parser.keywords) > 0

def test_heuristic_parser_keywords():
    """入札関連キーワードが含まれているか"""
    parser = HeuristicParser()
    assert "入札" in parser.keywords
    assert "仕様書" in parser.keywords
    assert "調達" in parser.keywords

def test_heuristic_parser_extract_pdf_links():
    """入札キーワードを含むPDFリンクが抽出されるか"""
    parser = HeuristicParser()
    html = '<html><body><a href="/bid/nyusatsu_spec.pdf">入札仕様書</a></body></html>'
    results = parser.parse(html, "https://example.com", "テスト省")
    assert len(results) >= 1
    assert results[0].title == "入札仕様書"

def test_heuristic_parser_relative_url():
    """相対URLが絶対URLに変換されるか"""
    parser = HeuristicParser()
    html = '<html><body><a href="/docs/spec.pdf">入札案件</a></body></html>'
    results = parser.parse(html, "https://example.com/page", "テスト省")
    if results:
        assert results[0].url.startswith("https://example.com")

def test_heuristic_parser_keyword_match_title():
    """タイトルにキーワードが含まれていればマッチするか"""
    parser = HeuristicParser()
    html = '<html><body><a href="/test.html">公告情報一覧</a></body></html>'
    results = parser.parse(html, "https://example.com", "テスト省")
    assert len(results) >= 1

def test_heuristic_parser_no_match():
    """キーワードに一致しないリンクは除外されるか"""
    parser = HeuristicParser()
    html = '<html><body><a href="/about.html">会社概要</a></body></html>'
    results = parser.parse(html, "https://example.com", "テスト省")
    assert len(results) == 0

def test_heuristic_parser_dedup():
    """同じURLは重複排除されるか"""
    parser = HeuristicParser()
    html = '''<html><body>
    <a href="/bid/spec.pdf">入札仕様書A</a>
    <a href="/bid/spec.pdf">入札仕様書A(重複)</a>
    </body></html>'''
    results = parser.parse(html, "https://example.com", "テスト省")
    urls = [r.url for r in results]
    assert len(urls) == len(set(urls))

def test_heuristic_parser_date_extraction_yyyy_mm_dd():
    """YYYY年MM月DD日 形式の日付を抽出できるか"""
    parser = HeuristicParser()
    html = '<html><body><div>2026年7月10日<a href="/spec.pdf">入札公告</a></div></body></html>'
    results = parser.parse(html, "https://example.com", "テスト省")
    if results:
        assert results[0].publish_date != "不明"

def test_heuristic_parser_date_extraction_slash():
    """YYYY/MM/DD 形式の日付を抽出できるか"""
    parser = HeuristicParser()
    html = '<html><body><div>2026/07/10<a href="/spec.pdf">仕様書公開</a></div></body></html>'
    results = parser.parse(html, "https://example.com", "テスト省")
    if results:
        assert results[0].publish_date != "不明"

def test_is_pdf_url_true():
    """PDF URLを正しく判定するか"""
    parser = HeuristicParser()
    assert parser._is_pdf_url("https://example.com/doc.pdf") == True
    assert parser._is_pdf_url("https://example.com/doc.PDF") == True
    assert parser._is_pdf_url("https://example.com/doc.pdf?v=1") == True

def test_is_pdf_url_false():
    """非PDF URLを正しく除外するか"""
    parser = HeuristicParser()
    assert parser._is_pdf_url("https://example.com/page.html") == False
    assert parser._is_pdf_url("https://example.com/image.jpg") == False

def test_heuristic_parser_empty_html():
    """空HTMLで空リストを返すか"""
    parser = HeuristicParser()
    results = parser.parse("", "https://example.com", "テスト省")
    assert results == []

def test_heuristic_parser_agency_name_set():
    """agency_nameが結果に正しくセットされるか"""
    parser = HeuristicParser()
    html = '<html><body><a href="/bid/spec.pdf">入札仕様書</a></body></html>'
    results = parser.parse(html, "https://example.com", "経済産業省")
    if results:
        assert results[0].agency_name == "経済産業省"

def test_heuristic_parser_url_keyword_match():
    """URLパスに 'nyusatsu' が含まれるリンクがマッチするか"""
    parser = HeuristicParser()
    html = '<html><body><a href="/nyusatsu/data.html">データ一覧</a></body></html>'
    results = parser.parse(html, "https://example.com", "テスト省")
    assert len(results) >= 1

def test_heuristic_parser_parent_text_match():
    """親要素のテキストにキーワードが含まれる場合マッチするか"""
    parser = HeuristicParser()
    html = '<html><body><div>入札情報のお知らせ<a href="/info/doc.html">詳細を見る</a></div></body></html>'
    results = parser.parse(html, "https://example.com", "テスト省")
    assert len(results) >= 1
