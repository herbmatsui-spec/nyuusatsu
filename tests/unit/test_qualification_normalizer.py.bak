import pytest
from unittest.mock import MagicMock
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
