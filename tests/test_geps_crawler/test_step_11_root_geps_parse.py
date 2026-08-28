
from geps_crawler import GEPSCrawler, CrawlerConfig

def test_parse_results_basic(sample_geps_html):
    """基本的なHTML解析テスト"""
    crawler = GEPSCrawler(CrawlerConfig())
    results = crawler.parse_results(sample_geps_html, "https://www.geps.go.jp")
    assert len(results) == 2
    assert results[0]["title"] == "○○業務委託に係る入札公告"

def test_parse_results_agency(sample_geps_html):
    """発注機関が正しく抽出されるか"""
    crawler = GEPSCrawler(CrawlerConfig())
    results = crawler.parse_results(sample_geps_html, "https://www.geps.go.jp")
    assert results[0]["agency"] == "経済産業省"
    assert results[1]["agency"] == "総務省"

def test_parse_results_pdf_url(sample_geps_html):
    """PDF URLが正しく抽出されるか"""
    crawler = GEPSCrawler(CrawlerConfig())
    results = crawler.parse_results(sample_geps_html, "https://www.geps.go.jp")
    assert results[0]["pdf_url"] == "https://www.geps.go.jp/docs/spec_001.pdf"

def test_parse_results_date(sample_geps_html):
    """公示日が正しく抽出されるか"""
    crawler = GEPSCrawler(CrawlerConfig())
    results = crawler.parse_results(sample_geps_html, "https://www.geps.go.jp")
    assert "2026" in results[0]["publish_date"]

def test_parse_results_empty_html():
    """空HTMLで空リストが返されるか"""
    crawler = GEPSCrawler(CrawlerConfig())
    results = crawler.parse_results("", "https://www.geps.go.jp")
    assert results == []

def test_parse_results_no_table(no_table_html):
    """テーブルなしHTMLで空リストが返されるか"""
    crawler = GEPSCrawler(CrawlerConfig())
    results = crawler.parse_results(no_table_html, "https://www.geps.go.jp")
    assert results == []

def test_parse_results_non_pdf_excluded():
    """PDFでないリンクは除外されるか"""
    crawler = GEPSCrawler(CrawlerConfig())
    html = """<html><body><table>
    <tr><td><a href="/page.html">HTML案件</a></td><td>省庁</td><td>2026/01/01</td></tr>
    </table></body></html>"""
    results = crawler.parse_results(html, "https://www.geps.go.jp")
    assert len(results) == 0

def test_parse_award_results_basic(sample_award_html):
    """落札結果のHTMLを正しくパースできるか"""
    crawler = GEPSCrawler(CrawlerConfig())
    results = crawler.parse_award_results(sample_award_html, "https://www.geps.go.jp")
    assert len(results) == 2
    assert results[0]["title"] == "○○業務委託"
    assert results[0]["company"] == "株式会社テスト"

def test_parse_award_results_amount(sample_award_html):
    """落札金額が正しく抽出されるか"""
    crawler = GEPSCrawler(CrawlerConfig())
    results = crawler.parse_award_results(sample_award_html, "https://www.geps.go.jp")
    assert "5,000,000" in results[0]["amount"]

def test_parse_award_results_empty():
    """空HTMLで空リストが返されるか"""
    crawler = GEPSCrawler(CrawlerConfig())
    results = crawler.parse_award_results("", "https://www.geps.go.jp")
    assert results == []

def test_parse_award_results_none():
    """NoneのHTMLで空リストが返されるか"""
    crawler = GEPSCrawler(CrawlerConfig())
    results = crawler.parse_award_results(None, "https://www.geps.go.jp")
    assert results == []
