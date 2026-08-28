import logging
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
from crawler.award_base_crawler import AwardBaseCrawler

logger = logging.getLogger(__name__)

class GenericAwardCrawler(AwardBaseCrawler):
    """
    HTMLの表形式（table）で落札結果を公開している多くの自治体に対応するための
    汎用クローラ。CSSセレクタを用いて抽出対象を柔軟に指定する。
    """

    def __init__(self, agency_key: str, list_selector: str, detail_selectors: Dict[str, str]):
        super().__init__()
        self.agency_key = agency_key
        self.list_selector = list_selector
        self.detail_selectors = detail_selectors

    def extract_award_links(self, html: str, base_url: str) -> List[Dict[str, Any]]:
        """
        指定された CSS セレクタを用いて、一覧ページから案件リンクを抽出する。
        """
        soup = BeautifulSoup(html, "html.parser")
        links = []
        
        # 指定されたセレクタでリンク要素をすべて取得
        elements = soup.select(self.list_selector)
        
        for el in elements:
            link_tag = el.find("a") if el.name != "a" else el
            if not link_tag or not link_tag.get("href"):
                continue
                
            href = link_tag.get("href")
            # 相対的なURLを絶対パスに変換
            full_url = href if href.startswith("http") else f"{base_url.rstrip('/')}/{href.lstrip('/')}"
            
            links.append({
                "url": full_url,
                "title": link_tag.get_text(strip=True),
                "agency_key": self.agency_key
            })
            
        return links

    def parse_award_detail(self, html: str) -> Optional[Dict[str, Any]]:
        """
        詳細ページから、指定されたセレクタに基づいて情報を抽出する。
        """
        soup = BeautifulSoup(html, "html.parser")
        result = {}
        
        try:
            for field, selector in self.detail_selectors.items():
                element = soup.select_one(selector)
                if element:
                    val = element.get_text(strip=True)
                    # 金額フィールドの場合は共通メソッドで数値化
                    if "amount" in field or "price" in field:
                        result[field] = self.safe_extract_amount(val)
                    else:
                        result[field] = val
                else:
                    result[field] = None
            
            # 必須項目（落札者名など）が全くない場合は None を返す
            if not result.get("winner_name"):
                return None
                
            return result
        except Exception as e:
            logger.error(f"Error parsing detail page with GenericAwardCrawler: {e}")
            return None
