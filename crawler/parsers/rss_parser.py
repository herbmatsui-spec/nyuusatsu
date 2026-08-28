import xml.etree.ElementTree as ET
import logging
from typing import List
from urllib.parse import urljoin
from datetime import datetime

from crawler.parsers.base_parser import BaseParser
from crawler.models.crawl_result import CrawlResult

class RSSParser(BaseParser):
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def parse(self, xml_content: str, base_url: str, agency_name: str) -> List[CrawlResult]:
        """
        RSSフィード（XML）を解析し、入札情報の一覧を抽出する。
        """
        results = []
        try:
            # XMLのパース
            root = ET.fromstring(xml_content.encode("utf-8", errors="ignore"))
            
            # RSS 2.0 / Atom 両対応のための簡易的なタグ検索
            # RSS 2.0: channel -> item -> title, link, pubDate
            # Atom: feed -> entry -> title, link, updated/published
            
            # 1. RSS 2.0 の判定
            items = root.findall(".//item")
            if items:
                for item in items:
                    title_el = item.find("title")
                    link_el = item.find("link")
                    pub_date_el = item.find("pubDate")
                    
                    title = title_el.text.strip() if title_el is not None and title_el.text else "無題"
                    link = link_el.text.strip() if link_el is not None and link_el.text else ""
                    
                    if not link:
                        continue
                    
                    full_url = urljoin(base_url, link)
                    
                    # 日付のパース
                    publish_date = "不明"
                    if pub_date_el is not None and pub_date_el.text:
                        try:
                            # RFC 2822 (e.g. "Tue, 03 Jun 2003 09:39:21 GMT")
                            dt = datetime.strptime(pub_date_el.text.strip()[:25].strip(), "%a, %d %b %Y %H:%M:%S")
                            publish_date = dt.strftime("%Y-%m-%d")
                        except Exception:
                            # フォールバック：テキストをそのまま保持
                            publish_date = pub_date_el.text.strip()

                    results.append(CrawlResult(
                        title=title,
                        url=full_url,
                        agency_name=agency_name,
                        publish_date=publish_date
                    ))
                return results

            # 2. Atom の判定
            # ElementTreeでは名前空間が必要になることがあるため、ローカル名での検索も考慮
            entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
            if not entries:
                entries = root.findall(".//entry")

            def _find_el(parent, *tags):
                for tag in tags:
                    el = parent.find(tag)
                    if el is not None:
                        return el
                return None

            if entries:
                for entry in entries:
                    title_el = _find_el(entry, "{http://www.w3.org/2005/Atom}title", "title")
                    link_el = _find_el(entry, "{http://www.w3.org/2005/Atom}link", "link")
                    pub_date_el = _find_el(
                        entry,
                        "{http://www.w3.org/2005/Atom}published",
                        "published",
                        "{http://www.w3.org/2005/Atom}updated",
                        "updated"
                    )

                    title = title_el.text.strip() if title_el is not None and title_el.text else "無題"
                    
                    link = ""
                    if link_el is not None:
                        # Atomのlinkは通常 href 属性にある
                        link = link_el.get("href", "").strip() or (link_el.text or "").strip()
                    
                    if not link:
                        continue

                        
                    full_url = urljoin(base_url, link)
                    
                    publish_date = "不明"
                    if pub_date_el is not None and pub_date_el.text:
                        try:
                            # ISO 8601 (e.g. "2003-12-13T18:30:02Z")
                            dt_str = pub_date_el.text.strip()
                            if "T" in dt_str:
                                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                                publish_date = dt.strftime("%Y-%m-%d")
                            else:
                                publish_date = dt_str[:10]
                        except Exception:
                            publish_date = pub_date_el.text.strip()

                    results.append(CrawlResult(
                        title=title,
                        url=full_url,
                        agency_name=agency_name,
                        publish_date=publish_date
                    ))
                return results

        except Exception as e:
            self.logger.error(f"Failed to parse RSS XML: {e}", exc_info=True)
            
        return results
