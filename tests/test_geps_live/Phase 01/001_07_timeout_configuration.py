import requests

def test_short_timeout_succeeds(live_geps_url):
    r = requests.get(live_geps_url, timeout=5)
    assert r.status_code < 400

def test_long_timeout_succeeds(live_geps_url):
    r = requests.get(live_geps_url, timeout=20)
    assert r.status_code < 400

def test_timeout_content_consistent(live_geps_url):
    r5 = requests.get(live_geps_url, timeout=5)
    r20 = requests.get(live_geps_url, timeout=20)
    d = abs(len(r5.content) - len(r20.content))
    m = max(len(r5.content), len(r20.content))
    assert d / max(m, 1) < 0.2