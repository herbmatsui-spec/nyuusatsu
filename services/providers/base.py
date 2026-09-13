from abc import ABC, abstractmethod
from typing import Dict, Any
from config import AppConfig

class LLMProvider(ABC):
    @abstractmethod
    def analyze(self, text: str, system_prompt: str) -> Dict[str, Any]:
        pass