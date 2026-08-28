"""
Grade Matcher
等級判定専用サービス。
"""
from typing import Optional, List
from config.qualification_grades import can_apply, normalize_grade, get_compatible_grades


def extract_grade_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    import re
    m = re.search(r"[甲乙丙丁ABCDabcd][級级]?|[1-4][級级]?", text)
    if m:
        return normalize_grade(m.group(0))
    m = re.search(r"(A|B|C|D)\s*(?:級|级)", text, re.IGNORECASE)
    if m:
        return normalize_grade(m.group(1))
    return None


def check_grade_requirement(company_grade: Optional[str], required_grade: Optional[str]) -> bool:
    return can_apply(company_grade, required_grade)


def get_highest_compatible_grade(company_grade: str) -> Optional[str]:
    if not company_grade:
        return None
    compatible = get_compatible_grades(normalize_grade(company_grade))
    if compatible:
        return compatible[0]
    return None


def grade_matches(company_grade: Optional[str], bid_grade: Optional[str]) -> dict:
    return {
        "company_grade": company_grade,
        "required_grade": bid_grade,
        "can_apply": check_grade_requirement(company_grade, bid_grade),
        "compatible_grades": get_compatible_grades(normalize_grade(company_grade) if company_grade else None),
    }