import requests

def test_https_scheme_in_url(live_geps_url):
    assert live_geps_url.startswith('https://')

def test_ssl_verify_succeeds(live_geps_url):
    r = requests.get(live_geps_url, timeout=10, verify=True)
    assert r.status_code < 400

def test_no_ssl_warning(live_geps_url):
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        requests.get(live_geps_url, timeout=10, verify=True)
    ssl_warnings = [x for x in w if 'ssl' in str(x.message).lower() or 'certificate' in str(x.message).lower()]
    assert len(ssl_warnings) == 0