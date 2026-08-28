"""
Phase 05: GEPS検索結果抽出
Step 36: 複数行の検索結果をパースできることを確認
"""
import pytest
from bs4 import BeautifulSoup


def test_parse_multiple_rows(sample_geps_html):
    """parse_results() で2件以上抽出できることを確認"""
    soup = BeautifulSoup(sample_geps_html, "lxml")
    rows = soup.select("table tr")
    data_rows = [r for r in rows if r.find("a")]
    assert len(data_rows) >= 2


def test_each_row_has_title(sample_geps_html):
    """全行にtitleが含まれることを確認"""
    soup = BeautifulSoup(sample_geps_html, "lxml")
    rows = soup.select("table tr")
    for row in rows:
        a = row.find("a")
        if a:
            title = a.get_text(strip=True)
            assert len(title) > 0


def test_each_row_has_url(sample_geps_html):
    """全行にpdf_urlが含まれることを確認"""
    soup = BeautifulSoup(sample_geps_html, "lxml")
    rows = soup.select("table tr")
    for row in rows:
        a = row.find("a")
        if a:
            assert a.get("href") is not None
            break
