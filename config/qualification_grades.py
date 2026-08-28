"""
Qualification Grades Configuration
全省庁統一資格等級の階級・互換関係を定義。
"""
from typing import List

GRADE_HIERARCHY: List[str] = ["A", "B", "C", "D"]


GRADE_COMPATIBILITY: dict = {
    "A": ["A", "B", "C", "D"],
    "B": ["B", "C", "D"],
    "C": ["C", "D"],
    "D": ["D"],
}


def get_compatible_grades(grade: str) -> List[str]:
    if grade in GRADE_COMPATIBILITY:
        return GRADE_COMPATIBILITY[grade]
    return []


def can_apply(company_grade: Optional[str], required_grade: Optional[str]) -> bool:
    if not required_grade:
        return True
    if not company_grade:
        return False
    compatible = GRADE_COMPATIBILITY.get(company_grade, [])
    return required_grade in compatible


def normalize_grade(grade: str) -> str:
    if not grade:
        return ""
    g = grade.upper().strip()
    if g in GRADE_HIERARCHY:
        return g
    return ""


ALL_GRADES_LIST: List[str] = list(GRADE_HIERARCHY)