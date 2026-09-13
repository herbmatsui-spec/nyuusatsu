"""
Qualification Grades Configuration
全省庁統一資格等級の互換性・階層定義
"""

# 等級階層（上位から下位）
GRADE_HIERARCHY = ["A", "B", "C", "D"]

# 互換性マップ: キーの等級が適用可能な等級のリスト
GRADE_COMPATIBILITY = {
    "A": ["A", "B", "C", "D"],
    "B": ["B", "C", "D"],
    "C": ["C", "D"],
    "D": ["D"],
}

# 全等級リスト
ALL_GRADES_LIST = ["A", "B", "C", "D"]


def normalize_grade(grade: str) -> str:
    """
    等級文字列を正規化する。
    - 小文字を大文字に
    - 全角英字を半角に
    - 無効な等級は空文字を返す
    """
    if not grade:
        return ""
    
    # 全角英字を半角に変換
    grade = grade.strip().upper()
    
    # 全角英字対応
    fullwidth_to_halfwidth = {
        "Ａ": "A", "Ｂ": "B", "Ｃ": "C", "Ｄ": "D",
        "ａ": "A", "ｂ": "B", "ｃ": "C", "ｄ": "D",
    }
    grade = fullwidth_to_halfwidth.get(grade, grade)
    
    # 有効な等級かチェック
    if grade in GRADE_HIERARCHY:
        return grade
    
    return ""


def can_apply(company_grade: str | None, required_grade: str | None) -> bool:
    """
    企業等級が必要等級に適用可能か判定する。
    
    Args:
        company_grade: 企業の保有等級
        required_grade: 案件の必要等級
    
    Returns:
        適用可能なら True
    """
    if required_grade is None:
        # 必要等級が指定されていない場合は常に適用可能
        return True
    
    if company_grade is None:
        # 企業等級がない場合は適用不可
        return False
    
    # 正規化
    company_grade = normalize_grade(company_grade)
    required_grade = normalize_grade(required_grade)
    
    if not company_grade or not required_grade:
        return False
    
    # 互換性チェック
    compatible = GRADE_COMPATIBILITY.get(company_grade, [])
    return required_grade in compatible


def get_compatible_grades(grade: str | None) -> list[str]:
    """
    指定等級が適用可能な等級リストを返す。
    
    Args:
        grade: 等級
    
    Returns:
        適用可能な等級のリスト
    """
    if not grade:
        return []
    
    grade = normalize_grade(grade)
    if not grade:
        return []
    
    return GRADE_COMPATIBILITY.get(grade, [])


if __name__ == "__main__":
    # 簡単な動作確認
    print("GRADE_HIERARCHY:", GRADE_HIERARCHY)
    print("GRADE_COMPATIBILITY:", GRADE_COMPATIBILITY)
    print("ALL_GRADES_LIST:", ALL_GRADES_LIST)
    print()
    print("normalize_grade('a'):", normalize_grade("a"))
    print("normalize_grade('Ａ'):", normalize_grade("Ａ"))
    print("normalize_grade('Z'):", normalize_grade("Z"))
    print()
    print("can_apply('A', 'B'):", can_apply("A", "B"))
    print("can_apply('B', 'A'):", can_apply("B", "A"))
    print("can_apply(None, 'A'):", can_apply(None, "A"))
    print("can_apply('A', None):", can_apply("A", None))
    print()
    print("get_compatible_grades('A'):", get_compatible_grades("A"))
    print("get_compatible_grades('D'):", get_compatible_grades("D"))