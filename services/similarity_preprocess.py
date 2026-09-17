"""Specification Text Preprocessing Pipeline

仕様書テキストからノイズを除去し、類似度算出向けに正規化を行う。

提供する機能:
  - HTMLタグの除去 (BeautifulSoup が利用可能ならテキストのみ抽出)
  - 改行・空白の正規化 (連続する空白を1つに、全角スペースを半角に)
  - 定型句除去 (辞書ベースフィルタ: 「以下省略」「※別添参照」等)
  - 文単位での分割 (「。」で区切り、最後の空白を除去)
"""
import re
import logging
from html import unescape
from typing import List, Optional

logger = logging.getLogger(__name__)

_HALF_WIDTH_SPACE = " "

_BOILERPLATE_PATTERNS: List[str] = [
    "以下省略",
    "※別添参照",
    "見積書参照",
    "別添参照",
    "以下参照",
    "文末参照",
    "注)",
    "※",
    "【別添】",
    "参照のこと",
    "添付ファイル参照",
    "ヘッダー参照",
    "フッター参照",
    "ページ参照",
]

_FULL_WIDTH_CHARS = {
    "　": _HALF_WIDTH_SPACE,
}


def remove_html_tags(text: str) -> str:
    """HTMLタグを除去してプレーンテキストのみを返す。

    BeautifulSoup が利用可能な場合はそれを使い、利用不可な場合は正規表現で除去する。
    """
    if not text:
        return ""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(text, "html.parser")
        for element in soup(["script", "style", "template"]):
            element.decompose()
        return soup.get_text(separator=" ", strip=True)
    except ImportError:
        text = re.sub(r"<(script|style|template)\b[^>]*>.*?</\1\s*>", " ", text, flags=re.I | re.S)
        return unescape(re.sub(r"<!--.*?-->|</?[a-zA-Z][^>]*>", " ", text, flags=re.S))


def normalize_whitespace(text: str) -> str:
    """改行・空白の正規化。

    - 連続する空白（半角・全角を問わず）を1つの半角スペースに
    - 制御文字を除去
    """
    if not text:
        return ""
    # 全角スペースを半角スペースに
    for fw, hw in _FULL_WIDTH_CHARS.items():
        text = text.replace(fw, hw)
    # 改行・タブ・制御文字をスペースに統一
    text = re.sub(r"[\r\n\t\f\v\u0000-\u001f]", " ", text)
    # 連続する空白を1つに
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def remove_boilerplate(text: str, patterns: Optional[List[str]] = None) -> str:
    """定型句を辞書ベースで除去する。

    Args:
        text: 入力テキスト
        patterns: 除去対象パターンリスト。未指定時は _BOILERPLATE_PATTERNS を使用。
    """
    if not text:
        return ""
    if patterns is None:
        patterns = _BOILERPLATE_PATTERNS
    result = text
    for pattern in patterns:
        result = result.replace(pattern, " ")
    return normalize_whitespace(result)


def split_sentences(text: str) -> List[str]:
    """「。」で区切り、各文の前後の空白を除去してリストで返す。

    日本語の句点以外に「．」（全角）も対象とする。
    """
    if not text:
        return []
    normalized = normalize_whitespace(text)
    # 「。」と「．」で分割
    sentences = re.split(r"[。．]", normalized)
    result = [s.strip() for s in sentences if s.strip()]
    return result


def preprocess_specification(
    text: str,
    do_remove_html: bool = True,
    do_remove_boilerplate: bool = True,
    custom_boilerplate: Optional[List[str]] = None,
) -> str:
    """仕様書テキストの前処理を一括実行。

    Args:
        text: 生の仕様書テキスト
        do_remove_html: HTMLタグを除去するか
        do_remove_boilerplate: 定型句を除去するか
        custom_boilerplate: カスタム除去パターン（追加で指定可能）

    Returns:
        前処理済みテキスト
    """
    if not text:
        return ""
    result = text
    if do_remove_html:
        result = remove_html_tags(result)
    result = normalize_whitespace(result)
    if do_remove_boilerplate:
        patterns = custom_boilerplate if custom_boilerplate is not None else None
        result = remove_boilerplate(result, patterns)
    return result


def get_clean_specification_text(
    bid_specification: Optional[str],
    bid_deliverables: Optional[str],
    bid_qualifications: Optional[str],
) -> str:
    """Bid モデルの各テキストフィールドの前処理結果を結合して返す。

    specification_text, deliverables, qualifications の各フィールドを結合・前処理する。
    """
    parts: List[str] = []
    for field in (bid_specification, bid_deliverables, bid_qualifications):
        if field:
            parts.append(field)
    combined = " ".join(parts)
    return preprocess_specification(combined)
