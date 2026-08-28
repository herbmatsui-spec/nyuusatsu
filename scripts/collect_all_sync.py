"""
全国入札情報同期クローラー（全県対応・Redis/RQ不要）

Usage:
    python scripts/collect_all_sync.py
    python scripts/collect_all_sync.py --prefecture-name "北海道" --limit 3
    python scripts/collect_all_sync.py --dry-run --prefecture-name "北海道"
    python scripts/collect_all_sync.py --log-file logs/collect_all_SYNC.log
"""
import sys
import os
import io

# PowerShell UTF-8対応: cp932 codec エラー回避
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
import logging
import time
import argparse
import random
import traceback
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from database.session import get_db
from database.models import Prefecture, Agency, CrawlConfig, Bid
from database.repositories.pdf_repository import PDFRepository
from crawler.generic_crawler import GenericCrawler
from crawler.downloader import PDFDownloader
from crawler.models.crawl_result import CrawlResult
from services.bid_analysis_service import BidAnalysisService


def setup_logging(log_file: Optional[str] = None) -> logging.Logger:
    logger = logging.getLogger("CollectAll")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


def get_args():
    parser = argparse.ArgumentParser(description="全国入札情報同期クローラー")
    parser.add_argument("--prefecture-id", type=int, default=None)
    parser.add_argument("--prefecture-name", type=str, default=None)
    parser.add_argument("--limit", type=int, default=5, help="1Agencyあたりの最大PDF処理件数")
    parser.add_argument("--agencies-limit", type=int, default=None, help="1県あたりの最大Agency処理件数")
    parser.add_argument("--dry-run", action="store_true", help="クロールのみ（DL+解析スキップ）")
    parser.add_argument("--log-file", type=str, default=None, help="ログファイルパス")
    parser.add_argument("--crawl-delay", type=float, default=5.0)
    parser.add_argument("--parser-type", type=str, default="heuristic",
                        choices=["heuristic", "rss", "llm", "agency_specific"])
    parser.add_argument("--shuffle", action="store_true", help="処理順シャッフル")
    parser.add_argument("--insecure", action="store_true", help="SSL証明書検証をスキップ")
    parser.add_argument("--resume", action="store_true", help="前回中断の続きから再開（処理済みAgencyをスキップ）")
    return parser.parse_args()


def crawl_and_process(
    cfg: CrawlConfig,
    agency_name: str,
    downloader: PDFDownloader,
    analysis: BidAnalysisService,
    logger: logging.Logger,
    dry_run: bool = False,
    limit: int = 5,
    delay: float = 5.0,
    parser_type: str = "heuristic",
) -> dict:
    result = {
        "config_id": cfg.id,
        "url": cfg.target_url,
        "links_found": 0,
        "pdf_found": 0,
        "downloaded": 0,
        "saved": 0,
        "skipped": 0,
        "errors": 0,
    }
    try:
        import asyncio
        crawler = GenericCrawler(parser_type=parser_type, delay=delay)
        crawl_results: List[CrawlResult] = asyncio.run(asyncio.wait_for(
            crawler.crawl_site(cfg.target_url, agency_name=agency_name),
            timeout=120
        ))
    except asyncio.TimeoutError:
        logger.warning(f"  クロールタイムアウト(120s) [{cfg.target_url}]")
        result["errors"] += 1
        return result
    except Exception as e:
        logger.warning(f"  クロール失敗 [{cfg.target_url}]: {e}")
        result["errors"] += 1
        return result

    result["links_found"] = len(crawl_results)
    pdf_links = [r for r in crawl_results if r.is_pdf_link or r.url.lower().endswith(".pdf")]
    result["pdf_found"] = len(pdf_links)

    logger.info(f"  -> {cfg.target_url}")
    logger.info(f"     取得リンク: {len(crawl_results)}件 / PDF: {len(pdf_links)}件")

    if dry_run:
        return result

    pdf_repo = PDFRepository(analysis.session)

    processed = 0
    for r in pdf_links:
        if processed >= limit:
            logger.info(f"     上限({limit}件)達: {len(pdf_links) - processed}件スキップ")
            result["skipped"] += len(pdf_links) - processed
            break

        # URL既知チェック: 既にDBに保存済みならスキップ
        if pdf_repo.exists_by_url(r.url):
            logger.info(f"     URL既知スキップ: {r.url}")
            result["skipped"] += 1
            continue

        success, path, sha256, err = downloader.download(r.url)
        if not success or not path:
            result["errors"] += 1
            continue

        # SHA256重複チェック
        if sha256 and pdf_repo.exists_by_sha256(sha256):
            logger.info(f"     SHA256重複スキップ: {r.url}")
            result["skipped"] += 1
            try:
                os.remove(path)
            except Exception:
                pass
            continue

        result["downloaded"] += 1

        try:
            bid = analysis.analyze_and_save(path, r.url, cfg.agency_id)
            result["saved"] += 1
            logger.info(f"     保存OK bid_id={bid.id} {bid.filename}")
        except Exception as e:
            result["errors"] += 1
            logger.warning(f"     解析失敗 [{r.url}]: {e}")
        finally:
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

        processed += 1

    # CrawlLog にクロール結果を記録
    try:
        from database.models.crawl_log import CrawlLog
        status = "success" if result["errors"] == 0 else "partial"
        log = CrawlLog(
            agency_id=cfg.agency_id,
            status=status,
            new_bids_count=result["saved"],
            error_message=f"links={result['links_found']},pdf={result['pdf_found']},dl={result['downloaded']},err={result['errors']}"
        )
        analysis.session.add(log)
        analysis.session.flush()
    except Exception as log_err:
        logger.warning(f"     CrawlLog記録失敗: {log_err}")

    return result


def main() -> None:
    args = get_args()
    logger = setup_logging(args.log_file)

    with get_db() as session:
        query = session.query(Prefecture).order_by(Prefecture.id)
        if args.prefecture_id:
            query = query.filter(Prefecture.id == args.prefecture_id)
        elif args.prefecture_name:
            query = query.filter(Prefecture.name.like(f"%{args.prefecture_name}%"))

        prefectures = query.all()
        if not prefectures:
            logger.error(f"対象県が見つかりません name={args.prefecture_name} id={args.prefecture_id}")
            return

        if args.shuffle:
            random.shuffle(prefectures)

        logger.info(f"========== 全国入札情報同步開始 ==========")
        logger.info(f"対象県数: {len(prefectures)}")
        logger.info(f"1Agency最大PDF: {args.limit}件")
        logger.info(f"ドライラン: {args.dry_run}")

        total = {
            "prefectures_processed": 0,
            "agencies_processed": 0,
            "configs_processed": 0,
            "total_links": 0,
            "total_pdfs": 0,
            "total_downloaded": 0,
            "total_saved": 0,
            "total_errors": 0,
        }

        for pref in prefectures:
            agencies = (
                session.query(Agency)
                .filter(Agency.region == pref.name)
                .join(CrawlConfig, CrawlConfig.agency_id == Agency.id)
                .filter(CrawlConfig.is_active == True)
                .distinct()
                .all()
            )
            if not agencies:
                logger.info(f"[{pref.id}] {pref.name}: 対象Agencyなし")
                continue

            if args.agencies_limit:
                agencies = agencies[:args.agencies_limit]

            logger.info(f"")
            logger.info(f"========== [{pref.id}] {pref.name} (Agency {len(agencies)}件) ==========")

            downloader = PDFDownloader(dest_dir="./temp_pdfs", insecure=args.insecure)
            analysis = BidAnalysisService(session)

            for agency_idx, agency in enumerate(agencies, 1):
                # --resume: 直近24時間以内にCrawlLog記録があるAgencyはスキップ
                if args.resume:
                    from database.models.crawl_log import CrawlLog
                    from datetime import datetime, timedelta
                    recent_log = (
                        session.query(CrawlLog)
                        .filter(CrawlLog.agency_id == agency.id)
                        .filter(CrawlLog.crawled_at >= datetime.utcnow() - timedelta(hours=24))
                        .first()
                    )
                    if recent_log:
                        logger.info(f"  {agency.name}: 直近24h内に処理済み → スキップ")
                        continue

                configs = (
                    session.query(CrawlConfig)
                    .filter_by(agency_id=agency.id, is_active=True)
                    .all()
                )
                pct = agency_idx / len(agencies) * 100
                logger.info(f"  [{agency_idx}/{len(agencies)}] ({pct:.0f}%) {agency.name}: Config {len(configs)}件")

                for cfg in configs:
                    summary = crawl_and_process(
                        cfg=cfg,
                        agency_name=agency.name,
                        downloader=downloader,
                        analysis=analysis,
                        logger=logger,
                        dry_run=args.dry_run,
                        limit=args.limit,
                        delay=args.crawl_delay,
                        parser_type=args.parser_type,
                    )

                    total["agencies_processed"] += 1
                    total["configs_processed"] += 1
                    total["total_links"] += summary["links_found"]
                    total["total_pdfs"] += summary["pdf_found"]
                    total["total_downloaded"] += summary["downloaded"]
                    total["total_saved"] += summary["saved"]
                    total["total_errors"] += summary["errors"]

                    session.commit()

            total["prefectures_processed"] += 1

        logger.info(f"")
        logger.info(f"========== 完了サマリー ==========")
        logger.info(f"処理県数:   {total['prefectures_processed']}")
        logger.info(f"処理Agency: {total['agencies_processed']}")
        logger.info(f"処理Config: {total['configs_processed']}")
        logger.info(f"取得リンク: {total['total_links']}")
        logger.info(f"PDF候補:   {total['total_pdfs']}")
        logger.info(f"ダウンロード: {total['total_downloaded']}")
        logger.info(f"保存Bid:   {total['total_saved']}")
        logger.info(f"エラー:    {total['total_errors']}")

        bid_count = session.query(Bid).count()
        logger.info(f"DB Bid合計: {bid_count}件")


if __name__ == "__main__":
    main()