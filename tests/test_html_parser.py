"""
Tests for HTML Parser
"""
from crawler.parsers.html_parser import HtmlParser


def test_html_parser_init_default():
    """デフォルトセレクタで初期化されることをテスト"""
    parser = HtmlParser()
    assert parser.selectors == {
        "title": "h1.title, h1",
        "organization": "div.org, span.org",
        "budget": "span.budget, div.budget",
        "deadline": "span.deadline, div.deadline",
        "description": "div.description, article",
    }


def test_html_parser_init_custom():
    """カスタムセレクタで初期化されることをテスト"""
    custom_selectors = {
        "title": "h2",
        "price": ".price"
    }
    parser = HtmlParser(selectors=custom_selectors)
    assert parser.selectors == custom_selectors


def test_select_text():
    """_select_textメソッドの動作をテスト"""
    from bs4 import BeautifulSoup
    parser = HtmlParser()
    
    html = "<h1>Hello World</h1><p>Some text</p>"
    soup = BeautifulSoup(html, "html.parser")
    
    # 既存のセレクタ
    assert parser._select_text(soup, "h1") == "Hello World"
    assert parser._select_text(soup, "p") == "Some text"
    # 存在しないセレクタ
    assert parser._select_text(soup, "div") == ""


def test_extract_fields():
    """extract_fieldsメソッドの動作をテスト"""
    parser = HtmlParser()
    
    html = """
    <html>
        <body>
            <h1 class="title">サンプル入札</h1>
            <div class="org">建設会社</div>
            <span class="budget">1,000,000円</span>
            <div class="deadline">2024年12月31日</div>
            <article class="description">これはサンプルの説明文です。</article>
        </body>
    </html>
    """
    
    result = parser.extract_fields(html)
    
    assert result["title"] == "サンプル入札"
    assert result["organization"] == "建設会社"
    assert result["budget"] == "1,000,000円"
    assert result["deadline"] == "2024年12月31日"
    assert result["description"] == "これはサンプルの説明文です。"


def test_extract_fields_missing():
    """要素が存在しない場合のextract_fieldsの動作をテスト"""
    parser = HtmlParser()
    
    html = """
    <html>
        <body>
            <h1 class="title">サンプル入札</h1>
            <!-- 組織名, 予算, 締切日, 説明が欠如 -->
        </body>
    </html>
    """
    
    result = parser.extract_fields(html)
    
    assert result["title"] == "サンプル入札"
    assert result["organization"] == ""
    assert result["budget"] == ""
    assert result["deadline"] == ""
    assert result["description"] == ""


def test_extract_fields_empty_input():
    """空文字列入力の場合のextract_fieldsの動作をテスト"""
    parser = HtmlParser()
    result = parser.extract_fields("")
    # すべてのフィールドが空文字列になることを期待
    assert all(value == "" for value in result.values())
    assert set(result.keys()) == set(parser.selectors.keys())


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])