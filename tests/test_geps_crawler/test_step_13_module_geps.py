from crawler.geps_crawler import GEPSCrawler as ModuleGEPSCrawler
import pytest

def test_module_geps_init():
    """モジュール版GEPSCrawlerの初期化"""
    crawler = ModuleGEPSCrawler()
    assert crawler.delay == 5.0
    assert crawler.timeout == 60000
    assert crawler.BASE_URL == "https://www.geps.go.jp"

def test_module_geps_custom_init():
    """カスタムパラメータでの初期化"""
    crawler = ModuleGEPSCrawler(delay=10.0, timeout=30000)
    assert crawler.delay == 10.0
    assert crawler.timeout == 30000

def test_module_geps_parse_search_results():
    """検索結果のHTMLパーステスト"""
    crawler = ModuleGEPSCrawler()
    html = """<html><body>
    <div class="search-result-item">
        <a class="title" href="/bid/001">テスト入札案件</a>
        <span class="organization">防衛省</span>
        <span class="budget">10,000,000円</span>
        <span class="deadline">2026年12月31日</span>
    </div>
    </body></html>"""
    results = crawler._parse_search_results(html)
    assert len(results) >= 1
    assert results[0]["title"] == "テスト入札案件"
    assert results[0]["organization"] == "防衛省"

def test_module_geps_parse_empty():
    """空HTMLの場合空リストを返すか"""
    crawler = ModuleGEPSCrawler()
    results = crawler._parse_search_results("")
    assert results == []

@pytest.mark.asyncio
async def test_module_geps_close():
    """closeメソッドがエラーなく実行されるか"""
    crawler = ModuleGEPSCrawler()
    await crawler.close()

@pytest.mark.asyncio
async def test_module_geps_fetch_pdf_links_mock(mocker):
    """PDFリンク抽出のモックテスト"""
    crawler = ModuleGEPSCrawler()
    mock_page = mocker.AsyncMock()
    mock_page.content = mocker.AsyncMock(return_value="""
    <html><body>
    <a href="/doc1.pdf">仕様書1</a>
    <a href="/doc2.pdf">仕様書2</a>
    <a href="/page.html">HTMLページ</a>
    </body></html>""")
    mock_page.goto = mocker.AsyncMock()

    mock_context = mocker.AsyncMock()
    mock_context.new_page = mocker.AsyncMock(return_value=mock_page)

    mock_browser = mocker.AsyncMock()
    mock_browser.new_context = mocker.AsyncMock(return_value=mock_context)

    mocker.patch.object(crawler, "init_browser", return_value=(mock_browser, mock_context, mock_page))
    mocker.patch.object(crawler, "close", return_value=None)

    links = await crawler.fetch_pdf_links("https://www.geps.go.jp/detail/001")
    assert len(links) == 2
    assert all(link.endswith(".pdf") for link in links)

@pytest.mark.asyncio
async def test_module_geps_fetch_pdf_links_empty(mocker):
    """PDFリンクがない場合空リストを返すか"""
    crawler = ModuleGEPSCrawler()
    mock_page = mocker.AsyncMock()
    mock_page.content = mocker.AsyncMock(return_value="<html><body>PDFなし</body></html>")
    mock_page.goto = mocker.AsyncMock()

    mock_context = mocker.AsyncMock()
    mock_context.new_page = mocker.AsyncMock(return_value=mock_page)

    mock_browser = mocker.AsyncMock()

    mocker.patch.object(crawler, "init_browser", return_value=(mock_browser, mock_context, mock_page))
    mocker.patch.object(crawler, "close", return_value=None)

    links = await crawler.fetch_pdf_links("https://www.geps.go.jp/detail/002")
    assert links == []
