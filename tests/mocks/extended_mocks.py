import json
import requests
from unittest.mock import MagicMock

class MockLLMResponse:
    """LLM APIのレスポンスをシミュレートするクラス"""
    def __init__(self, content, status_code=200):
        self.content = content
        self.status_code = status_code

    def json(self):
        return json.loads(self.content)

def mock_llm_api_call(prompt, model="gemini-3.1-flash-lite"):
    """Gemini/DeepSeek API呼び出しのモック"""
    # 正常系レスポンス
    success_content = json.dumps({
        "budget": "1,000,000円",
        "qualifications": ["全省庁統一資格 ランクB以上", "システム開発実績あり"],
        "deadline": "2026年12月末日",
        "deliverables": "システム設計書、実装ソースコード、テスト報告書",
        "key_risks": ["納期が非常にタイトであること", "特殊なAPI連携が必要"],
        "industry_category": "システム開発",
        "organization_name": "経済産業省"
    })
    
    return MockLLMResponse(success_content)

class MockSession(requests.Session):
    """requests.Sessionのモック"""
    def get(self, url, *args, **kwargs):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><h1>Mock Page</h1><a href='test.pdf'>PDF Link</a></body></html>"
        mock_response.raise_for_status = lambda: None
        return mock_response

    def post(self, url, *args, **kwargs):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success"}
        return mock_response
