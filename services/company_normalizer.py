"""
Company Normalizer
競合企業名の正規化・業種判定・類似検索を提供するサービス層。
"""
import logging
from typing import Any, Dict, Optional

from crawler.parsers.award_parser import extract_industry_from_text
from crawler.utils.company_name_normalizer import (
    detect_industry,
    find_similar,
    normalize,
    remove_suffix,
    similarity,
)

logger = logging.getLogger(__name__)


def normalize_company_name(raw_name: str) -> str:
    """企業名のraw値を正規化して返す。
    正規化ルールは `config/company_normalization_rules.py` の `NORMALIZATION_RULES` を適用します。"""
    if not raw_name:
        return ""
    # ルール適用（順序依存）
    from config.company_normalization_rules import NORMALIZATION_RULES
    import re
    name = raw_name.strip()
    for pattern, repl in NORMALIZATION_RULES.items():
        name = re.sub(pattern, repl, name)
    # 空白・記号除去はルール側でカバー
    return name


def build_competitor_payload(raw_name: str) -> Dict[str, Any]:
    """クローラから取得した raw_name から Competitor モデル用dictを生成する。"""
    normalized = normalize_company_name(raw_name)
    # 優先的に config の INDUSTRY_KEYWORDS を使用し、見つからなければ utils の detect_industry をフォールバック
    from config.company_normalization_rules import INDUSTRY_KEYWORDS
    industry = None
    for category, keywords in INDUSTRY_KEYWORDS.items():
        for kw in keywords:
            if kw in raw_name:
                industry = category
                break
        if industry:
            break
    if not industry:
        industry = detect_industry(raw_name) or extract_industry_from_text(raw_name)
    return {
        "normalized_name": normalized,
        "raw_names": raw_name,
        "industry_category": industry,
    }
