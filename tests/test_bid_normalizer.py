"""
Tests for Bid Normalizer - Improved Coverage
"""
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock
import json

# Create a mock module for google.genai to avoid import errors
mock_genai = MagicMock()
mock_genai.Client = MagicMock()
mock_genai.types = MagicMock()

# Register the mock modules in sys.modules before importing anything
sys.modules['google'] = MagicMock()
sys.modules['google.genai'] = mock_genai
sys.modules['google.genai.types'] = mock_genai.types


class TestBidNormalizer:
    """BidNormalizerクラスのテスト"""

    @pytest.fixture
    def normalizer_with_api_key(self):
        """APIキーありのBidNormalizerのインスタンスを提供"""
        with patch('services.bid_normalizer.genai.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            from services.bid_normalizer import BidNormalizer
            return BidNormalizer(api_key="test-api-key"), mock_client

    @pytest.fixture
    def normalizer_without_api_key(self):
        """APIキーなしのBidNormalizerのインスタンスを提供"""
        from services.bid_normalizer import BidNormalizer
        return BidNormalizer(api_key=None)

    @pytest.fixture
    def qualification_tag(self):
        """QualificationTagのインスタンスを提供"""
        from services.bid_normalizer import QualificationTag
        return QualificationTag

    def test_init_with_api_key(self, normalizer_with_api_key):
        """APIキーありでの初期化のテスト"""
        normalizer, mock_client = normalizer_with_api_key
        assert normalizer.api_key == "test-api-key"
        assert normalizer.client == mock_client
        # WARNINGログが出ないことを確認（省略）

    def test_init_without_api_key(self, normalizer_without_api_key):
        """APIキーなしでの初期化のテスト"""
        assert normalizer_without_api_key.api_key is None
        assert normalizer_without_api_key.client is None
        # WARNINGログが出ることを確認はログキャプチャが必要なので省略

    def test_extract_bid_metrics_success(self, normalizer_with_api_key):
        """入札情報抽出の成功ケースのテスト"""
        normalizer, mock_client = normalizer_with_api_key
        
        # LLMレスポンスのモック - 直接文字列を返すようにモック
        expected_json = json.dumps({
            "budget": "1,000,000円",
            "qualifications": "全省庁統一資格 ランクB以上",
            "deadline": "2024年12月31日",
            "deliverables": "システム設計書、実装ソースコード",
            "justification": "重要なインフラプロジェクト"
        })
        mock_client.analyze.return_value = expected_json
        
        # 実行
        result = normalizer.extract_bid_metrics("サンプル入札テキスト")
        
        # 検証
        assert result["budget"] == "1,000,000円"
        assert result["qualifications"] == "全省庁統一資格 ランクB以上"
        assert result["deadline"] == "2024年12月31日"
        assert result["deliverables"] == "システム設計書、実装ソースコード"
        assert result["justification"] == "重要なインフラプロジェクト"
        
        # モックが正しく呼ばれたことを確認
        mock_client.analyze.assert_called_once()
        call_args = mock_client.analyze.call_args
        assert "サンプル入札テキスト" in call_args[1]["prompt"]

    def test_extract_bid_metrics_exception(self, normalizer_with_api_key):
        """入札情報抽出の例外ケースのテスト"""
        normalizer, mock_client = normalizer_with_api_key
        
        # 例外を発生させるモック
        mock_client.analyze.side_effect = Exception("API Error")
        
        # 実行
        result = normalizer.extract_bid_metrics("サンプル入札テキスト")
        
        # 検証
        assert result == {}  # 例外時は空辞書を返す
        
        # モックが正しく呼ばれたことを確認
        mock_client.analyze.assert_called_once()

    def test_extract_bid_metrics_no_client(self, normalizer_without_api_key):
        """クライアントがない場合の入札情報抽出のテスト"""
        # 実行
        result = normalizer_without_api_key.extract_bid_metrics("サンプル入札テキスト")
        
        # 検証
        assert result == {}  # クライアントがない場合も空辞書を返す

    def test_normalize_qualification_success(self, normalizer_with_api_key):
        """資格正規化の成功ケースのテスト"""
        normalizer, mock_client = normalizer_with_api_key
        
        # LLMレスポンスのモック - str()で文字列に変換してjson.loadsでパースできるようにモック
        mock_response = Mock()
        mock_response.__str__ = Mock(return_value=json.dumps({
            "tag_code": "U_QUAL_B",
            "confidence_score": 0.95
        }))
        mock_client.analyze.return_value = mock_response
        
        # 実行
        result = normalizer.normalize_qualification("全省庁統一資格 ランクBを保有")
        
        # 検証
        assert len(result) == 1
        assert result[0].tag_code == "U_QUAL_B"
        assert result[0].display_name == "全省庁統一資格 ランクB"
        assert result[0].category == "統一資格"
        assert "中規模プロジェクト対象ランク" in result[0].description
        
        # モックが正しく呼ばれたことを確認
        mock_client.analyze.assert_called_once()

    def test_normalize_qualification_low_confidence(self, normalizer_with_api_key):
        """低確信度の資格正規化のテスト"""
        normalizer, mock_client = normalizer_with_api_key
        
        # LLMレスポンスのモック（低確信度）
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "tag_code": "U_QUAL_C",
            "confidence_score": 0.05  # 0.1以下なのでUNMATCHED扱いになる
        })
        mock_client.analyze.return_value = mock_response
        
        # 実行
        result = normalizer.normalize_qualification("不明確な資格")
        
        # 検証：低確信度なのでフォールバック処理が発動
        assert len(result) == 1
        # フォールバックではキーワードマッピングが試される
        # 今回のテキストにはマッチするキーワードがないのでデフォルトのU_QUAL_Cになるはず
        assert result[0].tag_code == "U_QUAL_C"

    def test_normalize_qualification_exception(self, normalizer_with_api_key):
        """資格正規化の例外ケースのテスト"""
        normalizer, mock_client = normalizer_with_api_key
        
        # 例外を発生させるモック
        mock_client.analyze.side_effect = Exception("API Error")
        
        # 実行
        result = normalizer.normalize_qualification("サンプル資格テキスト")
        
        # 検証：例外時は空リストを返す
        assert result == []
        
        # モックが正しく呼ばれたことを確認
        mock_client.analyze.assert_called_once()

    def test_normalize_qualification_no_client(self, normalizer_without_api_key):
        """クライアントがない場合の資格正規化のテスト"""
        # 実行
        result = normalizer_without_api_key.normalize_qualification("サンプル資格テキスト")
        
        # 検証
        assert result == []  # クライアントがない場合も空リストを返す

    def test_normalize_qualification_json_decode_error(self, normalizer_with_api_key):
        """JSONデコードエラーの資格正規化のテスト"""
        normalizer, mock_client = normalizer_with_api_key
        
        # JSONデコードエラーを引き起こすモックレスポンス - str()で変換するとJSONじゃない文字列になる
        mock_response = Mock()
        mock_response.__str__ = Mock(return_value="Invalid JSON Response")
        mock_client.analyze.return_value = mock_response
        
        # 実行
        result = normalizer.normalize_qualification("サンプル資格テキスト")
        
        # 検証：JSONデコードエラー時はフォールバック処理が発動
        assert len(result) == 1
        # デフォルトではU_QUAL_Cになるはず
        assert result[0].tag_code == "U_QUAL_C"

    def test_normalize_qualification_keyword_matching(self, normalizer_with_api_key):
        """キーワードマッチングによる資格正規化のテスト"""
        normalizer, mock_client = normalizer_with_api_key
        
        # LLMがUNMATCHEDを返すが、フォールバックのキーワードマッチングが発動するケース
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "tag_code": "UNMATCHED",
            "confidence_score": 0.0
        })
        mock_client.analyze.return_value = mock_response
        
        # 実行：「土木」というキーワードを含むテキスト
        result = normalizer.normalize_qualification("土木工事の経験があること")
        
        # 検証
        assert len(result) == 1
        assert result[0].tag_code == "LIC_CONSTRUCTION_A"
        assert result[0].display_name == "建設業許可（特定建設業"
        assert result[0].category == "業種許可"
        assert "道路・土木工事等の実績ある業者" in result[0].description

    def test_normalize_qualification_multiple_results(self, normalizer_with_api_key):
        """複数の資格を正規化するテスト（現在の実装では1つずつ処理されるため、複数回呼び出しをシミュレート）"""
        normalizer, mock_client = normalizer_with_api_key
        
        # 最初の呼び出し
        mock_response1 = Mock()
        mock_response1.__str__ = Mock(return_value=json.dumps({
            "tag_code": "U_QUAL_A",
            "confidence_score": 0.98
        }))
        # 2回目の呼び出し
        mock_response2 = Mock()
        mock_response2.__str__ = Mock(return_value=json.dumps({
            "tag_code": "LIC_TELECOM",
            "confidence_score": 0.92
        }))
        
        mock_client.analyze.side_effect = [mock_response1, mock_response2]
        
        # 実行：2つの異なる資格テキストを正規化
        result1 = normalizer.normalize_qualification("全省庁統一資格を保有")
        result2 = normalizer.normalize_qualification("電気通信事業の許可があること")
        
        # 検証
        assert len(result1) == 1
        assert result1[0].tag_code == "U_QUAL_A"
        assert len(result2) == 1
        assert result2[0].tag_code == "LIC_TELECOM"
        
        # モックが2回呼ばれたことを確認
        assert mock_client.analyze.call_count == 2

    def test_load_standard_tags(self, normalizer_with_api_key):
        """標準タグマスターの取得テスト"""
        normalizer, _ = normalizer_with_api_key
        
        # 実行
        result = normalizer._load_standard_tags()
        
        # 検証
        assert isinstance(result, dict)
        assert "U_QUAL_A" in result
        assert "U_QUAL_B" in result
        assert "U_QUAL_C" in result
        assert "LIC_CONSTRUCTION_A" in result
        assert "LIC_TELECOM" in result
        assert "EXP_BPO_3Y" in result
        assert "SEC_INFO" in result
        
        # 各タグの詳細を検証
        assert result["U_QUAL_A"]["display_name"] == "全省庁統一資格 ランクA"
        assert result["U_QUAL_A"]["category"] == "統一資格"
        assert result["U_QUAL_A"]["description"] == "国家レベルの最高等級資格"

    def test_qualification_tag_dataclass(self, qualification_tag):
        """QualificationTagデータクラスのテスト"""
        # 実行
        tag = qualification_tag(
            tag_code="U_QUAL_A",
            display_name="全省庁統一資格 ランクA",
            category="統一資格",
            description="国家レベルの最高等級資格"
        )
        
        # 検証
        assert tag.tag_code == "U_QUAL_A"
        assert tag.display_name == "全省庁統一資格 ランクA"
        assert tag.category == "統一資格"
        assert tag.description == "国家レベルの最高等級資格"

        # デフォルト値のテスト
        tag_default = qualification_tag()
        assert tag_default.tag_code == ""
        assert tag_default.display_name == ""
        assert tag_default.category == ""
        assert tag_default.description == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])