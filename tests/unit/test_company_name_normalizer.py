"""
Tests for Company Name Normalizer utilities.
"""

import pytest

from crawler.utils.company_name_normalizer import (
    INDUSTRY_KEYWORDS,
    SUFFIX_MAP,
    detect_industry,
    extract_corporate_number,
    find_similar,
    normalize,
    remove_suffix,
    similarity,
)


class TestNormalize:
    """normalize のテスト。"""

    @pytest.mark.parametrize(
        "input_name,expected",
        [
            ("(株)サンプル", "株式会社サンプル"),
            ("(有)テスト", "有限会社テスト"),
            ("(合)パートナー", "合資会社パートナー"),
            ("㈱サンプル", "株式会社サンプル"),
            ("㈲テスト", "有限会社テスト"),
            ("㈶基金", "基金"),
            ("株式会社サンプル", "株式会社サンプル"),
            ("有限会社テスト", "有限会社テスト"),
            (" 株式会社ABC ", "株式会社ABC"),
            ("", ""),
            (None, ""),
            ("サンプル", "サンプル"),
            ("サンプル株式会社", "サンプル株式会社"),
            ("サンプル有限会社", "サンプル有限会社"),
            ("サンプル合資会社", "サンプル合資会社"),
            ("サンプル合同会社", "サンプル合同会社"),
            ("サンプル合名会社", "サンプル合名会社"),
            ("サンプル公社", "サンプル公社"),
            ("サンプル公団", "サンプル公団"),
            ("サンプル Corp.", "株式会社サンプル"),
            ("サンプル Corp", "株式会社サンプル"),
            ("サンプル Co., Ltd.", "株式会社サンプル"),
            ("サンプル Co., Ltd", "株式会社サンプル"),
            ("サンプル Ltd.", "株式会社サンプル"),
            ("サンプル Ltd", "株式会社サンプル"),
            ("サンプル INC.", "株式会社サンプル"),
            ("サンプル INC", "株式会社サンプル"),
        ],
    )
    def test_normalize_various_formats(self, input_name, expected):
        assert normalize(input_name) == expected

    def test_normalize_whitespace(self):
        """空白文字の処理。"""
        assert normalize("  株式会社ABC  ") == "株式会社ABC"
        assert normalize("株式会社  ABC") == "株式会社ABC"
        assert normalize("株式会社　ABC") == "株式会社ABC"  # 全角スペース

    def test_normalize_multiple_suffixes(self):
        """複数のサフィックスがある場合、最初のものを処理。"""
        # 最初のマッチのみが処理される
        assert normalize("(株)株式会社サンプル") == "株式会社サンプル"
        assert normalize("株式会社(株)サンプル") == "株式会社サンプル"

    def test_normalize_case_sensitive(self):
        """接頭辞置換は大文字小文字を区別する。"""
        assert normalize("サンプル CORP.") == "サンプル CORP."
        assert normalize("サンプル CORP") == "サンプル CORP"


class TestRemoveSuffix:
    """remove_suffix のテスト。"""

    @pytest.mark.parametrize(
        "input_name,expected",
        [
            ("株式会社サンプル建設", "サンプル建設"),
            ("有限会社テスト", "テスト"),
            ("合資会社パートナー", "パートナー"),
            ("合同会社カンパニー", "カンパニー"),
            ("合名会社アソシエイツ", "アソシエイツ"),
            ("基金機構", "機構"),
            ("公社コーポレーション", "コーポレーション"),
            ("公団サービス", "サービス"),
            ("サンプル", "サンプル"),  # サフィックスなし
            ("", ""),
            (None, ""),
            ("株式会社", ""),  # サフィックスのみ
            ("有限会社", ""),
            ("株式会社  サンプル", "サンプル"),  # 空白あり
            ("株式会社　サンプル", "サンプル"),  # 全角空白
            ("株式会社サンプル株式会社", "サンプル"),  # 重複サフィックス
        ],
    )
    def test_remove_suffix_various(self, input_name, expected):
        assert remove_suffix(input_name) == expected


class TestExtractCorporateNumber:
    """extract_corporate_number のテスト。"""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("法人番号1234567890123", "1234567890123"),
            ("1234567890123は法人番号", "1234567890123"),
            ("法人番号: 1234567890123", "1234567890123"),
            ("1234567890123", "1234567890123"),
            ("12345678901234", None),  # 14桁
            ("123456789012", None),  # 12桁
            ("12345678901A", None),  # 英字混在
            ("", None),
            (None, None),
            ("法人番号なし", None),
            ("1234-5678-9012", None),  # ハイフンあり
            ("1234 5678 9012", None),  # スペースあり
            ("9999999999999", "9999999999999"),
            ("0000000000000", "0000000000000"),
        ],
    )
    def test_extract_corporate_number_various(self, text, expected):
        assert extract_corporate_number(text) == expected

    def test_extract_corporate_number_multiple(self):
        """複数の13桁数字がある場合、最初のものを返す。"""
        text = "番号1: 1234567890123, 番号2: 9876543210987"
        assert extract_corporate_number(text) == "1234567890123"

    def test_extract_corporate_number_with_zenkaku_digits(self):
        """全角数字は対象外。"""
        assert extract_corporate_number("法人番号１２３４５６７８９０１２３") is None


class TestSimilarity:
    """similarity のテスト。"""

    @pytest.mark.parametrize(
        "a,b,expected",
        [
            ("株式会社ABC", "株式会社ABC", 1.0),
            ("株式会社ABC", "株式会社ABD", 0.92),
            ("ABC", "XYZ", 0.0),
            ("", "", 0.0),
            ("", "ABC", 0.0),
            ("ABC", "", 0.0),
            ("株式会社サンプル", "株式会社サンプル", 1.0),
            ("(株)サンプル", "株式会社サンプル", 1.0),
            ("有限会社テスト", "㈲テスト", 1.0),
            ("サンプル", "サンプ ル", 0.8),
        ],
    )
    def test_similarity_various(self, a, b, expected):
        assert similarity(a, b) == expected

    def test_similarity_normalizes_suffixes_before_comparison(self):
        """サフィックス正規化後の文字列で類似度を計算する。"""
        assert similarity("Corp.サンプル", "株式会社サンプル") == 1.0
        assert similarity("Ltd.テスト", "有限会社テスト") == 1.0


class TestFindSimilar:
    """find_similar のテスト。"""

    def test_find_similar_returns_best_match(self):
        """候補の中から最も類似度の高いものを返す。"""
        candidates = ["株式会社ABC", "株式会社XYZ", "有限会社テスト"]
        assert find_similar("株式会社ABC", candidates) == "株式会社ABC"

    def test_find_similar_returns_none_below_threshold(self):
        """閾値未満の場合は None を返す。"""
        candidates = ["株式会社ABC", "株式会社XYZ"]
        assert find_similar("サンプル", candidates, threshold=0.9) is None

    def test_find_similar_threshold_edge(self):
        """閾値ちょうどは対象。"""
        candidates = ["ABC", "XYZ"]
        assert find_similar("ABC", candidates, threshold=1.0) == "ABC"
        assert find_similar("ABC", candidates, threshold=1.01) is None

    def test_find_similar_empty_candidates(self):
        """候補が空の場合は None。"""
        assert find_similar("ABC", []) is None

    def test_find_similar_uses_normalized_similarity(self):
        """正規化済み文字列で比較する。"""
        candidates = ["(株)ABC", "有限会社テスト"]
        assert find_similar("株式会社ABC", candidates) == "(株)ABC"


class TestDetectIndustry:
    """detect_industry のテスト。"""

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("田中建設", "建設"),
            ("山本建築", "建設"),
            ("合同会社データセンター", "IT"),
            ("株式会社クラウド", "IT"),
            ("〇〇コンサルティング", "コンサル"),
            ("調査会社", "コンサル"),
            ("〇〇物品販売", "物品"),
            ("備品販売", "物品"),
            ("〇〇委託", "委託"),
            ("清掃サービス", "委託"),
            ("〇〇病院", "医療"),
            ("介護施設", "医療"),
            ("〇〇教育", "教育"),
            ("学校法人", "教育"),
        ],
    )
    def test_detect_industry_categories(self, name, expected):
        assert detect_industry(name) == expected

    def test_detect_industry_keyword_order(self):
        """キーワードの定義順（辞書の順序）で判定する。"""
        name = "建設コンサルティング"
        assert detect_industry(name) == "建設"

    def test_detect_industry_unknown(self):
        """一致するキーワードがない場合は None。"""
        assert detect_industry("未知の業種") is None

    def test_detect_industry_empty(self):
        """空文字列は None。"""
        assert detect_industry("") is None
        assert detect_industry(None) is None

    def test_industry_keywords_are_defined(self):
        """業種カテゴリのキーワード定義が存在すること。"""
        assert "建設" in INDUSTRY_KEYWORDS
        assert "IT" in INDUSTRY_KEYWORDS
        assert "コンサル" in INDUSTRY_KEYWORDS
        assert "物品" in INDUSTRY_KEYWORDS
        assert "委託" in INDUSTRY_KEYWORDS
        assert "医療" in INDUSTRY_KEYWORDS
        assert "教育" in INDUSTRY_KEYWORDS


class TestSUFFIX_MAP:
    """SUFFIX_MAP のテスト。"""

    def test_suffix_map_contains_expected_entries(self):
        """法人格サフィックスの置換マップが想定通りであること。"""
        assert SUFFIX_MAP["(株)"] == "株式会社"
        assert SUFFIX_MAP["(有)"] == "有限会社"
        assert SUFFIX_MAP["(合)"] == "合資会社"
        assert SUFFIX_MAP["㈱"] == "株式会社"
        assert SUFFIX_MAP["㈲"] == "有限会社"
        assert SUFFIX_MAP["㈶"] == "基金"
        assert SUFFIX_MAP[" Corp."] == "株式会社"
        assert SUFFIX_MAP[" Ltd."] == "株式会社"
        assert SUFFIX_MAP[" INC."] == "株式会社"

