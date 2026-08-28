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
        self.last_usage = {"prompt_tokens": 10, "completion_tokens": 5}
        self.model = f"mock-{name}-model"

    def analyze(self, text: str, system_prompt: str) -> Dict[str, Any]:
        if self.should_fail:
            raise Exception(f"{self.name} API error")
        return {"provider": self.name, "summary": "Mock analysis result"}


class TestLLMProviderSwitching:
    """Step 67: LLMプロバイダー切り替えの単体テスト"""

    def test_deepseek_as_active_provider(self):
        """LLM_PROVIDER=deepseek の場合、DeepSeekが優先プロバイダーになること"""
        config = AppConfig()
        config.llm = LLMConfig(active_provider="deepseek")
        
        with patch("services.llm_service.DeepSeekProvider") as mock_ds, \
             patch("services.llm_service.GeminiProvider") as mock_gem:
            ds_instance = MockProvider("deepseek")
            gem_instance = MockProvider("gemini")
            mock_ds.return_value = ds_instance
            mock_gem.return_value = gem_instance

            service = LLMService("ds-key", "gem-key", config)

            assert len(service.providers) == 2
            assert service.providers[0].name == "deepseek"
            assert service.providers[1].name == "gemini"
            assert service.active_provider_name == "deepseek"

    def test_gemini_as_active_provider(self):
        """LLM_PROVIDER=gemini の場合、Geminiが優先プロバイダーになること"""
        config = AppConfig()
        config.llm = LLMConfig(active_provider="gemini")

        with patch("services.llm_service.DeepSeekProvider") as mock_ds, \
             patch("services.llm_service.GeminiProvider") as mock_gem:
            ds_instance = MockProvider("deepseek")
            gem_instance = MockProvider("gemini")
            mock_ds.return_value = ds_instance
            mock_gem.return_value = gem_instance

            service = LLMService("ds-key", "gem-key", config)

            assert len(service.providers) == 2
            # Geminiが先にくること
            assert service.providers[0].name == "gemini"
            assert service.providers[1].name == "deepseek"
            assert service.active_provider_name == "gemini"

    def test_only_deepseek_key(self):
        """Gemini APIキーがない場合、DeepSeekのみが有効になること"""
        config = AppConfig()
        config.llm = LLMConfig(active_provider="deepseek")

        with patch("services.llm_service.DeepSeekProvider") as mock_ds:
            ds_instance = MockProvider("deepseek")
            mock_ds.return_value = ds_instance

            service = LLMService("ds-key", None, config)

            assert len(service.providers) == 1
            assert service.providers[0].name == "deepseek"

    def test_get_active_provider(self):
        """get_active_provider が正しいプロバイダーを返すこと"""
        config = AppConfig()
        config.llm = LLMConfig(active_provider="gemini")

        with patch("services.llm_service.DeepSeekProvider") as mock_ds, \
             patch("services.llm_service.GeminiProvider") as mock_gem:
            ds_instance = MockProvider("deepseek")
            gem_instance = MockProvider("gemini")
            mock_ds.return_value = ds_instance
            mock_gem.return_value = gem_instance

            service = LLMService("ds-key", "gem-key", config)

            active = service.get_active_provider()
            assert active is not None
            assert active.name == "gemini"


class TestLLMFallback:
    """Step 68: LLMフォールバック動作の単体テスト"""

    @patch("services.cost_manager.CostManager")
    def test_primary_success(self, mock_cost):
        """ケース1: プライマリプロバイダーが成功する場合"""
        mock_cost.return_value = MagicMock()

        config = AppConfig()
        config.llm = LLMConfig(active_provider="deepseek")

        with patch("services.llm_service.DeepSeekProvider") as mock_ds, \
             patch("services.llm_service.GeminiProvider") as mock_gem:
            ds_instance = MockProvider("deepseek", should_fail=False)
            gem_instance = MockProvider("gemini", should_fail=False)
            mock_ds.return_value = ds_instance
            mock_gem.return_value = gem_instance

            service = LLMService("ds-key", "gem-key", config)
            result = service.analyze_with_fallback("Test bid text")

            assert result["provider"] == "deepseek"
            assert "summary" in result

    @patch("services.cost_manager.CostManager")
    def test_fallback_to_secondary(self, mock_cost):
        """ケース2: プライマリが失敗し、セカンダリが成功する場合"""
        mock_cost.return_value = MagicMock()

        config = AppConfig()
        config.llm = LLMConfig(active_provider="deepseek")

        with patch("services.llm_service.DeepSeekProvider") as mock_ds, \
             patch("services.llm_service.GeminiProvider") as mock_gem:
            ds_instance = MockProvider("deepseek", should_fail=True)
            gem_instance = MockProvider("gemini", should_fail=False)
            mock_ds.return_value = ds_instance
            mock_gem.return_value = gem_instance

            service = LLMService("ds-key", "gem-key", config)
            result = service.analyze_with_fallback("Test bid text")

            # セカンダリのGeminiが成功すること
            assert result["provider"] == "gemini"

    @patch("services.cost_manager.CostManager")
    def test_both_providers_fail(self, mock_cost):
        """ケース3: 両プロバイダーが失敗する場合、最終エラーがスローされること"""
        mock_cost.return_value = MagicMock()

        config = AppConfig()
        config.llm = LLMConfig(active_provider="deepseek")

        with patch("services.llm_service.DeepSeekProvider") as mock_ds, \
             patch("services.llm_service.GeminiProvider") as mock_gem:
            ds_instance = MockProvider("deepseek", should_fail=True)
            gem_instance = MockProvider("gemini", should_fail=True)
            mock_ds.return_value = ds_instance
            mock_gem.return_value = gem_instance

            service = LLMService("ds-key", "gem-key", config)

            with pytest.raises(Exception) as exc_info:
                service.analyze_with_fallback("Test bid text")

            assert "deepseek API error" in str(exc_info.value) or "gemini API error" in str(exc_info.value)


class TestLLMNoProviderError:
    """Step 69: 両プロバイダー未設定時のエラーハンドリングテスト"""

    @patch("services.cost_manager.CostManager")
    def test_no_providers_configured(self, mock_cost):
        """有効なAPIキーが1つもない場合、ValueErrorがスローされること"""
        mock_cost.return_value = MagicMock()

        config = AppConfig()
        config.llm = LLMConfig(active_provider="deepseek")

        service = LLMService(None, None, config)

        assert len(service.providers) == 0

        with pytest.raises(ValueError) as exc_info:
            service.analyze_with_fallback("Test bid text")

        assert "No LLM providers configured" in str(exc_info.value)

    def test_gemini_key_only_with_deepseek_active(self):
        """active_provider=deepseek だがDeepSeekキーがなく、Geminiキーのみある場合"""
        config = AppConfig()
        config.llm = LLMConfig(active_provider="deepseek")

        with patch("services.llm_service.GeminiProvider") as mock_gem:
            gem_instance = MockProvider("gemini", should_fail=False)
            mock_gem.return_value = gem_instance

            service = LLMService(None, "gem-key", config)

            # DeepSeekはスキップされ、Geminiのみがリストに入る
            assert len(service.providers) == 1
            assert service.providers[0].name == "gemini"

    def test_deepseek_key_only_with_gemini_active(self):
        """active_provider=gemini だがGeminiキーがなく、DeepSeekキーのみある場合"""
        config = AppConfig()
        config.llm = LLMConfig(active_provider="gemini")

        with patch("services.llm_service.DeepSeekProvider") as mock_ds:
            ds_instance = MockProvider("deepseek", should_fail=False)
            mock_ds.return_value = ds_instance

            service = LLMService("ds-key", None, config)

            # Geminiはスキップされ、DeepSeekのみがリストに入る
            assert len(service.providers) == 1
            assert service.providers[0].name == "deepseek"
