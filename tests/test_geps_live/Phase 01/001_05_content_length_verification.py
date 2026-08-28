import requests

def test_content_length_header_or_body(live_geps_url):
    r = requests.get(live_geps_url, timeout=10)
    cl = r.headers.get('content-length')
    if cl:
        assert int(cl) > 0
    assert len(r.content) > 0

def test_content_size_within_limit(live_geps_url):
    r = requests.get(live_geps_url, timeout=10)
    assert len(r.content) < 100 * 1024 * 1024

def test_content_size_consistent(live_geps_url):
    r1 = requests.get(live_geps_url, timeout=10)
    r2 = requests.get(live_geps_url, timeout=10)
    diff = abs(len(r1.content) - len(r2.content))
    max_sz = max(len(r1.content), len(r2.content))
    assert diff / max(max_sz, 1) < 0.2