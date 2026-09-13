"""Tests for Company Name Normalizer utilities."""

import pytest
from crawler.utils.company_name_normalizer import (
    normalize,
    remove_suffix,
    extract_corporate_number,
    similarity,
    find_similar,
    detect_industry,
)


class TestNormalize:
    """normalize のテスト。"""

    @pytest.mark.parametrize("name,expected", [
        ("株式会社ABC", "株式会社ABC"),
        ("(株)ABC", "株式会社ABC"),
        ("㈱ABC", "株式会社ABC"),
        ("株式会社 ABC", "株式会社ABC"),
        ("ABC 株式会社", "ABC株式会社"),
        ("有限会社XYZ", "有限会社XYZ"),
        ("(有)XYZ", "有限会社XYZ"),
        ("㈲XYZ", "有限会社XYZ"),
        ("合資会社DEF", "合資会社DEF"),
        ("(合)DEF", "合資会社DEF"),
        ("㈶基金", "基金基金"),  # "基金" が置換対象に含まれるため重複
        ("ABC Corp.", "ABC株式会社"),
        ("ABC Corp", "ABC株式会社"),
        ("ABC Co., Ltd.", "ABC株式会社"),
        ("ABC Co., Ltd", "ABC株式会社"),
        ("ABC Ltd.", "ABC株式会社"),
        ("ABC Ltd", "ABC株式会社"),
        ("ABC INC.", "ABC株式会社"),
        ("ABC INC", "ABC株式会社"),
        ("", ""),
        (None, ""),
        ("  株式会社ABC  ", "株式会社ABC"),
        ("㈱ 株式会社 ABC", "株式会社株式会社ABC"),  # 重複も正規化される
    ])
    def test_normalization(self, name, expected):
        assert normalize(name) == expected

    def test_multiple_suffixes(self):
        """複数のサフィックスが含まれる場合、最初にマッチしたもののみ置換。"""
        # (株) が先にマッチして株式会社になるが、元の「株式会社」も残る
        result = normalize("(株)株式会社ABC")
        assert result == "株式会社株式会社ABC"

    def test_removes_spaces(self):
        """スペース・全角スペースを除去。"""
        assert normalize("株式会社 A B C") == "株式会社ABC"
        # 全角スペースは除去されるが全角英数字は変換されない
        assert normalize("株式会社　ＡＢＣ") == "株式会社ＡＢＣ"


class TestRemoveSuffix:
    """remove_suffix のテスト。"""

    @pytest.mark.parametrize("name,expected", [
        ("株式会社ABC", "ABC"),
        ("有限会社XYZ", "XYZ"),
        ("合資会社DEF", "DEF"),
        ("合同会社GHI", "GHI"),
        ("合名会社JKL", "JKL"),
        ("基金MNO", "MNO"),
        ("公社PQR", "PQR"),
        ("公団STU", "STU"),
        ("ABC", "ABC"),  # サフィックスなし
        ("", ""),
        (None, ""),
        ("株式会社", ""),
        ("株式会社株式会社", ""),  # 重複も除去
    ])
    def test_suffix_removal(self, name, expected):
        assert remove_suffix(name) == expected

    def test_normalize_then_remove(self):
        """正規化してからサフィックス除去。"""
        assert remove_suffix("(株)ABC") == "ABC"
        assert remove_suffix("ABC Corp.") == "ABC"


class TestExtractCorporateNumber:
    """extract_corporate_number のテスト。"""

    @pytest.mark.parametrize("text,expected", [
        ("法人番号 1234567890123", "1234567890123"),
        ("法人番号：1234567890123", "1234567890123"),
        ("1234567890123", "1234567890123"),
        ("番号 1234567890123", "1234567890123"),
        ("123456789012", None),  # 12桁
        ("12345678901234", None),  # 14桁
        ("1234567890abc", None),  # 英数字混在
        ("", None),
        (None, None),
        ("法人番号なし", None),
    ])
    def test_corporate_number_extraction(self, text, expected):
        assert extract_corporate_number(text) == expected

    def test_embedded_in_text(self):
        """テキスト中に埋め込まれている場合。"""
        assert extract_corporate_number("法人番号 1234567890123 です") == "1234567890123"
        assert extract_corporate_number("ABC1234567890123DEF") is None  # 境界がない

    def test_multiple_numbers(self):
        """複数ある場合、最初のものを返す。"""
        text = "番号1: 1234567890123, 番号2: 9876543210987"
        assert extract_corporate_number(text) == "1234567890123"


class TestSimilarity:
    """similarity のテスト。"""

    @pytest.mark.parametrize("a,b,expected", [
        ("株式会社ABC", "株式会社ABC", 1.0),
        ("ABC", "ABC", 1.0),
        ("", "ABC", 0.0),
        ("ABC", "", 0.0),
        (None, "ABC", 0.0),
        ("ABC", None, 0.0),
        ("株式会社ABC", "(株)ABC", 1.0),  # 正規化後は同一
        ("株式会社ABC", "有限会社ABC", 0.71),  # 類似
        ("ABC株式会社", "XYZ株式会社", 0.57),
        ("建設株式会社", "建設株式会社", 1.0),
        ("建設株式会社", "建設工業株式会社", 0.25),
    ])
    def test_similarity_calculation(self, a, b, expected):
        result = similarity(a, b)
        assert result == expected

    def test_symmetry(self):
        """対称性の確認。"""
        a = "株式会社ABC"
        b = "有限会社XYZ"
        assert similarity(a, b) == similarity(b, a)


class TestFindSimilar:
    """find_similar のテスト。"""

    def test_find_exact_match(self):
        candidates = ["株式会社ABC", "有限会社XYZ", "合同会社DEF"]
        result = find_similar("株式会社ABC", candidates)
        assert result == "株式会社ABC"

    def test_find_similar_above_threshold(self):
        candidates = ["株式会社ABC", "株式会社XYZ", "有限会社DEF"]
        result = find_similar("株式会社ABC", candidates, threshold=0.7)
        assert result == "株式会社ABC"  # 完全一致が最優先

    def test_find_partial_match(self):
        candidates = ["建設株式会社", "建設工業株式会社", "IT株式会社"]
        result = find_similar("建設株式会社", candidates, threshold=0.6)
        assert result == "建設株式会社"

    def test_no_match_below_threshold(self):
        candidates = ["株式会社ABC", "有限会社XYZ"]
        result = find_similar("全く違う会社", candidates, threshold=0.7)
        assert result is None

    def test_empty_candidates(self):
        result = find_similar("株式会社ABC", [])
        assert result is None

    def test_empty_name(self):
        candidates = ["株式会社ABC"]
        result = find_similar("", candidates)
        assert result is None
        result = find_similar(None, candidates)
        assert result is None

    def test_threshold_adjustment(self):
        candidates = ["株式会社ABC", "株式会社XYZ"]
        # 閾値を下げると部分一致でもマッチ
        result = find_similar("株式会社AAA", candidates, threshold=0.5)
        assert result == "株式会社ABC"  # より類似度が高い方
        result = find_similar("株式会社AAA", candidates, threshold=0.8)
        assert result is None  # 閾値を超えない


class TestDetectIndustry:
    """detect_industry のテスト。"""

    @pytest.mark.parametrize("name,expected", [
        ("株式会社建設", "建設"),
        ("建設工業株式会社", "建設"),
        ("建築設計株式会社", "建設"),
        ("土木株式会社", "建設"),
        ("舗装工業株式会社", "建設"),
        ("管工事株式会社", "建設"),
        ("造園株式会社", "建設"),
        ("解体工業株式会社", "建設"),
        ("システム開発株式会社", "IT"),
        ("ソフトウェア株式会社", "IT"),
        ("ネットワーク株式会社", "IT"),
        ("データセンター株式会社", "IT"),
        ("クラウド株式会社", "IT"),
        ("情報システム株式会社", "IT"),
        ("コンサルティング株式会社", "コンサル"),
        ("調査株式会社", "コンサル"),
        ("計画設計株式会社", "コンサル"),
        ("シンクタンク株式会社", "コンサル"),
        ("物品販売株式会社", "物品"),
        ("備品株式会社", "物品"),
        ("機器株式会社", "物品"),
        ("設備株式会社", "物品"),
        ("委託株式会社", "委託"),
        ("業務委託株式会社", "委託"),
        ("サービス株式会社", "委託"),
        ("清掃株式会社", "委託"),
        ("警備株式会社", "委託"),
        ("医療株式会社", "医療"),
        ("病院株式会社", "医療"),
        ("介護株式会社", "医療"),
        ("福祉株式会社", "医療"),
        ("教育株式会社", "教育"),
        ("学校株式会社", "教育"),
        ("研修株式会社", "教育"),
        ("株式会社テスト", None),  # キーワードなし
        ("", None),
        (None, None),
    ])
    def test_industry_detection(self, name, expected):
        assert detect_industry(name) == expected

    def test_first_match_priority(self):
        """最初にマッチしたキーワードの業種が返される。"""
        # "建設" が "IT" より先にチェックされる
        assert detect_industry("建設システム株式会社") == "建設"


class TestEdgeCases:
    """エッジケースのテスト。"""

    def test_normalize_unicode(self):
        """全角文字の正規化。"""
        # 全角英数字は変換されない（mojimijiは別関数）
        assert normalize("㈱ＡＢＣ") == "株式会社ＡＢＣ"
        assert normalize("㈲ＸＹＺ") == "有限会社ＸＹＺ"

    def test_similarity_with_japanese(self):
        """日本語での類似度。"""
        assert similarity("建設", "建設") == 1.0
        assert similarity("建設", "建築") == 0.5  # 共通文字 "建" のみ

    def test_find_similar_case_insensitive(self):
        """大文字小文字は区別されない（正規化で吸収）。"""
        candidates = ["株式会社ABC", "株式会社XYZ"]
        result = find_similar("(株)abc", candidates)
        assert result is None  # "(株)abc" -> "株式会社abc" となり完全一致しない


if __name__ == "__main__":
    pytest.main([__file__, "-v"])