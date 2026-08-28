#!/usr/bin/env python3
"""url_hunter.py
Automated discovery of the most suitable bidding information URL for a given municipality.

The script takes a municipality name and query keyword from the CLI, searches DuckDuckGo for the
top three results, scrapes each page with Playwright for titles, links, PDF counts, and a text
excerpt, and asks Gemini (via google‑genai) to pick the best candidate URL.

Author: Your Name
"""

import asyncio
import logging
import os
import json
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin

# ---------------------------------------------------------------------------
# 3rd‑party imports – ensure these are present in requirements.txt
# ---------------------------------------------------------------------------
from duckduckgo_search import DDGS  # type: ignore
from playwright.async_api import async_playwright, Page, Browser, BrowserContext  # type: ignore
from google import genai
from google.genai import types
from dotenv import load_dotenv  # type: ignore
from pydantic import BaseModel, Field  # type: ignore

# ---------------------------------------------------------------------------
# Environment setup and basic configuration
# ---------------------------------------------------------------------------

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("error.log", encoding="utf-8")],
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL_NAME = "gemini-3.1-flash-lite"
RESULT_FILE = "url_hunter_result.json"
TIMEOUT_MS = 30000  # milliseconds for page load
NUM_SEARCH_RESULTS = 3
SLEEP_INTERVAL = 5  # seconds between requests

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# Pydantic model for the structured result returned by Gemini
# ---------------------------------------------------------------------------

class TargetURL(BaseModel):
    """Structured Gemini output."""
    agency_name: str = Field(description="自治体名")
    discovered_url: str
    confidence_score: int
    reason: str

# ---------------------------------------------------------------------------
# System prompt used for Gemini – includes the judgment rules
# ---------------------------------------------------------------------------

URL_HUNTER_PROMPT = """
検索結果のページ群から、
- 単なる「手続きの案内ページ」や「トップページ」を排除し、
- 具体的な「案件名」「公告」「仕様書」「PDF」というキーワードが高密度で含まれている、
- またはそれらのページに直結しているURLを最優先で選べ。
- 単一URLのみ回答。
"""

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def init_client() -> None:
    """Configure the global Gemini client with the API key from the environment."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY が環境変数/.env に設定されていません")
    # No configure needed for google.genai.Client


async def search_urls(query: str, num_results: int = NUM_SEARCH_RESULTS) -> List[str]:
    """Return the URLs of the top *num_results* DuckDuckGo search results."""
    # DuckDuckGo search is CPU bound; run it in a thread pool
    def _search():
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=num_results))
    results = await asyncio.to_thread(_search)
    return [r.get("href") for r in results if r.get("href")]


async def init_browser() -> tuple[async_playwright, Browser, BrowserContext, Page]:
    """Launch a headless Chromium instance and return the key objects."""
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context(user_agent=USER_AGENT)
    page = await context.new_page()
    return pw, browser, context, page


async def close_browser(pw: async_playwright, browser: Browser, context: BrowserContext) -> None:
    """Close Playwright resources cleanly."""
    await context.close()
    await browser.close()
    await pw.stop()


async def fetch_page_info(page: Page, url: str) -> Dict[str, Any]:
    """Scrape the page for title, links, PDF count, and a body excerpt."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
        await page.wait_for_load_state("networkidle", timeout=TIMEOUT_MS)
        content = await page.content()
        # Import BeautifulSoup lazily to avoid a top‑level dependency
        from bs4 import BeautifulSoup  # type: ignore

        soup = BeautifulSoup(content, "html.parser")
        links = []
        pdf_count = 0
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"])
            links.append({"text": a.get_text(strip=True), "href": href})
            if href.lower().endswith(".pdf"):
                pdf_count += 1
        body_text = soup.get_text(separator="\n", strip=True)[:2000]
        return {
            "url": url,
            "title": soup.title.string if soup.title else "",
            "links": links,
            "pdf_count": pdf_count,
            "text": body_text,
        }
    except Exception as e:
        logging.error(f"Failed to fetch page {url}: {e}")
        return {"url": url, "error": str(e)}


async def build_prompt(query: str, page_infos: List[Dict[str, Any]]) -> str:
    """Construct a Markdown prompt for Gemini based on extracted page data."""
    sections = []
    for idx, info in enumerate(page_infos, start=1):
        link_lines = "\n".join(
            f"- {link.get('text', 'n/a')} ({link.get('href')})"
            for link in info.get("links", [])[:20]
        )
        section = (
            f"### Page {idx}: {info.get('url', 'N/A')}\n"
            f"**Title:** {info.get('title', 'N/A')}\n"
            f"**PDF link count:** {info.get('pdf_count', 0)}\n"
            f"**Links (top 20):**\n{link_lines}\n\n"
            f"**Body excerpt:**\n{info.get('text', '')[:200]}"
        )
        sections.append(section)

    prompt = (
        "以下の情報をもとに、<assistant> に対して単一 URL を返してください。\n\n"
        "以下 3 つの検索結果から選びます: \n"
        + "\n".join(sections)
        + "\n\n"
        + URL_HUNTER_PROMPT
    )
    return prompt


def generate_target_url(_client, query: str, page_infos: List[Dict[str, Any]]) -> Optional[TargetURL]:
    """Generate the best candidate URL using Gemini.
    Attempts to synchronize with any async context by invoking
    `build_prompt` synchronously with `asyncio.run` and falls back
    to `loop.run_until_complete` if running inside an active event loop.
    """
    try:
        prompt = asyncio.run(build_prompt(query, page_infos))
    except RuntimeError:
        prompt = asyncio.get_event_loop().run_until_complete(build_prompt(query, page_infos))

    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=TargetURL,
            temperature=0.0,
        )
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[URL_HUNTER_PROMPT, prompt],
            config=config,
        )
        # Parse result
        if hasattr(response, "parsed") and response.parsed:
            return response.parsed
        if hasattr(response, "text") and response.text:
            try:
                data = json.loads(response.text)
                return TargetURL(**data)
            except json.JSONDecodeError as je:
                logging.error(f"Failed to decode Gemini response JSON: {je}")
        logging.error("Gemini response has no parsed data or text")
    except Exception as e:
        logging.error(f"Gemini inference failed: {e}")
    return None


def save_result(result: TargetURL, path: str = RESULT_FILE) -> None:
    """Persist the result as JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result.model_dump(), f, ensure_ascii=False, indent=2)
    logging.info(f"Result saved to {path}")


async def main_async(query: str) -> None:
    logging.info("=== url_hunter start ===")
    init_client()
    urls = await search_urls(query)
    if not urls:
        logging.warning("検索結果がありません")
        return

    pw, browser, context, page = await init_browser()
    try:
        page_infos: List[Dict[str, Any]] = []
        for idx, url in enumerate(urls, start=1):
            logging.info(f"[{idx}/{len(urls)}] 取得中: {url}")
            info = await fetch_page_info(page, url)
            page_infos.append(info)
            await asyncio.sleep(SLEEP_INTERVAL)

        target = generate_target_url(None, query, page_infos)
        if target:
            save_result(target)
        else:
            logging.warning("ターゲット URL が決定されませんでした")
    finally:
        await close_browser(pw, browser, context)
    logging.info("=== url_hunter end ===")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="url_hunter: 入札一覧ページ URL を自動推論")
    parser.add_argument("--query", required=True, help="自治体名＋検索キーワード（例: 宇和島市 入札情報)")
    args = parser.parse_args()
    asyncio.run(main_async(args.query))
