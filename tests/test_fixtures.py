import pytest

def test_sample_html_fixture(sample_html_content):
    """サンプルHTMLフィクスチャが正しく提供されることをテスト"""
    assert "<html>" in sample_html_content
    assert "予算額：1,000,000円" in sample_html_content
    assert "締切日：2024年12月31日" in sample_html_content

def test_sample_json_fixture(sample_json_response):
    """サンプルJSONフィクスチャが正しく提供されることをテスト"""
    assert sample_json_response["success"] is True
    assert "data" in sample_json_response
    assert sample_json_response["data"]["bid_id"] == "BID-2024-001"

def test_mock_requests_get_fixture(mock_requests_get):
    """requests.getモックフィクスチャが正しく機能することをテスト"""
    import requests
    response = requests.get("http://example.com")
    assert response.status_code == 200
    assert response.text == "<html><body>Mock HTML</body></html>"
    mock_requests_get.assert_called_once_with("http://example.com")