from bs4 import BeautifulSoup
import re
import logging
from typing import List, Dict, Any
from crawler.base_crawler import BaseCrawler

logger = logging.getLogger(__name__)

class HokkaidoExtractor(BaseCrawler):
    def __init__(self):
        super().__init__(delay=5.0)

    async def extract_links(self, html: str, base_url: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        seen_urls = set()

        # Find all links - Hokkaido might use different patterns
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            text = link.get_text(strip=True)
            # Filter likely bid-related links
            if any(keyword in text.lower() for keyword in ["入札", "公告", "仕様", "案件"]) or \
               any(keyword in href.lower() for keyword in ["bid", "tender", "nyuuketsu"]):
                full_url = href if href.startswith("http") else f"{base_url.rstrip('/')}/{href.lstrip('/')}"
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)
                results.append({
                    "title": text[:200],
                    "url": full_url,
                    "base_url": base_url,
                    "text": text[:500]  # for content analysis
                })

        logger.info(f"HokkaidoExtractor: found {len(results)} links from {base_url}")
        return results