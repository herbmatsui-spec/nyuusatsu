"""
Tests for Field Normalizer
"""
import pytest
from crawler.parsers.field_normalizer import (
    normalize_amount,
    normalize_date,
    normalize_whitespace,
    normalize_fullwidth_to_halfwidth,
    TRANSFORM_MAP
)
from datetime import date

# Check if mojimiji is available
try:
    import mojimiji
    MOJIMJI_AVAILABLE = True
except ImportError:
    MOJIMJI_AVAILABLE = False


def test_normalize_amount():
    """金額正規化のテスト"""
    # 通常のケース
    assert normalize_amount("12,345,678円") == 12345678
    assert normalize_amount("予定価格 12,345,678円") == 12345678
    assert normalize_amount("12 345 678") == 12345678
    assert normalize_amount("¥12,345,678") == 12345678
    assert normalize_amount("￥12,345,678") == 12345678
    assert normalize_amount("12345678") == 12345678
    
    # ゼロのケース
    assert normalize_amount("0円") == 0
    assert normalize_amount("ゼロ") == 0
    assert normalize_amount("") == 0
    
    # 負の数（マイナス符号は削除される）
    assert normalize_amount("-123円") == 123
    
    # 小数点以下は切り捨て
    assert normalize_amount("1234.56円") == 123456


def test_normalize_date():
    """日付正規化のテスト"""
    # 西暦形式
    assert normalize_date("2024.04.01") == date(2024, 4, 1)
    assert normalize_date("2024/04/01") == date(2024, 4, 1)
    assert normalize_date("2024-04-01") == date(2024, 4, 1)
    assert normalize_date("20240401") == date(2024, 4, 1)
    
    # ゼロパディング
    assert normalize_date("2024.1.1") == date(2024, 1, 1)
    assert normalize_date("2024/1/1") == date(2024, 1, 1)
    assert normalize_date("2024-1-1") == date(2024, 1, 1)
    assert normalize_date("2024111") == date(2024, 11, 1)
    
    # 無効な日付
    assert normalize_date("2024.13.01") is None  # 無効月
    assert normalize_date("2024.04.31") is None  # 無効日
    assert normalize_date("2023/02/29") is None  # 閏年ではない（2023は閏年ではない）
    assert normalize_date("不正な日付") is None
    assert normalize_date("") is None
    assert normalize_date("   ") is None


def test_normalize_whitespace():
    """空白正規化のテスト"""
    # 通常のケース
    assert normalize_whitespace("  hello  world  ") == "hello world"
    assert normalize_whitespace("hello\t\tworld") == "hello world"
    assert normalize_whitespace("hello\n\nworld") == "hello world"
    assert normalize_whitespace("  \t  \n  ") == ""
    
    # 日本語のケース
    assert normalize_whitespace("  こんにちは  世界  ") == "こんにちは 世界"
    assert normalize_whitespace("こんにちは\t\t世界") == "こんにちは 世界"
    
    # 空文字列
    assert normalize_whitespace("") == ""
    assert normalize_whitespace("   ") == ""


def test_normalize_fullwidth_to_halfwidth():
    """全角半角正規化のテスト"""
    if not MOJIMJI_AVAILABLE:
        pytest.skip("mojimiji library not available")
    
    # 数字の全角→半角
    assert normalize_fullwidth_to_halfwidth("１２３４５６７８９０") == "1234567890"
    
    # アルファベットの全角→半角
    assert normalize_fullwidth_to_halfwidth("ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ") == "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    assert normalize_fullwidth_to_halfwidth("ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ") == "abcdefghijklmnopqrstuvwxyz"
    
    # 記号の全角→半角
    assert normalize_fullwidth_to_halfwidth("！＃＄％＆’（）＊＋，－．／：；＜＞？＠［＼］＾＿｀｛｜｝～") == "!#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"
    
    # 日本語は変換されない（ひらがな・カタカナ・漢字）
    assert normalize_fullwidth_to_halfwidth("こんにちは") == "こんにちは"
    assert normalize_fullwidth_to_halfwidth("コンニチワ") == "コンニチワ"
    assert normalize_fullwidth_to_halfwidth("今日") == "今日"
    
    # 混合文字列
    assert normalize_fullwidth_to_halfwidth("Ｈｅｌｌｏ　Ｗｏｒｌｄ　１２３") == "Hello World 123"
    
    # 空文字列
    assert normalize_fullwidth_to_halfwidth("") == ""


def test_transform_map():
    """TRANSFORM_MAPのテスト"""
    # マップにすべての関数が含まれていることを確認
    assert "normalize_amount" in TRANSFORM_MAP
    assert "normalize_date" in TRANSFORM_MAP
    assert "normalize_whitespace" in TRANSFORM_MAP
    assert "normalize_fullwidth_to_halfwidth" in TRANSFORM_MAP
    
    # 各関数が正しくマップされていることを確認
    assert TRANSFORM_MAP["normalize_amount"] == normalize_amount
    assert TRANSFORM_MAP["normalize_date"] == normalize_date
    assert TRANSFORM_MAP["normalize_whitespace"] == normalize_whitespace
    assert TRANSFORM_MAP["normalize_fullwidth_to_halfwidth"] == normalize_fullwidth_to_halfwidth
    
    # 関数が実際に呼び出せることを確認
    assert TRANSFORM_MAP["normalize_amount"]("123円") == 123
    assert TRANSFORM_MAP["normalize_date"]("2024.04.01") == date(2024, 4, 1)
    assert TRANSFORM_MAP["normalize_whitespace"]("  a  b  ") == "a b"
    
    # normalize_fullwidth_to_halfwidthはmojimijiが利用可能な場合のみテスト
    if MOJIMJI_AVAILABLE:
        assert TRANSFORM_MAP["normalize_fullwidth_to_halfwidth"]("ＡＢＣ") == "ABC"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])