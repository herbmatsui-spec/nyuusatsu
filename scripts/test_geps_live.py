from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

from crawler.geps_crawler import GEPSCrawler

logger = logging.getLogger(__name__)


async def run_geps_crawler(
    query: str = "",
    prefecture_code: str = "01",
    max_pages: int = 1,
    timeout: int = 30,
    selectors_version: str = "2026.09",
) -> list[dict]:
    """GEPSクローラーを実行し、結果を返す。

    Args:
        query: 検索キーワード
        prefecture_code: 都道府県コード
        max_pages: 最大ページ数（現在は1ページのみ実装）
        timeout: タイムアウト（秒）
        selectors_version: セレクタバージョン

    Returns:
        検索結果のリスト
    """
    crawler = GEPSCrawler(
        delay=2.0,
        timeout=timeout * 1000,
        selectors_version=selectors_version,
    )

    try:
        results = await crawler.search_bids(
            query=query,
            prefecture_code=prefecture_code,
        )
        # 結果をJSONシリアライズ可能な形式に変換
        serializable_results = []
        for r in results[:max_pages]:
            serializable_results.append({
                "title": r.get("title"),
                "organization": r.get("organization"),
                "budget": r.get("budget"),
                "deadline": r.get("deadline"),
                "announcement_date": r.get("announcement_date"),
                "url": r.get("url"),
                "pdf_url": r.get("pdf_url"),
                "source_url": r.get("source_url"),
            })
        return serializable_results
    finally:
        await crawler.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="GEPS 実サイト統合テスト")
    parser.add_argument("--query", default="", help="検索キーワード")
    parser.add_argument("--prefecture", default="01", help="都道府県コード")
    parser.add_argument("--max-pages", type=int, default=1, help="最大ページ数")
    parser.add_argument("--timeout", type=int, default=30, help="タイムアウト（秒）")
    parser.add_argument("--selectors-version", default="2026.09", help="セレクタバージョン")
    parser.add_argument("--output", type=Path, help="出力ファイルパス")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    results = asyncio.run(run_geps_crawler(
        query=args.query,
        prefecture_code=args.prefecture,
        max_pages=args.max_pages,
        timeout=args.timeout,
        selectors_version=args.selectors_version,
    ))

    payload = json.dumps(results, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
        logger.info(f"Results written to {args.output}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
