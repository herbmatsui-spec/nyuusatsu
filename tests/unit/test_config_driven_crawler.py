import pytest
from datetime import date
from crawler.config_driven_crawler import ConfigDrivenCrawler

def test_parse_detail_no_fields():
    # Test fallback to raw text when no detail_fields are defined
    crawler = ConfigDrivenCrawler("/home/herbmatsui/nyuusatsu/config/sample_detail_fields.yaml")
    # Manually clear detail_fields to test fallback behavior
    crawler.config["detail_fields"] = {}
    html = "<div>Hello World</div>"
    result = crawler.parse_detail(html)
    # Should fallback to raw text extraction
    assert result == "Hello World"

def test_parse_detail_with_fields():
    # Test parsing with detail_fields
    crawler = ConfigDrivenCrawler("/home/herbmatsui/nyuusatsu/config/sample_detail_fields.yaml")
    html = """
    <div class="price">1,234,567円</div>
    <div class="date">2026.08.27</div>
    <div class="title">   平成元年   </div>
    """
    result = crawler.parse_detail(html)
    # Check that we get the expected fields
    assert "field1" in result  # price field
    assert "field2" in result  # date field
    assert "field3" in result  # title field
    # Check values - transform functions should be applied
    assert result["field1"] == 1234567  # normalize_amount removes non-digits and converts to int
    assert result["field2"] == date(2026, 8, 27)  # normalize_date converts to date object
    # field3 has multiple: true, so it returns a list
    assert isinstance(result["field3"], list)
    assert result["field3"][0] == "平成元年"  # normalize_whitespace should clean up spaces

def test_parse_detail_multiple_elements():
    # Test multiple element handling
    crawler = ConfigDrivenCrawler("/home/herbmatsui/nyuusatsu/config/sample_detail_fields.yaml")
    html = """
    <div class="price">1,234,567円</div>
    <div class="date">2026.08.27</div>
    <div class="title">First Title</div>
    <div class="title">Second Title</div>
    """
    result = crawler.parse_detail(html)
    # field3 has multiple: true, so it should be a list
    assert isinstance(result["field3"], list)
    assert len(result["field3"]) == 2
    assert "First Title" in result["field3"]
    assert "Second Title" in result["field3"]


def test_parse_detail_missing_selector():
    # Test behavior when selector doesn't match
    crawler = ConfigDrivenCrawler("/home/herbmatsui/nyuusatsu/config/sample_detail_fields.yaml")
    html = """
    <div class="price">1,234,567円</div>
    <div class="date">2026.08.27</div>
    <div>No matching selector for title</div>
    """
    result = crawler.parse_detail(html)
    # field1 should have value since selector ".price" matches
    assert result["field1"] == 1234567
    # field3 should be empty list since selector ".title" doesn't match and multiple: true
    assert result["field3"] == []

def test_parse_detail_required_field_missing():
    # Test that required fields raise an error when missing
    crawler = ConfigDrivenCrawler("/home/herbmatsui/nyuusatsu/config/sample_detail_fields.yaml")
    html = "<div>No matching selector for required field</div>"
    with pytest.raises(ValueError, match="Required field field1 not found in HTML"):
        crawler.parse_detail(html)
