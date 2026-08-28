import asyncio
import pytest
from crawler.generic_crawler import GenericCrawler
from crawler.models.crawl_result import CrawlResult

@pytest.mark.asyncio
async def test_crawl_site_recursive_logic():
    """
    GenericCrawler の再帰クロールロジックをテストする。
    実際のネットワーク通信を避けるため、_crawl_single_page をモック化する。
    """
    # 1. 準備
    crawler = GenericCrawler(max_depth=2)
    agency_name = "テスト自治体"
    target_url = "http://example.com/start"
    
    # 擬似的なページ構造を定義
    # depth 0: /start -> リンク [A, B]
    # depth 1: /A -> リンク [C]
    # depth 1: /B -> リンク [D, PDF_1]
    # depth 2: /C -> リンク []
    # depth 2: /D -> リンク [E] (深度制限により /E はクロールされないはず)
    
    mock_pages = {
        "http://example.com/start": [
            CrawlResult(url="http://example.com/A", title="Page A", agency_name=agency_name),
            CrawlResult(url="http://example.com/B", title="Page B", agency_name=agency_name),
        ],
        "http://example.com/A": [
            CrawlResult(url="http://example.com/C", title="Page C", agency_name=agency_name),
        ],
        "http://example.com/B": [
            CrawlResult(url="http://example.com/D", title="Page D", agency_name=agency_name),
            CrawlResult(url="http://example.com/PDF_1.pdf", title="PDF 1", agency_name=agency_name),
        ],
        "http://example.com/C": [],
        "http://example.com/D": [
            CrawlResult(url="http://example.com/E", title="Page E", agency_name=agency_name),
        ],
    }

    async def mock_crawl_single_page(page, url, agency, depth):
        # 正規化してキーを検索
        norm_url = url.split('#')[0].rstrip('/')
        results = mock_pages.get(norm_url, [])
        # _extract_links_from_page の挙動を模倣して depth をセット
        for r in results:
            r.depth = depth
        return results

    # メソッドを差し替える
    crawler._crawl_single_page = mock_crawl_single_page
    async def mock_init_browser(*args, **kwargs):
        return None, None, None
    
    async def mock_close(*args, **kwargs):
        pass

    crawler.init_browser = mock_init_browser
    crawler.close = mock_close

    # 2. 実行
    results = await crawler.crawl_site_recursive(target_url, agency_name)

    # 3. 検証
    result_urls = [r.url for r in results]
    
    # 期待される収集URL:
    # depth 0 から見つかった: A, B
    # depth 1 (A) から見つかった: C
    # depth 1 (B) から見つかった: D, PDF_1
    # depth 2 (C) から見つかった: なし
    # depth 2 (D) から見つかった: E
    # 合計: A, B, C, D, PDF_1, E
    
    assert "http://example.com/A" in result_urls
    assert "http://example.com/B" in result_urls
    assert "http://example.com/C" in result_urls
    assert "http://example.com/D" in result_urls
    assert "http://example.com/PDF_1.pdf" in result_urls
    assert "http://example.com/E" in result_urls
    
    # 訪問済みリストの確認
    assert "http://example.com/start" in crawler.visited_urls
    assert "http://example.com/A" in crawler.visited_urls
    assert "http://example.com/B" in crawler.visited_urls
    assert "http://example.com/C" in crawler.visited_urls
    assert "http://example.com/D" in crawler.visited_urls
    # E は depth 3 になるためクロール（訪問）されないはず
    assert "http://example.com/E" not in crawler.visited_urls

    print("Recursive crawl logic test passed!")

if __name__ == "__main__":
    asyncio.run(test_crawl_site_recursive_logic())
