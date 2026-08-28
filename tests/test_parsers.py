import pytest
from unittest.mock import MagicMock
from crawler.parsers.heuristic_parser import HeuristicParser
from crawler.parsers.rss_parser import RSSParser
from crawler.parsers.llm_parser import LLMParser
from crawler.models.crawl_result import CrawlResult

def test_heuristic_parser():
    parser = HeuristicParser()
    mock_html = """
    <html>
        <body>
            <div>
                <span>公示日: 2026年7月1日</span>
                <a href="/docs/shiyousho.pdf">業務委託仕様書</a>
            </div>
            <div>
                <a href="/docs/image.jpg">参考写真.jpg</a>
            </div>
            <div>
                <a href="/nyusatsu/annai.pdf">入札案内はこちら (令和8年7月5日告示)</a>
            </div>
            <div>
                <a href="https://example.com/other">無関係なリンク</a>
            </div>
        </body>
    </html>
    """
    results = parser.parse(mock_html, "https://example.com/index.html", "テスト自治体")
    
    assert len(results) == 2
    
    # 1つ目のリンクの検証 (shiyousho.pdf)
    assert results[0].title == "業務委託仕様書"
    assert results[0].url == "https://example.com/docs/shiyousho.pdf"
    assert results[0].publish_date == "2026-07-01"  # 親要素の日付が取得できているか

    # 2つ目のリンクの検証 (annai.pdf)
    assert results[1].title == "入札案内はこちら (令和8年7月5日告示)"
    assert results[1].url == "https://example.com/nyusatsu/annai.pdf"
    # 和暦(令和8年)は非対応なので不明か、もし正規表現でマッチしてしまった場合は対応フォーマットになる
    # 現状の date_regex は ((?:19|20)\d{2}) なので和暦は無視されて "不明" になるはず
    assert results[1].publish_date == "不明"

def test_rss_parser_rss2():
    parser = RSSParser()
    rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <title>入札新着情報</title>
            <link>https://example.com</link>
            <description>テストRSS</description>
            <item>
                <title>システム構築委託入札公告</title>
                <link>https://example.com/bids/101.pdf</link>
                <pubDate>Mon, 06 Jul 2026 12:00:00 GMT</pubDate>
            </item>
            <item>
                <title>物品調達に関するお知らせ</title>
                <link>/bids/102.html</link>
                <pubDate>Tue, 07 Jul 2026 15:30:00 GMT</pubDate>
            </item>
        </channel>
    </rss>
    """
    results = parser.parse(rss_xml, "https://example.com/rss", "テスト自治体")
    
    assert len(results) == 2
    assert results[0].title == "システム構築委託入札公告"
    assert results[0].url == "https://example.com/bids/101.pdf"
    assert results[0].publish_date == "2026-07-06"

    assert results[1].title == "物品調達に関するお知らせ"
    assert results[1].url == "https://example.com/bids/102.html"
    assert results[1].publish_date == "2026-07-07"

def test_rss_parser_atom():
    parser = RSSParser()
    atom_xml = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <title>入札情報Atom</title>
        <entry>
            <title>サーバー機器調達公募</title>
            <link href="https://example.com/atom/201.pdf"/>
            <published>2026-07-05T10:00:00Z</published>
        </entry>
        <entry>
            <title>ホームページ改修委託結果</title>
            <link href="/atom/202.html"/>
            <updated>2026-07-06T09:00:00+09:00</updated>
        </entry>
    </feed>
    """
    results = parser.parse(atom_xml, "https://example.com/atom", "テスト自治体")
    
    assert len(results) == 2
    assert results[0].title == "サーバー機器調達公募"
    assert results[0].url == "https://example.com/atom/201.pdf"
    assert results[0].publish_date == "2026-07-05"

    assert results[1].title == "ホームページ改修委託結果"
    assert results[1].url == "https://example.com/atom/202.html"
    assert results[1].publish_date == "2026-07-06"

@pytest.mark.asyncio
async def test_llm_parser_mocked(mocker):
    # Geminiクライアントのモックを作成
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"matched_links": [{"link_id": 0, "publish_date": "2026-07-07"}]}'
    
    # generate_content メソッドのモック化
    mock_client.models.generate_content = MagicMock(return_value=mock_response)
    
    parser = LLMParser(api_key="dummy_key")
    parser.client = mock_client
    
    mock_html = """
    <html>
        <body>
            <a href="/specs/nyusatsu.pdf">調達仕様書PDF</a>
            <a href="https://example.com/home">トップページ</a>
        </body>
    </html>
    """
    
    # parseは同期メソッドとして実装したので直接呼び出し
    results = parser.parse(mock_html, "https://example.com/index.html", "テスト自治体")
    
    assert len(results) == 1
    assert results[0].title == "調達仕様書PDF"
    assert results[0].url == "https://example.com/specs/nyusatsu.pdf"
    assert results[0].publish_date == "2026-07-07"
