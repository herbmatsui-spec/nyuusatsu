"""
Award PDF Parser
PDF内の落札結果情報から必要なフィールドを抽出する。
"""
import logging
import re
from typing import Any, Dict, Optional

from crawler.parsers.award_parser import (
    extract_industry_from_text,
    parse_date as parse_award_date,
    parse_date as parse_announcement_date,
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
        # Split text into lines and process each line
        lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
        
        # Initialize result with default values
        result = {
            "project_name": None,
            "agency_name": None,
            "category": "",
            "budget_amount": 0,
            "contract_amount": 0,
            "award_rate": None,
            "winner_name": "",
            "winner_count": 1,
            "announcement_date": None,
            "award_date": None,
        }
        
        # Process each line to extract relevant information
        for line in lines:
            # Extract budget amount
            if '予定価格' in line:
                budget_amount = parse_budget_amount(line)
                if budget_amount is not None:
                    result["budget_amount"] = budget_amount
            
            # Extract contract amount
            if '落札価格' in line:
                contract_amount = parse_contract_amount(line)
                if contract_amount is not None:
                    result["contract_amount"] = contract_amount
            
            # Calculate award rate if both amounts are available
            if result["budget_amount"] > 0 and result["contract_amount"] > 0:
                result["award_rate"] = round((result["contract_amount"] / result["budget_amount"]) * 100, 2)
            
            # Extract winner name
            if '落札者：' in line:
                winner_name = parse_winner_name(line)
                if winner_name is not None:
                    result["winner_name"] = winner_name
            
            # Extract category/industry from text
            category = extract_industry_from_text(line)
            if category is not None:
                result["category"] = category
            
            # Extract announcement date
            if '公告日' in line or '告示日' in line:
                announcement_date = parse_announcement_date(line)
                if announcement_date is not None:
                    result["announcement_date"] = announcement_date
            
            # Extract award date
            if '落札日' in line:
                award_date = parse_award_date(line)
                if award_date is not None:
                    result["award_date"] = award_date
        
        return result
    except Exception as e:
        logger.error(f"Failed to parse award PDF text: {e}")
        return {}
