"""
Tests for Company Name Normalizer utilities.
"""

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

    @pytest.mark.parametrize("input_name,expected", [
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
        ("サンプル Ltd.", "株式会社サンプル"),
        ("サンプル Inc.", "株式会社サンプル"),
        ("サンプル Co., Ltd.", "株式会社サンプル"),
    ])
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
        assert normalize("(株)株式会社サンプル") == "株式会社サンプル"  # (株) が最初にマッチ
        assert normalize("株式会社(株)サンプル") == "株式会社サンプル"  # 株式会社 が最初にマッチ


class TestRemoveSuffix:
    """remove_suffix のテスト。"""

    @pytest.mark.parametrize("input_name,expected", [
        ("株式会社ABC", "ABC"),
        ("有限会社テスト", "テスト"),
        ("(株)サンプル", "サンプル"),
        ("㈱サンプル", "サンプル"),
        ("(有)テスト", "テスト"),
        ("(合)パートナー", "パートナー"),
        ("(株)株式会社ABC", "株式会社ABC"),
        ("株式会社(株)ABC", "ABC"),
        ("ABC株式会社", "ABC"),
        ("ABC有限会社", "ABC"),
        ("ABC合同会社", "ABC"),
        ("ABC合資会社", "ABC"),
        ("ABC合名会社", "ABC"),
        ("ABC公社", "ABC"),
        ("ABC公団", "ABC"),
        ("ABC Corp.", "ABC"),
        ("ABC Ltd.", "ABC"),
        ("ABC Inc.", "ABC"),
        ("ABC Co., Ltd.", "ABC"),
        ("ABC 合同会社", "ABC"),
        ("", ""),
        (None, ""),
    ])
    def test_remove_suffix(self, input_name, expected):
        assert remove_suffix(input_name) == expected

    def test_remove_suffix_empty(self):
        assert remove_suffix("") == ""

    def test_remove_suffix_none(self):
        assert remove_suffix(None) == ""


class TestExtractCorporateNumber:
    """extract_corporate_number のテスト。"""

    @pytest.mark.parametrize("input_text,expected", [
        ("法人番号: 1234567890123", "1234567890123"),
        ("法人番号 1234567890123", "1234567890123"),
        ("法人番号：1234567890123", "1234567890123"),
        ("1234567890123", "1234567890123"),
        ("法人番号: 123456789012", None),  # 12桁は無効
        ("法人番号: 12345678901234", None),  # 14桁は無効
        ("法人番号: abcdefghijklm", None),  # 数字以外は無効
        ("", None),
        (None, None),
        ("法人番号なし", None),
    ])
    def test_extract_corporate_number(self, input_text, expected):
        assert extract_corporate_number(input_text) == expected


class TestSimilarity:
    """similarity のテスト。"""

    @pytest.mark.parametrize("name1,name2,expected_min", [
        ("株式会社ABC", "株式会社ABC", 1.0),
        ("株式会社ABC", "㈱ABC", 0.8),
        ("株式会社ABC", "有限会社ABC", 0.5),
        ("株式会社ABC", "株式会社XYZ", 0.5),
        ("", "", 1.0),
        ("ABC", "", 0.0),
        (None, "ABC", 0.0),
        ("株式会社サンプル", "サンプル株式会社", 0.5),
    ])
    def test_similarity(self, name1, name2, expected_min):
        result = similarity(name1, name2)
        assert result >= expected_min
        assert 0.0 <= result <= 1.0


class TestFindSimilar:
    """find_similar のテスト。"""

    def test_find_similar_basic(self):
        candidates = ["株式会社ABC", "有限会社XYZ", "合同会社DEF"]
        result = find_similar("㈱ABC", candidates, threshold=0.7)
        assert len(result) > 0
        assert result[0][0] == "株式会社ABC"

    def test_find_similar_empty_candidates(self):
        result = find_similar("株式会社ABC", [], threshold=0.7)
        assert result == []

    def test_find_similar_no_match(self):
        candidates = ["株式会社XYZ", "有限会社DEF"]
        result = find_similar("株式会社ABC", candidates, threshold=0.9)
        assert result == []

    def test_find_similar_threshold(self):
        candidates = ["株式会社ABC", "株式会社ABD", "株式会社XYZ"]
        result = find_similar("株式会社ABC", candidates, threshold=0.8)
        assert len(result) >= 1
        assert result[0][0] == "株式会社ABC"


class TestDetectIndustry:
    """detect_industry のテスト。"""

    @pytest.mark.parametrize("company_name,expected_industry", [
        ("株式会社建設", "建設業"),
        ("株式会社建築", "建設業"),
        ("株式会社土木", "建設業"),
        ("株式会社電気", "電気工事業"),
        ("株式会社管工事", "管工事業"),
        ("株式会社造園", "造園業"),
        ("株式会社舗装", "舗装工事業"),
        ("株式会社塗装", "塗装工事業"),
        ("株式会社内装", "内装仕上工事業"),
        ("株式会社解体", "解体工事業"),
        ("株式会社測量", "測量業"),
        ("株式会社設計", "建築設計業"),
        ("株式会社コンサル", "建設コンサルタント業"),
        ("株式会社清掃", "清掃業"),
        ("株式会社警備", "警備業"),
        ("株式会社運送", "運送業"),
        ("株式会社倉庫", "倉庫業"),
        ("株式会社不動産", "不動産業"),
        ("株式会社ソフトウェア", "情報処理業"),
        ("株式会社システム", "情報処理業"),
        ("株式会社IT", "情報処理業"),
        ("株式会社Web", "情報処理業"),
        ("株式会社デザイン", "デザイン業"),
        ("株式会社広告", "広告業"),
        ("株式会社印刷", "印刷業"),
        ("株式会社出版", "出版業"),
        ("株式会社翻訳", "翻訳業"),
        ("株式会社通訳", "通訳業"),
        ("株式会社人材", "人材派遣業"),
        ("株式会社派遣", "人材派遣業"),
        ("株式会社紹介", "職業紹介業"),
        ("株式会社教育", "教育業"),
        ("株式会社学習", "学習塾業"),
        ("株式会社医療", "医療業"),
        ("株式会社介護", "介護業"),
        ("株式会社福祉", "福祉業"),
        ("株式会社薬局", "薬局業"),
        ("株式会社飲食", "飲食業"),
        ("株式会社レストラン", "飲食業"),
        ("株式会社カフェ", "飲食業"),
        ("株式会社ホテル", "宿泊業"),
        ("株式会社旅館", "宿泊業"),
        ("株式会社小売", "小売業"),
        ("株式会社卸売", "卸売業"),
        ("株式会社商社", "卸売業"),
        ("株式会社製造", "製造業"),
        ("株式会社食品", "食品製造業"),
        ("株式会社化学", "化学工業"),
        ("株式会社機械", "機械工業"),
        ("株式会社電子", "電子部品工業"),
        ("株式会社自動車", "自動車工業"),
        ("株式会社鉄鋼", "鉄鋼業"),
        ("株式会社非鉄", "非鉄金属工業"),
        ("株式会社金属", "金属製品工業"),
        ("株式会社繊維", "繊維工業"),
        ("株式会社紙", "パルプ・紙工業"),
        ("株式会社ゴム", "ゴム製品工業"),
        ("株式会社プラスチック", "プラスチック製品工業"),
        ("株式会社セラミック", "窯業・土石製品工業"),
        ("株式会社木材", "木材・木製品工業"),
        ("株式会社家具", "家具・装備品工業"),
        ("株式会社印刷", "印刷・同関連業"),
        ("株式会社皮革", "皮革・同製品工業"),
        ("株式会社その他", "その他の製造業"),
        ("株式会社サンプル", "その他"),
    ])
    def test_detect_industry(self, company_name, expected_industry):
        assert detect_industry(company_name) == expected_industry

    def test_detect_industry_empty(self):
        assert detect_industry("") == "その他"
        assert detect_industry(None) == "その他"
