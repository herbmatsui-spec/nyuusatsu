"""
Grade Parser
仕様書テキストから全省庁統一資格等级を抽出するパーサ。
"""
import re
from typing import Optional


def extract_grade_from_text(text: str) -> Optional[str]:
    """
    テキストから全省庁統一資格等级を抽出する。
    例: 「全省庁統一资格 A」→ "A"
        「資格: B級」→ "B"
        「甲等級」→ "A" (甲=A, 乙=B, 丙=C, 丁=D)
    """
    if not text:
        return None

    GRADE_MAP = {
        "A": ["A", "a", "Ａ", "ａ"],
        "B": ["B", "b", "Ｂ", "ｂ"],
        "C": ["C", "c", "Ｃ", "ｃ"],
        "D": ["D", "d", "Ｄ", "ｄ"],
    }
    KANJI_GRADE_MAP = {
        "甲": "A",
        "乙": "B",
        "丙": "C",
        "丁": "D",
    }

    # Check exact matches (case-sensitive for full-width)
    for grade, variants in GRADE_MAP.items():
        for v in variants:
            if v in text:
                return grade

    for kanji, grade in KANJI_GRADE_MAP.items():
        if kanji in text:
            return grade

    m = re.search(r"[ABCDabcd][\s]*[\-\–]?\s*[級]", text)
    if m:
        g = m.group(0)[0].upper()
        if g in ["A", "B", "C", "D"]:
            return g

    return None


def extract_unified_qualification_number(text: str) -> Optional[str]:
    """全省庁統一資格番号（13桁）を抽出する。"""
    if not text:
        return None
    m = re.search(r"\b(\d{13})\b", text)
    return m.group(1) if m else None


def extract_all_grades(text: str) -> list[str]:
    """テキストから複数等级を一括抽出する。"""
    grade = extract_grade_from_text(text)
    if grade:
        return [grade.upper()]
    return []


def normalize_grade_text(text: str) -> str:
    """等级表記正規化: 「甲」→「A」等に変換。"""
    if not text:
        return ""
    KANJI = {"甲": "A", "乙": "B", "丙": "C", "丁": "D", "1": "A", "2": "B", "3": "C", "4": "D"}
    result = text
    for kanji, latin in KANJI.items():
        result = result.replace(kanji, latin)
    return result.strip()