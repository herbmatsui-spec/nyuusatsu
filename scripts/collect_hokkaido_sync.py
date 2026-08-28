"""北海道の入札情報を実際に収集する同期ランナー（Redis/RQ不要・ログ文件出力）。

実行:
  python scripts/collect_hokkaido_sync.py
進捗確認:
  type collect_hokkaido.log
"""
import sys
import os
import codecs
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler("collect_hokkaido.log", encoding="utf-8"),
              logging.StreamHandler(codecs.getwriter("utf-8")(sys.stdout.buffer, "strict"))],
)
logger = logging.getLogger("collect_hokkaido")

from database.engine import SessionLocal
from database.models import Agency, CrawlConfig
from crawler.generic_crawler import GenericCrawler
from crawler.downloader import PDFDownloader
from services.bid_analysis_service import BidAnalysisService
import asyncio


def main():
    session = SessionLocal()
    try:
        hokkaido = session.query(Agency).filter_by(name="北海道").first()
        if not hokkaido:
            logger.error("北海道が見つかりません")
            return

        # 道庁の入札公告ページのみ（ルートはリンクが多すぎるため除外）
        configs = (
            session.query(CrawlConfig)
            .filter_by(agency_id=hokkaido.id, is_active=True)
            .all()
        )
        configs = [c for c in configs if "chotatsu" in c.target_url]
        logger.info("北海道対象CrawlConfig: %d件", len(configs))

        crawler = GenericCrawler(parser_type="heuristic", delay=3.0)
        downloader = PDFDownloader(dest_dir="./temp_pdfs")
        analysis = BidAnalysisService(session)

        total_links = 0
        total_downloaded = 0
        total_saved = 0
        errors = []

        for cfg in configs:
            logger.info("=== クロール: %s ===", cfg.target_url)
            try:
                results = asyncio.run(crawler.crawl_site(cfg.target_url, agency_name=hokkaido.name))
            except Exception as e:
                errors.append("crawl failed %s: %s" % (cfg.target_url, e))
                logger.exception("クロール失敗")
                continue

            pdf_links = [r for r in results if r.is_pdf_link or r.url.lower().endswith(".pdf")]
            logger.info("抽出リンク %d件 (PDF %d件)", len(results), len(pdf_links))
            total_links += len(results)

            for r in pdf_links[:5]:  # 初回は最大5件に抑制
                success, path, sha256, err = downloader.download(r.url)
                if not success or not path:
                    errors.append("download failed %s: %s" % (r.url, err))
                    continue
                total_downloaded += 1
                try:
                    bid = analysis.analyze_and_save(path, r.url, hokkaido.id)
                    total_saved += 1
                    logger.info("保存OK Bid id=%d %s", bid.id, bid.filename)
                except Exception as e:
                    errors.append("analyze failed %s: %s" % (r.url, e))
                    logger.exception("解析失敗")
                finally:
                    try:
                        if path and os.path.exists(path):
                            os.remove(path)
                    except Exception:
                        pass

        session.commit()
        logger.info("================ 結果 ================")
        logger.info("抽出リンク合計: %d", total_links)
        logger.info("ダウンロード:   %d", total_downloaded)
        logger.info("保存(Bid):     %d", total_saved)
        if errors:
            logger.info("エラー: %d件", len(errors))
            for e in errors[:10]:
                logger.info("  - %s", e)
    finally:
        session.close()


if __name__ == "__main__":
    main()
