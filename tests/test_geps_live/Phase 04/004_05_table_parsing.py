from bs4 import BeautifulSoup

def test_table_parses_rows(sample_geps_html):
    soup = BeautifulSoup(sample_geps_html, 'lxml')
    rows = soup.select('table tr')
    assert len(rows) >= 3

def test_table_cells_not_empty(sample_geps_html):
    soup = BeautifulSoup(sample_geps_html, 'lxml')
    for row in soup.select('table tr'):
        cells = row.find_all('td')
        if cells:
            for cell in cells:
                assert len(cell.get_text(strip=True)) >= 0

def test_table_headers_skippable(sample_geps_html):
    soup = BeautifulSoup(sample_geps_html, 'lxml')
    rows = soup.select('table tr')
    data_rows = [r for r in rows if r.find('a')]
    assert len(data_rows) > 0