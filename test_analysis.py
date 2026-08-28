import sys
import os
from unittest.mock import MagicMock

# プロジェクトルートをパスに追加
sys.path.append(os.getcwd())

from services.bid_analysis_service import BidAnalysisService

from database.session import get_db
from config import AppConfig

# 実際のセッション
with get_db() as session:
    # サービス初期化
    service = BidAnalysisService(session)

    # テスト用テキスト
    text = """
    入札公告
    件名：宇和島市庁舎清掃業務
    予算：1,000,000円
    期限：2026年12月31日
    成果物：清掃完了報告書
    参加資格：全省庁統一資格A等級
    """

    # 解析実行
    print("解析を開始します...")
    # LLMService が設定されているか確認
    if service.llm_service.providers:
        result = service.llm_service.analyze_with_fallback(text)
        print(result)
    else:
        print("LLMプロバイダーが設定されていません。")
