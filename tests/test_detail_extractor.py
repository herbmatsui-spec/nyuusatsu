import pytest
from crawler.detail_extractor import BidDetailExtractor

@pytest.fixture
def extractor():
    return BidDetailExtractor()

def test_extract_budget_basic(extractor):
    """予算額の基本抽出テスト"""
    texts = [
        ("予算額：1,000,000円", "1,000,000円"),
        ("予定価格 500万円", "500万円"),
        ("見積額: 1.2億円", "1.2億円"),
        ("予算 100,000千円", "100,000千円"),
    ]
    for text, expected in texts:
        assert extractor.extract_budget(text) == expected

def test_extract_budget_max_value(extractor):
    """複数の金額がある場合に最大値を抽出するかテスト"""
    text = "予定価格は1,000,000円ですが、予算額は500万円です。"
    # 500万円 > 1,000,000円
    assert extractor.extract_budget(text) == "500万円"

def test_extract_deadline_formats(extractor):
    """締切日の様々なフォーマット抽出テスト"""
    texts = [
        ("締切日：2024年12月31日", "2024-12-31"),
        ("提出期限 2024/12/31", "2024-12-31"),
        ("入札期限 2024-12-31", "2024-12-31"),
        ("締切 R6.12.31", "2024-12-31"), # 令和6年 = 2024年
        ("期限 H31.4.30", "2019-04-30"), # 平成31年 = 2019年
    ]
    for text, expected in texts:
        assert extractor.extract_deadline(text) == expected

def test_extract_qualifications(extractor):
    """参加資格の抽出テスト"""
    text = "【参加資格】北海道内に本店を有する法人であること。また、過去3年間に同様の業務実績があること。"
    result = extractor.extract_qualifications(text)
    assert result is not None
    assert "北海道内に本店を有する法人" in result

def test_extract_announcement_date(extractor):
    """公告日の抽出テスト"""
    text = "公告日：令和6年7月10日"
    assert extractor.extract_announcement_date(text) == "2024-07-10"

def test_extract_from_html_fixture(extractor):
    """フィクスチャHTMLからの抽出テスト"""
    with open("tests/fixtures/detail_page_sample.html", "r", encoding="utf-8") as f:
        html = f.read()
    
    result = extractor.extract_from_html(html)
    
    assert result['budget'] == "15,000,000円"
    assert result['deadline'] == "2025-05-15"
    assert "北海道内に本店を有し" in result['qualifications']
