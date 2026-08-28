from urllib.parse import urljoin

def test_relative_path_resolved():
    base = 'https://www.geps.go.jp/search'
    relative = '/docs/spec.pdf'
    result = urljoin(base, relative)
    assert result == 'https://www.geps.go.jp/docs/spec.pdf'

def test_absolute_path_preserved():
    base = 'https://www.geps.go.jp/search'
    absolute = 'https://www.geps.go.jp/docs/spec.pdf'
    result = urljoin(base, absolute)
    assert result == absolute

def test_empty_href_returns_base():
    base = 'https://www.geps.go.jp/search'
    result = urljoin(base, '')
    assert result == base