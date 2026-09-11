from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.async_api import async_playwright


async def inspect_geps(url: str, max_pages: int, timeout: int) -> list[dict]:
    results = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            context = await browser.new_context()
            page = await context.new_page()
            page.set_default_timeout(timeout * 1000)
            current_url = url
            for page_number in range(1, max_pages + 1):
                await page.goto(current_url, wait_until="domcontentloaded", timeout=timeout * 1000)
                rows = await page.query_selector_all("table tr")
                links = await page.query_selector_all("a[href]")
                results.append(
                    {
                        "page": page_number,
                        "url": page.url,
                        "table_rows": len(rows),
                        "links": len(links),
                    }
                )
                next_link = await page.query_selector('a:has-text("次へ"), a:has-text("次のページ")')
                if not next_link or page_number == max_pages:
                    break
                current_url = await next_link.get_attribute("href")
                if not current_url:
                    break
                if current_url.startswith("/"):
                    from urllib.parse import urljoin
                    current_url = urljoin(url, current_url)
            await context.close()
        finally:
            await browser.close()
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="GEPS 実サイト統合テスト")
    parser.add_argument("--url", default="https://www.geps.go.jp")
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    results = asyncio_run(inspect_geps(args.url, args.max_pages, args.timeout))
    payload = json.dumps(results, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


def asyncio_run(awaitable):
    import asyncio
    return asyncio.run(awaitable)


if __name__ == "__main__":
    raise SystemExit(main())
