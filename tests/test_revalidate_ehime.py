import pytest
import csv
import os
from scripts.revalidate_ehime_urls import check_url, update_csv_row

def test_check_url_valid():
    # Use a known valid URL (Google)
    is_valid, has_keywords = check_url("https://www.google.com")
    assert is_valid is True

def test_check_url_invalid():
    # Use a non-existent domain
    is_valid, has_keywords = check_url("https://this-should-not-exist-123456.com")
    assert is_valid is False

def test_update_csv_row():
    row = {'name': '松山市', 'target_url': 'old_url'}
    updated = update_csv_row(row, 'new_url', True)
    assert updated['target_url'] == 'new_url'
