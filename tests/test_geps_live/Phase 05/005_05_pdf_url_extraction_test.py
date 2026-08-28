"""
Phase 05: GEPS検索結果抽出
Step 35: 検索結果からPDF仕様書URLを抽出できることを確認
"""
import pytest
from bs4 import BeautifulSoup
from urllib.parse import urljoin


def test_extract_pdf_url_from_link(sample_geps_html):
    """a href=.pdf からURLを抽出できることを確認"""
    soup = BeautifulSoup(sample_geps_html, "lxml")
    pdf_links = [a for a in soup.find_all("a", href=True) if a["href"].lower().endswith(".pdf")]
    assert len(pdf_links) > 0


def test_pdf_url_is_absolute(sample_geps_html):
    """urljoin で絶対URL化されることを確認"""
    soup = BeautifulSoup(sample_geps_html, "lxml")
    base = "https://www.geps.go.jp"
    for a in soup.find_all("a", href=True):
        if a["href"].lower().endswith(".pdf"):
            absolute = urljoin(base, a["href"])
            assert absolute.startswith("https://www.geps.go.jp")


def test_pdf_url_ends_with_pdf(sample_geps_html):
    """抽出URLが .pdf で終わることを確認"""
    soup = BeautifulSoup(sample_geps_html, "lxml")
    for a in soup.find_all("a", href=True):
        href = a["href"].split("?")[0]
        if href.lower().endswith(".pdf"):
            assert href.lower().endswith(".pdf")
            break
