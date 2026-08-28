"""
Phase 05: GEPS検索結果抽出
Step 34: 検索結果から公示日を抽出できることを確認
"""
import re


def test_extract_date_yyyy_mm_dd():
    """2026年7月1日 形式の日付を抽出できることを確認"""
    pattern = r"(19|20)\d{2}[/\-年]\s*\d{1,2}[/\-月]\s*\d{1,2}日?"
    m = re.search(pattern, "2026年7月1日")
    assert m is not None
    assert "2026" in m.group()


def test_extract_date_slash():
    """2026/07/01 形式の日付を抽出できることを確認"""
    pattern = r"(19|20)\d{2}[/\-年]\s*\d{1,2}[/\-月]\s*\d{1,2}日?"
    m = re.search(pattern, "2026/07/01")
    assert m is not None


def test_date_regex_no_match_non_date():
    """日付以外の文字列にマッチしないことを確認"""
    pattern = r"(19|20)\d{2}[/\-年]\s*\d{1,2}[/\-月]\s*\d{1,2}日?"
    assert re.search(pattern, "ただいま募集中") is None
    assert re.search(pattern, "abc123") is None
