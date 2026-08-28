import sys
import os

# プロジェクトルートを sys.path に追加
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest

@pytest.fixture
def sample_geps_html():
    """GEPS検索結果ページを模したHTML"""
    return """
    <html><body>
    <table>
      <tr>
        <td><a href="/docs/spec_001.pdf">○○業務委託に係る入札公告</a></td>
        <td>経済産業省</td>
        <td>2026年7月1日</td>
      </tr>
      <tr>
        <td><a href="/docs/spec_002.pdf">△△システム構築仕様書</a></td>
        <td>総務省</td>
        <td>2026/06/28</td>
      </tr>
      <tr>
        <td>ヘッダ行</td>
        <td>発注機関</td>
      </tr>
    </table>
    </body></html>
    """

@pytest.fixture
def sample_award_html():
    """落札結果ページを模したHTML"""
    return """
    <html><body>
    <table>
      <tr>
        <td>○○業務委託</td>
        <td>株式会社テスト</td>
        <td>5,000,000円</td>
        <td>2026年6月15日</td>
      </tr>
      <tr>
        <td>△△調達案件</td>
        <td>テスト商事</td>
        <td>12,300,000円</td>
        <td>2026年6月20日</td>
      </tr>
    </table>
    </body></html>
    """

@pytest.fixture
def empty_html():
    """空のHTMLページ"""
    return "<html><body></body></html>"

@pytest.fixture
def no_table_html():
    """テーブルが無いHTMLページ"""
    return "<html><body><p>テーブルなしのページです</p></body></html>"

@pytest.fixture
def sample_rss_xml():
    """RSS 2.0形式のXML"""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>入札情報</title>
        <item>
          <title>入札公告: サーバ調達</title>
          <link>https://example.gov.jp/bid/001.pdf</link>
          <pubDate>Mon, 01 Jul 2026 00:00:00 GMT</pubDate>
        </item>
        <item>
          <title>仕様書: ネットワーク構築</title>
          <link>https://example.gov.jp/bid/002.pdf</link>
          <pubDate>Tue, 02 Jul 2026 00:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """

@pytest.fixture
def sample_atom_xml():
    """Atom形式のXML"""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <title>調達情報</title>
      <entry>
        <title>入札案件A</title>
        <link href="https://example.gov.jp/atom/a.pdf"/>
        <published>2026-07-01T00:00:00Z</published>
      </entry>
      <entry>
        <title>入札案件B</title>
        <link href="https://example.gov.jp/atom/b.pdf"/>
        <updated>2026-07-03T12:00:00Z</updated>
      </entry>
    </feed>
    """

@pytest.fixture
def mock_playwright_page(mocker):
    """Playwright Page のモック"""
    page = mocker.AsyncMock()
    page.url = "https://www.geps.go.jp/search.html"
    page.content = mocker.AsyncMock(return_value="<html><body></body></html>")
    page.goto = mocker.AsyncMock()
    page.wait_for_selector = mocker.AsyncMock()
    page.query_selector = mocker.AsyncMock(return_value=None)
    page.set_default_timeout = mocker.MagicMock()
    page.locator = mocker.MagicMock()
    return page

@pytest.fixture
def mock_playwright_context(mocker, mock_playwright_page):
    """Playwright BrowserContext のモック"""
    context = mocker.AsyncMock()
    context.new_page = mocker.AsyncMock(return_value=mock_playwright_page)
    return context

@pytest.fixture
def mock_playwright_browser(mocker, mock_playwright_context):
    """Playwright Browser のモック"""
    browser = mocker.AsyncMock()
    browser.new_context = mocker.AsyncMock(return_value=mock_playwright_context)
    return browser
