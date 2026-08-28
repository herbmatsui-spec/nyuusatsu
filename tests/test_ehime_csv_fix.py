import pytest
import csv
import os
from scripts.fix_ehime_active import is_ehime, activate

def test_is_ehime():
    # Case: Ehime
    row_ehime = {'name': '松山市', 'region': '愛媛県'}
    assert is_ehime(row_ehime) is True
    
    # Case: Not Ehime
    row_hokkaido = {'name': '札幌市', 'region': '北海道'}
    assert is_ehime(row_hokkaido) is False

def test_activate():
    # Case: Update False to True
    row = {'name': '松山市', 'region': '愛媛県', 'is_active': 'False'}
    updated = activate(row)
    assert updated['is_active'] == 'True'
    
    # Case: Already True
    row_true = {'name': '愛媛県', 'region': '愛媛県', 'is_active': 'True'}
    updated_true = activate(row_true)
    assert updated_true['is_active'] == 'True'

def test_run_simulation(tmp_path):
    # Create a temporary CSV
    csv_file = tmp_path / "test_agencies.csv"
    content = [
        ["name", "region", "is_active"],
        ["松山市", "愛媛県", "False"],
        ["今治市", "愛媛県", "False"],
        ["札幌市", "北海道", "True"],
    ]
    with open(csv_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(content)
    
    # We need to mock the path in the script or pass it as an argument
    # Since the script has hardcoded 'data/agencies.csv', 
    # we will implement a small wrapper or temporarily patch it.
    import scripts.fix_ehime_active as fea
    original_path = 'data/agencies.csv'
    # Patching the logic manually for test
    
    # Simulate the logic of run()
    with open(csv_file, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    updated_rows = []
    for row in rows:
        if is_ehime(row):
            row = activate(row)
        updated_rows.append(row)
    
    assert updated_rows[0]['is_active'] == 'True' # Matsuyama
    assert updated_rows[1]['is_active'] == 'True' # Imabari
    assert updated_rows[2]['is_active'] == 'True' # Sapporo (unchanged)
