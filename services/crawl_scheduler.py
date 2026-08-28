from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json
import asyncio

from services.bid_storage_service import BidStorageService
from database.models import Bid, Prefecture, BidSource
from crawler.geps_crawler import GEPSCrawler
from crawler.generic_crawler import GenericCrawler


@dataclass
class CrawlResult:
    prefecture_id: int
    source_url: str
    bids_found: int
    bids_new: int
    bids_updated: int
    errors: List[str]
    log: str


class CrawlScheduler:
    """全国の入札情報を定期的に巡回・収集するスケジューラ"""
    
    def __init__(self):
        self.storage = BidStorageService()
        self.results: List[CrawlResult] = []
    
    def get_prefecture_sources(self, prefecture_id: int) -> List[BidSource]:
        from database.session import get_db
        with get_db() as db:
            return db.query(BidSource).filter(
                BidSource.prefecture_id == prefecture_id,
                BidSource.is_active == True
            ).all()
    
    def _get_hokkaido_id(self) -> Optional[int]:
        from database.session import get_db
        with get_db() as db:
            prefecture = db.query(Prefecture).filter(Prefecture.code == "JP-01").first()
            return prefecture.id if prefecture else None
    
    def _get_prefecture_code(self, prefecture_id: int) -> Optional[str]:
        """都道府県IDからコードを取得"""
        from database.session import get_db
        with get_db() as db:
            prefecture = db.query(Prefecture).get(prefecture_id)
            return prefecture.code if prefecture else None
    
    def run_crawl_for_prefecture(self, prefecture_id: int) -> CrawlResult:
        from database.session import get_db
        with get_db() as db:
            sources = db.query(BidSource).filter(
                BidSource.prefecture_id == prefecture_id,
                BidSource.is_active == True
            ).all()
            prefecture = db.query(Prefecture).get(prefecture_id)
            
            if not prefecture:
                return CrawlResult(
                    prefecture_id=prefecture_id,
                    source_url="",
                    bids_found=0,
                    bids_new=0,
                    bids_updated=0,
                    errors=[f"Prefecture {prefecture_id} not found"],
                    log=""
                )
            
            total_found = 0
            total_new = 0
            total_updated = 0
            all_errors = []
            log_parts = []
            
            for source in sources:
                result = self._crawl_source(source, prefecture.name)
                total_found += result.bids_found
                total_new += result.bids_new
                total_updated += result.bids_updated
                all_errors.extend(result.errors)
                log_parts.append(f"[{source.source_type}] {source.url}: {result.bids_found} found, {result.bids_new} new")
            
            return CrawlResult(
                prefecture_id=prefecture_id,
                source_url=", ".join([s.url for s in sources]),
                bids_found=total_found,
                bids_new=total_new,
                bids_updated=total_updated,
                errors=all_errors,
                log="\n".join(log_parts)
            )
    
    def _crawl_source(self, source: BidSource, prefecture_name: str) -> CrawlResult:
        bids_found = 0
        bids_new = 0
        bids_updated = 0
        errors = []
        
        try:
            if source.source_type == "geps":
                result = self._crawl_geps(source)
            elif source.source_type == "web":
                result = self._crawl_web(source, prefecture_name)
            else:
                result = {"found": 0, "new": 0, "updated": 0, "errors": [f"Unknown source type: {source.source_type}"]}
            
            bids_found = result["found"]
            bids_new = result["new"]
            bids_updated = result["updated"]
            errors = result["errors"]
            
            from database.session import get_db
            with get_db() as db:
                db_source = db.merge(source)
                db_source.last_crawled_at = datetime.utcnow()
                db.add(db_source)
                db.flush()
        except Exception as e:
            errors.append(f"Crawl failed: {str(e)}")
        
        return CrawlResult(
            prefecture_id=source.prefecture_id,
            source_url=source.url,
            bids_found=bids_found,
            bids_new=bids_new,
            bids_updated=bids_updated,
            errors=errors,
            log=f"Crawled {source.url}: {bids_found} found"
        )
    
    def _crawl_geps(self, source: BidSource) -> Dict:
        prefecture_code = self._get_prefecture_code(source.prefecture_id) or "JP-01"
        found = 0
        new_count = 0
        updated_count = 0
        errors = []
        
        try:
            crawler = GEPSCrawler()
            try:
                query = source.url.split('q=')[-1].split('&')[0] if 'q=' in source.url else ""
                
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                results = loop.run_until_complete(crawler.search_bids(query=query, prefecture_code=prefecture_code))
                loop.close()
                found = len(results)
                
                for item in results:
                    bid_data = {
                        "title": item.get("title", "未取得"),
                        "organization": item.get("organization", ""),
                        "budget": item.get("budget", ""),
                        "deadline": item.get("deadline", ""),
                        "source_url": item.get("url", ""),
                        "project_name": item.get("title", "未取得"),
                        "prefecture_code": prefecture_code,
                    }
                    
                    try:
                        # 詳細ページスクレイピング
                        if bid_data["source_url"]:
                            from crawler.detail_extractor import BidDetailExtractor
                            import requests
                            extractor = BidDetailExtractor()
                            
                            # ページ取得
                            response = requests.get(bid_data["source_url"], timeout=10)
                            if response.status_code == 200:
                                details = extractor.extract(response.text, bid_data["source_url"])
                                bid_data.update(details)
                            
                            # PDFリンク取得
                            loop2 = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop2)
                            pdf_links = loop2.run_until_complete(crawler.fetch_pdf_links(bid_data["source_url"]))
                            loop2.close()
                            if pdf_links:
                                bid_data["pdf_links"] = pdf_links
                    except Exception as e:
                        errors.append(f"Detail fetch failed for {bid_data.get('source_url')}: {str(e)}")
                    
                    bid = self.storage.save_bid(bid_data)
                    if bid:
                        new_count += 1
            except Exception as e:
                errors.append(f"GEPS crawl failed: {str(e)}")
            finally:
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(crawler.close())
                    loop.close()
                except:
                    pass
        except Exception as e:
            errors.append(f"GEPS crawl failed: {str(e)}")
        
        return {"found": found, "new": new_count, "updated": updated_count, "errors": errors}
    
    def _crawl_web(self, source: BidSource, prefecture_name: str) -> Dict:
        prefecture_code = self._get_prefecture_code(source.prefecture_id) or "JP-01"
        found = 0
        new_count = 0
        updated_count = 0
        errors = []
        
        try:
            crawler = GenericCrawler(parser_type=source.parser_type or "heuristic", delay=5.0)
            
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(crawler.crawl_site(source.url))
                loop.close()
                found = len(results)
                
                for item in results:
                    bid_data = {
                        "title": item.get("title", "未取得"),
                        "organization": prefecture_name,
                        "budget": "",
                        "deadline": "",
                        "source_url": item.get("url", ""),
                        "project_name": item.get("title", "未取得"),
                        "prefecture_code": prefecture_code,
                    }
                    
                    try:
                        # 詳細ページスクレイピング
                        from crawler.detail_extractor import BidDetailExtractor
                        import requests
                        extractor = BidDetailExtractor()
                        
                        # ページ取得
                        response = requests.get(item.get("url"), timeout=10)
                        if response.status_code == 200:
                            details = extractor.extract(response.text, item.get("url"))
                            bid_data.update(details)
                    except Exception as e:
                        errors.append(f"Detail fetch failed for {item.get('url')}: {str(e)}")
                    
                    bid = self.storage.save_bid(bid_data)
                    if bid:
                        new_count += 1
            except Exception as e:
                errors.append(f"Web crawl failed: {str(e)}")
            finally:
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(crawler.close())
                    loop.close()
                except:
                    pass
        except Exception as e:
            errors.append(f"Web crawl failed: {str(e)}")
        
        return {"found": found, "new": new_count, "updated": updated_count, "errors": errors}
    
    def run_all_prefectures(self) -> List[CrawlResult]:
        from database.session import get_db
        with get_db() as db:
            prefectures = db.query(Prefecture).filter(
                Prefecture.is_active == True
            ).order_by(Prefecture.priority.asc()).all()
        
        results = []
        for pref in prefectures:
            result = self.run_crawl_for_prefecture(pref.id)
            results.append(result)
            print(f"Completed {pref.name}: {result.bids_new} new bids")
        
        return results
    
    def run_hokkaido_pilot(self, html: str = None, detail_pages: dict = None) -> CrawlResult:
        """北海道パイロットクロールを実行。
        
        Args:
            html: オフラインテスト用のHTMLフィクスチャ。指定時はWebクロールを行わず、
                  このHTMLを解析して入札情報を抽出・保存する。
            detail_pages: オフラインテスト用の詳細ページHTMLマッピング {url: html}。
                          指定時はHTTPリクエストを行わず、このマッピングから詳細ページを取得する。
        """
        hokkaido_id = self._get_hokkaido_id()
        if not hokkaido_id:
            return CrawlResult(
                prefecture_id=1,
                source_url="",
                bids_found=0,
                bids_new=0,
                bids_updated=0,
                errors=["Hokkaido not found in prefectures"],
                log=""
            )
        
        # オフラインテスト用HTMLが指定されている場合
        if html is not None:
            return self._crawl_hokkaido_offline(html, hokkaido_id, detail_pages)
        
        return self.run_crawl_for_prefecture(hokkaido_id)
    
    def _crawl_hokkaido_offline(self, html: str, prefecture_id: int, detail_pages: dict = None) -> CrawlResult:
        """オフラインHTMLフィクスチャから北海道入札情報を抽出・保存
        
        Args:
            html: 一覧ページのHTML
            prefecture_id: 都道府県ID
            detail_pages: 詳細ページHTMLのマッピング {url: html}。指定時はHTTPリクエストを行わない。
        """
        from crawler.hokkaido.scanner import HokkaidoCrawler
        from crawler.detail_extractor import BidDetailExtractor
        import requests
        
        crawler = HokkaidoCrawler()
        bids_data = crawler.parse(html, "https://www.pref.hokkaido.lg.jp")
        
        found = len(bids_data)
        new_count = 0
        updated_count = 0
        errors = []
        
        prefecture_code = self._get_prefecture_code(prefecture_id) or "JP-01"
        detail_extractor = BidDetailExtractor()
        
        for bid_data in bids_data:
            bid_data["prefecture_code"] = prefecture_code
            # HokkaidoCrawler returns "url" but save_bid expects "source_url"
            if bid_data.get("url") and not bid_data.get("source_url"):
                bid_data["source_url"] = bid_data["url"]
            try:
                # 詳細ページスクレイピング
                if bid_data.get("url"):
                    try:
                        detail_html = None
                        if detail_pages and bid_data["url"] in detail_pages:
                            # オフラインモード: マッピングからHTMLを取得
                            detail_html = detail_pages[bid_data["url"]]
                        else:
                            # オンラインモード: HTTPリクエストで取得
                            response = requests.get(bid_data["url"], timeout=10)
                            if response.status_code == 200:
                                detail_html = response.text
                        
                        if detail_html:
                            details = detail_extractor.extract(detail_html, bid_data["url"])
                            bid_data.update(details)
                    except Exception as e:
                        errors.append(f"Detail fetch failed for {bid_data.get('url')}: {str(e)}")
                
                bid = self.storage.save_bid(bid_data)
                if bid:
                    new_count += 1
            except Exception as e:
                errors.append(f"Failed to save bid: {str(e)}")
        
        return CrawlResult(
            prefecture_id=prefecture_id,
            source_url="https://www.pref.hokkaido.lg.jp (offline fixture)",
            bids_found=found,
            bids_new=new_count,
            bids_updated=updated_count,
            errors=errors,
            log=f"Offline crawl: {found} found, {new_count} new"
        )


def main():
    scheduler = CrawlScheduler()
    print("Starting Hokkaido pilot crawl...")
    result = scheduler.run_hokkaido_pilot()
    print(f"Results: {result.bids_found} found, {result.bids_new} new, {result.bids_updated} updated")
    if result.errors:
        print(f"Errors: {result.errors}")
    print(f"Log: {result.log}")


if __name__ == "__main__":
    main()