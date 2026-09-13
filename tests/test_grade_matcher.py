"""
Tests for Grade Matcher (Phase2 Step16)
"""
import pytest
from config.qualification_grades import (
    can_apply,
    get_compatible_grades,
    normalize_grade,
    GRADE_COMPATIBILITY,
    GRADE_HIERARCHY,
)
from crawler.parsers.grade_parser import (
    extract_all_grades,
    extract_grade_from_text,
    extract_unified_qualification_number,
    normalize_grade_text,
)


class TestGradeCompatibility:
    def test_a_can_apply_b(self):
        assert can_apply("A", "B") is True

    def test_a_can_apply_c(self):
        assert can_apply("A", "C") is True

    def test_b_can_apply_c(self):
        assert can_apply("B", "C") is True

    def test_b_cannot_apply_a(self):
        assert can_apply("B", "A") is False

    def test_cannot_apply_d_for_a(self):
        assert can_apply("D", "A") is False

    def test_no_company_grade(self):
        assert can_apply(None, "A") is False

    def test_no_required_grade(self):
        assert can_apply("A", None) is True

    def test_empty_grade(self):
        assert can_apply("", "A") is False


class TestGradeHierarchy:
    def test_hierarchy_order(self):
        assert GRADE_HIERARCHY == ["A", "B", "C", "D"]

    def test_compatibility_map(self):
        assert "A" in GRADE_COMPATIBILITY
        assert "D" in GRADE_COMPATIBILITY
        assert "A" in GRADE_COMPATIBILITY["A"]
        assert "D" not in GRADE_COMPATIBILITY["B"]

    def test_get_compatible_grades(self):
        assert "A" in get_compatible_grades("A")
        assert "D" in get_compatible_grades("A")
        assert "A" not in get_compatible_grades("D")


class TestNormalizeGrade:
    def test_normalize_lowercase(self):
        assert normalize_grade("a") == "A"

    def test_normalize_fullwidth(self):
        assert normalize_grade("Ａ") == "A"

    def test_normalize_invalid(self):
        assert normalize_grade("Z") == ""


class TestGradeParser:
    def test_extract_grade_ab(self):
        assert extract_grade_from_text("全省庁統一資格 A") == "A"
        assert extract_grade_from_text("資格：B") == "B"

    def test_extract_grade_kanji(self):
        assert extract_grade_from_text("甲等級") == "A"
        assert extract_grade_from_text("乙級") == "B"

    def test_extract_grade_number(self):
        assert extract_grade_from_text("1級") == "1"
        assert extract_grade_from_text("2級") == "2"

    def test_extract_unified_number(self):
        assert extract_unified_qualification_number("番号1234567890123です") == "1234567890123"
        assert extract_unified_qualification_number("なし") is None

    def test_normalize_grade_text(self):
        assert normalize_grade_text("甲等級") == "A等級"
        assert normalize_grade_text("乙") == "B"

    def test_extract_all_grades(self):
        assert extract_all_grades("全省庁統一資格 A") == ["A"]
        assert extract_all_grades("甲等級") == ["A"]
        assert set(extract_all_grades("A級とB級が必要")) == {"A", "B"}
        assert set(extract_all_grades("甲等級 乙級 丙級")) == {"A", "B", "C"}
        assert extract_all_grades("") == []
        assert extract_all_grades(None) == []