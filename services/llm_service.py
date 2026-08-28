from typing import Dict, Any, Optional, List
from config import AppConfig
from .providers.base import LLMProvider
from .providers.deepseek import DeepSeekProvider
from .providers.gemini import GeminiProvider

class LLMService:
    """
    Orchestrates LLM calls with primary/secondary fallback.
    """
    def __init__(self, deepseek_key: Optional[str], gemini_key: Optional[str], config: AppConfig):
        self.config = config
        self.providers: List[LLMProvider] = []
        # Configで指定されたactive_providerを優先してリストの先頭に配置する
        active_provider = self.config.llm.active_provider
        
        if active_provider == "deepseek" and deepseek_key:
            self.providers.append(DeepSeekProvider(deepseek_key, config))
        elif active_provider == "gemini" and gemini_key:
            self.providers.append(GeminiProvider(gemini_key, config))
            
        # フォールバック用に残りのプロバイダーを追加
        if active_provider != "deepseek" and deepseek_key:
            self.providers.append(DeepSeekProvider(deepseek_key, config))
        if active_provider != "gemini" and gemini_key:
            self.providers.append(GeminiProvider(gemini_key, config))

    @property
    def active_provider_name(self) -> str:
        """現在優先的に使用されているプロバイダー名を返す"""
        return self.config.llm.active_provider

    def get_active_provider(self) -> Optional[LLMProvider]:
        """現在アクティブなプロバイダーのインスタンスを返す"""
        for p in self.providers:
            p_name = p.__class__.__name__.replace("Provider", "").lower()
            if p_name == self.config.llm.active_provider:
                return p
        return self.providers[0] if self.providers else None

    def analyze_with_fallback(self, text: str) -> Dict[str, Any]:
        """Try providers in order until one succeeds."""
        from services.cost_manager import CostManager
        cost_manager = CostManager()
        
        if not self.providers:
            raise ValueError("No LLM providers configured.")
            
        system_prompt = self.config.llm.system_prompt
        
        last_error = None
        for provider in self.providers:
            try:
                # 優先プロバイダーから順に試行
                result = provider.analyze(text, system_prompt)
                
                # 利用実績を記録
                provider_name = provider.__class__.__name__.replace("Provider", "").lower()
                model_name = getattr(provider, "model", getattr(provider, "model_name", "unknown"))
                
                # Providerインスタンスがlast_usageを保持しているか確認
                usage = getattr(provider, "last_usage", {"prompt_tokens": 0, "completion_tokens": 0})
                cost_manager.record_usage(
                    provider=provider_name,
                    model=model_name,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0)
                )
                
                return result
            except Exception as e:
                # ソフトスキップ（APIキー未設定等）か、実際のエラーかを区別してログに出せるが
                # ここでは単純に次のプロバイダーへフォールバックする
                last_error = e
                continue
        
        raise last_error or Exception("All LLM providers failed or are not configured.")
