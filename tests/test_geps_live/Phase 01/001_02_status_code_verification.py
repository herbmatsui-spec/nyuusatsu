import requests

def test_head_and_get_match(live_geps_url):
    head_r = requests.head(live_geps_url, timeout=10, allow_redirects=True)
    get_r = requests.get(live_geps_url, timeout=10)
    assert head_r.status_code == get_r.status_code

def test_status_code_2xx_or_3xx(live_geps_url):
    r = requests.head(live_geps_url, timeout=10, allow_redirects=True)
    assert 200 <= r.status_code < 400

def test_content_type_is_html(live_geps_url):
    r = requests.get(live_geps_url, timeout=10)
    ct = r.headers.get('content-type', '').lower()
    assert 'text/html' in ct