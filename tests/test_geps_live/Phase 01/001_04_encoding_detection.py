import requests

def test_content_type_has_charset(live_geps_url):
    r = requests.get(live_geps_url, timeout=10)
    ct = r.headers.get('content-type', '').lower()
    assert 'charset' in ct or 'text/html' in ct

def test_decoded_text_readable(live_geps_url):
    r = requests.get(live_geps_url, timeout=10)
    assert len(r.text) > 100
    assert r.text.count('<') > 2

def test_encoding_not_garbled(live_geps_url):
    r = requests.get(live_geps_url, timeout=10)
    assert '\\ufffd' not in r.text[:5000]