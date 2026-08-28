"""
Phase 05: GEPS検索結果抽出
Step 32: 検索結果から案件名（タイトル）を抽出できることを確認
"""
import pytest
from bs4 import BeautifulSoup


def test_extract_title_from_row(sample_geps_html):
    """1行目の a タグテキストが取得できることを確認"""
    soup = BeautifulSoup(sample_geps_html, "lxml")
    rows = soup.select("table tr")
    for row in rows:
        a = row.find("a")
        if a:
            title = a.get_text(strip=True)
            assert len(title) > 0
            break


def test_title_not_empty(sample_geps_html):
    """抽出したタイトルが空でないことを確認"""
    soup = BeautifulSoup(sample_geps_html, "lxml")
    titles = [a.get_text(strip=True) for a in soup.find_all("a") if a.get_text(strip=True)]
    assert len(titles) > 0
    for t in titles:
        assert len(t) > 0


def test_title_contains_japanese(sample_geps_html):
    """タイトルに日本語文字が含まれることを確認"""
    soup = BeautifulSoup(sample_geps_html, "lxml")
    for a in soup.find_all("a"):
        text = a.get_text(strip=True)
        if text:
            assert any(ord(c) > 0x3000 for c in text)
            break
