import pytest
from unittest.mock import patch

from crawler.parsers.award_pdf_parser import parse_award_pdf_text
from crawler.parsers.award_parser import (
    extract_industry_from_text,
    parse_date as parse_award_date,
    parse_date as parse_announcement_date,
    parse_budget_amount,
    parse_contract_amount,
    parse_winner_name,
)

def test_parse_award_pdf_text_valid():
    """有効なPDFテキスト入力に対する正常系テスト"""
    # Test with the exact format that the parser functions expect
    budget_line = "予定価格 12,345,678円"
    contract_line = "落札価格 11,111,111円"
    winner_line = "落札者：株式会社サンプル"  # Use the exact format that parse_winner_name expects
    
    # Test individual parsing functions
    budget_amount = parse_budget_amount(budget_line)
    contract_amount = parse_contract_amount(contract_line)
    winner_name = parse_winner_name(winner_line)
    
    assert budget_amount == 12345678
    assert contract_amount == 11111111
    assert winner_name == "株式会社サンプル"
    
    # Test with the full context but properly extract lines
    sample_text = """
    入札公告番号: 令和5年度第1号
    予定価格 12,345,678円
    落札価格 11,111,111円
    落札者：株式会社サンプル
    公告日: 令和5年3月1日
    落札日: 令和5年4月1日
    建設工事の入札
    """
    # Extract relevant parts
    lines = [line.strip() for line in sample_text.strip().split('\n') if line.strip()]
    budget_line = next((l for l in lines if '予定価格' in l), None)
    contract_line = next((l for l in lines if '落札価格' in l), None)
    winner_line = next((l for l in lines if '落札者：' in l), None)  # Look for the full-width colon
    # Note: We don't extract the industry line separately as it's processed by the main function
    
    assert budget_line is not None
    assert contract_line is not None
    assert winner_line is not None
    
    # Test the main parsing function with all lines
    result = parse_award_pdf_text(sample_text)
    assert isinstance(result, dict)
    assert result["budget_amount"] == 12345678
    assert result["contract_amount"] == 11111111
    assert result["award_rate"] == 90.0  # 11111111 / 12345678 * 100 ≈ 90.0
    assert result["winner_name"] == "株式会社サンプル"
    assert result["category"] == "建設"  # example industry extraction
    assert result["announcement_date"] is not None
    assert result["award_date"] is not None

def test_parse_award_pdf_text_empty():
    """空テキスト入力時の動作テスト"""
    result = parse_award_pdf_text("")
    assert isinstance(result, dict)
    # All numeric fields should be 0 or None, strings empty
    assert result["budget_amount"] == 0
    assert result["contract_amount"] == 0
    assert result["award_rate"] is None
    assert result["winner_name"] == ""
    assert result["category"] == ""
    assert result["announcement_date"] is None
    assert result["award_date"] is None

def test_parse_award_pdf_text_invalid():
    """無効なテキスト入力時の例外処理テスト"""
    invalid_text = "このテキストはPDFではありません"
    result = parse_award_pdf_text(invalid_text)
    assert isinstance(result, dict)
    # On exception, should return empty dict (all values default)
    assert result["budget_amount"] == 0
    assert result["contract_amount"] == 0
    assert result["award_rate"] is None
    assert result["winner_name"] == ""
    assert result["category"] == ""
    assert result["announcement_date"] is None
    assert result["award_date"] is None

def test_parse_award_pdf_text_budget_zero():
    """予算金額がゼロの場合のfallback処理テスト"""
    sample_text = """
    入札公告番号: テスト
    予定価格 0円
    落札価格: 500,000円
    落札者：株式会社テスト
    落札日: 令和5年4月1日
    """
    # Extract relevant lines
    lines = [line.strip() for line in sample_text.strip().split('\n') if line.strip()]
    budget_line = next((l for l in lines if '予定価格' in l), None)
    contract_line = next((l for l in lines if '落札価格' in l), None)
    winner_line = next((l for l in lines if '落札者：' in l), None)
    
    assert budget_line is not None
    assert contract_line is not None
    assert winner_line is not None
    
    result = parse_award_pdf_text(sample_text)
    # budget_amount should be 0 (parse_budget_amount returns 0 for "0円")
    assert result["budget_amount"] == 0
    assert result["contract_amount"] == 500000
    # award_rate should be None because budget is zero
    assert result["award_rate"] is None
    assert result["winner_name"] == "株式会社テスト"

def test_parse_award_pdf_text_missing_fields():
    """必須フィールドが欠如しているケースのテスト"""
    sample_text = """
    入札公告番号: テスト
    予定価格 10,000,000円
    落札価格: 9,000,000円
    落札者：株式会社サンプル
    # 落札日・業者名が抜けている
    """
    # Extract relevant lines
    lines = [line.strip() for line in sample_text.strip().split('\n') if line.strip()]
    budget_line = next((l for l in lines if '予定価格' in l), None)
    contract_line = next((l for l in lines if '落札価格' in l), None)
    winner_line = next((l for l in lines if '落札者：' in l), None)
    
    assert budget_line is not None
    assert contract_line is not None
    assert winner_line is not None
    
    result = parse_award_pdf_text('\n'.join([budget_line, contract_line, winner_line]))
    assert result["budget_amount"] == 10000000
    assert result["contract_amount"] == 9000000
    # winner_name may be empty string if parsing fails
    assert result["winner_name"] == "株式会社サンプル"
    # category may be empty
    assert result["category"] == ""
    # dates may be None
    assert result["announcement_date"] is None
    assert result["award_date"] is None

# Mock the external parser functions to isolate the logic
@patch("crawler.parsers.award_pdf_parser.parse_budget_amount")
@patch("crawler.parsers.award_pdf_parser.parse_contract_amount")
@patch("crawler.parsers.award_pdf_parser.parse_winner_name")
@patch("crawler.parsers.award_pdf_parser.extract_industry_from_text")
@patch("crawler.parsers.award_pdf_parser.parse_award_date")
@patch("crawler.parsers.award_pdf_parser.parse_announcement_date")
def test_parse_award_pdf_text_mocked(
    mock_parse_announcement_date,
    mock_parse_award_date,
    mock_extract_industry,
    mock_parse_winner_name,
    mock_parse_contract,
    mock_parse_budget,
):
    # Mock return values
    mock_parse_budget.return_value = 1000000
    mock_parse_contract.return_value = 900000
    mock_parse_winner_name.return_value = "株式会社テスト"
    mock_extract_industry.return_value = "IT"
    mock_parse_award_date.return_value = "2024-04-01"
    mock_parse_announcement_date.return_value = "2024-03-01"

    sample_text = """
    予定価格 1,000,000円
    落札価格 900,000円
    落札者：株式会社テスト
    公告日: 2024-03-01
    落札日: 2024-04-01
    建設工事の入札
    """
    result = parse_award_pdf_text(sample_text)

    # Verify that the external functions were called with the cleaned text
    # The actual cleaning is internal, so we just check the result
    assert result["budget_amount"] == 1000000
    assert result["contract_amount"] == 900000
    assert result["award_rate"] == 90.0
    assert result["winner_name"] == "株式会社テスト"
    assert result["category"] == "IT"
    assert result["announcement_date"] == "2024-03-01"
    assert result["award_date"] == "2024-04-01"