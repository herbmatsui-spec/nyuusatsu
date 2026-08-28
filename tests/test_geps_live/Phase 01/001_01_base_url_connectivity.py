import pytest
import requests

def test_base_url_returns_200(live_geps_url):
    r = requests.get(live_geps_url, timeout=10)
    assert r.status_code < 400

def test_base_url_content_not_empty(live_geps_url):
    r = requests.get(live_geps_url, timeout=10)
    assert len(r.content) > 0

def test_base_url_has_html_tag(live_geps_url):
    r = requests.get(live_geps_url, timeout=10)
    assert '<html' in r.text.lower() or '<!doctype' in r.text.lower()