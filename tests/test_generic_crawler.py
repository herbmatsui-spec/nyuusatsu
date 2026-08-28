import pytest
from crawler.generic_award_crawler import GenericAwardCrawler

# テスト用のモックHTML
MOCK_LIST_HTML = """
<html>
    <body>
        <table id="award-table">
            <tr>
                <td><a href="/detail/1">案件A</a></td>
                <td>2026-01-01</td>
            </tr>
            <tr>
                <td><a href="/detail/2">案件B</a></td>
                <td>2026-01-02</td>
            </tr>
            <tr>
                <td><a href="https://example.com/detail/3">案件C (絶対パス)</a></td>
                <td>2026-01-03</td>
            </tr>
            <tr>
                <td>リンクなしの行</td>
                <td>2026-01-04</td>
            </tr>
        </table>
    </body>
</html>
"""

MOCK_DETAIL_HTML = """
<html>
    <body>
        <div class="award-detail">
            <span class="title">案件Aの落札結果</span>
            <span class="winner">株式会社サンプル商事</span>
            <span class="amount">1,234,567円</span>
            <span class="date">2026-01-01</span>
        </div>
    </body>
</html>
"""

MOCK_DETAIL_HTML_EMPTY = """
<html>
    <body>
        <div class="award-detail">
            <span class="title">案件Bの落札結果</span>
            <span class="winner"></span>
            <span class="amount">0円</span>
        </div>
    </body>
</html>
"""

def test_extract_award_links():
    # セットアップ
    agency_key = "test_agency"
    list_selector = "#award-table tr td a" # リンク要素を直接指定する場合
    # 実際には <tr> を指定して内部で <a> を探す実装になっているため、それに合わせる
    list_selector = "#award-table tr" 
    detail_selectors = {} # links抽出には不要
    
    crawler = GenericAwardCrawler(agency_key, list_selector, detail_selectors)
    base_url = "https://test.example.jp"
    
    links = crawler.extract_award_links(MOCK_LIST_HTML, base_url)
    
    # 検証
    assert len(links) == 3
    assert links[0]["title"] == "案件A"
    assert links[0]["url"] == "https://test.example.jp/detail/1"
    assert links[1]["title"] == "案件B"
    assert links[1]["url"] == "https://test.example.jp/detail/2" # typo fix: links[1]["url"]
    assert links[2]["title"] == "案件C (絶対パス)"
    assert links[2]["url"] == "https://example.com/detail/3"

def test_extract_award_links_fixed():
    # 再テスト（タイポ修正後）
    agency_key = "test_agency"
    list_selector = "#award-table tr" 
    detail_selectors = {}
    crawler = GenericAwardCrawler(agency_key, list_selector, detail_selectors)
    base_url = "https://test.example.jp"
    links = crawler.extract_award_links(MOCK_LIST_HTML, base_url)
    assert links[1]["url"] == "https://test.example.jp/detail/2"

def test_parse_award_detail_success():
    # セットアップ
    agency_key = "test_agency"
    list_selector = ""
    detail_selectors = {
        "title": ".title",
        "winner_name": ".winner",
        "award_amount": ".amount",
        "award_date": ".date"
    }
    
    crawler = GenericAwardCrawler(agency_key, list_selector, detail_selectors)
    
    result = crawler.parse_award_detail(MOCK_DETAIL_HTML)
    
    # 検証
    assert result is not None
    assert result["title"] == "案件Aの落札結果"
    assert result["winner_name"] == "株式会社サンプル商事"
    assert result["award_amount"] == 1234567
    assert result["award_date"] == "2026-01-01"

def test_parse_award_detail_missing_winner():
    # 必須項目 (winner_name) がない場合は None を返すはず
    agency_key = "test_agency"
    list_selector = ""
    detail_selectors = {
        "title": ".title",
        "winner_name": ".winner",
        "award_amount": ".amount",
    }
    
    crawler = GenericAwardCrawler(agency_key, list_selector, detail_selectors)
    
    # winnerの中身が空（stripして空）の場合の挙動を確認
    # 現在の実装は get_text(strip=True) して、その結果が None かどうかではなく
    # result.get("winner_name") が存在するか（ただし値が空文字でもTrue）
    # 実装を再確認： if not result.get("winner_name"):
    # 空文字 "" は False と判定されるため、Noneを返す。
    
    result = crawler.parse_award_detail(MOCK_DETAIL_HTML_EMPTY)
    assert result is None

def test_parse_award_detail_partial_missing():
    # 一部のセレクタが見つからないが winner_name はある場合
    agency_key = "test_agency"
    list_selector = ""
    detail_selectors = {
        "title": ".non-existent",
        "winner_name": ".winner",
        "award_amount": ".amount",
    }
    
    crawler = GenericAwardCrawler(agency_key, list_selector, detail_selectors)
    result = crawler.parse_award_detail(MOCK_DETAIL_HTML)
    
    assert result is not None
    assert result["title"] is None
    assert result["winner_name"] == "株式会社サンプル商事"
    assert result["award_amount"] == 1234567
