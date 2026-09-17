import pytest
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock
from database.models import Bid, Customer, Partner, CustomerBidLink, PartnerBidLink
from services.bid_analysis_service import BidAnalysisService

def test_extract_text_from_pdf(mocker):
    # os.path.exists の動作をモック化してTrueを返すようにする
    mocker.patch("os.path.exists", return_value=True)

    # pdfplumber の動作をモック化
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "これはテスト用の入札仕様書のテキスト本文です。一定以上の長さが必要です。十分に長いテキストを用意することで、最小文字数しきい値をクリアし、エラーを回避します。"
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdf.__enter__.return_value = mock_pdf
    
    mocker.patch("pdfplumber.open", return_value=mock_pdf)
    
    service = BidAnalysisService(session=MagicMock(), llm_service=MagicMock())
    text = service.extract_text_from_pdf("dummy_path.pdf")
    
    assert "テスト用の入札仕様書" in text

def test_analyze_and_save_flow(db_session, mocker):
    # テスト用の Customer と Partner を挿入（必須カラムを設定）
    now = datetime.now(timezone.utc)
    customer = Customer(name="株式会社テストクライアント", company="テストクライアント", memo="AI, 開発, クラウド", created_at=now, updated_at=now)
    partner = Partner(name="パートナー開発会社", category="システム開発", memo="システム開発, 保守", created_at=now, updated_at=now)
    db_session.add_all([customer, partner])
    db_session.commit()

    # pdfplumber をモック化して十分な長さのテキストを返すようにする
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "【件名】AIシステム開発業務調達\n予算は1500万円。工期は2026年12月末。成果物は開発ソースコード一式。参加資格は全省庁統一資格のシステム開発。これはテスト用のダミー仕様書テキストです。"
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdf.__enter__.return_value = mock_pdf
    mocker.patch("pdfplumber.open", return_value=mock_pdf)


    # LLMのレスポンスを定義
    mock_llm_result = {
        "budget": "1,500万円",
        "qualifications": ["全省庁統一資格 A等級またはB等級", "システム開発の実績"],
        "deadline": "2026-12-31",
        "deliverables": "AIシステム開発ソースコードおよびドキュメント一式",
        "key_risks": ["開発スケジュールの遅延リスク"],
        "industry_category": "システム開発",
        "organization_name": "テスト省"
    }
    
    mock_llm_service = MagicMock()
    mock_llm_service.analyze_with_fallback.return_value = mock_llm_result

    # 一時ダミーファイルの存在を確認させる
    mocker.patch("os.path.exists", return_value=True)

    service = BidAnalysisService(session=db_session, llm_service=mock_llm_service)
    
    # 実行
    bid = service.analyze_and_save("dummy_spec.pdf", "https://example.com/spec.pdf", agency_id=1)
    
    # Assertions on Bid record
    assert bid is not None
    assert bid.filename == "dummy_spec.pdf"
    assert bid.budget == "1,500万円"
    assert bid.budget_amount == 15000000  # parse_budgetの確認
    assert bid.deadline == "2026-12-31"
    assert bid.deliverables == "AIシステム開発ソースコードおよびドキュメント一式"

    # 正規化済みフィールドの確認
    # qualifications はリスト→正規化テキスト（改行結合）として保存される
    assert "全省庁統一資格 A等級またはB等級" in bid.qualifications
    assert "システム開発の実績" in bid.qualifications
    # deadline が日付型として delivery_deadline に保存される
    from datetime import date
    assert bid.delivery_deadline == date(2026, 12, 31)
    
    # マッチングリンクが正しく作成されているか確認
    # Customer: memoに「AI」「開発」があり、bidのdeliverablesに「AIシステム開発」が含まれるためマッチするはず
    c_link = db_session.query(CustomerBidLink).filter(CustomerBidLink.bid_id == bid.id).first()
    assert c_link is not None
    assert c_link.customer_id == customer.id
    assert "AI" in c_link.memo or "開発" in c_link.memo
    
    # Partner: memoに「システム開発」があり、bidのqualificationsやテキストに含まれるためマッチするはず
    p_link = db_session.query(PartnerBidLink).filter(PartnerBidLink.bid_id == bid.id).first()
    assert p_link is not None
    assert p_link.partner_id == partner.id


def test_extract_text_from_pdf_normal(mocker):
    """通常PDF: pdfplumber のみで成功 (既存動作の維持確認)"""
    mocker.patch("os.path.exists", return_value=True)
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "これはテスト用の入札仕様書のテキスト本文です。一定以上の長さが必要です。十分に長いテキストを用意することで、最小文字数しきい値をクリアし、エラーを回避します。"
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdf.__enter__.return_value = mock_pdf
    mocker.patch("pdfplumber.open", return_value=mock_pdf)

    service = BidAnalysisService(session=MagicMock(), llm_service=MagicMock())
    text = service.extract_text_from_pdf("dummy_path.pdf")
    assert "テスト用の入札仕様書" in text


def test_extract_text_from_pdf_scanned_ocr_fallback(mocker):
    """スキャンPDF: pdfplumber 空 → is_scanned_pdf True → OCRフォールバック成功"""
    mocker.patch("os.path.exists", return_value=True)
    # Stage 1: pdfplumber は空文字を返す
    mock_page = MagicMock()
    mock_page.extract_text.return_value = ""
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdf.__enter__.return_value = mock_pdf
    mocker.patch("pdfplumber.open", return_value=mock_pdf)
    # スキャン判定を True に強制
    mocker.patch("services.bid_analysis_service.is_scanned_pdf", return_value=True)

    # OCR プロバイダーのモック
    ocr_result = MagicMock()
    ocr_result.full_text = "OCR抽出テキスト " * 20
    ocr_result.average_confidence = 0.85
    mock_provider = MagicMock()
    mock_provider.is_available.return_value = True
    mock_provider.extract_text.return_value = ocr_result
    mocker.patch("services.bid_analysis_service.create_ocr_provider", return_value=mock_provider)

    service = BidAnalysisService(session=MagicMock(), llm_service=MagicMock())
    text = service.extract_text_from_pdf("scanned.pdf")
    assert "OCR抽出テキスト" in text
    mock_provider.extract_text.assert_called_once()


def test_extract_text_from_pdf_scanned_ocr_unavailable(mocker):
    """スキャンPDFだがOCR利用不可 → 品質検証で例外"""
    mocker.patch("os.path.exists", return_value=True)
    mock_page = MagicMock()
    mock_page.extract_text.return_value = ""
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdf.__enter__.return_value = mock_pdf
    mocker.patch("pdfplumber.open", return_value=mock_pdf)
    mocker.patch("services.bid_analysis_service.is_scanned_pdf", return_value=True)

    mock_provider = MagicMock()
    mock_provider.is_available.return_value = False
    mocker.patch("services.bid_analysis_service.create_ocr_provider", return_value=mock_provider)

    service = BidAnalysisService(session=MagicMock(), llm_service=MagicMock())
    import pytest
    with pytest.raises(RuntimeError):
        service.extract_text_from_pdf("scanned.pdf")


def test_ocr_metrics_recording(mocker):
    """OCRフォールバック時のメトリクス記録確認"""
    from ocr.metrics import get_metrics, reset_metrics
    reset_metrics()  # テスト開始前にリセット

    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("services.bid_analysis_service.is_scanned_pdf", return_value=True)

    ocr_result = MagicMock()
    ocr_result.full_text = "OCRテストテキスト" * 20
    ocr_result.average_confidence = 0.85
    mock_provider = MagicMock()
    mock_provider.is_available.return_value = True
    mock_provider.extract_text.return_value = ocr_result
    mocker.patch("services.bid_analysis_service.create_ocr_provider", return_value=mock_provider)

    service = BidAnalysisService(session=MagicMock(), llm_service=MagicMock())
    service.extract_text_from_pdf("scanned.pdf")

    metrics = get_metrics()
    assert metrics.fallback_count == 1
    assert metrics.average_confidence == 0.85


def test_ocr_metrics_normal_extract(mocker):
    """通常抽出時のメトリクス記録確認"""
    from ocr.metrics import get_metrics, reset_metrics
    reset_metrics()

    mocker.patch("os.path.exists", return_value=True)
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "通常テキスト" * 10
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdf.__enter__.return_value = mock_pdf
    mocker.patch("pdfplumber.open", return_value=mock_pdf)

    service = BidAnalysisService(session=MagicMock(), llm_service=MagicMock())
    service.extract_text_from_pdf("normal.pdf")

    metrics = get_metrics()
    assert metrics.normal_extract_count == 1
