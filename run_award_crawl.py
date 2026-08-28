"""
Run Award Crawl (Manual Trigger)
コマンドラインから落札結果クロールを手動実行する。
"""
import argparse
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main():
    parser = argparse.ArgumentParser(description="落札結果クローラ手動実行")
    parser.add_argument("--agency", default="hokkaido", help="対象自治体キー (default: hokkaido)")
    parser.add_argument("--limit", type=int, default=20, help="取得件数上限")
    parser.add_argument("--all", action="store_true", help="全自治体を対象")
    args = parser.parse_args()

    try:
        from crawler.award_list_crawler import AwardListCrawler, get_crawler_for_agency

        if args.all:
            crawler = AwardListCrawler()
            results = crawler.crawl(limit_per_agency=args.limit)
        else:
            single = get_crawler_for_agency(args.agency)
            if single is None:
                print(f"No crawler configured for agency: {args.agency}")
                sys.exit(1)
            results = single.crawl(limit=args.limit)

        print(f"Crawled {len(results)} award results")
        for r in results[:5]:
            print(f"  - {r.get('project_name')} | {r.get('winner_name')} | {r.get('award_rate')}%")
        if len(results) > 5:
            print(f"  ... and {len(results) - 5} more")

    except Exception as e:
        logging.error(f"Award crawl failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
