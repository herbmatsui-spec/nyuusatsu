import requests

def test_status_same_with_different_ua(live_geps_url):
    r1 = requests.get(live_geps_url, timeout=10)
    r2 = requests.get(live_geps_url, timeout=10, headers={'User-Agent': 'TestBot/1.0'})
    assert r1.status_code == r2.status_code

def test_content_similar_with_different_ua(live_geps_url):
    r1 = requests.get(live_geps_url, timeout=10)
    r2 = requests.get(live_geps_url, timeout=10, headers={'User-Agent': 'TestBot/1.0'})
    d = abs(len(r1.content) - len(r2.content))
    m = max(len(r1.content), len(r2.content))
    assert d / max(m, 1) < 0.2

def test_html_present_with_different_ua(live_geps_url):
    r = requests.get(live_geps_url, timeout=10, headers={'User-Agent': 'TestBot/1.0'})
    assert '<html' in r.text.lower() or '<!doctype' in r.text.lower()