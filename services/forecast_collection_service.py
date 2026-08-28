from typing import List, Dict, Any
from sqlalchemy.orm import Session

from crawler.forecast_list_crawler import ForecastListCrawler
from crawler.forecast_pdf_crawler import ForecastPdfCrawler
from crawler.utils.agency_url_templates import get_forecast_url_candidates
from utils.forecast_logger import ForecastLogger


class ForecastCollectionService:
    """発注見通し収集のオーケストレーションを行うサービス。"""

    def __init__(self, session: Session):
        self.session = session
        self.logger = ForecastLogger("CollectionService")
        self.list_crawler = ForecastListCrawler()
        self.pdf_crawler = ForecastPdfCrawler()

    async def collect_for_agency(
        self, agency_id: int, agency_name: str, base_url: str, agency_type: str = "municipality"
    ) -> List[Dict[str, Any]]:
        self.logger.info(f"Starting collection for agency", agency_id=agency_id, name=agency_name)
        all_found_items: List[Dict[str, Any]] = []
        url_candidates = get_forecast_url_candidates(base_url, agency_type)

        for url in url_candidates:
            try:
                self.logger.info(f"Checking candidate URL", url=url)
                links = await self.list_crawler.crawl_forecast_list(url, agency_name)
                for link in links:
                    if link["url"].lower().endswith(".pdf"):
                        pdf_result = await self.pdf_crawler.process_pdf(link["url"], agency_id)
                        if pdf_result:
                            all_found_items.append({"type": "pdf", "url": link["url"], "metadata": pdf_result})
                    else:
                        all_found_items.append({"type": "html", "url": link["url"], "text": link["text"]})
            except Exception as e:
                self.logger.error(f"Error crawling candidate URL", url=url, error=str(e))
                continue

        self.logger.info(f"Collection completed for agency", agency_id=agency_id, items_found=len(all_found_items))
        return all_found_items

    async def cleanup(self):
        await self.list_crawler.close()
        await self.pdf_crawler.close()
