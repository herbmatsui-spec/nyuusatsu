"""
Step 67-69: LLMサービスの単体テスト
- Step 67: LLMプロバイダー切り替えの検証
- Step 68: フォールバック動作の検証
- Step 69: 両プロバイダー未設定時のエラーハンドリング検証
"""
import pytest
from unittest.mock import MagicMock, patch
from typing import Dict, Any

from services.llm_service import LLMService
from services.providers.base import LLMProvider
from config import AppConfig, LLMConfig


class MockProvider(LLMProvider):
    """テスト用モックプロバイダー"""
    def __init__(self, name: str, should_fail: bool = False):
        self.name = name
        self.should_fail = should_fail

    def analyze(self, text: str, system_prompt: str) -> Dict[str, Any]:
        if self.should_fail:
            raise Exception(f"{self.name} provider failed")
        return {
            "provider": self.name,
            "text": text[:50] + "..." if len(text) > 50 else text,
            "length": len(text)
        }


def test_llm_service_provider_selection():
    """LLMサービスが設定されたプロバイダーを正しく選択することをテスト"""
    config = AppConfig()
    config.llm.active_provider = "deepseek"
    
    service = LLMService(
        deepseek_key="deepseek-key",
        gemini_key="gemini-key",
        config=config
    )
    
    assert service.active_provider_name == "deepseek"
    assert len(service.providers) == 2  # Both providers should be added for fallback
    assert service.get_active_provider() is not None


def test_llm_service_fallback():
    """LLMサービスがプライマリプロバイダー失敗時にフォールバックすることをテスト"""
    config = AppConfig()
    config.llm.active_provider = "deepseek"
    
    service = LLMService(
        deepseek_key="deepseek-key",
        gemini_key="gemini-key",
        config=config
    )
    
    # Replace providers with mocks
    mock_deepseek = MockProvider("deepseek", should_fail=True)
    mock_gemini = MockProvider("gemini", should_fail=False)
    service.providers = [mock_deepseek, mock_gemini]
    
    # This should succeed with the gemini provider
    result = service.analyze_with_fallback("test text")
    assert result["provider"] == "gemini"


def test_llm_service_no_providers():
    """LLMサービスがプロバイダーが設定されていない場合にエラーを送出することをテスト"""
    config = AppConfig()
    
    service = LLMService(
        deepseek_key=None,
        gemini_key=None,
        config=config
    )
    
    with pytest.raises(ValueError, match="No LLM providers configured"):
        service.analyze_with_fallback("test text")


def test_llm_service_all_providers_fail():
    """LLMサービスがすべてのプロバイダーが失敗した場合にエラーを送出することをテスト"""
    config = AppConfig()
    config.llm.active_provider = "deepseek"
    
    service = LLMService(
        deepseek_key="deepseek-key",
        gemini_key="gemini-key",
        config=config
    )
    
    # Replace providers with mocks that both fail
    mock_deepseek = MockProvider("deepseek", should_fail=True)
    mock_gemini = MockProvider("gemini", should_fail=True)
    service.providers = [mock_deepseek, mock_gemini]
    
    # This should fail with the error from the last provider that failed (gemini)
    with pytest.raises(Exception, match="gemini provider failed"):
        service.analyze_with_fallback("test text")