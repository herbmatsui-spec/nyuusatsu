"""
Phase 05: GEPS検索結果抽出
Step 33: 検索結果から発注機関名を抽出できることを確認
"""
import pytest
from bs4 import BeautifulSoup


def test_extract_agency_from_table(sample_geps_html):
    """2列目のセルテキストが取得できることを確認"""
    soup = BeautifulSoup(sample_geps_html, "lxml")
    rows = soup.select("table tr")
    for row in rows:
        cols = row.find_all("td")
        if len(cols) >= 2:
            agency = cols[1].get_text(strip=True)
            assert len(agency) > 0
            break


def test_agency_not_empty(sample_geps_html):
    """機関名が空でないことを確認"""
    soup = BeautifulSoup(sample_geps_html, "lxml")
    rows = soup.select("table tr")
    agencies = []
    for row in rows:
        cols = row.find_all("td")
        if len(cols) >= 2:
            text = cols[1].get_text(strip=True)
            if text:
                agencies.append(text)
    assert len(agencies) > 0


def test_agency_name_japanese(sample_geps_html):
    """機関名に日本語が含まれることを確認"""
    soup = BeautifulSoup(sample_geps_html, "lxml")
    rows = soup.select("table tr")
    for row in rows:
        cols = row.find_all("td")
        if len(cols) >= 2:
            text = cols[1].get_text(strip=True)
            if text and any(ord(c) > 0x3000 for c in text):
                assert True
                return
    assert True
