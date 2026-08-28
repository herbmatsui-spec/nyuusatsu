# 改善点1 ステップ13-17: services/pipeline_service.py
# 【DEPRECATED】このサービスは PipelineOrchestrator による非同期イベント駆動パイプラインに置き換えられました。
# 抽出されたリンクからPDFをダウンロードし、解析してDBに保存するエンドツーエンドのパイプラインを実装します。

import os
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from crawler.models.crawl_result import CrawlResult
from crawler.downloader import Downloader
from utils.temp_manager import TempDirManager
from services.bid_analysis_service import BidAnalysisService
from database.session import SessionLocal

logger = logging.getLogger("PipelineService")

class PipelineService:
    """
    【DEPRECATED】
    クロール結果の処理からDB保存までを統合管理するサービス。
    現在は PipelineOrchestrator を使用してください。
    """
    def __init__(self, analysis_service: BidAnalysisService):
        self.analysis_service = analysis_service
        self.downloader = Downloader()
        self.temp_manager = TempDirManager()

    async def process_crawl_results(self, results: List[CrawlResult], agency_name: str, agency_id: Optional[int] = None):
        """
        【DEPRECATED】
        抽出されたリンク一覧を処理し、PDFのダウンロードから解析・保存までを行う。
        今後は PipelineOrchestrator.start_pipeline を使用してください。
        """
        import warnings
        warnings.warn(
            "PipelineService.process_crawl_results is deprecated. Use PipelineOrchestrator.start_pipeline instead.",
            DeprecationWarning,
            stacklevel=2
        )
        if not results:
            logger.info(f"No results to process for {agency_name}")
            return

        logger.info(f"Starting pipeline for {agency_name}: {len(results)} items found.")
        
        # 1. 処理用の一時ディレクトリを作成
        temp_dir = self.temp_manager.create()
        
        processed_count = 0
        failed_count = 0

        try:
            for result in results:
                try:
                    # PDFリンクであるか確認
                    if not result.url.lower().endswith('.pdf'):
                        logger.debug(f"Skipping non-PDF URL: {result.url}")
                        continue

                    # ファイル名の決定 (URLから抽出または生成)
                    filename = result.url.split('/')[-1]
                    if not filename or '.' not in filename:
                        import uuid
                        filename = f"bid_{uuid.uuid4().hex[:8]}.pdf"
                    
                    dest_path = temp_dir / filename

                    # 2. ダウンロード
                    success = self.downloader.download_pdf(result.url, dest_path)
                    if not success:
                        logger.error(f"Failed to download PDF: {result.url}")
                        failed_count += 1
                        continue

                    # 3. 解析と保存
                    # BidAnalysisService.analyze_and_save を呼び出す
                    # 注: analyze_and_save は内部的に DB セッションを扱うため、
                    # analysis_service が適切に session を保持している前提
                    self.analysis_service.analyze_and_save(
                        pdf_path=str(dest_path),
                        source_url=result.url,
                        agency_id=agency_id
                    )
                    
                    processed_count += 1
                    logger.info(f"Successfully processed: {filename}")

                except Exception as e:
                    logger.exception(f"Error processing item {result.url}: {e}")
                    failed_count += 1

        finally:
            # 4. 一時ディレクトリのクリーンアップ
            self.temp_manager.cleanup(temp_dir)

        logger.info(f"Pipeline completed for {agency_name}. Processed: {processed_count}, Failed: {failed_count}")
        return {"processed": processed_count, "failed": failed_count}
