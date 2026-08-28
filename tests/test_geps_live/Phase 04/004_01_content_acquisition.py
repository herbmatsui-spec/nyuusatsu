import pytest
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def test_bs4_parses_links(sample_geps_html):
    soup = BeautifulSoup(sample_geps_html, 'lxml')
    links = soup.find_all('a', href=True)
    assert len(links) > 0

def test_bs4_extracts_text(sample_geps_html):
    soup = BeautifulSoup(sample_geps_html, 'lxml')
    text = soup.get_text()
    assert '入札' in text

def test_bs4_parses_tables(sample_geps_html):
    soup = BeautifulSoup(sample_geps_html, 'lxml')
    tables = soup.find_all('table')
    assert len(tables) > 0
    rows = soup.select('table tr')
    assert len(rows) > 0