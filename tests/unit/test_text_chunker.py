import pytest
from utils.text_chunker import TextChunker

def test_text_chunker_split_by_sections():
    chunker = TextChunker(max_chars=100)
    text = "第1章 予算\n予算は100万円です。\n\n第2章 資格\n資格はA等級です。"
    chunks = chunker.split_by_sections(text)
    assert len(chunks) == 2
    assert "第1章 予算" in chunks[0]
    assert "第2章 資格" in chunks[1]

def test_text_chunker_forced_split():
    chunker = TextChunker(max_chars=10)
    text = "This is a very long string that exceeds max chars"
    result = chunker.prepare_for_llm(text)
    assert len(result) <= 10
