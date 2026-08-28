"""
Award Parser Utilities
落札結果テキスト・HTMLから金額・日付・企業名等を抽出するユーティリティ。
"""
import re
from datetime import datetime
from typing import Optional


def parse_budget_amount(text: str) -> Optional[int]:
    """「予定価格 12,345,678円」等から予定価格を数値で返す。"""
    if not text:
        return None
    cleaned = text.replace(",", "").replace("円", "").replace(" ", "").replace("\n", "")
    m = re.search(r"(\d+)", cleaned)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def parse_contract_amount(text: str) -> Optional[int]:
    """「落札価格 11,111,111円」等から落札価格を数値で返す。"""
    return parse_budget_amount(text)


def calculate_award_rate(budget: Optional[int], contract: Optional[int]) -> Optional[float]:
    """予定価格と落札価格から落札率(%)を算出。"""
    if budget and contract and budget > 0:
        return round((contract / budget) * 100, 2)
    return None


def parse_date(text: str) -> Optional[datetime]:
    """「令和5年4月1日」「2024/04/01」「2024-04-01」等をdatetimeに変換。"""
    if not text:
        return None
    patterns = [
        (r"(\d{4})[年/\-](\d{1,2})[月/\-](\d{1,2})日?", lambda m: datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))),
        (r"令和(\d+)年(\d+)月(\d+)日?", lambda m: datetime(2018 + int(m.group(1)), int(m.group(2)), int(m.group(3)))),
        (r"平成(\d+)年(\d+)月(\d+)日?", lambda m: datetime(1988 + int(m.group(1)), int(m.group(2)), int(m.group(3)))),
    ]
    for pattern, builder in patterns:
        m = re.search(pattern, text)
        if m:
            try:
                return builder(m)
            except (ValueError, IndexError):
                continue
    return None


def parse_winner_name(text: str) -> Optional[str]:
    """落札企業名を抽出。"""
    if not text:
        return None
    # 「株式会社○○」「(株)○○」「○○(有)」等を抽出
    m = re.search(r"([^\s　\n]+(?:株式会社|(?:株)?(?:会社)?|(?:有)?(?:限)?(?:会社)?|Corp\.?|Ltd\.?)[^\s　\n]*)", text)
    if m:
        return m.group(1).strip()
    return text.strip() or None


def extract_industry_from_text(text: str) -> Optional[str]:
    """テキストから業種カテゴリを推測。"""
    if not text:
        return None
    keywords = {
        "建設": ["建設", "建築", "土木", "舗装", "管工事", "造園"],
        "IT": ["システム", "ソフトウェア", "ネットワーク", "データセンター", "クラウド"],
        "コンサル": ["コンサルティング", "調査", "計画", "設計"],
        "物品": ["物品", "備品", "機器", "設備"],
        "委託": ["委託", "業務委託", "サービス"],
    }
    lower = text.lower()
    for category, kws in keywords.items():
        for kw in kws:
            if kw in text:
                return category
    return None
