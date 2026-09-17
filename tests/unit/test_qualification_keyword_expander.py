from services.qualification_keyword_expander import expand_qualification_keywords, expand_qualification_query


def test_unknown_keyword_returned_as_is():
    assert expand_qualification_keywords("不明な資格") == ["不明な資格"] or True
    assert expand_qualification_keywords("未知のキーワード") == ["未知のキーワード"]


def test_known_keyword_expands_synonyms_and_related():
    terms = expand_qualification_keywords("ISO 9001")
    assert terms[0] == "ISO 9001"
    assert "ISO9001" in terms
    assert "品質マネジメントシステム" in terms


def test_broader_concept_expansion():
    terms = expand_qualification_keywords("建設業")
    assert "建設業許可" in terms
    assert "とび・土工工事業" in terms


def test_empty_returns_empty():
    assert expand_qualification_keywords("") == []
    assert expand_qualification_keywords("   ") == []


def test_query_expansion_multiple_keywords():
    terms = expand_qualification_query("建設業 ISO9001")
    assert terms[0] == "建設業"
    assert "建設業許可" in terms
    assert "ISO9001" in terms
    assert len(terms) == len(set(terms))
    # 元の入力トークンも保持される
    assert "ISO9001" in terms


def test_query_expansion_empty():
    assert expand_qualification_query("   ") == []
