import os
import time
import logging
import io
from datetime import datetime
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup
import pdfplumber
import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from google import genai
from urllib.robotparser import RobotFileParser
from config_dir import AppConfig
from utils.logger import setup_logging, get_logger
from utils.file_cache import is_file_cached, save_to_cache
from services.pdf_processor import PDFProcessor, PDFExtractionError
from services.analysis_service_core import AnalysisServiceCore

# -----------------------------------------------------------------------------
# 設定 (config.py から AppConfig を使用)
# -----------------------------------------------------------------------------
config = AppConfig()


# -----------------------------------------------------------------------------
# Pydanticモデル
# -----------------------------------------------------------------------------
class BidRequirement(BaseModel):
    budget: str = Field(description="予算上限や予定価格。記載なしは「不明」")
    qualifications: str = Field(description="参加資格（特定の許可、等級等）")
    deadline: str = Field(description="納品期限または履行期間")
    deliverables: str = Field(description="成果物や作業内容。300文字以内")


# -----------------------------------------------------------------------------
# ユーティリティ
# -----------------------------------------------------------------------------
def load_env() -> None:
    """.envファイルの読み込み"""
    load_dotenv()


def get_gemini_api_key() -> str:
    """Gemini APIキーの取得"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY が .env ファイルまたは環境変数に設定されていません。")
    return api_key


def today_str() -> str:
    """日付文字列生成 (YYYYMMDD)"""
    return datetime.now().strftime("%Y%m%d")


# -----------------------------------------------------------------------------
# コアロジック
# -----------------------------------------------------------------------------
class BidCollector:
    def __init__(self, client, gemini_key: Optional[str] = None):
        self.client = client
        self.session = self._make_session()
        self.logger = get_logger("BidCollector")
        self.pdf_processor = PDFProcessor(config)
        self.gemini_key = gemini_key
        self.config = config

    def _make_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({"User-Agent": config.crawler.user_agent})
        return session

    def can_fetch(self, url: str) -> bool:
        """robots.txt を確認して、URLへのアクセスが許可されているか判定する。"""
        try:
            parsed_url = urljoin(url, "/robots.txt")
            rp = RobotFileParser()
            rp.set_url(parsed_url)
            rp.read()
            return rp.can_fetch(config.crawler.user_agent, url)
        except Exception as e:
            self.logger.warning("Could not parse robots.txt for %s: %s", url, e)
            return True

    def fetch_page(self, url: str) -> str:
        """ページのHTML取得"""
        if not self.can_fetch(url):
            self.logger.warning("Access forbidden by robots.txt: %s", url)
            return ""

        try:
            self.logger.info("Fetching page: %s", url)
            response = self.session.get(url, timeout=config.crawler.request_timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            self.logger.error("Failed to fetch page %s: %s", url, e)
            raise

    def parse_pdf_links(self, html: str, base_url: str) -> List[str]:
        """PDFリンクの収集・正規化・フィルタリング"""
        soup = BeautifulSoup(html, "html.parser")
        links = []
        for a_tag in soup.find_all("a", href=True):
            full_url = urljoin(base_url, a_tag["href"])
            if full_url.lower().endswith(".pdf"):
                links.append(full_url)
        return list(dict.fromkeys(links))

    def ensure_temp_dir(self) -> None:
        """一時フォルダの作成"""
        if not os.path.exists(config.crawler.temp_dir):
            os.makedirs(config.crawler.temp_dir)
            logging.info("Created temp directory: %s", config.crawler.temp_dir)

    def download_pdf(self, url: str, index: int) -> Optional[str]:
        """PDFのダウンロードとキャッシュ保存"""
        try:
            response = self.session.get(url, timeout=config.crawler.pdf_timeout, stream=True)
            response.raise_for_status()
            file_data = response.content

            cached_path = is_file_cached(file_data, config.crawler.temp_dir)
            if cached_path:
                self.logger.info("PDF cache hit for %s", url)
                return cached_path

            dest_path = save_to_cache(file_data, config.crawler.temp_dir)
            self.logger.info("Downloaded and cached PDF: %s -> %s", url, dest_path)
            return dest_path
        except Exception as e:
            self.logger.error("Failed to download PDF %s: %s", url, e)
            return None

    def extract_text(self, pdf_path: str) -> Optional[str]:
        """PDFからのテキスト抽出"""
        try:
            path = io.BytesIO(open(pdf_path, "rb").read()) if False else pdf_path
            processor = PDFProcessor(config)
            text = processor.extract_text(path, source_name=os.path.basename(pdf_path))
            return text
        except PDFExtractionError as e:
            self.logger.warning("PDF extraction issue for %s: %s", pdf_path, e)
            return None
        except Exception as e:
            self.logger.error("Error extracting text from %s: %s", pdf_path, e)
            return None

    def _prepare_text_for_llm(self, text: str) -> str:
        """LLMに送る前にテキストを最適化する。"""
        if not self.config.chunking.enable_smart_chunking:
            return text[: self.config.chunking.max_text_chars]
        
        from utils.text_chunker import TextChunker
        chunker = TextChunker(
            max_chars=self.config.chunking.max_text_chars,
            priority_keywords=self.config.chunking.priority_keywords,
        )
        return chunker.prepare_for_llm(text)

    def analyze_text(self, text: str) -> Optional[Dict[str, Any]]:
        """LLM Serviceによる要件抽出"""
        try:
            from services.llm_service import LLMService
            llm_service = LLMService(self.config)
            
            self.logger.info("Analyzing optimized text with LLM Service...")
            prepared = self._prepare_text_for_llm(text)
            
            # analyze_with_fallback を使用して設定済みのプロバイダーで解析
            result = llm_service.analyze_with_fallback(prepared)
            return result
        except Exception as e:
            self.logger.error("LLM analysis error: %s", e)
            return None

    def save_results_to_csv(self, results: List[Dict[str, Any]]) -> str:
        """結果をCSVへ保存"""
        if not results:
            return ""

        df = pd.DataFrame(results)
        filename = f"bid_results_{today_str()}.csv"
        output_path = os.path.join(config.crawler.output_dir, filename)

        if not os.path.exists(config.crawler.output_dir):
            os.makedirs(config.crawler.output_dir)

        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        return output_path

    def cleanup_temp_dir(self) -> None:
        """一時ファイルの削除"""
        if os.path.exists(config.crawler.temp_dir):
            self.logger.info("Cleaning up temp directory: %s", config.crawler.temp_dir)
            for file in os.listdir(config.crawler.temp_dir):
                file_path = os.path.join(config.crawler.temp_dir, file)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    self.logger.error("Failed to delete %s: %s", file_path, e)


# -----------------------------------------------------------------------------
# メイン実行関数
# -----------------------------------------------------------------------------
def main():
    setup_logging()
    load_env()

    # LLMService が内部でキーを管理するため、Clientを直接渡す必要はない
    collector = BidCollector(None)
    url = config.crawler.target_url

    try:
        html = collector.fetch_page(url)
        if not html:
            logging.error("No HTML content retrieved. Stopping.")
            return

        pdf_urls = collector.parse_pdf_links(html, url)
        logging.info("Found %d PDF links.", len(pdf_urls))

        if not pdf_urls:
            logging.warning("No PDF links found at %s. Site structure might have changed.", url)
            return

        collector.ensure_temp_dir()
        all_results = []

        with ThreadPoolExecutor(max_workers=config.crawler.parallel_downloads) as executor:
            future_to_url = {
                executor.submit(collector.download_pdf, u, i): u
                for i, u in enumerate(pdf_urls, 1)
            }

            for future in as_completed(future_to_url):
                pdf_url = future_to_url[future]
                try:
                    pdf_path = future.result()
                    if not pdf_path:
                        continue

                    text = collector.extract_text(pdf_path)
                    if not text:
                        continue

                    analysis = collector.analyze_text(text)
                    if analysis:
                        analysis["project_name"] = pdf_url.split("/")[-1]
                        all_results.append(analysis)

                except Exception as e:
                    logging.error("Unexpected error processing %s: %s", pdf_url, e)

        if all_results:
            csv_path = collector.save_results_to_csv(all_results)
            logging.info("Results saved to: %s", csv_path)
        else:
            logging.info("No valid requirements extracted.")

    except Exception as e:
        logging.error("Critical error in main flow: %s", e)
    finally:
        collector.cleanup_temp_dir()


if __name__ == "__main__":
    main()
