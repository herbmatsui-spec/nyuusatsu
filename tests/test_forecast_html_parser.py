"""
Tests for Forecast HTML Parser
"""
from crawler.parsers.forecast_html_parser import ForecastHtmlParser


def test_forecast_html_parser_init():
    """初期化のテスト"""
    parser = ForecastHtmlParser()
    assert parser.logger is not None


def test_extract_tables_simple():
    """単純なテーブルの抽出テスト"""
    parser = ForecastHtmlParser()
    html = """
    <table>
        <tr>
            <th>項目</th>
            <th>値</th>
        </tr>
        <tr>
            <td>予算額</td>
            <td>1,000,000円</td>
        </tr>
        <tr>
            <td>締切日</td>
            <td>2024年12月31日</td>
        </tr>
    </table>
    """
    result = parser.extract_tables(html, "http://example.com")
    assert len(result) == 2
    assert result[0] == {"項目": "予算額", "値": "1,000,000円", "_links": []}
    assert result[1] == {"項目": "締切日", "値": "2024年12月31日", "_links": []}


def test_extract_tables_no_table():
    """テーブルがない場合のテスト"""
    parser = ForecastHtmlParser()
    html = "<p>テーブルなし</p>"
    result = parser.extract_tables(html, "http://example.com")
    assert result == []


def test_extract_tables_mismatched_rows():
    """ヘッダーと行のセル数が不一致の場合はスキップされるテスト"""
    parser = ForecastHtmlParser()
    html = """
    <table>
        <tr>
            <th>A</th>
            <th>B</th>
        </tr>
        <tr>
            <td>1</td>
            <td>2</td>
            <td>3</td>
        </tr>
        <tr>
            <td>4</td>
            <td>5</td>
        </tr>
    </table>
    """
    result = parser.extract_tables(html, "http://example.com")
    # Only the second row matches the header length (2 cells)
    assert len(result) == 1
    assert result[0] == {"A": "4", "B": "5", "_links": []}


def test_extract_tables_with_links():
    """リンクを含むテーブルの抽出テスト"""
    parser = ForecastHtmlParser()
    html = """
    <table>
        <tr>
            <th>名前</th>
            <th>リンク</th>
        </tr>
        <tr>
            <td>サンプル</td>
            <td><a href="/detail.html">詳細</a></td>
        </tr>
    </table>
    """
    result = parser.extract_tables(html, "http://example.com/path/")
    assert len(result) == 1
    assert result[0]["名前"] == "サンプル"
    assert result[0]["リンク"] == "詳細"
    assert result[0]["_links"] == ["http://example.com/detail.html"]


def test_extract_links():
    """リンク抽出のテスト"""
    parser = ForecastHtmlParser()
    html = """
    <a href="/page1.html">ページ1</a>
    <a href="http://other.com/page2.html">ページ2</a>
    """
    result = parser.extract_links(html, "http://example.com/base/")
    assert len(result) == 2
    assert result[0] == {"url": "http://example.com/page1.html", "text": "ページ1"}
    assert result[1] == {"url": "http://other.com/page2.html", "text": "ページ2"}


def test_parse():
    """parseメソッドはextract_tablesを呼び出すことをテスト"""
    parser = ForecastHtmlParser()
    html = "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>"
    # We'll monkey-patch extract_tables to verify it's called
    original_extract_tables = parser.extract_tables
    called = []
    def mock_extract_tables(html, base_url):
        called.append((html, base_url))
        return [{"result": "mocked"}]
    parser.extract_tables = mock_extract_tables
    try:
        result = parser.parse(html, "http://example.com")
        assert len(called) == 1
        assert called[0] == (html, "http://example.com")
        assert result == [{"result": "mocked"}]
    finally:
        parser.extract_tables = original_extract_tables


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])