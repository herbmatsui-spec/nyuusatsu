import os
import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
import pdfplumber

from database.models import Bid, BidStatus, Customer, Partner, CustomerBidLink, PartnerBidLink
from database.repositories.bid_repository import BidRepository
from database.repositories.customer_repository import CustomerRepository
from database.repositories.partner_repository import PartnerRepository
from services.llm_service import LLMService
from config import AppConfig
from utils.budget_parser import parse_budget
from ocr import is_scanned_pdf, create_ocr_provider, OCRConfig
from ocr.metrics import record_fallback, record_normal_extract

logger = logging.getLogger("BidAnalysisService")

# OCR fallback thresholds
TEXT_MIN_LENGTH = 50
OCR_CONFIDENCE_MIN = 0.6

class BidAnalysisService:
    def __init__(self, session, llm_service: Optional[LLMService] = None, ocr_config: Optional[OCRConfig] = None):
        self.session = session
        self.config = AppConfig()
        self.ocr_config = ocr_config or OCRConfig.from_env()
        
        # LLMServiceの初期化（未指定の場合は環境変数から自動構成）
        if llm_service is None:
            deepseek_key = os.getenv("DEEPSEEK_API_KEY")
            gemini_key = os.getenv("GEMINI_API_KEY")
            self.llm_service = LLMService(
                deepseek_key=deepseek_key,
                gemini_key=gemini_key,
                config=self.config
            )
        else:
            self.llm_service = llm_service

        self.bid_repo = BidRepository(session)
        self.customer_repo = CustomerRepository(session)
        self.partner_repo = PartnerRepository(session)

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """
        3段階でPDFからテキストを抽出する。
        Stage 1: pdfplumber で通常のテキスト抽出
        Stage 2: 文字が少ない場合、スキャンPDF判定してOCRへフォールバック
        Stage 3: 抽出結果の品質検証 (文字数しきい値)
        """
        logger.info(f"Extracting text from PDF: {pdf_path}")
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        # === Stage 1: 通常のテキスト抽出 ===
        text = self._extract_with_pdfplumber(pdf_path)
        
        # Record success of normal text extraction
        record_normal_extract()
        
        # === Stage 2: スキャンPDF判定とOCRフォールバック ===
        if len(text.strip()) < TEXT_MIN_LENGTH:
            logger.warning(
                f"[OCR-FALLBACK] pdfplumber_low_text | file={os.path.basename(pdf_path)} | chars={len(text.strip())}"
            )
            try:
                with open(pdf_path, "rb") as f:
                    file_data = f.read()
            except Exception as e:
                logger.error(f"Failed to read PDF for scan check: {e}")
                file_data = b""
                
            if is_scanned_pdf(file_data, char_threshold=TEXT_MIN_LENGTH):
                logger.info(
                    f"[OCR-FALLBACK] scanned_detected | file={os.path.basename(pdf_path)}"
                )
                text = self._extract_with_ocr_fallback(pdf_path)
            else:
                logger.info(
                    f"[OCR-FALLBACK] low_text_not_scanned | file={os.path.basename(pdf_path)} | accepting_as_is"
                )
        
        # === Stage 3: 品質検証 ===
        if not text or len(text.strip()) < TEXT_MIN_LENGTH:
            raise RuntimeError(
                f"PDF text extraction failed for {os.path.basename(pdf_path)}: "
                f"pdfplumber and OCR both returned insufficient text (<{TEXT_MIN_LENGTH} chars)"
            )
        return text

    def _extract_with_pdfplumber(self, pdf_path: str) -> str:
        """pdfplumber のみでテキスト抽出 (失敗時は空文字を返す)"""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                return "\n".join([p.extract_text() or "" for p in pdf.pages]).strip()
        except Exception as e:
            logger.error(f"Failed to extract text from {pdf_path}: {e}")
            return ""

    def _extract_with_ocr_fallback(self, pdf_path: str) -> str:
        """Tesseract/Azure OCR プロバイダーでテキスト抽出 (フォールバック用)"""
        logger.info(f"[OCR-FALLBACK] ocr_start | file={os.path.basename(pdf_path)}")
        provider = create_ocr_provider(self.ocr_config)

        if not provider.is_available():
            logger.error(
                f"[OCR-FALLBACK] provider_unavailable | file={os.path.basename(pdf_path)}"
            )
            from ocr.metrics import record_ocr_failure
            record_ocr_failure()
            return ""

        try:
            result = provider.extract_text(pdf_path)
        except Exception as e:
            logger.error(
                f"[OCR-FALLBACK] ocr_failed | file={os.path.basename(pdf_path)} | error={e}"
            )
            from ocr.metrics import record_ocr_failure
            record_ocr_failure()
            return ""

        if result.average_confidence < OCR_CONFIDENCE_MIN:
            logger.warning(
                f"[OCR-FALLBACK] low_confidence | file={os.path.basename(pdf_path)} | "
                f"confidence={result.average_confidence:.3f} < {OCR_CONFIDENCE_MIN}"
            )
        else:
            logger.info(
                f"[OCR-FALLBACK] ocr_done | file={os.path.basename(pdf_path)} | "
                f"confidence={result.average_confidence:.3f} | chars={len(result.full_text)}"
            )

        from ocr.metrics import record_fallback
        record_fallback(provider="tesseract", confidence=result.average_confidence)

        return result.full_text

    def analyze_and_save(self, pdf_path: str, source_url: str, agency_id: Optional[int] = None) -> Bid:
        """
        PDFのテキスト抽出 -> LLM要件定義解析 -> データベース保存 -> 顧客/パートナーマッチングの一連の処理を実行。
        """
        filename = os.path.basename(pdf_path)
        logger.info(f"Starting analysis and save pipeline for {filename}")

        # 1. テキスト抽出
        text = self.extract_text_from_pdf(pdf_path)

        # 2. LLM解析 (Gemini / DeepSeek フォールバック呼び出し)
        logger.info("Calling LLM Service for requirements extraction...")
        try:
            analysis_result = self.llm_service.analyze_with_fallback(text)
        except Exception as llm_err:
            logger.warning(f"LLM解析失敗（空欄フィールドで保存続行）: {llm_err}")
            analysis_result = {
                "budget": "記載なし",
                "qualifications": "記載なし",
                "deadline": "記載なし",
                "deliverables": "記載なし",
                "key_risks": [],
                "industry_category": "不明",
                "organization_name": "不明",
            }
        
        # 3. データの保存
        logger.info("Saving bid details to DB...")
        
        # source_url または filename をベースに UPSERT 処理を行う
        # 予算・納期・資格などの解析結果を更新し、重複レコードを防ぐ
        bid_data = {
            "filename": filename,
            "source_url": source_url,
        }
        # 解析結果を bid_data に追加
        bid, is_new = self.bid_repo.upsert(bid_data)

        # LLM解析結果のマッピング
        # すでに upsert で basic info は更新済みのため、解析詳細を更新
        bid.budget = str(analysis_result.get("budget", "記載なし"))
        
        # qualifications と key_risks はリストで返される場合があるため、JSON文字列化して格納
        quals = analysis_result.get("qualifications", [])
        if isinstance(quals, list):
            bid.qualifications = json.dumps(quals, ensure_ascii=False)
        else:
            bid.qualifications = str(quals)

        bid.deadline = str(analysis_result.get("deadline", "記載なし"))
        bid.deliverables = str(analysis_result.get("deliverables", "記載なし"))

        risks = analysis_result.get("key_risks", [])
        if isinstance(risks, list):
            bid.key_risks = json.dumps(risks, ensure_ascii=False)
        else:
            bid.key_risks = str(risks)

        # 追加の解析項目
        bid.industry_category = str(analysis_result.get("industry_category", "不明"))
        bid.organization_name = str(analysis_result.get("organization_name", "不明"))
        
        # 予算金額の数値化
        bid.budget_amount = parse_budget(bid.budget)
        bid.full_text = text
        bid.analyzed_at = datetime.utcnow()
        
        self.session.flush()

        # ステータス履歴の追加 (新規案件時のみ)
        if is_new:
            self.bid_repo.add_status_history(
                bid_id=bid.id,
                status="未確認",
                changed_by="system",
                memo="新着自治体クロール経由で自動検知"
            )

        # 4. マッチング処理の呼び出し
        self.match_customers_and_partners(bid)

        self.session.commit()
        logger.info(f"Bid analysis pipeline completed successfully for Bid ID: {bid.id}")
        return bid

    def match_customers_and_partners(self, bid: Bid):
        """
        新着案件とすべての顧客/パートナーの要件マッチングを行い、リンクを作成する。
        """
        logger.info(f"Running matches for Bid ID: {bid.id}")

        # 既存リンクの削除（再実行時の二重登録を防ぐ）
        self.session.query(CustomerBidLink).filter(CustomerBidLink.bid_id == bid.id).delete()
        self.session.query(PartnerBidLink).filter(PartnerBidLink.bid_id == bid.id).delete()

        # 検索対象となる案件のキーワード集合
        bid_text = f"{bid.filename} {bid.industry_category} {bid.organization_name} {bid.deliverables} {bid.qualifications} {bid.budget}"
        bid_text_lower = bid_text.lower()

        # 1. 顧客マッチング
        customers = self.customer_repo.list_all(limit=1000)
        for customer in customers:
            # 顧客のmemoやcompany名、nameをカンマやスペース等で簡易分割し、キーワードを抽出
            keywords = self._extract_matching_keywords(customer.memo, customer.company, customer.name)
            
            # マッチしたキーワードがあればリンクを生成
            matched_keys = [k for k in keywords if k in bid_text_lower]
            if matched_keys:
                memo = f"キーワードマッチ: {', '.join(matched_keys)}"
                link = CustomerBidLink(
                    customer_id=customer.id,
                    bid_id=bid.id,
                    memo=memo
                )
                self.session.add(link)
                logger.info(f"Customer Match: Customer {customer.name} (ID: {customer.id}) linked to Bid {bid.id}")

        # 2. パートナーマッチング
        partners = self.partner_repo.list_all(limit=1000)
        for partner in partners:
            keywords = self._extract_matching_keywords(partner.memo, partner.category, partner.name)
            
            matched_keys = [k for k in keywords if k in bid_text_lower]
            if matched_keys:
                memo = f"キーワードマッチ: {', '.join(matched_keys)}"
                link = PartnerBidLink(
                    partner_id=partner.id,
                    bid_id=bid.id,
                    memo=memo
                )
                self.session.add(link)
                logger.info(f"Partner Match: Partner {partner.name} (ID: {partner.id}) linked to Bid {bid.id}")

    def _extract_matching_keywords(self, memo: Optional[str], category_or_company: Optional[str], name: str) -> List[str]:
        """
        メモやカテゴリなどの属性テキストからマッチング用のキーワードリスト（小文字）を抽出するヘルパー。
        """
        words = []
        # メモやカテゴリからカンマ・読点・スペースで区切って単語を抽出
        for text in [memo, category_or_company]:
            if text:
                # 日本語の読点・カンマ、および半角全角スペース等で分割
                split_words = re.split(r'[,，、\s\n]+', text)
                for w in split_words:
                    w = w.strip().lower()
                    # 2文字以上のキーワードを採用（あまりに短いものはノイズになるため）
                    if len(w) >= 2:
                        words.append(w)
        
        # 固有名詞として会社名や名前も簡易チェック用に追加
        if name and len(name.strip()) >= 2:
            words.append(name.strip().lower())
            
        # 重複排除
        return list(set(words))
