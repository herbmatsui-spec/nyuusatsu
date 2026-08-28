import re
import unicodedata
from typing import List

def normalize_text(text: str) -> str:
    """
    テキストの正規化（全角半角の統一、不要な空白の除去など）を行う。
    改行は保持し、行内の連続する空白のみを圧縮する。
    """
    if not text:
        return ""

    # 全角を半角に変換（NFKC正規化）
    text = unicodedata.normalize("NFKC", text)
    
    # 行ごとに処理し、行内の連続する空白を1つにまとめる
    lines = text.splitlines()
    normalized_lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in lines]
    
    # 空行を除去せず、前後の余分な空行だけを削除して再結合
    return "\n".join(normalized_lines).strip()


def _split_at_word_boundary(text: str, max_chars: int) -> List[str]:
    """最大文字数を超えないように句点・読点・空白で区切って分割する"""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    remaining = text
    while len(remaining) > max_chars:
        # まず句点で区切ろうとする
        split_point = max(remaining.rfind('。', 0, max_chars),
                          remaining.rfind('、', 0, max_chars),
                          remaining.rfind(' ', 0, max_chars))
        if split_point == -1:
            # 区切り文字が見つからない場合は強制的にmax_charsで切る
            split_point = max_chars
        else:
            # 区切り文字を含める
            split_point += 1
        chunks.append(remaining[:split_point])
        remaining = remaining[split_point:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


def chunk_text(text: str, max_chars: int = 4000, priority_keywords: List[str] = None) -> List[str]:
    """
    テキストを意味のある単位（見出しや段落）で分割し、
    指定された最大文字数以下のチャンクに分ける。
    """
    if not text:
        return []

    # デフォルトの見出しパターンに加えて、優先キーワードベースの分割を追加
    base_pattern = r'(\n(?=第[一二三四五六七八九十\d]+章)|(?=^[\d]{1,2}\.\s)|(?=^【[^】]+】))'
    if priority_keywords:
        # キーワードをエスケープして先読みパターンとして追加
        keywords_pattern = '|'.join([re.escape(k) for k in priority_keywords])
        pattern = f'({base_pattern}|(?={keywords_pattern}))'
    else:
        pattern = base_pattern

    sections = re.split(pattern, text, flags=re.MULTILINE)

    chunks = []
    current_chunk = ""

    for section in sections:
        if not section:
            continue
        if len(current_chunk) + len(section) <= max_chars:
            current_chunk += section
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            
            # セクション自体が max_chars を超える場合は単語境界で分割
            if len(section) > max_chars:
                sub_chunks = _split_at_word_boundary(section, max_chars)
                chunks.extend([c.strip() for c in sub_chunks if c.strip()])
                current_chunk = ""
            else:
                current_chunk = section

    if current_chunk:
        chunks.append(current_chunk.strip())

    # 空のチャンクを除去
    return [c for c in chunks if c]
