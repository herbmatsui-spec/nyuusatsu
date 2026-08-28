from bs4 import BeautifulSoup
from urllib.parse import urljoin

def test_filter_pdf_links(sample_geps_html):
    soup = BeautifulSoup(sample_geps_html, 'lxml')
    links = soup.find_all('a', href=True)
    pdf_links = [a for a in links if a['href'].lower().endswith('.pdf')]
    assert len(pdf_links) > 0

def test_filter_relative_urls(sample_geps_html):
    soup = BeautifulSoup(sample_geps_html, 'lxml')
    links = soup.find_all('a', href=True)
    relative_links = [a for a in links if not a['href'].startswith('http')]
    assert len(relative_links) > 0

def test_resolve_relative_to_absolute(sample_geps_html):
    soup = BeautifulSoup(sample_geps_html, 'lxml')
    base = 'https://www.geps.go.jp'
    for a in soup.find_all('a', href=True):
        absolute = urljoin(base, a['href'])
        assert absolute.startswith('https://www.geps.go.jp')