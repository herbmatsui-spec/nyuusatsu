"""
Award PDF Parser
PDF内の落札結果情報から必要なフィールドを抽出する。
"""
import logging
import re
from typing import Any, Dict, Optional

from crawler.parsers.award_parser import (
    extract_industry_from_text,
    parse_award_date,
    parse_announcement_date,
    parse_budget_amount,
    parse_contract_amount,
    parse_winner_name,
)
from crawler.utils.text_cleaner import normalize_whitespace, remove_html_tags

logger = logging.getLogger(__name__)


def parse_award_pdf_text(text: str) -> Dict[str, Any]:
    """
    PDFから抽出した生テキストから落札情報を生成する。

    想定するPDFテキスト例:
       入札公告番号: 令和5年度第○○号
       予定価格: 12,345,678円
       落札価格: 11,111,111円
       落札業者名: 株式会社サンプル
       落札日: 令和5年4月1日
    """
    try:
        clean = normalize_whitespace(remove_html_tags(text))
        budget = parse_budget_amount(clean)
        contract = parse_contract_amount(clean)
        award_rate = None
        if budget and contract and budget > 0:
            award_rate = round((contract / budget) * 100, 2)

        winner = parse_winner_name(clean)
        category = extract_industry_from_text(clean)
        announcement = parse_announcement_date(clean)
        award = parse_award_date(clean)

        return {
            "project_name": None,
            "agency_name": None,
            "category": category,
            "budget_amount": budget,
            "contract_amount": contract,
            "award_rate": award_rate,
            "winner_name": winner,
            "winner_count": 1,
            "announcement_date": announcement,
            "award_date": award,
        }
    except Exception as e:
        logger.error(f"Failed to parse award PDF text: {e}")
        return {}
