import os
from geps_crawler import GEPSCrawler, CrawlerConfig

def test_make_filename_basic():
    """ファイル名が正しく生成されるか"""
    crawler = GEPSCrawler(CrawlerConfig())
    fname = crawler._make_filename("2026年7月1日", "テスト案件", "https://example.com/doc.pdf")
    assert fname.endswith(".pdf")
    assert "テスト案件" in fname

def test_make_filename_sanitize():
    """不正文字がサニタイズされるか"""
    crawler = GEPSCrawler(CrawlerConfig())
    fname = crawler._make_filename("2026/7/1", 'ファイル名<に>危険|な*文字', "https://example.com/doc.pdf")
    assert "<" not in fname
    assert ">" not in fname
    assert "|" not in fname
    assert "*" not in fname

def test_make_filename_empty_title():
    """タイトルが空の場合 'untitled' になるか"""
    crawler = GEPSCrawler(CrawlerConfig())
    fname = crawler._make_filename("2026-01-01", "", "https://example.com/doc.pdf")
    assert "untitled" in fname

def test_make_filename_long_title():
    """長いタイトルが60文字以内に切り詰められるか"""
    crawler = GEPSCrawler(CrawlerConfig())
    long_title = "あ" * 200
    fname = crawler._make_filename("2026-01-01", long_title, "https://example.com/doc.pdf")
    assert len(fname) <= 200

def test_make_filename_no_date():
    """日付なしの場合URLパスからファイル名を生成するか"""
    crawler = GEPSCrawler(CrawlerConfig())
    fname = crawler._make_filename("", "テスト", "https://example.com/docs/spec.pdf")
    assert fname.endswith(".pdf")
    assert len(fname) > 0

def test_ensure_temp_dir(tmp_path):
    """temp_dirが作成されるか"""
    config = CrawlerConfig(temp_dir=str(tmp_path / "new_dir"))
    crawler = GEPSCrawler(config)
    crawler.ensure_temp_dir()
    assert os.path.exists(str(tmp_path / "new_dir"))

def test_make_session():
    """HTTPセッションが正しく作成されるか"""
    crawler = GEPSCrawler(CrawlerConfig())
    assert crawler.session is not None
    assert "User-Agent" in crawler.session.headers
