"""Tests for Grade Parser utilities."""

import pytest
from crawler.parsers.grade_parser import (
    extract_grade_from_text,
    extract_unified_qualification_number,
    extract_all_grades,
    normalize_grade_text,
)


class TestExtractGradeFromText:
    """extract_grade_from_text のテスト。"""

    @pytest.mark.parametrize("text,expected", [
        ("全省庁統一資格 A", "A"),
        ("全省庁統一資格 B", "B"),
        ("全省庁統一資格 C", "C"),
        ("全省庁統一資格 D", "D"),
        ("資格: A", "A"),
        ("資格：B", "B"),
        ("等級 C", "C"),
        ("ランク D", "D"),
        ("甲等級", "A"),
        ("乙等級", "B"),
        ("丙等級", "C"),
        ("丁等級", "D"),
        ("甲", "A"),
        ("乙", "B"),
        ("丙", "C"),
        ("丁", "D"),
        ("A級", "A"),
        ("B級", "B"),
        ("C級", "C"),
        ("D級", "D"),
        ("A-級", "A"),
        ("B–級", "B"),  # 全角ダッシュ
        ("  A  級  ", "A"),
        ("資格 A 級", "A"),
        ("", None),
        (None, None),
        ("資格なし", None),
        ("等級なし", None),
        ("E級", None),  # 非対象
        ("Z級", None),
    ])
    def test_grade_extraction(self, text, expected):
        assert extract_grade_from_text(text) == expected

    def test_fullwidth_variants(self):
        """全角英数字のバリアント。"""
        assert extract_grade_from_text("Ａ") == "A"
        assert extract_grade_from_text("Ｂ") == "B"
        assert extract_grade_from_text("Ｃ") == "C"
        assert extract_grade_from_text("Ｄ") == "D"

    def test_lowercase(self):
        """小文字の処理。"""
        assert extract_grade_from_text("a") == "A"
        assert extract_grade_from_text("b") == "B"
        assert extract_grade_from_text("c") == "C"
        assert extract_grade_from_text("d") == "D"


class TestExtractUnifiedQualificationNumber:
    """extract_unified_qualification_number のテスト。"""

    @pytest.mark.parametrize("text,expected", [
        ("全省庁統一資格番号 1234567890123", "1234567890123"),
        ("資格番号：1234567890123", "1234567890123"),
        ("番号 1234567890123", "1234567890123"),
        ("1234567890123", "1234567890123"),
        ("123456789012", None),  # 12桁
        ("12345678901234", None),  # 14桁
        ("1234567890abc", None),  # 英数字混在
        ("", None),
        (None, None),
        ("資格番号なし", None),
        ("9999999999999", "9999999999999"),
    ])
    def test_number_extraction(self, text, expected):
        assert extract_unified_qualification_number(text) == expected

    def test_multiple_numbers(self):
        """複数の13桁数字がある場合、最初のものを返す。"""
        text = "番号1: 1234567890123, 番号2: 9876543210987"
        assert extract_unified_qualification_number(text) == "1234567890123"

    def test_embedded_in_text(self):
        """テキスト中に埋め込まれている場合。"""
        assert extract_unified_qualification_number("ABC1234567890123DEF") is None  # 境界がない
        assert extract_unified_qualification_number("番号 1234567890123 です") == "1234567890123"


class TestExtractAllGrades:
    """extract_all_grades のテスト。"""

    def test_single_grade(self):
        # extract_grade_from_text は最初に見つかった1つしか返さない
        assert extract_all_grades("資格 A") == ["A"]

    def test_multiple_grades(self):
        # 現在の実装では最初の等級のみ抽出される
        result = extract_all_grades("A級 B級 C級")
        assert result == ["A"]  # 最初の "A" のみ

    def test_duplicate_grades(self):
        result = extract_all_grades("A級 A等級")
        assert result == ["A"]

    def test_kanji_grades(self):
        result = extract_all_grades("甲 乙 丙")
        assert result == ["A"]  # 最初の "甲" のみ

    def test_mixed_formats(self):
        result = extract_all_grades("A級 乙等級 C")
        assert result == ["A"]  # 最初の "A" のみ

    def test_no_grades(self):
        assert extract_all_grades("資格なし") == []
        assert extract_all_grades("") == []
        assert extract_all_grades(None) == []

    def test_case_insensitive(self):
        result = extract_all_grades("a b c d")
        assert result == ["A"]  # 最初の "a" のみ


class TestNormalizeGradeText:
    """normalize_grade_text のテスト。"""

    @pytest.mark.parametrize("text,expected", [
        ("甲", "A"),
        ("乙", "B"),
        ("丙", "C"),
        ("丁", "D"),
        ("甲等級", "A等級"),
        ("乙等級", "B等級"),
        ("丙等級", "C等級"),
        ("丁等級", "D等級"),
        ("甲乙丙丁", "ABCD"),
        ("1級", "A級"),
        ("2級", "B級"),
        ("3級", "C級"),
        ("4級", "D級"),
        ("A", "A"),
        ("B", "B"),
        ("C", "C"),
        ("D", "D"),
        ("", ""),
        ("等級なし", "等級なし"),
    ])
    def test_normalization(self, text, expected):
        assert normalize_grade_text(text) == expected

    def test_preserves_non_grade_text(self):
        """等級以外のテキストは保持される。"""
        assert normalize_grade_text("全省庁統一資格 甲等級") == "全省庁統一資格 A等級"
        assert normalize_grade_text("建設業 乙") == "建設業 B"
        assert normalize_grade_text("IT 丙 設計") == "IT C 設計"


class TestEdgeCases:
    """エッジケースのテスト。"""

    def test_extract_grade_with_special_chars(self):
        """特殊文字を含むテキスト。"""
        assert extract_grade_from_text("A（等級）") == "A"
        assert extract_grade_from_text("等級[A]") == "A"
        assert extract_grade_from_text("等級（A）") == "A"

    def test_extract_number_with_dashes(self):
        """ダッシュを含む番号。"""
        assert extract_unified_qualification_number("1234-5678-9012") is None
        assert extract_unified_qualification_number("1234 5678 9012") is None

    def test_normalize_empty_and_none(self):
        """空文字とNoneの処理。"""
        assert normalize_grade_text("") == ""
        assert normalize_grade_text(None) == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])