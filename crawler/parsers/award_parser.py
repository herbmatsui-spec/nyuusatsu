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
    # Convert full-width digits to half-width
    text = text.translate(str.maketrans({chr(0xFF10 + i): str(i) for i in range(10)}))
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
    if budget is not None and budget > 0 and contract is not None:
        return round((contract / budget) * 100, 2)
    return None


def parse_date(text: str) -> Optional[datetime]:
    """「令和5年4月1日」「2024/04/01」「2024-04-01」「2024.04.01」等をdatetimeに変換。"""
    if not text:
        return None
    text = text.strip()
    patterns = [
        (r"(\d{4})\s*[年/.\-]\s*(\d{1,2})\s*[月/.\-]\s*(\d{1,2})日?", lambda m: datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))),
        (r"令和\s*(\d+|元)\s*年\s*(\d+)\s*月\s*(\d+)日?", lambda m: datetime(2018 + (1 if m.group(1) == '元' else int(m.group(1))), int(m.group(2)), int(m.group(3)))),
        (r"平成\s*(\d+|元)\s*年\s*(\d+)\s*月\s*(\d+)日?", lambda m: datetime(1988 + (1 if m.group(1) == '元' else int(m.group(1))), int(m.group(2)), int(m.group(3)))),
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
    if not text or text.isspace():
        return None
    text = text.strip()
    for prefix in ("落札者：", "契約者：", "発注者：", "業者：", "供給者："):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
    return text  # Can be empty string


def extract_industry_from_text(text: str) -> Optional[str]:
    """テキストから業種カテゴリを推測。"""
    if not text:
        return None
    keywords = {
        "建設": ["建設", "建築", "土木", "舗装", "管工事", "造園"],
        "IT": ["システム", "ソフトウェア", "ネットワーク", "データセンター", "クラウド"],
        "コンサル": ["コンサルティング", "調査", "計画", "設計"],
        "物品": ["物品", "備品", "機器", "設備", "用品"],
        "委託": ["業務委託", "サービス", "業務"],
    }
    for category, kws in keywords.items():
        for kw in kws:
            if kw in text:
                return category
    return None