"""
全国入札情報 非同期キュー投入スクリプト

Redis/RQを使って、全アクティブなCrawlConfigのクロールタスクをキューに投入する。
実際のクロールはRQワーカーが実行する。

Usage:
    py -3 scripts/collect_all_async.py
    py -3 scripts/collect_all_async.py --prefecture-name "北海道"
    py -3 scripts/collect_all_async.py --chunk-size 50 --chunk-delay 3
"""
import sys
import os
import io
import time
import random
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from database.session import get_db
from database.models import Prefecture, Agency, CrawlConfig
from crawler.pipeline import trigger_agency_crawl

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CollectAllAsync")


def get_args():
    parser = argparse.ArgumentParser(description="全国入札情報 非同期キュー投入")
    parser.add_argument("--prefecture-id", type=int, default=None)
    parser.add_argument("--prefecture-name", type=str, default=None)
    parser.add_argument("--chunk-size", type=int, default=50, help="1チャンクあたりの最大投入数")
    parser.add_argument("--chunk-delay", type=float, default=3.0, help="チャンク間の待機秒数")
    parser.add_argument("--mode", type=str, default="initial", choices=["initial", "daily"],
                        help="initial=全件投入, daily=前日未完了のみ再投入")
    return parser.parse_args()


def main():
    args = get_args()

    with get_db() as session:
        # CrawlConfig を取得
        query = session.query(CrawlConfig).filter(CrawlConfig.is_active == True)

        if args.prefecture_id or args.prefecture_name:
            pref_query = session.query(Prefecture)
            if args.prefecture_id:
                pref_query = pref_query.filter(Prefecture.id == args.prefecture_id)
            elif args.prefecture_name:
                pref_query = pref_query.filter(Prefecture.name.like(f"%{args.prefecture_name}%"))
            prefs = pref_query.all()
            pref_names = [p.name for p in prefs]

            # Prefecture名でAgencyを絞り込み
            agency_ids = [
                a.id for a in session.query(Agency).filter(Agency.region.in_(pref_names)).all()
            ]
            query = query.filter(CrawlConfig.agency_id.in_(agency_ids))

        configs = query.all()
        logger.info(f"対象CrawlConfig: {len(configs)}件")

        if not configs:
            logger.warning("対象のCrawlConfigが見つかりません")
            return

        # チャンク分割して投入
        enqueued = 0
        for i in range(0, len(configs), args.chunk_size):
            chunk = configs[i:i + args.chunk_size]
            for cfg in chunk:
                try:
                    trigger_agency_crawl(cfg.id)
                    enqueued += 1
                    logger.info(f"  Enqueued config_id={cfg.id} (agency_id={cfg.agency_id})")
                except Exception as e:
                    logger.error(f"  Enqueue失敗 config_id={cfg.id}: {e}")

            # チャンク間の待機（ランダムジッター付き）
            if i + args.chunk_size < len(configs):
                delay = args.chunk_delay + random.uniform(0, 2)
                logger.info(f"  チャンク完了 ({i + len(chunk)}/{len(configs)}), {delay:.1f}秒待機...")
                time.sleep(delay)

        logger.info(f"完了: {enqueued}/{len(configs)} 件をキューに投入しました")


if __name__ == "__main__":
    main()
