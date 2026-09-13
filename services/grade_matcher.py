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
    # First, try to match Kanji, alphabetic, or numeric grades with optional level marker (no space)
    pattern1 = r"[甲乙丙丁ABCDabcd1-4][級级]?"
    m = re.search(pattern1, text)
    if m:
        matched = m.group(0)
        # Map Kanji to letters
        kanji_to_grade = {"甲": "A", "乙": "B", "丙": "C", "丁": "D"}
        base = matched[0]
        if base in kanji_to_grade:
            return kanji_to_grade[base]
        # For alphabetic and numeric, remove trailing "級" or "级" if present, then uppercase
        if matched.endswith(("級", "级")):
            matched = matched[:-1]
        return matched.upper()
    # Second, try to match alphabetic grade with possible space and level marker
    pattern2 = r"(A|B|C|D)\s*(?:級|级)"
    m = re.search(pattern2, text, re.IGNORECASE)
    if m:
        return m.group(1).upper()
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


if __name__ == "__main__":
    pass