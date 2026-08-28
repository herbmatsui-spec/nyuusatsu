import requests

def test_redirect_count_reasonable(live_geps_url):
    s = requests.Session()
    r = s.get(live_geps_url, timeout=10, allow_redirects=True)
    assert len(r.history) <= 5

def test_final_url_contains_geps_domain(live_geps_url):
    s = requests.Session()
    r = s.get(live_geps_url, timeout=10, allow_redirects=True)
    assert 'geps.go.jp' in r.url

def test_final_url_accessible(live_geps_url):
    s = requests.Session()
    r = s.get(live_geps_url, timeout=10, allow_redirects=True)
    assert r.status_code < 400