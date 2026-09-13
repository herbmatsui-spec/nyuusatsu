import unittest
from unittest.mock import MagicMock, patch
from services.qualification_normalizer import QualificationNormalizer
from services.llm_service import LLMService
from config_dir import AppConfig

class TestQualificationNormalizerIntegration(unittest.TestCase):
    """ルールベースマッチングとLLMマッチングの統合テスト"""
    def setUp(self):
        # Mock LLMService
        self.mock_llm_service = MagicMock()
        
        # Create QualificationNormalizer with mock LLM service
        self.normalizer = QualificationNormalizer(llm_service=self.mock_llm_service)
        
        # Load master tags for testing
        self.master_tags = self.normalizer._load_tags()
        if not self.master_tags:
            self.master_tags = [
                {"tag_code": "GEN-A", "display_name": "一般公募"},
                {"tag_code": "GEN-B", "display_name": "一般企業"},
                {"tag_code": "GEN-C", "display_name": "官公立"},
            ]
            
    def test_normalize_rule_based_match(self):
        """ルールベースマッチングが機能栧ed -. - <img>"""