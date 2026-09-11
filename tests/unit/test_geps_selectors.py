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
    assert len(results) == 2
    assert results[0]["title"] == "クラウド基盤整備業務"
    assert not results[0]["url"].endswith(".pdf")


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
