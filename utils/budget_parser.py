import re
import logging

logger = logging.getLogger(__name__)

def parse_budget(budget_str: str) -> Optional[int]:
    """
    予算文字列を数値（円単位）に変換する。
    例: '1,500万円' -> 15000000
    例: '1,000,000円' -> 1000000
    """
    if not budget_str or budget_str in ["不明", "記載なし", "None"]:
        return None

    try:
        # カンマを除去
        clean_str = budget_str.replace(",", "")
        
        # 数値部分を抽出
        match = re.search(r'(\d+(\.\d+)?)', clean_str)
        if not match:
            return None
            
        value = float(match.group(1))
        
        if '億円' in clean_str:
            return int(value * 100_000_000)
        elif '万円' in clean_str:
            return int(value * 10_000)
        elif '千円' in clean_str:
            return int(value * 1_000)
        else:
            return int(value)
    except Exception as e:
        logger.warning(f"Failed to parse budget string '{budget_str}': {e}")
        return None
