import pytest
from unittest.mock import MagicMock, patch
from services.qualification_normalizer import QualificationNormalizer

@pytest.fixture
def mock_llm():
    mock = MagicMock()
    # 簡易的なLLMレスポンス
    mock.analyze_with_fallback.return_value = {"tag_code": "GEN-A", "confidence": 0.9}
    return mock

def test_normalize_rule_based():
    # LLMサービスは不要（ルールベースでマッチするため）
    normalizer = QualificationNormalizer(llm_service=MagicMock())
    
    # CSVにあるタグでテスト
    results = normalizer.normalize(["一般公募"])
    assert len(results) == 1
    assert results[0]["tag_code"] == "GEN-A"
    assert results[0]["confidence"] == 1.0

def test_normalize_llm_match(mock_llm):
    normalizer = QualificationNormalizer(llm_service=mock_llm)
    
    # ルールベースでマッチしないテキスト
    results = normalizer.normalize(["未知の資格"])
    assert len(results) == 1
    assert results[0]["tag_code"] == "GEN-A" # モックがGEN-Aを返すため
    assert results[0]["confidence"] == 0.9

def test_normalize_unmatched(mock_llm):
    # 低信頼度のモック
    mock_llm.analyze_with_fallback.return_value = {"tag_code": "GEN-A", "confidence": 0.1}
    normalizer = QualificationNormalizer(llm_service=mock_llm)
    
    results = normalizer.normalize(["未知の資格"])
    assert len(results) == 1
    assert results[0]["tag_code"] == "UNMATCHED"
    assert results[0]["confidence"] == 0.0

def test_load_tags_exception():
    """CSV読み込みに失敗した場合のテスト"""
    with patch('services.qualification_normalizer.load_master_csv') as mock_load:
        mock_load.side_effect = Exception("CSV error")
        mock_llm = MagicMock()
        normalizer = QualificationNormalizer(llm_service=mock_llm)
        # _load_tags内の例外はログに出されるが、例外は捕捉されて空リストになる
        assert normalizer.master_tags == []
        # ログが出力されることを確認（ここではログの内容は確認しない）
        mock_llm.analyze_with_fallback.assert_not_called()

def test_match_llm_exception():
    """LLMサービスが例外を投げた場合のテスト"""
    mock_llm = MagicMock()
    mock_llm.analyze_with_fallback.side_effect = Exception("LLM error")
    normalizer = QualificationNormalizer(llm_service=mock_llm)
    
    # マスタータグを空にしないと、_match_llmが呼ばれないかもしれない
    # ルールベースでマッチしないテキストを使う
    with patch.object(normalizer, '_match_rule_based', return_value=None):
        result = normalizer._match_llm(" algún texto ")
        assert result is None
        mock_llm.analyze_with_fallback.assert_called_once()

def test_match_llm_no_json_in_response():
    """LLMの応答がJSONオブジェクトを含まない文字列の場合のテスト"""
    mock_llm = MagicMock()
    mock_llm.analyze_with_fallback.return_value = "これはJSONではないテキストです"
    normalizer = QualificationNormalizer(llm_service=mock_llm)
    
    with patch.object(normalizer, '_match_rule_based', return_value=None):
        result = normalizer._match_llm(" algún texto ")
        assert result is None
        mock_llm.analyze_with_fallback.assert_called_once()

def test_normalize_empty_list():
    """空のリストを正規化した場合のテスト"""
    mock_llm = MagicMock()
    normalizer = QualificationNormalizer(llm_service=mock_llm)
    results = normalizer.normalize([])
    assert results == []
    mock_llm.analyze_with_fallback.assert_not_called()

def test_normalize_multiple_items(mock_llm):
    """複数の項目を正規化した場合のテスト"""
    normalizer = QualificationNormalizer(llm_service=mock_llm)
    # 1つ目はルールベースでマッチ、2つ目はLLMでマッチ
    results = normalizer.normalize(["一般公募", "未知の資格"])
    assert len(results) == 2
    # 1つ目: ルールベース
    assert results[0]["tag_code"] == "GEN-A"
    assert results[0]["confidence"] == 1.0
    assert results[0]["original_text"] == "一般公募"
    # 2つ目: LLM
    assert results[1]["tag_code"] == "GEN-A"
    assert results[1]["confidence"] == 0.9
    assert results[1]["original_text"] == "未知の資格"
    assert mock_llm.analyze_with_fallback.call_count == 1

def test_normalize_llm_confidence_below_threshold(mock_llm):
    """LLMの信頼度が閾値未満の場合のテスト"""
    mock_llm.analyze_with_fallback.return_value = {"tag_code": "GEN-A", "confidence": 0.4}
    normalizer = QualificationNormalizer(llm_service=mock_llm)
    
    with patch.object(normalizer, '_match_rule_based', return_value=None):
        results = normalizer.normalize(["未知の資格"])
        assert len(results) == 1
        assert results[0]["tag_code"] == "UNMATCHED"
        assert results[0]["confidence"] == 0.0

def test_normalize_llm_returns_none(mock_llm):
    """LLMがNoneを返した場合のテスト"""
    mock_llm.analyze_with_fallback.return_value = None
    normalizer = QualificationNormalizer(llm_service=mock_llm)
    
    with patch.object(normalizer, '_match_rule_based', return_value=None):
        results = normalizer.normalize(["未知の資格"])
        assert len(results) == 1
        assert results[0]["tag_code"] == "UNMATCHED"
        assert results[0]["confidence"] == 0.0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])