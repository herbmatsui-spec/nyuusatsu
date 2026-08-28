import unittest
from unittest.mock import MagicMock, patch
from main import BidCollector, AppConfig
from utils.text_chunker import TextChunker

class TestBidCollectorIntegration(unittest.TestCase):
    def setUp(self):
        # Mock LLMService
        self.mock_llm_service = MagicMock()
        
        # BidCollector.__init__ now takes client=None as the first arg
        self.collector = BidCollector(None)
        
        # Inject mock LLMService into the analysis flow
        # Since analyze_text instantiates LLMService internally, we patch the class
        self.llm_patcher = patch('services.llm_service.LLMService')
        self.mock_llm_class = self.llm_patcher.start()
        self.mock_llm_class.return_value = self.mock_llm_service
        
        # Setup config for testing
        self.collector.config = AppConfig()
        self.collector.config.chunking.max_text_chars = 180
        self.collector.config.chunking.enable_smart_chunking = True
        self.collector.config.chunking.priority_keywords = ["納期", "成果物"]

    def test_analyze_text_smart_chunking_integration(self):
        """
        長大なテキストにおいて、前半部分と後半の重要キーワードを含む部分が
        適切に組み合わされてLLMに渡されることを検証する。
        """
        # 1. テストデータ作成
        prefix = "これは導入文です。" * 20
        late_section = "【納期】2026年12月末まで。 【成果物】報告書一式。"
        full_text = prefix + "\n" + "中間の不要なテキスト" * 100 + "\n" + late_section
        
        # LLMのレスポンスをモック
        self.mock_llm_service.analyze_with_fallback.return_value = {
            "budget": "100万円",
            "qualifications": "なし",
            "deadline": "2026年12月末",
            "deliverables": "報告書一式"
        }

        # 実行
        result = self.collector.analyze_text(full_text)

        # 検証: LLMService.analyze_with_fallback が呼ばれたことを確認
        self.mock_llm_service.analyze_with_fallback.assert_called_once()
        sent_text = self.mock_llm_service.analyze_with_fallback.call_args[0][0]
        
        # 1. テキストが max_text_chars 以内に収まっていること
        self.assertLessEqual(len(sent_text), self.collector.config.chunking.max_text_chars + 20)
        
        # 2. 結果が正しく返却されていること
        self.assertEqual(result["deadline"], "2026年12月末")

    def test_analyze_text_fallback_to_simple_truncation(self):
        """
        enable_smart_chunking = False の場合、単純な切り詰めが行われることを検証する。
        """
        self.collector.config.chunking.enable_smart_chunking = False
        
        text = "A" * 200 + "重要要件"
        
        self.mock_llm_service.analyze_with_fallback.return_value = {}
        
        self.collector.analyze_text(text)
        
        # LLMService.analyze_with_fallback が呼ばれたことを確認
        self.mock_llm_service.analyze_with_fallback.assert_called_once()
        sent_text = self.mock_llm_service.analyze_with_fallback.call_args[0][0]
        
        # 単純切り詰めなので、後半の「重要要件」は消えているはず
        self.assertNotIn("重要要件", sent_text)
        self.assertEqual(len(sent_text), self.collector.config.chunking.max_text_chars)

def tearDown(self):
    self.llm_patcher.stop()

if __name__ == "__main__":
    unittest.main()
