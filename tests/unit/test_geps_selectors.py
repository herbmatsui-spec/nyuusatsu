from pathlib import Path
import asyncio

import pytest
import yaml

from crawler.geps_crawler import GEPSCrawler
from crawler.utils.selector_validator import SelectorValidator

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "geps"
SELECTOR_CONFIG = Path(__file__).parents[2] / "crawler" / "config" / "geps_selectors.yaml"


def test_selector_config_loads_with_version():
    crawler = GEPSCrawler()
    config = crawler._load_selectors()
    assert config["selectors_version"] == "2026.09"
    assert "table tr" in config["pages"]["search_results"]["item"]


def test_selector_config_rejects_version_mismatch():
    with pytest.raises(ValueError, match="version mismatch"):
        GEPSCrawler(selectors_version="1900.01")


def test_selector_validator_accepts_config():
    result = SelectorValidator.from_file(SELECTOR_CONFIG).validate()
    assert result["valid"]
    assert result["selector_count"] > 20


def test_selector_validator_rejects_invalid_selector():
    config = {"selectors_version": "1", "pages": {"search_results": {"item": ["["]}}}
    result = SelectorValidator(config).validate()
    assert not result["valid"]
    assert result["errors"]


def test_parser_uses_fallback_table_selectors():
    crawler = GEPSCrawler()
    html = """
    <table><tr>
      <td><a class="title" href="/detail/001">案件</a></td>
      <td class="organization">機関</td>
      <td class="budget">1,000円</td>
      <td class="deadline">2026-02-01</td>
    </tr></table>
    """
    results = crawler.parse_list(html)
    assert len(results) == 1
    assert results[0]["organization"] == "機関"
    assert results[0]["url"] == "https://www.geps.go.jp/detail/001"


def test_parser_uses_configured_result_items():
    crawler = GEPSCrawler()
    html = (FIXTURE_DIR / "search_results.html").read_text(encoding="utf-8")
    results = crawler.parse_list(html)
    # Fixture contains 2 div items + 1 table row = 3 total
    assert len(results) == 3
    assert results[0]["title"] == "テスト入札情報"
    assert not results[0]["url"].endswith(".pdf")


# === Selector Regression Tests ===

def test_search_form_selectors_match_fixture():
    """検索フォームのセレクタがフィクスチャのHTMLにマッチすることを確認"""
    from bs4 import BeautifulSoup
    html = (FIXTURE_DIR / "search_form.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    
    # Query input
    query = soup.select_one("#query")
    assert query is not None, "Query input #query not found"
    assert query.get("name") == "query"
    
    # Start date
    start_date = soup.select_one("#startDate")
    assert start_date is not None, "Start date #startDate not found"
    assert start_date.get("name") == "startDate"
    
    # End date
    end_date = soup.select_one("#endDate")
    assert end_date is not None, "End date #endDate not found"
    assert end_date.get("name") == "endDate"
    
    # Submit button
    submit = soup.select_one("#searchButton")
    assert submit is not None, "Submit button #searchButton not found"
    assert submit.get("type") == "submit"


def test_search_results_selectors_match_fixture():
    """検索結果のセレクタがフィクスチャのHTMLにマッチすることを確認"""
    from bs4 import BeautifulSoup
    html = (FIXTURE_DIR / "search_results.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    
    # Item containers
    items = soup.select(".search-result-item, .result-item, tr.result-row, table tr")
    assert len(items) >= 3, f"Expected at least 3 items, got {len(items)}"
    
    # First item (div.search-result-item)
    item1 = soup.select_one(".search-result-item")
    assert item1 is not None
    title1 = item1.select_one(".title, .result-title, td.title a, a[href]")
    assert title1 is not None, "Title not found in first item"
    assert "テスト入札情報" in title1.get_text()
    
    org1 = item1.select_one(".organization, .result-organization, td.organization, td:nth-child(2)")
    assert org1 is not None, "Organization not found in first item"
    assert "テスト組織" in org1.get_text()
    
    budget1 = item1.select_one(".budget, .result-budget, td.budget, td:nth-child(3)")
    assert budget1 is not None, "Budget not found in first item"
    assert "1,000,000円" in budget1.get_text()
    
    deadline1 = item1.select_one(".deadline, .result-deadline, td.deadline, td:nth-child(4)")
    assert deadline1 is not None, "Deadline not found in first item"
    assert "2026-12-31" in deadline1.get_text()
    
    pdf1 = item1.select_one(".pdf-url, .result-pdf, a[href$='.pdf'], a[href*='.pdf']")
    assert pdf1 is not None, "PDF URL not found in first item"
    assert pdf1.get("href") == "/files/123.pdf"
    
    # Second item (div.result-item)
    item2 = soup.select_one(".result-item")
    assert item2 is not None
    title2 = item2.select_one(".title, .result-title, td.title a, a[href]")
    assert title2 is not None
    assert "もう一つの入札" in title2.get_text()
    
    # Third item (table row)
    table_row = soup.select_one("tr.result-row")
    assert table_row is not None
    title3 = table_row.select_one("td.title a")
    assert title3 is not None
    assert "テーブル形式の入札" in title3.get_text()


def test_detail_page_selectors_match_fixture():
    """詳細ページのセレクタがフィクスチャのHTMLにマッチすることを確認"""
    from bs4 import BeautifulSoup
    html = (FIXTURE_DIR / "detail.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    
    # Title
    title = soup.select_one("#detailTitle, h1, [data-field='title'], title")
    assert title is not None, "Title not found"
    assert "クラウド基盤整備業務" in title.get_text()
    
    # Organization
    org = soup.select_one("#detailOrganization, [data-field='organization'], .organization, th.organization + td")
    assert org is not None, "Organization not found"
    assert "デジタル庁" in org.get_text()
    
    # Budget
    budget = soup.select_one("#detailBudget, [data-field='budget'], .budget, th.budget + td")
    assert budget is not None, "Budget not found"
    assert "12,000,000円" in budget.get_text()
    
    # Deadline
    deadline = soup.select_one("#detailDeadline, [data-field='deadline'], .deadline, th.deadline + td")
    assert deadline is not None, "Deadline not found"
    assert "2026-02-15" in deadline.get_text()


def test_selector_fallback_priority():
    """セレクタのフォールバック優先順位が正しく動作することを確認"""
    from bs4 import BeautifulSoup
    
    # 優先度の高いセレクタ（ID）が優先されることを確認
    html = """
    <div class="title" id="detailTitle">優先タイトル</div>
    <h1>劣後タイトル</h1>
    """
    soup = BeautifulSoup(html, "html.parser")
    crawler = GEPSCrawler()
    title_elem = crawler._select_one(soup, crawler.selectors["pages"]["detail"]["title"])
    assert title_elem is not None
    assert "優先タイトル" in title_elem.get_text()
    
    # IDがなければ次のセレクタが使われる
    html2 = "<h1>劣後タイトル</h1>"
    soup2 = BeautifulSoup(html2, "html.parser")
    title_elem2 = crawler._select_one(soup2, crawler.selectors["pages"]["detail"]["title"])
    assert title_elem2 is not None
    assert "劣後タイトル" in title_elem2.get_text()


def test_select_all_returns_unique_elements():
    """_select_all が重複要素を除外して返すことを確認"""
    from bs4 import BeautifulSoup
    html = """
    <div class="search-result-item">
        <a class="title" href="/detail/1">タイトル1</a>
    </div>
    <div class="search-result-item">
        <a class="title" href="/detail/2">タイトル2</a>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    crawler = GEPSCrawler()
    elements = crawler._select_all(soup, crawler.selectors["pages"]["search_results"]["item"])
    assert len(elements) == 2


class FakeDateElement:
    async def fill(self, value):
        self.value = value


class FakePage:
    def __init__(self):
        self.calls = []
        self.date_fields = [FakeDateElement(), FakeDateElement()]

    async def query_selector(self, selector):
        return None

    async def query_selector_all(self, selector):
        return self.date_fields if selector == 'input[type="date"]' else []

    async def wait_for_selector(self, selector, timeout=None):
        self.calls.append(selector)
        if selector != "table tr":
            raise TimeoutError(selector)


def test_date_detection_and_explicit_result_wait():
    async def run_checks():
        crawler = GEPSCrawler()
        page = FakePage()
        field = await crawler._find_date_field(page, "end_date")
        assert field is page.date_fields[-1]
        await crawler._wait_for_results(page)
        assert "table tr" in page.calls

    asyncio.run(run_checks())


def test_selector_validator_counts_selectors():
    """セレクタバリデーターが正しくセレクタ数をカウントすることを確認"""
    result = SelectorValidator.from_file(SELECTOR_CONFIG).validate()
    assert result["valid"]
    # 以下のセレクタ数を確認（カテゴリごとのセレクタの総和）
    assert result["selector_count"] >= 25  # 最低限のセレクタ数


if __name__ == "__main__":
    pytest.main([__file__, "-v"])