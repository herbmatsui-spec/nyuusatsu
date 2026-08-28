import pytest
import os
from unittest.mock import MagicMock, patch
from crawler.pipeline import trigger_agency_crawl, download_pdf_task, crawl_agency_task
from database.models.agency import Agency
from database.models.crawl_config import CrawlConfig
from database.models.pdf_document import PDFDocument
from database.models.customer import Customer
from database.models.links import CustomerBidLink


def test_trigger_agency_crawl(mocker):
    mock_queue = mocker.patch("crawler.pipeline.crawl_queue")
    trigger_agency_crawl(42)
    mock_queue.enqueue.assert_called_once_with(crawl_agency_task, 42)

def test_download_pdf_task_success(db_session, mocker):
    # テスト用の Agency を作成
    agency = Agency(name="テスト省", type="ministry", region="全国")
    db_session.add(agency)
    db_session.commit()
    
    # PDFDownloader.download の動作をモック化
    # (success, file_path, sha256, error_msg)
    mock_file_path = "tests/fixtures/sample.pdf"
    # モック用のダミーファイルを一時的に作成
    os.makedirs(os.path.dirname(mock_file_path), exist_ok=True)
    with open(mock_file_path, "wb") as f:
        f.write(b"mock pdf content")
        
    mocker.patch("crawler.downloader.PDFDownloader.download", return_value=(True, mock_file_path, "hash123456", ""))
    
    try:
        # DBセッションを提供する get_db コンテキストマネージャをモック化して、テスト用の db_session を返すようにする
        mock_get_db = mocker.patch("crawler.pipeline.get_db")
        mock_get_db.return_value.__enter__.return_value = db_session
        
        doc_id = download_pdf_task(agency.id, "仕様書PDF", "https://example.com/spec.pdf", "2026-07-07")
        
        assert doc_id is not None
        
        # DBに保存されたか確認
        pdf_doc = db_session.get(PDFDocument, doc_id)
        assert pdf_doc is not None
        assert pdf_doc.url == "https://example.com/spec.pdf"
        assert pdf_doc.sha256 == "hash123456"
        assert pdf_doc.agency_id == agency.id
        
    finally:
        # 一時ファイルのクリーンアップ
        if os.path.exists(mock_file_path):
            os.remove(mock_file_path)

def test_download_pdf_task_duplicate(db_session, mocker):
    agency = Agency(name="テスト省2", type="ministry", region="全国")
    db_session.add(agency)
    db_session.commit()
    
    # 既存の PDFDocument をDBに登録しておく (ハッシュ値 "duplicate_hash")
    existing_doc = PDFDocument(
        url="https://example.com/old_spec.pdf",
        filename="old.pdf",
        sha256="duplicate_hash",
        file_size=100,
        agency_id=agency.id
    )
    db_session.add(existing_doc)
    db_session.commit()
    
    # PDFDownloader.download をモック化し、同じハッシュ値を返すようにする
    mock_file_path = "tests/fixtures/dup_sample.pdf"
    os.makedirs(os.path.dirname(mock_file_path), exist_ok=True)
    with open(mock_file_path, "wb") as f:
        f.write(b"mock pdf content")
        
    mocker.patch("crawler.downloader.PDFDownloader.download", return_value=(True, mock_file_path, "duplicate_hash", ""))
    
    try:
        mock_get_db = mocker.patch("crawler.pipeline.get_db")
        mock_get_db.return_value.__enter__.return_value = db_session
        
        # 重複ダウンロードタスクの実行
        doc_id = download_pdf_task(agency.id, "重複仕様書", "https://example.com/new_spec.pdf", "2026-07-07")
        
        # 既存のドキュメントIDが返されることを検証
        assert doc_id == existing_doc.id
        
        # 重複ファイルであるため、一時ダウンロードファイルが削除されていることを確認
        assert not os.path.exists(mock_file_path)
        
    finally:
        if os.path.exists(mock_file_path):
            os.remove(mock_file_path)

@pytest.mark.asyncio
async def test_crawl_agency_async_flow(db_session, mocker):
    # テスト用データ準備
    agency = Agency(name="テスト自治体X", type="municipality", region="東京都")
    db_session.add(agency)
    db_session.commit()
    
    config = CrawlConfig(
        agency_id=agency.id,
        target_url="https://example.com/nyusatsu.html",
        parser_type="heuristic",
        frequency="daily",
        is_active=True
    )
    db_session.add(config)
    db_session.commit()
    
    # すでに登録済みのURL
    existing_pdf = PDFDocument(
        url="https://example.com/old_spec.pdf",
        filename="old.pdf",
        sha256="old_hash",
        file_size=50,
        agency_id=agency.id
    )
    db_session.add(existing_pdf)
    db_session.commit()
    
    # GenericCrawler.crawl_site のモック化
    # 2件のリンクを返す（1件は既存URL、1件は新規URL）
    from crawler.models.crawl_result import CrawlResult
    mock_results = [
        CrawlResult(title="既存仕様書", url="https://example.com/old_spec.pdf", agency_name="テスト自治体X"),
        CrawlResult(title="新規仕様書", url="https://example.com/new_spec.pdf", agency_name="テスト自治体X")
    ]
    mocker.patch("crawler.generic_crawler.GenericCrawler.crawl_site", new_callable=mocker.AsyncMock, return_value=mock_results)

    
    # download_queue.enqueue のモック化
    mock_download_queue = mocker.patch("crawler.pipeline.download_queue")
    
    mock_get_db = mocker.patch("crawler.pipeline.get_db")
    mock_get_db.return_value.__enter__.return_value = db_session
    
    from crawler.pipeline import crawl_agency_async
    results = await crawl_agency_async(config.id)
    
    # クロール結果の件数確認
    assert len(results) == 2
    
    # 新規リンクのみダウンロードキューに登録されたことを検証
    # (既存リンク https://example.com/old_spec.pdf はスキップされるため、enqueueは1回だけ呼ばれる)
    mock_download_queue.enqueue.assert_called_once_with(
        download_pdf_task,
        agency.id,
        "新規仕様書",
        "https://example.com/new_spec.pdf",
        "不明"
    )

def test_full_pipeline_integration(db_session, mocker):
    # テスト用データ準備
    agency = Agency(name="統合テスト自治体", type="municipality", region="東京都")
    customer = Customer(name="顧客A", memo="AI")
    db_session.add_all([agency, customer])
    db_session.commit()

    # 1. download_pdf_task のテスト (PDFダウンロード -> メタデータ保存 -> 解析ジョブ登録)
    mock_file_path = "tests/fixtures/sample_pipeline.pdf"
    os.makedirs(os.path.dirname(mock_file_path), exist_ok=True)
    with open(mock_file_path, "wb") as f:
        f.write(b"mock pipeline pdf content")

    mocker.patch("crawler.downloader.PDFDownloader.download", return_value=(True, mock_file_path, "sha256_pipeline_test", ""))
    mock_analysis_queue = mocker.patch("crawler.pipeline.analysis_queue")
    
    mock_get_db = mocker.patch("crawler.pipeline.get_db")
    mock_get_db.return_value.__enter__.return_value = db_session

    try:
        # ダウンロードタスク実行
        pdf_doc_id = download_pdf_task(agency.id, "仕様書", "https://example.com/spec.pdf", "2026-07-07")
        
        assert pdf_doc_id is not None
        # 解析ジョブが登録されたことを検証
        mock_analysis_queue.enqueue.assert_called_once_with(
            mocker.ANY, # analyze_pdf_task 関数オブジェクト
            pdf_doc_id,
            mock_file_path,
            "https://example.com/spec.pdf",
            agency.id
        )

        # 2. analyze_pdf_task のテスト (解析 -> マッチング -> 通知ジョブ登録)
        # pdfplumber と LLMService をモック化
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "AIシステム開発の仕様書です。予算は1000万。これは十分な長さを持つテスト用ダミーテキストです。仕様書要件抽出のため、最小文字数制限を回避します。"
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__.return_value = mock_pdf
        mocker.patch("pdfplumber.open", return_value=mock_pdf)


        mocker.patch("os.path.exists", return_value=True)

        mock_llm_result = {
            "budget": "1,000万円",
            "qualifications": ["全省庁統一資格"],
            "deadline": "2026-12",
            "deliverables": "AIソースコード",
            "key_risks": [],
            "industry_category": "システム開発",
            "organization_name": "統合テスト自治体"
        }
        mock_llm_service = MagicMock()
        mock_llm_service.analyze_with_fallback.return_value = mock_llm_result
        mocker.patch("services.bid_analysis_service.LLMService", return_value=mock_llm_service)

        mock_notification_queue = mocker.patch("crawler.pipeline.notification_queue")

        # 解析タスク実行
        from crawler.pipeline import analyze_pdf_task
        bid_id = analyze_pdf_task(pdf_doc_id, mock_file_path, "https://example.com/spec.pdf", agency.id)

        assert bid_id is not None
        
        # Bid/CustomerBidLinkが保存されているか検証
        from database.models import Bid
        bid_record = db_session.get(Bid, bid_id)
        assert bid_record is not None
        assert bid_record.budget == "1,000万円"
        
        c_link = db_session.query(CustomerBidLink).filter(
            CustomerBidLink.bid_id == bid_id,
            CustomerBidLink.customer_id == customer.id
        ).first()
        assert c_link is not None


        # 通知ジョブが登録されたことを検証
        mock_notification_queue.enqueue.assert_called_once_with(
            mocker.ANY, # send_new_bid_notification_task
            bid_id
        )

        # 3. send_new_bid_notification_task のテスト
        # SystemSetting に Slack Webhook URL をダミー登録
        from database.models.crawl import SystemSetting
        db_session.add(SystemSetting(key="slack_webhook_url", value="https://hooks.slack.com/services/dummy"))
        db_session.commit()

        mock_post = mocker.patch("requests.post")
        
        # 通知タスク実行
        from crawler.pipeline import send_new_bid_notification_task
        send_new_bid_notification_task(bid_id)

        # SlackへのPOSTリクエストが送信されたことを検証
        mock_post.assert_called_once()
        sent_payload = mock_post.call_args[1]["json"]
        assert "🔔 【新着入札案件検知】" in sent_payload["text"]
        assert "統合テスト自治体" in sent_payload["text"]

    finally:
        try:
            if os.path.exists(mock_file_path):
                os.remove(mock_file_path)
        except FileNotFoundError:
            pass


