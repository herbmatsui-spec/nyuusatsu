"""Tests for services/similarity_preprocess.py"""
import pytest
from services.similarity_preprocess import (
    remove_html_tags,
    normalize_whitespace,
    remove_boilerplate,
    split_sentences,
    preprocess_specification,
    get_clean_specification_text,
    _BOILERPLATE_PATTERNS,
)


def test_remove_html_tags_with_html():
    html = "<p>テスト文章</p><div>別のテキスト</div>"
    result = remove_html_tags(html)
    assert "テスト文章" in result
    assert "別のテキスト" in result
    assert "<" not in result
    assert ">" not in result


def test_remove_html_tags_plain_text():
    text = "これはプレーンテキストです"
    result = remove_html_tags(text)
    assert result == text


def test_remove_html_tags_empty():
    assert remove_html_tags("") == ""
    assert remove_html_tags(None) == ""


def test_normalize_whitespace_fullwidth_space():
    text = "テスト\u3000\u3000文章"
    result = normalize_whitespace(text)
    assert "\u3000" not in result
    assert "  " not in result


def test_normalize_whitespace_consecutive_spaces():
    text = "a   b\t\tc\n\nd"
    result = normalize_whitespace(text)
    assert "  " not in result
    assert "\t" not in result
    assert "\n" not in result


def test_normalize_whitespace_strips():
    text = "  hello  "
    result = normalize_whitespace(text)
    assert result == "hello"


def test_remove_boilerplate():
    text = "以下省略※別添参照 見積書参照 実際の内容"
    result = remove_boilerplate(text)
    assert "以下省略" not in result
    assert "※別添参照" not in result
    assert "見積書参照" not in result
    assert "実際の内容" in result


def test_remove_boilerplate_custom_patterns():
    text = "カスタムテキスト 削除対象 カスタムテキスト"
    result = remove_boilerplate(text, patterns=["削除対象"])
    assert "削除対象" not in result
    assert "カスタムテキスト" in result


def test_remove_boilerplate_empty():
    assert remove_boilerplate("") == ""
    assert remove_boilerplate(None) == ""


def test_split_sentences():
    text = "最初の文。二番目の文。第三の文。"
    result = split_sentences(text)
    assert len(result) == 3
    assert result[0] == "最初の文"
    assert result[1] == "二番目の文"
    assert result[2] == "第三の文"


def test_split_sentences_fullwidth_period():
    text = "最初の文．二番目の文．"
    result = split_sentences(text)
    assert len(result) == 2


def test_split_sentences_empty():
    assert split_sentences("") == []
    assert split_sentences(None) == []


def test_split_sentences_strips_whitespace():
    text = "  文一  。  文二  。  "
    result = split_sentences(text)
    assert all(s == s.strip() for s in result)


def test_preprocess_specification_basic():
    html_text = "<p>テスト仕様書</p><br>以下省略"
    result = preprocess_specification(html_text)
    assert "テスト仕様書" in result
    assert "以下省略" not in result
    assert "<" not in result


def test_preprocess_specification_skip_html():
    text = "テスト仕様書以下省略"
    result = preprocess_specification(text, do_remove_html=False, do_remove_boilerplate=True)
    assert "テスト仕様書" in result
    assert "以下省略" not in result


def test_preprocess_specification_skip_boilerplate():
    text = "<p>以下省略</p>"
    result = preprocess_specification(text, do_remove_boilerplate=False)
    assert "以下省略" in result


def test_preprocess_specification_empty():
    assert preprocess_specification("") == ""
    assert preprocess_specification(None) == ""


def test_preprocess_specification_custom_boilerplate():
    text = "内容カスタム除去対象"
    result = preprocess_specification(text, custom_boilerplate=["除去対象"])
    assert "除去対象" not in result


def test_get_clean_specification_text_combines_fields():
    spec = "仕様書<以下省略>"
    deliverables = "成果物"
    qualifications = "資格要件"
    result = get_clean_specification_text(spec, deliverables, qualifications)
    assert "仕様書" in result
    assert "成果物" in result
    assert "資格要件" in result
    assert "以下省略" not in result


def test_get_clean_specification_text_empty():
    assert get_clean_specification_text(None, None, None) == ""
    assert get_clean_specification_text("", "", "") == ""


def test_html_noise_entities_and_unicode_whitespace():
    text = '<style>noise</style><script>noise</script><template>noise</template><p>A&nbsp; B\u2003C</p>'
    assert preprocess_specification(text) == "A B C"


def test_html_fallback_decodes_entities_and_removes_noise(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "bs4", None)
    assert preprocess_specification('<script>noise</script><p>A&nbsp; B</p>') == "A B"
    assert preprocess_specification("2 < 3、5 > 4") == "2 < 3、5 > 4"


def test_preprocessing_preserves_substantive_requirements():
    text = "実績3年以上。別添の仕様を満たすこと。"
    assert preprocess_specification(text) == text


def test_boilerplate_patterns_contains_expected():
    assert "以下省略" in _BOILERPLATE_PATTERNS
    assert "※別添参照" in _BOILERPLATE_PATTERNS
    assert "見積書参照" in _BOILERPLATE_PATTERNS
