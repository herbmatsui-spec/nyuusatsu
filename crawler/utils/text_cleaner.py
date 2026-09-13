"""
Text Cleaner Utilities
HTMLや生テキストから落札情報抽出の前処理を行う。
"""
import re
from typing import Optional


def normalize_whitespace(text: str) -> str:
    """連続する空白・改行・タブを単一スペースに正規化。"""
    if not text:
        return ""
    return re.sub(r"[\s\u3000]+", " ", text).strip()


def remove_html_tags(text: str) -> str:
    """HTMLタグを除去。"""
    if not text:
        return ""
    # script/style タグの中身も除去
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)
    return re.sub(r"<[^>]+>", "", text)


def normalize_numbers(text: str) -> str:
    """数字の表記を正規化（全角→半角、カンマ・ピリオド除去）。"""
    if not text:
        return ""
    # 全角数字・英字を半角に変換
    text = text.translate(str.maketrans(
        "０１２３４５６７８９"
        "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
        "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ",
        "0123456789"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "abcdefghijklmnopqrstuvwxyz"
    ))
    text = text.replace(",", "").replace("，", "").replace("．", "").replace(".", "")
    return text


def clean_amount_text(text: str) -> Optional[int]:
    """金額テキストを数値に変換。"""
    if not text:
        return None
    cleaned = normalize_numbers(text)
    cleaned = cleaned.replace("円", "").replace("¥", "").replace("￥", "").strip()
    m = re.search(r"(\d+(?:\.\d+)?)", cleaned)
    if m:
        try:
            return int(float(m.group(1)))
        except ValueError:
            return None
    return None


def truncate(text: str, max_length: int = 200) -> str:
    """長いテキストを max_length で truncate。"""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    # 単純に max_length 文字で切る
    return text[:max_length]
