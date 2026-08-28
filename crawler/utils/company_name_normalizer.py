"""
Company Name Normalizer
企業名の表記揺れ（株式会社/(株)/㈱/Corp/Ltd 等）を正規化する。
"""
import re


SUFFIX_MAP = {
    "(株)": "株式会社",
    "(有)": "有限会社",
    "(合)": "合資会社",
    "㈱": "株式会社",
    "㈲": "有限会社",
    "㈶": "基金",
    "株式会社 ": "株式会社",
    "有限会社 ": "有限会社",
    " Corp.": "株式会社",
    " Corp": "株式会社",
    " Co., Ltd.": "株式会社",
    " Co., Ltd": "株式会社",
    " Ltd.": "株式会社",
    " Ltd": "株式会社",
    " INC.": "株式会社",
    " INC": "株式会社",
}


def normalize(name: str) -> str:
    """企業名を正規化して返す。"""
    if not name:
        return ""
    name = name.strip()
    for old, new in SUFFIX_MAP.items():
        if old in name:
            name = name.replace(old, new)
            break
    name = re.sub(r"[\s　]+", "", name)
    return name


def remove_suffix(name: str) -> str:
    """法人格サフィックスを除去してコア名だけ返す。"""
    if not name:
        return ""
    normalized = normalize(name)
    suffixes = [
        "株式会社", "有限会社", "合資会社", "合同会社",
        "合名会社", "基金", "公社", "公団",
    ]
    for suffix in suffixes:
        normalized = normalized.replace(suffix, "")
    return normalized.strip()


def extract_corporate_number(text: str) -> Optional[str]:
    """13桁の法人番号を抽出。"""
    if not text:
        return None
    m = re.search(r"\b(\d{13})\b", text)
    return m.group(1) if m else None


def similarity(a: str, b: str) -> float:
    """簡単な類似度（0.0～1.0）。同一なら1.0。"""
    if not a or not b:
        return 0.0
    na, nb = normalize(a), normalize(b)
    if na == nb:
        return 1.0
    shorter = min(len(na), len(nb))
    if shorter == 0:
        return 0.0
    matches = sum(1 for i in range(shorter) if na[i] == nb[i])
    return round(matches / max(len(na), len(nb)), 2)


def find_similar(name: str, candidates: list[str], threshold: float = 0.7) -> Optional[str]:
    """candidates から name に類似するものを探す。"""
    best_match = None
    best_score = 0.0
    for cand in candidates:
        score = similarity(name, cand)
        if score > best_score and score >= threshold:
            best_score = score
            best_match = cand
    return best_match


INDUSTRY_KEYWORDS = {
    "建設": ["建設", "建築", "土木", "舗装", "管工事", "造園", "解体"],
    "IT": ["システム", "ソフトウェア", "ネットワーク", "データセンター", "クラウド", "情報"],
    "コンサル": ["コンサルティング", "調査", "計画", "設計", "シンクタンク"],
    "物品": ["物品", "備品", "機器", "設備", "販売"],
    "委託": ["委託", "業務委託", "サービス", "清掃", "警備"],
    "医療": ["医療", "病院", "介護", "福祉"],
    "教育": ["教育", "学校", "研修"],
}


def detect_industry(name: str) -> Optional[str]:
    """企業名・案件名から業種カテゴリを推測。"""
    if not name:
        return None
    for category, keywords in INDUSTRY_KEYWORDS.items():
        for kw in keywords:
            if kw in name:
                return category
    return None
