import os
import json
import logging
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from crawler.parsers.base_parser import BaseParser
from crawler.models.crawl_result import CrawlResult

# Pydantic出力スキーマの定義
class LinkMatchItem(BaseModel):
    link_id: int = Field(description="マッチしたリンクのID番号")
    publish_date: str = Field(description="公告日や公開日（あれば。フォーマットは YYYY-MM-DD。無ければ '不明'）")

class LLMParserResponseSchema(BaseModel):
    matched_links: List[LinkMatchItem] = Field(description="入札関連、または仕様書PDFに該当するリンクの一覧")

from services.cost_manager import CostManager

class LLMParser(BaseParser):
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        """
        LLM (Gemini) を使用して、HTMLから知的に入札リンクを特定するパーサー。
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name
        self.logger = logging.getLogger(self.__class__.__name__)
        self.cost_manager = CostManager()
        
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None
            self.logger.warning("Gemini API key is missing. LLMParser will be disabled.")

    def parse(self, html: str, base_url: str, agency_name: str) -> List[CrawlResult]:
        """
        HTML内のリンク候補を前処理し、LLMに判断させて入札リンクを抽出する。
        """
        if not self.client:
            self.logger.error("Gemini Client not initialized. Skipping LLM parse.")
            return []

        if self.cost_manager.is_limit_exceeded():
            self.logger.warning(f"LLM API limit exceeded. Skipping LLM parse for {agency_name}")
            return []

        soup = BeautifulSoup(html, "html.parser")
        
        # 1. リンク候補の収集（前処理）
        raw_links = []
        seen_urls = set()
        link_id = 0

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            title = a.get_text(strip=True)
            
            # あまりに短いテキストや明らかな不要リンク（javascript:等）を弾く
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            full_url = urljoin(base_url, href)
            if full_url in seen_urls:
                continue

            # PDFまたは入札ページ候補となる拡張子/キーワードのみを対象とする
            # （LLMに渡すコンテキスト量を削減するため）
            lower_url = full_url.lower()
            is_likely = (
                lower_url.endswith(".pdf") or
                any(kw in title for kw in ["入札", "調達", "公示", "公告", "結果", "仕様", "見積", "契約", "公募"]) or
                any(kw in lower_url for kw in ["bid", "nyusatsu", "chotatsu", "spec", "notice"])
            )
            
            if is_likely:
                raw_links.append({
                    "id": link_id,
                    "title": title or "リンクテキストなし",
                    "url": full_url,
                    "parent_text": a.parent.get_text(strip=True)[:100] if a.parent else ""
                })
                seen_urls.add(full_url)
                link_id += 1

        if not raw_links:
            self.logger.info("No candidate links found for LLM analysis.")
            return []

        # 2. LLMへのインプット生成
        input_list_str = ""
        for item in raw_links:
            input_list_str += (
                f"ID: {item['id']}\n"
                f"Title: {item['title']}\n"
                f"URL: {item['url']}\n"
                f"Context: {item['parent_text']}\n"
                f"-------------------\n"
            )

        prompt = (
            "あなたは入札情報の収集アシスタントです。\n"
            "提示されたリンクのリストから、「入札案件情報」「入札公告・公示」「調達仕様書（PDF等）」に該当するものを識別し、そのIDを抽出してください。\n"
            "単なるホームページの案内や組織紹介、入札と無関係なニュースなどは除外してください。\n"
            "また、文脈やタイトルから公告日（公開日）がわかる場合は、YYYY-MM-DDの形式で抽出してください。\n\n"
            "【リンクのリスト】\n"
            f"{input_list_str}"
        )

        # 3. LLMの呼び出しとパース（エラーハンドリング徹底）
        try:
            self.logger.info(f"Sending {len(raw_links)} links to Gemini ({self.model_name})")
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=LLMParserResponseSchema,
                    temperature=0.0
                )
            )

            # JSON文字列のパース
            data = json.loads(response.text)
            matched_items = data.get("matched_links", [])
            
            results = []
            id_to_link = {item["id"]: item for item in raw_links}

            for matched in matched_items:
                matched_id = matched.get("link_id")
                pub_date = matched.get("publish_date", "不明")
                
                if matched_id in id_to_link:
                    orig = id_to_link[matched_id]
                    results.append(CrawlResult(
                        title=orig["title"],
                        url=orig["url"],
                        agency_name=agency_name,
                        publish_date=pub_date
                    ))
            
            self.logger.info(f"LLM identified {len(results)} matches.")
            return results

        except Exception as e:
            self.logger.error(f"Error during LLM Parsing: {e}", exc_info=True)
            return []
