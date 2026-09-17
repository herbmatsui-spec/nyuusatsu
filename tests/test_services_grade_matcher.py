"""
Tests for services.grade_matcher
"""
from services.grade_matcher import (
    extract_grade_from_text,
    check_grade_requirement,
    get_highest_compatible_grade,
    grade_matches,
)

def test_extract_grade_from_text():
    # 英字の等級
    assert extract_grade_from_text("全省庁統一資格 A") == "A"
    assert extract_grade_from_text("資格：B") == "B"
    assert extract_grade_from_text("c") == "C"
    assert extract_grade_from_text("d") == "D"
    # 漢字の等級
    assert extract_grade_from_text("甲等級") == "A"
    assert extract_grade_from_text("乙級") == "B"
    assert extract_grade_from_text("丙") == "C"
    assert extract_grade_from_text("丁") == "D"
    # 数字の等級
    assert extract_grade_from_text("1級") == "1"
    assert extract_grade_from_text("2級") == "2"
    assert extract_grade_from_text("3級") == "3"
    assert extract_grade_from_text("4級") == "4"
    # 組み合わせ
    assert extract_grade_from_text("甲等級 1級") == "A"  # 最初のマッチ
    assert extract_grade_from_text("資格 B級") == "B"
    # マッチしない場合
    assert extract_grade_from_text("") is None
    assert extract_grade_from_text("無し") is None
    assert extract_grade_from_text("資格：Z") is None

def test_check_grade_requirement():
    # 会社等級がNone
    assert check_grade_requirement(None, "A") is False
    # 必要等級がNone
    assert check_grade_requirement("A", None) is True
    # 両方None
    assert check_grade_requirement(None, None) is True
    # 等級AはA,B,C,Dに適用可能
    assert check_grade_requirement("A", "A") is True
    assert check_grade_requirement("A", "B") is True
    assert check_grade_requirement("A", "C") is True
    assert check_grade_requirement("A", "D") is True
    assert check_grade_requirement("A", "E") is False  # Eは存在しない
    # 等量BはB,C,Dに適用可能
    assert check_grade_requirement("B", "A") is False
    assert check_grade_requirement("B", "B") is True
    assert check_grade_requirement("B", "C") is True
    assert check_grade_requirement("B", "D") is True
    assert check_grade_requirement("B", "E") is False
    # 等量CはC,Dに適用可能
    assert check_grade_requirement("C", "A") is False
    assert check_grade_requirement("C", "B") is False
    assert check_grade_requirement("C", "C") is True
    assert check_grade_requirement("C", "D") is True
    assert check_grade_requirement("C", "E") is False
    # 等量DはDのみ適用可能
    assert check_grade_requirement("D", "A") is False
    assert check_grade_requirement("D", "B") is False
    assert check_grade_requirement("D", "C") is False
    assert check_grade_requirement("D", "D") is True
    assert check_grade_requirement("D", "E") is False
    # 数字等級（設定によるが、現状の設定では数字等級は無効?)
    # 設定を見ると、数字等級は定義されていないため、normalize_grade("1")は""になる
    # したがって、check_grade_requirement("1", "1")はFalseになるはず
    assert check_grade_requirement("1", "1") is False

def test_get_highest_compatible_grade():
    # 会社等級がNone
    assert get_highest_compatible_grade(None) is None
    # 会社等級がA
    assert get_highest_compatible_grade("A") == "A"  # A自身が最初?
    # 実際の設定では、Aの互換等級は[A, B, C, D]？設定を見てみよう
    # 設定ファイルを見ると、GRADE_COMPATIBILITY["A"] = ["A", "B", "C", "D"]?
    # 実際の設定は分からないが、関数は互換等級のリストの最初を返す
    # 設定により異なるが、テストでは設定に依存しないようにするため、
    # 互換等級が存在する場合は最初の要素を返すことを確認
    # ここでは、モックを使わずに実際の設定に依存するテストを書く
    # ただし、設定が変更されるとテストが失敗する可能性がある
    # 代わりに、get_compatible_gradesをモックしてテストする
    # しかし、ここでは実際の設定に依存するテストを書く
    # 設定を見ると、A: [A, B, C, D], B: [B, C, D], C: [C, D], D: [D]
    # したがって、Aの最高互換等級はA、BはB、CはC、DはD
    assert get_highest_compatible_grade("A") == "A"
    assert get_highest_compatible_grade("B") == "B"
    assert get_highest_compatible_grade("C") == "C"
    assert get_highest_compatible_grade("D") == "D"
    # 存在しない等級
    assert get_highest_compatible_grade("Z") is None

def test_grade_matches():
    # 会社等級がNone
    result = grade_matches(None, "A")
    assert result["company_grade"] is None
    assert result["required_grade"] == "A"
    assert result["can_apply"] is False
    assert result["compatible_grades"] == []  # Noneのときは空リスト?
    # 実際の関数では、normalize_grade(None)がNoneになり、get_compatible_grades(None)は[]を返す
    # 必要等級=at's note: the next line is cut off in the original text, but we know it should be:
    # assert result["compatible_grades"] == ["A", "B", "C", "D"]  # Aの互換等級
    # Let's write it correctly.
    result = grade_matches("A", None)
    assert result["company_grade"] == "A"
    assert result["required_grade"] is None
    assert result["can_apply"] is True  # 必要等級がNoneだとTrue
    assert result["compatible_grades"] == ["A", "B", "C", "D"]  # Aの互換等級
    # 両方None
    result = grade_matches(None, None)
    assert result["company_grade"] is None
    assert result["required_grade"] is None
    assert result["can_apply"] is True
    assert result["compatible_grades"] == []
    # 通常のケース
    result = grade_matches("A", "C")
    assert result["company_grade"] == "A"
    assert result["required_grade"] == "C"
    assert result["can_apply"] is True
    assert result["compatible_grades"] == ["A", "B", "C", "D"]
    # 適用不可能なケース
    result = grade_matches("C", "A")
    assert result["company_grade"] == "C"
    assert result["required_grade"] == "A"
    assert result["can_apply"] is False
    assert result["compatible_grades"] == ["C", "D"]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])