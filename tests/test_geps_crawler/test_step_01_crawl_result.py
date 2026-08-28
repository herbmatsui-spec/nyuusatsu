from crawler.models.crawl_result import CrawlResult
import pytest

def test_crawl_result_defaults():
    """CrawlResultのデフォルト値が正しいか"""
    r = CrawlResult(title="テスト", url="https://example.com/test.pdf", agency_name="テスト省")
    assert r.publish_date == "不明"
    assert r.depth == 0
    assert r.parent_url == ""
    assert r.is_pdf_link == False

def test_crawl_result_custom_values():
    """CrawlResultにカスタム値を設定できるか"""
    r = CrawlResult(
        title="案件A", url="https://example.com/a.pdf",
        agency_name="国交省", publish_date="2026-07-01",
        depth=2, parent_url="https://example.com", is_pdf_link=True
    )
    assert r.title == "案件A"
    assert r.publish_date == "2026-07-01"
    assert r.depth == 2
    assert r.is_pdf_link == True

def test_crawl_result_required_fields():
    """必須フィールド（title, url, agency_name）が設定されていること"""
    r = CrawlResult(title="タイトル", url="https://a.com/b.pdf", agency_name="省庁A")
    assert r.title == "タイトル"
    assert r.url == "https://a.com/b.pdf"
    assert r.agency_name == "省庁A"

def test_crawl_result_missing_required_raises():
    """必須フィールドが未指定の場合 TypeError になる"""
    with pytest.raises(TypeError):
        CrawlResult(title="テスト")  # url, agency_name が不足

def test_crawl_result_japanese_title():
    """日本語タイトルが正しく格納されるか"""
    r = CrawlResult(title="令和６年度　○○業務委託", url="https://a.com/b.pdf", agency_name="経産省")
    assert "令和" in r.title
    assert "○○" in r.title

def test_crawl_result_empty_strings():
    """空文字列のフィールドも許容されるか"""
    r = CrawlResult(title="", url="", agency_name="")
    assert r.title == ""
    assert r.url == ""

def test_crawl_result_equality():
    """dataclassの等価性テスト"""
    r1 = CrawlResult(title="A", url="https://a.com", agency_name="X")
    r2 = CrawlResult(title="A", url="https://a.com", agency_name="X")
    assert r1 == r2

def test_crawl_result_mutation():
    """属性を後から変更できるか"""
    r = CrawlResult(title="A", url="https://a.com", agency_name="X")
    r.depth = 5
    r.is_pdf_link = True
    assert r.depth == 5
    assert r.is_pdf_link == True
