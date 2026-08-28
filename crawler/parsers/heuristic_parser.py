import re
from typing import List, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from crawler.parsers.base_parser import BaseParser
from crawler.models.crawl_result import CrawlResult

from crawler.parsers.agency_config_loader import AgencyConfigLoader

class HeuristicParser(BaseParser):
    def __init__(self, config_loader: Optional[AgencyConfigLoader] = None):
        # 入札や仕様書等に関するキーワード定義
        self.keywords = [
            "入札", "仕様書", "調達", "公示", "公告", "公募", "結果", "落札",
            "見積", "契約", "説明書", "告示", "選定"
        ]
        self.config_loader = config_loader or AgencyConfigLoader()
        # 日付抽出用正規表現 (YYYY年MM月DD日 または YYYY/MM/DD または YYYY-MM-DD)
        self.date_regex = re.compile(
            r"((?:19|20)\d{2})[\s/\-年]\s*(0?[1-9]|1[0-2])[\s/\-月]\s*(0?[1-9]|[12]\d|3[01])日?"
        )

    def _filter_by_keywords(self, urls: List[str], keywords: List[str]) -> List[str]:
        """URLパスに指定されたキーワードが含まれるものを抽出する。"""
        return [url for url in urls if any(kw in url.lower() for kw in keywords)]

    def _is_pdf_url(self, url: str) -> bool:
        """URLがPDFファイルであるか判定する。"""
        url_lower = url.lower()
        return url_lower.endswith(".pdf") or ".pdf?" in url_lower or "/files/" in url_lower

    def parse(self, html: str, base_url: str, agency_name: str) -> List[CrawlResult]:
        """
        HTMLをヒューリスティックに解析し、入札関連のPDF仕様書リンクと情報を抽出する。
        自治体別設定がある場合はそれを優先し、なければ汎用ロジックを使用する。
        """
        config = self.config_loader.load(agency_name)
        soup = BeautifulSoup(html, "html.parser")
        results = []
        seen_urls = set()

        # 自治体別CSSセレクタがある場合は優先的にリンクを抽出
        links_to_process = []
        if config.get("css_selectors"):
            for selector in config["css_selectors"]:
                for a in soup.select(selector):
                    if a.name == 'a' and a.get('href'):
                        links_to_process.append(a)
        
        # 個別設定でリンクが抽出されなかった、または汎用抽出も併用する場合は find_all('a') を使用
        if not links_to_process:
            links_to_process = soup.find_all("a", href=True)

        for a in links_to_process:
            href = a["href"].strip()
            title = a.get_text(strip=True)
            
            # URLを絶対URLに変換
            full_url = urljoin(base_url, href)
            
            # 重複排除
            if full_url in seen_urls:
                continue

            # PDFファイルのみを対象にする (拡張子チェック)
            # is_pdf = full_url.lower().endswith(".pdf") or ".pdf?" in full_url.lower()
            # if not is_pdf:
            #     continue

            # タイトルまたはURLが入札に関連するキーワードを含んでいるかチェック
            matched = False
            # aタグのテキストでチェック (自治体別キーワードがあれば優先)
            current_keywords = config.get("title_keywords") or self.keywords
            if any(kw in title for kw in current_keywords):
                matched = True
            # URLのパスでチェック (自治体別URLフィルタがあれば優先)
            elif config.get("url_includes"):
                if any(inc in full_url for inc in config["url_includes"]):
                    matched = True
            elif any(kw in full_url for kw in ["bid", "nyusatsu", "chotatsu", "kougo", "spec"]):
                matched = True
            
            if not matched:
                # 親要素のテキストや周辺テキストも簡易チェックする（より寛容な抽出）
                parent_text = a.parent.get_text() if a.parent else ""
                if any(kw in parent_text for kw in self.keywords):
                    matched = True

            if matched:
                # 日付の抽出を試みる（リンクテキスト、または親要素のテキストから）
                search_text = f"{title} | {a.parent.get_text() if a.parent else ''}"
                publish_date = "不明"
                date_match = self.date_regex.search(search_text)
                if date_match:
                    year, month, day = date_match.groups()
                    publish_date = f"{year}-{int(month):02d}-{int(day):02d}"

                results.append(CrawlResult(
                    title=title or "仕様書PDF",
                    url=full_url,
                    agency_name=agency_name,
                    publish_date=publish_date
                ))
                seen_urls.add(full_url)

        return results
