import pytest
from utils.text_processor import normalize_text, chunk_text

def test_normalize_text():
    # 全角英数字を半角に変換
    assert normalize_text("ａＢＣ１２３") == "aBC123"
    # 連続スペースを縮小
    assert normalize_text("a   b\t\tc") == "a b c"
    # 改行は保持
    assert normalize_text("a\n\nb") == "a\n\nb"
    # 前後の空白除去
    assert normalize_text("  \n  hello  \n  world  \n  ") == "hello\nworld"
    # 空文字列
    assert normalize_text("") == ""
    # Noneは空文字列になる
    assert normalize_text(None) == ""

def test_normalize_text_newlines():
    s = "line1\n  line2  \n\n   line3   \n"
    assert normalize_text(s) == "line1\nline2\n\nline3"

def test_chunk_text_respects_max_chars():
    text = "あ" * 5000
    chunks = chunk_text(text, max_chars=1000)
    assert all(len(c) <= 1000 for c in chunks)
    # 結合すると元の長さになる（空白の差異は許容）
    joined = "".join(chunks)
    assert len(joined) >= 5000  # 少なくとも元の長さ以上（スペース削減あり）
    # チャンク間に余計な文字が入っていないことを確認
    # 簡易チェック：元の文字列と比較（スペース除去後）
    orig_no_space = text.replace(" ", "")
    joined_no_space = joined.replace(" ", "")
    # これは厳密ではないが、だいたい同じであることを期待
    assert abs(len(orig_no_space) - len(joined_no_space)) <= 10

def test_chunk_text_respects_sentence_boundary():
    text = "これは最初の文です。これは二番目の文です。これは三番目の文です。" * 10
    chunks = chunk_text(text, max_chars=100)
    # 各チャンクが100文字以内であること
    assert all(len(c) <= 100 for c in chunks)
    # 句点で切れているか確認（最後に句点がないチャンクは最後のチャンクのみ許容）
    for i, c in enumerate(chunks[:-1]):
        # 最後の文字が句点または読点であることが望ましい
        assert c.rstrip().endswith(("。", "、")), f"Chunk {i} does not end with punctuation: '{c[-10:]}'"

def test_chunk_text_priority_keywords():
    text = "予算について説明します。これは重要なポイントです。次に進みます。"
    # キーワード「優先」を含むブロックで分割したいが、ここでは単純にキーワード付近で分割されるか確認
    chunks = chunk_text(text, max_chars=20, priority_keywords=["重要"])
    # 少なくとも一つのチャンクに「重要」が含まれているか
    assert any("重要" in c for c in chunks)
    # 各チャンクはmax_chars以内
    assert all(len(c) <= 20 for c in chunks)

def test_chunk_text_empty():
    assert chunk_text("", max_chars=100) == []
    assert chunk_text(None, max_chars=100) == []

def test_chunk_text_exact_boundary():
    text = "x" * 100
    chunks = chunk_text(text, max_chars=100)
    assert len(chunks) == 1
    assert chunks[0] == text

def test_chunk_text_overboundary():
    text = "x" * 101
    chunks = chunk_text(text, max_chars=100)
    # 2チャンクに分割されるはず
    assert len(chunks) == 2
    assert len(chunks[0]) == 100
    assert len(chunks[1]) == 1
    assert chunks[0] + chunks[1] == text