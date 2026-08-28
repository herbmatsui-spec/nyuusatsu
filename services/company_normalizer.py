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
    """企業名のraw値を正規化して返す。"""
    if not raw_name:
        return ""
    return normalize(raw_name)


def build_competitor_payload(raw_name: str) -> Dict[str, Any]:
    """クローラから取得した raw_name から Competitor モデル用dictを生成する。"""
    normalized = normalize_company_name(raw_name)
    industry = detect_industry(raw_name) or extract_industry_from_text(raw_name)
    return {
        "normalized_name": normalized,
        "raw_names": raw_name,
        "industry_category": industry,
    }
