"""
Competitor Enricher
法人番号・業種・地域情報から競合企業の属性を補完する。
"""
import logging
from typing import Any, Dict, Optional

from crawler.utils.company_name_normalizer import detect_industry
from crawler.parsers.award_parser import extract_industry_from_text

logger = logging.getLogger(__name__)


def enrich_from_industry(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """raw_data から業種カテゴリを推測して返す。"""
    text = raw_data.get("winner_name") or raw_data.get("project_name") or ""
    category = detect_industry(text) or extract_industry_from_text(text)
    if category:
        raw_data["industry_category"] = category
    return raw_data


def enrich_from_corporate_number(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """法人番号があればキーとして保持（将来的にAPI問合せ拡張用）。"""
    corporate_number = raw_data.get("corporate_number")
    if corporate_number:
        raw_data["corporate_number"] = str(corporate_number).strip()
    return raw_data


def enrich_region(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """発注機関名や企業名から地域を推測。"""
    from config.company_normalization_rules import PREFECTURE_CODES
    text = raw_data.get("agency_name") or raw_data.get("winner_name") or ""
    for pref, code in PREFECTURE_CODES.items():
        if pref in text:
            raw_data["region"] = pref
            break
    return raw_data


def enrich_all(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """全エンリッチ処理を適用。"""
    raw_data = enrich_from_industry(raw_data)
    raw_data = enrich_from_corporate_number(raw_data)
    raw_data = enrich_region(raw_data)
    return raw_data
