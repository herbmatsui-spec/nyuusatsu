import os
import time
import logging
import argparse
from datetime import datetime
from typing import List, Optional, Dict, Any, Set
from urllib.parse import urljoin
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup
import pdfplumber
import pandas as pd
from database.session import get_db
from services.bid_bid_service import BidService  # Note: check filename if it's bid_service or _bid_service
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from google import genai

# -----------------------------------------------------------------------------
# 設定クラス (Step 8: 設定外部化)
# -----------------------------------------------------------------------------
@dataclass
class ProcessorConfig:
    target_url: str = "https://example.gov.jp/bids"
    temp_dir: str = "./temp_pdfs"
    csv_path: str = "./bid_ledger.csv"
    error_log: str = "./error.log"
    model_name: str = "gemini-3.1-flash-lite"
    request_timeout: int = 30
    pdf_timeout: int = 60
    api_retry_delay: int = 10
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

config = ProcessorConfig()

# -----------------------------------------------------------------------------
# カスタム例外 (Step 8: エラーハンドリング強化)
# -----------------------------------------------------------------------------
class BidProcessorError(Exception):
    """BidProcessorの基本例外クラス"""
    pass

class PDFExtractionError(BidProcessorError):
    """PDFからのテキスト抽出失敗時の例外"""
    pass

class LLMAnalysisError(BidProcessorError):
    """LLM解析失敗時の例外"""
    pass

# -----------------------------------------------------------------------------
# Pydantic 出力スキーマ
# -----------------------------------------------------------------------------
class BidAnalysis(BaseModel):
    budget: str = Field(description="予算上限や予定価格。記載がない場合は'記載なし'")
    qualifications: list[str] = Field(description="必須となる参加資格を箇条書きで分解して格納")
    deadline: str = Field(description="工期、履行期間、または納品期限")
    deliverables: str = Field(description="求められる成果物や具体的な作業内容。300文字以内")
    key_risks: list[str] = Field(description="仕様書から読み取れる遅延リスクや注意点")
    industry_category: str = Field(description="業種・カテゴリ。1つの代表的なカテゴリを抽出")
    organization_name: str = Field(description="発注機関名")

SYSTEM_PROMPT = (
    "あなたは入札仕様書の専門解析者です。以下の厳格ルールに従え。\n"
    "【禁止事項】サマリー（要約）は一切禁止。\n"
    "【抽出方針】誰が、いつ、どこで、何をするのかを、実務レベルの解像度で抽出せよ。\n"
    "【出力】指定スキーマのJSONのみ。説明文・コードブロックは不可。\n"
    "【記載なし】該当しない場合は文字列'記載なし'、リスト項目は空配列[]とすること。\n"
    "【deliverables】300文字以内。現場のアクションが具体的にイメージできる解像度で記述すること。\n"
    "【industry_category】案件内容から最も適切な業種カテゴリを1つ選定せよ。\n"
    "【organization_name】仕様書から発注元となる機関名を正確に抽出せよ。"
)

# -----------------------------------------------------------------------------
# ユーティリティ
# -----------------------------------------------------------------------------
def load_env():
    load_dotenv()

def get_gemini_api_key():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY が設定されていません。")
    return api_key

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        c_handler = logging.StreamHandler()
        c_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        c_handler.setFormatter(c_format)
        logger.addHandler(c_handler)

        f_handler = logging.FileHandler(config.error_log, encoding='utf-8')
        f_handler.setLevel(logging.ERROR)
        f_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        f_handler.setFormatter(f_format)
        logger.addHandler(f_handler)

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# -----------------------------------------------------------------------------
# プロセッサクラス (責務の分離)
# -----------------------------------------------------------------------------
class BidProcessor:
    def __init__(self, client: genai.Client):
        self.client = client
        self.session = self._make_session()

    def _make_session(self):
        session = requests.Session()
        session.headers.update({"User-Agent": config.user_agent})
        return session

    def fetch_page(self, url: str) -> str:
        try:
            logging.info(f"Fetching page: {url}")
            res = self.session.get(url, timeout=config.request_timeout)
            res.raise_for_status()
            return res.text
        except Exception as e:
            logging.error(f"Failed to fetch page {url}: {e}")
            raise BidProcessorError(f"Page fetch failed: {e}")

    def parse_pdf_links(self, html: str, base_url: str) -> List[str]:
        soup = BeautifulSoup(html, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            full_url = urljoin(base_url, a["href"])
            if full_url.lower().endswith(".pdf"):
                links.append(full_url)
        return list(dict.fromkeys(links))

    def is_already_processed(self, filename: str) -> bool:
        # DBチェック
        try:
            with get_session() as session:
                from services.bid_service import BidService
                service = BidService(session)
                bids = service.list_bids(limit=1000)
                if any(bid.filename == filename for bid in bids):
                    return True
        except Exception as e:
            logging.error(f"Duplicate check DB error: {e}")
        
        # ローカルファイルチェック
        if os.path.exists(config.temp_dir):
            if filename in os.listdir(config.temp_dir):
                return True
        return False

    def download_pdf(self, url: str, dest_path: str) -> bool:
        try:
            time.sleep(3)  # サーバー負荷軽減
            logging.info(f"Downloading: {url}")
            res = self.session.get(url, timeout=config.pdf_timeout, stream=True)
            res.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in res.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        except Exception as e:
            logging.error(f"Download failed {url}: {e}")
            return False

    def extract_text(self, pdf_path: str) -> str:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text = "\n".join([p.extract_text() or "" for p in pdf.pages]).strip()
                if not text or len(text) < 50:
                    raise PDFExtractionError(f"Scanned PDF or empty: {pdf_path}")
                return text
        except Exception as e:
            logging.error(f"PDF read error {pdf_path}: {e}")
            raise PDFExtractionError(str(e))

    def analyze_text(self, text: str) -> BidAnalysis:
        try:
            time.sleep(config.api_retry_delay)
            logging.info("Analyzing with Gemini...")
            response = self.client.models.generate_content(
                model=config.model_name,
                contents=f"{SYSTEM_PROMPT}\n\n--- Specification Text ---\n{text}",
                config={
                    "response_mime_type": "application/json",
                    "response_schema": BidAnalysis,
                },
            )
            if not response.parsed:
                raise LLMAnalysisError("No parsed result from LLM")
            return response.parsed
        except Exception as e:
            logging.error(f"Gemini API Error: {e}")
            raise LLMAnalysisError(str(e))

    def save_bid_result(self, record: Dict[str, Any], full_text: Optional[str] = None):
        from database.engine import get_session
        from database.repositories import save_bid
        
        try:
            session = get_session()
            try:
                bid_data = {
                    "filename": record["ファイル名"],
                    "project_name": record.get("案件名", record["ファイル名"]),
                    "organization": record.get("発注機関", "不明"),
                    "budget": record.get("予算", "不明"),
                    "qualifications": record.get("参加資格", "不明"),
                    "deadline": record.get("納期", "不明"),
                    "industry": record.get("業種カテゴリ", "不明"),
                    "region": record.get("地域", "不明"),
                    "announcement_date": record.get("公告日"),
                    "closing_date": record.get("締切日"),
                }
                save_bid(session, bid_data, full_text)
                session.commit()
            except Exception as e:
                session.rollback()
                logging.error(f"Database save failed: {e}")
            finally:
                session.close()
        except Exception as e:
            logging.error(f"Session error: {e}")

        # CSV Backup
        df_new = pd.DataFrame([record])
        file_exists = os.path.exists(config.csv_path)
        df_new.to_csv(config.csv_path, mode='a', index=False, header=not file_exists, encoding='utf-8-sig')

# -----------------------------------------------------------------------------
# メインフロー
# -----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", type=str, default=config.target_url, help="Target URL for scraping")
    args = parser.parse_args()

    setup_logging()
    load_env()
    
    try:
        api_key = get_gemini_api_key()
        client = genai.Client(api_key=api_key)
        processor = BidProcessor(client)
    except Exception as e:
        logging.error(f"Setup failed: {e}")
        return

    try:
        html = processor.fetch_page(args.url)
        pdf_urls = processor.parse_pdf_links(html, args.url)
        logging.info(f"Found {len(pdf_urls)} PDF links.")
        
        if not os.path.exists(config.temp_dir):
            os.makedirs(config.temp_dir)
        
        batch_records = []
        batch_texts = []

        for pdf_url in pdf_urls:
            filename = pdf_url.split("/")[-1]
            if processor.is_already_processed(filename):
                logging.info(f"Skipping processed file: {filename}")
                continue
            
            dest_path = os.path.join(config.temp_dir, filename)
            
            if not processor.download_pdf(pdf_url, dest_path):
                continue
            
            try:
                text = processor.extract_text(dest_path)
                analysis = processor.analyze_text(text)
                
                record = {
                    "解析日時": now_str(),
                    "ファイル名": filename,
                    "予算": analysis.budget,
                    "参加資格": "; ".join(analysis.qualifications),
                    "納期": analysis.deadline,
                    "成果物": analysis.deliverables,
                    "リスク": "; ".join(analysis.key_risks),
                    "業種カテゴリ": analysis.industry_category,
                    "発注機関": analysis.organization_name,
                    "備考": "解析完了"
                }
                batch_records.append(record)
                batch_texts.append(text)
                
            except PDFExtractionError as e:
                logging.warning(f"PDF Text Error for {filename}: {e}")
                record = {"解析日時": now_str(), "ファイル名": filename, "備考": "テキスト抽出不可"}
                processor.save_bid_result(record)
            except LLMAnalysisError as e:
                logging.error(f"LLM Error for {filename}: {e}")
                record = {"解析日時": now_str(), "ファイル名": filename, "備考": "Gemini APIエラー"}
                processor.save_bid_result(record)
            except Exception as e:
                logging.error(f"Unexpected error processing {pdf_url}: {e}")
                continue

        if batch_records:
            from database.engine import get_session
            from database.repositories import save_bids_batch
            db_session = get_session()
            try:
                save_bids_batch(db_session, batch_records, batch_texts)
                db_session.commit()
                logging.info(f"Batch saved {len(batch_records)} records.")
            except Exception as e:
                db_session.rollback()
                logging.error(f"Batch save failed: {e}")
                for rec, txt in zip(batch_records, batch_texts):
                    processor.save_bid_result(rec, full_text=txt)
            finally:
                db_session.close()

    except Exception as e:
        logging.error(f"Critical system error: {e}")

if __name__ == "__main__":
    main()
