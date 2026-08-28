import re

def test_date_regex_yyyy_mm_dd():
    pattern = r'(19|20)\d{2}[/\-年]\s*\d{1,2}[/\-月]\s*\d{1,2}日?'
    assert re.search(pattern, '2026年7月1日')
    assert re.search(pattern, '2026/07/01')
    assert re.search(pattern, '2026-7-1')

def test_date_regex_extracts_year():
    pattern = r'(19|20)\d{2}[/\-年]\s*\d{1,2}[/\-月]\s*\d{1,2}日?'
    m = re.search(pattern, '2026年7月10日')
    assert m and '2026' in m.group()

def test_date_regex_no_match_non_date():
    pattern = r'(19|20)\d{2}[/\-年]\s*\d{1,2}[/\-月]\s*\d{1,2}日?'
    assert not re.search(pattern, 'ただいま募集中')
    assert not re.search(pattern, 'abc123xyz')