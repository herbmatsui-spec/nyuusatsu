from datetime import date, datetime

from app_unified_search import CSV_COLUMNS, results_to_csv


def test_csv_datetime_announcement_normalized():
    rows = [
        {
            "id": 1, "title": "案件B", "organization": "大阪府",
            "announcement_date": datetime(2026, 9, 17, 15, 30),
            "budget_amount": None, "qualification_requirements": None,
            "delivery_deadline": date(2026, 12, 31), "deliverables": None,
        }
    ]
    lines = results_to_csv(rows).decode("utf-8-sig").splitlines()
    assert "2026-09-17" in lines[1]
    assert "T00:00:00" not in lines[1]
    assert "T15:30" not in lines[1]
    assert "2026-12-31" in lines[1]


def test_csv_contains_extracted_fields():
    rows = [
        {
            "id": 1,
            "title": "案件A",
            "organization": "東京都",
            "announcement_date": date(2026, 9, 1),
            "budget_amount": 1500000,
            "qualification_requirements": "建設業許可",
            "delivery_deadline": date(2026, 12, 31),
            "deliverables": "舗装工事一式",
        }
    ]
    csv_text = results_to_csv(rows).decode("utf-8-sig")
    lines = csv_text.splitlines()
    header = lines[0]
    assert header == ",".join(CSV_COLUMNS.values())
    assert "予算額（円）" in header
    assert "資格要件" in header
    assert "納期限" in header
    assert "成果物" in header
    assert "2026-12-31" in lines[1]
    assert "1500000" in lines[1]


def test_csv_iso_date_and_none_empty():
    rows = [
        {
            "id": 1, "title": "x", "organization": None,
            "announcement_date": None, "budget_amount": None,
            "qualification_requirements": None,
            "delivery_deadline": date(2026, 1, 31), "deliverables": None,
        }
    ]
    lines = results_to_csv(rows).decode("utf-8-sig").splitlines()
    assert "2026-01-31" in lines[1]
    assert lines[1] == "1,x,,,,,2026-01-31,"


def test_csv_formula_injection_escaped():
    rows = [
        {
            "id": 1, "title": "=HYPERLINK(1)", "organization": "+cmd",
            "announcement_date": None, "budget_amount": None,
            "qualification_requirements": "@x", "delivery_deadline": None,
            "deliverables": "-1",
        }
    ]
    lines = results_to_csv(rows).decode("utf-8-sig").splitlines()
    assert "'=cmd" not in lines[1]
    for cell in lines[1].split(","):
        assert not cell.startswith(("=", "+", "-", "@")) or cell.startswith("'")


def test_csv_empty_rows():
    assert results_to_csv([]).decode("utf-8-sig").strip() == ",".join(CSV_COLUMNS.values())
