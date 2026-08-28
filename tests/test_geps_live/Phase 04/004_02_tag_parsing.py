from bs4 import BeautifulSoup

def test_find_all_a_tags(sample_geps_html):
    soup = BeautifulSoup(sample_geps_html, 'lxml')
    a_tags = soup.find_all('a')
    assert len(a_tags) > 0

def test_find_all_td_tags(sample_geps_html):
    soup = BeautifulSoup(sample_geps_html, 'lxml')
    td_tags = soup.find_all('td')
    assert len(td_tags) > 0

def test_find_all_tr_tags(sample_geps_html):
    soup = BeautifulSoup(sample_geps_html, 'lxml')
    tr_tags = soup.find_all('tr')
    assert len(tr_tags) >= 2